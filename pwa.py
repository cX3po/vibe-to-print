"""
pwa.py
------
Progressive Web App (PWA) support for Vibe-to-Print Engine.

Injects the HTML <head> tags that allow the app to be "installed" on a phone
like a native app via Chrome (Android) or Safari (iPhone) "Add to Home Screen".

Static assets (manifest.json, icon.svg) live in ./static/ and are served at
/app/static/ by Streamlit's built-in static file server
(enableStaticServing = true in .streamlit/config.toml).

Public API
----------
inject()    — call once at the top of app.py, before any other st.* calls.
"""

from __future__ import annotations
import streamlit as st

# Path where Streamlit serves the ./static/ folder
_STATIC = "./app/static"


def inject() -> None:
    """
    Inject all PWA-related <head> elements into the Streamlit page.
    Safe to call multiple times (Streamlit deduplicates identical markdown blocks).
    """
    manifest_url    = f"{_STATIC}/manifest.json"
    icon_url        = f"{_STATIC}/icon.svg"
    theme_color     = "#1d3557"
    app_name        = "Vibe-to-Print Engine"
    app_name_short  = "Vibe-to-Print"

    st.markdown(f"""
<head>
  <!-- ── Web App Manifest (Android Chrome install / PWA) ──────────── -->
  <link rel="manifest" href="{manifest_url}">

  <!-- ── iOS Safari "Add to Home Screen" ─────────────────────────── -->
  <meta name="apple-mobile-web-app-capable"            content="yes">
  <meta name="apple-mobile-web-app-status-bar-style"   content="black-translucent">
  <meta name="apple-mobile-web-app-title"              content="{app_name_short}">
  <link rel="apple-touch-icon"                         href="{icon_url}">

  <!-- ── Android / Chrome theme colour ───────────────────────────── -->
  <meta name="theme-color"           content="{theme_color}">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="application-name"       content="{app_name}">

  <!-- ── Open Graph / share preview ──────────────────────────────── -->
  <meta property="og:title"       content="{app_name}">
  <meta property="og:description" content="Turn any photo into a 3D-printable file using AI.">
  <meta property="og:image"       content="{icon_url}">
  <meta property="og:type"        content="website">

  <!-- ── Viewport (already set by Streamlit but belt-and-suspenders) -->
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
</head>
""", unsafe_allow_html=True)
