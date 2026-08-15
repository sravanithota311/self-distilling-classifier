"""A tiny HTTP-POST helper with retry-on-transient-error.

Gemini (like any web API) occasionally returns 503 "overloaded" or 429
"rate limited" — temporary conditions that usually clear in a few seconds.
This retries those with exponential backoff (waits 2s, 4s, 8s...) up to a
bounded number of attempts, then gives up with a clear error.

It does NOT retry permanent errors (bad model = 404, bad key = 401/403),
since those would fail identically every time.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

# HTTP codes worth retrying — transient "try again later" conditions.
_RETRYABLE = {429, 500, 502, 503, 504}


def post_json(url: str, payload: dict, headers: dict,
              timeout: int = 120, max_attempts: int = 5) -> dict:
    """POST JSON and return the parsed JSON response, retrying transient errors.

    Raises RuntimeError with the API's own message on a permanent failure or
    after exhausting retries.
    """
    body = json.dumps(payload).encode()
    delay = 2.0
    last_detail = ""

    for attempt in range(1, max_attempts + 1):
        req = urllib.request.Request(url, data=body, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            last_detail = e.read().decode("utf-8", "replace")
            if e.code in _RETRYABLE and attempt < max_attempts:
                print(f"      API busy (HTTP {e.code}) — retry "
                      f"{attempt}/{max_attempts - 1} in {delay:.0f}s...")
                time.sleep(delay)
                delay *= 2  # exponential backoff
                continue
            # permanent error, or out of retries
            raise RuntimeError(
                f"API returned HTTP {e.code}. Details:\n{last_detail}"
            ) from None
        except urllib.error.URLError as e:
            # network hiccup — also transient
            if attempt < max_attempts:
                print(f"      network error ({e.reason}) — retry "
                      f"{attempt}/{max_attempts - 1} in {delay:.0f}s...")
                time.sleep(delay)
                delay *= 2
                continue
            raise RuntimeError(f"Network error after {max_attempts} attempts: {e.reason}") from None

    raise RuntimeError(f"Failed after {max_attempts} attempts. Last detail:\n{last_detail}")
