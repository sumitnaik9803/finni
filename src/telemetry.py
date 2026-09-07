"""
Finni Telemetry — a single tally of every external call the run makes.

The pipeline talks to five things that can fail independently: RSS feeds, two LLM
providers, three market-data libraries, screener.in and Google Sheets. Each one
already logs its own failures, but those lines are scattered across thousands of
log rows, so "did Gemini work, and how much of the run did it carry?" was only
answerable by reading the whole log.

Every call site records an outcome here, and main prints one table at the end.
Deliberately dependency-free and never fatal: telemetry must not be able to break
the pipeline it is measuring.
"""

import os
from collections import Counter
from dataclasses import dataclass, field

# Display order and labels. Anything recorded under an unlisted key still shows up,
# in an "OTHER" group at the bottom, so a new call site is never silently dropped.
_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    ("NEWS", [
        ("rss", "RSS feeds"),
        ("google-news", "Google News"),
    ]),
    ("LLM", [
        ("gemini", "Gemini"),
        ("groq", "Groq"),
        ("mistral", "Mistral"),
        ("cerebras", "Cerebras"),
        ("batch", "Batch scoring"),
    ]),
    ("MARKET DATA", [
        ("yfinance", "yfinance"),
        ("jugaad", "jugaad-data"),
        ("nselib", "nselib"),
    ]),
    ("FUNDAMENTALS", [
        ("screener", "screener.in"),
    ]),
    ("EVENTS", [
        ("nse-actions", "NSE corp actions"),
        ("nse-events", "NSE event cal"),
        ("nse-holidays", "NSE holidays"),
    ]),
    ("OUTPUT", [
        ("sheets", "Google Sheets"),
    ]),
]

_LABELS = {key: label for _, pairs in _GROUPS for key, label in pairs}


@dataclass
class _Component:
    """Per-dependency tally: successes, failures with reasons, and free-form notes."""
    ok: int = 0
    fail: int = 0
    skip: int = 0
    reasons: Counter = field(default_factory=Counter)
    variants: Counter = field(default_factory=Counter)
    notes: dict[str, str] = field(default_factory=dict)


class Telemetry:
    """Process-wide call tally. One instance, imported as `telemetry`."""

    def __init__(self):
        self._components: dict[str, _Component] = {}

    def _get(self, component: str) -> _Component:
        if component not in self._components:
            self._components[component] = _Component()
        return self._components[component]

    def ok(self, component: str, variant: str | None = None):
        """Record a successful call. `variant` distinguishes how it succeeded."""
        c = self._get(component)
        c.ok += 1
        if variant:
            c.variants[variant] += 1

    def fail(self, component: str, reason: str = "error"):
        """Record a failed call. `reason` is grouped and counted in the summary."""
        c = self._get(component)
        c.fail += 1
        c.reasons[str(reason)[:60]] += 1

    def skip(self, component: str, reason: str = "unavailable"):
        """Record a call that was never attempted (library missing, provider disabled)."""
        c = self._get(component)
        c.skip += 1
        c.reasons[str(reason)[:60]] += 1

    def note(self, component: str, key: str, value):
        """Attach a single resolved fact — the model name, the endpoint in use."""
        self._get(component).notes[key] = str(value)

    def get(self, component: str) -> _Component | None:
        return self._components.get(component)

    def render(self) -> str:
        """Format the whole tally as a log-friendly block."""
        width = 74
        lines = ["", "=" * width, " RUN SUMMARY - every external call, by dependency", "=" * width]

        seen: set[str] = set()
        for group, pairs in _GROUPS:
            rows = [(key, label) for key, label in pairs if key in self._components]
            if not rows:
                continue
            lines.append(f" {group}")
            for key, label in rows:
                seen.add(key)
                lines.extend(self._render_component(label, self._components[key]))

        leftover = [k for k in self._components if k not in seen]
        if leftover:
            lines.append(" OTHER")
            for key in leftover:
                lines.extend(self._render_component(_LABELS.get(key, key), self._components[key]))

        lines.append("=" * width)
        return "\n".join(lines)

    @staticmethod
    def _render_component(label: str, c: _Component) -> list[str]:
        total = c.ok + c.fail + c.skip
        pct = f"{100 * c.ok / total:.0f}%" if total else "—"
        line = f"   {label:<16} {c.ok:>4} ok  {c.fail:>4} failed"
        if c.skip:
            line += f"  {c.skip:>3} skipped"
        line += f"   [{pct} success]"
        out = [line]

        if c.variants:
            detail = ", ".join(f"{name} x{n}" for name, n in c.variants.most_common())
            out.append(f"        via: {detail}")
        if c.notes:
            detail = "  ".join(f"{k}={v}" for k, v in c.notes.items())
            out.append(f"        {detail}")
        if c.reasons:
            detail = ", ".join(f"{why} x{n}" for why, n in c.reasons.most_common(5))
            out.append(f"        why: {detail}")
        return out

    def reset(self):
        """Clear all counters (used by tests)."""
        self._components.clear()


telemetry = Telemetry()


def debug_llm_enabled() -> bool:
    """
    True when FINNI_DEBUG_LLM is set, which makes the scorer log the prompt and raw
    response of every LLM call. Off by default: it is very noisy, but it is the only
    way to see what the model was actually sent and what came back.
    """
    return os.environ.get("FINNI_DEBUG_LLM", "").lower() in ("1", "true", "yes")
