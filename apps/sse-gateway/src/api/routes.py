from fastapi import APIRouter

router = APIRouter()

@router.get("/healthz/live")
def liveness() -> dict[str, str]:
    return {"status": "live"}

@router.get("/healthz/ready")
def readiness() -> dict[str, str]:
    return {"status": "ready"}


@router.get("/healthz/info")
def deployment_info() -> dict[str, str]:
    import os
    info: dict = {"service": "sse-gateway"}
    if os.getenv("APP_ENV", "development") == "development":
        info["app_env"] = "development"
        info["deployment_profile"] = os.getenv("DEPLOYMENT_PROFILE", "local")
    return info

