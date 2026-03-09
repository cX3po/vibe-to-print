"""
getting_started.py
------------------
All content and logic for the "Getting Started" guide tab.

Public API
----------
render(ss)                      – render the full guide into the current Streamlit page
test_key(provider, key) -> (ok, message, detail)
                                – validate an API key with a minimal live call
"""

from __future__ import annotations

import streamlit as st

# ── Color / style tokens (match app theme) ───────────────────────────────────
_BG       = "#0d1b2a"
_CARD_BG  = "#10202e"
_ACCENT   = "#a8dadc"
_WARN     = "#ffd700"
_OK       = "#52b788"
_ERR      = "#e94560"
_TEXT     = "#e0f0ff"
_MUTED    = "#7a9ab8"


# ═══════════════════════════════════════════════════════════════════════════════
# Key validation (tiny live test call)
# ═══════════════════════════════════════════════════════════════════════════════

def test_key(provider: str, api_key: str,
             ollama_url: str = "http://localhost:11434") -> tuple[bool, str, str]:
    """
    Send the smallest possible message to the chosen provider.
    Returns (ok: bool, short_message: str, detail: str).
    detail is shown in an expander for technical users.
    """
    if provider == "Claude (Anthropic)":
        return _test_claude(api_key)
    elif provider == "GPT-4o (OpenAI)":
        return _test_openai(api_key)
    elif provider == "Local (Ollama)":
        return _test_ollama(ollama_url)
    elif provider == "Free / Open Source (Hugging Face)":
        return _test_hf(api_key)
    return False, "Unknown provider.", ""


def _test_claude(api_key: str) -> tuple[bool, str, str]:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp   = client.messages.create(
            model      = "claude-haiku-4-5-20251001",   # cheapest, fastest model
            max_tokens = 5,
            messages   = [{"role": "user", "content": "Hi"}],
        )
        reply = resp.content[0].text if resp.content else "(empty)"
        return True, "API key is valid! Claude responded successfully.", f"Reply: {reply!r}"

    except Exception as exc:
        return _classify_anthropic_error(exc)


def _classify_anthropic_error(exc: Exception) -> tuple[bool, str, str]:
    """Turn an anthropic exception into a friendly user message."""
    try:
        import anthropic as _a

        if isinstance(exc, _a.AuthenticationError):
            return (False,
                    "Invalid API key — check for typos and ensure you copied it fully.",
                    f"HTTP 401: {exc}")

        if isinstance(exc, _a.PermissionDeniedError):
            msg = str(exc).lower()
            if any(w in msg for w in ("billing", "credit", "payment", "balance")):
                return (False,
                        "Billing not set up — add a payment method at "
                        "console.anthropic.com/billing then try again.",
                        f"HTTP 403: {exc}")
            return (False,
                    "Access denied — your account may lack permissions for this model.",
                    f"HTTP 403: {exc}")

        if isinstance(exc, _a.RateLimitError):
            return (True,       # key IS valid — just rate-limited
                    "Key is valid but you've hit your rate limit. "
                    "Wait a moment and try again.",
                    f"HTTP 429: {exc}")

        if isinstance(exc, _a.BadRequestError):
            return (False,
                    f"Bad request: {exc}",
                    str(exc))

    except ImportError:
        pass

    msg = str(exc).lower()
    if "billing" in msg or "credit" in msg or "payment" in msg:
        return (False,
                "Billing not set up — add a payment method at "
                "console.anthropic.com/billing.",
                str(exc))
    if "timeout" in msg or "connect" in msg:
        return (False,
                "Could not reach the Anthropic API. Check your internet connection.",
                str(exc))
    return (False, f"Unexpected error: {exc}", str(exc))


def _test_openai(api_key: str) -> tuple[bool, str, str]:
    try:
        from openai import OpenAI, AuthenticationError, PermissionDeniedError, RateLimitError
        client = OpenAI(api_key=api_key)
        resp   = client.chat.completions.create(
            model      = "gpt-4o-mini",    # cheapest model for testing
            max_tokens = 5,
            messages   = [{"role": "user", "content": "Hi"}],
        )
        reply = resp.choices[0].message.content or "(empty)"
        return True, "API key is valid! GPT-4o Mini responded successfully.", f"Reply: {reply!r}"

    except Exception as exc:
        cls = type(exc).__name__

        if "AuthenticationError" in cls:
            return (False,
                    "Invalid OpenAI API key — check for typos.",
                    str(exc))
        if "PermissionDeniedError" in cls:
            msg = str(exc).lower()
            if any(w in msg for w in ("billing", "credit", "payment", "quota")):
                return (False,
                        "OpenAI billing not set up or quota exceeded. "
                        "Add a payment method at platform.openai.com/billing.",
                        str(exc))
            return (False,
                    "Access denied — check your OpenAI account status.",
                    str(exc))
        if "RateLimitError" in cls:
            return (True,
                    "Key is valid but you've hit your OpenAI rate limit. "
                    "Wait a moment and try again.",
                    str(exc))

        msg = str(exc).lower()
        if "timeout" in msg or "connect" in msg:
            return (False,
                    "Could not reach the OpenAI API. Check your internet connection.",
                    str(exc))
        return (False, f"Unexpected error: {exc}", str(exc))


def _test_ollama(base_url: str) -> tuple[bool, str, str]:
    import requests
    url = base_url.rstrip("/") + "/api/tags"
    try:
        resp = requests.get(url, timeout=6)
        resp.raise_for_status()
        data   = resp.json()
        models = [m.get("name", "") for m in data.get("models", [])]
        if models:
            return (True,
                    f"Ollama is running! Found {len(models)} model(s): "
                    + ", ".join(models[:5]),
                    str(data))
        return (True,
                "Ollama is running but no models are pulled yet. "
                "Run: `ollama pull llava && ollama pull llama3`",
                str(data))
    except requests.ConnectionError:
        return (False,
                "Cannot reach Ollama at " + base_url + ". "
                "Make sure `ollama serve` is running.",
                "ConnectionError")
    except Exception as exc:
        return (False, f"Ollama error: {exc}", str(exc))


def _test_hf(token: str) -> tuple[bool, str, str]:
    """Test a Hugging Face token (or anonymous access) with a tiny inference call."""
    try:
        from huggingface_hub import InferenceClient
    except ImportError:
        return (False,
                "huggingface_hub is not installed. Run: pip install huggingface_hub",
                "ImportError")

    try:
        client = InferenceClient(token=token or None)
        resp   = client.chat_completion(
            model    = "mistralai/Mistral-7B-Instruct-v0.3",
            messages = [{"role": "user", "content": "Reply with just the word: OK"}],
            max_tokens = 5,
        )
        reply = (resp.choices[0].message.content or "").strip()
        if token:
            return (True,
                    "HF token is valid! Mistral responded successfully.",
                    f"Reply: {reply!r}")
        else:
            return (True,
                    "Anonymous HF access works! (Limited rate — add a token for more.)",
                    f"Reply: {reply!r}")

    except Exception as exc:
        err = str(exc)
        if "401" in err or "unauthorized" in err.lower():
            return (False,
                    "Invalid Hugging Face token. Check for typos or regenerate at "
                    "huggingface.co/settings/tokens.",
                    err)
        if "429" in err or "rate limit" in err.lower():
            return (True,    # token is valid, just hit the limit
                    "Token is valid but you've hit the rate limit. "
                    "Wait a moment and try again.",
                    err)
        if "503" in err or "loading" in err.lower():
            return (True,    # model loading is normal
                    "Model is loading on HF servers (cold start). "
                    "Wait ~30 seconds then try again — this is normal.",
                    err)
        if "timeout" in err.lower() or "connect" in err.lower():
            return (False,
                    "Could not reach the Hugging Face API. Check your internet connection.",
                    err)
        return (False, f"Hugging Face error: {exc}", err)


# ═══════════════════════════════════════════════════════════════════════════════
# UI helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _step_header(n: int, title: str, done: bool = False) -> None:
    icon  = "✅" if done else f"**{n}**"
    color = _OK if done else _ACCENT
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:12px;margin:18px 0 6px">'
        f'<div style="background:{color};color:#0d1b2a;border-radius:50%;'
        f'width:32px;height:32px;display:flex;align-items:center;justify-content:center;'
        f'font-weight:700;font-size:16px;flex-shrink:0">{icon}</div>'
        f'<div style="font-size:20px;font-weight:700;color:{_TEXT}">{title}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _provider_card(icon: str, name: str, tagline: str,
                   color: str, selected: bool) -> str:
    border = f"3px solid {color}" if selected else f"1px solid #1d3557"
    bg     = f"rgba({','.join(str(int(color.lstrip('#')[i:i+2],16)) for i in (0,2,4))}, 0.15)" \
             if selected else _CARD_BG
    return (
        f'<div style="background:{bg};border:{border};border-radius:12px;'
        f'padding:14px 16px;text-align:center">'
        f'<div style="font-size:30px">{icon}</div>'
        f'<div style="font-weight:700;color:{color};font-size:15px;margin-top:4px">{name}</div>'
        f'<div style="color:{_MUTED};font-size:12px;margin-top:4px">{tagline}</div>'
        f'</div>'
    )


def _result_box(ok: bool, message: str) -> None:
    color = _OK if ok else _ERR
    icon  = "✅" if ok else "❌"
    st.markdown(
        f'<div style="background:{_BG};border:2px solid {color};border-radius:10px;'
        f'padding:14px 18px;margin-top:10px">'
        f'<span style="font-size:22px">{icon}</span> '
        f'<span style="font-size:16px;color:{_TEXT};font-weight:600">{message}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Main render function
# ═══════════════════════════════════════════════════════════════════════════════

def render(ss) -> None:
    """Render the full Getting Started guide. Call from app.py."""

    # ── Hero header ───────────────────────────────────────────────────────────
    st.markdown(f"""
<div style="background:linear-gradient(135deg,#1d3557 0%,#0d1b2a 100%);
            border-radius:14px;padding:28px 32px;margin-bottom:24px;
            border:1px solid #2a4a6a">
  <div style="font-size:28px;font-weight:800;color:{_ACCENT};margin-bottom:8px">
    🚀 Getting Started with Vibe-to-Print Engine
  </div>
  <div style="color:{_TEXT};font-size:16px;line-height:1.7">
    This app turns a <strong>photo of any object</strong> into a
    <strong>3D-printable file</strong> using AI.<br>
    Choose from <strong>Claude&nbsp;(Anthropic)</strong>,
    <strong>ChatGPT&nbsp;(OpenAI)</strong>,
    <strong>Hugging&nbsp;Face</strong> (free online), <strong>Ollama</strong>
    (free, offline), or <strong>Manual&nbsp;Mode</strong> — no AI, no key,
    just pick a template and measure your part.
  </div>
</div>""", unsafe_allow_html=True)

    # ── Step 1 · Choose provider ──────────────────────────────────────────────
    cur_provider = ss.get("ai_provider", "Claude (Anthropic)")
    _step_header(1, "Choose your AI Brain")

    p_col1, p_col2, p_col3, p_col4, p_col5 = st.columns(5, gap="small")
    providers = {
        "Claude (Anthropic)":                ("🟣", "#a78bfa", "Best quality"),
        "GPT-4o (OpenAI)":                   ("🟢", "#34d399", "Great all-rounder"),
        "Free / Open Source (Hugging Face)": ("🤗", "#ffd700", "Free online"),
        "Local (Ollama)":                    ("🔵", "#60a5fa", "Free offline"),
        "Manual (No AI — Template Mode)":    ("🛠️", "#fb923c", "No AI needed"),
    }
    _short = {
        "Claude (Anthropic)":                "Claude",
        "GPT-4o (OpenAI)":                   "GPT-4o",
        "Free / Open Source (Hugging Face)": "HF Free",
        "Local (Ollama)":                    "Ollama",
        "Manual (No AI — Template Mode)":    "Manual",
    }
    chosen_col = {
        "Claude (Anthropic)":                p_col1,
        "GPT-4o (OpenAI)":                   p_col2,
        "Free / Open Source (Hugging Face)": p_col3,
        "Local (Ollama)":                    p_col4,
        "Manual (No AI — Template Mode)":    p_col5,
    }
    for pname, (icon, color, tagline) in providers.items():
        chosen_col[pname].markdown(
            _provider_card(icon, _short[pname], tagline, color, cur_provider == pname),
            unsafe_allow_html=True,
        )

    st.caption(
        f"Currently selected in the sidebar: **{cur_provider}**. "
        "Switch with the 'AI Brain' dropdown in the left sidebar."
    )

    # ── Step 2 · Get API key ──────────────────────────────────────────────────
    _step_header(2, "Get your API key")

    tab_claude, tab_openai, tab_hf, tab_ollama, tab_manual = st.tabs([
        "Claude (Anthropic)", "GPT-4o (OpenAI)",
        "🤗 Hugging Face (Free)", "Ollama (Local — Free)", "🛠️ Manual (No AI)"
    ])

    with tab_claude:
        st.markdown(f"""
<div style="background:{_CARD_BG};border-radius:10px;padding:18px 20px;
            border:1px solid #2a4a6a">
  <ol style="color:{_TEXT};font-size:15px;line-height:2.0;margin:0;padding-left:20px">
    <li>Go to the Anthropic Console:
        <a href="https://console.anthropic.com/keys" target="_blank"
           style="color:{_ACCENT};font-weight:700">
           console.anthropic.com/keys ↗
        </a></li>
    <li>Sign up or log in with your email.</li>
    <li>Click <strong>"Create Key"</strong>, give it a name (e.g. "Vibe-to-Print").</li>
    <li>Copy the key — it starts with <code>sk-ant-api03-...</code></li>
    <li>Paste it into the <strong>"Anthropic API Key"</strong> field in the left sidebar.</li>
    <li>Add a payment method at
        <a href="https://console.anthropic.com/billing" target="_blank"
           style="color:{_WARN}">console.anthropic.com/billing ↗</a>
        (required to make API calls — typical cost: pennies per design).</li>
  </ol>
</div>""", unsafe_allow_html=True)

    with tab_openai:
        st.markdown(f"""
<div style="background:{_CARD_BG};border-radius:10px;padding:18px 20px;
            border:1px solid #2a4a6a">
  <ol style="color:{_TEXT};font-size:15px;line-height:2.0;margin:0;padding-left:20px">
    <li>Go to the OpenAI Platform:
        <a href="https://platform.openai.com/api-keys" target="_blank"
           style="color:{_ACCENT};font-weight:700">
           platform.openai.com/api-keys ↗
        </a></li>
    <li>Sign up or log in.</li>
    <li>Click <strong>"Create new secret key"</strong>.</li>
    <li>Copy the key — it starts with <code>sk-proj-...</code> or <code>sk-...</code></li>
    <li>Paste it into the <strong>"OpenAI API Key"</strong> field in the left sidebar.</li>
    <li>Add credits at
        <a href="https://platform.openai.com/settings/organization/billing" target="_blank"
           style="color:{_WARN}">platform.openai.com/billing ↗</a>.</li>
  </ol>
</div>""", unsafe_allow_html=True)

    with tab_hf:
        st.markdown(f"""
<div style="background:{_CARD_BG};border-radius:10px;padding:18px 20px;
            border:1px solid #2a4a6a">
  <div style="color:{_OK};font-weight:700;font-size:15px;margin-bottom:10px">
    🤗 Hugging Face is free — no credit card needed!
  </div>
  <ol style="color:{_TEXT};font-size:15px;line-height:2.2;margin:0;padding-left:20px">
    <li>Go to Hugging Face:
        <a href="https://huggingface.co/join" target="_blank"
           style="color:{_ACCENT};font-weight:700">huggingface.co/join ↗</a>
        (free account)</li>
    <li>Open your token settings:
        <a href="https://huggingface.co/settings/tokens" target="_blank"
           style="color:{_ACCENT};font-weight:700">
           huggingface.co/settings/tokens ↗
        </a></li>
    <li>Click <strong>"New token"</strong>, choose <strong>Read</strong> access,
        give it a name (e.g. "vibe-to-print").</li>
    <li>Copy the token — it starts with <code>hf_...</code></li>
    <li>Select <strong>"Free / Open Source (Hugging Face)"</strong> in the sidebar.</li>
    <li>Paste your token into the <strong>"HF Token"</strong> field in the sidebar.</li>
  </ol>
  <div style="background:#0d1b2a;border-radius:8px;padding:12px 16px;margin-top:14px">
    <div style="color:{_WARN};font-weight:700;font-size:13px;margin-bottom:6px">
      ⚡ What to expect
    </div>
    <ul style="color:{_MUTED};font-size:13px;line-height:1.9;margin:0;padding-left:18px">
      <li><strong style="color:{_TEXT}">Vision model</strong> (photo analysis):
          Llama 3.2 11B Vision — good quality, free</li>
      <li><strong style="color:{_TEXT}">Text model</strong> (CAD generation):
          Mistral 7B Instruct — solid OpenSCAD generation</li>
      <li>Models may take <strong>20–60 seconds</strong> to wake up on their first call
          (cold start). Subsequent calls are faster.</li>
      <li>Anonymous (no token) access works but has very low rate limits.</li>
    </ul>
  </div>
</div>""", unsafe_allow_html=True)

    with tab_manual:
        st.markdown(f"""
<div style="background:{_CARD_BG};border-radius:10px;padding:18px 20px;
            border:1px solid #2a4a6a">
  <div style="color:{_OK};font-weight:700;font-size:15px;margin-bottom:10px">
    🛠️ Manual Mode — no account, no API key, no internet required!
  </div>
  <div style="color:{_TEXT};font-size:15px;line-height:1.9">
    <strong>How it works:</strong>
    <ol style="margin:8px 0 16px;padding-left:20px;line-height:2.2">
      <li>Select <strong>"Manual (No AI — Template Mode)"</strong> in the AI Brain
          dropdown in the left sidebar.</li>
      <li>Click <strong>"Launch Vibe-to-Print Engine"</strong> below — you'll see
          a template browser instead of the photo upload screen.</li>
      <li>Search or browse <strong>12 built-in parametric templates</strong>:
          knobs, boxes, brackets, hooks, spacers, and more.</li>
      <li>Select a template and fill in your measurements.
          Each field has a sensible default to get you started.</li>
      <li>Click <strong>Confirm Dimensions</strong> — parametric OpenSCAD is
          generated instantly (no AI call, no wait).</li>
      <li>Compile to STL and slice to G-code as usual.</li>
    </ol>
    <div style="background:#0d1b2a;border-radius:8px;padding:12px 16px;
                border-left:3px solid #fb923c">
      <strong style="color:#fb923c">Best for:</strong>
      <span style="color:{_TEXT}"> common replacement parts where you already know
      the shape — knobs, end caps, spacers, brackets — and just need to plug in
      your measurements.</span>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    with tab_ollama:
        st.markdown(f"""
<div style="background:{_CARD_BG};border-radius:10px;padding:18px 20px;
            border:1px solid #2a4a6a">
  <div style="color:{_OK};font-weight:700;font-size:15px;margin-bottom:10px">
    ✅ Ollama is completely free — it runs AI models on your own machine.
  </div>
  <ol style="color:{_TEXT};font-size:15px;line-height:2.2;margin:0;padding-left:20px">
    <li>Install Ollama:
        <a href="https://ollama.com/download" target="_blank"
           style="color:{_ACCENT};font-weight:700">ollama.com/download ↗</a>
        (Mac, Windows, Linux)</li>
    <li>Open a terminal and run:<br>
        <code style="background:#1a2a3a;padding:4px 10px;border-radius:4px;
                     color:#a8dadc">ollama pull llava</code>
        &nbsp;(vision model, ~4 GB)<br>
        <code style="background:#1a2a3a;padding:4px 10px;border-radius:4px;
                     color:#a8dadc">ollama pull llama3</code>
        &nbsp;(text model, ~4 GB)</li>
    <li>Start the server: <code style="background:#1a2a3a;padding:4px 10px;
        border-radius:4px;color:#a8dadc">ollama serve</code></li>
    <li>Select <strong>"Local (Ollama)"</strong> in the sidebar — no key needed!</li>
  </ol>
  <div style="color:{_MUTED};font-size:13px;margin-top:12px">
    ⚡ Requires a modern GPU or Apple Silicon Mac for good speed.
    On CPU-only machines, generation can be slow (1–5 minutes per request).
  </div>
</div>""", unsafe_allow_html=True)

    # ── Step 3 · Test your key ────────────────────────────────────────────────
    key_ok_already = bool(ss.get("api_key", "")) or ss.get("ai_provider") in {
        "Local (Ollama)", "Free / Open Source (Hugging Face)", "Manual (No AI — Template Mode)"
    }
    _step_header(3, "Test your key", done=key_ok_already and bool(ss.get("gs_test_ok")))

    test_col, _ = st.columns([2, 1])
    with test_col:
        _no_key_providers = {
            "Local (Ollama)",
            "Free / Open Source (Hugging Face)",
            "Manual (No AI — Template Mode)",
        }
        test_key_input = st.text_input(
            "Paste your API key here to test (or leave blank to test the sidebar key)",
            type="password",
            key="gs_test_key_input",
            placeholder="sk-ant-...  /  sk-proj-...  /  hf_...  (Ollama: no key needed)",
        )

        ollama_url_input = ""
        if ss.get("ai_provider") == "Local (Ollama)":
            ollama_url_input = st.text_input(
                "Ollama base URL",
                value="http://localhost:11434",
                key="gs_ollama_url",
            )

        test_btn = st.button(
            "Test My Key",
            type="primary",
            use_container_width=True,
            help="Sends a tiny 'Hi' message to verify the key works.",
        )

    if test_btn:
        # Use input field key if provided, else fall back to sidebar key
        key_to_test = test_key_input.strip() or ss.get("api_key", "")
        provider    = ss.get("ai_provider", "Claude (Anthropic)")

        if provider not in _no_key_providers and not key_to_test:
            st.warning("Paste a key above or enter one in the sidebar first.")
        else:
            with st.spinner("Testing your key — sending a tiny 'Hello'…"):
                ok, message, detail = test_key(
                    provider,
                    key_to_test,
                    ollama_url=ollama_url_input or "http://localhost:11434",
                )
            # Store result
            ss["gs_test_ok"]      = ok
            ss["gs_test_message"] = message
            ss["gs_test_detail"]  = detail

            # If key is valid and not already in sidebar, offer to apply it
            if ok and test_key_input.strip():
                ss["gs_pending_key"] = test_key_input.strip()

    # Show persistent result
    if "gs_test_ok" in ss:
        _result_box(ss["gs_test_ok"], ss["gs_test_message"])

        if ss.get("gs_test_detail"):
            with st.expander("Technical details"):
                st.code(ss["gs_test_detail"])

        # Offer to copy valid key to sidebar
        if ss.get("gs_test_ok") and ss.get("gs_pending_key"):
            if st.button("Apply this key to the sidebar", type="primary"):
                ss["api_key"]        = ss["gs_pending_key"]
                ss["gs_pending_key"] = None
                st.success("Key applied! You can now use the app.")

    # ── Step 4 · Tutorial video ───────────────────────────────────────────────
    _step_header(4, "Watch the setup tutorial (optional)")

    video_url = ss.get("gs_video_url", "").strip()

    vid_col, cfg_col = st.columns([3, 2], gap="large")
    with vid_col:
        if video_url:
            # st.video handles YouTube URLs directly
            try:
                st.video(video_url)
            except Exception:
                st.markdown(
                    f'<iframe width="100%" height="280" '
                    f'src="{video_url.replace("watch?v=","embed/")}" '
                    f'frameborder="0" allowfullscreen '
                    f'style="border-radius:10px"></iframe>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(f"""
<div style="background:{_CARD_BG};border:2px dashed #2a4a6a;border-radius:12px;
            height:220px;display:flex;flex-direction:column;
            align-items:center;justify-content:center;gap:10px">
  <div style="font-size:40px">▶️</div>
  <div style="color:{_MUTED};font-size:14px;text-align:center;max-width:260px">
    No tutorial video linked yet.<br>
    Paste a YouTube URL on the right to display it here.
  </div>
</div>""", unsafe_allow_html=True)

    with cfg_col:
        st.caption("Configure tutorial video")
        new_url = st.text_input(
            "YouTube URL",
            value=video_url,
            key="gs_video_url_input",
            placeholder="https://www.youtube.com/watch?v=...",
        )
        if st.button("Set video", use_container_width=True):
            ss["gs_video_url"] = new_url.strip()
            st.rerun()
        if video_url:
            if st.button("Remove video", use_container_width=True):
                ss["gs_video_url"] = ""
                st.rerun()

        st.markdown(f"""
<div style="background:{_CARD_BG};border-radius:8px;padding:10px 12px;
            margin-top:8px;font-size:13px;color:{_MUTED}">
  💡 <strong style="color:{_ACCENT}">Screenshot tip</strong><br>
  You can also upload a PNG/JPG screenshot of your API dashboard
  via the main photo uploader — the AI will walk you through it step by step.
</div>""", unsafe_allow_html=True)

    # ── Step 5 · Start! ───────────────────────────────────────────────────────
    _step_header(5, "Start your first print!")

    _free_providers = {
        "Local (Ollama)",
        "Free / Open Source (Hugging Face)",
        "Manual (No AI — Template Mode)",
    }
    has_key = bool(ss.get("api_key")) or ss.get("ai_provider") in _free_providers

    if has_key:
        st.success("You're all set! Click the button below to start designing.")
    else:
        st.info("Complete steps 1–3 above, then come back here to launch the app.")

    launch_col, _ = st.columns([1, 2])
    launch_col.button(
        "Launch Vibe-to-Print Engine →",
        type="primary",
        use_container_width=True,
        disabled=not has_key,
        key="gs_launch_btn",
        on_click=lambda: ss.update({"phase": "vision"}),
    )

    # ── Install as App ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("📱 Install as an App on Your Phone")
    st.caption(
        "Even though this is a website, you can add it to your home screen so it "
        "feels exactly like a real app — full screen, its own icon, no browser bars."
    )

    ios_col, android_col = st.columns(2, gap="large")

    with ios_col:
        st.markdown(f"""
<div style="background:{_CARD_BG};border:1px solid #2a4a6a;border-radius:12px;
            padding:18px 20px">
  <div style="font-size:24px;margin-bottom:8px">🍎 iPhone / iPad (Safari)</div>
  <ol style="color:{_TEXT};font-size:14px;line-height:2.2;margin:0;padding-left:18px">
    <li>Open the app link in <strong>Safari</strong>
        <span style="color:{_MUTED}">(Chrome on iOS won't work for this)</span></li>
    <li>Tap the <strong>Share button</strong>
        <span style="color:{_ACCENT}">⬆</span> at the bottom of the screen</li>
    <li>Scroll down and tap
        <strong>"Add to Home Screen"</strong></li>
    <li>Optionally rename it, then tap
        <strong style="color:{_OK}">"Add"</strong> in the top-right corner</li>
    <li>The <strong>Vibe-to-Print</strong> icon now appears on your home screen!</li>
  </ol>
  <div style="background:#0d1b2a;border-radius:8px;padding:10px 12px;
              margin-top:12px;font-size:13px;color:{_MUTED}">
    💡 Once installed, it opens full-screen with no browser address bar —
    just like a native app.
  </div>
</div>""", unsafe_allow_html=True)

    with android_col:
        st.markdown(f"""
<div style="background:{_CARD_BG};border:1px solid #2a4a6a;border-radius:12px;
            padding:18px 20px">
  <div style="font-size:24px;margin-bottom:8px">🤖 Android (Chrome)</div>
  <ol style="color:{_TEXT};font-size:14px;line-height:2.2;margin:0;padding-left:18px">
    <li>Open the app link in <strong>Chrome</strong></li>
    <li>Tap the <strong>three-dot menu</strong>
        <span style="color:{_ACCENT}">⋮</span> in the top-right corner</li>
    <li>Tap <strong>"Add to Home screen"</strong>
        <span style="color:{_MUTED}">(or watch for an automatic install banner)</span></li>
    <li>Tap <strong style="color:{_OK}">"Add"</strong> on the confirmation dialog</li>
    <li>The icon appears on your home screen and app drawer!</li>
  </ol>
  <div style="background:#0d1b2a;border-radius:8px;padding:10px 12px;
              margin-top:12px;font-size:13px;color:{_MUTED}">
    💡 On newer Android + Chrome versions, you may see an automatic
    <strong>"Install app"</strong> prompt in the address bar — just tap it!
  </div>
</div>""", unsafe_allow_html=True)

    st.markdown(f"""
<div style="background:#1d3557;border-radius:10px;padding:14px 18px;
            margin-top:12px;display:flex;align-items:flex-start;gap:14px">
  <div style="font-size:28px;flex-shrink:0">✨</div>
  <div>
    <div style="font-weight:700;color:{_ACCENT};font-size:15px;margin-bottom:4px">
      The magic of web apps
    </div>
    <div style="color:{_TEXT};font-size:14px;line-height:1.7">
      Every time a new feature is added to Vibe-to-Print, it <strong>automatically
      appears</strong> on your phone — no App Store update needed. Just open the
      app and the latest version is already there.
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    # ── GitHub / Deploy guide ─────────────────────────────────────────────────
    st.divider()
    st.subheader("🚀 Deploy Your Own Copy (Optional)")
    st.caption("Host Vibe-to-Print yourself so you control updates and keep your API keys private.")

    with st.expander("Step-by-step: GitHub + Streamlit Community Cloud"):
        st.markdown(f"""
<div style="color:{_TEXT};font-size:14px;line-height:2.0">

**Step 1 — Create a GitHub account**
<br>Go to <a href="https://github.com" target="_blank" style="color:{_ACCENT}">github.com ↗</a>
and sign up for free. GitHub is your "command centre" — every change you push
here instantly appears in the live app.

**Step 2 — Create a new repository**
<br>Click the <strong>+</strong> button → <em>New repository</em>.
Name it something like <code>vibe-to-print</code>. Set it to <strong>Public</strong>
(required for the free Streamlit hosting tier).

**Step 3 — Upload your files**
<br>Upload all the <code>.py</code> files, <code>requirements.txt</code>,
the <code>static/</code> folder, and <code>.streamlit/config.toml</code>
using the GitHub web interface or GitHub Desktop.

**Step 4 — Deploy on Streamlit Community Cloud**
<br>Go to <a href="https://share.streamlit.io" target="_blank" style="color:{_ACCENT}">share.streamlit.io ↗</a>,
click <strong>"New app"</strong>, connect your GitHub account, select your repo,
and set the main file to <code>app.py</code>. Hit <strong>Deploy</strong> — your
app is live in ~2 minutes at a <code>*.streamlit.app</code> URL!

**Step 5 — Share the link**
<br>Copy your app URL and send it to anyone. They can open it in a browser and
install it as a home screen app following the instructions above.

**The "Vibe" of updates:**
Whenever you think of a new feature, just edit the file and push to GitHub.
The live app updates automatically — everyone who uses it gets the new version
instantly, with no reinstall required.

</div>
""", unsafe_allow_html=True)

    # ── FAQ ───────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Frequently asked questions")

    faqs = [
        ("Can I use the app offline after installing it?",
         "The app requires an internet connection to call the AI APIs. "
         "However, if you use **Local (Ollama)** or **Manual (Template Mode)**, "
         "you can use it fully offline once Ollama models are downloaded. "
         "The installed icon on your home screen will always open the app — "
         "it just needs Wi-Fi or mobile data to generate designs with cloud AI."),
        ("How much does it cost to use Claude or GPT-4o?",
         "A single design session (photo analysis + OpenSCAD generation) typically costs "
         "**$0.01–$0.05** with Claude or GPT-4o. Both providers give new accounts "
         "some free credits to start."),
        ("Is my photo / API key stored anywhere?",
         "No. Photos are encoded in-memory and sent directly to the AI provider over HTTPS. "
         "Your API key is stored only in your browser session and cleared when you close the tab. "
         "This app does not have a backend database."),
        ("Can I use this without an internet connection?",
         "Yes — select **Local (Ollama)** in the AI Brain dropdown. You'll need to download "
         "the models once (~8 GB total), but after that everything runs on your machine offline."),
        ("What file types does the slicer produce?",
         "The app generates **.scad** (OpenSCAD source), **.stl** (3D mesh), and **.gcode** "
         "(machine instructions for your printer). All three can be downloaded separately."),
        ("Which printers are supported?",
         "Any FDM printer. 18 popular models are pre-configured (Ender 3, Bambu P1S, Prusa MK4, "
         "Voron 2.4, etc.). You can also save custom profiles with your own bed dimensions."),
        ("The sliced G-code doesn't look right — what should I do?",
         "The built-in slicer uses basic settings. For best results, download the **.stl** "
         "and slice it in **PrusaSlicer** or **Bambu Studio** using your usual profile. "
         "The OpenSCAD code is always available as a source of truth."),
    ]

    for question, answer in faqs:
        with st.expander(question):
            st.markdown(answer)
