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


def suggest_dimensions_from_context(
    caption: str,
    description: str,
    search_context: str,
    hf_token: str = "",
) -> str:
    """
    Feed BLIP caption + DDG/Wikipedia context to an HF text model and ask it
    to return structured dimension suggestions as JSON.

    Returns raw model response (JSON string).  Caller parses it.
    Raises RuntimeError on failure.
    """
    try:
        from huggingface_hub import InferenceClient
    except ImportError:
        raise RuntimeError("huggingface_hub not installed.")

    _TEXT_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"

    system = (
        "You are a mechanical engineering expert specialising in 3D printing. "
        "Given a description of a physical object plus reference information, "
        "output ONLY a JSON array of dimension suggestions — no other text.\n"
        'Format: [{"name":"Outer diameter","value":"25","unit":"mm","confidence":"medium"}]'
    )
    user = (
        f"Object (from photo AI): {caption}\n"
        f"User description: {description}\n"
        f"Reference info:\n{search_context[:1200]}\n\n"
        "List 3–8 key dimensions needed to 3D-print this object. "
        "Use the reference info where possible. Mark confidence as high/medium/low/estimated."
    )

    token  = hf_token or None
    client = InferenceClient(token=token)
    try:
        resp = client.chat_completion(
            model=_TEXT_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            max_tokens=512,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        err = str(exc)
        if "429" in err or "rate" in err.lower():
            raise RuntimeError(
                "HF rate limit — add a free token at huggingface.co/settings/tokens"
            )
        if "503" in err or "loading" in err.lower():
            raise RuntimeError("HF model warming up — try again in 20 s.")
        raise RuntimeError(f"HF text model error: {exc}")


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
