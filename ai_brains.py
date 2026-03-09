"""
ai_brains.py
------------
Unified AI abstraction layer.

Supported providers:
  - Claude  (anthropic SDK, any vision-capable model)
  - GPT-4o  (openai SDK)
  - Ollama  (local REST API — uses llava for vision, any model for text)
  - Hugging Face (huggingface_hub InferenceClient — free tier)

Public API
----------
AIBrain(provider, api_key, model_override=None, hf_vision_model=None, hf_text_model=None)
  .call(system, user_text, image_b64, media_type)
      -> str                # raw response from the chosen provider
  .extract_dimensions(image_b64, media_type, description, printer_name, material,
                       reference_hint="")
      -> (summary, [{id, question, estimated_value?, ...}], scale_meta)
  .generate_openscad(description, dim_answers, printer_profile, material,
                      material_temps, centering_text)
      -> str                # raw OpenSCAD code (fenced block stripped)
"""

from __future__ import annotations
import re
import json
import base64
import requests

# ── Provider constants ────────────────────────────────────────────────────────
PROVIDER_CLAUDE  = "Claude (Anthropic)"
PROVIDER_GPT4O   = "GPT-4o (OpenAI)"
PROVIDER_OLLAMA  = "Local (Ollama)"
PROVIDER_HF      = "Free / Open Source (Hugging Face)"
PROVIDER_MANUAL  = "Manual (No AI — Template Mode)"

ALL_PROVIDERS    = [PROVIDER_CLAUDE, PROVIDER_GPT4O, PROVIDER_OLLAMA,
                    PROVIDER_HF, PROVIDER_MANUAL]

DEFAULT_MODELS = {
    PROVIDER_CLAUDE: "claude-opus-4-6",
    PROVIDER_GPT4O:  "gpt-4o",
    PROVIDER_OLLAMA: "llava",          # vision-capable; falls back to llama3 for text-only
    PROVIDER_HF:     "mistralai/Mistral-7B-Instruct-v0.3",
}

OLLAMA_TEXT_MODEL = "llama3"          # used when no image is present

# ── Hugging Face model lists ──────────────────────────────────────────────────
HF_VISION_MODEL_DEFAULT = "meta-llama/Llama-3.2-11B-Vision-Instruct"
HF_TEXT_MODEL_DEFAULT   = "mistralai/Mistral-7B-Instruct-v0.3"

HF_VISION_MODELS = [
    "meta-llama/Llama-3.2-11B-Vision-Instruct",
    "meta-llama/Llama-3.2-90B-Vision-Instruct",
    "Qwen/Qwen2-VL-7B-Instruct",
]

HF_TEXT_MODELS = [
    "mistralai/Mistral-7B-Instruct-v0.3",
    "meta-llama/Meta-Llama-3-8B-Instruct",
    "microsoft/Phi-3-mini-4k-instruct",
    "HuggingFaceH4/zephyr-7b-beta",
]

# ── System persona ────────────────────────────────────────────────────────────
_SYSTEM_PERSONA = (
    "You are a Master Mechanical Modeler — a world-class expert in 3D printing, "
    "parametric CAD design, and mechanical engineering. "
    "You can model any physical object: knobs, brackets, toys, tools, enclosures, "
    "jigs, and custom hardware. "
    "You produce clean, parametric, well-commented OpenSCAD code that prints "
    "first-time without modification. "
    "You always define every key measurement as a named variable at the top of "
    "the file so the user can rescale with a single edit."
)

_REFERENCE_OBJECTS_KNOWLEDGE = """
RELATIVE SCALING — use this when the user has no caliper measurements.

Scan the photo for ANY of these known-size reference objects:

  CARDS
    • Credit / debit card    : 85.60 × 53.98 × 0.76 mm  (ISO/IEC 7810 ID-1)
    • US business card       : 88.90 × 50.80 mm
    • EU business card       : 85.00 × 55.00 mm

  US COINS
    • Quarter  (25¢)         : 24.26 mm diameter, 1.75 mm thick
    • Penny    (1¢)          : 19.05 mm diameter, 1.52 mm thick
    • Dime     (10¢)         : 17.91 mm diameter, 1.35 mm thick
    • Nickel   (5¢)          : 21.21 mm diameter, 1.95 mm thick
    • Half dollar (50¢)      : 30.61 mm diameter, 2.15 mm thick

  EU / UK COINS
    • €1 euro               : 23.25 mm diameter, 2.33 mm thick
    • €2 euro               : 25.75 mm diameter, 2.20 mm thick
    • UK £1                 : 23.43 mm diameter, 2.80 mm thick
    • UK 10p                : 24.50 mm diameter, 1.85 mm thick

  BATTERIES (IEC 60086)
    • AA                    : 14.5 mm diameter × 50.5 mm long
    • AAA                   : 10.5 mm diameter × 44.5 mm long
    • C                     : 26.2 mm diameter × 50.0 mm long
    • D                     : 34.2 mm diameter × 61.5 mm long

  COMMON HARDWARE
    • USB-A connector       : 12.0 mm wide × 4.5 mm tall
    • M4 hex bolt head      : 7.0 mm across-flats
    • M6 hex bolt head      : 10.0 mm across-flats

  BODY (low confidence — high variability)
    • Adult thumb width     : ~18–22 mm  (use as rough guide only)
    • Adult index finger    : ~14–18 mm wide

Scaling method:
  1. Identify the reference object's visible dimension (e.g. coin diameter in pixels).
  2. Calculate: scale = known_mm / pixel_span.
  3. Apply scale to the target object's pixel dimensions.
  4. Report: which reference, which dimension used, estimated scale factor.

Always include estimated_value and estimation_source even if the user hasn't
provided measurements — mark estimation_confidence as "estimated (high|medium|low)".
"""

_DIM_EXTRACT_SYSTEM = (
    _SYSTEM_PERSONA + "\n\n"
    "Your current task is Phase A – The Vision.\n"
    "Analyse the photo and/or description. Do TWO things:\n"
    "  A) Identify what measurements are needed to model this object.\n"
    "  B) Attempt to ESTIMATE those measurements using Relative Scaling "
    "     (see below) — even if the user provided no numbers.\n\n"
    + _REFERENCE_OBJECTS_KNOWLEDGE +
    "\nRespond with a JSON object in this EXACT format (no extra text):\n"
    "{\n"
    '  "object_summary":    "one-sentence description of what you see",\n'
    '  "scaling_method":    "reference_object | ruler | user_provided | estimated | unknown",\n'
    '  "reference_detected":"describe any reference object you found, or null",\n'
    '  "scale_note":        "how you derived the scale (or why you could not)",\n'
    '  "dimensions": [\n'
    "    {\n"
    '      "id":                   "shaft_diameter",\n'
    '      "question":             "What is the shaft diameter? (mm)",\n'
    '      "estimated_value":      "6.35",\n'
    '      "estimated_unit":       "mm",\n'
    '      "estimation_confidence":"medium",\n'
    '      "estimation_source":    "Scaled from US quarter visible in photo"\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "Rules:\n"
    "• Include 3–8 dimensions — only those truly needed for the model.\n"
    "• Always populate estimated_value if you can, even a rough guess.\n"
    "• Use clear, non-technical language in 'question'.\n"
    "• Set estimation_confidence to 'high', 'medium', 'low', or 'none'.\n"
    "• If no reference is found and you cannot estimate, set estimated_value to null."
)

_OPENSCAD_SYSTEM = (
    _SYSTEM_PERSONA + "\n\n"
    "Your current task is Phase B – The CAD. "
    "Generate complete, parametric OpenSCAD code. Rules:\n"
    "1. All key measurements must be top-level variables.\n"
    "2. Each module must have a one-line comment.\n"
    "3. The outermost call MUST use the bed-centering translate provided.\n"
    "4. Output ONLY a ```openscad ... ``` fenced code block, then a short "
    "   bullet-point design summary. No other text before the code block."
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_code_fence(text: str) -> str:
    """Extract content from the first ```...``` block found."""
    match = re.search(r"```(?:openscad|scad)?\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else text.strip()


def _parse_dim_response(raw: str) -> tuple[str, list[dict], dict]:
    """
    Parse the AI dimension-extraction response.
    Returns (object_summary, [{id, question, estimated_value?, ...}], scale_meta).
    Falls back gracefully if JSON is malformed.
    scale_meta keys: scaling_method, reference_detected, scale_note
    """
    clean = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("`")
    try:
        data    = json.loads(clean)
        summary = data.get("object_summary", "")
        dims    = data.get("dimensions", [])
        meta    = {
            "scaling_method":    data.get("scaling_method", "unknown"),
            "reference_detected": data.get("reference_detected") or "",
            "scale_note":        data.get("scale_note", ""),
        }
        return summary, dims, meta
    except (json.JSONDecodeError, AttributeError):
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        dims  = [{"id": f"dim_{i}", "question": l} for i, l in enumerate(lines) if l]
        return "", dims, {"scaling_method": "unknown",
                          "reference_detected": "", "scale_note": ""}


# ── Main class ────────────────────────────────────────────────────────────────

class AIBrain:
    def __init__(self, provider: str, api_key: str = "",
                 model_override: str = "",
                 hf_vision_model: str = "",
                 hf_text_model: str = ""):
        self.provider       = provider
        self.api_key        = api_key
        self.model          = model_override or DEFAULT_MODELS.get(provider, "")
        self.hf_vision_model = hf_vision_model or HF_VISION_MODEL_DEFAULT
        self.hf_text_model   = hf_text_model   or HF_TEXT_MODEL_DEFAULT

    # ── Unified dispatcher ────────────────────────────────────────────────────

    def call(self, system: str, user_text: str,
             image_b64: str | None = None,
             media_type: str = "image/jpeg") -> str:
        """Route a call to the correct provider backend."""
        if self.provider == PROVIDER_MANUAL:
            raise RuntimeError(
                "Manual (Template) mode does not use an AI provider. "
                "Code generation is handled directly by template_library.generate_scad()."
            )
        elif self.provider == PROVIDER_CLAUDE:
            return self._claude_call(system, user_text, image_b64, media_type)
        elif self.provider == PROVIDER_GPT4O:
            return self._gpt4o_call(system, user_text, image_b64, media_type)
        elif self.provider == PROVIDER_HF:
            return self._hf_call(system, user_text, image_b64, media_type)
        else:  # OLLAMA
            return self._ollama_call(system, user_text, image_b64, vision=bool(image_b64))

    # ── Phase A ───────────────────────────────────────────────────────────────

    def extract_dimensions(
        self,
        image_b64:      str | None,
        media_type:     str,
        description:    str,
        printer_name:   str,
        material:       str,
        reference_hint: str = "",   # plain-English hint from scale_inference.hint_text()
    ) -> tuple[str, list[dict], dict]:
        """
        Ask the AI what measurements it needs and attempt relative-scale estimation.
        Returns (object_summary, [{id, question, estimated_value?, ...}], scale_meta).
        scale_meta = {scaling_method, reference_detected, scale_note}
        """
        ref_block = f"\n\n{reference_hint}" if reference_hint.strip() else ""

        user_text = (
            f"Object description: {description}\n"
            f"Target printer: {printer_name}  |  Material: {material}"
            f"{ref_block}\n\n"
            "Analyse the photo (if provided) and the description above. "
            "Estimate dimensions where possible using Relative Scaling. "
            "Return the JSON with the dimensions needed to model this object."
        )

        raw = self.call(_DIM_EXTRACT_SYSTEM, user_text, image_b64, media_type)
        return _parse_dim_response(raw)

    # ── Phase A · Refine (re-ask after user changes) ──────────────────────────

    def refine_dimensions(
        self,
        original_dims:   list[dict],    # [{id, question, estimated_value?}]
        current_values:  dict[str, str], # {id: current user value}
        change_request:  str,            # user's plain-English change description
        image_b64:       str | None = None,
        media_type:      str = "image/jpeg",
    ) -> tuple[str, list[dict], dict]:
        """
        Re-ask the AI to update dimension estimates given a change description.
        Returns same 3-tuple as extract_dimensions.
        Only dimensions mentioned in change_request should be updated; the rest
        are preserved with their current values.
        """
        dim_block = "\n".join(
            f"  {d.get('id','?')}: {current_values.get(d.get('id','?'), '(empty)')} "
            f"← question: {d.get('question','')}"
            for d in original_dims
        )

        user_text = (
            "The user has updated the part description. "
            "Below are the CURRENT dimension values already measured or estimated. "
            "Update ONLY the dimensions affected by the change request; "
            "carry the rest over unchanged.\n\n"
            f"## Current Dimensions\n{dim_block}\n\n"
            f"## Change Request\n{change_request}\n\n"
            "Return the FULL dimensions list in the same JSON format, "
            "with updated estimated_value and estimation_source where relevant."
        )

        system = (
            _DIM_EXTRACT_SYSTEM
            + "\n\nIMPORTANT: preserve unchanged dimensions exactly as given. "
            "Only revise what the change request explicitly affects."
        )

        raw = self.call(system, user_text, image_b64, media_type)
        return _parse_dim_response(raw)

    # ── Phase B ───────────────────────────────────────────────────────────────

    def generate_openscad(
        self,
        description:    str,
        dim_answers:    dict[str, str],   # {id: "question – answer"}
        printer_profile: dict,
        material:       str,
        material_temps: dict,
        centering_text: str,
    ) -> tuple[str, str]:
        """
        Generate OpenSCAD code.
        Returns (openscad_code, design_notes).
        """
        import printer_profiles as pp
        temps = pp.resolve_temps(printer_profile, material, material_temps)
        cx, cy = pp.bed_center(printer_profile)

        dim_block = "\n".join(
            f"  - {info}" for info in dim_answers.values()
        )

        user_text = (
            f"## Object\n{description}\n\n"
            f"## Printer\n"
            f"- Model        : {printer_profile.get('name', 'Unknown')}\n"
            f"- Build volume : {printer_profile['bed_x']} × "
            f"{printer_profile['bed_y']} × {printer_profile['bed_z']} mm\n"
            f"- Notes        : {printer_profile.get('notes', '')}\n\n"
            f"## Material\n"
            f"- Type   : {material}\n"
            f"- Hotend : {temps['hotend']} °C\n"
            f"- Bed    : {temps['bed']} °C\n\n"
            f"## Measured Dimensions\n{dim_block}\n\n"
            f"## Bed Centering (REQUIRED)\n{centering_text}\n"
        )

        raw   = self.call(_OPENSCAD_SYSTEM, user_text)  # no image for CAD gen
        code  = _strip_code_fence(raw)
        fence = re.search(r"```(?:openscad|scad)?\n.*?```", raw, re.DOTALL | re.IGNORECASE)
        notes = raw[fence.end():].strip() if fence else ""
        return code, notes

    # ── Provider implementations ───────────────────────────────────────────────

    def _claude_call(self, system: str, user_text: str,
                      image_b64: str | None = None,
                      media_type: str = "image/jpeg") -> str:
        import anthropic
        content: list = []
        if image_b64:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": image_b64},
            })
        content.append({"type": "text", "text": user_text})

        client = anthropic.Anthropic(api_key=self.api_key)
        resp   = client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": content}],
        )
        return resp.content[0].text

    def _gpt4o_call(self, system: str, user_text: str,
                     image_b64: str | None = None,
                     media_type: str = "image/jpeg") -> str:
        from openai import OpenAI
        content: list = []
        if image_b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{media_type};base64,{image_b64}"},
            })
        content.append({"type": "text", "text": user_text})

        client = OpenAI(api_key=self.api_key)
        resp   = client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": content},
            ],
        )
        return resp.choices[0].message.content or ""

    def _ollama_call(self, system: str, user_text: str,
                      image_b64: str | None = None,
                      vision: bool = False) -> str:
        model = self.model if vision else OLLAMA_TEXT_MODEL
        payload: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user_text},
            ],
            "stream": False,
        }
        if image_b64 and vision:
            payload["messages"][-1]["images"] = [image_b64]

        try:
            resp = requests.post(
                "http://localhost:11434/api/chat",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        except requests.ConnectionError:
            raise RuntimeError(
                "Cannot connect to Ollama. Make sure `ollama serve` is running on port 11434."
            )
        except Exception as exc:
            raise RuntimeError(f"Ollama error: {exc}") from exc

    def _hf_call(self, system: str, user_text: str,
                  image_b64: str | None = None,
                  media_type: str = "image/jpeg") -> str:
        """
        Call a Hugging Face Inference API model (free tier).
        Uses the vision model when an image is present, text model otherwise.
        """
        try:
            from huggingface_hub import InferenceClient
        except ImportError:
            raise RuntimeError(
                "huggingface_hub is not installed. Run: pip install huggingface_hub"
            )

        model = self.hf_vision_model if image_b64 else self.hf_text_model

        # Build user content — multimodal if image present
        if image_b64:
            user_content: list | str = [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{image_b64}"},
                },
                {"type": "text", "text": user_text},
            ]
        else:
            user_content = user_text

        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_content},
        ]

        token = self.api_key or None   # None → anonymous (very low rate limit)
        client = InferenceClient(token=token)

        try:
            resp = client.chat_completion(
                model=model,
                messages=messages,
                max_tokens=4096,
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            err = str(exc)
            if "401" in err or "unauthorized" in err.lower():
                raise RuntimeError(
                    "Hugging Face token invalid or missing. "
                    "Get a free token at huggingface.co/settings/tokens"
                ) from exc
            if "429" in err or "rate limit" in err.lower():
                raise RuntimeError(
                    "Hugging Face rate limit hit. "
                    "Wait a moment or add a token for higher limits."
                ) from exc
            if "503" in err or "loading" in err.lower():
                raise RuntimeError(
                    f"Model '{model}' is loading on HF servers — try again in 30 seconds."
                ) from exc
            raise RuntimeError(f"Hugging Face error: {exc}") from exc
