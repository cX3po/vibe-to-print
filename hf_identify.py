"""
hf_identify.py — In-app object identification for Vibe-to-Print.

Pipeline
--------
1. BLIP  (free, anonymous)  — captions the photo in plain English
2. Template match            — finds the closest printable template
3. HF text model (optional) — writes a richer "what to create" description
                               and suggests typical dimensions

All three tiers degrade gracefully: if BLIP is rate-limited the caption
is empty but template matching still runs on the user description; if
there is no HF token the creation idea falls back to a keyword map.

Public API
----------
identify_object(image_bytes, description, hf_token="") -> IdentifyResult
caption_image(image_bytes, hf_token="") -> str
"""

from __future__ import annotations

import re
import json
from dataclasses import dataclass, field

import requests

# ── BLIP captioning ───────────────────────────────────────────────────────────
_BLIP_URL = (
    "https://api-inference.huggingface.co"
    "/models/Salesforce/blip-image-captioning-large"
)
_BLIP_TIMEOUT = 35   # seconds — cold-start can be slow

# ── HF text model (for creation idea + dim suggestions) ───────────────────────
_TEXT_MODEL   = "mistralai/Mistral-7B-Instruct-v0.3"
_TEXT_TIMEOUT = 30


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class IdentifyResult:
    # What the photo shows
    caption:         str  = ""
    # Human-readable object type inferred from caption + description
    object_type:     str  = ""
    # One-sentence suggestion of what to 3D-print
    creation_idea:   str  = ""
    # Best template from library
    template_match:  dict = field(default_factory=dict)
    # Up to 2 runner-up templates for "not quite right" alternatives
    alternatives:    list = field(default_factory=list)
    # How we reached the result
    method:          str  = ""   # "blip+template" | "blip+hf" | "description_only"
    # Non-fatal warning to surface in UI
    warning:         str  = ""


# ── Public entry point ────────────────────────────────────────────────────────

def identify_object(
    image_bytes:  bytes | None,
    description:  str,
    hf_token:     str = "",
) -> IdentifyResult:
    """
    Full identification pipeline.  Always returns an IdentifyResult —
    even if every network call fails, template keyword-matching on the
    description still provides a useful result.
    """
    import template_library as tl

    result = IdentifyResult()

    # ── Step 1: BLIP caption ─────────────────────────────────────────────────
    if image_bytes:
        try:
            result.caption = caption_image(image_bytes, hf_token)
            result.method  = "blip+template"
        except RuntimeError as exc:
            result.warning = str(exc)
            result.method  = "description_only"
    else:
        result.method = "description_only"

    # ── Step 2: Template matching ─────────────────────────────────────────────
    # Try increasingly broad queries until we get at least one hit
    queries = [
        f"{result.caption} {description}",
        result.caption,
        description,
    ]
    matches: list[dict] = []
    for q in queries:
        q = q.strip()
        if q:
            matches = tl.search(q, "")
            if matches:
                break

    if matches:
        result.template_match = matches[0]
        result.alternatives   = matches[1:3]
        result.object_type    = matches[0].get("category", "")

    # ── Step 3: Creation idea ─────────────────────────────────────────────────
    if hf_token and (result.caption or description):
        try:
            result.creation_idea = _hf_creation_idea(
                result.caption, description, hf_token
            )
            result.method = "blip+hf" if result.caption else "hf_text"
        except RuntimeError as exc:
            result.warning = (result.warning + "  " + str(exc)).strip()
            result.creation_idea = _keyword_creation_idea(
                result.caption, description, matches
            )
    else:
        result.creation_idea = _keyword_creation_idea(
            result.caption, description, matches
        )

    return result


# ── BLIP image captioning ─────────────────────────────────────────────────────

def caption_image(image_bytes: bytes, hf_token: str = "") -> str:
    """
    Send raw image bytes to BLIP and return a plain-English caption.
    Raises RuntimeError with a user-friendly message on any failure.
    """
    headers: dict[str, str] = {}
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"

    try:
        resp = requests.post(
            _BLIP_URL, headers=headers,
            data=image_bytes, timeout=_BLIP_TIMEOUT,
        )
    except requests.Timeout:
        raise RuntimeError(
            "Photo read timed out — HF servers may be busy. "
            "Result is based on your description only."
        )
    except requests.ConnectionError:
        raise RuntimeError("No internet — working from description only.")

    if resp.status_code == 503:
        raise RuntimeError(
            "Photo AI is warming up (~20 s) — try again in a moment. "
            "Searching by description in the meantime."
        )
    if resp.status_code == 429:
        raise RuntimeError(
            "Rate limit hit. Add a free HF token in ⚙️ Advanced Settings "
            "for higher limits (huggingface.co/settings/tokens)."
        )
    if not resp.ok:
        raise RuntimeError(
            f"Photo AI unavailable ({resp.status_code}). "
            "Using description only."
        )

    try:
        data = resp.json()
        if isinstance(data, list) and data:
            return data[0].get("generated_text", "").strip()
    except Exception:
        pass
    return ""


# ── HF text model: creation idea ─────────────────────────────────────────────

def _hf_creation_idea(caption: str, description: str, hf_token: str) -> str:
    """Ask a small HF text model to suggest what to 3D-print. ~1 sentence."""
    try:
        from huggingface_hub import InferenceClient
    except ImportError:
        raise RuntimeError("huggingface_hub not installed.")

    combined = " ".join(filter(None, [caption, description]))
    prompt   = (
        f"Object: {combined}\n\n"
        "In ONE sentence starting with 'A replacement' or 'A custom', "
        "describe the most useful 3D-printable part to make from this. "
        "Be specific about function. No extra text."
    )

    client = InferenceClient(token=hf_token)
    try:
        resp = client.chat_completion(
            model=_TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
        )
        text = (resp.choices[0].message.content or "").strip()
        # Truncate at first sentence boundary
        for sep in (".", "!", "?"):
            idx = text.find(sep)
            if idx > 20:
                return text[: idx + 1]
        return text
    except Exception as exc:
        err = str(exc)
        if "429" in err or "rate" in err.lower():
            raise RuntimeError(
                "HF rate limit — add a free token at "
                "huggingface.co/settings/tokens for higher limits."
            )
        raise RuntimeError(f"HF text error: {exc}")


# ── Keyword fallback: creation idea ──────────────────────────────────────────

_KEYWORD_MAP = [
    (["knob", "dial", "control", "pot", "rotary"],
     "A replacement control knob for your appliance or audio device."),
    (["hinge", "door", "lid", "flap", "cover"],
     "A replacement hinge or pivot to repair a door, lid or panel."),
    (["bracket", "mount", "holder", "clip", "clamp"],
     "A custom mounting bracket or holder for your specific application."),
    (["gear", "cog", "wheel", "sprocket", "pulley"],
     "A replacement gear or drive wheel to restore movement."),
    (["hook", "hang", "wall"],
     "A wall-mount hook or hanger sized for your item."),
    (["box", "enclosure", "case", "tray", "container"],
     "A custom enclosure, tray or storage box."),
    (["leg", "foot", "stand", "base"],
     "A replacement foot, leg or stabilising base."),
    (["cap", "plug", "cover", "stopper"],
     "A protective cap, plug or cover for an opening."),
    (["handle", "grip", "lever", "pull"],
     "A replacement handle or grip."),
    (["spacer", "shim", "washer", "ring"],
     "A precision spacer, shim or alignment ring."),
]


def _keyword_creation_idea(
    caption: str, description: str, matches: list[dict]
) -> str:
    # Use template description when we have a confident match
    if matches:
        return (
            f"A {matches[0]['name'].lower()} — "
            f"{matches[0]['description']}"
        )

    text = f"{caption} {description}".lower()
    for keywords, idea in _KEYWORD_MAP:
        if any(kw in text for kw in keywords):
            return idea

    return (
        "A custom 3D-printable replacement part based on your photo "
        "and description."
    )
