"""
Universal Vibe-to-Print Engine
A mobile-first Streamlit app for photo → OpenSCAD → G-code → Printer.
"""

import base64
import hashlib
import tempfile
import urllib.parse
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import ai_brains        as ab
import caliper_guide    as cg
import deep_search      as ds
import getting_started  as gs
import printer_profiles as pp
import project_manager  as pm
import pwa
import scale_inference  as si
import slicer           as sl
import template_library as tl
import transfer         as tr
import viewer3d         as v3d
import hf_identify      as hfi
import web_search       as ws

# ══════════════════════════════════════════════════════════════════════════════
# Page config & mobile-first CSS
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Vibe-to-Print Engine",
    page_icon="🖨️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

pwa.inject()   # PWA meta tags — must come right after set_page_config

st.markdown("""
<style>
/* ── Strip Streamlit chrome ───────────────────────────────────── */
footer { display: none !important; }
header[data-testid="stHeader"] { height: 2.2rem !important; min-height: 2.2rem !important; }
#MainMenu { visibility: hidden; }

/* ── Remove excessive container padding ───────────────────────── */
.main .block-container {
    padding-top: 0.4rem !important;
    padding-bottom: 0.5rem !important;
    padding-left: 0.75rem !important;
    padding-right: 0.75rem !important;
    max-width: 100% !important;
}

/* ── Global font ──────────────────────────────────────────────── */
html, body, [class*="css"] { font-size: 15px !important; }

/* ── Headings — no excess margin ─────────────────────────────── */
h1, h2, h3 {
    margin-top: 0.1rem !important;
    margin-bottom: 0.2rem !important;
    line-height: 1.2 !important;
}
p { margin-bottom: 0.3rem !important; }

/* ── All secondary buttons — compact touch targets ────────────── */
div.stButton > button {
    min-height: 42px !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    border-radius: 10px !important;
    width: 100%;
    padding: 4px 8px !important;
}

/* ── Primary action buttons — large for thumb taps ────────────── */
div.stButton > button[kind="primary"] {
    min-height: 56px !important;
    font-size: 17px !important;
    font-weight: 700 !important;
    background: #e94560 !important;
    color: #ffffff !important;
    border: none !important;
}
div.stButton > button[kind="primary"]:hover { background: #c73050 !important; }

/* ── Download buttons ─────────────────────────────────────────── */
div.stDownloadButton > button {
    min-height: 46px !important;
    font-size: 15px !important;
    font-weight: 700 !important;
    background: #2d6a4f !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    width: 100%;
}

/* ── Upload area — compact on mobile ──────────────────────────── */
section[data-testid="stFileUploader"] > div {
    min-height: 70px !important;
    font-size: 14px !important;
    padding: 8px !important;
}

/* ── Camera widget — full-width prominent ─────────────────────── */
section[data-testid="stCameraInput"] > div {
    border-radius: 12px !important;
}

/* ── Text areas & inputs ──────────────────────────────────────── */
textarea { font-size: 15px !important; }
input[type="text"], input[type="password"], input[type="number"] {
    font-size: 15px !important;
}

/* ── Dim input colour coding ──────────────────────────────────── */
div[data-suggested="true"] input {
    background-color: rgba(58,120,201,0.18) !important;
    border-color: #4a9eff !important; border-width: 2px !important;
}
div[data-verified="true"] input {
    background-color: rgba(45,106,79,0.20) !important;
    border-color: #52b788 !important; border-width: 2px !important;
}
div[data-userentered="true"] input {
    background-color: rgba(180,180,180,0.08) !important;
    border-color: #8899aa !important; border-width: 2px !important;
}

/* ── Expanders — compact ──────────────────────────────────────── */
details summary { font-size: 13px !important; padding: 4px 0 !important; }

/* ── Alerts — smaller padding ─────────────────────────────────── */
div[data-testid="stAlert"] { padding: 8px 12px !important; font-size: 13px !important; }

/* ── Dividers — thinner ───────────────────────────────────────── */
hr { margin: 0.4rem 0 !important; }

/* ── Phase badge (legacy, kept for getting_started) ───────────── */
.phase-badge {
    display: inline-block; padding: 4px 14px; border-radius: 20px;
    font-size: 13px; font-weight: 700; margin-bottom: 8px;
}
.phase-a { background:#1d3557; color:#a8dadc; }
.phase-b { background:#2d6a4f; color:#b7e4c7; }
.phase-c { background:#7b2d8b; color:#e0aaff; }
.phase-x { background:#b5451b; color:#ffd6a5; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════════════

MATERIAL_TEMPS = {
    "PLA":  {"hotend": 210, "bed": 60},
    "PETG": {"hotend": 235, "bed": 85},
    "ABS":  {"hotend": 245, "bed": 110},
}

PHASES = ["getting_started", "vision", "deep_review", "dimensions",
          "cad", "slicer", "export"]

PHASE_LABELS = {
    "getting_started": ("?", "Getting Started",  "phase-a"),
    "vision":          ("A", "The Vision",       "phase-a"),
    "deep_review":     ("A", "Deep Search",      "phase-a"),
    "dimensions":      ("A", "Measuring Up",     "phase-a"),
    "cad":             ("B", "The CAD",          "phase-b"),
    "slicer":          ("C", "The Slicer",       "phase-c"),
    "export":          ("X", "Export & Send",    "phase-x"),
}

# ══════════════════════════════════════════════════════════════════════════════
# Session-state initialisation
# ══════════════════════════════════════════════════════════════════════════════

_DEFAULTS = {
    "phase":             "vision",
    "image_bytes":       None,
    "image_name":        "",
    "image_media_type":  "image/jpeg",
    "vibe_description":  "",
    "object_summary":    "",
    "required_dims":     [],   # [{id, question, prefill?}]
    "dim_answers":       {},   # {id: "question – value mm"}
    "openscad_code":     "",
    "openscad_notes":    "",
    "work_dir":          None, # str path
    "stl_path":          None, # str path
    "gcode_path":        None, # str path
    "slicer_log":        "",
    "active_profile":    None,
    "material":          "PLA",
    # Deep Search
    "ds_result":         None,  # dict (DeepSearchResult.as_dict())
    "ds_confirmed":      False,
    # Scale inference
    "scale_meta":        None,  # {scaling_method, reference_detected, scale_note}
    "ref_obj_key":       "auto",
    # Smart Suggestions / dimension confirmation
    "dim_values":        {},    # {id: current string value}
    "dim_statuses":      {},    # {id: "suggested"|"verified"|"user_entered"|"empty"}
    "dims_confirmed":    False,
    # Getting Started
    "gs_test_ok":        None,
    "gs_test_message":   "",
    "gs_test_detail":    "",
    "gs_pending_key":    None,
    "gs_video_url":      "",
    # Hugging Face provider
    "hf_vision_model":   ab.HF_VISION_MODEL_DEFAULT,
    "hf_text_model":     ab.HF_TEXT_MODEL_DEFAULT,
    # Manual / Template mode
    "selected_template_id": None,   # template chosen in template browser
    # Multi-photo capture
    "captured_images":      [],     # list of {bytes, name, media_type}
    "camera_counter":       0,      # incremented each snap to reset the widget
    "last_cam_hash":        "",     # prevents double-processing same photo
    # Default AI provider (no-key mode for new users)
    "ai_provider":          "Manual (No AI — Template Mode)",
    # Dims fingerprint — detects if measurements changed after SCAD was generated
    "scad_dims_fp":         "",
    # Identify result card (persisted across reruns)
    "_identify_result":     None,   # dict from hfi.identify_object or None
}

for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


def reset_to(phase: str) -> None:
    """Reset session state to the beginning of a given phase."""
    resets = {
        "vision":     list(_DEFAULTS.keys()),
        "dimensions": ["dim_answers", "dim_values", "dim_statuses", "dims_confirmed",
                       "scale_meta", "openscad_code", "openscad_notes",
                       "stl_path", "gcode_path", "slicer_log"],
        "cad":        ["openscad_code", "openscad_notes",
                       "stl_path", "gcode_path", "slicer_log"],
        "slicer":     ["stl_path", "gcode_path", "slicer_log"],
        "export":     [],
    }
    for k in resets.get(phase, []):
        st.session_state[k] = _DEFAULTS[k]
    st.session_state.phase = phase


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=10)
def _all_profiles() -> dict:
    return pp.load_all_profiles()


def _is_manual() -> bool:
    return st.session_state.get("ai_provider") == ab.PROVIDER_MANUAL


def _needs_no_key() -> bool:
    """True for providers that work without a paid API key."""
    return st.session_state.get("ai_provider") in (
        ab.PROVIDER_OLLAMA, ab.PROVIDER_HF, ab.PROVIDER_MANUAL
    )


def _get_brain() -> ab.AIBrain:
    provider = st.session_state.get("ai_provider", ab.PROVIDER_CLAUDE)
    key      = st.session_state.get("api_key", "")
    model    = st.session_state.get("model_override", "")
    return ab.AIBrain(
        provider, key, model,
        hf_vision_model=st.session_state.get("hf_vision_model", ab.HF_VISION_MODEL_DEFAULT),
        hf_text_model=st.session_state.get("hf_text_model",   ab.HF_TEXT_MODEL_DEFAULT),
    )


def _active_profile() -> dict:
    return st.session_state.active_profile or {
        "name": "Unknown", "bed_x": 235, "bed_y": 235, "bed_z": 250, "notes": ""
    }


def _work_dir() -> Path:
    if st.session_state.work_dir is None:
        td = tempfile.mkdtemp(prefix="vibe_")
        st.session_state.work_dir = td
    return Path(st.session_state.work_dir)


def _phase_badge(phase: str) -> None:
    letter, label, css = PHASE_LABELS.get(phase, ("?", phase, "phase-a"))
    st.markdown(
        f'<span class="phase-badge {css}">Phase {letter} · {label}</span>',
        unsafe_allow_html=True,
    )


def _wizard_header(phase: str) -> None:
    """Interactive wizard navigation — each completed step is a clickable button."""
    _STEPS = [
        ("📸", "Snap",    "vision",     ["vision", "deep_review"]),
        ("📏", "Measure", "dimensions", ["dimensions"]),
        ("⚙️", "Design",  "cad",        ["cad"]),
        ("🔪", "Slice",   "slicer",     ["slicer"]),
        ("🖨️", "Print",   "export",     ["export"]),
    ]
    _ORDER = ["vision", "deep_review", "dimensions", "cad", "slicer", "export"]
    try:
        cur_idx = _ORDER.index(phase)
    except ValueError:
        cur_idx = 0

    # Which phases can the user jump to directly?
    _reachable = {
        "vision":      True,
        "deep_review": bool(st.session_state.get("ds_result")),
        "dimensions":  bool(st.session_state.get("required_dims")),
        "cad":         bool(st.session_state.get("openscad_code") or
                            st.session_state.get("dims_confirmed")),
        "slicer":      bool(st.session_state.get("openscad_code")),
        "export":      bool(st.session_state.get("gcode_path")),
    }

    cols = st.columns(len(_STEPS))
    for col, (icon, label, target, step_phases) in zip(cols, _STEPS):
        step_max_idx = max((_ORDER.index(p) for p in step_phases if p in _ORDER), default=0)
        is_active = phase in step_phases
        is_done   = cur_idx > step_max_idx
        can_click = (not is_active) and _reachable.get(target, False)

        disp = f"✓ {label}" if is_done else f"{icon} {label}"

        with col:
            if col.button(
                disp,
                key=f"wiz_{target}",
                use_container_width=True,
                disabled=not can_click,
                type="primary" if is_active else "secondary",
                help="You're here" if is_active else
                     ("Jump to this step" if can_click else "Complete earlier steps first"),
            ):
                st.session_state.phase = target
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    # ── Logo ──────────────────────────────────────────────────────────────────
    st.markdown("""
<div style="text-align:center;padding:8px 0 2px">
  <div style="font-size:24px;font-weight:800;color:#a8dadc;letter-spacing:-0.5px">
    🖨️ Vibe-to-Print
  </div>
  <div style="font-size:12px;color:#4a7090;margin-top:2px">Snap · Measure · Print</div>
</div>""", unsafe_allow_html=True)

    # ── Quick action row ───────────────────────────────────────────────────────
    gs_active = st.session_state.phase == "getting_started"
    qa1, qa2 = st.columns(2)
    with qa1:
        if st.button("❓ Help", use_container_width=True,
                     type="primary" if gs_active else "secondary"):
            st.session_state.phase = "vision" if gs_active else "getting_started"
            st.rerun()
    with qa2:
        if st.button("↺ Restart", use_container_width=True):
            reset_to("vision")
            st.rerun()

    st.divider()

    # ── Quick settings (always visible) ───────────────────────────────────────
    all_profiles = _all_profiles()
    profile_names = sorted(all_profiles.keys()) + ["➕ Add New Printer"]
    chosen  = st.selectbox("🖨️ Printer", profile_names, key="printer_choice")
    adding  = chosen == "➕ Add New Printer"
    material = st.selectbox("🧵 Material", list(MATERIAL_TEMPS.keys()), key="material")

    st.divider()

    # ── Advanced Settings expander ─────────────────────────────────────────────
    with st.expander("⚙️ Advanced Settings", expanded=False):

        # ── AI Brain ──────────────────────────────────────────────────────────
        st.subheader("AI Brain")
        provider = st.selectbox(
            "Select AI provider",
            ab.ALL_PROVIDERS,
            key="ai_provider",
        )

        if provider == ab.PROVIDER_OLLAMA:
            st.info("Ollama: `ollama serve` must be running on port 11434.\n"
                    "Vision uses **llava**; code gen uses **llama3**.")
            st.text_input("Model override (optional)", placeholder="e.g. llava:13b",
                          key="model_override")

        elif provider == ab.PROVIDER_HF:
            st.info(
                "**Free tier** — no credit card needed.\n\n"
                "Optional token at [huggingface.co/settings/tokens]"
                "(https://huggingface.co/settings/tokens) for higher rate limits.",
                icon="🤗",
            )
            st.text_input("HF Token (optional)", type="password",
                          placeholder="hf_...", key="api_key",
                          help="Read token from huggingface.co/settings/tokens")
            st.selectbox("Vision model (photos)", ab.HF_VISION_MODELS,
                         key="hf_vision_model",
                         help="Used when a photo is attached")
            st.selectbox("Text model (CAD gen)", ab.HF_TEXT_MODELS,
                         key="hf_text_model",
                         help="Used for OpenSCAD code generation")

        elif provider == ab.PROVIDER_MANUAL:
            st.success(
                "**No API key needed!**\n\n"
                "Choose from 12 built-in parametric templates — knobs, boxes, "
                "brackets, hooks, and more.",
                icon="🛠️",
            )

        else:
            label = "Anthropic API Key" if provider == ab.PROVIDER_CLAUDE else "OpenAI API Key"
            st.text_input(label, type="password", placeholder="sk-...", key="api_key")
            st.text_input("Model override (optional)",
                          placeholder=ab.DEFAULT_MODELS[provider],
                          key="model_override")

        # ── Bed Dimensions ─────────────────────────────────────────────────────
        st.divider()
        st.subheader("Bed Dimensions")

        if adding:
            new_name = st.text_input("New printer name", placeholder="My CoreXY 300",
                                     key="new_printer_name")
            bx, by, bz = 235, 235, 250
            bnotes = ""
        else:
            prof     = all_profiles[chosen]
            new_name = chosen
            bx, by, bz = prof["bed_x"], prof["bed_y"], prof["bed_z"]
            bnotes   = prof.get("notes", "")

        c1, c2, c3 = st.columns(3)
        bed_x = c1.number_input("X mm", 50, 1500, bx, 5, key="bed_x")
        bed_y = c2.number_input("Y mm", 50, 1500, by, 5, key="bed_y")
        bed_z = c3.number_input("Z mm", 50, 1500, bz, 5, key="bed_z")
        bed_notes = st.text_input("Notes", value=bnotes, key="bed_notes")

        cx_live = bed_x / 2; cy_live = bed_y / 2
        st.caption(f"Bed centre → X: **{cx_live:.1f}**  Y: **{cy_live:.1f}** mm")

        sc1, sc2 = st.columns(2)
        with sc1:
            if st.button("Save Profile", use_container_width=True):
                tgt = new_name.strip() if adding else chosen
                if tgt:
                    pp.save_user_profile(tgt, int(bed_x), int(bed_y), int(bed_z), bed_notes)
                    st.success(f'Saved "{tgt}"')
                    st.cache_data.clear()
                    st.rerun()
        with sc2:
            can_del = not adding and pp.is_user_profile(chosen)
            if st.button("Delete", disabled=not can_del, use_container_width=True,
                         help="Only user-saved profiles can be deleted"):
                pp.delete_user_profile(chosen)
                st.cache_data.clear()
                st.rerun()

        # ── Temperatures ───────────────────────────────────────────────────────
        st.divider()
        _adv_active_p: dict = {
            "name":  new_name if adding else chosen,
            "bed_x": int(bed_x), "bed_y": int(bed_y), "bed_z": int(bed_z),
            "notes": bed_notes,
        }
        if not adding:
            for _k in ("hotend_override", "bed_override"):
                if _k in all_profiles.get(chosen, {}):
                    _adv_active_p[_k] = all_profiles[chosen][_k]
        temps = pp.resolve_temps(_adv_active_p, material, MATERIAL_TEMPS)
        st.caption(f"Hotend: **{temps['hotend']} °C**  ·  Bed: **{temps['bed']} °C**")

        # ── Deep Search ────────────────────────────────────────────────────────
        st.divider()
        st.subheader("Deep Search")
        ds_enabled = st.toggle(
            "Enable Deep Search mode",
            value=False,
            key="ds_enabled",
            help="Identifies the exact model and looks up factory specs.",
        )

        if ds_enabled:
            st.text_input(
                "Google Cloud Vision API key",
                type="password",
                key="gcv_api_key",
                placeholder="AIza...",
                help="Get a key at console.cloud.google.com → Vision API.",
            )
            st.selectbox(
                "Web search provider",
                ds.ALL_SEARCH_PROVIDERS,
                key="ds_search_provider",
                help="Searches for factory specs after identification.",
            )
            search_prov = st.session_state.get("ds_search_provider", ds.SEARCH_PROVIDER_AI)
            if search_prov != ds.SEARCH_PROVIDER_AI:
                lbl = "SerpAPI key" if "SerpAPI" in search_prov else "Brave API key"
                st.text_input(lbl, type="password", key="ds_search_api_key",
                              placeholder="your-key-here")
            else:
                st.caption("AI Knowledge Only: no web call — specs from AI training data.")

        # ── Project File ───────────────────────────────────────────────────────
        st.divider()
        st.subheader("Project File")

        proj_bytes = pm.to_json_bytes(pm.build_project(st.session_state))
        st.download_button(
            label="Save Project (.vtp.json)",
            data=proj_bytes,
            file_name=pm.project_filename(st.session_state),
            mime="application/json",
            use_container_width=True,
            help="Save dimensions, AI results, and OpenSCAD code.",
        )

        proj_upload = st.file_uploader(
            "Load project file",
            type=["json"],
            key="project_upload",
            help="Restore a previously saved .vtp.json project.",
        )
        if proj_upload is not None:
            try:
                proj_dict = pm.from_json_bytes(proj_upload.read())
                restored  = pm.apply_to_session(proj_dict, st.session_state)
                st.success(f"Loaded — {len(restored)} fields restored.")
                st.session_state.image_bytes = None
                st.cache_data.clear()
                st.rerun()
            except ValueError as exc:
                st.error(f"Load failed: {exc}")

        # ── Slicer status ──────────────────────────────────────────────────────
        st.divider()
        st.subheader("Slicer Tools")
        status = sl.slicer_status()
        st.markdown(
            f"OpenSCAD: {'✅ found' if status['openscad'] else '❌ not found'}  \n"
            f"Slicer:   {'✅ ' + (status['slicer_type'] or '') if status['can_slice'] else '❌ not found'}"
        )
        if not status["can_compile"]:
            st.warning("Install OpenSCAD to enable .stl compilation.")
        if not status["can_slice"]:
            st.warning("Install PrusaSlicer or CuraEngine to enable G-code generation.")

    # ── Build active_profile (always runs — outside expander) ─────────────────
    _chosen   = st.session_state.get("printer_choice", (sorted(all_profiles.keys()) + ["Custom"])[0])
    _adding   = _chosen == "➕ Add New Printer"
    _prof_raw = all_profiles.get(_chosen, {"bed_x": 235, "bed_y": 235, "bed_z": 250, "notes": ""})

    active_p: dict = {
        "name":  st.session_state.get("new_printer_name", "Custom") if _adding else _chosen,
        "bed_x": int(st.session_state.get("bed_x", _prof_raw.get("bed_x", 235))),
        "bed_y": int(st.session_state.get("bed_y", _prof_raw.get("bed_y", 235))),
        "bed_z": int(st.session_state.get("bed_z", _prof_raw.get("bed_z", 250))),
        "notes": st.session_state.get("bed_notes", _prof_raw.get("notes", "")),
    }
    if not _adding:
        for _k in ("hotend_override", "bed_override"):
            if _k in _prof_raw:
                active_p[_k] = _prof_raw[_k]
    st.session_state.active_profile = active_p


# ══════════════════════════════════════════════════════════════════════════════
# Header
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(
    '<div style="display:flex;align-items:center;gap:8px;margin-bottom:2px">'
    '<span style="font-size:18px;font-weight:800;color:#a8dadc">🖨️ Vibe-to-Print</span>'
    '<span style="font-size:12px;color:#3a5570;margin-top:2px">Snap · Measure · Print</span>'
    '</div>',
    unsafe_allow_html=True,
)

phase = st.session_state.phase

# Getting Started has its own full-width layout — skip badge/progress
if phase == "getting_started":
    gs.render(st.session_state)
    st.stop()

_wizard_header(phase)

# ══════════════════════════════════════════════════════════════════════════════
# PHASE A-1 · THE VISION — Upload & Describe
# ══════════════════════════════════════════════════════════════════════════════

if phase == "vision":
    # ── Camera — always shown first in all modes ──────────────────────────────
    _cam_key = f"cam_{st.session_state.camera_counter}"
    camera_photo = st.camera_input(
        "📸 Snap a photo — tap to add more",
        key=_cam_key,
        label_visibility="visible",
        help="Each photo snapped is added to the gallery below. Tap again to add another.",
    )

    # Auto-add newly snapped photo to captured_images list
    if camera_photo is not None:
        _cam_bytes = camera_photo.getvalue()
        _cam_hash  = hashlib.md5(_cam_bytes).hexdigest()
        if _cam_hash != st.session_state.last_cam_hash:
            n = len(st.session_state.captured_images) + 1
            st.session_state.captured_images.append({
                "bytes":      _cam_bytes,
                "name":       f"photo_{n}.jpg",
                "media_type": "image/jpeg",
            })
            st.session_state.last_cam_hash  = _cam_hash
            st.session_state.camera_counter += 1  # reset widget → blank for next snap
            st.rerun()

    # ── File upload (multiple files supported) ────────────────────────────────
    with st.expander("📁 Upload image files (multiple OK)"):
        uploaded_files = st.file_uploader(
            "Images",
            type=["png", "jpg", "jpeg", "webp", "gif"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
        if uploaded_files:
            existing_hashes = {
                hashlib.md5(ci["bytes"]).hexdigest()
                for ci in st.session_state.captured_images
            }
            added = 0
            for uf in uploaded_files:
                ub = uf.getvalue()
                if hashlib.md5(ub).hexdigest() not in existing_hashes:
                    ext = Path(uf.name).suffix.lstrip(".").lower()
                    st.session_state.captured_images.append({
                        "bytes":      ub,
                        "name":       uf.name,
                        "media_type": {
                            "png": "image/png", "jpg": "image/jpeg",
                            "jpeg": "image/jpeg", "webp": "image/webp",
                        }.get(ext, "image/jpeg"),
                    })
                    existing_hashes.add(hashlib.md5(ub).hexdigest())
                    added += 1
            if added:
                st.rerun()

    # ── Photo gallery — thumbnails with remove buttons ─────────────────────────
    imgs = st.session_state.captured_images
    if imgs:
        st.markdown(
            f'<div style="font-size:13px;color:#52b788;font-weight:600;margin:4px 0">'
            f'📷 {len(imgs)} photo{"s" if len(imgs)>1 else ""} attached'
            f'{"  ·  📌 first = main for AI" if len(imgs)>1 else ""}'
            f'</div>',
            unsafe_allow_html=True,
        )
        # 3-up grid
        n_cols = min(len(imgs), 3)
        thumb_cols = st.columns(n_cols)
        to_remove = None
        for idx, ci in enumerate(imgs):
            with thumb_cols[idx % n_cols]:
                st.image(ci["bytes"], use_container_width=True)
                label = "📌 Main" if idx == 0 else f"#{idx+1}"
                c1, c2 = st.columns([2, 1])
                c1.caption(label)
                if c2.button("✕", key=f"rm_img_{idx}", help="Remove this photo"):
                    to_remove = idx
                if idx > 0 and st.button("↑ Make main", key=f"promote_{idx}",
                                          use_container_width=True):
                    # Move to front
                    st.session_state.captured_images.insert(
                        0, st.session_state.captured_images.pop(idx)
                    )
                    st.rerun()
        if to_remove is not None:
            st.session_state.captured_images.pop(to_remove)
            st.rerun()

        if st.button("🗑 Clear all photos", use_container_width=False):
            st.session_state.captured_images = []
            st.session_state.last_cam_hash   = ""
            st.session_state.camera_counter += 1
            st.rerun()

    st.divider()

    # ── Derive primary image (first in gallery) ───────────────────────────────
    if st.session_state.captured_images:
        _primary = st.session_state.captured_images[0]
        st.session_state.image_bytes      = _primary["bytes"]
        st.session_state.image_name       = _primary["name"]
        st.session_state.image_media_type = _primary["media_type"]

    # ── Describe — always visible in all modes ───────────────────────────────
    vibe = st.text_area(
        "Describe what you want to make",
        value=st.session_state.vibe_description,
        height=90,
        placeholder="e.g. Broken stove knob — D-shaft 6 mm, chunky grip  "
                    "or  Wall bracket for 32mm pipe",
    )
    st.session_state.vibe_description = vibe

    # ── Scale reference + tips (tucked away) ──────────────────────────────────
    with st.expander("📐 Scale reference & tips (optional)"):
        st.markdown(si.tip_card_html(), unsafe_allow_html=True)
        all_ref_labels = si.all_ui_labels()
        default_ref_idx = (all_ref_labels.index("Credit / debit card")
                           if "Credit / debit card" in all_ref_labels else 0)
        ref_label = st.selectbox(
            "Reference object in photo",
            options=all_ref_labels,
            index=default_ref_idx,
            key="ref_label_selector",
        )
        ref_key = si.key_for_label(ref_label)
        st.session_state.ref_obj_key = ref_key
        ref_entry = si.REFERENCE_DB.get(ref_key, {})
        dims_str  = " · ".join(
            f"{k}: **{v} mm**" for k, v in ref_entry.get("dims", {}).items()
        )
        if dims_str:
            st.caption(f"Known size → {dims_str}")

    has_image = bool(st.session_state.image_bytes)
    key_ok    = bool(st.session_state.get("api_key")) or _needs_no_key()

    if _is_manual():
        # ── Identify button ───────────────────────────────────────────────────
        if st.button(
            "🔍 Identify from Photo & Description",
            type="primary",
            disabled=not (has_image or vibe.strip()),
            use_container_width=True,
        ):
            with st.spinner("Analysing photo and description…"):
                _ir = hfi.identify_object(
                    image_bytes = st.session_state.image_bytes if has_image else None,
                    description = vibe,
                    hf_token    = st.session_state.get("api_key", ""),
                )
            # Serialize to plain dict for session state storage
            st.session_state["_identify_result"] = {
                "caption":        _ir.caption,
                "object_type":    _ir.object_type,
                "creation_idea":  _ir.creation_idea,
                "template_match": _ir.template_match,
                "alternatives":   _ir.alternatives,
                "method":         _ir.method,
                "warning":        _ir.warning,
            }
            st.rerun()

        # ── Interactive result card ───────────────────────────────────────────
        _ir_data: dict | None = st.session_state.get("_identify_result")

        if _ir_data:
            _caption  = _ir_data.get("caption", "")
            _idea     = _ir_data.get("creation_idea", "")
            _best_t   = _ir_data.get("template_match") or {}
            _alts     = _ir_data.get("alternatives") or []
            _warning  = _ir_data.get("warning", "")

            if _warning:
                st.warning(_warning, icon="⚠️")

            # ── What we see ───────────────────────────────────────────────────
            if _caption:
                st.markdown(
                    f'<div style="background:#0a1929;border-left:3px solid #3a78c9;'
                    f'border-radius:6px;padding:10px 14px;margin-bottom:10px">'
                    f'<div style="font-size:11px;color:#3a78c9;font-weight:700;'
                    f'letter-spacing:.05em;text-transform:uppercase">📷 Photo shows</div>'
                    f'<div style="color:#e0f0ff;font-size:15px;margin-top:4px">'
                    f'{_caption}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # ── Creation idea ─────────────────────────────────────────────────
            if _idea:
                st.markdown(
                    f'<div style="background:#0a1929;border-left:3px solid #52b788;'
                    f'border-radius:6px;padding:10px 14px;margin-bottom:14px">'
                    f'<div style="font-size:11px;color:#52b788;font-weight:700;'
                    f'letter-spacing:.05em;text-transform:uppercase">💡 What to make</div>'
                    f'<div style="color:#e0f0ff;font-size:15px;margin-top:4px">'
                    f'{_idea}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # ── Best template match ───────────────────────────────────────────
            if _best_t:
                st.markdown(
                    f'<div style="background:#0d2137;border:2px solid #52b788;'
                    f'border-radius:10px;padding:14px 16px;margin-bottom:8px">'
                    f'<div style="font-size:11px;color:#52b788;font-weight:700;'
                    f'letter-spacing:.05em;text-transform:uppercase;margin-bottom:6px">'
                    f'🖨️ Best match</div>'
                    f'<div style="font-weight:700;color:#a8dadc;font-size:17px">'
                    f'{_best_t.get("name","")}</div>'
                    f'<div style="color:#7a9ab8;font-size:12px;margin:3px 0 8px">'
                    f'{_best_t.get("category","")}</div>'
                    f'<div style="color:#cdd8e0;font-size:13px">'
                    f'{_best_t.get("description","")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                if st.button(
                    f"✓ Yes — make a {_best_t.get('name','')} →",
                    type="primary",
                    use_container_width=True,
                    key="confirm_best_match",
                ):
                    _t = tl.get(_best_t["id"])
                    st.session_state.selected_template_id = _best_t["id"]
                    st.session_state.required_dims = [
                        {"id": d["id"], "question": d["question"],
                         "prefill": str(d["default"])}
                        for d in _t["dims"]
                    ]
                    st.session_state.vibe_description = vibe or _best_t["name"]
                    st.session_state.object_summary   = (
                        (f"📷 *{_caption}*\n\n" if _caption else "") +
                        f"**{_best_t['name']}** — {_best_t['description']}"
                    )
                    reset_to("dimensions")
                    st.rerun()

            else:
                st.info(
                    "No template matched yet — try describing it more specifically "
                    "below, or browse templates manually.",
                    icon="🔎",
                )

            # ── Alternatives ──────────────────────────────────────────────────
            if _alts:
                st.markdown(
                    '<div style="font-size:12px;color:#7a9ab8;margin:8px 0 4px">'
                    'Other possibilities:</div>',
                    unsafe_allow_html=True,
                )
                _alt_cols = st.columns(len(_alts))
                for _col, _alt in zip(_alt_cols, _alts):
                    with _col:
                        st.markdown(
                            f'<div style="background:#10202e;border:1px solid #1d3557;'
                            f'border-radius:8px;padding:10px 12px">'
                            f'<div style="font-weight:600;color:#a8dadc;font-size:14px">'
                            f'{_alt.get("name","")}</div>'
                            f'<div style="color:#7a9ab8;font-size:11px;margin-top:3px">'
                            f'{_alt.get("description","")}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        if st.button(
                            "Use this",
                            key=f"use_alt_{_alt['id']}",
                            use_container_width=True,
                        ):
                            _at = tl.get(_alt["id"])
                            st.session_state.selected_template_id = _alt["id"]
                            st.session_state.required_dims = [
                                {"id": d["id"], "question": d["question"],
                                 "prefill": str(d["default"])}
                                for d in _at["dims"]
                            ]
                            st.session_state.vibe_description = vibe or _alt["name"]
                            st.session_state.object_summary   = (
                                f"**{_alt['name']}** — {_alt['description']}"
                            )
                            reset_to("dimensions")
                            st.rerun()

            # ── Refine description ────────────────────────────────────────────
            st.markdown(
                '<div style="font-size:12px;color:#7a9ab8;margin:12px 0 2px">'
                '🔄 Not right? Add more detail and identify again:</div>',
                unsafe_allow_html=True,
            )
            _refine = st.text_input(
                "Refine",
                label_visibility="collapsed",
                placeholder="e.g. it's a D-shaft knob, 30mm diameter, for a stove",
                key="refine_description",
            )
            if _refine.strip():
                st.session_state.vibe_description = _refine
                st.session_state["_identify_result"] = None
                st.rerun()

            st.divider()

        # ── Smarter AI options (collapsed) ────────────────────────────────────
        with st.expander("🤖 Get smarter results — connect an AI"):
            st.markdown("""
**Free Hugging Face token** *(best first step)*
Unlocks better photo reading + richer creation suggestions.
1. Sign up free → [huggingface.co](https://huggingface.co)
2. Create a token → [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
3. Paste it in **⚙️ Advanced Settings → AI Brain**

---

**Local AI — Ollama** *(offline, private, no cost)*
1. Install [Ollama](https://ollama.ai) on your computer or home server
2. `ollama pull llava` (vision model)
3. Select **Local (Ollama)** in ⚙️ Advanced Settings — works over Wi-Fi

---

**Any AI app on your phone**
Share the photo with ChatGPT / Claude / Gemini and ask:
*"What is this? What measurements do I need to 3D print a replacement in mm?"*
Then paste the answer into the description above and tap Identify again.
""")

        # ── Browse templates manually ─────────────────────────────────────────
        with st.expander("📚 Browse all templates manually"):
            search_col, cat_col = st.columns([3, 1], gap="medium")
            with search_col:
                q = st.text_input("Search", placeholder="knob  /  box  /  bracket  …",
                                  key="tl_search_query")
            with cat_col:
                cats = ["All"] + tl.CATEGORIES
                cat  = st.selectbox("Category", cats, key="tl_category")

            matches = tl.search(q, cat if cat != "All" else "")
            if not matches:
                st.warning("No templates match.")
            else:
                st.caption(f"{len(matches)} template{'s' if len(matches) != 1 else ''} found")
                for row_start in range(0, len(matches), 2):
                    c1, c2 = st.columns(2, gap="medium")
                    for col, tmpl in zip((c1, c2), matches[row_start:row_start + 2]):
                        with col:
                            selected = st.session_state.selected_template_id == tmpl["id"]
                            border   = "#52b788" if selected else "#1d3557"
                            bg       = "rgba(45,106,79,0.15)" if selected else "#10202e"
                            st.markdown(
                                f'<div style="background:{bg};border:2px solid {border};'
                                f'border-radius:10px;padding:12px 14px;margin-bottom:4px">'
                                f'<div style="font-weight:700;color:#a8dadc;font-size:16px">'
                                f'{tmpl["name"]}</div>'
                                f'<div style="color:#7a9ab8;font-size:12px;margin:2px 0 6px">'
                                f'{tmpl["category"]}</div>'
                                f'<div style="color:#cdd8e0;font-size:13px">'
                                f'{tmpl["description"]}</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                            btn_lbl = "✓ Selected" if selected else "Use this template"
                            btn_type = "primary" if selected else "secondary"
                            if st.button(btn_lbl, key=f"sel_{tmpl['id']}",
                                         use_container_width=True, type=btn_type):
                                st.session_state.selected_template_id = tmpl["id"]
                                t = tl.get(tmpl["id"])
                                st.session_state.required_dims = [
                                    {"id": d["id"], "question": d["question"],
                                     "prefill": str(d["default"])}
                                    for d in t["dims"]
                                ]
                                st.session_state.vibe_description = vibe or t["name"]
                                st.session_state.object_summary   = t["description"]
                                reset_to("dimensions")
                                st.rerun()

    else:
        # ── AI MODE — Analyse with configured provider ────────────────────────
        if not key_ok:
            st.warning("Add an API key in ⚙️ Advanced Settings → AI Brain.", icon="🔑")

        ds_on = st.session_state.get("ds_enabled", False)

        if ds_on:
            ds_btn = st.button(
                "🔍 Deep Search — Identify & Look Up Specs",
                type="primary",
                disabled=not key_ok or not has_image,
                use_container_width=True,
            )
            if ds_btn:
                if not vibe.strip():
                    st.error("Add a description first.")
                    st.stop()
                img_b64 = base64.standard_b64encode(st.session_state.image_bytes).decode()
                with st.spinner("Identifying and searching for specs…"):
                    try:
                        result = ds.run_deep_search(
                            image_b64       = img_b64,
                            media_type      = st.session_state.image_media_type,
                            description     = vibe,
                            brain           = _get_brain(),
                            gcv_api_key     = st.session_state.get("gcv_api_key", ""),
                            search_provider = st.session_state.get(
                                "ds_search_provider", ds.SEARCH_PROVIDER_AI),
                            search_api_key  = st.session_state.get("ds_search_api_key", ""),
                        )
                    except Exception as exc:
                        st.error(f"Deep Search error: {exc}")
                        st.stop()
                st.session_state.ds_result    = result.as_dict()
                st.session_state.ds_confirmed = False
                st.session_state.vibe_description = vibe
                st.session_state.phase = "deep_review"
                st.rerun()

        if st.button("🔍 Identify & Suggest Measurements",
                     type="primary" if not ds_on else "secondary",
                     disabled=not key_ok,
                     use_container_width=True):
            if not vibe.strip():
                st.error("Please describe the object first.")
                st.stop()
            img_b64  = (base64.standard_b64encode(st.session_state.image_bytes).decode()
                        if has_image else None)
            ref_hint = si.hint_text(st.session_state.get("ref_obj_key", "auto"))
            with st.spinner("AI is examining the object…"):
                try:
                    brain = _get_brain()
                    summary, dims, scale_meta = brain.extract_dimensions(
                        img_b64, st.session_state.image_media_type, vibe,
                        active_p["name"], material, reference_hint=ref_hint,
                    )
                except Exception as exc:
                    st.error(f"AI error: {exc}")
                    st.stop()
            if not dims:
                st.error("AI returned no dimensions. Try rephrasing the description.")
                st.stop()
            st.session_state.object_summary = summary
            st.session_state.required_dims  = dims
            st.session_state.scale_meta     = scale_meta
            reset_to("dimensions")
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PHASE A-1.5 · DEEP REVIEW — Show identification + suggested dims for approval
# ══════════════════════════════════════════════════════════════════════════════

elif phase == "deep_review":
    dsr = st.session_state.get("ds_result") or {}

    # ── Identity card ─────────────────────────────────────────────────────────
    conf_color = {"high": "#2d6a4f", "medium": "#7b5800", "low": "#7b2020"}.get(
        dsr.get("confidence", "low"), "#555"
    )
    conf_emoji = {"high": "✅", "medium": "🟡", "low": "⚠️"}.get(
        dsr.get("confidence", "low"), "❓"
    )

    st.markdown(f"""
<div style="background:#0d1b2a;border-left:5px solid {conf_color};
            border-radius:8px;padding:18px 20px;margin-bottom:16px">
  <div style="font-size:22px;font-weight:700;color:#e0f0ff;margin-bottom:6px">
    {conf_emoji} {dsr.get('identified_label', 'Unknown Object')}
  </div>
  <div style="color:#a8c8e8;font-size:15px">
    Manufacturer: <strong>{dsr.get('manufacturer') or '—'}</strong> &nbsp;|&nbsp;
    Model: <strong>{dsr.get('model_number') or '—'}</strong> &nbsp;|&nbsp;
    Confidence: <strong>{dsr.get('confidence', 'low').title()}</strong>
  </div>
  <div style="margin-top:12px;color:#c8dff0;font-size:16px;font-style:italic">
    {dsr.get('user_message', '')}
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Suggested dimensions table ────────────────────────────────────────────
    suggested = dsr.get("suggested_dims", [])
    if suggested:
        st.subheader("Suggested Dimensions")
        st.caption(
            "These are the factory specs found for this model. "
            "You can accept them all, edit individual values, or start fresh."
        )

        conf_badge = {
            "high":   '<span style="background:#2d6a4f;color:#b7e4c7;'
                      'padding:2px 8px;border-radius:10px;font-size:13px">high</span>',
            "medium": '<span style="background:#7b5800;color:#ffe08a;'
                      'padding:2px 8px;border-radius:10px;font-size:13px">medium</span>',
            "low":    '<span style="background:#7b2020;color:#ffb3b3;'
                      'padding:2px 8px;border-radius:10px;font-size:13px">low</span>',
        }

        # Editable table — one row per dimension
        st.markdown("---")
        edited_dims: list[dict] = []
        for i, dim in enumerate(suggested):
            c_label, c_val, c_unit, c_conf = st.columns([3, 1.5, 1, 1.2])
            c_label.markdown(f"**{dim['label']}**")
            new_val  = c_val.text_input(
                "Value", value=dim["value"],
                key=f"dsval_{i}", label_visibility="collapsed"
            )
            new_unit = c_unit.text_input(
                "Unit", value=dim.get("unit", "mm"),
                key=f"dsunit_{i}", label_visibility="collapsed"
            )
            c_conf.markdown(
                conf_badge.get(dim.get("confidence", "medium"), dim.get("confidence", "")),
                unsafe_allow_html=True,
            )
            if dim.get("source_note"):
                st.caption(f"   ↳ {dim['source_note']}")
            edited_dims.append({
                "id":       dim["id"],
                "question": dim["label"],
                "prefill":  f"{new_val} {new_unit}",
            })

    # ── Sources ───────────────────────────────────────────────────────────────
    sources = dsr.get("search_sources", [])
    if sources:
        with st.expander(f"Sources consulted ({len(sources)})"):
            for url in sources:
                if url:
                    st.markdown(f"- {url}")

    # ── Debug log ─────────────────────────────────────────────────────────────
    if dsr.get("raw_debug"):
        with st.expander("Deep Search debug log"):
            st.code(dsr["raw_debug"])

    # ── Action buttons ────────────────────────────────────────────────────────
    st.markdown("---")
    btn_accept, btn_fresh, btn_back = st.columns(3)

    if btn_accept.button("Use These Dimensions →", type="primary"):
        # Convert suggested dims into the format the dimensions phase expects,
        # pre-answering each one with the (possibly edited) value from above.
        if suggested:
            prefilled_dims   = edited_dims if "edited_dims" in dir() else []
            pre_answers: dict = {}
            for d in prefilled_dims:
                pre_answers[d["id"]] = f"{d['question']} → {d['prefill']}"
            st.session_state.required_dims = prefilled_dims
            st.session_state.dim_answers   = pre_answers
            st.session_state.object_summary = dsr.get("identified_label", "")
            st.session_state.ds_confirmed  = True
            st.session_state.phase = "dimensions"
            st.rerun()
        else:
            st.warning("No dimensions were found. Try 'Start Fresh' instead.")

    if btn_fresh.button("Start Fresh (manual entry)"):
        img_b64 = (
            base64.standard_b64encode(st.session_state.image_bytes).decode()
            if st.session_state.image_bytes else None
        )
        ref_hint = si.hint_text(st.session_state.get("ref_obj_key", "auto"))
        with st.spinner("AI is analysing the object…"):
            try:
                brain = _get_brain()
                summary, dims, scale_meta = brain.extract_dimensions(
                    img_b64,
                    st.session_state.image_media_type,
                    st.session_state.vibe_description,
                    active_p["name"],
                    material,
                    reference_hint=ref_hint,
                )
            except Exception as exc:
                st.error(f"AI error: {exc}")
                st.stop()
        st.session_state.object_summary = summary
        st.session_state.required_dims  = dims
        st.session_state.scale_meta     = scale_meta
        st.session_state.dim_answers    = {}
        st.session_state.phase = "dimensions"
        st.rerun()

    if btn_back.button("← Back"):
        st.session_state.phase = "vision"
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PHASE A-2 · DIMENSIONS — User fills in measurements
# ══════════════════════════════════════════════════════════════════════════════

elif phase == "dimensions":
    ds_confirmed = st.session_state.get("ds_confirmed", False)
    dsr          = st.session_state.get("ds_result") or {}
    dims         = st.session_state.required_dims

    # ── Initialise dim_values / dim_statuses on first entry ───────────────────
    if not st.session_state.dim_values:
        init_vals: dict = {}
        init_stat: dict = {}
        for item in dims:
            qid     = item.get("id", "dim")
            prefill = item.get("prefill", "")
            if not prefill:
                ev   = item.get("estimated_value") or ""
                eu   = item.get("estimated_unit", "mm")
                if ev and str(ev).strip() not in ("null", "None", ""):
                    prefill = f"{ev} {eu}"
            init_vals[qid] = prefill
            # In manual/template mode the prefill is a chosen default — treat as
            # user_entered so the Confirm button is available immediately.
            if prefill:
                init_stat[qid] = "user_entered" if _is_manual() else "suggested"
            else:
                init_stat[qid] = "empty"
        st.session_state.dim_values   = init_vals
        st.session_state.dim_statuses = init_stat

    # ── AI / Template trust card ──────────────────────────────────────────────
    if ds_confirmed and dsr.get("identified_label"):
        st.markdown(f"""
<div style="background:rgba(45,106,79,0.2);border:2px solid #52b788;border-radius:12px;
            padding:14px 18px;margin-bottom:14px">
  <div style="font-size:13px;color:#52b788;font-weight:700;margin-bottom:4px">
    ✅ Deep Search matched
  </div>
  <div style="font-size:18px;font-weight:700;color:#e0f0ff">{dsr['identified_label']}</div>
  <div style="font-size:13px;color:#a8dadc;margin-top:4px">
    Review the factory specs below and adjust any values before generating your model.
  </div>
</div>""", unsafe_allow_html=True)

    elif _is_manual() and st.session_state.object_summary:
        st.markdown(f"""
<div style="background:rgba(58,120,201,0.15);border:2px solid #3a78c9;border-radius:12px;
            padding:14px 18px;margin-bottom:14px">
  <div style="font-size:13px;color:#3a78c9;font-weight:700;margin-bottom:4px">
    🛠️ Template selected
  </div>
  <div style="font-size:17px;font-weight:700;color:#e0f0ff">{st.session_state.vibe_description}</div>
  <div style="font-size:13px;color:#a8dadc;margin-top:4px">
    {st.session_state.object_summary}
  </div>
</div>""", unsafe_allow_html=True)

    elif st.session_state.object_summary:
        st.markdown(f"""
<div style="background:rgba(123,45,139,0.18);border:2px solid #9b59b6;border-radius:12px;
            padding:14px 18px;margin-bottom:14px">
  <div style="font-size:13px;color:#c77dff;font-weight:700;margin-bottom:4px">
    🤖 AI understood your vibe
  </div>
  <div style="font-size:17px;font-weight:700;color:#e0f0ff">{st.session_state.vibe_description or 'Your object'}</div>
  <div style="font-size:14px;color:#d4b8f0;margin-top:6px;font-style:italic">
    "{st.session_state.object_summary}"
  </div>
  <div style="font-size:12px;color:#8a6aaa;margin-top:6px">
    Verify or adjust the dimensions below, then click Confirm to generate your 3D model.
  </div>
</div>""", unsafe_allow_html=True)

    scale_meta = st.session_state.get("scale_meta") or {}
    method     = scale_meta.get("scaling_method", "unknown")
    if method not in ("unknown", "user_provided", ""):
        mc = {"reference_object":"#2d6a4f","ruler":"#2d6a4f","estimated":"#7b5800"}.get(method,"#555")
        mi = {"reference_object":"📐","ruler":"📏","estimated":"🔮"}.get(method,"ℹ️")
        ref_line = f"Reference: **{scale_meta.get('reference_detected','')}**  " if scale_meta.get("reference_detected") else ""
        st.markdown(f'<div style="background:#0d1b2a;border-left:5px solid {mc};border-radius:8px;'
                    f'padding:10px 14px;margin-bottom:12px">'
                    f'{mi} <strong style="color:#e0f0ff">Scale: {method.replace("_"," ").title()}</strong>'
                    f'<br><span style="color:#a8c8e8;font-size:14px">{ref_line}'
                    f'{scale_meta.get("scale_note","")}</span></div>', unsafe_allow_html=True)

    # ── Caliper guide expander ─────────────────────────────────────────────────
    with st.expander("📐 How to measure with calipers — tap to open diagram guide"):
        st.markdown(cg.full_guide_html(), unsafe_allow_html=True)

    st.divider()

    # ── Smart Suggestions legend ──────────────────────────────────────────────
    if _is_manual():
        st.info(
            "Template defaults are pre-filled below. Measure your part and update "
            "each value, then click **Confirm Dimensions & Generate OpenSCAD**.",
            icon="📐",
        )
    else:
        st.markdown("""
<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:10px;font-size:13px">
  <span><span style="display:inline-block;width:12px;height:12px;border-radius:3px;
    background:rgba(58,120,201,0.4);border:2px solid #4a9eff;margin-right:4px"></span>
    <strong style="color:#4a9eff">Blue</strong> = AI Suggestion (needs confirmation)</span>
  <span><span style="display:inline-block;width:12px;height:12px;border-radius:3px;
    background:rgba(45,106,79,0.4);border:2px solid #52b788;margin-right:4px"></span>
    <strong style="color:#52b788">Green</strong> = Verified</span>
  <span><span style="display:inline-block;width:12px;height:12px;border-radius:3px;
    background:rgba(180,180,180,0.15);border:2px solid #8899aa;margin-right:4px"></span>
    <strong style="color:#aabbcc">Grey</strong> = Manually entered</span>
</div>""", unsafe_allow_html=True)

    # ── Per-dimension rows ────────────────────────────────────────────────────
    statuses  = st.session_state.dim_statuses
    values    = st.session_state.dim_values
    any_empty = False

    _STATUS_BORDER = {
        "suggested":    "#4a9eff",
        "verified":     "#52b788",
        "user_entered": "#8899aa",
        "empty":        "#e94560",
    }
    _STATUS_BG = {
        "suggested":    "rgba(58,120,201,0.15)",
        "verified":     "rgba(45,106,79,0.20)",
        "user_entered": "rgba(180,180,180,0.08)",
        "empty":        "rgba(233,69,96,0.10)",
    }
    _STATUS_LABEL = {
        "suggested":    "AI Suggestion",
        "verified":     "Verified ✓",
        "user_entered": "Manually entered",
        "empty":        "Not filled",
    }

    for item in dims:
        qid       = item.get("id", "dim")
        question  = item.get("question", "")
        est_conf  = str(item.get("estimation_confidence", "")).lower()
        est_src   = item.get("estimation_source", "")
        status    = statuses.get(qid, "empty")
        cur_val   = values.get(qid, "")

        border = _STATUS_BORDER.get(status, "#555")
        bg     = _STATUS_BG.get(status, "transparent")
        slabel = _STATUS_LABEL.get(status, status)

        # Container card for this dimension
        st.markdown(f"""
<div style="border:2px solid {border};background:{bg};
            border-radius:10px;padding:12px 14px;margin-bottom:10px">""",
            unsafe_allow_html=True)

        # Two-column layout: [input column] [suggestion sidebar]
        col_input, col_suggest = st.columns([3, 2], gap="medium")

        with col_input:
            # Status chip
            st.markdown(
                f'<span style="font-size:12px;color:{border};font-weight:700">'
                f'{slabel}</span>',
                unsafe_allow_html=True,
            )
            new_val = st.text_input(
                question,
                value=cur_val,
                key=f"dq_{qid}",
                placeholder="e.g. 12.5 mm",
            )
            # Detect if user changed the value
            if new_val != cur_val:
                st.session_state.dim_values[qid]   = new_val
                st.session_state.dim_statuses[qid] = (
                    "user_entered" if new_val.strip() else "empty"
                )
                statuses[qid] = st.session_state.dim_statuses[qid]

        with col_suggest:
            # Smart Suggestion box (AI mode only)
            has_estimate = (not _is_manual()) and bool(cur_val) and status in ("suggested", "verified")
            if has_estimate or (est_src and not _is_manual()):
                conf_color = {"high":"#52b788","medium":"#ffd700","low":"#e94560",
                              "estimated (high)":"#52b788","estimated (medium)":"#ffd700",
                              "estimated (low)":"#e94560"}.get(est_conf,"#aabbcc")
                st.markdown(f"""
<div style="background:#0d1b2a;border-radius:8px;padding:8px 10px;
            border-left:3px solid {conf_color}">
  <div style="color:#a8dadc;font-size:12px;font-weight:700;margin-bottom:3px">
    AI Suggests
  </div>
  <div style="color:#e0f0ff;font-size:16px;font-weight:700">{cur_val or '—'}</div>
  <div style="color:#7a9ab8;font-size:11px;margin-top:3px">
    Confidence: <span style="color:{conf_color}">{est_conf or 'n/a'}</span>
  </div>
  {"<div style='color:#6a8aa8;font-size:11px;margin-top:2px;font-style:italic'>" + est_src + "</div>" if est_src else ""}
</div>""", unsafe_allow_html=True)

            # Accept / Clear buttons
            b1, b2 = st.columns(2)
            if b1.button("✓ Accept", key=f"acc_{qid}",
                         help="Mark this value as verified"):
                if st.session_state.dim_values.get(qid, "").strip():
                    st.session_state.dim_statuses[qid] = "verified"
                    st.rerun()
                else:
                    st.warning("Enter a value first.")
            if b2.button("✗ Clear", key=f"clr_{qid}",
                         help="Clear and re-enter manually"):
                st.session_state.dim_values[qid]   = ""
                st.session_state.dim_statuses[qid] = "empty"
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        if not st.session_state.dim_values.get(qid, "").strip():
            any_empty = True

    # ── Accept All shortcut (AI mode only) ───────────────────────────────────
    st.divider()
    accept_all_col, _ = st.columns([1, 2])
    if not _is_manual() and accept_all_col.button(
            "✓ Accept All AI Suggestions", use_container_width=True,
            help="Mark every pre-filled value as verified at once"):
        for item in dims:
            qid = item.get("id", "dim")
            if st.session_state.dim_values.get(qid, "").strip():
                st.session_state.dim_statuses[qid] = "verified"
        st.rerun()

    # ── Confirmation progress & button ────────────────────────────────────────
    n_total    = len(dims)
    n_ready    = sum(1 for item in dims
                     if st.session_state.dim_statuses.get(item.get("id",""), "empty")
                     in ("verified", "user_entered")
                     and st.session_state.dim_values.get(item.get("id",""), "").strip())
    all_ready  = (n_ready == n_total) and n_total > 0

    st.markdown(f"""
<div style="background:#0d1b2a;border-radius:8px;padding:10px 16px;
            margin:10px 0;display:flex;align-items:center;gap:12px">
  <div style="flex:1">
    <div style="color:#a8dadc;font-weight:700;font-size:14px">
      Confirmation progress
    </div>
    <div style="background:#1d3557;border-radius:4px;height:8px;margin-top:6px">
      <div style="background:{'#52b788' if all_ready else '#3a78c9'};
                  border-radius:4px;height:8px;
                  width:{int(n_ready/max(n_total,1)*100)}%"></div>
    </div>
  </div>
  <div style="color:#e0f0ff;font-size:20px;font-weight:700;white-space:nowrap">
    {n_ready}/{n_total}
  </div>
</div>""", unsafe_allow_html=True)

    conf_col, back_col = st.columns([2, 1])

    if conf_col.button(
        "Confirm Dimensions & Generate OpenSCAD →",
        type="primary",
        disabled=not all_ready,
        use_container_width=True,
        help="All dimensions must be verified or manually entered before generating.",
    ):
        # Compile dim_answers from confirmed values
        compiled: dict = {}
        for item in dims:
            qid = item.get("id", "dim")
            q   = item.get("question", "")
            v   = st.session_state.dim_values.get(qid, "")
            compiled[qid] = f"{q} → {v}"
        st.session_state.dim_answers  = compiled
        st.session_state.dims_confirmed = True
        reset_to("cad")
        st.rerun()

    if back_col.button(
        "← Back to Deep Search" if ds_confirmed else "← Back",
        use_container_width=True,
    ):
        st.session_state.phase = "deep_review" if ds_confirmed else "vision"
        st.rerun()

    # ── Live SCAD preview (template mode — instant, no API call) ─────────────
    if _is_manual():
        _tmpl_live = tl.get(st.session_state.get("selected_template_id"))
        if _tmpl_live:
            _cx, _cy = pp.bed_center(_active_profile())
            _live_code = tl.generate_scad(
                _tmpl_live, st.session_state.dim_values, _cx, _cy
            )
            with st.expander("📄 Live OpenSCAD Preview (updates as you type)", expanded=False):
                st.code(_live_code, language="openscad")
                st.caption(
                    "This is exactly the code that will be used when you click "
                    "**Confirm Dimensions & Generate OpenSCAD**."
                )

    # ── Ask AI to update estimates (AI mode only) ─────────────────────────────
    if not _is_manual():
        st.divider()
        with st.expander("🤖 Something changed? Ask the AI to update estimates"):
            st.caption(
                "Describe what changed — a different size, a new feature, a correction. "
                "The AI will revise only the affected dimensions and preserve the rest."
            )
            change_req = st.text_area(
                "What changed?",
                height=90,
                placeholder="e.g. The shaft is actually 8 mm, not 6 mm. "
                            "Also add a recess for an M3 nut on the back.",
                key="change_request_text",
            )
            key_ok2 = bool(st.session_state.get("api_key")) or _needs_no_key()

            if st.button("Re-ask AI for updated estimates", disabled=not key_ok2,
                         use_container_width=True):
                if not change_req.strip():
                    st.warning("Describe the change first.")
                    st.stop()
                img_b64 = (
                    base64.standard_b64encode(st.session_state.image_bytes).decode()
                    if st.session_state.image_bytes else None
                )
                with st.spinner("AI is updating estimates…"):
                    try:
                        brain = _get_brain()
                        _, new_dims, new_meta = brain.refine_dimensions(
                            original_dims   = dims,
                            current_values  = st.session_state.dim_values,
                            change_request  = change_req,
                            image_b64       = img_b64,
                            media_type      = st.session_state.image_media_type,
                        )
                    except Exception as exc:
                        st.error(f"AI error: {exc}")
                        st.stop()

                for nd in new_dims:
                    nid      = nd.get("id", "")
                    new_est  = nd.get("estimated_value", "")
                    new_unit = nd.get("estimated_unit", "mm")
                    old_val  = st.session_state.dim_values.get(nid, "")
                    new_val  = (f"{new_est} {new_unit}"
                                if new_est and str(new_est) not in ("null", "None", "")
                                else old_val)
                    if new_val != old_val:
                        st.session_state.dim_values[nid]   = new_val
                        st.session_state.dim_statuses[nid] = "suggested"
                existing_ids = {d.get("id") for d in st.session_state.required_dims}
                for nd in new_dims:
                    if nd.get("id") not in existing_ids:
                        st.session_state.required_dims.append(nd)
                        st.session_state.dim_values[nd.get("id", "")] = ""
                        st.session_state.dim_statuses[nd.get("id", "")] = "empty"
                st.session_state.scale_meta = new_meta
                st.success("Estimates updated. Review the changes above.")
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PHASE B · CAD — Generate & display OpenSCAD
# ══════════════════════════════════════════════════════════════════════════════

elif phase == "cad":
    st.subheader("Step 3 · Your 3D Design")

    profile  = _active_profile()
    centering = pp.centering_instruction(profile)

    if not st.session_state.openscad_code:
        if _is_manual():
            # Template mode — instant deterministic generation, no AI call
            tmpl_id = st.session_state.get("selected_template_id")
            tmpl    = tl.get(tmpl_id) if tmpl_id else None
            if tmpl is None:
                st.error("No template selected. Go back and choose a template.")
                if st.button("← Back to Templates"):
                    reset_to("vision")
                    st.rerun()
                st.stop()
            cx, cy = pp.bed_center(profile)
            code   = tl.generate_scad(
                tmpl,
                st.session_state.dim_values,
                cx, cy,
            )
            notes  = (
                f"Generated from template: **{tmpl['name']}** ({tmpl['category']})\n\n"
                f"{tmpl['description']}"
            )
        else:
            with st.spinner("Master Mechanical Modeler is designing your part…"):
                try:
                    brain = _get_brain()
                    code, notes = brain.generate_openscad(
                        st.session_state.vibe_description,
                        st.session_state.dim_answers,
                        profile,
                        material,
                        MATERIAL_TEMPS,
                        centering,
                    )
                except Exception as exc:
                    st.error(f"AI error: {exc}")
                    st.stop()

        # Store fingerprint so we can detect if dims change later
        _fp = hashlib.md5(str(st.session_state.dim_values).encode()).hexdigest()[:10]
        st.session_state.scad_dims_fp   = _fp
        st.session_state.openscad_code  = code
        st.session_state.openscad_notes = notes

    code  = st.session_state.openscad_code
    notes = st.session_state.openscad_notes

    # ── Stale-dims banner ─────────────────────────────────────────────────────
    _current_fp = hashlib.md5(str(st.session_state.dim_values).encode()).hexdigest()[:10]
    _stored_fp  = st.session_state.get("scad_dims_fp", "")
    _dims_stale = bool(_stored_fp and _current_fp != _stored_fp)
    if _dims_stale:
        st.warning(
            "Your measurements changed since this code was generated. "
            "Click **↺ Regenerate** to update the design.",
            icon="🔄",
        )
    else:
        st.success("OpenSCAD code generated!")

    col_dl, col_slice, col_regen, col_back = st.columns(4)

    col_dl.download_button(
        "⬇ Download .scad",
        data=code,
        file_name="vibe_model.scad",
        mime="text/plain",
    )

    if col_slice.button("Compile & Slice →", type="primary"):
        reset_to("slicer")
        st.rerun()

    if col_regen.button("↺ Regenerate", type="primary" if _dims_stale else "secondary"):
        st.session_state.openscad_code = ""
        st.session_state.scad_dims_fp  = ""
        st.rerun()

    if col_back.button("← Back"):
        reset_to("dimensions")
        st.rerun()

    st.divider()

    # ── Code view + browser preview ───────────────────────────────────────────
    with st.expander("📄 View OpenSCAD Code", expanded=False):
        st.code(code, language="openscad")

    if notes:
        with st.expander("🧠 Design decisions", expanded=False):
            st.markdown(notes)

    # ── Zero-install preview option ────────────────────────────────────────────
    status_cad = sl.slicer_status()
    if not status_cad["can_compile"]:
        st.info(
            "**OpenSCAD not installed locally** — you can still preview and compile "
            "your model in the browser for free.",
            icon="🌐",
        )
    with st.expander("🌐 Preview in Browser (No Install Required)", expanded=not status_cad["can_compile"]):
        st.markdown("""
**Option A — openscad.cloud** (recommended)
1. Click **"⬇ Download .scad"** above to save the file
2. Open **[openscad.cloud](https://openscad.cloud)** in a new tab
3. Click **Open** → select your `.scad` file → click ▶ **Render**
4. Export the resulting STL and come back here to slice it

**Option B — OpenSCAD Web (official)**
1. Download the `.scad` file above
2. Open **[ochafik.com/openscad2](https://ochafik.com/openscad2/)** in a new tab
3. Open your file and render

Once you have an STL file, use the upload option in the Slicer step, or slice it
online with **[kiri.moto](https://kiri.moto)**.
""")
        st.caption("These free browser tools compile OpenSCAD to STL without installing anything.")

# ══════════════════════════════════════════════════════════════════════════════
# PHASE C · SLICER — Compile .scad → .stl → .gcode
# ══════════════════════════════════════════════════════════════════════════════

elif phase == "slicer":
    st.subheader("Step 4 · Compile & Slice")
    profile = _active_profile()
    status  = sl.slicer_status()

    # ── Step 1: .scad → .stl ─────────────────────────────────────────────────
    if st.session_state.stl_path is None:
        if not status["can_compile"]:
            # No local OpenSCAD — show browser alternative prominently
            st.warning("OpenSCAD is not installed on this machine.", icon="⚠️")
            st.markdown("""
<div style="background:#1d3557;border-radius:10px;padding:16px 18px;margin:8px 0">
<div style="font-size:16px;font-weight:700;color:#a8dadc;margin-bottom:8px">
🌐 Compile in your browser — free, no install needed
</div>
<ol style="color:#cdd8e0;font-size:15px;margin:0;padding-left:20px;line-height:2">
  <li>Go back to Step 3 and click <strong>⬇ Download .scad</strong></li>
  <li>Open <a href="https://openscad.cloud" target="_blank" style="color:#4a9eff">openscad.cloud</a>
      in a new tab</li>
  <li>Click <strong>Open</strong>, select your file, then click ▶ <strong>Render</strong></li>
  <li>Export the STL — then come back and upload it below</li>
</ol>
</div>""", unsafe_allow_html=True)
            st.divider()
            st.markdown("**Or upload a pre-compiled STL:**")
            ext_stl = st.file_uploader("Upload STL file", type=["stl"], key="ext_stl_upload")
            if ext_stl:
                stl_dest = _work_dir() / "uploaded_model.stl"
                stl_dest.write_bytes(ext_stl.getvalue())
                st.session_state.stl_path = str(stl_dest)
                st.success("STL loaded — ready to slice!")
                st.rerun()
            if st.button("← Back to Design"):
                reset_to("cad")
                st.rerun()
            st.stop()

        with st.spinner("OpenSCAD is compiling your model to STL…"):
            ok, log, stl_p = sl.compile_to_stl(
                st.session_state.openscad_code,
                output_dir=_work_dir(),
            )
        st.session_state.slicer_log += f"=== OpenSCAD ===\n{log}\n\n"

        if not ok:
            st.error("OpenSCAD compilation failed.")
            with st.expander("Compiler log"):
                st.code(log)
            if st.button("← Back to Design"):
                reset_to("cad")
                st.rerun()
            st.stop()

        st.session_state.stl_path = str(stl_p)

    stl_path = Path(st.session_state.stl_path)

    # ── 3D Preview ─────────────────────────────────────────────────────────────
    st.success("✅ 3D model ready!")
    with st.expander("🎯 3D Preview — rotate · zoom · pan", expanded=True):
        try:
            stl_bytes_preview = stl_path.read_bytes()
            components.html(v3d.stl_viewer_html(stl_bytes_preview), height=400, scrolling=False)
        except Exception as _ve:
            st.caption(f"Preview unavailable: {_ve}")

    col_stl_dl, col_back_cad = st.columns(2)
    col_stl_dl.download_button(
        "⬇ Download STL",
        data=stl_path.read_bytes(),
        file_name=stl_path.name,
        mime="application/octet-stream",
        use_container_width=True,
    )
    if col_back_cad.button("← Back to Design", use_container_width=True):
        reset_to("cad")
        st.rerun()

    st.divider()

    # ── Step 2: .stl → .gcode ────────────────────────────────────────────────
    import basic_slicer as bs

    if st.session_state.gcode_path is None:
        if status["can_slice"]:
            # ── Local PrusaSlicer / CuraEngine ────────────────────────────────
            with st.spinner(f"Slicing with {status['slicer_type']}…"):
                ok, log, gcode_p = sl.slice_stl(
                    stl_path, profile, material, MATERIAL_TEMPS, _work_dir()
                )
            st.session_state.slicer_log += f"=== {status['slicer_type']} ===\n{log}\n\n"

            if not ok:
                st.error("Slicing failed.")
                with st.expander("Slicer log"):
                    st.code(log)
                st.download_button(
                    "⬇ Download STL (slice manually)",
                    data=stl_path.read_bytes(),
                    file_name=stl_path.name,
                    mime="application/octet-stream",
                )
            else:
                sl.prepend_start_gcode(gcode_p, profile, material, MATERIAL_TEMPS)
                st.session_state.gcode_path = str(gcode_p)
                st.success("✅ G-code ready!")

        elif bs.available():
            # ── Built-in Python slicer (zero install) ─────────────────────────
            st.info(
                "No local slicer found — using the **built-in Python slicer** "
                "(perimeters + rectilinear infill). "
                "Install PrusaSlicer for production-quality G-code.",
                icon="🐍",
            )
            with st.spinner("Slicing with built-in Python slicer…"):
                ok, log, gcode_p = bs.slice_stl(
                    stl_path, profile, material, MATERIAL_TEMPS, _work_dir()
                )
            st.session_state.slicer_log += f"=== Built-in Slicer ===\n{log}\n\n"

            if not ok:
                st.error(f"Built-in slicer failed: {log}")
            else:
                st.session_state.gcode_path = str(gcode_p)
                st.success("✅ G-code ready! (built-in slicer)")

        else:
            # ── Fallback: manual browser workflow ─────────────────────────────
            st.warning("No slicer available. Install numpy-stl and shapely, "
                       "or use an external slicer.", icon="⚠️")
            st.markdown("""
Download your STL above, then slice it online at
**[kiri.moto](https://kiri.moto)** or **[PrusaSlicer Web](https://slicer.prusa3d.com)**.
""")
            st.caption("Install PrusaSlicer locally for fully automatic in-app slicing.")

    if st.session_state.gcode_path:
        gcode_path = Path(st.session_state.gcode_path)

        col_dl, col_next, _ = st.columns(3)
        col_dl.download_button(
            "⬇ Download G-code",
            data=gcode_path.read_bytes(),
            file_name=gcode_path.name,
            mime="text/plain",
            use_container_width=True,
        )
        if col_next.button("Send to Printer →", type="primary", use_container_width=True):
            st.session_state.phase = "export"
            st.rerun()

        if st.session_state.slicer_log:
            with st.expander("Full slicer log"):
                st.code(st.session_state.slicer_log)

# ══════════════════════════════════════════════════════════════════════════════
# PHASE X · EXPORT — All transfer methods
# ══════════════════════════════════════════════════════════════════════════════

elif phase == "export":
    st.subheader("Export & Send")

    gcode_path = (
        Path(st.session_state.gcode_path)
        if st.session_state.gcode_path else None
    )
    stl_path = (
        Path(st.session_state.stl_path)
        if st.session_state.stl_path else None
    )

    # ── Quick downloads ───────────────────────────────────────────────────────
    st.markdown("#### Quick Download")
    dl1, dl2, dl3 = st.columns(3)

    if gcode_path and gcode_path.exists():
        dl1.download_button(
            "⬇  Download G-code",
            data=gcode_path.read_bytes(),
            file_name=gcode_path.name,
            mime="text/plain",
        )
    if stl_path and stl_path.exists():
        dl2.download_button(
            "⬇  Download STL",
            data=stl_path.read_bytes(),
            file_name=stl_path.name,
            mime="application/octet-stream",
        )
    if dl3.button("💾  Copy to Downloads folder"):
        if gcode_path and gcode_path.exists():
            ok, msg = tr.copy_to_downloads(gcode_path)
            (st.success if ok else st.error)(msg)
        else:
            st.warning("No G-code file available yet.")

    st.divider()

    # ── Transfer tabs ─────────────────────────────────────────────────────────
    tab_email, tab_octo, tab_moon = st.tabs([
        "📧  Email Transfer",
        "🐙  OctoPrint",
        "🌙  Moonraker / Klipper",
    ])

    # ── Email ─────────────────────────────────────────────────────────────────
    with tab_email:
        st.markdown("Send the G-code as an email attachment.")
        smtp_host = st.text_input("SMTP host", value="smtp.gmail.com",
                                   placeholder="smtp.gmail.com")
        smtp_port = st.number_input("SMTP port", min_value=1, max_value=65535,
                                     value=465, step=1)
        smtp_user = st.text_input("Your email address",
                                   placeholder="you@gmail.com")
        smtp_pass = st.text_input("Password / App Password", type="password")
        to_addr   = st.text_input("Send to", placeholder="recipient@example.com")

        st.caption(
            "Gmail users: generate an **App Password** at "
            "myaccount.google.com → Security → App passwords. "
            "Do NOT use your regular password."
        )

        if st.button("Send Email", type="primary"):
            if not gcode_path or not gcode_path.exists():
                st.error("No G-code file to send. Complete the Slicer phase first.")
            elif not all([smtp_host, smtp_user, smtp_pass, to_addr]):
                st.error("Fill in all email fields.")
            else:
                with st.spinner("Sending…"):
                    ok, msg = tr.send_email(
                        smtp_host, int(smtp_port),
                        smtp_user, smtp_pass, to_addr, gcode_path,
                    )
                (st.success if ok else st.error)(msg)

    # ── OctoPrint ─────────────────────────────────────────────────────────────
    with tab_octo:
        st.markdown("Upload directly to your OctoPrint instance.")
        octo_ip  = st.text_input("OctoPrint IP / hostname",
                                  placeholder="192.168.1.100 or octopi.local")
        octo_key = st.text_input("OctoPrint API Key", type="password",
                                  help="Settings → API → API Key")
        octo_print_now = st.checkbox("Start printing immediately after upload")

        if st.button("Upload to OctoPrint", type="primary"):
            if not gcode_path or not gcode_path.exists():
                st.error("No G-code file. Complete the Slicer phase first.")
            elif not octo_ip or not octo_key:
                st.error("Enter the OctoPrint IP and API key.")
            else:
                with st.spinner("Uploading to OctoPrint…"):
                    ok, msg = tr.send_to_octoprint(
                        octo_ip, octo_key, gcode_path, octo_print_now
                    )
                (st.success if ok else st.error)(msg)

    # ── Moonraker ─────────────────────────────────────────────────────────────
    with tab_moon:
        st.markdown("Upload directly to Moonraker (Mainsail / Fluidd / Klipper).")
        moon_ip        = st.text_input("Moonraker IP / hostname",
                                        placeholder="192.168.1.101 or mainsail.local")
        moon_print_now = st.checkbox("Start printing immediately after upload",
                                      key="moon_print_now")

        st.caption("Moonraker does not require an API key by default.")

        if st.button("Upload to Moonraker", type="primary"):
            if not gcode_path or not gcode_path.exists():
                st.error("No G-code file. Complete the Slicer phase first.")
            elif not moon_ip:
                st.error("Enter the Moonraker IP address.")
            else:
                with st.spinner("Uploading to Moonraker…"):
                    ok, msg = tr.send_to_moonraker(
                        moon_ip, gcode_path, moon_print_now
                    )
                (st.success if ok else st.error)(msg)

    st.divider()

    # ── Navigation ────────────────────────────────────────────────────────────
    col_back, col_restart = st.columns(2)
    if col_back.button("← Back to Slicer"):
        st.session_state.phase = "slicer"
        st.rerun()
    if col_restart.button("↺  Start a New Object", type="primary"):
        reset_to("vision")
        st.rerun()
