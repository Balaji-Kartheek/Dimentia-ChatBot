"""
Visual identity and copy for the Streamlit UI (reskin only; logic unchanged).
"""
from __future__ import annotations

# Product surface name shown in the app (internal code may still use original names).
APP_NAME = "Recall Harbor"
APP_TAGLINE = "Private memory workspace — voice, text, and calm organization"
APP_SHORT_TAGLINE = "Private memory workspace"
PAGE_ICON = "✦"

# Navigation labels (values must stay aligned with router keys in main.py).
NAV_HOME = "Overview"
NAV_ADD_MEMORY = "Capture"
NAV_ASK = "Consult"
NAV_SUPPORT = "Reference desk"
NAV_SETTINGS = "Preferences"
NAV_LOGOUT = "Sign out"


def global_css() -> str:
    return """
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap');

    :root {
        --rh-bg-deep: #070a12;
        --rh-bg-mid: #0b1020;
        --rh-bg-elevated: #121a2e;
        --rh-input-bg: rgba(17, 24, 39, 0.95);
        --rh-input-border: rgba(148, 163, 184, 0.35);
        --rh-border: rgba(148, 163, 184, 0.12);
        --rh-text: #e2e8f0;
        --rh-text-muted: #94a3b8;
        --rh-placeholder: #64748b;
        --rh-accent: #38bdf8;
        --rh-accent-soft: rgba(56, 189, 248, 0.15);
    }

    html, body, input, button, textarea, select {
        font-family: "Outfit", system-ui, sans-serif !important;
    }

    .stApp {
        background: var(--rh-bg-deep);
        background-image:
            radial-gradient(ellipse 900px 500px at 15% -20%, rgba(56, 189, 248, 0.12), transparent 55%),
            radial-gradient(ellipse 700px 450px at 95% 10%, rgba(167, 139, 250, 0.08), transparent 50%),
            linear-gradient(165deg, var(--rh-bg-deep) 0%, var(--rh-bg-mid) 45%, #0d1424 100%);
        color: var(--rh-text);
    }

    /* Top chrome: Streamlit header/toolbar/decoration often stay light — make them part of the same canvas */
    div[data-testid="stAppViewContainer"] {
        background: transparent !important;
    }
    header[data-testid="stHeader"] {
        background: transparent !important;
        border-bottom: none !important;
    }
    div[data-testid="stToolbar"] {
        background: transparent !important;
    }
    button[data-testid="baseButton-header"] {
        color: var(--rh-text-muted) !important;
    }
    [data-testid="stDecoration"] {
        display: none !important;
    }
    section[data-testid="stMain"] > div,
    section.main > div {
        background: transparent !important;
    }
    .block-container {
        padding-top: 1.25rem !important;
    }

    section.main [data-testid="stMarkdownContainer"] p,
    section.main [data-testid="stMarkdownContainer"] li {
        color: #cbd5e1;
    }

    h1, h2, h3 {
        font-family: "Source Serif 4", Georgia, serif !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em;
        color: #f1f5f9 !important;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(185deg, #05070d 0%, #0a0f1a 55%, #0d1526 100%) !important;
        border-right: 1px solid var(--rh-border) !important;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label {
        color: #cbd5e1 !important;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] label {
        color: var(--rh-text-muted) !important;
        font-size: 0.75rem !important;
        letter-spacing: 0.06em !important;
        text-transform: uppercase !important;
        font-family: "Outfit", sans-serif !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: var(--rh-border) !important;
    }

    .app-hero {
        background: linear-gradient(125deg, #1e3a5f 0%, #0f2847 35%, #162044 70%, #1a1f3a 100%);
        padding: 1.35rem 1.75rem;
        border-radius: 16px;
        margin-bottom: 1.75rem;
        color: #f8fafc !important;
        text-align: center;
        box-shadow:
            0 0 0 1px rgba(56, 189, 248, 0.2),
            0 20px 50px rgba(0, 0, 0, 0.45);
        border: 1px solid rgba(56, 189, 248, 0.25);
    }
    .app-hero h1 {
        color: #f8fafc !important;
        font-family: "Source Serif 4", Georgia, serif !important;
        margin: 0 0 0.35rem 0;
        font-size: 1.85rem;
    }
    .app-hero p {
        margin: 0;
        opacity: 0.9;
        font-size: 1.02rem;
        font-weight: 500;
        color: #bae6fd !important;
    }

    .login-hero .app-hero {
        text-align: center;
    }

    .memory-card, .surface-card {
        background: rgba(18, 26, 46, 0.85);
        backdrop-filter: blur(10px);
        padding: 1rem 1.15rem;
        border-radius: 14px;
        border: 1px solid var(--rh-border);
        border-left: 4px solid var(--rh-accent);
        margin: 1rem 0;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
    }

    .feature-grid p, .feature-grid li {
        color: #94a3b8;
        line-height: 1.55;
    }

    .success-message {
        background: rgba(16, 185, 129, 0.12);
        color: #6ee7b7;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid rgba(52, 211, 153, 0.35);
    }
    .error-message {
        background: rgba(239, 68, 68, 0.12);
        color: #fca5a5;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid rgba(248, 113, 113, 0.35);
    }
    .info-message {
        background: rgba(56, 189, 248, 0.1);
        color: #7dd3fc;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid rgba(56, 189, 248, 0.3);
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(15, 23, 42, 0.6) !important;
        padding: 6px;
        border-radius: 12px;
        border: 1px solid var(--rh-border);
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: #cbd5e1;
    }

    [data-testid="stExpander"] details {
        background-color: rgba(15, 23, 42, 0.4);
        border: 1px solid var(--rh-border);
        border-radius: 10px;
    }

    div[data-testid="stMetric"] {
        background: rgba(15, 23, 42, 0.5);
        padding: 0.75rem 1rem;
        border-radius: 12px;
        border: 1px solid var(--rh-border);
    }

    /* ---- Form controls (Streamlit + Base Web): readable text & muted placeholders ---- */
    label[data-testid="stWidgetLabel"] p,
    label[data-testid="stWidgetLabel"] span {
        color: #cbd5e1 !important;
    }

    .stApp input:not([type="checkbox"]):not([type="radio"]):not([type="submit"]),
    .stApp textarea,
    .stApp select {
        background-color: var(--rh-input-bg) !important;
        color: #e2e8f0 !important;
        border: 1px solid var(--rh-input-border) !important;
        border-radius: 8px !important;
        caret-color: var(--rh-accent) !important;
    }

    .stApp input::placeholder,
    .stApp textarea::placeholder {
        color: var(--rh-placeholder) !important;
        opacity: 1 !important;
    }
    .stApp input::-webkit-input-placeholder,
    .stApp textarea::-webkit-input-placeholder {
        color: var(--rh-placeholder) !important;
        opacity: 1 !important;
    }
    .stApp input::-moz-placeholder,
    .stApp textarea::-moz-placeholder {
        color: var(--rh-placeholder) !important;
        opacity: 1 !important;
    }
    .stApp input:-ms-input-placeholder,
    .stApp textarea:-ms-input-placeholder {
        color: var(--rh-placeholder) !important;
    }

    /* Base Web wrappers (Streamlit text_input / text_area / number_input) */
    [data-baseweb="input"] input,
    [data-baseweb="textarea"] textarea {
        background-color: var(--rh-input-bg) !important;
        color: #e2e8f0 !important;
        border-color: var(--rh-input-border) !important;
    }
    [data-baseweb="input"] input::placeholder,
    [data-baseweb="textarea"] textarea::placeholder {
        color: var(--rh-placeholder) !important;
        opacity: 1 !important;
    }

    /* Select / multiselect control surface */
    [data-baseweb="select"] > div,
    [data-baseweb="select"] [role="combobox"] {
        background-color: var(--rh-input-bg) !important;
        border-color: var(--rh-input-border) !important;
        color: #e2e8f0 !important;
    }
    [data-baseweb="select"] [class*="singleValue"],
    [data-baseweb="select"] [class*="valueContainer"] {
        color: #e2e8f0 !important;
    }
    [data-baseweb="select"] [class*="placeholder"] {
        color: var(--rh-placeholder) !important;
    }

    /* Dropdown menus (portaled) */
    div[data-baseweb="popover"] ul,
    div[data-baseweb="menu"] {
        background-color: #0f172a !important;
        border: 1px solid var(--rh-input-border) !important;
    }
    div[data-baseweb="popover"] li,
    div[data-baseweb="menu"] li {
        color: #e2e8f0 !important;
        background-color: transparent !important;
    }
    div[data-baseweb="popover"] li:hover {
        background-color: rgba(56, 189, 248, 0.12) !important;
    }

    /* File uploader */
    [data-testid="stFileUploaderDropzone"] {
        background: rgba(17, 24, 39, 0.75) !important;
        border: 1px dashed var(--rh-input-border) !important;
        border-radius: 10px !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] span,
    [data-testid="stFileUploaderDropzoneInstructions"] small,
    [data-testid="stFileUploaderDropzoneInstructions"] div {
        color: var(--rh-text-muted) !important;
    }
    .stApp [data-testid="stBaseButton-secondary"] {
        color: #e2e8f0 !important;
        border: 1px solid var(--rh-input-border) !important;
        background-color: rgba(30, 41, 59, 0.85) !important;
    }

    /* Dataframe / table text in dark */
    [data-testid="stDataFrame"] {
        color: #e2e8f0;
    }

    /* Autofill: stop bright yellow blocks in Chrome */
    .stApp input:-webkit-autofill,
    .stApp input:-webkit-autofill:hover,
    .stApp input:-webkit-autofill:focus,
    .stApp textarea:-webkit-autofill {
        -webkit-box-shadow: 0 0 0 1000px #111827 inset !important;
        -webkit-text-fill-color: #e2e8f0 !important;
        caret-color: var(--rh-accent) !important;
    }
    """


def sidebar_brand_block() -> str:
    return f"""
    <div style="padding: 0.25rem 0 1rem 0;">
        <p style="margin:0; font-size:1.35rem; font-weight:700; letter-spacing:-0.03em;">{PAGE_ICON} {APP_NAME}</p>
        <p style="margin:0.35rem 0 0 0; font-size:0.82rem; opacity:0.85; line-height:1.35;">{APP_SHORT_TAGLINE}</p>
    </div>
    """
