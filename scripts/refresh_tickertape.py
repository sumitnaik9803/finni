"""
Re-resolve every tracked stock's Tickertape URL and report what changed.

Tickertape keys its pages on its own security id, not the NSE symbol — JSWSTEEL
is JSTL, HCLTECH is HCLT, Tata Steel is TISC — so TICKERTAPE_SLUGS in config.py
is a resolved mapping rather than something derivable. Run this after adding a
company, or if a link starts 404ing:

    python scripts/refresh_tickertape.py

It prints a ready-to-paste TICKERTAPE_SLUGS block for anything that moved. It
only reports; it never edits config.py.
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, ".")

from src.config import COMPANIES, TICKERTAPE_SLUGS, get_tickertape_url

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
_JSON = {"User-Agent": _UA, "Accept": "application/json, text/plain, */*"}
_HTML = {"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml"}


def search(text: str) -> list[dict]:
    url = ("https://api.tickertape.in/search?"
           + urllib.parse.urlencode({"text": text, "types": "stock"}))
    with urllib.request.urlopen(urllib.request.Request(url, headers=_JSON), timeout=30) as r:
        payload = json.loads(r.read().decode("utf-8", "replace"))
    return (payload.get("data") or {}).get("stocks") or []


def resolve(symbol: str, name: str, short: str) -> str | None:
    """The slug whose NSE ticker matches ours exactly, or None."""
    for query in (symbol, short, name):
        try:
            hits = search(query)
        except Exception:
            continue
        for hit in hits:
            if (hit.get("ticker") or "").upper() == symbol.upper():
                return hit.get("slug")
        time.sleep(0.2)
    return None


def status(url: str):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=_HTML), timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return f"ERR {type(e).__name__}"


def main() -> int:
    changed, unresolved, broken = {}, [], []

    for company in COMPANIES:
        symbol = company.ticker.replace(".NS", "")
        current = TICKERTAPE_SLUGS.get(symbol)
        found = resolve(symbol, company.name, company.short_name)

        if found is None:
            # Not in the search index. That is not automatically wrong — LTIM is
            # only listed under its pre-merger id — so verify what we already have
            # rather than reporting a false alarm.
            existing = get_tickertape_url(symbol)
            code = status(existing) if existing else None
            if code == 200:
                print(f"{symbol:14} not in search, but current link is live (200)")
            else:
                unresolved.append(symbol)
                print(f"{symbol:14} UNRESOLVED (current link: {code})")
        elif found != current:
            changed[symbol] = found
            print(f"{symbol:14} CHANGED  {current} -> {found}")

        time.sleep(0.15)

    print("\nverifying current links...")
    for company in COMPANIES:
        symbol = company.ticker.replace(".NS", "")
        url = get_tickertape_url(changed.get(symbol) and symbol or symbol)
        if changed.get(symbol):
            url = f"https://www.tickertape.in{changed[symbol]}"
        if not url:
            continue
        code = status(url)
        if code != 200:
            broken.append((symbol, url, code))
            print(f"  {symbol:14} {code}  {url}")
        time.sleep(0.15)

    print(f"\n{len(changed)} changed, {len(unresolved)} unresolved, {len(broken)} not returning 200")
    if changed:
        print("\nPaste into TICKERTAPE_SLUGS in src/config.py:\n")
        for symbol, slug in sorted(changed.items()):
            print(f'    "{symbol}": "{slug}",')
    return 1 if (unresolved or broken) else 0


if __name__ == "__main__":
    sys.exit(main())
