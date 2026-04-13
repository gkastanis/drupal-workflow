#!/usr/bin/env python3
"""Shared utilities for session-analysis scripts."""
import sys
from datetime import datetime, timezone
from pathlib import Path

# Per-MTok pricing: (input, output, cache_create, cache_read)
MODEL_PRICING = {
    "claude-opus-4-6": (15.0, 75.0, 18.75, 1.50),
    "claude-sonnet-4-6": (3.0, 15.0, 3.75, 0.30),
    "claude-haiku-4-5": (0.80, 4.0, 1.0, 0.08),
}
# Default to opus pricing for unknown models
_DEFAULT_PRICING = MODEL_PRICING["claude-opus-4-6"]


def warn(msg):
    print(f"warning: {msg}", file=sys.stderr)


def dt(obj):
    """Extract timezone-aware datetime from any event object or raw ISO string."""
    if obj is None:
        return None
    # Accept a raw string directly
    if isinstance(obj, str):
        value = obj
    elif isinstance(obj, dict):
        value = obj.get("timestamp") or obj.get("snapshot", {}).get("timestamp")
    else:
        return None
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def jsonl_files(path):
    """List .jsonl files from a file path or directory."""
    p = Path(path)
    if p.is_file():
        return [p]
    if p.is_dir():
        return sorted(x for x in p.iterdir() if x.is_file() and x.suffix == ".jsonl")
    raise FileNotFoundError(path)


def parts(content):
    """Normalize message content to a list of dicts."""
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return [p for p in content if isinstance(p, dict)]
    return []


def model_cost(model, input_tok, output_tok, cache_create_tok, cache_read_tok):
    """Compute cost in USD given token counts for a specific model."""
    p_in, p_out, p_cc, p_cr = MODEL_PRICING.get(model, _DEFAULT_PRICING)
    return (
        input_tok * p_in
        + output_tok * p_out
        + cache_create_tok * p_cc
        + cache_read_tok * p_cr
    ) / 1_000_000.0
