import streamlit as st
import anthropic
import base64
import json
import os
import re
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
st.set_page_config(page_title="VulaFlow | Enterprise Gateway", page_icon="🏢", layout="wide")

# Initialize AI Client
try:
    client = anthropic.Anthropic()
except Exception:
    client = None

# --- ENTERPRISE DARK MODE CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
    
    /* Core Theme */
    .stApp { background-color: #0F172A; color: #F8FAFC; font-family: 'Inter', sans-serif; }
    [data-testid="stSidebar"] { background-color: #1E293B; border-right: 1px solid #334155; }
    [data-testid="stSidebar"] * { color: #E2E8F0 !important; }
    
    /* Headers */
    h1, h2, h3, h4 { color: #F8FAFC !important; font-weight: 600 !important; letter-spacing: -0.02em; }
    
    /* Cards */
    .css-card { background-color: #1E293B; border: 1px solid #334155; padding: 24px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2); }
    .css-card h3 { margin-top: 0; color: #38BDF8 !important; }
    
    /* Buttons */
    .stButton>button { background-color: #3B82F6; color: white; border-radius: 6px; font-weight: 600; border: none; width: 100%; height: 2.8em; transition: 0.2s; }
    .stButton>button:hover { background-color: #2563EB; color: white; }
    
    /* Inputs & Forms */
    div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] { background-color: #0F172A !important; border: 1px solid #475569 !important; color: white !important; }
    div[data-testid="stForm"] { background-color: #1E293B; border: 1px solid #334155; padding: 20px; border-radius: 8px; }
    
    /* Status Badges */
    .badge { display: inline-block; padding: 4px 10px; border-radius: 4px; font-size: 0.75em; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; font-family: 'JetBrains Mono', monospace; }
    .badge-ready { background: rgba(16, 185, 129, 0.2); color: #34D399; border: 1px solid #059669; }
    .badge-fix { background: rgba(245, 158, 11, 0.2); color: #FBBF24; border: 1px solid #D97706; }
    .badge-no { background: rgba(239, 68, 68, 0.2); color: #F87171; border: 1px solid #DC2626; }
    
    /* Score Bar */
    .score-container { background-color: #0F172A; border-radius: 8px; padding: 15px; margin-top: 10px; border: 1px solid #334155; }
    .score-bar { height: 8px; border-radius: 4px; background: linear-gradient(90deg, #EF4444 0%, #F59E0B 50%, #10B981 100%); width: 100%; margin: 10px 0; position: relative; }
    .score-marker { position: absolute; top: -4px; width: 16px; height: 16px; background-color: #FFF; border: 2px solid #0F172A; border-radius: 50%; transform: translateX(-50%); }
    
    /* Hide Streamlit Defaults */
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def get_file_content(uploaded_file):
    """Converts uploaded file to base64 for Claude."""
    bytes_data = uploaded_file.getvalue()
    base64_data = base64.b64encode(bytes_data).decode("utf-8")
    media_type = uploaded_file.type
    if media_type == "application/pdf":
        return {"type": "document", "source": {"type": "base64", "media_type": media_type, "data": base64_data}}
    elif media_type in ["image/jpeg", "image/png"]:
        return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": base64_data}}
    return None

def ai_extract_profile(file):
    """Extracts SME compliance data from PDF/Image."""
    content = get_file_content(file)
    if not content or not client: return None
    
    prompt = """Extract the business details from this South African compliance document. 
    Return ONLY a JSON object with keys: business_name, description (what they do, max 20 words), 
    region (Gauteng, Western Cape, KZN, etc.), cipc_expiry, tax_expiry, bbbee_expiry (YYYY-MM-DD), bbbee_level (1-8).
    Use null for missing data. Do not guess."""
    
    try:
        res = client.messages.create(model="claude-3-haiku-20240307", max_tokens=500,
            messages=[{"role": "user", "content": [content, {"type": "text", "text": prompt}]}])
        clean_json = res.content[0].text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        st.error(f"Extraction failed: {e}")
        return None

def ai_extract_rfq(file):
    """Extracts structured requirements from an RFQ PDF."""
    content = get_file_content(file)
    if not content or not client: return None
    
    prompt = """Extract the tender details from this RFQ document. 
    Return ONLY a JSON object with keys: title, scope (max 30 words), budget (integer, ZAR), 
    region (Gauteng, Western Cape, KZN, etc.), max_bbbee (integer 1-8), po_ref (string).
    Use null for missing data. Do not guess."""
    
    try:
        res = client.messages.create(model="claude-3-haiku-20240307", max_tokens=500,
            messages=[{"role": "user", "content": [content, {"type": "text", "text": prompt}]}])
        clean_json = res.content[0].text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        st.error(f"RFQ parsing failed: {e}")
        return None

def ai_calculate_capability(sme, rfq):
    """Calculates a match % and provides reasoning based on past work."""
    prompt = f"""You are a procurement analyst. Evaluate this SME for an RFQ.
    RFQ Scope: {rfq['scope']}
    SME Description: {sme['description']}
    SME References: {sme.get('references', 'No references provided')}
    
    Return ONLY a JSON object with keys: 
    - score (integer 0-100)
    - reasoning (2 sentences explaining why they got this score based on their references vs the RFQ scope).
    """
    try:
        res = client.messages.create(model="claude-3-haiku-20240307", max_tokens=200, messages=[{"role": "user", "content": prompt}])
        clean_json = res.content[0].text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception:
        return {"score": 50, "reasoning": "AI analysis unavailable. Standard compliance match applied."}

def check_compliance(sme):
    today = date.today()
    issues = []
    for doc, expiry_str in sme.get("docs", {}).items():
        if not expiry_str:
            issues.append(f"Missing {doc}")
        else:
            try:
                expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
                if expiry < today:
                    issues.append(f"Expired {doc}")
                elif expiry < today + timedelta(days=60):
                    issues.append(f"{doc} expiring soon")
            except: pass
    return issues

# --- SESSION STATE ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'role' not in st.session_state: st.session_state.role = None
if 'sme_profile' not in st.session_state: st.session_state.sme_profile = None
if 'rfqs' not in st.session_state: st.session_state.rfqs = []
if 'registry' not in st.session_state: st.session_state.registry = []

# --- LOGIN ---
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        if st.session_state.role is None:
            st.markdown("<div class='css-card' style='text-align:center;'><h1>VulaFlow</h1><p>Enterprise Procurement Gateway</p></div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if c1.button("SME Vendor"): st.session_state.role = "SME"; st.rerun()
            if c2.button("Corporate Buyer"): st.session_state.role = "Corporate"; st.rerun()
        else:
            st.markdown(f"<div class='css-card' style='text-align:center;'><h2>{st.session_state.role} Login</h2></div>", unsafe_allow_html=True)
            with st.form("login"):
                st.text_input("Work Email")
                st.text_input("Password", type="password")
                if st.form_submit_button("Sign In"):
                    st.session_state.logged_in = True
                    st.rerun()
            if st.button("Switch Role"):
                st.session_state.role = None
                st.rerun()

# --- MAIN APP ---
else:
    with st.sidebar:
        st.markdown(f"### VulaFlow")
        st.caption(f"Logged in as: {st.session_state.role}")
        st.divider()
        if st.button("Log Out"):
            st.session_state.logged_in = False
            st.session_state.role = None
            st.session_state.sme_profile = None
            st.rerun()

    # ==========================================
    # SME DASHBOARD
    # ==========================================
    if st.session_state.role == "SME":
        if not st.session_state.sme_profile:
            st.title("Onboard Your Business")
            st.write("Upload your compliance documents. Our AI will extract the data for your review.")
            
            uploaded_file = st.file_uploader("Upload CIPC / Tax / B-BBEE Certificate (PDF or Image)", type=["pdf", "png", "jpg", "jpeg"])
            
            if uploaded_file and st.button("Extract Data with AI"):
                with st.spinner("Processing document..."):
                    data = ai_extract_profile(uploaded_file)
                    if data:
                        st.session_state.sme_profile = {
                            "name": data.get("business_name") or "",
                            "description": data.get("description") or "",
                            "region": data.get("region") or "Gauteng",
                            "docs": {
                                "CIPC": data.get("cipc_expiry"),
                                "Tax": data.get("tax_expiry"),
                                "B-BBEE": data.get("bbbee_expiry")
                            },
                            "bbbee_level": data.get("bbbee_level") or 4,
                            "references": ""
                        }
                        st.success("Extraction complete. Please confirm below.")
                        st.rerun()
        else:
            st.title(f"{st.session_state.sme_profile['name']}")
            
            # Compliance Check
            issues = check_compliance(st.session_state.sme_profile)
            if issues:
                st.markdown(f"<div class='badge badge-fix'>Action Required: {', '.join(issues)}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='badge badge-ready'>100% Compliant</div>", unsafe_allow_html=True)
                
            st.markdown("### Opportunities")
            if not st.session_state.rfqs:
                st.info("No active RFQs available.")
            
            for rfq in st.session_state.rfqs:
                # AI Match Score for SME view
                cap_data = ai_calculate_capability(st.session_state.sme_profile, rfq)
                
                with st.container():
                    st.markdown(f"""
                    <div class='css-card'>
                        <h3>{rfq['title']}</h3>
                        <p style='color:#94A3B8;'>{rfq['scope']}</p>
                        <p><b>Budget:</b> R{rfq['budget']:,} | <b>Region:</b> {rfq['region']} | <b>Max B-BBEE:</b> {rfq['max_bbbee']}</p>
                        <div class='score-container'>
                            <div style='display:flex; justify-content:space-between;'>
                                <span>Capability Match</span>
                                <strong>{cap_data['score']}%</strong>
                            </div>
                            <div class='score-bar'><div class='score-marker' style='left:{cap_data['score']}%;'></div></div>
                            <p style='font-size:0.85em; color:#94A3B8; font-style:italic;'>AI Note: {cap_data['reasoning']}</p>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    if rfq.get('pdf_bytes'):
                        col1.download_button("📄 Download Original RFQ PDF", data=rfq['pdf_bytes'], file_name=f"{rfq['title']}.pdf", mime="application/pdf", key=f"dl_{rfq['title']}")
                    if col2.button("Submit Proposal", key=f"apply_{rfq['title']}"):
                        st.success("Proposal submitted.")

    # ==========================================
    # CORPORATE DASHBOARD
    # ==========================================
    elif st.session_state.role == "Corporate":
        st.title("Corporate Gateway")
        
        tab1, tab2 = st.tabs(["Post New RFQ", "Supplier Shortlist"])
        
        with tab1:
            st.write("Upload your RFQ document. The AI will extract the requirements automatically.")
            rfq_file = st.file_uploader("Upload RFQ (PDF)", type=["pdf"], key="rfq_upload")
            
            if rfq_file and st.button("Parse RFQ"):
                with st.spinner("Parsing RFQ document..."):
                    data = ai_extract_rfq(rfq_file)
                    if data:
                        st.session_state.temp_rfq = {
                            "title": data.get("title") or "Untitled RFQ",
                            "scope": data.get("scope") or "",
                            "budget": data.get("budget") or 0,
                            "region": data.get("region") or "Gauteng",
                            "max_bbbee": data.get("max_bbbee") or 4,
                            "po_ref": data.get("po_ref") or "PO-000",
                            "pdf_bytes": rfq_file.getvalue()
                        }
                        st.success("Parsed successfully. Please confirm.")
            
            if 'temp_rfq' in st.session_state:
                st.markdown("### Confirm RFQ Details")
                with st.form("confirm_rfq"):
                    title = st.text_input("Title", value=st.session_state.temp_rfq["title"])
                    scope = st.text_area("Scope", value=st.session_state.temp_rfq["scope"])
                    budget = st.number_input("Budget (ZAR)", value=st.session_state.temp_rfq["budget"])
                    region = st.text_input("Region", value=st.session_state.temp_rfq["region"])
                    max_bbbee = st.number_input("Max B-BBEE Level", value=st.session_state.temp_rfq["max_bbbee"])
                    po_ref = st.text_input("PO Reference", value=st.session_state.temp_rfq["po_ref"])
                    
                    if st.form_submit_button("Publish RFQ"):
                        st.session_state.rfqs.append({
                            "title": title, "scope": scope, "budget": budget, "region": region, 
                            "max_bbbee": max_bbbee, "po_ref": po_ref, "pdf_bytes": st.session_state.temp_rfq["pdf_bytes"]
                        })
                        del st.session_state.temp_rfq
                        st.success("RFQ Published to platform.")
                        st.rerun()

        with tab2:
            if not st.session_state.rfqs:
                st.info("No RFQs posted yet.")
            
            for rfq in st.session_state.rfqs:
                st.markdown(f"#### {rfq['title']} (Ref: {rfq['po_ref']})")
                
                # If there are no SMEs in registry, add some dummy ones for demo
                if not st.session_state.registry:
                    st.session_state.registry = [
                        {"name": "EcoSpark Solar", "description": "Solar panel maintenance", "region": "Gauteng", "bbbee_level": 1, "references": "Serviced 3 warehouses.", "docs": {"CIPC": "2026-01-01", "Tax": "2025-10-01", "B-BBEE": "2026-05-01"}},
                        {"name": "SunGrid Energy", "description": "Rooftop solar cleaning", "region": "Gauteng", "bbbee_level": 2, "references": "Municipal clinics.", "docs": {"CIPC": "2026-01-01", "Tax": "2025-12-01", "B-BBEE": "2026-05-01"}}
                    ]
                
                for sme in st.session_state.registry:
                    # Filter by hard rules first
                    if sme['bbbee_level'] > rfq['max_bbbee']: continue
                    
                    cap_data = ai_calculate_capability(sme, rfq)
                    issues = check_compliance(sme)
                    tier = "READY" if not issues else "FIXABLE" if any("expired" not in i.lower() for i in issues) else "NOT_ELIGIBLE"
                    
                    with st.expander(f"{sme['name']} - {tier}"):
                        st.markdown(f"""
                        <div class='css-card'>
                            <div style='display:flex; justify-content:space-between; align-items:center;'>
                                <h3 style='margin:0;'>{sme['name']}</h3>
                                <span class='badge badge-{'ready' if tier=='READY' else 'fix' if tier=='FIXABLE' else 'no'}'>{tier}</span>
                            </div>
                            <p style='margin-top:10px;'>{sme['description']}</p>
                            
                            <div class='score-container'>
                                <div style='display:flex; justify-content:space-between;'>
                                    <span>AI Capability Score</span>
                                    <strong>{cap_data['score']}%</strong>
                                </div>
                                <div class='score-bar'><div class='score-marker' style='left:{cap_data['score']}%;'></div></div>
                                <p style='font-size:0.85em; color:#94A3B8; font-style:italic;'>AI Reasoning: {cap_data['reasoning']}</p>
                            </div>
                            
                            <div style='margin-top:15px;'>
                                <b>Compliance Check:</b><br>
                                {'<br>'.join([f'<span style="color:#F87171;">❌ {i}</span>' for i in issues]) if issues else '<span style="color:#34D399;">✅ All documents valid</span>'}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)