"""Lightweight Prometheus text parser — parses /metrics output from Keviq Core services.

Only supports the subset of Prometheus text format emitted by MetricsRegistry:
- Counter lines: metric_name{label="value",...} numeric_value
- Label-less counters: metric_name numeric_value
- Ignores # HELP and # TYPE lines

NOT a full Prometheus parser — intentionally minimal for O8-S3.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MetricSample:
    """A single parsed metric sample."""
    metric_name: str
    labels: dict[str, str]
    value: float


# Pattern: metric_name{key="val",key2="val2"} 123.45
_METRIC_WITH_LABELS = re.compile(
    r'^([a-zA-Z_][a-zA-Z0-9_]*)\{(.+?)\}\s+([0-9eE.+-]+)$'
)

# Pattern: metric_name 123.45  (no labels)
_METRIC_NO_LABELS = re.compile(
    r'^([a-zA-Z_][a-zA-Z0-9_]*)\s+([0-9eE.+-]+)$'
)

# Pattern: key="value" within label set
_LABEL_PAIR = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="([^"]*)"')


def parse_prometheus_text(text: str) -> list[MetricSample]:
    """Parse Prometheus text exposition format into MetricSample list.

    Skips comment lines (# HELP, # TYPE) and blank lines.
    Returns empty list on empty/invalid input.
    """
    samples: list[MetricSample] = []

    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        # Try with labels first
        m = _METRIC_WITH_LABELS.match(line)
        if m:
            name = m.group(1)
            labels_str = m.group(2)
            value = float(m.group(3))
            labels = dict(_LABEL_PAIR.findall(labels_str))
            samples.append(MetricSample(metric_name=name, labels=labels, value=value))
            continue

        # Try without labels
        m = _METRIC_NO_LABELS.match(line)
        if m:
            name = m.group(1)
            value = float(m.group(2))
            samples.append(MetricSample(metric_name=name, labels={}, value=value))

    return samples
