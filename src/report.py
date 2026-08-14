"""Claude writes a plain-English report on what happened this run.

Turns the raw metrics dict into a short markdown changelog a human (or a
recruiter reading your repo) can actually understand. Falls back to a
template if no API key is set.
"""
from __future__ import annotations

import json
import os
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"


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


def write_report(metrics: dict, model: str) -> str:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _fallback(metrics)

    prompt = (
        "You are the ML engineer on call. Write a short (120-word max) markdown "
        "changelog for this self-retraining run. Explain in plain English whether "
        "the model improved, whether the data drifted, and what you'd watch next. "
        "Start with an H1 title. Here are the metrics:\n\n"
        f"{json.dumps(metrics, indent=2)}"
    )
    body = json.dumps({
        "model": model,
        "max_tokens": 500,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        API_URL, data=body, method="POST",
        headers={
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        return "".join(b.get("text", "") for b in data.get("content", []))
    except Exception as e:  # never let reporting crash the pipeline
        return _fallback(metrics) + f"\n\n> (report model unavailable: {e})\n"
