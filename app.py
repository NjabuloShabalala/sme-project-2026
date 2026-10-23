import html
import json
import os
import re
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
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

esc = html.escape

# ---------------------------------------------------------------- AI (optional, always has a fallback)
AI_ENABLED = os.getenv("VULA_AI", "on").lower() != "off"
MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")


@st.cache_resource
def get_client():
    if not AI_ENABLED or anthropic is None or not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        return anthropic.Anthropic()
    except Exception:
        return None


client = get_client()


def ask_claude(prompt, max_tokens=700):
    """Returns text, or None when AI is off or the call fails. Callers must have a fallback."""
    if client is None:
        return None
    try:
        res = client.messages.create(model=MODEL, max_tokens=max_tokens,
                                     messages=[{"role": "user", "content": prompt}])
        return res.content[0].text.strip()
    except Exception:
        return None


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


def parse_document_with_ai(file_name, file_text=None):
    """DEMO extraction. Reads the text of a .txt upload if given, else only the file name.
    Production path: OCR, then structured extraction with source quotes, then code validation."""
    source = file_text if file_text else file_name
    out = ask_claude(f"""Extract business details from this South African compliance document text or filename:
"{source}"
Return ONLY a JSON object with keys business_name, description, region (one of {', '.join(SA_PROVINCES)}),
cipc, tax, bbbee (expiry dates as YYYY-MM-DD). Use null for anything not stated.""", max_tokens=300)
    if out:
        try:
            out = out.strip()
            out = re.sub(r"^```(?:json)?|```$", "", out).strip()
            return json.loads(out)
        except Exception:
            pass
    return {"business_name": "Demo Supplier (Pty) Ltd",
            "description": "Solar panel installation and photovoltaic maintenance for commercial sites.",
            "region": "Gauteng",
            "cipc": str(today() + timedelta(days=200)),
            "tax": str(today() + timedelta(days=120)),
            "bbbee": str(today() + timedelta(days=90))}


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
    st.sidebar.caption(f"Active role: {role}")
    st.sidebar.caption("AI: " + (f"on ({MODEL})" if client else "off, using templates and rules"))
    st.sidebar.markdown("---")
    if role == "SME":
        menu = st.sidebar.radio("Navigation", ["My Profile", "Opportunities & Proposals", "Log Out"])
    else:
        menu = st.sidebar.radio("Navigation", ["Post RFQ & Shortlist", "Supplier Directory", "Log Out"])
    st.sidebar.markdown("---")
    if st.sidebar.button("Reset demo data"):
        reset_demo()
        st.rerun()

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
                a, b = st.columns([3, 1])
                with a:
                    st.markdown("<h2 style='color: #1E293B;'>Create Your SME Vendor Profile</h2>", unsafe_allow_html=True)
                    st.caption("Upload documents, confirm the extracted details, and see which tenders you qualify for.")
                with b:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("⚡ Load Demo Profile"):
                        st.session_state.user_profile = next(s for s in st.session_state.registry if s["name"].startswith("Sizwe"))
                        st.rerun()

                st.markdown("<div class='css-card'>", unsafe_allow_html=True)
                st.markdown("#### 📄 Document Upload (demo extraction)")
                st.caption("Demo mode reads the text of a .txt upload, or just the file name. "
                           "Every extracted field must be confirmed by you below.")
                up = st.file_uploader("Drop CIPC / Tax / B-BBEE document", type=["pdf", "png", "jpg", "txt"])
                if st.button("Extract details"):
                    text = None
                    if up is not None and up.name.lower().endswith(".txt"):
                        text = up.getvalue().decode("utf-8", errors="ignore")[:4000]
                    with st.spinner("Extracting..."):
                        st.session_state.extracted_ai_data = parse_document_with_ai(up.name if up else "demo_compliance.pdf", text)

                ai = st.session_state.extracted_ai_data or {}
                if ai:
                    st.info("Extraction complete. Review every field, correct anything wrong, then confirm.")
                reg = ai.get("region") if ai.get("region") in SA_PROVINCES else "Gauteng"
                with st.form("profile_form"):
                    name = st.text_input("Business name", value=ai.get("business_name") or "")
                    desc = st.text_area("What your business does", value=ai.get("description") or "")
                    c0, c1 = st.columns(2)
                    region = c0.selectbox("Province", SA_PROVINCES, index=SA_PROVINCES.index(reg))
                    level = c1.selectbox("B-BBEE level (from your certificate)", [1, 2, 3, 4, 5, 6, 7, 8], index=1)
                    d1, d2, d3 = st.columns(3)
                    lim = dict(min_value=date(2015, 1, 1), max_value=date(2035, 12, 31))
                    cipc = d1.date_input("CIPC expiry", value=parse_date(ai.get("cipc"), today() + timedelta(days=365)), **lim)
                    tax = d2.date_input("Tax letter expiry", value=parse_date(ai.get("tax"), today() + timedelta(days=180)), **lim)
                    bb = d3.date_input("B-BBEE certificate expiry", value=parse_date(ai.get("bbbee"), today() + timedelta(days=90)), **lim)
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