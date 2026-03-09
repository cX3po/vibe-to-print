"""
hf_identify.py — Zero-friction image captioning via HF BLIP.

Uses the Hugging Face Inference API with the BLIP image-captioning model.
Works completely anonymously (no account or token required) with modest
rate limits.  Pass a free HF token for higher throughput.

Public API
----------
caption_image(image_bytes, hf_token="") -> str
    Returns a plain-English caption of the photo, e.g.
    "a white plastic knob with a d-shaped hole in the centre"

make_search_urls(description, caption="") -> dict
    Returns {"google": url, "bing": url, "google_lens": url}
"""

from __future__ import annotations

import urllib.parse

import requests

# BLIP large — best free anonymous captioning model on HF Inference API
_BLIP_URL   = ("https://api-inference.huggingface.co"
               "/models/Salesforce/blip-image-captioning-large")
_TIMEOUT    = 35   # seconds; cold-start can be slow


def caption_image(image_bytes: bytes, hf_token: str = "") -> str:
    """
    Send raw image bytes to BLIP and return the generated caption.

    Raises RuntimeError with a user-friendly message on failure so the
    caller can show it in the UI and fall back gracefully.
    """
    headers: dict[str, str] = {}
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"

    try:
        resp = requests.post(
            _BLIP_URL,
            headers=headers,
            data=image_bytes,
            timeout=_TIMEOUT,
        )
    except requests.Timeout:
        raise RuntimeError(
            "Photo analysis timed out — HF servers may be busy. "
            "Try again or use a description-only search."
        )
    except requests.ConnectionError:
        raise RuntimeError(
            "No internet connection. Using description-only search."
        )

    if resp.status_code == 503:
        raise RuntimeError(
            "BLIP model is warming up on HF servers — try again in ~20 seconds."
        )
    if resp.status_code == 429:
        raise RuntimeError(
            "Rate limit reached. Add a free HF token in ⚙️ Advanced Settings "
            "for higher limits (huggingface.co/settings/tokens)."
        )
    if not resp.ok:
        raise RuntimeError(
            f"HF API returned {resp.status_code}. "
            "Falling back to description-only search."
        )

    try:
        result = resp.json()
        if isinstance(result, list) and result:
            return result[0].get("generated_text", "").strip()
        return ""
    except Exception:
        return ""


def make_search_urls(description: str, caption: str = "") -> dict[str, str]:
    """
    Build web-search and Google Lens URLs pre-filled with the
    combined description + caption query.
    """
    query = " ".join(filter(None, [caption, description])).strip()
    if not query:
        query = "3d printable replacement part dimensions mm"

    # Append useful search suffixes for finding measurements
    search_q = urllib.parse.quote_plus(f"{query} dimensions mm 3d print")

    return {
        "google":      f"https://www.google.com/search?q={search_q}",
        "bing":        f"https://www.bing.com/search?q={search_q}",
        "google_lens": "https://lens.google.com/",
    }
