"""The teacher: Claude labels a batch of abstracts (the "oracle").

Batches many abstracts into one call for cost efficiency, and asks for
strict JSON back. Falls back to a keyword heuristic in --mock mode so you
can run the whole pipeline locally before wiring up an API key.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"

# Only used by mock mode so you can test with zero cost / no key.
_MOCK_KEYWORDS = (
    "language model", "llm", "gpt", "transformer", "agent",
    "retrieval-augmented", "rag", "in-context", "prompt", "chatbot",
)


def _mock_label(text: str) -> int:
    low = text.lower()
    return int(any(k in low for k in _MOCK_KEYWORDS))


def label_batch(papers: list[dict], task_question: str, model: str,
                mock: bool = False) -> dict[str, int]:
    """Return {paper_id: 0|1} for the batch."""
    if mock or not os.environ.get("ANTHROPIC_API_KEY"):
        return {p["id"]: _mock_label(p["text"]) for p in papers}

    numbered = "\n".join(f'{i}. (id={p["id"]}) {p["text"][:600]}'
                         for i, p in enumerate(papers))
    prompt = (
        f"You are labeling arXiv abstracts for one yes/no question:\n"
        f"QUESTION: {task_question}\n\n"
        f"For each abstract below, answer 1 for yes, 0 for no.\n"
        f"Return ONLY a JSON array like "
        f'[{{"id": "2401.01234", "label": 1}}, ...] with no other text.\n\n'
        f"{numbered}"
    )
    body = json.dumps({
        "model": model,
        "max_tokens": 1500,
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
    except urllib.error.HTTPError as e:
        # Surface the API's actual error message (e.g. an invalid model name)
        detail = e.read().decode("utf-8", "replace")
        raise RuntimeError(
            f"Anthropic API returned HTTP {e.code}. Details:\n{detail}\n\n"
            f"If this says the model was not found, update 'teacher_model' in "
            f"config.yaml to a current model from "
            f"https://docs.claude.com/en/docs/about-claude/models"
        ) from None

    text = "".join(b.get("text", "") for b in data.get("content", []))
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError(f"Could not parse label JSON from response:\n{text[:400]}")
    rows = json.loads(match.group(0))
    labels = {str(r["id"]): int(r["label"]) for r in rows}
    # Any the model skipped default to 0 so downstream code stays simple.
    return {p["id"]: labels.get(p["id"], 0) for p in papers}