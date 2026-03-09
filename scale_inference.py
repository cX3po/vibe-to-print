"""
scale_inference.py
------------------
Reference-object database and helpers for "no-caliper" relative scaling.

Common objects with internationally standardised or well-known dimensions
are stored here. The app injects the user's chosen reference into the AI
prompt so the model can estimate target-object dimensions from pixel ratios.

Public API
----------
REFERENCE_DB               dict  – all known reference objects
all_ui_options()           -> list[tuple[str, str]]  (label, key) for dropdowns
hint_text(key)             -> str   injected into the AI prompt
describe_reference(key)    -> str   human-readable description for UI
"""

from __future__ import annotations

# ── Reference object database ─────────────────────────────────────────────────
# Each entry:
#   name        : display name shown in UI
#   dims        : dict of {measurement_name: value_mm}  (standardised sizes)
#   notes       : optional caveat / source
#   confidence  : baseline confidence level when used as reference
#
# Sources:
#   ISO/IEC 7810 (card dimensions), US Mint, EU Mint, IEC 60086 (batteries)

REFERENCE_DB: dict[str, dict] = {

    # ── Auto-detect (no hint — AI scans the whole image) ─────────────────────
    "auto": {
        "name":       "Auto-detect (AI picks the reference)",
        "dims":       {},
        "notes":      "The AI will scan the photo and identify any recognisable "
                      "reference objects on its own.",
        "confidence": "medium",
    },

    # ── Cards ─────────────────────────────────────────────────────────────────
    "credit_card": {
        "name":       "Credit / debit card",
        "dims":       {"width": 85.60, "height": 53.98, "thickness": 0.76},
        "notes":      "ISO/IEC 7810 ID-1 standard. Any Visa, Mastercard, "
                      "Amex, bank card. Width is the long side.",
        "confidence": "high",
    },
    "business_card_us": {
        "name":       "Business card (US, 3.5\" × 2\")",
        "dims":       {"width": 88.90, "height": 50.80},
        "notes":      "Standard North American business card size.",
        "confidence": "high",
    },
    "business_card_eu": {
        "name":       "Business card (EU, 85 × 55 mm)",
        "dims":       {"width": 85.00, "height": 55.00},
        "notes":      "Standard European business card size.",
        "confidence": "high",
    },

    # ── US coins ─────────────────────────────────────────────────────────────
    "us_quarter": {
        "name":       "US quarter (25¢)",
        "dims":       {"diameter": 24.26, "thickness": 1.75},
        "notes":      "Very common; excellent reference for small parts.",
        "confidence": "high",
    },
    "us_penny": {
        "name":       "US penny (1¢)",
        "dims":       {"diameter": 19.05, "thickness": 1.52},
        "confidence": "high",
    },
    "us_dime": {
        "name":       "US dime (10¢)",
        "dims":       {"diameter": 17.91, "thickness": 1.35},
        "confidence": "high",
    },
    "us_nickel": {
        "name":       "US nickel (5¢)",
        "dims":       {"diameter": 21.21, "thickness": 1.95},
        "confidence": "high",
    },
    "us_half_dollar": {
        "name":       "US half dollar (50¢)",
        "dims":       {"diameter": 30.61, "thickness": 2.15},
        "confidence": "high",
    },

    # ── EU / UK coins ─────────────────────────────────────────────────────────
    "euro_1": {
        "name":       "€1 euro coin",
        "dims":       {"diameter": 23.25, "thickness": 2.33},
        "confidence": "high",
    },
    "euro_2": {
        "name":       "€2 euro coin",
        "dims":       {"diameter": 25.75, "thickness": 2.20},
        "confidence": "high",
    },
    "euro_50c": {
        "name":       "€0.50 euro coin",
        "dims":       {"diameter": 24.25, "thickness": 2.38},
        "confidence": "high",
    },
    "uk_10p": {
        "name":       "UK 10p coin",
        "dims":       {"diameter": 24.50, "thickness": 1.85},
        "confidence": "high",
    },
    "uk_pound": {
        "name":       "UK £1 coin",
        "dims":       {"diameter": 23.43, "thickness": 2.80},
        "confidence": "high",
    },

    # ── Batteries ─────────────────────────────────────────────────────────────
    "aa_battery": {
        "name":       "AA battery",
        "dims":       {"diameter": 14.50, "length": 50.50},
        "notes":      "IEC 60086 standard. Any brand. Lay flat for best reference.",
        "confidence": "high",
    },
    "aaa_battery": {
        "name":       "AAA battery",
        "dims":       {"diameter": 10.50, "length": 44.50},
        "confidence": "high",
    },
    "c_battery": {
        "name":       "C battery",
        "dims":       {"diameter": 26.20, "length": 50.00},
        "confidence": "high",
    },
    "d_battery": {
        "name":       "D battery",
        "dims":       {"diameter": 34.20, "length": 61.50},
        "confidence": "high",
    },
    "9v_battery": {
        "name":       "9V battery (PP3)",
        "dims":       {"width": 26.50, "height": 17.50, "length": 48.50},
        "confidence": "high",
    },

    # ── Common hardware ───────────────────────────────────────────────────────
    "usb_a": {
        "name":       "USB-A connector",
        "dims":       {"width": 12.00, "height": 4.50, "depth": 17.00},
        "notes":      "The plug end that goes into a PC port.",
        "confidence": "high",
    },
    "matchbox": {
        "name":       "Standard matchbox",
        "dims":       {"length": 57.00, "width": 36.00, "height": 15.00},
        "notes":      "Bryant & May / Swan Vesta style. Sizes vary slightly.",
        "confidence": "medium",
    },
    "m4_bolt_head": {
        "name":       "M4 hex bolt head",
        "dims":       {"across_flats": 7.00, "height": 3.20},
        "notes":      "ISO 4014. Good for very small scale references.",
        "confidence": "high",
    },
    "m6_bolt_head": {
        "name":       "M6 hex bolt head",
        "dims":       {"across_flats": 10.00, "height": 4.00},
        "confidence": "high",
    },

    # ── Body parts (lowest confidence — high variability) ─────────────────────
    "thumb_adult": {
        "name":       "Adult human thumb (rough guide only)",
        "dims":       {"width": 20.00},
        "notes":      "Average adult thumb width ~18-22 mm. Highly variable. "
                      "Use only as a last resort.",
        "confidence": "low",
    },
    "finger_adult": {
        "name":       "Adult index finger (rough guide only)",
        "dims":       {"width": 16.00},
        "notes":      "Average adult index finger ~14-18 mm wide.",
        "confidence": "low",
    },

    # ── Ruler / tape ──────────────────────────────────────────────────────────
    "ruler_mm": {
        "name":       "Ruler or tape measure (mm markings visible)",
        "dims":       {},
        "notes":      "The AI will read the mm markings directly from the photo.",
        "confidence": "high",
    },
    "ruler_inch": {
        "name":       "Ruler or tape measure (inch markings visible)",
        "dims":       {},
        "notes":      "The AI will read the inch markings and convert to mm.",
        "confidence": "high",
    },
}


# ── Grouped options for the UI dropdown ──────────────────────────────────────

_GROUPS: list[tuple[str, list[str]]] = [
    ("Auto",      ["auto"]),
    ("Cards",     ["credit_card", "business_card_us", "business_card_eu"]),
    ("US Coins",  ["us_quarter", "us_penny", "us_dime", "us_nickel",
                   "us_half_dollar"]),
    ("EU/UK Coins", ["euro_1", "euro_2", "euro_50c", "uk_10p", "uk_pound"]),
    ("Batteries", ["aa_battery", "aaa_battery", "c_battery",
                   "d_battery", "9v_battery"]),
    ("Hardware",  ["usb_a", "matchbox", "m4_bolt_head", "m6_bolt_head"]),
    ("Ruler",     ["ruler_mm", "ruler_inch"]),
    ("Body (low confidence)", ["thumb_adult", "finger_adult"]),
]

# Flat ordered list with group headers for st.selectbox
_FLAT_OPTIONS: list[str] = []
_KEY_FOR_LABEL: dict[str, str] = {}   # label → key

for _group, _keys in _GROUPS:
    for _k in _keys:
        _label = REFERENCE_DB[_k]["name"]
        _FLAT_OPTIONS.append(_label)
        _KEY_FOR_LABEL[_label] = _k


def all_ui_labels() -> list[str]:
    """Return ordered list of display labels for st.selectbox."""
    return _FLAT_OPTIONS.copy()


def key_for_label(label: str) -> str:
    """Convert a display label back to its database key."""
    return _KEY_FOR_LABEL.get(label, "auto")


def describe_reference(key: str) -> str:
    """Return a short human-readable description for display in the UI."""
    ref = REFERENCE_DB.get(key, REFERENCE_DB["auto"])
    name  = ref["name"]
    dims  = ref.get("dims", {})
    notes = ref.get("notes", "")
    conf  = ref.get("confidence", "medium")

    dim_parts = [f"{k}: {v} mm" for k, v in dims.items()]
    dim_str   = " · ".join(dim_parts) if dim_parts else "AI reads markings from photo"

    return f"**{name}**  \n{dim_str}  \n_{notes}_  \nConfidence: `{conf}`"


def hint_text(key: str) -> str:
    """
    Return the text injected into the AI prompt describing the reference object.
    This tells the AI exactly what to look for and what dimensions to use.
    """
    ref = REFERENCE_DB.get(key, REFERENCE_DB["auto"])

    if key == "auto":
        return (
            "SCALING HINT: The user has not placed a specific reference object. "
            "Scan the entire photo carefully for ANY recognisable reference object "
            "(coins, cards, batteries, hardware, ruler markings, or hands) and use "
            "its known dimensions to estimate the scale. State which reference you "
            "found and how confident you are."
        )

    if key in ("ruler_mm", "ruler_inch"):
        unit = "mm" if key == "ruler_mm" else "inches (convert to mm)"
        return (
            f"SCALING HINT: A ruler/tape measure with {unit} markings is visible "
            f"in the photo. Read the scale markings directly and use them to measure "
            f"the target object. This is a high-confidence reference."
        )

    dims      = ref.get("dims", {})
    dim_parts = [f"{k} = {v} mm" for k, v in dims.items()]
    dim_str   = ", ".join(dim_parts) if dim_parts else "see notes"
    notes     = ref.get("notes", "")
    conf      = ref.get("confidence", "medium")

    return (
        f"SCALING HINT: The user has placed a '{ref['name']}' next to the object "
        f"as a size reference. Known dimensions: {dim_str}. "
        f"{('Note: ' + notes) if notes else ''} "
        f"Use this reference to calculate the pixel-to-mm ratio and estimate the "
        f"target object's dimensions. Confidence of this reference: {conf}. "
        f"Report which dimension of the reference you used and how you derived "
        f"the scale factor."
    )


def tip_card_html() -> str:
    """Return the HTML for the 'No calipers?' tip card shown in the UI."""
    return """
<div style="
    background: linear-gradient(135deg, #1d3557 0%, #14213d 100%);
    border: 1px solid #457b9d;
    border-radius: 12px;
    padding: 16px 18px;
    margin: 10px 0 14px 0;
">
  <div style="font-size:17px;font-weight:700;color:#a8dadc;margin-bottom:8px">
    📏 No calipers? Use a reference object!
  </div>
  <div style="color:#cdd8e0;font-size:15px;line-height:1.6">
    Place <strong>one of these</strong> next to the part and retake the photo:
  </div>
  <div style="
      display:flex; gap:12px; flex-wrap:wrap;
      margin-top:10px; margin-bottom:6px;
  ">
    <div style="background:#0d1b2a;border-radius:8px;padding:8px 12px;
                border:1px solid #2a4a6a;text-align:center;flex:1;min-width:90px">
      <div style="font-size:22px">💳</div>
      <div style="color:#e0f0ff;font-size:13px;font-weight:600">Credit card</div>
      <div style="color:#7a9ab8;font-size:12px">85.6 × 54.0 mm</div>
    </div>
    <div style="background:#0d1b2a;border-radius:8px;padding:8px 12px;
                border:1px solid #2a4a6a;text-align:center;flex:1;min-width:90px">
      <div style="font-size:22px">🪙</div>
      <div style="color:#e0f0ff;font-size:13px;font-weight:600">US quarter</div>
      <div style="color:#7a9ab8;font-size:12px">24.26 mm dia</div>
    </div>
    <div style="background:#0d1b2a;border-radius:8px;padding:8px 12px;
                border:1px solid #2a4a6a;text-align:center;flex:1;min-width:90px">
      <div style="font-size:22px">🔋</div>
      <div style="color:#e0f0ff;font-size:13px;font-weight:600">AA battery</div>
      <div style="color:#7a9ab8;font-size:12px">14.5 mm dia</div>
    </div>
    <div style="background:#0d1b2a;border-radius:8px;padding:8px 12px;
                border:1px solid #2a4a6a;text-align:center;flex:1;min-width:90px">
      <div style="font-size:22px">📏</div>
      <div style="color:#e0f0ff;font-size:13px;font-weight:600">Ruler</div>
      <div style="color:#7a9ab8;font-size:12px">Direct reading</div>
    </div>
  </div>
  <div style="color:#7a9ab8;font-size:13px;margin-top:4px">
    Then select the reference object from the dropdown below.
  </div>
</div>
"""
