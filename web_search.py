"""
web_search.py — In-app object research using free, no-key public APIs.

DuckDuckGo Instant Answers and Wikipedia are both free, require no API
key, and return structured JSON — making them ideal for in-app lookups
without sending users to a browser.

Public API
----------
search_object(caption, description) -> SearchResult
    Queries DDG + Wikipedia and returns structured findings.

extract_dimensions_from_text(text) -> list[dict]
    Regex scan for dimension mentions (mm / cm / inch) in any text block.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field

import requests

_TIMEOUT = 10   # seconds per request

# ── DuckDuckGo Instant Answers ────────────────────────────────────────────────
_DDG_URL = "https://api.duckduckgo.com/"

# ── Wikipedia ─────────────────────────────────────────────────────────────────
_WIKI_API = "https://en.wikipedia.org/w/api.php"


@dataclass
class SearchResult:
    caption:     str = ""          # BLIP image caption
    description: str = ""          # user description
    ddg_abstract: str = ""         # DDG instant abstract
    ddg_answer:   str = ""         # DDG definitive answer
    wiki_extract: str = ""         # Wikipedia article intro
    wiki_title:   str = ""         # Wikipedia article title
    dimensions:   list[dict] = field(default_factory=list)  # [{value, unit, context}]
    errors:       list[str]  = field(default_factory=list)

    def has_content(self) -> bool:
        return bool(self.ddg_abstract or self.ddg_answer or self.wiki_extract)

    def full_text(self) -> str:
        """All text content concatenated — used for dimension extraction."""
        return " ".join(filter(None, [
            self.ddg_answer, self.ddg_abstract, self.wiki_extract
        ]))


# ── Public entry point ────────────────────────────────────────────────────────

def search_object(caption: str, description: str) -> SearchResult:
    """
    Look up an object using DuckDuckGo Instant Answers + Wikipedia.

    Both APIs are free and require no key.  Results are returned
    as a SearchResult so the caller can render them however it likes.
    """
    result = SearchResult(caption=caption, description=description)

    # Build search query from the best available signal
    query_parts = list(filter(None, [caption, description]))
    if not query_parts:
        result.errors.append("No caption or description to search.")
        return result

    query = " ".join(query_parts)

    # ── DuckDuckGo Instant Answers ────────────────────────────────────────────
    try:
        r = requests.get(
            _DDG_URL,
            params={
                "q":              f"{query} specifications dimensions",
                "format":         "json",
                "no_html":        "1",
                "skip_disambig":  "1",
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        ddg = r.json()
        result.ddg_abstract = ddg.get("Abstract", "").strip()
        result.ddg_answer   = ddg.get("Answer",   "").strip()
    except Exception as exc:
        result.errors.append(f"DDG search unavailable: {exc}")

    # ── Wikipedia ─────────────────────────────────────────────────────────────
    try:
        # 1. Find the best article title
        sr = requests.get(
            _WIKI_API,
            params={
                "action":   "query",
                "list":     "search",
                "srsearch": query,
                "format":   "json",
                "srlimit":  "1",
            },
            timeout=_TIMEOUT,
        )
        sr.raise_for_status()
        hits = sr.json().get("query", {}).get("search", [])

        if hits:
            title = hits[0]["title"]
            result.wiki_title = title

            # 2. Fetch the article intro (first few sentences)
            er = requests.get(
                _WIKI_API,
                params={
                    "action":      "query",
                    "titles":      title,
                    "prop":        "extracts",
                    "exintro":     True,
                    "exsentences": 6,
                    "explaintext": True,
                    "format":      "json",
                },
                timeout=_TIMEOUT,
            )
            er.raise_for_status()
            pages = er.json().get("query", {}).get("pages", {})
            for page in pages.values():
                result.wiki_extract = (page.get("extract") or "").strip()
    except Exception as exc:
        result.errors.append(f"Wikipedia unavailable: {exc}")

    # ── Dimension extraction ──────────────────────────────────────────────────
    result.dimensions = extract_dimensions_from_text(result.full_text())

    return result


# ── Dimension regex ───────────────────────────────────────────────────────────

_DIM_PATTERN = re.compile(
    r"""
    (?P<value>
        \d{1,4}(?:\.\d{1,3})?   # integer or decimal
        |
        \d{1,3}/\d{1,3}          # fraction  e.g.  1/4
    )
    \s*
    (?P<unit>
        mm | cm | m(?!\w) |      # metric
        inch(?:es)? | in(?:\b|") | "   # imperial
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

_CONTEXT_WINDOW = 40   # chars either side of the match


def extract_dimensions_from_text(text: str) -> list[dict]:
    """
    Return up to 12 dimension mentions with surrounding context.

    Each entry: {"value": "25", "unit": "mm", "context": "…outer diameter 25mm…"}
    """
    dims = []
    for m in _DIM_PATTERN.finditer(text):
        start = max(0, m.start() - _CONTEXT_WINDOW)
        end   = min(len(text), m.end()   + _CONTEXT_WINDOW)
        ctx   = text[start:end].replace("\n", " ").strip()
        dims.append({
            "value":   m.group("value"),
            "unit":    m.group("unit").lower().rstrip('"'),
            "context": ctx,
        })
        if len(dims) >= 12:
            break
    return dims
