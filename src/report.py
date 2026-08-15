"""The reporter: an LLM writes a plain-English report on what happened this run.

Uses Gemini (free tier) with the same retry-on-transient-error behavior.
Falls back to a template if no API key is set or the call fails.
"""
from __future__ import annotations

import json
import os

try:
    from . import http_client
except ImportError:
    import http_client

API_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _fallback(metrics: dict) -> str:
    verdict = "promoted" if metrics["promoted"] else "kept the incumbent"
    return (
        f"# Retrain report — {metrics['timestamp']}\n\n"
        f"- New batch: {metrics['batch_size']} papers\n"
        f"- Positive rate (teacher): {metrics['positive_rate']:.0%}\n"
        f"- Challenger agreement: {metrics['challenger_agreement']:.1%}\n"
        f"- Champion agreement: {metrics['champion_agreement']:.1%}\n"
        f"- Decision: **{verdict}**\n"
        f"- Agreement drift vs recent avg: {metrics['agreement_drift']:+.3f}\n"
        f"- New-vocabulary rate: {metrics['vocabulary_drift']:.0%}\n"
    )


def write_report(metrics: dict, model: str, use_llm: bool = False) -> str:
    if not use_llm or not os.environ.get("GEMINI_API_KEY"):
        return _fallback(metrics)

    prompt = (
        "You are the ML engineer on call. Write a short (120-word max) markdown "
        "changelog for this self-retraining run. Explain in plain English whether "
        "the model improved, whether the data drifted, and what you'd watch next. "
        "Start with an H1 title. Here are the metrics:\n\n"
        f"{json.dumps(metrics, indent=2)}"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {
        "content-type": "application/json",
        "x-goog-api-key": os.environ["GEMINI_API_KEY"],
    }
    try:
        data = http_client.post_json(API_TMPL.format(model=model), payload, headers)
        parts = (data.get("candidates", [{}])[0]
                     .get("content", {})
                     .get("parts", []))
        text = "".join(p.get("text", "") for p in parts)
        return text or _fallback(metrics)
    except Exception as e:  # never let reporting crash the pipeline
        return _fallback(metrics) + f"\n\n> (report model unavailable: {e})\n"
