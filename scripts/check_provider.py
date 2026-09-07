"""
Tail-provider diagnostic — "is my key live, is the model id right, and will the
fallback chain actually reach it?"

    python scripts/check_provider.py mistral            # reads MISTRAL_API_KEY from the env
    python scripts/check_provider.py mistral xxxxxxxx   # or pass the key directly
    python scripts/check_provider.py cerebras csk-...   # works for any registered provider

Why this exists: tail providers sit LAST in LLM_PROVIDER_ORDER, so a normal pipeline
run never calls them — Gemini and Groq serve everything long before the chain gets
that far. That is the point of a tail provider, and also its danger: a bad key, a
renamed model or a blocked User-Agent stays invisible until the day the providers
ahead are exhausted and you actually need it. A full run is not a test of this path;
this is. It has already caught two such faults.

Unlike check_gemini.py, this imports the pipeline on purpose. It drives the real
_call_openai_compatible, _parse_response and complete_json, so a pass means the
shipped code path works — not that a reimplementation of it does. Nothing here
writes to the pipeline.
"""

import asyncio
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import (  # noqa: E402
    LLM_PROVIDER_ORDER,
    OPENAI_COMPATIBLE_PROVIDERS,
)
from src.llm_scorer import LLMScorer  # noqa: E402
from src.telemetry import telemetry  # noqa: E402

PROMPT = (
    "Score this headline for Tata Steel. Reply with ONLY a JSON array of one object "
    "with keys id, sentiment_score (-1.0 to 1.0), sentiment_label, confidence, "
    "impact_magnitude, reasoning.\n\n"
    "1. Tata Steel Q2 profit rises 18% on higher domestic volumes"
)


def _get(url: str, key: str, user_agent: str | None) -> tuple[int, str]:
    headers = {"Authorization": f"Bearer {key}"}
    if user_agent:
        headers["User-Agent"] = user_agent
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers=headers), timeout=45
        ) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # network, DNS, TLS
        return 0, f"{type(e).__name__}: {e}"


def main() -> int:
    known = ", ".join(sorted(OPENAI_COMPATIBLE_PROVIDERS))
    if len(sys.argv) < 2 or sys.argv[1] not in OPENAI_COMPATIBLE_PROVIDERS:
        print(f"Usage: python scripts/check_provider.py <provider> [key]")
        print(f"Registered providers: {known}")
        return 2

    provider = sys.argv[1]
    spec = OPENAI_COMPATIBLE_PROVIDERS[provider]
    env_var = spec["key_env"]

    key = sys.argv[2] if len(sys.argv) > 2 else os.environ.get(env_var, "")
    if not key:
        print(f"No key. Pass it as an argument or set {env_var}.")
        print(f'  PowerShell:  $env:{env_var} = "..."')
        return 2
    os.environ[env_var] = key

    in_chain = provider in LLM_PROVIDER_ORDER
    print(f"provider: {provider}")
    print(f"key:      {key[:6]}...{key[-4:]}  ({len(key)} chars)")
    print(f"model:    {spec['model']}")
    print(f"order:    {' -> '.join(LLM_PROVIDER_ORDER)}"
          f"{'' if in_chain else f'   [!] {provider} is NOT in the chain'}\n")

    # ── 1. Which models does this key actually reach? ────────────────────────────
    status, body = _get(spec["models_url"], key, spec.get("user_agent"))
    print(f"[1] GET /v1/models            -> HTTP {status}")
    available: list[str] = []
    if status == 200:
        try:
            available = sorted(m["id"] for m in json.loads(body).get("data", []))
        except Exception as e:
            print(f"    could not parse model list: {e}")
        print(f"    {len(available)} models visible"
              f"{' (showing 40)' if len(available) > 40 else ''}:")
        for m in available[:40]:
            print(f"      {m}{'  <-- configured' if m == spec['model'] else ''}")
    else:
        print(f"    {body[:400]}")
        if "1010" in body or "error code:" in body:
            # A bare Cloudflare string, not provider JSON — the request was blocked
            # before it reached the API, so this says nothing about the key.
            print(f"\n    That is Cloudflare, not {provider}: error 1010 means the "
                  "request's User-Agent was banned, so it never reached the API. "
                  'Your key has NOT been tested — set a "user_agent" on this '
                  "provider in OPENAI_COMPATIBLE_PROVIDERS.")
            return 1
        if status in (401, 403):
            print(f"\n    The key was rejected by {provider} itself. Check it was "
                  "copied whole, and that the account has API access.")
            return 1

    if available and spec["model"] not in available:
        print(f"\n    !! model {spec['model']!r} is NOT in that list.")
        print(f"       Fix the entry in src/config.py before relying on this provider.")

    # ── 2. Does the real call path work end to end? ──────────────────────────────
    scorer = LLMScorer()
    print(f"\n[2] _call_openai_compatible() -> available="
          f"{scorer._oai_available.get(provider)}")
    if not scorer._oai_available.get(provider):
        print(f"    Scorer reports {provider} unavailable — key not picked up.")
        return 1

    try:
        text = asyncio.run(scorer._call_openai_compatible(provider, PROMPT))
        print(f"    HTTP 200, {len(text)} chars returned")
        print(f"    raw: {text[:200].strip()}")
    except Exception as e:
        print(f"    FAILED: {e}")
        if "402" in str(e):
            print("\n    402 means the account has no inference quota — the key is "
                  "valid but the plan does not include API inference.")
        return 1

    # ── 3. Does it parse the way the pipeline needs? ─────────────────────────────
    try:
        parsed = scorer._parse_response(text, expect_array=True)
        item = parsed[0] if isinstance(parsed, list) and parsed else parsed
        print("\n[3] _parse_response()         -> OK")
        print(f"    score={item.get('sentiment_score')} "
              f"label={item.get('sentiment_label')} "
              f"confidence={item.get('confidence')}")
    except Exception as e:
        print(f"\n[3] _parse_response()         -> FAILED: {e}")
        print("    The model answered but not as usable JSON. Check the model id, or "
              f"whether {spec['max_tokens']} output tokens is enough for a batch.")
        return 1

    # ── 4. Will the chain actually fall through to it? ───────────────────────────
    # Simulate the only day this provider matters: everything ahead of it spent.
    chain = LLMScorer()
    chain._gemini_available = False
    chain._groq_available = False
    for other in chain._oai_available:
        chain._oai_available[other] = (other == provider)
    result = asyncio.run(chain.complete_json(PROMPT, expect_array=True))
    print("\n[4] fallback chain            -> ", end="")
    if result is None:
        print(f"FAILED — complete_json returned None with only {provider} left")
        return 1
    _, served_by = result
    print(f"served by {served_by!r}")
    if served_by != provider:
        print(f"    Expected {provider!r}. Check LLM_PROVIDER_ORDER: {LLM_PROVIDER_ORDER}")
        return 1

    print(telemetry.render())
    print(f"\nAll four checks passed. {provider} will take over when Groq is exhausted.")
    if not in_chain:
        print(f"NOTE: {provider} is not in LLM_PROVIDER_ORDER, so the pipeline will "
              "never call it until you add it there.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
