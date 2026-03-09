"""
deep_search.py
--------------
"Deep Search" mode: multi-stage visual identification + web spec lookup.

Pipeline
--------
  image
    → Stage 1 · Visual ID
        Option A : Google Cloud Vision API  (WEB_DETECTION feature)
        Option B : AI-vision fallback       (Claude / GPT-4o / llava)
    → Stage 2 · Web Spec Search
        Option A : SerpAPI  (Google Search)
        Option B : Brave Search API
        Option C : AI knowledge fallback    (no web call — model training data)
    → Stage 3 · AI Spec Extraction
        AI reads the search snippets and returns structured dimensions
    → DeepSearchResult
        • identified_label   – e.g. "Zenith 12-S-232 Console Radio"
        • manufacturer       – e.g. "Zenith"
        • model_number       – e.g. "12-S-232"
        • confidence         – "high" / "medium" / "low"
        • suggested_dims     – [{id, label, value, unit, confidence, source_note}]
        • search_sources     – list of URLs consulted
        • user_message       – the ready-to-display user-facing sentence
        • raw_debug          – full concatenated debug text

Public entry point
------------------
run_deep_search(image_b64, media_type, description, brain,
                gcv_api_key="", search_provider="AI Only", search_api_key="")
    -> DeepSearchResult
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import requests

# ── Search provider names (shown in sidebar dropdown) ────────────────────────
SEARCH_PROVIDER_SERPAPI  = "SerpAPI (Google)"
SEARCH_PROVIDER_BRAVE    = "Brave Search"
SEARCH_PROVIDER_AI       = "AI Knowledge Only"

ALL_SEARCH_PROVIDERS = [
    SEARCH_PROVIDER_AI,
    SEARCH_PROVIDER_SERPAPI,
    SEARCH_PROVIDER_BRAVE,
]

# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class SuggestedDim:
    id:          str          # machine-readable id, e.g. "shaft_diameter"
    label:       str          # human question, e.g. "Knob shaft diameter"
    value:       str          # e.g. "6.35"
    unit:        str          # e.g. "mm"
    confidence:  str          # "high" / "medium" / "low"
    source_note: str = ""     # e.g. "Antique Radio Forums service manual scan"


@dataclass
class DeepSearchResult:
    identified_label: str = ""
    manufacturer:     str = ""
    model_number:     str = ""
    confidence:       str = "low"
    suggested_dims:   list[SuggestedDim] = field(default_factory=list)
    search_sources:   list[str]          = field(default_factory=list)
    user_message:     str = ""
    raw_debug:        str = ""

    def to_dim_list(self) -> list[dict]:
        """Convert to the [{id, question}] format expected by the dimensions phase."""
        return [
            {
                "id":       d.id,
                "question": f"{d.label} (suggested: {d.value} {d.unit})",
                "prefill":  f"{d.value} {d.unit}",
            }
            for d in self.suggested_dims
        ]

    def as_dict(self) -> dict:
        return {
            "identified_label": self.identified_label,
            "manufacturer":     self.manufacturer,
            "model_number":     self.model_number,
            "confidence":       self.confidence,
            "suggested_dims": [
                {"id": d.id, "label": d.label, "value": d.value,
                 "unit": d.unit, "confidence": d.confidence,
                 "source_note": d.source_note}
                for d in self.suggested_dims
            ],
            "search_sources": self.search_sources,
            "user_message":   self.user_message,
            "raw_debug":      self.raw_debug,
        }


# ── Stage 1A : Google Cloud Vision web detection ─────────────────────────────

_GCV_URL = "https://vision.googleapis.com/v1/images:annotate"

def _gcv_web_detect(image_b64: str, api_key: str) -> dict:
    """
    Call Google Cloud Vision WEB_DETECTION.
    Returns the raw webDetection dict, or {} on error.
    """
    payload = {
        "requests": [{
            "image": {"content": image_b64},
            "features": [
                {"type": "WEB_DETECTION",    "maxResults": 10},
                {"type": "LABEL_DETECTION",  "maxResults": 10},
            ],
        }]
    }
    try:
        resp = requests.post(
            _GCV_URL, params={"key": api_key},
            json=payload, timeout=20,
        )
        resp.raise_for_status()
        result  = resp.json()
        annots  = result.get("responses", [{}])[0]
        return annots
    except Exception as exc:
        return {"_error": str(exc)}


def _parse_gcv_result(annots: dict) -> tuple[str, float, list[str]]:
    """
    Extract (best_label, score, [web_entity_descriptions]) from GCV response.
    """
    web = annots.get("webDetection", {})

    # bestGuessLabels is the most direct identification
    guesses = web.get("bestGuessLabels", [])
    if guesses:
        best   = guesses[0]
        label  = best.get("label", "")
        score  = 0.85 if best.get("languageCode") else 0.7
    else:
        label, score = "", 0.0

    entities = [e.get("description", "") for e in web.get("webEntities", [])
                if e.get("score", 0) > 0.4]

    sources = [p.get("url", "") for p in web.get("pagesWithMatchingImages", [])[:5]]

    return label, score, entities, sources


# ── Stage 1B : AI vision identification fallback ─────────────────────────────

_ID_SYSTEM = (
    "You are an expert antique/vintage object identifier and mechanical archivist. "
    "Given a photo and optional description, identify the specific manufacturer, "
    "model number/name, and approximate year of manufacture. "
    "Be as specific as possible — not just 'a radio' but 'Zenith 12-S-232 console radio (1938)'. "
    "If you are uncertain, say so and give your best estimate with a confidence level. "
    "Respond ONLY with a JSON object (no extra text):\n"
    "{\n"
    '  "identified_label": "full descriptive label",\n'
    '  "manufacturer":     "brand/maker",\n'
    '  "model_number":     "model number or name",\n'
    '  "year_estimate":    "circa 1938",\n'
    '  "category":         "vintage radio / appliance knob / industrial bracket / etc.",\n'
    '  "confidence":       "high|medium|low",\n'
    '  "reasoning":        "one sentence why you think this"\n'
    "}"
)

def _ai_identify(image_b64: str | None, media_type: str,
                  description: str, brain) -> dict:
    """Ask the AI brain to identify the object. Returns parsed JSON dict."""
    user_text = (
        f"Description from user: {description or 'No description provided.'}\n\n"
        "Please identify the specific model/manufacturer of this object "
        "and return the JSON as instructed."
    )
    try:
        raw = brain.call(_ID_SYSTEM, user_text, image_b64, media_type)
    except Exception as exc:
        return {"_error": str(exc), "identified_label": "Unknown", "confidence": "low"}

    clean = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("`")
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return {"identified_label": raw[:200], "confidence": "low", "_raw": raw}


# ── Stage 2A : SerpAPI web search ─────────────────────────────────────────────

def _serpapi_search(query: str, api_key: str, num: int = 6) -> tuple[list[str], list[str]]:
    """
    Returns ([snippet, ...], [url, ...]) from SerpAPI Google Search.
    """
    try:
        resp = requests.get(
            "https://serpapi.com/search.json",
            params={"q": query, "api_key": api_key, "num": num, "hl": "en"},
            timeout=20,
        )
        resp.raise_for_status()
        data     = resp.json()
        results  = data.get("organic_results", [])
        snippets = [r.get("snippet", "") for r in results if r.get("snippet")]
        urls     = [r.get("link", "")    for r in results if r.get("link")]
        return snippets, urls
    except Exception as exc:
        return [f"[SerpAPI error: {exc}]"], []


# ── Stage 2B : Brave Search ───────────────────────────────────────────────────

def _brave_search(query: str, api_key: str, num: int = 6) -> tuple[list[str], list[str]]:
    """
    Returns ([snippet, ...], [url, ...]) from Brave Search API.
    """
    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": num},
            headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
            timeout=20,
        )
        resp.raise_for_status()
        data    = resp.json()
        results = data.get("web", {}).get("results", [])
        snippets = [r.get("description", "") for r in results if r.get("description")]
        urls     = [r.get("url", "")        for r in results if r.get("url")]
        return snippets, urls
    except Exception as exc:
        return [f"[Brave error: {exc}]"], []


# ── Stage 3 : AI spec extraction ─────────────────────────────────────────────

_SPEC_SYSTEM = (
    "You are a Master Mechanical Modeler and vintage parts restoration expert. "
    "You have been given a known object identification and some web search snippets "
    "(or your own knowledge). "
    "Extract or estimate the key physical dimensions needed to 3D print a replacement part. "
    "Focus on dimensions that affect fit: shaft diameters, bore sizes, depths, thread pitches, "
    "and any tolerance-critical measurements. "
    "If web snippets mention specific values, prefer those over estimates. "
    "Respond ONLY with a JSON object (no extra text):\n"
    "{\n"
    '  "object_type": "what part we are printing",\n'
    '  "specs_source": "web search / AI knowledge / mixed",\n'
    '  "dimensions": [\n'
    '    {\n'
    '      "id":          "shaft_diameter",\n'
    '      "label":       "Knob shaft diameter",\n'
    '      "value":       "6.35",\n'
    '      "unit":        "mm",\n'
    '      "confidence":  "high",\n'
    '      "source_note": "Standard Zenith 1/4-inch D-shaft, confirmed in service manual"\n'
    "    }\n"
    "  ]\n"
    "}"
)

def _ai_extract_specs(identification: dict, snippets: list[str],
                       description: str, brain) -> dict:
    """
    Ask the AI to extract structured dimensions from search snippets.
    Returns parsed JSON dict.
    """
    snippet_block = "\n\n".join(f"SNIPPET {i+1}: {s}" for i, s in enumerate(snippets[:8]))
    if not snippet_block:
        snippet_block = "(No web snippets available — use your training knowledge.)"

    user_text = (
        f"## Identified Object\n"
        f"- Label       : {identification.get('identified_label', 'Unknown')}\n"
        f"- Manufacturer: {identification.get('manufacturer', 'Unknown')}\n"
        f"- Model       : {identification.get('model_number', 'Unknown')}\n"
        f"- Year        : {identification.get('year_estimate', 'Unknown')}\n\n"
        f"## User's Repair Goal\n{description}\n\n"
        f"## Web Search Snippets\n{snippet_block}\n\n"
        "Extract the dimensional specifications needed to model a replacement part."
    )
    try:
        raw = brain.call(_SPEC_SYSTEM, user_text)
    except Exception as exc:
        return {"_error": str(exc), "dimensions": []}

    clean = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("`")
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return {"dimensions": [], "_raw": raw}


# ── Build search query ────────────────────────────────────────────────────────

def _build_spec_query(identification: dict, description: str) -> str:
    label = identification.get("identified_label", "")
    model = identification.get("model_number", "")
    mfr   = identification.get("manufacturer", "")

    base = model or label or mfr or "vintage part"
    # Pull key nouns from the description to narrow the search
    part_hints = ""
    for keyword in ["knob", "shaft", "dial", "chassis", "bearing",
                    "bracket", "gear", "switch", "potentiometer"]:
        if keyword.lower() in description.lower():
            part_hints += f" {keyword}"
    return f"{base}{part_hints} specifications dimensions service manual"


# ── Main entry point ──────────────────────────────────────────────────────────

def run_deep_search(
    image_b64:       str | None,
    media_type:      str,
    description:     str,
    brain,                            # ai_brains.AIBrain instance
    gcv_api_key:     str = "",
    search_provider: str = SEARCH_PROVIDER_AI,
    search_api_key:  str = "",
) -> DeepSearchResult:
    """
    Full deep-search pipeline.
    Returns a DeepSearchResult (always succeeds, degrades gracefully).
    """
    debug_log: list[str] = []
    result = DeepSearchResult()

    # ── Stage 1 · Visual identification ──────────────────────────────────────
    identification: dict = {}

    if gcv_api_key and image_b64:
        debug_log.append("=== Stage 1A: Google Cloud Vision WEB_DETECTION ===")
        annots = _gcv_web_detect(image_b64, gcv_api_key)
        debug_log.append(json.dumps(annots, indent=2)[:2000])

        if "_error" not in annots:
            best_label, score, entities, gcv_sources = _parse_gcv_result(annots)
            result.search_sources.extend(gcv_sources)

            # Ask AI to refine the GCV result
            gcv_hint = (
                f"Google Vision best guess: '{best_label}'. "
                f"Web entities: {', '.join(entities[:6])}."
            )
            enhanced_desc = f"{description}\n\nVision API hint: {gcv_hint}"
            identification = _ai_identify(image_b64, media_type, enhanced_desc, brain)
            debug_log.append(f"GCV best guess: {best_label} | score: {score:.2f}")
        else:
            debug_log.append(f"GCV error: {annots['_error']} — falling back to AI-only.")
            identification = _ai_identify(image_b64, media_type, description, brain)
    else:
        debug_log.append("=== Stage 1B: AI-only visual identification ===")
        identification = _ai_identify(image_b64, media_type, description, brain)

    debug_log.append(f"Identification: {json.dumps(identification, indent=2)[:1000]}")

    result.identified_label = identification.get("identified_label", "Unknown object")
    result.manufacturer     = identification.get("manufacturer", "")
    result.model_number     = identification.get("model_number", "")
    result.confidence       = identification.get("confidence", "low")

    # ── Stage 2 · Web spec search ─────────────────────────────────────────────
    snippets: list[str] = []
    query = _build_spec_query(identification, description)
    debug_log.append(f"\n=== Stage 2: Web search  ===\nQuery: {query}")

    if search_provider == SEARCH_PROVIDER_SERPAPI and search_api_key:
        snippets, urls = _serpapi_search(query, search_api_key)
        result.search_sources.extend(urls)
        debug_log.append(f"SerpAPI returned {len(snippets)} snippets.")

    elif search_provider == SEARCH_PROVIDER_BRAVE and search_api_key:
        snippets, urls = _brave_search(query, search_api_key)
        result.search_sources.extend(urls)
        debug_log.append(f"Brave returned {len(snippets)} snippets.")

    else:
        debug_log.append("No web search API — AI will use training knowledge only.")

    # ── Stage 3 · AI spec extraction ─────────────────────────────────────────
    debug_log.append("\n=== Stage 3: AI spec extraction ===")
    spec_data = _ai_extract_specs(identification, snippets, description, brain)
    debug_log.append(json.dumps(spec_data, indent=2)[:2000])

    raw_dims = spec_data.get("dimensions", [])
    for d in raw_dims:
        result.suggested_dims.append(SuggestedDim(
            id          = d.get("id", "dim"),
            label       = d.get("label", "Dimension"),
            value       = str(d.get("value", "")),
            unit        = d.get("unit", "mm"),
            confidence  = d.get("confidence", "medium"),
            source_note = d.get("source_note", ""),
        ))

    # ── Build user-facing message ─────────────────────────────────────────────
    conf_tag = {
        "high":   "confident this is",
        "medium": "believe this is",
        "low":    "think this might be",
    }.get(result.confidence, "believe this is")

    mfr_part = f"{result.manufacturer} " if result.manufacturer else ""
    mdl_part = result.model_number or result.identified_label

    src_tag = ""
    if search_provider != SEARCH_PROVIDER_AI and snippets:
        src_tag = " (sourced from web search)"
    elif snippets:
        src_tag = " (from web search)"
    else:
        src_tag = " (from AI training knowledge)"

    result.user_message = (
        f"I {conf_tag} a **{mfr_part}{mdl_part}**. "
        f"Factory specs suggest the following dimensions{src_tag}. "
        f"Would you like to use these, or edit them first?"
    )

    result.raw_debug = "\n".join(debug_log)
    return result
