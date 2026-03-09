"""
project_manager.py
------------------
Save and load a complete Vibe-to-Print project as a single JSON file.

The project file (.vtp.json) captures everything needed to resume from any
phase: description, printer profile, material, dimension measurements,
OpenSCAD code, and all AI metadata.

Public API
----------
build_project(ss)   -> dict         serialise session state to a plain dict
to_json_bytes(d)    -> bytes         encode as pretty-printed JSON UTF-8
from_json_bytes(b)  -> dict          parse and validate; raises ValueError on error
apply_to_session(d, ss)             restore dict into st.session_state
project_filename(ss) -> str          suggest a filename for the download
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

# ── Schema version — bump when breaking changes are made ─────────────────────
_VERSION = "2.0"

# Keys that are safe to serialise (exclude runtime-only / binary fields)
_SERIALISABLE = [
    "phase",
    "image_name",
    "image_media_type",
    "vibe_description",
    "object_summary",
    "required_dims",
    "dim_values",
    "dim_statuses",
    "dim_answers",
    "scale_meta",
    "ref_obj_key",
    "openscad_code",
    "openscad_notes",
    "slicer_log",
    "ds_result",
    "ds_confirmed",
    "active_profile",
    "material",
    "work_dir",
    "stl_path",
    "gcode_path",
]

# Keys that must be restored but NOT written (they hold bytes or None)
_SKIP_WRITE = {"image_bytes"}   # raw bytes — too large; saved separately if needed


# ── Serialise ─────────────────────────────────────────────────────────────────

def build_project(ss: Any) -> dict:
    """
    Read the relevant keys from st.session_state and return a plain dict
    safe for JSON serialisation.
    `ss` is st.session_state (passed explicitly to keep this module testable).
    """
    payload: dict = {
        "_schema":    _VERSION,
        "_saved_at":  datetime.now(timezone.utc).isoformat(),
        "_app":       "Universal Vibe-to-Print Engine",
    }
    for key in _SERIALISABLE:
        val = getattr(ss, key, None)
        # Streamlit stores session state as attribute OR dict-key; try both
        if val is None:
            val = ss.get(key, None) if hasattr(ss, "get") else None
        payload[key] = _make_serialisable(val)

    return payload


def _make_serialisable(obj: Any) -> Any:
    """Recursively convert any non-JSON-safe types."""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, dict):
        return {str(k): _make_serialisable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serialisable(v) for v in obj]
    if isinstance(obj, bytes):
        return None   # skip raw bytes
    return str(obj)   # last resort


def to_json_bytes(project: dict) -> bytes:
    """Return UTF-8 encoded, pretty-printed JSON."""
    return json.dumps(project, indent=2, ensure_ascii=False).encode("utf-8")


def project_filename(ss: Any) -> str:
    """Suggest a download filename based on the vibe description."""
    vibe = getattr(ss, "vibe_description", "") or ""
    slug = "_".join(vibe.split()[:4]).lower()
    # Keep only alphanumeric + underscores
    slug = "".join(c if c.isalnum() or c == "_" else "" for c in slug) or "project"
    ts   = datetime.now().strftime("%Y%m%d_%H%M")
    return f"vibe_{slug}_{ts}.vtp.json"


# ── Deserialise ───────────────────────────────────────────────────────────────

def from_json_bytes(raw: bytes) -> dict:
    """
    Parse a .vtp.json file.  Returns the project dict.
    Raises ValueError with a human-readable message on failure.
    """
    try:
        text = raw.decode("utf-8")
    except Exception as exc:
        raise ValueError(f"File is not valid UTF-8: {exc}") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Project file must be a JSON object.")

    schema = data.get("_schema", "unknown")
    if schema not in (_VERSION, "1.0"):   # accept older saves
        raise ValueError(
            f"Unrecognised project schema version '{schema}'. "
            f"This app expects version {_VERSION}."
        )
    return data


def apply_to_session(project: dict, ss: Any) -> list[str]:
    """
    Restore a project dict into st.session_state.
    Returns a list of keys that were restored, for logging.
    `ss` is st.session_state.
    """
    restored: list[str] = []
    for key in _SERIALISABLE:
        if key in project:
            try:
                ss[key] = project[key]
                restored.append(key)
            except Exception:
                pass   # read-only key or session error — skip silently
    return restored


# ── Convenience: build a human-readable project summary ──────────────────────

def project_summary(project: dict) -> str:
    """Return a short markdown string describing the saved project."""
    saved_at = project.get("_saved_at", "unknown time")
    vibe     = project.get("vibe_description", "—")[:120]
    phase    = project.get("phase", "unknown")
    printer  = (project.get("active_profile") or {}).get("name", "—")
    material = project.get("material", "—")
    n_dims   = len(project.get("required_dims") or [])
    has_code = bool(project.get("openscad_code"))

    return (
        f"**Saved:** {saved_at[:19].replace('T', ' ')} UTC  \n"
        f"**Phase:** {phase}  \n"
        f"**Vibe:** {vibe}  \n"
        f"**Printer:** {printer}  ·  **Material:** {material}  \n"
        f"**Dimensions:** {n_dims}  ·  **OpenSCAD:** {'yes' if has_code else 'not yet'}"
    )
