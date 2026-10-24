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

st.set_page_config(page_title="VulaFlow | Procurement Gateway", page_icon="🇿🇦", layout="wide")

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

# ---------------------------------------------------------------- AI SETUP
AI_ENABLED = os.getenv("VULA_AI", "on").lower() != "off"
MODEL = os.getenv("CLAUDE_MODEL", "claude-3-haiku-20240307")

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
    if client is None: return None
    try:
        res = client.messages.create(model=MODEL, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}])
        return res.content[0].text.strip()
    except Exception:
        return None

# ---------------------------------------------------------------- DOMAIN DATA
SA_PROVINCES = ["Gauteng", "Western Cape", "KwaZulu-Natal", "Eastern Cape", "Free State", "Limpopo", "Mpumalanga", "North West", "Northern Cape"]

SECTOR_KEYWORDS = {
    "Renewable Energy & Solar": ["solar", "photovoltaic", "pv ", "inverter", "renewable"],
    "Electrical Engineering": ["electrical", "wiring", "electrician", "switchgear"],
    "Precision Agriculture & IoT": ["farming", "irrigation", "crop", "agricultur", "agri"],
    "Construction & Roofing": ["roof", "waterproof", "construction", "building"],
    "ICT Services": ["software", "it support", "network", "helpdesk"],
}
RELATED = {"Renewable Energy & Solar": {"Electrical Engineering"}, "Electrical Engineering": {"Renewable Energy & Solar"}}
DOC_LABEL = {"CIPC": "CIPC registration", "Tax": "tax compliance letter", "B-BBEE": "B-BBEE certificate"}
DOC_SOURCE = {"CIPC": "CIPC registration document", "Tax": "SARS tax compliance letter", "B-BBEE": "B-BBEE certificate"}
WARN_DAYS = 30

HISTORICAL_BID_DATA = {
    "Renewable Energy & Solar": {
        "winning_patterns": ["Itemised maintenance schedule with response-time commitments", "Quantified past performance (kWp serviced, uptime achieved)", "Price 5 to 12 percent below budget with fixed call-out rates"],
        "rejection_patterns": ["Generic scope with no site inspection plan", "Price more than 10 percent above budget", "No quantified past performance", "Compliance documents expired or expiring soon after closing"],
        "win_discount_range": (5, 12), "timeline_range": (10, 21), "sample_size": 148
    },
    "Precision Agriculture & IoT": {
        "winning_patterns": ["Pilot or proof of concept offered on one site first", "Hardware warranty plus local support commitment", "Quantified water or yield savings from past deployments"],
        "rejection_patterns": ["Hardware supplied without installation or training", "Import lead times not addressed", "No local service presence in the province"],
        "win_discount_range": (4, 10), "timeline_range": (21, 45), "sample_size": 92
    }
}
DEFAULT_HISTORY = {"winning_patterns": ["Clear scope, fixed price, quantified past performance"], "rejection_patterns": ["Vague scope, no references, price far above budget"], "win_discount_range": (3, 10), "timeline_range": (14, 45), "sample_size": 60}

def today(): return date.today()
def fmt(d): return d.strftime("%d %b %Y")
def money(n): return f"R{n:,.0f}"
def parse_date(s, default):
    try: return datetime.strptime(str(s), "%Y-%m-%d").date()
    except Exception: return default

def classify_sector(text):
    low = (text or "").lower()
    for sector, words in SECTOR_KEYWORDS.items():
        if any(w in low for w in words): return sector
    out = ask_claude(f'Identify the primary South African industry sector of this business in 2 to 4 words. Return ONLY the sector name.\n\n"{text}"', max_tokens=25)
    return out.title() if out else "General Enterprise Services"

# ---------------------------------------------------------------- STANDARDIZATION ENGINE
def regex_standardize(raw):
    price, prices = None, []
    for m in re.finditer(r"R\s?(\d{1,3}(?:[\s,]\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)", raw):
        try: prices.append(float(re.sub(r"[\s,]", "", m.group(1))))
        except ValueError: pass
    if prices: price = max([p for p in prices if p >= 1000])
    days, m = None, re.search(r"(\d+)\s*(?:calendar\s+|working\s+)?(day|week)s?", raw, re.I)
    if m:
        n = int(m.group(1)); days = n * 7 if m.group(2).lower() == "week" else n
    summary = re.sub(r"\s+", " ", raw).strip()[:170]
    return {"price": price, "timeline_days": days, "summary": summary, "references": ""}

def verify_extraction(raw, price, days):
    flat = re.sub(r"[\s,]", "", raw)
    price_ok = price is not None and str(int(round(price))) in flat
    nums = {int(n) for n in re.findall(r"\d+", raw)}
    days_ok = days is None or days in nums or (days % 7 == 0 and days // 7 in nums)
    return bool(price_ok and days_ok)

def standardize_raw_bid(raw):
    prompt = f"""Extract a standardized bid from this supplier submission. Return ONLY a JSON object with keys: 
    price_zar (number), timeline_days (number; convert weeks to days), summary (max 40 words, only facts), references (or null). 
    Use null when not stated. Do not infer or invent.\n\nSUBMISSION:\n{raw[:6000]}"""
    parsed = None
    if client:
        try:
            out = ask_claude(prompt, 300)
            if out:
                out = re.sub(r"^```(?:json)?|```$", "", out.strip(), flags=re.MULTILINE).strip()
                data = json.loads(out)
                parsed = {"price": float(data["price_zar"]) if data.get("price_zar") is not None else None,
                          "timeline_days": int(data["timeline_days"]) if data.get("timeline_days") is not None else None,
                          "summary": str(data.get("summary") or "")[:300], "references": str(data.get("references") or "")}
        except Exception: pass
    engine = "AI"
    if parsed is None or parsed["price"] is None:
        parsed = regex_standardize(raw)
        engine = "Rules"
    parsed["engine"] = engine
    parsed["verified"] = verify_extraction(raw, parsed["price"], parsed["timeline_days"])
    return parsed

# ---------------------------------------------------------------- RULE ENGINE
def evaluate(sme, rfq):
    rows, closing = [], rfq["closes"]
    def add(rule_id, rule, requirement, value, source, passed, fixable, fix="", warning=""):
        rows.append(dict(rule_id=rule_id, rule=rule, requirement=requirement, value=value, source=source, passed=passed, fixable=fixable, fix=fix, warning=warning))
    same = sme["sector"] == rfq["sector"]
    related = sme["sector"] in RELATED.get(rfq["sector"], set())
    add("sector", "Service category", f"{rfq['sector']} (or related)", sme["sector"] + (" (related)" if related and not same else ""), "Business profile", same or related, False)
    add("region", "Province served", rfq["region"], sme["region"], "Business profile", sme["region"] == rfq["region"], False)
    add("bbbee_level", "B-BBEE level", f"Level {rfq['max_bbbee']} or better", f"Level {sme['bbbee_level']}", DOC_SOURCE["B-BBEE"], sme["bbbee_level"] <= rfq["max_bbbee"], False)
    for doc, rule_id in (("CIPC", "cipc"), ("Tax", "tax"), ("B-BBEE", "bbbee_cert")):
        exp, label, need = sme["docs"].get(doc), DOC_LABEL[doc], f"Valid on closing date ({fmt(closing)})"
        if exp is None: add(rule_id, f"{doc} document", need, "Missing", "No document on file", False, True, f"Upload your {label}")
        elif exp < closing: add(rule_id, f"{doc} document", need, f"Expired {fmt(exp)}", DOC_SOURCE[doc], False, True, f"Upload a renewed {label}")
        else:
            gap = (exp - closing).days
            warn = f"Expires {gap} days after closing" if gap < WARN_DAYS else ""
            add(rule_id, f"{doc} document", need, f"Valid to {fmt(exp)}", DOC_SOURCE[doc], True, True, warning=warn)
    return rows

def tier_of(rows):
    failed = [r for r in rows if not r["passed"]]
    if not failed: return "READY"
    if all(r["fixable"] for r in failed): return "FIXABLE"
    return "NOT_ELIGIBLE"

def tier_badge(tier, rows):
    if tier == "READY": return '<span class="badge badge-ready">READY NOW</span>'
    if tier == "FIXABLE": return f'<span class="badge badge-fix">{sum(1 for r in rows if not r["passed"])} FIXES AWAY</span>'
    return '<span class="badge badge-no">NOT ELIGIBLE</span>'

TIER_COLOUR = {"READY": "#10B981", "FIXABLE": "#F59E0B", "NOT_ELIGIBLE": "#EF4444"}
TIER_ORDER = {"READY": 0, "FIXABLE": 1, "NOT_ELIGIBLE": 2}

def classify_all(rfq, smes):
    out = []
    for sme in smes:
        rows = evaluate(sme, rfq)
        out.append((sme, rows, tier_of(rows)))
    out.sort(key=lambda t: (TIER_ORDER[t[2]], t[0]["bbbee_level"], t[0]["name"]))
    return out

# ---------------------------------------------------------------- BID INTELLIGENCE
def price_position(bid, rfq, hist):
    below = (rfq["budget"] - bid["price"]) / rfq["budget"] * 100
    lo, hi = hist["win_discount_range"]
    tlo, thi = hist["timeline_range"]
    return {"below_pct": below, "price_in_range": lo <= below <= hi, "price_range": (lo, hi), "timeline_in_range": tlo <= bid["timeline_days"] <= thi, "timeline_range": (tlo, thi)}

def benchmark_bid_against_history(sme, rfq, bid):
    hist = HISTORICAL_BID_DATA.get(rfq["sector"], DEFAULT_HISTORY)
    pos = price_position(bid, rfq, hist)
    prompt = f"""You are a Corporate Procurement AI Analyst. Evaluate this bid against historical patterns.
    RFQ: {rfq['title']} - {rfq['scope']}
    BUDGET: {money(rfq['budget'])} | BID PRICE: {money(bid['price'])} ({pos['below_pct']:.1f}% {'below' if pos['below_pct'] >= 0 else 'above'} budget) | TIMELINE: {bid['timeline_days']} days
    SUPPLIER: {sme['description']}
    BID SUMMARY: {bid['summary']}
    Winning patterns: {hist['winning_patterns']}
    Rejection patterns: {hist['rejection_patterns']}
    Write exactly 2 sentences: why this aligns with winning patterns, and biggest risk of rejection. Use only facts above."""
    text = ask_claude(prompt, max_tokens=150)
    if text: return text
    where = "inside" if pos["price_in_range"] else "outside"
    return f"Price sits {abs(pos['below_pct']):.1f}% {'below' if pos['below_pct'] >= 0 else 'above'} budget, {where} the typical winning range. Biggest rejection risk: {hist['rejection_patterns'][0].lower()}."

# ---------------------------------------------------------------- PROPOSAL DRAFTER
def fact_sheet(sme, rfq):
    docs = "; ".join(f"{DOC_LABEL[d]} valid to {fmt(e)}" for d, e in sme["docs"].items() if e)
    return {"company": sme["name"], "province": sme["region"], "sector": sme["sector"], "bbbee_level": f"Level {sme['bbbee_level']}", "services": sme["description"], "past_work": sme.get("references", ""), "compliance": docs, "rfq_title": rfq["title"], "rfq_scope": rfq["scope"], "rfq_closes": fmt(rfq["closes"]), "rfq_budget": money(rfq["budget"]), "rfq_po": rfq["po_ref"]}

def numbers_in(text): return {m.rstrip(".,") for m in re.findall(r"\d[\d,\.]*", text)}

def verify_draft(text, facts):
    allowed = numbers_in(" ".join(str(v) for v in facts.values()))
    bad = sorted(n for n in numbers_in(text) if n not in allowed)
    return (not bad), bad

def generate_proposal(sme, rfq):
    f = fact_sheet(sme, rfq)
    prompt = f"""Write a short proposal (under 220 words). Use ONLY the facts below. Do not invent clients, prices, figures or dates. Leave price and timeline as [SME to complete].\n\nFACTS:\n{json.dumps(f, indent=2)}"""
    for _ in range(2):
        text = ask_claude(prompt, max_tokens=700)
        if not text: break
        ok, bad = verify_draft(text, f)
        if ok: return text, "AI-assisted draft", "Facts check passed."
        prompt += f"\n\nYour draft contained numbers not in the facts: {bad}. Remove them."
    return f"Subject: Response to {f['rfq_title']}\n\nDear Procurement Team,\n\n{f['company']} ({f['bbbee_level']}, {f['province']}) submits this response.\n\n{f['services']}\n\nCompliance: {f['compliance']}\n\nKind regards,\n{f['company']}", "Template draft", "AI unavailable or failed check."

# ---------------------------------------------------------------- STATE & DATA
def seed_registry():
    t = today()
    return [
        {"name": "EcoSpark Solar Solutions", "sector": "Renewable Energy & Solar", "region": "Gauteng", "bbbee_level": 1, "description": "Photovoltaic maintenance and green energy systems.", "references": "Serviced 3 commercial warehouses.", "docs": {"CIPC": t + timedelta(days=400), "Tax": t + timedelta(days=200), "B-BBEE": t + timedelta(days=150)}},
        {"name": "SunGrid Energy", "sector": "Renewable Energy & Solar", "region": "Gauteng", "bbbee_level": 2, "description": "Rooftop solar inspection, cleaning and inverter servicing.", "references": "Municipal clinics.", "docs": {"CIPC": t + timedelta(days=24), "Tax": t + timedelta(days=200), "B-BBEE": t + timedelta(days=120)}},
        {"name": "Sizwe Roof & Solar Services", "sector": "Renewable Energy & Solar", "region": "Gauteng", "bbbee_level": 2, "description": "Solar panel servicing, inverter checks.", "references": "School installations.", "docs": {"CIPC": t + timedelta(days=300), "Tax": t - timedelta(days=45), "B-BBEE": t + timedelta(days=90)}},
    ]

def seed_rfqs():
    t = today()
    return [{"id": 1, "title": "Solar Panel Servicing & Maintenance - Gauteng", "sector": "Renewable Energy & Solar", "scope": "Photovoltaic maintenance for regional corporate facilities.", "budget": 450000, "region": "Gauteng", "max_bbbee": 2, "po_ref": "PO-994821", "closes": t + timedelta(days=14)}]

def reset_demo():
    st.session_state.registry = seed_registry()
    st.session_state.rfqs = seed_rfqs()
    st.session_state.bids = []
    st.session_state.drafts = {}
    st.session_state.audit = []
    st.session_state.user_profile = None
    st.session_state.extracted_ai_data = None
    st.session_state.pop("sel_rfq", None)

if "registry" not in st.session_state: reset_demo()
for key, default in (("logged_in", False), ("portal_role", None), ("user_profile", None), ("extracted_ai_data", None), ("drafts", {}), ("audit", []), ("bids", [])):
    if key not in st.session_state: st.session_state[key] = default

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
            st.markdown("""<div class="css-card" style="text-align: center;"><h1 style="color: #0F4C81; margin-bottom: 5px;">🇿🇦 VulaFlow</h1><p style="color: #64748B; margin-bottom: 25px;">Select your gateway.</p></div>""", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if c1.button("I am an SME Vendor"): st.session_state.portal_role = "SME"; st.rerun()
            if c2.button("I am a Corporate Buyer"): st.session_state.portal_role = "Corporate"; st.rerun()
        else:
            role_label = "SME Portal" if st.session_state.portal_role == "SME" else "Corporate Portal"
            st.markdown(f"""<div class="css-card" style="text-align: center;"><h2 style="color: #0F4C81; margin-bottom: 0;">{role_label}</h2><p style="color: #64748B; font-size: 0.9em;">Demo sign-in</p></div>""", unsafe_allow_html=True)
            with st.form("login_form"):
                st.text_input("Work Email", value="demo@vulaflow.co.za")
                st.text_input("Password", type="password", value="password123")
                if st.form_submit_button("Sign In"): st.session_state.logged_in = True; st.rerun()
            if st.button("← Switch Portal Type"): st.session_state.portal_role = None; st.rerun()

# ---------------------------------------------------------------- MAIN APP
else:
    role = st.session_state.portal_role
    st.sidebar.markdown(f"<h3 style='color: #0F4C81;'>VulaFlow</h3>", unsafe_allow_html=True)
    st.sidebar.caption(f"Role: {role}")
    st.sidebar.markdown("---")
    if role == "SME":
        menu = st.sidebar.radio("Navigation", ["My Profile", "Opportunities & Proposals", "Log Out"])
    else:
        menu = st.sidebar.radio("Navigation", ["Post RFQ & Shortlist", "Bid Intake (Standardization)", "Awarded Contracts", "Log Out"])
    st.sidebar.markdown("---")
    if st.sidebar.button("Reset demo"): reset_demo(); st.rerun()

    if menu == "Log Out":
        st.session_state.logged_in = False; st.session_state.portal_role = None; st.session_state.user_profile = None; st.rerun()

    # ============================== SME
    if role == "SME":
        if menu == "My Profile":
            if st.session_state.user_profile is None:
                if st.button("⚡ Load Demo Profile"):
                    st.session_state.user_profile = next(s for s in st.session_state.registry if s["name"].startswith("Sizwe"))
                    st.rerun()
                st.markdown("<div class='css-card'>", unsafe_allow_html=True)
                with st.form("profile_form"):
                    name = st.text_input("Business name", value="Sizwe Roof & Solar")
                    desc = st.text_area("Business description", value="Solar panel servicing and maintenance.")
                    cipc = st.date_input("CIPC expiry", value=today() + timedelta(days=365))
                    tax = st.date_input("Tax expiry", value=today() - timedelta(days=10))
                    bb = st.date_input("B-BBEE expiry", value=today() + timedelta(days=90))
                    if st.form_submit_button("Save Profile"):
                        st.session_state.user_profile = {"name": name, "description": desc, "sector": classify_sector(desc), "region": "Gauteng", "bbbee_level": 2, "references": "", "docs": {"CIPC": cipc, "Tax": tax, "B-BBEE": bb}}
                        st.session_state.registry = [s for s in st.session_state.registry if s["name"] != name] + [st.session_state.user_profile]
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                p = st.session_state.user_profile
                summary = doc_summary(p)
                ok = all(s[0] in ("Valid", "Expiring Soon") for s in summary.values())
                badge = '<span class="badge badge-ready">DOCUMENTS CURRENT</span>' if ok else '<span class="badge badge-no">ACTION REQUIRED</span>'
                st.markdown(f"""<div class="css-card"><h1 style="color: #0F4C81; margin-top: 0; display: inline-block;">{esc(p['name'])}</h1> {badge}<br><br><div class="sector-badge">🏷️ {esc(p['sector'])}</div><p style="color: #475569;">{esc(p['description'])}</p></div>""", unsafe_allow_html=True)
                for doc, (status, days) in summary.items():
                    if status == "Valid": st.markdown(f"<div class='doc-valid'>✅ <b>{doc}</b>: valid ({days} days left)</div>", unsafe_allow_html=True)
                    elif status == "Expiring Soon": st.markdown(f"<div class='doc-warning'>⏳ <b>{doc}</b>: expires in {days} days</div>", unsafe_allow_html=True)
                    else: st.markdown(f"<div class='doc-error'>❌ <b>{doc}</b>: {status.lower()}</div>", unsafe_allow_html=True)

        else: # Opportunities
            p = st.session_state.user_profile
            if p is None: st.warning("Create or load your profile first.")
            else:
                for rfq in st.session_state.rfqs:
                    rows = evaluate(p, rfq)
                    tier = tier_of(rows)
                    failed = [r for r in rows if not r["passed"]]
                    st.markdown(f"""<div class="css-card" style="border-left: 4px solid {TIER_COLOUR[tier]};"><h3 style="color: #0F4C81; margin-top: 0;">{esc(rfq['title'])} {tier_badge(tier, rows)}</h3><p style="color: #64748B;">{esc(rfq['scope'])} | Budget: {money(rfq['budget'])}</p>""", unsafe_allow_html=True)
                    for r in failed:
                        st.markdown(f"<div class='fixbox'>🔧 <b>{esc(r['fix'])}</b> ({esc(r['rule'])})</div>", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)
                    if tier == "READY":
                        if st.button("Draft my proposal", key=f"draft_{rfq['id']}"):
                            with st.spinner("Drafting..."):
                                st.session_state.drafts[rfq['id']] = generate_proposal(p, rfq)
                        if rfq['id'] in st.session_state.drafts:
                            text, source, note = st.session_state.drafts[rfq['id']]
                            st.caption(f"{source}. {note}.")
                            st.text_area("Proposal", value=text, height=250, key=f"edit_{rfq['id']}")

    # ============================== CORPORATE
    else:
        if menu == "Post RFQ & Shortlist":
            st.markdown("<h2 style='color: #1E293B;'>📝 Post an RFQ & View Shortlist</h2>", unsafe_allow_html=True)
            with st.expander("Post a new RFQ"):
                with st.form("rfq_post_form"):
                    title = st.text_input("Title"); scope = st.text_area("Scope")
                    c1, c2, c3 = st.columns(3)
                    region = c1.selectbox("Province", SA_PROVINCES); max_level = c2.selectbox("Max B-BBEE", [1,2,3,4]); budget = c3.text_input("Budget (ZAR)")
                    po = st.text_input("PO Reference")
                    if st.form_submit_button("Publish"):
                        if not (title and scope and budget and po): st.error("All fields required.")
                        else:
                            st.session_state.rfqs.append({"id": len(st.session_state.rfqs)+1, "title": title, "sector": classify_sector(scope), "scope": scope, "budget": int(re.sub(r'[^\d]', '', budget)), "region": region, "max_bbbee": int(max_level), "po_ref": po, "closes": today() + timedelta(days=14)})
                            st.rerun()

            rfq = st.selectbox("Select RFQ to view", st.session_state.rfqs, format_func=lambda r: r['title'])
            if rfq:
                classified = classify_all(rfq, st.session_state.registry)
                for sme, rows, tier in classified:
                    st.markdown(f"""<div class="css-card" style="padding: 16px; border-left: 4px solid {TIER_COLOUR[tier]};"><h4 style="color: #0F4C81; margin: 0;">{esc(sme['name'])} {tier_badge(tier, rows)}</h4></div>""", unsafe_allow_html=True)

        elif menu == "Bid Intake (Standardization)":
            st.markdown("<h2 style='color: #1E293B;'>📥 Bid Intake & Standardization</h2>", unsafe_allow_html=True)
            st.write("Paste a messy supplier email to standardize it and benchmark it against historical data.")
            rfq = st.selectbox("Select RFQ", st.session_state.rfqs, format_func=lambda r: r['title'])
            supplier_name = st.selectbox("Supplier", [s['name'] for s in st.session_state.registry])
            
            with st.expander("Ingest Raw Bid", expanded=True):
                raw = st.text_area("Paste original submission here", height=150, placeholder="Hi team, Thando here... we can do the servicing for R 431 000...")
                if st.button("Standardize Bid"):
                    if raw.strip():
                        std = standardize_raw_bid(raw)
                        if std['price'] and std['timeline_days']:
                            st.session_state.bids.append({"rfq_id": rfq['id'], "supplier": supplier_name, "price": std['price'], "timeline_days": std['timeline_days'], "summary": std['summary'], "verified": std['verified'], "engine": std['engine']})
                            st.success(f"Standardized via {std['engine']}: {money(std['price'])}, {std['timeline_days']} days.")
                        else: st.error("Could not parse price or timeline.")
            
            st.markdown("### Standardized Bids for this RFQ")
            matching_bids = [b for b in st.session_state.bids if b['rfq_id'] == rfq['id']]
            if not matching_bids: st.info("No bids ingested yet.")
            for b in matching_bids:
                sme = next(s for s in st.session_state.registry if s['name'] == b['supplier'])
                st.markdown(f"**{esc(b['supplier'])}** | Price: {money(b['price'])} | Timeline: {b['timeline_days']} days | Source Check: {'✅' if b['verified'] else '⚠️'}")
                st.caption(f"Summary: {esc(b['summary'])}")
                
                hist = HISTORICAL_BID_DATA.get(rfq["sector"], DEFAULT_HISTORY)
                pos = price_position(b, rfq, hist)
                lo, hi = pos["price_range"]
                st.markdown(f"*Price is {abs(pos['below_pct']):.1f}% {'below' if pos['below_pct'] >= 0 else 'above'} budget. Typical winning range is {lo}-{hi}% below.*")
                if st.button("Run AI Bid Analysis", key=f"intel_{b['supplier']}"):
                    with st.spinner("Analyzing..."):
                        st.info(benchmark_bid_against_history(sme, rfq, b))
                st.markdown("---")

        elif menu == "Awarded Contracts":
            st.markdown("<h2 style='color: #1E293B;'>🏆 Awarded Contracts</h2>", unsafe_allow_html=True)
            awarded = [b for b in st.session_state.bids if b.get("status") == "Awarded"]
            if not awarded: st.info("No contracts awarded yet.")
            for b in awarded:
                st.markdown(f"**{esc(b['supplier'])}** - {money(b['price'])}")