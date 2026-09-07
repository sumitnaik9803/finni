"""
Cerebras key diagnostic — answers "is my key live, is the model id right, and will
the fallback chain actually reach it?"

    python scripts/check_cerebras.py            # reads CEREBRAS_API_KEY from the environment
    python scripts/check_cerebras.py csk-xxx    # or pass the key directly

Why this exists: Cerebras is the LAST entry in LLM_PROVIDER_ORDER, so a normal
pipeline run never calls it — Gemini and Groq serve everything long before the chain
gets that far. That is the point of a tail provider, and also its danger: a bad key or
a renamed model would sit undetected until the day Groq is exhausted and you actually
need it. A full run is not a test of this; this is.

Unlike check_gemini.py, this imports the pipeline on purpose. It drives the real
_call_cerebras and the real complete_json, so a pass here means the shipped code path
works — not that a reimplementation of it does. Nothing here writes to the pipeline.
"""

import asyncio
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import (  # noqa: E402
    CEREBRAS_MAX_TOKENS,
    CEREBRAS_MODEL,
    CEREBRAS_URL,
    CEREBRAS_USER_AGENT,
    LLM_PROVIDER_ORDER,
)
from src.llm_scorer import LLMScorer  # noqa: E402
from src.telemetry import telemetry  # noqa: E402

MODELS_URL = "https://api.cerebras.ai/v1/models"

PROMPT = (
    "Score this headline for Tata Steel. Reply with ONLY a JSON array of one object "
    'with keys id, sentiment_score (-1.0 to 1.0), sentiment_label, confidence, '
    "impact_magnitude, reasoning.\n\n"
    "1. Tata Steel Q2 profit rises 18% on higher domestic volumes"
)


def _get(url: str, key: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {key}",
        # Cloudflare bans python-urllib's default UA before Cerebras ever sees the
        # request. Same header the pipeline sends — see CEREBRAS_USER_AGENT.
        "User-Agent": CEREBRAS_USER_AGENT,
    })
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # network, DNS, TLS
        return 0, f"{type(e).__name__}: {e}"


def main() -> int:
    key = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CEREBRAS_API_KEY", "")
    if not key:
        print("No key. Pass it as an argument or set CEREBRAS_API_KEY.")
        print('  PowerShell:  $env:CEREBRAS_API_KEY = "csk-..."')
        return 2
    os.environ["CEREBRAS_API_KEY"] = key

    print(f"key: {key[:8]}...{key[-4:]}  ({len(key)} chars)")
    print(f"configured model: {CEREBRAS_MODEL}")
    print(f"provider order:   {' -> '.join(LLM_PROVIDER_ORDER)}\n")

    # ── 1. Which models does this key actually reach? ────────────────────────────
    status, body = _get(MODELS_URL, key)
    print(f"[1] GET /v1/models            -> HTTP {status}")
    available: list[str] = []
    if status == 200:
        try:
            available = sorted(m["id"] for m in json.loads(body).get("data", []))
        except Exception as e:
            print(f"    could not parse model list: {e}")
        print(f"    {len(available)} models visible:")
        for m in available:
            mark = "  <-- configured" if m == CEREBRAS_MODEL else ""
            print(f"      {m}{mark}")
    else:
        print(f"    {body[:400]}")
        if "1010" in body or "error code:" in body:
            # A bare Cloudflare string, not Cerebras JSON — the request was blocked
            # before it reached the API, so this says nothing about the key.
            print("\n    That is Cloudflare, not Cerebras: error 1010 means the "
                  "request's User-Agent was banned, so it never reached the API. "
                  "Your key has NOT been tested. Check CEREBRAS_USER_AGENT is being "
                  "sent on this request.")
            return 1
        if status in (401, 403):
            print("\n    The key was rejected by Cerebras itself. Check it was copied "
                  "whole, and that the account is on a tier with API access.")
            return 1

    if available and CEREBRAS_MODEL not in available:
        print(f"\n    !! CEREBRAS_MODEL = {CEREBRAS_MODEL!r} is NOT in that list.")
        near = [m for m in available if "oss" in m or "120" in m] or available
        print(f"       Closest candidates: {', '.join(near[:5])}")
        print("       Fix the one line in src/config.py before relying on this provider.")

    # ── 2. Does the real _call_cerebras path work end to end? ────────────────────
    scorer = LLMScorer()
    print(f"\n[2] _call_cerebras()          -> available={scorer._cerebras_available}")
    if not scorer._cerebras_available:
        print("    Scorer reports Cerebras unavailable — the key was not picked up.")
        return 1

    try:
        text = asyncio.run(scorer._call_cerebras(PROMPT))
        print(f"    HTTP 200, {len(text)} chars returned")
        print(f"    raw: {text[:200].strip()}")
    except Exception as e:
        print(f"    FAILED: {e}")
        return 1

    # ── 3. Does it parse the way the pipeline needs? ─────────────────────────────
    try:
        parsed = scorer._parse_response(text, expect_array=True)
        item = parsed[0] if isinstance(parsed, list) and parsed else parsed
        print(f"\n[3] _parse_response()         -> OK")
        print(f"    score={item.get('sentiment_score')} "
              f"label={item.get('sentiment_label')} "
              f"confidence={item.get('confidence')}")
    except Exception as e:
        print(f"\n[3] _parse_response()         -> FAILED: {e}")
        print("    The model answered but not as usable JSON. Check the model id, or "
              f"whether {CEREBRAS_MAX_TOKENS} output tokens is enough for a batch.")
        return 1

    # ── 4. Will the chain actually fall through to it? ───────────────────────────
    # Simulate the only day this provider matters: Gemini and Groq both spent.
    chain = LLMScorer()
    chain._gemini_available = False
    chain._groq_available = False
    result = asyncio.run(chain.complete_json(PROMPT, expect_array=True))
    print("\n[4] fallback chain            -> ", end="")
    if result is None:
        print("FAILED — complete_json returned None with only Cerebras left")
        return 1
    _, provider = result
    print(f"served by {provider!r}")
    if provider != "cerebras":
        print(f"    Expected 'cerebras'. Check LLM_PROVIDER_ORDER: {LLM_PROVIDER_ORDER}")
        return 1

    print(telemetry.render())
    print("\nAll four checks passed. Cerebras will take over when Groq is exhausted.")
    print(f"Endpoint: {CEREBRAS_URL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
