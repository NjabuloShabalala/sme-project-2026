import base64
import html
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# .env is read from next to this file first, then from the folder you launched from.
# override=True so an empty or stale shell variable cannot hide the key in .env.
ENV_FILE = None
try:
    from dotenv import find_dotenv, load_dotenv
    _p = Path(__file__).resolve().with_name(".env")
    if not _p.is_file():
        _alt = find_dotenv(usecwd=True)
        _p = Path(_alt) if _alt else None
    if _p:
        load_dotenv(_p, override=True)
        ENV_FILE = str(_p)
except Exception:
    pass
if os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_API_KEY"].strip().strip("\"'")
try:
    import anthropic
except Exception:
    anthropic = None

st.set_page_config(page_title="VulaFlow | Procurement Co-Pilot", page_icon="🇿🇦", layout="wide")

# ---------------------------------------------------------------- STYLING
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #F8FAFC; }
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E2E8F0; }
    .stButton>button { background-color: #0F4C81; color: white; border-radius: 8px; height: 2.8em;
        width: 100%; font-weight: 600; border: none; transition: background-color 0.2s; }
    .stButton>button:hover { background-color: #0A365C; color: white; }
    .css-card { background-color: #FFFFFF; padding: 24px; border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03);
        border: 1px solid #E2E8F0; margin-bottom: 20px; }
    .badge { color: white; padding: 4px 12px; border-radius: 30px; font-size: 0.75em; font-weight: 700;
        margin-left: 8px; display: inline-block; vertical-align: middle; }
    .badge-ready { background: linear-gradient(135deg, #059669 0%, #10B981 100%); }
    .badge-fix { background: linear-gradient(135deg, #D97706 0%, #F59E0B 100%); }
    .badge-no { background: linear-gradient(135deg, #DC2626 0%, #EF4444 100%); }
    .sector-badge { background-color: #EFF6FF; color: #1D4ED8; padding: 6px 14px; border-radius: 20px;
        font-size: 0.85em; font-weight: 600; display: inline-block; border: 1px solid #BFDBFE; margin-bottom: 12px; }
    .doc-valid { background: #F0FDF4; border-left: 4px solid #22C55E; padding: 16px; border-radius: 8px; margin-bottom: 12px; color: #166534; }
    .doc-warning { background: #FFFBEB; border-left: 4px solid #F59E0B; padding: 16px; border-radius: 8px; margin-bottom: 12px; color: #92400E; }
    .doc-error { background: #FEF2F2; border-left: 4px solid #EF4444; padding: 16px; border-radius: 8px; margin-bottom: 12px; color: #991B1B; }
    .fixbox { background: #FFFBEB; border: 1px solid #FDE68A; padding: 10px 14px; border-radius: 8px; margin-top: 8px; color: #92400E; font-size: 0.92em; }
    .whybox { background: #F8FAFC; padding: 10px 14px; border-radius: 6px; margin-top: 8px; font-size: 0.9em; color: #334155; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------- ENTERPRISE DARK THEME (additive overlay, v4)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
    :root { --bg:#0A0D12; --panel:#10151C; --raised:#172030; --line:#243041; --text:#E8EEF5; --muted:#8FA1B5;
            --blue:#4C9AFF; --green:#2FD07F; --amber:#F5A623; --red:#FF5C5C; }
    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif !important; }
    .stApp { background-color: var(--bg) !important; color: var(--text); color-scheme: dark; }
    .block-container { padding-top: 0.6rem !important; max-width: 1400px; }
    [data-testid="stHeader"] { background: transparent !important; }
    [data-testid="stSidebar"] { background-color: var(--panel) !important; border-right: 1px solid var(--line) !important; }
    [data-testid="stSidebar"] * { color: var(--text); }
    [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3, [data-testid="stMarkdownContainer"] h4 { color: var(--text); }
    [data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label, label { color: var(--muted) !important; font-size: 0.84rem; }
    [data-testid="stCaptionContainer"], .stCaption { color: var(--muted) !important; }
    h1, h2, h3, h4 { letter-spacing: 0.005em; }
    /* inline colours set by the v3 markup, remapped for dark */
    [style*="0f4c81" i] { color: #7CB7FF !important; }
    [style*="1e293b" i] { color: var(--text) !important; }
    [style*="64748b" i], [style*="475569" i] { color: var(--muted) !important; }
    /* panels */
    .css-card { background-color: var(--panel) !important; border: 1px solid var(--line) !important; border-radius: 4px !important;
        box-shadow: none !important; padding: 16px 18px !important; }
    .sector-badge { background-color: var(--raised) !important; color: var(--blue) !important; border: 1px solid var(--line) !important;
        border-radius: 3px !important; font-family: 'IBM Plex Mono', monospace; font-size: 0.78em !important; }
    .badge { border-radius: 3px !important; font-family: 'IBM Plex Mono', monospace; font-weight: 600 !important; background-image: none !important; }
    .badge-ready { background: rgba(47,208,127,.12) !important; color: var(--green) !important; border: 1px solid rgba(47,208,127,.5); }
    .badge-fix { background: rgba(245,166,35,.12) !important; color: var(--amber) !important; border: 1px solid rgba(245,166,35,.5); }
    .badge-no { background: rgba(255,92,92,.12) !important; color: var(--red) !important; border: 1px solid rgba(255,92,92,.5); }
    .doc-valid { background: rgba(47,208,127,.08) !important; border-left: 3px solid var(--green) !important; color: #9BE8C2 !important; border-radius: 3px !important; }
    .doc-warning { background: rgba(245,166,35,.08) !important; border-left: 3px solid var(--amber) !important; color: #FFD58A !important; border-radius: 3px !important; }
    .doc-error { background: rgba(255,92,92,.08) !important; border-left: 3px solid var(--red) !important; color: #FFB1B1 !important; border-radius: 3px !important; }
    .fixbox { background: rgba(245,166,35,.08) !important; border: 1px solid rgba(245,166,35,.35) !important; color: #FFD58A !important; border-radius: 3px !important; }
    .whybox { background: var(--raised) !important; color: var(--text) !important; border: 1px solid var(--line); border-radius: 3px !important; }
    /* controls */
    .stButton>button, .stDownloadButton>button, .stFormSubmitButton>button { background-color: #1F6FEB !important; color: #fff !important;
        border: 1px solid #3B82F6 !important; border-radius: 3px !important; font-weight: 600; letter-spacing: 0.01em; }
    .stButton>button:hover, .stDownloadButton>button:hover, .stFormSubmitButton>button:hover { background-color: #388BFD !important; }
    .stButton>button:disabled { background-color: var(--raised) !important; color: var(--muted) !important; border-color: var(--line) !important; }
    [data-baseweb="input"] > div, [data-baseweb="base-input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {
        background-color: var(--raised) !important; border-color: var(--line) !important; border-radius: 3px !important; }
    input, textarea { color: var(--text) !important; -webkit-text-fill-color: var(--text) !important; }
    [data-baseweb="popover"] *, [data-baseweb="menu"] { background-color: var(--raised) !important; color: var(--text) !important; }
    [data-testid="stFileUploaderDropzone"] { background: var(--raised) !important; border: 1px dashed #35465C !important; border-radius: 3px !important; }
    [data-testid="stFileUploaderDropzone"] * { color: var(--muted) !important; }
    [data-testid="stExpander"] { background: var(--panel) !important; border: 1px solid var(--line) !important; border-radius: 4px !important; }
    [data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { color: var(--text) !important; }
    [data-testid="stForm"] { background: var(--panel) !important; border: 1px solid var(--line) !important; border-radius: 4px !important; }
    [data-testid="stAlert"] { background: var(--raised) !important; border: 1px solid var(--line) !important; border-radius: 3px !important; }
    [data-testid="stAlert"] * { color: var(--text) !important; }
    [data-testid="stMetric"] { background: var(--panel); border: 1px solid var(--line); border-radius: 4px; padding: 10px 14px; }
    [data-testid="stMetricValue"] { font-family: 'IBM Plex Mono', monospace !important; color: var(--text) !important; }
    [data-testid="stMetricLabel"] * { color: var(--muted) !important; }
    [data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 4px; }
    hr { border-color: var(--line) !important; }
    ::-webkit-scrollbar { width: 10px; height: 10px; } ::-webkit-scrollbar-thumb { background: #2A3A50; border-radius: 3px; }
    /* terminal status bar */
    .vf-term { display: flex; justify-content: space-between; align-items: center; background: #05070A; border: 1px solid var(--line);
        border-bottom: 2px solid var(--amber); padding: 7px 14px; margin-bottom: 14px; font-family: 'IBM Plex Mono', monospace;
        font-size: 0.78rem; color: var(--muted); }
    .vf-term .vf-brand { color: var(--amber); font-weight: 600; letter-spacing: 0.08em; }
    .vf-term .vf-sep { margin: 0 10px; color: #35465C; }
    .vf-term .vf-live-on { color: var(--green); } .vf-term .vf-live-off { color: var(--muted); }
    /* shared analysis widgets (supplier analysis panel, RFQ tables) */
    .vf-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 4px; background: var(--panel); margin-bottom: 10px; }
    .vf-table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
    .vf-table th { background: var(--raised); text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); color: var(--muted); font-weight: 600; white-space: nowrap; }
    .vf-table td { padding: 8px 10px; border-bottom: 1px solid #1B2433; color: var(--text); vertical-align: top; }
    .vf-table tr:last-child td { border-bottom: none; }
    .vf-mono { font-family: 'IBM Plex Mono', monospace; }
    .dot { display: inline-block; width: 11px; height: 11px; border-radius: 50%; margin-right: 8px; vertical-align: middle; }
    .dot-green { background: var(--green); box-shadow: 0 0 8px rgba(47,208,127,.65); }
    .dot-amber { background: var(--amber); box-shadow: 0 0 8px rgba(245,166,35,.65); }
    .dot-red { background: var(--red); box-shadow: 0 0 8px rgba(255,92,92,.65); }
    .vf-panel-title { font-size: 0.95rem; font-weight: 600; color: var(--text); margin: 2px 0 8px 0; }
    .vf-panel-sub { color: var(--muted); font-size: 0.8rem; margin-bottom: 8px; }
    .vf-light { display: flex; align-items: center; background: var(--raised); border: 1px solid var(--line); border-radius: 4px; padding: 10px 14px; margin-bottom: 10px; }
    .vf-light .dot { width: 16px; height: 16px; }
    .vf-score { background: var(--raised); border: 1px solid var(--line); border-radius: 4px; padding: 12px 16px; margin-bottom: 10px; }
    .vf-score-num { font-family: 'IBM Plex Mono', monospace; font-size: 2.6rem; font-weight: 600; color: var(--text); line-height: 1.05; }
    .vf-score-lbl { color: var(--muted); font-size: 0.8rem; margin-bottom: 8px; }
    .vf-bar { height: 8px; background: #0A0D12; border: 1px solid var(--line); border-radius: 2px; }
    .vf-bar > div { height: 100%; background: var(--blue); }
    .vf-ai { background: var(--raised); border: 1px solid var(--line); border-left: 3px solid var(--blue); border-radius: 3px; padding: 10px 14px; margin-bottom: 10px; color: var(--text); font-size: 0.92rem; }
    .vf-note { background: #0D1219; border: 1px dashed #35465C; border-radius: 3px; padding: 10px 14px; color: var(--muted); font-size: 0.83rem; margin-bottom: 8px; }
    .vf-note b, .vf-note .vf-mono { color: var(--text); }
    </style>
""", unsafe_allow_html=True)
# ---------------------------------------------------------------- AI (optional, always has a fallback)
AI_ENABLED = os.getenv("VULA_AI", "on").lower() != "off"
MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")
if "ai_last_error" not in st.session_state:
    st.session_state["ai_last_error"] = None


def ai_problem():
    """Plain-English reason the AI cannot run right now, or None when it can."""
    if not AI_ENABLED:
        return "VULA_AI is set to off"
    if anthropic is None:
        return f"the anthropic package is not installed in this Python ({sys.executable}). Run: {sys.executable} -m pip install anthropic"
    if not os.getenv("ANTHROPIC_API_KEY"):
        return ("ANTHROPIC_API_KEY is empty or missing in " + ENV_FILE) if ENV_FILE else \
               "no .env file was found next to the app or in the folder you launched from"
    return None


@st.cache_resource
def _make_client(api_key):
    return anthropic.Anthropic(api_key=api_key)


def get_client():
    if ai_problem():
        return None
    try:
        return _make_client(os.environ["ANTHROPIC_API_KEY"])
    except Exception as e:
        st.session_state["ai_last_error"] = f"{type(e).__name__}: {str(e)[:300]}"
        return None


client = get_client()


def ask_claude_blocks(content, max_tokens=700):
    """content is a string or a list of content blocks (text, document, image). Returns text, or None on any failure,
    and records the real reason in session state so the screen can show it."""
    if client is None:
        st.session_state["ai_last_error"] = "AI is off: " + (ai_problem() or "client could not be created")
        return None
    try:
        res = client.messages.create(model=MODEL, max_tokens=max_tokens,
                                     messages=[{"role": "user", "content": content}])
        text = "".join(b.text for b in res.content if getattr(b, "type", "") == "text").strip()
        st.session_state["ai_last_error"] = None
        return text or None
    except Exception as e:
        st.session_state["ai_last_error"] = f"{type(e).__name__}: {str(e)[:300]}"
        return None


def ask_claude(prompt, max_tokens=700):
    """Returns text, or None when AI is off or the call fails. Callers must have a fallback."""
    return ask_claude_blocks(prompt, max_tokens)


def _file_block(data, media_type):
    kind = "document" if media_type == "application/pdf" else "image"
    return {"type": kind, "source": {"type": "base64", "media_type": media_type,
                                     "data": base64.standard_b64encode(data).decode()}}


_vf_ai_on = client is not None
_vf_role = {"SME": "SME vendor session", "Corporate": "Corporate buyer session"}.get(st.session_state.get("portal_role"), "Signed out")
st.markdown(f"""<div class="vf-term"><div><span class="vf-brand">VULAFLOW</span><span class="vf-sep">|</span>Enterprise Procurement Terminal</div>
    <div><span>{_vf_role}</span><span class="vf-sep">|</span><span>{datetime.now():%d %b %Y %H:%M}</span></div></div>""", unsafe_allow_html=True)

esc = html.escape

# ---------------------------------------------------------------- DOMAIN DATA
SA_PROVINCES = ["Gauteng", "Western Cape", "KwaZulu-Natal", "Eastern Cape", "Free State",
                "Limpopo", "Mpumalanga", "North West", "Northern Cape"]

SECTOR_KEYWORDS = {
    "Renewable Energy & Solar": ["solar", "photovoltaic", "pv ", "inverter", "renewable"],
    "Electrical Engineering": ["electrical", "wiring", "electrician", "switchgear"],
    "Precision Agriculture & IoT": ["farming", "irrigation", "crop", "agricultur", "agri"],
    "Construction & Roofing": ["roof", "waterproof", "construction", "building"],
    "ICT Services": ["software", "it support", "network", "helpdesk"],
}
# Sectors treated as close enough to pass the category rule (shown as "related" in the matrix)
RELATED = {
    "Renewable Energy & Solar": {"Electrical Engineering"},
    "Electrical Engineering": {"Renewable Energy & Solar"},
}
DOC_LABEL = {"CIPC": "CIPC registration", "Tax": "tax compliance letter", "B-BBEE": "B-BBEE certificate"}
DOC_SOURCE = {"CIPC": "CIPC registration document", "Tax": "SARS tax compliance letter",
              "B-BBEE": "B-BBEE certificate"}
WARN_DAYS = 30


def today():
    return date.today()


def fmt(d):
    return d.strftime("%d %b %Y")


def classify_sector(text):
    """Deterministic keyword classifier first, AI only if no keyword matches."""
    low = (text or "").lower()
    best, best_hits = None, 0
    for sector, words in SECTOR_KEYWORDS.items():
        hits = sum(1 for w in words if w in low)
        if hits > best_hits:
            best, best_hits = sector, hits
    if best:
        return best
    out = ask_claude(f'Name the industry sector of this South African business or tender in 2 to 4 words, '
                     f'no punctuation, nothing else.\n\n"{text}"', max_tokens=25)
    return out.title() if out else "General Services"


def parse_documents_with_ai(files):
    """files: list of (file_name, bytes). Claude reads PDFs (including scans), images and .txt directly.
    Returns (fields_dict, error_message_or_None). It never fills in made-up data when the AI fails."""
    if client is None:
        return {}, "AI is off: " + (ai_problem() or "client could not be created")
    blocks = []
    for name, data in files[:5]:
        low = name.lower()
        if low.endswith(".pdf"):
            blocks += [{"type": "text", "text": f"Document file name: {name}"}, _file_block(data, "application/pdf")]
        elif low.endswith(".png"):
            blocks += [{"type": "text", "text": f"Document file name: {name}"}, _file_block(data, "image/png")]
        elif low.endswith((".jpg", ".jpeg")):
            blocks += [{"type": "text", "text": f"Document file name: {name}"}, _file_block(data, "image/jpeg")]
        elif low.endswith(".txt"):
            blocks.append({"type": "text", "text": f"Document file name: {name}\n" + data.decode("utf-8", errors="ignore")[:20000]})
    if not blocks:
        return {}, "None of the uploaded files could be read (use PDF, PNG, JPG or TXT)."
    prompt = (
        "These are South African business compliance documents (CIPC registration, SARS tax compliance letter, "
        "B-BBEE certificate or affidavit). Combine what they say into ONE JSON object and return ONLY that JSON. "
        "Keys: business_name (registered name), description (what the business does, only if a document states it, else null), "
        f"region (one of {', '.join(SA_PROVINCES)}, taken from the registered or physical address, else null), "
        "bbbee_level (integer 1 to 8 from the B-BBEE certificate, else null), "
        "cipc (CIPC document validity or expiry date as YYYY-MM-DD, else null), "
        "tax (tax compliance letter expiry or validity-end date as YYYY-MM-DD, else null), "
        "bbbee (B-BBEE certificate expiry date as YYYY-MM-DD, else null), "
        "documents_found (array containing any of 'CIPC', 'Tax', 'B-BBEE'), "
        "notes (one short sentence about anything unclear). Use null when not stated. Never invent anything.")
    raw = ask_claude_blocks(blocks + [{"type": "text", "text": prompt}], max_tokens=1500)
    data = _json_from(raw)
    if not data:
        return {}, st.session_state.get("ai_last_error") or "The AI replied, but the answer could not be read. Please try again."
    return data, None


def parse_date(s, default):
    try:
        return datetime.strptime(str(s), "%Y-%m-%d").date()
    except Exception:
        return default


# ---------------------------------------------------------------- RULE ENGINE (no AI in here)
def evaluate(sme, rfq):
    """Returns one row per rule. Eligibility is decided here, by code."""
    rows = []
    closing = rfq["closes"]

    def add(rule_id, rule, requirement, value, source, passed, fixable, fix="", warning=""):
        rows.append(dict(rule_id=rule_id, rule=rule, requirement=requirement, value=value,
                         source=source, passed=passed, fixable=fixable, fix=fix, warning=warning))

    same = sme["sector"] == rfq["sector"]
    related = sme["sector"] in RELATED.get(rfq["sector"], set())
    add("sector", "Service category", f"{rfq['sector']} (or related)",
        sme["sector"] + (" (related)" if related and not same else ""), "Business profile",
        same or related, False)
    add("region", "Province served", rfq["region"], sme["region"], "Business profile",
        sme["region"] == rfq["region"], False)
    add("bbbee_level", "B-BBEE level", f"Level {rfq['max_bbbee']} or better", f"Level {sme['bbbee_level']}",
        DOC_SOURCE["B-BBEE"], sme["bbbee_level"] <= rfq["max_bbbee"], False)

    for doc, rule_id in (("CIPC", "cipc"), ("Tax", "tax"), ("B-BBEE", "bbbee_cert")):
        exp = sme["docs"].get(doc)
        label = DOC_LABEL[doc]
        need = f"Valid on closing date ({fmt(closing)})"
        if exp is None:
            add(rule_id, f"{doc} document", need, "Missing", "No document on file", False, True,
                f"Upload your {label}")
        elif exp < closing:
            add(rule_id, f"{doc} document", need, f"Expired {fmt(exp)}", DOC_SOURCE[doc], False, True,
                f"Upload a renewed {label}")
        else:
            gap = (exp - closing).days
            warn = f"Expires {gap} days after closing" if gap < WARN_DAYS else ""
            add(rule_id, f"{doc} document", need, f"Valid to {fmt(exp)}", DOC_SOURCE[doc], True, True,
                warning=warn)
    return rows


def tier_of(rows):
    failed = [r for r in rows if not r["passed"]]
    if not failed:
        return "READY"
    if all(r["fixable"] for r in failed):
        return "FIXABLE"
    return "NOT_ELIGIBLE"


def tier_badge(tier, rows):
    if tier == "READY":
        return '<span class="badge badge-ready">READY NOW</span>'
    if tier == "FIXABLE":
        n = sum(1 for r in rows if not r["passed"])
        return f'<span class="badge badge-fix">{n} FIX{"ES" if n > 1 else ""} AWAY</span>'
    return '<span class="badge badge-no">NOT ELIGIBLE</span>'


TIER_COLOUR = {"READY": "#10B981", "FIXABLE": "#F59E0B", "NOT_ELIGIBLE": "#EF4444"}
TIER_ORDER = {"READY": 0, "FIXABLE": 1, "NOT_ELIGIBLE": 2}


def matrix_df(rfq, smes):
    recs = []
    for sme in smes:
        for r in evaluate(sme, rfq):
            recs.append({"Supplier": sme["name"], "Rule": r["rule"], "Requirement": r["requirement"],
                         "Supplier value": r["value"], "Source": r["source"],
                         "Result": "PASS" if r["passed"] else "FAIL",
                         "Fix": r["fix"], "Note": r["warning"]})
    return pd.DataFrame(recs)


def classify_all(rfq, smes):
    out = []
    for sme in smes:
        rows = evaluate(sme, rfq)
        out.append((sme, rows, tier_of(rows)))
    out.sort(key=lambda t: (TIER_ORDER[t[2]], t[0]["bbbee_level"], t[0]["name"]))
    return out


# ---------------------------------------------------------------- PROPOSAL DRAFTER (facts-only, verified in code)
def fact_sheet(sme, rfq):
    docs = "; ".join(f"{DOC_LABEL[d]} valid to {fmt(e)}" for d, e in sme["docs"].items() if e)
    return {
        "company": sme["name"], "province": sme["region"], "sector": sme["sector"],
        "bbbee_level": f"Level {sme['bbbee_level']}", "services": sme["description"],
        "past_work": sme.get("references", ""), "compliance": docs,
        "rfq_title": rfq["title"], "rfq_scope": rfq["scope"], "rfq_closes": fmt(rfq["closes"]),
        "rfq_budget": rfq["budget"], "rfq_po": rfq["po_ref"],
    }


def numbers_in(text):
    return {m.rstrip(".,") for m in re.findall(r"\d[\d,\.]*", text)}


def verify_draft(text, facts):
    allowed = numbers_in(" ".join(str(v) for v in facts.values()))
    bad = sorted(n for n in numbers_in(text) if n not in allowed)
    return (not bad), bad


def template_draft(f):
    return (f"Subject: Response to {f['rfq_title']}\n\n"
            f"Dear Procurement Team,\n\n"
            f"{f['company']} is a {f['bbbee_level']} B-BBEE supplier based in {f['province']}. "
            f"We submit this response to your request for {f['rfq_title']} (reference {f['rfq_po']}).\n\n"
            f"What we do: {f['services']}\n\n"
            f"Relevant experience: {f['past_work'] or '[SME to add past work]'}\n\n"
            f"Compliance: {f['compliance']}. Full documents are attached in the compliance packet.\n\n"
            f"Price and delivery timeline: [SME to complete]\n\n"
            f"Kind regards,\n{f['company']}")


def generate_proposal(sme, rfq):
    """Returns (text, source, note). AI draft only if it passes the facts check, else template."""
    f = fact_sheet(sme, rfq)
    prompt = f"""Write a short, plain-English proposal (under 220 words) from a South African small business
responding to a corporate request. Use ONLY the facts below. Do not invent clients, projects, prices, numbers,
certifications or dates. Leave price and delivery timeline as the placeholder [SME to complete].
Sections: Subject line, greeting, who we are, how we meet the request, compliance, price placeholder, sign-off.

FACTS (JSON):
{json.dumps(f, indent=2)}"""
    for _ in range(2):
        text = ask_claude(prompt, max_tokens=700)
        if not text:
            break
        ok, bad = verify_draft(text, f)
        if ok:
            return text, "AI-assisted draft", f"Facts check passed ({len(numbers_in(text))} numbers matched to the record)"
        prompt += f"\n\nYour last draft contained numbers not in the facts: {bad}. Remove them."
    note = "Template draft (AI off or draft failed the facts check)"
    return template_draft(f), "Template draft", note


# ---------------------------------------------------------------- SEED DATA / STATE
def seed_registry():
    t = today()
    return [
        {"name": "EcoSpark Solar Solutions", "sector": "Renewable Energy & Solar", "region": "Gauteng", "bbbee_level": 1,
         "description": "Photovoltaic maintenance and green energy systems for commercial sites.",
         "references": "Serviced rooftop solar arrays at commercial warehouses.",
         "docs": {"CIPC": t + timedelta(days=400), "Tax": t + timedelta(days=200), "B-BBEE": t + timedelta(days=150)}},
        {"name": "Thabo Electrical", "sector": "Electrical Engineering", "region": "Gauteng", "bbbee_level": 2,
         "description": "Electrical wiring and commercial infrastructure repairs.",
         "references": "Maintenance contracts for office parks.",
         "docs": {"CIPC": t + timedelta(days=500), "Tax": t + timedelta(days=21), "B-BBEE": t + timedelta(days=120)}},
        {"name": "Sizwe Roof & Solar Services", "sector": "Renewable Energy & Solar", "region": "Gauteng", "bbbee_level": 2,
         "description": "Solar panel servicing, inverter checks and roof-mounted system maintenance.",
         "references": "Annual servicing for school and clinic solar installations.",
         "docs": {"CIPC": t + timedelta(days=300), "Tax": t - timedelta(days=45), "B-BBEE": t + timedelta(days=90)}},
        {"name": "Highveld Solar Co", "sector": "Renewable Energy & Solar", "region": "Gauteng", "bbbee_level": 4,
         "description": "Solar installation and servicing.", "references": "Residential and light commercial installs.",
         "docs": {"CIPC": t + timedelta(days=300), "Tax": t + timedelta(days=200), "B-BBEE": t + timedelta(days=200)}},
        {"name": "Karoo Solar Installers", "sector": "Renewable Energy & Solar", "region": "Western Cape", "bbbee_level": 1,
         "description": "Off-grid solar installation and maintenance.", "references": "Farm and lodge solar systems.",
         "docs": {"CIPC": t + timedelta(days=300), "Tax": t + timedelta(days=200), "B-BBEE": t + timedelta(days=200)}},
        {"name": "ApexAgro Solutions", "sector": "Precision Agriculture & IoT", "region": "Gauteng", "bbbee_level": 1,
         "description": "Automated precision farming systems and IoT-driven irrigation hardware.",
         "references": "Deployed irrigation IoT systems for commercial farm co-ops.",
         "docs": {"CIPC": t + timedelta(days=300), "Tax": t + timedelta(days=200), "B-BBEE": t + timedelta(days=200)}},
    ]


def seed_rfqs():
    t = today()
    return [
        {"id": 1, "title": "Solar Panel Servicing & Maintenance - Gauteng", "sector": "Renewable Energy & Solar",
         "scope": "Photovoltaic maintenance and solar power servicing for regional corporate facilities.",
         "budget": "R450,000", "region": "Gauteng", "max_bbbee": 2, "po_ref": "PO-994821", "closes": t + timedelta(days=14)},
        {"id": 2, "title": "Precision Irrigation Hardware Supply", "sector": "Precision Agriculture & IoT",
         "scope": "Automated precision farming systems and IoT irrigation hardware.",
         "budget": "R280,000", "region": "Gauteng", "max_bbbee": 3, "po_ref": "PO-771204", "closes": t + timedelta(days=21)},
    ]


def rfq_label(r):
    return f"#{r['id']}  {r['title']}"


def reset_demo():
    st.session_state.registry = seed_registry()
    st.session_state.rfqs = seed_rfqs()
    st.session_state.drafts = {}
    st.session_state.audit = []
    st.session_state.user_profile = None
    st.session_state.extracted_ai_data = None
    st.session_state.pop("sel_rfq", None)


if "registry" not in st.session_state:
    reset_demo()
for key, default in (("logged_in", False), ("portal_role", None), ("user_profile", None),
                     ("extracted_ai_data", None), ("drafts", {}), ("audit", [])):
    if key not in st.session_state:
        st.session_state[key] = default


def doc_summary(sme):
    out = {}
    for d, e in sme["docs"].items():
        days = (e - today()).days if e else None
        out[d] = ("Missing", 0) if e is None else (("Expired", days) if days < 0 else (("Expiring Soon", days) if days < 60 else ("Valid", days)))
    return out


# ---------------------------------------------------------------- ADDITIONS v4: RFQ PDF upload, SME RFQ breakdown, supplier analysis (rules + AI capability score)
import base64
import hashlib
import io

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

for _k, _d in (("rfq_parsed", None), ("rfq_nonce", 0), ("magic_sme", None), ("cap_cache", {})):
    if _k not in st.session_state:
        st.session_state[_k] = _d


def ask_claude_file(prompt, data, media_type="application/pdf", max_tokens=2500):
    """Like ask_claude, but sends a PDF or image to the model. Returns None when AI is off or fails,
    and records the reason in session state so the screen can show it."""
    st.session_state.pop("rfq_ai_error", None)
    if not data:
        return None
    out = ask_claude_blocks([_file_block(data, media_type), {"type": "text", "text": prompt}], max_tokens)
    if out is None:
        st.session_state["rfq_ai_error"] = st.session_state.get("ai_last_error") or "no answer from the AI"
    return out


def _json_from(text):
    if not text:
        return None
    try:
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group(0)) if m else None
    except Exception:
        return None


def vf_table(headers, rows):
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="vf-wrap"><table class="vf-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


# ---- RFQ PDF reading --------------------------------------------------------
def extract_pdf_text(data):
    if PdfReader is None or not data:
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages)[:20000]
    except Exception:
        return ""


_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun",
                                       "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _first_date(s):
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", s or "")
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})\b", s or "")
    if m and m.group(2)[:3].lower() in _MONTHS:
        try:
            return date(int(m.group(3)), _MONTHS[m.group(2)[:3].lower()], int(m.group(1)))
        except ValueError:
            pass
    return None


def _money(s):
    digits = re.sub(r"[^\d]", "", str(s or ""))
    return f"R{int(digits):,}" if digits else ""


def rules_parse_rfq(text):
    """Deterministic fallback reader. Works with no AI, on any PDF that has a text layer."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out = {}
    for l in lines:
        m = re.match(r"(?:subject|title|tender|rfq)\s*[:\-]\s*(.{8,140})", l, re.I)
        if m:
            out["title"] = m.group(1).strip()
            break
    if "title" not in out:
        for l in lines[:12]:
            if len(l.split()) >= 4 and not re.search(r"\b(pty|ltd|street|road|tel|email|www|box)\b", l, re.I):
                out["title"] = l[:140]
                break
    m = re.search(r"\bPO[-\s]?\d{4,}\b", text)
    if m:
        out["po_ref"] = m.group(0).replace(" ", "-")
    m = re.search(r"budget[^\n]{0,60}?R\s?(\d{1,3}(?:[ ,]\d{3})+|\d+)", text, re.I) or \
        re.search(r"\bR\s?(\d{1,3}(?:[ ,]\d{3})+)\b", text)
    if m:
        out["budget"] = _money(m.group(1))
    for l in lines:
        if re.search(r"clos", l, re.I) and _first_date(l):
            out["closes"] = _first_date(l)
            break
    m = re.search(r"b-?bbee[^\n]{0,80}?level\s*(\d)", text, re.I) or re.search(r"level\s*(\d)[^\n]{0,40}b-?bbee", text, re.I)
    if m and 1 <= int(m.group(1)) <= 8:
        out["max_bbbee"] = int(m.group(1))
    for p in SA_PROVINCES:
        if p.lower() in text.lower():
            out["region"] = p
            break
    m = re.search(r"scope of work[:\s]+(.+?)(?=\n\s*(?:key |mandatory |minimum )?requirements|\n\s*evaluation|\n\s*submission|\Z)",
                  text, re.I | re.S)
    scope = re.sub(r"\s+", " ", m.group(1)).strip()[:600] if m else ""
    out["scope"] = scope or re.sub(r"\s+", " ", text).strip()[:400]
    ev_at = next((i for i, l in enumerate(lines) if re.match(r"evaluation", l, re.I)), len(lines))
    reqs = [re.sub(r"^[\-\u2022\*\u2013\d\.\)\s]+", "", l) for l in lines[:ev_at] if re.match(r"^[\-\u2022\*\u2013]|^\d+[\.\)]\s", l)]
    if not reqs:
        reqs = [l for l in lines if re.search(r"\b(must|shall|required|mandatory)\b", l, re.I)]
    docs = [label for label, rx in (("CIPC registration", r"cipc"), ("SARS tax compliance letter", r"tax compliance|tax clearance"),
                                    ("B-BBEE certificate", r"b-?bbee (?:certificate|affidavit)")) if re.search(rx, text, re.I)]
    ev = []
    for i, l in enumerate(lines):
        if re.match(r"evaluation", l, re.I):
            ev = [re.sub(r"^[\-\u2022\*\u2013\s]+", "", x) for x in lines[i + 1:i + 4]]
            break
    first = re.split(r"(?<=[.!?])\s+", out["scope"])
    out["brief"] = {"summary": " ".join(first[:2])[:400], "key_requirements": reqs[:8],
                    "mandatory_documents": docs, "evaluation_criteria": ev, "key_dates": []}
    return out


def parse_rfq_pdf(file_name, data):
    """Returns title, scope, region, max_bbbee, budget, closes (date), po_ref, brief, _source, _warnings.
    AI reads the PDF itself (so scanned letterheads work); rules read the text layer as a fallback."""
    text = extract_pdf_text(data)
    base = rules_parse_rfq(text) if text.strip() else {}
    diag = []
    if PdfReader is None:
        diag.append("pypdf is not installed in this Python environment (run: python -m pip install pypdf)")
    elif not text.strip():
        diag.append("no text layer was found in the PDF (it may be a scan or image-only)")
    prompt = (
        "Read this South African corporate Request for Quotation (RFQ) and return ONLY a JSON object with keys: "
        "title (string), scope (string, 2 to 4 plain-English sentences), "
        f"region (one of: {', '.join(SA_PROVINCES)}, or null), max_bbbee_level (integer 1 to 8 or null), "
        "budget (string like R450,000, or null), closing_date (YYYY-MM-DD or null), po_ref (string or null), "
        "key_requirements (array of up to 8 short strings), mandatory_documents (array of short strings), "
        "evaluation_criteria (array of up to 5 short strings), key_dates (array of short strings such as "
        "'Site briefing: 3 Nov 2026'), summary (max 60 words, written for a small business owner: what is asked, "
        "what they must have, what to watch out for). Use null or [] when not stated. Never invent anything."
    )
    raw = ask_claude_file(prompt, data)
    ai = _json_from(raw)
    if raw and not ai:
        raw = ask_claude_file(prompt + " Keep every string short so the whole JSON object is complete.", data, max_tokens=4000)
        ai = _json_from(raw)
        if raw and not ai:
            diag.append("the AI replied, but the reply could not be read as JSON")
    if not raw and st.session_state.get("rfq_ai_error"):
        diag.append("AI read failed: " + st.session_state["rfq_ai_error"])
    out, source = dict(base), ("rules" if base else "none")
    brief = dict(base.get("brief") or {})
    if ai:
        source = "ai"
        for k_ai, k in (("title", "title"), ("scope", "scope"), ("po_ref", "po_ref")):
            if ai.get(k_ai):
                out[k] = str(ai[k_ai]).strip()
        if ai.get("region") in SA_PROVINCES:
            out["region"] = ai["region"]
        try:
            if ai.get("max_bbbee_level") and 1 <= int(ai["max_bbbee_level"]) <= 8:
                out["max_bbbee"] = int(ai["max_bbbee_level"])
        except Exception:
            pass
        if ai.get("budget"):
            out["budget"] = _money(ai["budget"]) or out.get("budget", "")
        if _first_date(str(ai.get("closing_date") or "")):
            out["closes"] = _first_date(str(ai["closing_date"]))
        for k in ("key_requirements", "mandatory_documents", "evaluation_criteria", "key_dates"):
            if isinstance(ai.get(k), list) and ai[k]:
                brief[k] = [str(x) for x in ai[k]][:8]
        if ai.get("summary"):
            brief["summary"] = str(ai["summary"]).strip()
    out["brief"] = brief
    warnings = []
    if text.strip():
        flat = re.sub(r"[\s,]", "", text)
        if out.get("budget") and re.sub(r"[^\d]", "", out["budget"]) not in flat:
            warnings.append("The budget was not found in the PDF text, check it against the document.")
        if out.get("po_ref") and out["po_ref"].replace("-", "").replace(" ", "") not in flat.replace("-", ""):
            warnings.append("The PO reference was not found in the PDF text, check it against the document.")
    out["_source"], out["_warnings"], out["_diag"] = source, warnings, diag
    return out


def default_brief(rfq):
    """Breakdown for RFQs that were typed in rather than uploaded. Built from the structured fields only."""
    return {"summary": rfq["scope"],
            "key_requirements": [f"Based in {rfq['region']}", f"B-BBEE Level {rfq['max_bbbee']} or better",
                                 f"Capability in {rfq['sector']}"],
            "mandatory_documents": ["CIPC registration", "SARS tax compliance letter", "B-BBEE certificate",
                                    "All valid on the closing date"],
            "evaluation_criteria": ["Compliance is checked first, by rules (pass or fail)"],
            "key_dates": [f"Closes {fmt(rfq['closes'])}"]}


def _brief_md(b):
    parts = []
    if b.get("summary"):
        parts.append(f"**In short.** {b['summary']}")
    for title, key in (("What you need", "key_requirements"), ("Documents to have ready", "mandatory_documents"),
                       ("How you will be assessed", "evaluation_criteria"), ("Key dates", "key_dates")):
        items = b.get(key) or []
        if items:
            parts.append(f"**{title}**\n" + "\n".join(f"- {i}" for i in items))
    return "\n\n".join(parts)


def render_rfq_breakdown(rfq):
    """SME view: the important details of an RFQ, plus the buyer's original PDF when there is one."""
    with st.expander("What you need to know about this RFQ"):
        brief = rfq.get("brief") or default_brief(rfq)
        src = {"ai": "Read by AI from the buyer's PDF.", "rules": "Extracted automatically from the buyer's PDF."}.get(
            rfq.get("brief_source"), "Summarised from the details the buyer posted.")
        st.caption(src + " The buyer's own document is the source of truth.")
        st.markdown(_brief_md(brief))
        if rfq.get("pdf_bytes"):
            st.download_button("Download the original RFQ (PDF)", rfq["pdf_bytes"], file_name=rfq.get("pdf_name", "rfq.pdf"),
                               mime="application/pdf", key=f"dl_rfq_sme_{rfq['id']}")


def render_rfq_source_panel(rfq):
    """Corporate view: shows the uploaded source PDF and the breakdown suppliers will see."""
    if not rfq.get("pdf_bytes"):
        return
    c1, c2 = st.columns([3, 1])
    c1.caption(f"Source document: {rfq.get('pdf_name', 'rfq.pdf')}. Suppliers see the breakdown below and can download this PDF.")
    c2.download_button("Download RFQ PDF", rfq["pdf_bytes"], file_name=rfq.get("pdf_name", "rfq.pdf"),
                       mime="application/pdf", key=f"dl_rfq_corp_{rfq['id']}")
    with st.expander("Preview: what suppliers see"):
        st.markdown(_brief_md(rfq.get("brief") or default_brief(rfq)))


def render_rfq_upload():
    """Corporate: upload the RFQ PDF, review what was read, then publish. A person confirms every field."""
    ss = st.session_state
    with st.expander("Upload an RFQ as a PDF (recommended, we read the letterhead document for you)"):
        st.caption("Upload the RFQ exactly as you issue it. The key details are read into the form below for you to confirm. "
                   "Suppliers get a plain-English breakdown and can download your original PDF.")
        up = st.file_uploader("RFQ document", type=["pdf"], key="rfq_pdf_up")
        if st.button("Read RFQ", key="rfq_read_btn", disabled=up is None):
            with st.spinner("Reading the RFQ..."):
                data = up.getvalue()
                parsed = parse_rfq_pdf(up.name, data)
                parsed["_file"], parsed["_bytes"] = up.name, data
                ss.rfq_parsed, ss.rfq_nonce = parsed, ss.rfq_nonce + 1
        p = ss.rfq_parsed
        if not p:
            return
        if p["_source"] == "ai":
            st.info("Read by AI. Review every field, correct anything wrong, then confirm.")
        elif p["_source"] == "rules":
            st.info("Read with the built-in reader (AI is off). Review every field, correct anything wrong, then confirm.")
        else:
            st.warning("The PDF could not be read automatically. It is attached, so complete the fields below by hand.")
        for w in p.get("_warnings", []):
            st.warning(w)
        for d in p.get("_diag", []):
            st.caption(f"Why the AI or the reader fell back: {d}")
        n, br = ss.rfq_nonce, p.get("brief") or {}
        with st.form("rfq_pdf_form"):
            title = st.text_input("Opportunity title", value=p.get("title") or "", key=f"rp_title_{n}")
            scope = st.text_area("Scope of work", value=p.get("scope") or "", key=f"rp_scope_{n}", height=130)
            c1, c2, c3, c4 = st.columns(4)
            reg = p.get("region") if p.get("region") in SA_PROVINCES else "Gauteng"
            region = c1.selectbox("Required province", SA_PROVINCES, index=SA_PROVINCES.index(reg), key=f"rp_reg_{n}")
            level = c2.selectbox("Max B-BBEE level", [1, 2, 3, 4, 5, 6, 7, 8], index=int(p.get("max_bbbee") or 2) - 1, key=f"rp_lvl_{n}")
            budget = c3.text_input("Budget (ZAR)", value=p.get("budget") or "", key=f"rp_bud_{n}")
            closes = c4.date_input("Closing date", value=p.get("closes") or today() + timedelta(days=14), key=f"rp_cl_{n}")
            po = st.text_input("Cost centre / PO reference (mandatory)", value=p.get("po_ref") or "", key=f"rp_po_{n}")
            reqs = st.text_area("Key requirements shown to suppliers (one per line)", value="\n".join(br.get("key_requirements") or []),
                                key=f"rp_req_{n}", height=110)
            if st.form_submit_button("Confirm and publish RFQ"):
                if not (title.strip() and scope.strip() and budget.strip() and po.strip()):
                    st.error("Title, scope, budget and PO reference are all required before an RFQ goes live.")
                else:
                    new_id = max(r["id"] for r in ss.rfqs) + 1
                    dates = list(br.get("key_dates") or [])
                    if not any("clos" in d.lower() for d in dates):
                        dates.append(f"Closes {fmt(closes)}")
                    rfq = {"id": new_id, "title": title.strip(), "sector": classify_sector(scope), "scope": scope.strip(),
                           "budget": _money(budget) or budget.strip(), "region": region, "max_bbbee": int(level),
                           "po_ref": po.strip(), "closes": closes, "pdf_name": p["_file"], "pdf_bytes": p["_bytes"],
                           "brief_source": p["_source"],
                           "brief": {"summary": br.get("summary") or scope.strip()[:300],
                                     "key_requirements": [x.strip() for x in reqs.splitlines() if x.strip()],
                                     "mandatory_documents": br.get("mandatory_documents") or [],
                                     "evaluation_criteria": br.get("evaluation_criteria") or [], "key_dates": dates}}
                    ss.rfqs.append(rfq)
                    ss["sel_rfq"] = rfq_label(rfq)
                    ss.rfq_parsed = None
                    st.success("RFQ published from your PDF. Suppliers can now read the breakdown and download the original.")


# ---- Supplier analysis: rule engine lights + AI capability score -------------
CAP_WEIGHTS = {"scope": 0.50, "experience": 0.30, "sector": 0.20}
CONCEPTS = {
    "solar and PV": r"\b(?:solar|photovoltaics?|pv|panels?|inverters?)\b",
    "maintenance and servicing": r"\b(?:maintenance|maintain\w*|servic\w*|repairs?|inspections?)\b",
    "electrical works": r"\b(?:electrical|wiring|switchgear|electricians?)\b",
    "precision agriculture and IoT": r"\b(?:irrigation|iot|sensors?|farming|precision|agricultur\w*|crops?)\b",
    "hardware supply and installation": r"\b(?:hardware|supply|install\w*|equipment)\b",
    "roofing and construction": r"\b(?:roof\w*|waterproof\w*|construction|building)\b",
    "ICT services": r"\b(?:software|network\w*|helpdesk|it support)\b",
}


def _hits(text, concepts):
    return [c for c in concepts if re.search(CONCEPTS[c], text or "", re.I)]


def keyword_capability(sme, rfq):
    concepts = _hits(f"{rfq['title']} {rfq['scope']}", list(CONCEPTS))
    n = max(len(concepts), 1)
    d, r = _hits(sme["description"], concepts), _hits(sme.get("references", ""), concepts)
    missing = [c for c in concepts if c not in set(d) | set(r)]
    analysis = (f"The profile covers {len(d)} of {len(concepts)} scope areas ({', '.join(d) or 'none'}) and the stated past work "
                f"evidences {len(r)} ({', '.join(r) or 'none'}). "
                + (f"Not evidenced: {', '.join(missing)}." if missing else "No scope area is missing from the supplier's stated work."))
    return round(90 * len(d) / n), round(90 * len(r) / n), analysis


def ai_capability(sme, rfq):
    out = _json_from(ask_claude(f"""You are a procurement analyst. Rate how well a supplier's STATED capability fits an RFQ. Use only the text below.
RFQ: {rfq['title']}. Scope: {rfq['scope']}
Supplier description: {sme['description']}
Supplier past work: {sme.get('references') or 'none stated'}
Rubric, 0 to 100.
scope_alignment: 90-100 same work; 70-89 closely related; 40-69 partly covers; 10-39 adjacent only; 0-9 unrelated.
experience_relevance: 90-100 named past work of the same type and setting; 70-89 similar work; 40-69 some related work; 10-39 weak; 0 none stated.
Return ONLY JSON: {{"scope_alignment": int, "experience_relevance": int, "analysis": "2 sentences: cite the supplier's own stated work that matches the scope, then the main gap or risk. Invent nothing."}}""",
                                max_tokens=300))
    try:
        s, e, a = int(out["scope_alignment"]), int(out["experience_relevance"]), str(out["analysis"]).strip()
        ok, _ = verify_draft(a, fact_sheet(sme, rfq))
        return (max(0, min(100, s)), max(0, min(100, e)), a) if (a and ok) else None
    except Exception:
        return None


def capability_score(sme, rfq):
    sig = hashlib.md5(f"{rfq['title']}|{rfq['scope']}|{sme['description']}|{sme.get('references','')}|{sme['sector']}".encode()).hexdigest()[:10]
    key = (rfq["id"], sme["name"], sig)
    cache = st.session_state.cap_cache
    if key in cache:
        return cache[key]
    same, related = sme["sector"] == rfq["sector"], sme["sector"] in RELATED.get(rfq["sector"], set())
    sector = 100 if same else 70 if related else 0
    ai = ai_capability(sme, rfq)
    why = ""
    if ai:
        scope, exp, analysis = ai
        method = "ai"
    else:
        scope, exp, analysis = keyword_capability(sme, rfq)
        method = "keywords"
        why = (ai_problem() if client is None else st.session_state.get("ai_last_error")
               or "the AI's analysis cited figures that are not in the profile or the RFQ")
    total = round(CAP_WEIGHTS["scope"] * scope + CAP_WEIGHTS["experience"] * exp + CAP_WEIGHTS["sector"] * sector)
    result = dict(total=total, scope=scope, exp=exp, sector=sector, analysis=analysis, method=method, why=why)
    if not (client is not None and st.session_state.get("ai_last_error")):
        cache[key] = result  # a failed AI call is not cached, so the next open retries it
    return result


def rule_light(r):
    if r["passed"] and not r["warning"]:
        return "green"
    return "amber" if (r["passed"] or r["fixable"]) else "red"


def _close_magic():
    st.session_state.magic_sme = None


def render_magic_panel(rfq, sme, rows, tier):
    """Drawn directly under the supplier card that opened it, then scrolled into view once."""
    ss = st.session_state
    st.markdown("<div id='vf-analysis-anchor'></div>", unsafe_allow_html=True)
    if ss.pop("magic_scroll", False):
        components.html("""<script>
            const go = () => { const el = window.parent.document.getElementById('vf-analysis-anchor');
                               if (el) el.scrollIntoView({behavior: 'smooth', block: 'start'}); };
            setTimeout(go, 150); setTimeout(go, 700);
            </script>""", height=0)
    with st.spinner("Scoring capability..."):
        cap = capability_score(sme, rfq)
    h1, h2 = st.columns([4, 1])
    h1.markdown(f"<h3 style='margin:0;'>{esc(sme['name'])}</h3><div class='vf-panel-sub'>{esc(sme['description'])} | Level {sme['bbbee_level']} | {esc(sme['region'])}</div>", unsafe_allow_html=True)
    h2.button("Close analysis", key="magic_close", on_click=_close_magic)
    left, right = st.columns([1.2, 1])
    with left:
        colour = {"READY": "green", "FIXABLE": "amber", "NOT_ELIGIBLE": "red"}[tier]
        verdict = {"READY": "Green: passes every rule", "FIXABLE": "Amber: one or more fixes away",
                   "NOT_ELIGIBLE": "Red: cannot be fixed for this RFQ"}[tier]
        st.markdown(f"<div class='vf-panel-title'>Compliance rule engine <span class='vf-panel-sub'>(decided in code, no AI)</span></div>"
                    f"<div class='vf-light'><span class='dot dot-{colour}'></span><b>{verdict}</b></div>", unsafe_allow_html=True)
        body = []
        for r in rows:
            result = (esc(r["warning"]) if r["passed"] and r["warning"] else "Pass" if r["passed"]
                      else esc(r["fix"]) if r["fixable"] else "Cannot be fixed for this RFQ")
            body.append([f"<span class='dot dot-{rule_light(r)}'></span>{esc(r['rule'])}", esc(r["requirement"]), esc(r["value"]), result])
        st.markdown(vf_table(["Rule", "Required", "Supplier has", "Result"], body), unsafe_allow_html=True)
    with right:
        st.markdown("<div class='vf-panel-title'>AI capability score <span class='vf-panel-sub'>(ranks capability, never eligibility)</span></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='vf-score'><div class='vf-score-num'>{cap['total']}%</div><div class='vf-score-lbl'>match to this RFQ's scope</div>"
                    f"<div class='vf-bar'><div style='width:{cap['total']}%'></div></div></div>"
                    f"<div class='vf-ai'><b>AI analysis.</b> {esc(cap['analysis'])}</div>", unsafe_allow_html=True)
        basis = ("AI rates scope alignment and past work against a fixed 0 to 100 rubric and writes the analysis."
                 if cap["method"] == "ai" else
                 f"The AI scorer could not be used ({cap.get('why') or 'unknown reason'}), so scope alignment and past work are keyword estimates: the share of the RFQ's scope areas found in the profile, capped at 90 because keywords cannot prove delivery.")
        st.markdown(f"<div class='vf-note'><b>How we got to {cap['total']}%.</b> It is a weighted average computed in code: "
                    f"<span class='vf-mono'>0.50 x {cap['scope']} (scope alignment) + 0.30 x {cap['exp']} (relevant past work) + 0.20 x {cap['sector']} (sector fit) = {cap['total']}</span>. "
                    f"{basis} Sector fit is fixed by code: same sector 100, related 70, other 0. "
                    "The score never overrides the rule engine, and a person approves every award.</div>", unsafe_allow_html=True)
        with st.expander("Show the working"):
            st.markdown(vf_table(["Part", "Weight", "Score", "Points", "Basis"], [
                ["Scope alignment", "50%", cap["scope"], f"{CAP_WEIGHTS['scope'] * cap['scope']:.1f}", "AI rubric" if cap["method"] == "ai" else "Keyword estimate"],
                ["Relevant past work", "30%", cap["exp"], f"{CAP_WEIGHTS['experience'] * cap['exp']:.1f}", "AI rubric" if cap["method"] == "ai" else "Keyword estimate"],
                ["Sector fit", "20%", cap["sector"], f"{CAP_WEIGHTS['sector'] * cap['sector']:.1f}", "Code (sector rule)"],
                ["<b>Total</b>", "100%", "", f"<b>{cap['total']}</b>", ""]]), unsafe_allow_html=True)
    if tier == "READY":
        reading = ("Strong candidate: compliant and capable." if cap["total"] >= 80
                   else "Compliant, but the evidence of capability is thinner. Ask for references before shortlisting.")
    else:
        what = "; ".join(r["fix"] if r["fixable"] else f"{r['rule']} ({r['value']})" for r in rows if not r["passed"])
        reading = (f"Capable, but not awardable today: {what}." if cap["total"] >= 80 else f"Lower priority. Not awardable today: {what}.")
    st.markdown(f"<div class='vf-note'><b>Reading both together.</b> {esc(reading)}</div>", unsafe_allow_html=True)
    st.markdown("---")

# ---------------------------------------------------------------- LOGIN
if not st.session_state.logged_in:
    _, col2, _ = st.columns([1, 1.4, 1])
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.session_state.portal_role is None:
            st.markdown("""<div class="css-card" style="text-align: center;">
                <h1 style="color: #0F4C81; margin-bottom: 5px;">🇿🇦 VulaFlow</h1>
                <p style="color: #64748B; margin-bottom: 5px;">AI procurement co-pilot for SMEs and corporate buyers.</p>
                <p style="color: #64748B; margin-bottom: 25px;">Select your gateway.</p></div>""", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if c1.button("I am an SME Vendor"):
                st.session_state.portal_role = "SME"
                st.rerun()
            if c2.button("I am a Corporate Buyer"):
                st.session_state.portal_role = "Corporate"
                st.rerun()
        else:
            role_label = "SME Vendor Portal" if st.session_state.portal_role == "SME" else "Corporate Buyer Portal"
            st.markdown(f"""<div class="css-card" style="text-align: center;">
                <h2 style="color: #0F4C81; margin-bottom: 0;">{role_label}</h2>
                <p style="color: #64748B; font-size: 0.9em;">Demo sign-in (no real authentication)</p></div>""", unsafe_allow_html=True)
            with st.form("login_form"):
                st.text_input("Work Email Address", value="vendor@sizwesolar.co.za" if st.session_state.portal_role == "SME" else "procurement@corporate.co.za")
                st.text_input("Password", type="password", value="password123")
                if st.form_submit_button("Sign In"):
                    st.session_state.logged_in = True
                    st.rerun()
            if st.button("← Switch Portal Type"):
                st.session_state.portal_role = None
                st.rerun()

# ---------------------------------------------------------------- APP
else:
    role = st.session_state.portal_role
    st.sidebar.markdown("<h3 style='color: #0F4C81; margin-bottom: 0;'>VulaFlow</h3>", unsafe_allow_html=True)
    st.sidebar.caption("Corporate Portal" if role == "Corporate" else "SME Portal")
    st.sidebar.markdown("---")
    if role == "SME":
        menu = st.sidebar.radio("Navigation", ["My Profile", "Opportunities & Proposals", "Log Out"])
    else:
        menu = st.sidebar.radio("Navigation", ["Post RFQ & Shortlist", "Supplier Directory", "Log Out"])
    st.sidebar.markdown("---")

    if menu == "Log Out":
        st.session_state.logged_in = False
        st.session_state.portal_role = None
        st.session_state.user_profile = None
        st.session_state.extracted_ai_data = None
        st.rerun()

    # ============================== SME
    if role == "SME":
        if menu == "My Profile":
            if st.session_state.user_profile is None:
                st.markdown("<h2 style='color: #1E293B;'>Create Your SME Vendor Profile</h2>", unsafe_allow_html=True)
                st.caption("Upload documents, confirm the extracted details, and see which tenders you qualify for.")

                st.markdown("<div class='css-card'>", unsafe_allow_html=True)
                st.markdown("#### 📄 Document Upload")
                st.caption("Upload your CIPC, tax and B-BBEE documents (PDF, PNG, JPG or TXT). Claude reads them, including scans. "
                           "Every extracted field must be confirmed by you below.")
                up_files = st.file_uploader("Drop CIPC / Tax / B-BBEE documents (select several at once if you like)",
                                            type=["pdf", "png", "jpg", "jpeg", "txt"], accept_multiple_files=True)
                if st.button("Extract details", disabled=not up_files):
                    with st.spinner("Reading your documents..."):
                        _data, _err = parse_documents_with_ai([(f.name, f.getvalue()) for f in up_files])
                    st.session_state.extracted_ai_data = _data or None
                    st.session_state.extract_error = _err
                if st.session_state.get("extract_error"):
                    st.error("Could not read the documents: " + st.session_state["extract_error"])

                ai = st.session_state.extracted_ai_data or {}
                if ai:
                    st.info("Extraction complete. Review every field, correct anything wrong, then confirm."
                            + (f" Found: {', '.join(map(str, ai.get('documents_found') or []))}." if ai.get("documents_found") else ""))
                    if ai.get("notes"):
                        st.caption(f"Note from the reader: {ai['notes']}")
                reg = ai.get("region") if ai.get("region") in SA_PROVINCES else "Gauteng"
                with st.form("profile_form"):
                    name = st.text_input("Business name", value=ai.get("business_name") or "")
                    desc = st.text_area("What your business does", value=ai.get("description") or "")
                    c0, c1 = st.columns(2)
                    region = c0.selectbox("Province", SA_PROVINCES, index=SA_PROVINCES.index(reg))
                    try:
                        _lvl = min(8, max(1, int(ai.get("bbbee_level") or 2)))
                    except Exception:
                        _lvl = 2
                    level = c1.selectbox("B-BBEE level (from your certificate)", [1, 2, 3, 4, 5, 6, 7, 8], index=_lvl - 1)
                    d1, d2, d3 = st.columns(3)
                    lim = dict(min_value=date(2015, 1, 1), max_value=date(2035, 12, 31))
                    _clamp = lambda d: min(max(d, lim["min_value"]), lim["max_value"])
                    cipc = d1.date_input("CIPC expiry", value=_clamp(parse_date(ai.get("cipc"), today() + timedelta(days=365))), **lim)
                    tax = d2.date_input("Tax letter expiry", value=_clamp(parse_date(ai.get("tax"), today() + timedelta(days=180))), **lim)
                    bb = d3.date_input("B-BBEE certificate expiry", value=_clamp(parse_date(ai.get("bbbee"), today() + timedelta(days=90))), **lim)
                    refs = st.text_area("Past work and references", value="")
                    if st.form_submit_button("Confirm & Save Profile"):
                        if not name.strip() or not desc.strip():
                            st.error("Business name and description are required.")
                        else:
                            profile = {"name": name.strip(), "description": desc.strip(), "sector": classify_sector(desc),
                                       "region": region, "bbbee_level": int(level), "references": refs.strip(),
                                       "docs": {"CIPC": cipc, "Tax": tax, "B-BBEE": bb}}
                            st.session_state.registry = [s for s in st.session_state.registry if s["name"] != profile["name"]] + [profile]
                            st.session_state.user_profile = profile
                            st.session_state.extracted_ai_data = None
                            st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                p = st.session_state.user_profile
                summary = doc_summary(p)
                ok = all(s[0] in ("Valid", "Expiring Soon") for s in summary.values())
                badge = '<span class="badge badge-ready">DOCUMENTS CURRENT</span>' if ok else '<span class="badge badge-no">ACTION REQUIRED</span>'
                st.markdown(f"""<div class="css-card">
                    <h1 style="color: #0F4C81; margin-top: 0; margin-bottom: 5px; display: inline-block;">{esc(p['name'])}</h1> {badge}
                    <br><br><div class="sector-badge">🏷️ {esc(p['sector'])} &nbsp;|&nbsp; 📍 {esc(p['region'])} &nbsp;|&nbsp; B-BBEE Level {p['bbbee_level']}</div>
                    <p style="color: #475569; font-size: 1.05em;">{esc(p['description'])}</p></div>""", unsafe_allow_html=True)
                st.markdown("<h3 style='color: #1E293B;'>Document status</h3>", unsafe_allow_html=True)
                for doc, (status, days) in summary.items():
                    if status == "Valid":
                        st.markdown(f"<div class='doc-valid'>✅ <b>{doc}</b>: valid ({days} days remaining)</div>", unsafe_allow_html=True)
                    elif status == "Expiring Soon":
                        st.markdown(f"<div class='doc-warning'>⏳ <b>{doc}</b>: expires in {days} days. Renew soon.</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='doc-error'>❌ <b>{doc}</b>: {status.lower()}. Renew to qualify for tenders.</div>", unsafe_allow_html=True)
                st.caption("Your documents decide which tenders you qualify for. See Opportunities & Proposals.")

        else:  # Opportunities & Proposals
            st.markdown("<h2 style='color: #1E293B;'>🎯 Your Opportunities</h2>", unsafe_allow_html=True)
            st.write("Every tender is checked against your verified profile. You see what qualifies now, and exactly what to fix for the rest.")
            p = st.session_state.user_profile
            if p is None:
                st.warning("Create or load your profile first (My Profile).")
            else:
                results = sorted(((r, rows, tier_of(rows)) for r in st.session_state.rfqs for rows in [evaluate(p, r)]),
                                 key=lambda t: TIER_ORDER[t[2]])
                for rfq, rows, tier in results:
                    failed = [r for r in rows if not r["passed"]]
                    warns = [r["warning"] for r in rows if r["warning"]]
                    st.markdown(f"""<div class="css-card" style="border-left: 4px solid {TIER_COLOUR[tier]};">
                        <h3 style="color: #0F4C81; margin-top: 0;">{esc(rfq['title'])} {tier_badge(tier, rows)}</h3>
                        <p style="color: #64748B; margin-bottom: 8px;">{esc(rfq['scope'])}</p>
                        <p style="font-size: 0.9em; color: #475569;">Budget <b>{esc(rfq['budget'])}</b> &nbsp;|&nbsp; Ref <b>{esc(rfq['po_ref'])}</b>
                        &nbsp;|&nbsp; Closes <b>{fmt(rfq['closes'])}</b> &nbsp;|&nbsp; {esc(rfq['region'])}</p>""", unsafe_allow_html=True)
                    if tier == "FIXABLE":
                        for r in failed:
                            st.markdown(f"<div class='fixbox'>🔧 <b>{esc(r['fix'])}</b> ({esc(r['rule'])}: {esc(r['value'])}). Fix this and you qualify.</div>", unsafe_allow_html=True)
                    if tier == "NOT_ELIGIBLE":
                        for r in failed:
                            st.markdown(f"<div class='whybox'>Not eligible: {esc(r['rule'])} requires {esc(r['requirement'])}, you have {esc(r['value'])}.</div>", unsafe_allow_html=True)
                    for w in warns:
                        st.markdown(f"<div class='whybox'>⏳ {esc(w)}</div>", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)
                    render_rfq_breakdown(rfq)

                    if tier == "FIXABLE":
                        for r in failed:
                            doc = {"cipc": "CIPC", "tax": "Tax", "bbbee_cert": "B-BBEE"}.get(r["rule_id"])
                            if doc and st.button(f"Simulate: upload renewed {DOC_LABEL[doc]}", key=f"fix_{rfq['id']}_{doc}"):
                                p["docs"][doc] = today() + timedelta(days=365)
                                st.rerun()
                    if tier == "READY":
                        key = (rfq["id"], p["name"])
                        if st.button("Draft my proposal", key=f"draft_{rfq['id']}"):
                            with st.spinner("Drafting from your verified profile..."):
                                st.session_state.drafts[key] = generate_proposal(p, rfq)
                        if key in st.session_state.drafts:
                            text, source, note = st.session_state.drafts[key]
                            st.caption(f"{source}. {note}. Edit freely, you own what you send.")
                            edited = st.text_area("Proposal", value=text, height=320, key=f"edit_{rfq['id']}")
                            ok, bad = verify_draft(edited, fact_sheet(p, rfq))
                            if not ok:
                                st.warning(f"These numbers are not in your profile or the RFQ, please check them: {', '.join(bad)}")
                            if st.button("Approve proposal", key=f"approve_{rfq['id']}"):
                                st.session_state.audit.append({"time": datetime.now().strftime("%H:%M:%S"), "supplier": p["name"],
                                                               "rfq": rfq["title"], "action": f"Proposal approved by SME ({source})"})
                                st.success("Approved and recorded. In this demo nothing is transmitted; the next phase sends it with your compliance packet.")
                if st.session_state.audit:
                    with st.expander("Approval log"):
                        st.dataframe(pd.DataFrame(st.session_state.audit), hide_index=True)

    # ============================== CORPORATE
    else:
        if menu == "Post RFQ & Shortlist":
            st.markdown("<h2 style='color: #1E293B;'>📝 Post an RFQ and get a qualified shortlist</h2>", unsafe_allow_html=True)
            st.write("Rules check every supplier against your requirements. You see who is ready now, who is one fix away, and why the rest were excluded.")
            render_rfq_upload()
            with st.expander("Post a new RFQ", expanded=False):
                with st.form("rfq_post_form"):
                    title = st.text_input("Opportunity title")
                    scope = st.text_area("Scope of work")
                    c1, c2, c3, c4 = st.columns(4)
                    region = c1.selectbox("Required province", SA_PROVINCES)
                    max_level = c2.selectbox("Max B-BBEE level", [1, 2, 3, 4, 5, 6, 7, 8], index=1)
                    budget = c3.text_input("Budget (ZAR)", placeholder="R450,000")
                    closes = c4.date_input("Closing date", value=today() + timedelta(days=14))
                    po = st.text_input("Cost centre / PO reference (mandatory)")
                    if st.form_submit_button("Publish & run qualification"):
                        if not (title.strip() and scope.strip() and budget.strip() and po.strip()):
                            st.error("Title, scope, budget and PO reference are all required before an RFQ goes live.")
                        else:
                            new_id = max(r["id"] for r in st.session_state.rfqs) + 1
                            st.session_state.rfqs.append({"id": new_id, "title": title.strip(), "sector": classify_sector(scope),
                                                          "scope": scope.strip(), "budget": budget.strip(), "region": region,
                                                          "max_bbbee": int(max_level), "po_ref": po.strip(), "closes": closes})
                            st.session_state["sel_rfq"] = rfq_label(st.session_state.rfqs[-1])

            labels = {rfq_label(r): r for r in st.session_state.rfqs}
            if st.session_state.get("sel_rfq") not in labels:
                st.session_state["sel_rfq"] = next(iter(labels))
            rfq = labels[st.selectbox("RFQ", list(labels), key="sel_rfq")]
            classified = classify_all(rfq, st.session_state.registry)
            counts = {t: sum(1 for c in classified if c[2] == t) for t in TIER_ORDER}

            st.markdown(f"<div class='sector-badge'>{esc(rfq['sector'])} &nbsp;|&nbsp; {esc(rfq['region'])} &nbsp;|&nbsp; Level {rfq['max_bbbee']} or better &nbsp;|&nbsp; Closes {fmt(rfq['closes'])}</div>", unsafe_allow_html=True)
            render_rfq_source_panel(rfq)
            m1, m2, m3 = st.columns(3)
            m1.metric("Ready now", counts["READY"])
            m2.metric("One or more fixes away", counts["FIXABLE"])
            m3.metric("Not eligible", counts["NOT_ELIGIBLE"])

            if counts["READY"] < 2:
                fix_docs = {}
                for sme, rows, t in classified:
                    if t == "FIXABLE":
                        for r in rows:
                            if not r["passed"]:
                                fix_docs[r["rule"]] = fix_docs.get(r["rule"], 0) + 1
                tail = ""
                if fix_docs:
                    top = max(fix_docs, key=fix_docs.get)
                    tail = f" {counts['FIXABLE']} more would qualify after a fix, most often: {top.lower()} ({fix_docs[top]})."
                st.warning(f"Thin supply: only {counts['READY']} ready supplier(s) for this RFQ.{tail} "
                           "This is where supplier development spend would unlock the most supply.")

            for sme, rows, tier in classified:
                failed = [r for r in rows if not r["passed"]]
                warns = [r["warning"] for r in rows if r["warning"]]
                st.markdown(f"""<div class="css-card" style="padding: 16px; border-left: 4px solid {TIER_COLOUR[tier]};">
                    <h4 style="color: #0F4C81; margin: 0;">{esc(sme['name'])} {tier_badge(tier, rows)}</h4>
                    <p style="color: #64748B; margin: 5px 0;">{esc(sme['description'])} | Level {sme['bbbee_level']} | {esc(sme['region'])}</p>""", unsafe_allow_html=True)
                if tier == "READY":
                    st.markdown("<div class='whybox'>Passes every rule. Source documents are listed in the matrix below.</div>", unsafe_allow_html=True)
                for r in failed:
                    extra = f" Fix: {esc(r['fix'])}." if r["fixable"] else " Cannot be fixed for this RFQ."
                    st.markdown(f"<div class='whybox'>❌ {esc(r['rule'])}: needs {esc(r['requirement'])}, has {esc(r['value'])}.{extra}</div>", unsafe_allow_html=True)
                for w in warns:
                    st.markdown(f"<div class='whybox'>⏳ {esc(w)}</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
                if st.button("Open analysis", key=f"magic_{rfq['id']}_{sme['name']}"):
                    st.session_state.magic_sme = sme["name"]
                    st.session_state.magic_rfq = rfq["id"]
                    st.session_state.magic_scroll = True
                if st.session_state.magic_sme == sme["name"] and st.session_state.get("magic_rfq") == rfq["id"]:
                    render_magic_panel(rfq, sme, rows, tier)

            st.markdown("### Compliance evaluation matrix")
            df = matrix_df(rfq, [c[0] for c in classified])
            st.dataframe(df, hide_index=True)
            st.download_button("Download matrix (CSV)", df.to_csv(index=False).encode("utf-8"),
                               file_name=f"compliance_matrix_rfq_{rfq['id']}.csv", mime="text/csv")
            st.caption("Eligibility is decided by these rules in code. AI is only used to read documents and draft text, and a person approves.")

        else:  # Supplier directory
            st.markdown("<h2 style='color: #1E293B;'>🏢 Supplier Directory</h2>", unsafe_allow_html=True)
            for sme in st.session_state.registry:
                summary = doc_summary(sme)
                ok = all(s[0] in ("Valid", "Expiring Soon") for s in summary.values())
                badge = '<span class="badge badge-ready">DOCUMENTS CURRENT</span>' if ok else '<span class="badge badge-no">DOCUMENT EXPIRED</span>'
                st.markdown(f"""<div class="css-card"><h3 style="color: #0F4C81; margin-top: 0;">{esc(sme['name'])} {badge}</h3>
                    <div class="sector-badge">{esc(sme['sector'])}</div><p style="color: #475569;">{esc(sme['description'])}</p>
                    <p style="font-size: 0.9em; color: #64748B;"><b>Location:</b> {esc(sme['region'])} &nbsp;|&nbsp; <b>B-BBEE:</b> Level {sme['bbbee_level']}</p></div>""", unsafe_allow_html=True)