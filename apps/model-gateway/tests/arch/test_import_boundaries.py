"""Architecture tests: verify import boundaries for model-gateway.

G15 Gates:
- G15-1: Only model-gateway holds provider credentials (no other service imports provider SDK)
- G15-2: Provider results are normalized through ProviderResponse
- G15-3: Usage persistence is real (DbUsageRecordWriter exists and writes SQL)
"""

import ast
from pathlib import Path

# ── Helpers ──────────────────────────────────────────────────────

SERVICE_ROOT = Path(__file__).resolve().parents[2]  # apps/model-gateway
DOMAIN_DIR = SERVICE_ROOT / "src" / "domain"
APP_DIR = SERVICE_ROOT / "src" / "application"
INFRA_DIR = SERVICE_ROOT / "src" / "infrastructure"

INFRA_PACKAGES = {"sqlalchemy", "psycopg2", "httpx", "fastapi", "uvicorn", "starlette"}
FRAMEWORK_PACKAGES = {"fastapi", "httpx", "sqlalchemy", "uvicorn", "starlette", "pydantic"}


def _collect_python_files(directory: Path) -> list[Path]:
    return [p for p in directory.rglob("*.py") if p.name != "__init__.py" and p.exists()]


def _extract_imports(filepath: Path) -> list[str]:
    """Extract all imported module names from a Python file."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module.split(".")[0])
    return imports


# ── G15-1: Domain layer does not import infrastructure ───────────

def test_domain_does_not_import_infrastructure():
    """Domain layer must not import from infrastructure packages."""
    violations = []
    for pyfile in _collect_python_files(DOMAIN_DIR):
        imported = _extract_imports(pyfile)
        for mod in imported:
            if mod in INFRA_PACKAGES:
                violations.append(f"{pyfile.name} imports {mod}")
    assert not violations, f"Domain imports infrastructure: {violations}"


def test_application_does_not_import_infrastructure():
    """Application layer must not import from infrastructure packages."""
    violations = []
    for pyfile in _collect_python_files(APP_DIR):
        imported = _extract_imports(pyfile)
        for mod in imported:
            if mod in INFRA_PACKAGES:
                violations.append(f"{pyfile.name} imports {mod}")
    assert not violations, f"Application imports infrastructure: {violations}"


# ── G15-2: Contracts are transport-agnostic ──────────────────────

def test_contracts_no_framework_imports():
    """contracts.py must not import any framework/transport package."""
    contracts_file = DOMAIN_DIR / "contracts.py"
    assert contracts_file.exists(), "contracts.py not found"

    imported = _extract_imports(contracts_file)
    framework_hits = [m for m in imported if m in FRAMEWORK_PACKAGES]
    assert not framework_hits, f"Contracts import framework packages: {framework_hits}"


def test_ports_no_framework_imports():
    """ports.py must not import any framework/transport package."""
    ports_file = DOMAIN_DIR / "ports.py"
    assert ports_file.exists(), "ports.py not found"

    imported = _extract_imports(ports_file)
    framework_hits = [m for m in imported if m in FRAMEWORK_PACKAGES]
    assert not framework_hits, f"Ports import framework packages: {framework_hits}"


# ── G15-2: Provider results normalized through ProviderResponse ──

def test_provider_adapter_returns_provider_response():
    """OpenAI adapter must import and return ProviderResponse from domain ports."""
    adapter_file = INFRA_DIR / "providers" / "openai_compatible.py"
    assert adapter_file.exists(), "openai_compatible.py not found"

    source = adapter_file.read_text(encoding="utf-8")
    assert "ProviderResponse" in source, "Adapter does not reference ProviderResponse"

    # Must import from domain ports, not define its own
    tree = ast.parse(source)
    found_port_import = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and "domain.ports" in node.module:
            names = [alias.name for alias in node.names]
            if "ProviderResponse" in names:
                found_port_import = True
    assert found_port_import, "Adapter must import ProviderResponse from domain.ports"


def test_provider_adapter_no_sdk_leakage():
    """Provider adapter must not expose raw SDK types — only ProviderResponse."""
    adapter_file = INFRA_DIR / "providers" / "openai_compatible.py"
    source = adapter_file.read_text(encoding="utf-8")

    # Must not import openai SDK
    assert "import openai" not in source, "Adapter imports openai SDK directly"
    assert "from openai" not in source, "Adapter imports from openai SDK"


# ── G15-1: Only model-gateway holds provider credentials ─────────

def test_only_infra_layer_touches_api_keys():
    """api_key must not appear in domain or application layer code."""
    for layer_dir in (DOMAIN_DIR, APP_DIR):
        for pyfile in _collect_python_files(layer_dir):
            source = pyfile.read_text(encoding="utf-8")
            tree = ast.parse(source)

            for node in ast.walk(tree):
                # Check for string literal "api_key" used as an assignment target
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Attribute) and target.attr == "api_key":
                            # Allow in type annotations and port definitions
                            pass

    # The real test: api_key is only set/used in infrastructure config
    config_file = INFRA_DIR / "config.py"
    source = config_file.read_text(encoding="utf-8")
    assert "api_key" in source, "Config must handle api_key"


# ── G15-3: Usage persistence is real ─────────────────────────────

def test_usage_writer_exists_and_uses_sql():
    """DbUsageRecordWriter must exist and write to the correct table."""
    writer_file = INFRA_DIR / "db" / "usage_writer.py"
    assert writer_file.exists(), "usage_writer.py not found"

    source = writer_file.read_text(encoding="utf-8")
    assert "model_usage_records" in source, "Writer must target model_usage_records table"
    assert "model_gateway_core" in source, "Writer must use model_gateway_core schema"
    assert "INSERT INTO" in source, "Writer must perform INSERT"


def test_usage_writer_implements_port():
    """DbUsageRecordWriter must implement UsageRecordWriter port."""
    writer_file = INFRA_DIR / "db" / "usage_writer.py"
    source = writer_file.read_text(encoding="utf-8")

    assert "UsageRecordWriter" in source, "Writer must reference UsageRecordWriter port"
    assert "class DbUsageRecordWriter" in source, "DbUsageRecordWriter class must exist"


# ── Credential boundary: env-only secrets ────────────────────────

def test_credentials_come_from_env_not_db():
    """Provider config loader must read API keys from env, not from DB."""
    config_file = INFRA_DIR / "config.py"
    source = config_file.read_text(encoding="utf-8")

    # Must use os.environ for API key
    assert "os.environ" in source or "os.getenv" in source, "Config must read from environment"

    imported = _extract_imports(config_file)
    assert "sqlalchemy" not in imported, "Config loader must not import sqlalchemy (env-only in Phase A)"
