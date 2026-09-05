"""
Gemini key diagnostic — answers "is my key working, and on which endpoint?"

Run it before blaming the pipeline:

    python scripts/check_gemini.py          # reads GEMINI_API_KEY from the environment
    python scripts/check_gemini.py AQ.xxx   # or pass the key directly

It reports the key format, lists the models the key can actually reach, and calls
both API surfaces (Interactions and the legacy generateContent) so you can see
exactly which one your key is accepted on. Nothing here writes to the pipeline.
"""

import json
import sys
import urllib.error
import urllib.request

MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
GENERATECONTENT_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


def _request(url: str, key: str, payload: dict | None = None) -> tuple[int, str]:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        method="POST" if data else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:  # DNS, TLS, timeout
        return 0, str(e)


def main() -> int:
    key = sys.argv[1] if len(sys.argv) > 1 else __import__("os").environ.get("GEMINI_API_KEY", "")
    if not key:
        print("No key. Pass it as an argument or set GEMINI_API_KEY.")
        return 1

    kind = "auth key (current format)" if key.startswith("AQ.") else (
        "standard key (being retired by Google)" if key.startswith("AIza") else "unrecognised format"
    )
    print(f"Key: {key[:7]}... — {kind}\n")

    # 1. Which models can this key see?
    status, body = _request(MODELS_URL, key)
    print(f"[1] list models        -> HTTP {status}")
    model = "gemini-2.5-flash"
    if status == 200:
        names = [
            (m.get("name") or "").removeprefix("models/")
            for m in json.loads(body).get("models", [])
        ]
        flash = [n for n in names if "flash" in n and "thinking" not in n]
        print(f"    {len(names)} models visible; flash models: {', '.join(flash[:8]) or 'none'}")
        if flash:
            model = flash[0]
    else:
        print(f"    {body[:300]}")

    print(f"\n    testing generation with: {model}\n")

    # 2. Interactions API — the surface AQ. auth keys are documented against.
    status, body = _request(
        INTERACTIONS_URL, key, {"model": model, "input": "Reply with the single word OK."}
    )
    print(f"[2] interactions       -> HTTP {status}")
    print(f"    {body[:300]}\n")

    # 3. Legacy generateContent — works with AIza keys, 401s on AQ. keys.
    status, body = _request(
        GENERATECONTENT_URL.format(model=model),
        key,
        {"contents": [{"parts": [{"text": "Reply with the single word OK."}]}]},
    )
    print(f"[3] generateContent    -> HTTP {status}")
    print(f"    {body[:300]}")

    print(
        "\nWhichever of [2] or [3] returned 200 is the surface Finni will use — "
        "it tries Interactions first and falls back automatically."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
