"""Fetch the latest arXiv abstracts for a category.

No API key needed — arXiv has a free public API. We dedupe against IDs
we've already labeled so every run works on genuinely new data.
"""
from __future__ import annotations

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

ARXIV_API = "http://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"


def fetch_recent(category: str, max_results: int, seen_ids: set[str]) -> list[dict]:
    """Return up to `max_results` recent papers not already in `seen_ids`.

    Each item: {"id": str, "title": str, "text": str}
    """
    # Over-fetch a bit so that after removing already-seen papers we still
    # have a full batch.
    query = {
        "search_query": f"cat:{category}",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "start": 0,
        "max_results": max_results * 3,
    }
    url = f"{ARXIV_API}?{urllib.parse.urlencode(query)}"
    with urllib.request.urlopen(url, timeout=60) as resp:
        raw = resp.read()

    root = ET.fromstring(raw)
    out: list[dict] = []
    for entry in root.findall(f"{ATOM}entry"):
        arxiv_id = entry.findtext(f"{ATOM}id", "").strip()
        # normalize e.g. http://arxiv.org/abs/2401.01234v1 -> 2401.01234
        short = arxiv_id.rsplit("/", 1)[-1].split("v")[0]
        if not short or short in seen_ids:
            continue
        title = (entry.findtext(f"{ATOM}title", "") or "").strip().replace("\n", " ")
        summary = (entry.findtext(f"{ATOM}summary", "") or "").strip().replace("\n", " ")
        out.append({"id": short, "title": title, "text": f"{title}. {summary}"})
        if len(out) >= max_results:
            break
    return out


if __name__ == "__main__":
    papers = fetch_recent("cs.CL", 5, set())
    for p in papers:
        print(p["id"], "-", p["title"][:80])
