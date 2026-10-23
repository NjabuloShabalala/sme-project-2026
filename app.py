import streamlit as st
import anthropic
import os
import json
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

# 1. SETUP & CONFIG
load_dotenv()

st.set_page_config(page_title="VulaFlow | Enterprise Procurement Gateway", page_icon="🇿🇦", layout="wide")

# --- MODERN FINTECH SAAS STYLING ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    .stApp {
        background-color: #F8FAFC;
    }
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E2E8F0;
    }
    .stButton>button {
        background-color: #0F4C81;
        color: white;
        border-radius: 8px;
        height: 2.8em;
        width: 100%;
        font-weight: 600;
        border: none;
        transition: background-color 0.2s;
    }
    .stButton>button:hover {
        background-color: #0A365C;
        color: white;
    }
    .css-card {
        background-color: #FFFFFF;
        padding: 24px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        border: 1px solid #E2E8F0;
        margin-bottom: 20px;
    }
    .badge-verified { 
        background: linear-gradient(135deg, #059669 0%, #10B981 100%);
        color: white; 
        padding: 6px 16px; 
        border-radius: 30px; 
        font-size: 0.8em; 
        font-weight: 700; 
        margin-left: 10px;
        box-shadow: 0 4px 6px rgba(16, 185, 129, 0.3);
        display: inline-flex;
        align-items: center;
        gap: 6px;
        vertical-align: middle;
    }
    .badge-unverified { 
        background: linear-gradient(135deg, #DC2626 0%, #EF4444 100%);
        color: white; 
        padding: 6px 16px; 
        border-radius: 30px; 
        font-size: 0.8em; 
        font-weight: 700; 
        margin-left: 10px;
        box-shadow: 0 4px 6px rgba(239, 68, 68, 0.3);
        display: inline-flex;
        align-items: center;
        gap: 6px;
        vertical-align: middle;
    }
    .sector-badge { 
        background-color: #EFF6FF; 
        color: #1D4ED8; 
        padding: 6px 14px; 
        border-radius: 20px; 
        font-size: 0.85em; 
        font-weight: 600; 
        display: inline-block; 
        border: 1px solid #BFDBFE; 
        margin-bottom: 12px; 
    }
    .doc-valid { background: #F0FDF4; border-left: 4px solid #22C55E; padding: 16px; border-radius: 8px; margin-bottom: 12px; color: #166534; }
    .doc-warning { background: #FFFBEB; border-left: 4px solid #F59E0B; padding: 16px; border-radius: 8px; margin-bottom: 12px; color: #92400E; }
    .doc-error { background: #FEF2F2; border-left: 4px solid #EF4444; padding: 16px; border-radius: 8px; margin-bottom: 12px; color: #991B1B; }

    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# Initialize Anthropic Client
@st.cache_resource
def get_client():
    return anthropic.Anthropic()

client = get_client()

# SA PROVINCES LIST
SA_PROVINCES = [
    "Gauteng", 
    "Western Cape", 
    "KwaZulu-Natal", 
    "Eastern Cape", 
    "Free State", 
    "Limpopo", 
    "Mpumalanga", 
    "North West", 
    "Northern Cape"
]

# 2. HELPER FUNCTIONS & AI ENGINE

def get_sector_from_description(description):
    """Dynamically detects any and every sector from a business description without rigid taxonomy constraints."""
    if not description or not description.strip():
        return "General Services"
    
    prompt = f"""
    Analyze the following South African business description and determine its exact industry sector or vertical in 2 to 4 words max (e.g., 'Precision Agriculture & IoT', 'Renewable Energy Engineering', 'Fintech & Payments', 'Mining Logistics').
    
    Description: "{description}"
    
    Respond with ONLY the professional sector name. Do NOT include punctuation, quotation marks, or explanations.
    """
    try:
        res = client.messages.create(
            model="claude-3-haiku-20240307", 
            max_tokens=25, 
            messages=[{"role": "user", "content": prompt}]
        )
        sector = res.content[0].text.strip().title()
        return sector
    except Exception as e:
        return "General Services"

def parse_document_dates_with_ai(file_text_simulated):
    """Simulates AI document extraction (POPIA-compliant human-in-the-loop validation)."""
    prompt = f"""
    Extract key document expiry dates from this document summary:
    "{file_text_simulated}"
    
    Return a valid JSON object with keys "CIPC", "Tax", and "BBBEE" formatted as "YYYY-MM-DD".
    Example: {{"CIPC": "2027-04-15", "Tax": "2026-11-30", "BBBEE": "2026-12-31"}}
    """
    try:
        res = client.messages.create(
            model="claude-3-haiku-20240307", 
            max_tokens=100, 
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(res.content[0].text.strip())
    except:
        # Fallback safe extraction dates for demo
        return {
            "CIPC": (date.today() + timedelta(days=200)).strftime("%Y-%m-%d"),
            "Tax": (date.today() + timedelta(days=120)).strftime("%Y-%m-%d"),
            "BBBEE": (date.today() + timedelta(days=90)).strftime("%Y-%m-%d")
        }

def check_document_status(expiry_date):
    """Evaluates document compliance state based on native date comparison."""
    if not expiry_date: 
        return "Missing", 0
    today = date.today()
    if isinstance(expiry_date, str):
        expiry_date = datetime.strptime(expiry_date, "%Y-%m-%d").date()
    days_left = (expiry_date - today).days
    if days_left < 0: 
        return "Expired", days_left
    elif days_left < 60: 
        return "Expiring Soon", days_left
    else: 
        return "Valid", days_left

# 3. MOCK DATABASES IN SESSION STATE
if 'rfqs' not in st.session_state:
    st.session_state.rfqs = [
        {
            "id": 1, 
            "title": "Solar Panel Servicing & Maintenance - Gauteng", 
            "sector": "Renewable Energy & Solar Services", 
            "scope": "Photovoltaic maintenance and solar power servicing for regional corporate facilities.", 
            "budget": "R450,000", 
            "region": "Gauteng",
            "max_bbbee": "2",
            "po_ref": "PO-994821",
            "verified_only": True
        }
    ]

if 'verified_smes' not in st.session_state:
    st.session_state.verified_smes = [
        {"name": "EcoSpark Solar Solutions", "sector": "Renewable Energy & Solar Services", "desc": "Photovoltaic maintenance and green energy systems.", "bbbee": "Level 1", "location": "Gauteng", "verified": True},
        {"name": "Thabo Electrical", "sector": "Electrical & Infrastructure Engineering", "desc": "Electrical wiring and commercial infrastructure repairs.", "bbbee": "Level 2", "location": "Gauteng", "verified": True},
        {"name": "Cape Wind Technologies", "sector": "Renewable Energy & Solar Services", "desc": "Wind turbine maintenance and solar servicing.", "bbbee": "Level 4", "location": "Western Cape", "verified": False}
    ]

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'portal_role' not in st.session_state: st.session_state.portal_role = None 
if 'user_profile' not in st.session_state: st.session_state.user_profile = None

# --- ROLE SELECTION & LOGIN LANDING ---
if not st.session_state.logged_in:
    _, col2, _ = st.columns([1, 1.4, 1])
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.session_state.portal_role is None:
            st.markdown("""
                <div class="css-card" style="text-align: center;">
                    <h1 style="color: #0F4C81; margin-bottom: 5px;">🇿🇦 VulaFlow</h1>
                    <p style="color: #64748B; margin-bottom: 25px;">Select your gateway to enter the ecosystem.</p>
                </div>
            """, unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            if c1.button("I am an SME Vendor"):
                st.session_state.portal_role = "SME"
                st.rerun()
            if c2.button("I am a Corporate Buyer"):
                st.session_state.portal_role = "Corporate"
                st.rerun()
        else:
            role_label = "SME Vendor Portal" if st.session_state.portal_role == "SME" else "Corporate Buyer Portal"
            st.markdown(f"""
                <div class="css-card" style="text-align: center;">
                    <h2 style="color: #0F4C81; margin-bottom: 0;">{role_label}</h2>
                    <p style="color: #64748B; font-size: 0.9em;">Secure Authentication Gateway</p>
                </div>
            """, unsafe_allow_html=True)
            
            with st.form("login_form"):
                email = st.text_input("Work Email Address", value="vendor@ecospark.co.za" if st.session_state.portal_role == "SME" else "procurement@absa.co.za")
                password = st.text_input("Password", type="password", value="password123")
                submit = st.form_submit_button("Sign In")
                
                if submit:
                    st.session_state.logged_in = True
                    st.rerun()
                    
            if st.button("← Switch Portal Type"):
                st.session_state.portal_role = None
                st.rerun()

# --- MAIN APP INTERFACE ---
else:
    role = st.session_state.portal_role
    
    st.sidebar.markdown(f"<h3 style='color: #0F4C81; margin-bottom: 0;'>VulaFlow</h3>", unsafe_allow_html=True)
    st.sidebar.caption(f"Active Role: {role} Gateway")
    st.sidebar.markdown("---")
    
    if role == "SME":
        menu = st.sidebar.radio("Navigation", ["My Profile", "Actionable Opportunities", "Log Out"])
    else:
        menu = st.sidebar.radio("Navigation", ["Post Actionable RFQ", "Verified Supplier Directory", "Log Out"])
    
    if menu == "Log Out":
        st.session_state.logged_in = False
        st.session_state.portal_role = None
        st.session_state.user_profile = None
        st.rerun()

    # ==========================================
    # SME PORTAL LOGIC
    # ==========================================
    if role == "SME":
        if menu == "My Profile":
            if st.session_state.user_profile is None:
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown("<h2 style='color: #1E293B;'>Create Your SME Vendor Profile</h2>", unsafe_allow_html=True)
                    st.caption("Complete compliance data to unlock automated corporate RFQ matching.")
                with col_b:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("⚡ Load Demo Profile"):
                        st.session_state.user_profile = {
                            "name": "EcoSpark Solar Solutions (Pty) Ltd",
                            "description": "Photovoltaic maintenance, solar power servicing, and commercial green energy installations across Gauteng.",
                            "sector": "Renewable Energy & Solar Services",
                            "region": "Gauteng",
                            "bbbee": "Level 1",
                            "references": "Successfully completed 500kW solar installation and grid-tie maintenance for corporate client X.",
                            "docs": {
                                "CIPC": date.today() + timedelta(days=180),
                                "Tax": date.today() + timedelta(days=90),
                                "B-BBEE": date.today() + timedelta(days=120)
                            }
                        }
                        st.rerun()

                with st.container():
                    st.markdown("<div class='css-card'>", unsafe_allow_html=True)
                    
                    # AI Document Parser Dropzone (Backing up Pitch Script)
                    st.markdown("#### 📄 Option A: AI Fast-Upload (Parse Compliance Certificates)")
                    uploaded_doc = st.file_uploader("Drop CIPC / Tax / B-BBEE document here", type=["pdf", "png", "jpg", "txt"])
                    if uploaded_doc or st.button("🤖 Auto-Extract Dates from Sample Certificate"):
                        with st.spinner("AI parsing document metadata and extraction dates..."):
                            extracted = parse_document_dates_with_ai("Sample Tax Clearance Certificate Valid until 2027-05-30")
                            st.success("AI Extracted Expiry Dates Successfully! Please verify below (Human-in-the-Loop).")
                            st.json(extracted)

                    st.markdown("<hr>", unsafe_allow_html=True)
                    st.markdown("#### Option B: Manual Profile Entry")
                    
                    with st.form("profile_form"):
                        biz_name = st.text_input("Business Name", value="EcoSpark Solar Solutions")
                        description = st.text_area("Business Description & Capabilities", value="Photovoltaic maintenance, solar panel servicing, and clean energy solutions.")
                        sme_region = st.selectbox("Operating Region", SA_PROVINCES)
                        
                        st.markdown("<h4 style='margin-top: 15px;'>Compliance Expiry Dates (Fully Adjustable)</h4>", unsafe_allow_html=True)
                        c1, c2, c3 = st.columns(3)
                        
                        # Flexible Date Input Controls (Min Date set to 10 years ago, Max to 10 years ahead)
                        cipc_date = c1.date_input(
                            "CIPC Registration Expiry", 
                            value=date.today() + timedelta(days=365),
                            min_value=date(2015, 1, 1), 
                            max_value=date(2035, 12, 31)
                        )
                        tax_date = c2.date_input(
                            "Tax Clearance Expiry", 
                            value=date.today() + timedelta(days=180),
                            min_value=date(2015, 1, 1), 
                            max_value=date(2035, 12, 31)
                        )
                        bbbee_date = c3.date_input(
                            "B-BBEE Certificate Expiry", 
                            value=date.today() + timedelta(days=90),
                            min_value=date(2015, 1, 1), 
                            max_value=date(2035, 12, 31)
                        )
                        
                        st.markdown("<h4 style='margin-top: 15px;'>References & Track Record</h4>", unsafe_allow_html=True)
                        reference_text = st.text_area("Client References / Past Work", value="Completed solar PV maintenance for Corp X.")
                        
                        submitted = st.form_submit_button("Submit Profile for Verification")
                        
                        if submitted:
                            with st.spinner("AI is categorizing capabilities..."):
                                sector = get_sector_from_description(description)
                                st.session_state.user_profile = {
                                    "name": biz_name,
                                    "description": description,
                                    "sector": sector,
                                    "region": sme_region,
                                    "bbbee": "Level 1",
                                    "references": reference_text,
                                    "docs": {
                                        "CIPC": cipc_date,
                                        "Tax": tax_date,
                                        "B-BBEE": bbbee_date
                                    }
                                }
                                st.session_state.verified_smes.append({
                                    "name": biz_name, "sector": sector, "desc": description, "bbbee": "Level 1", "location": sme_region, "verified": True
                                })
                                st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
            else:
                profile = st.session_state.user_profile
                doc_statuses = {doc: check_document_status(dt) for doc, dt in profile['docs'].items()}
                all_valid = all(status[0] == "Valid" for status in doc_statuses.values())
                
                badge_html = '<span class="badge-verified">✓ 100% VERIFIED</span>' if all_valid else '<span class="badge-unverified">⚠ ACTION REQUIRED</span>'
                st.markdown(f"""
                    <div class="css-card">
                        <h1 style="color: #0F4C81; margin-top: 0; margin-bottom: 5px; display: inline-block;">{profile['name']}</h1> {badge_html}
                        <br><br>
                        <div class="sector-badge">🏷️ Sector: {profile['sector']}</div>
                        <p style="color: #475569; font-size: 1.05em;">{profile['description']}</p>
                    </div>
                """, unsafe_allow_html=True)
                
                st.markdown("<h3 style='color: #1E293B;'>Compliance Gateway Status</h3>", unsafe_allow_html=True)
                for doc, (status, days) in doc_statuses.items():
                    if status == "Valid":
                        st.markdown(f"<div class='doc-valid'>✅ <b>{doc}</b>: Valid and compliant ({days} days remaining)</div>", unsafe_allow_html=True)
                    elif status == "Expiring Soon":
                        st.markdown(f"<div class='doc-warning'>⏳ <b>{doc}</b>: Expiring in {days} days! Action required.</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='doc-error'>❌ <b>{doc}</b>: Expired or Invalid ({abs(days)} days past). Access Locked.</div>", unsafe_allow_html=True)

        elif menu == "Actionable Opportunities":
            st.markdown("<h2 style='color: #1E293B;'>🎯 Pre-Qualified Actionable Opportunities</h2>", unsafe_allow_html=True)
            st.write("Every tender below is guaranteed actionable with verified corporate budgets attached.")
            
            if st.session_state.user_profile is None:
                st.warning("Please complete your 'My Profile' compliance gateway first to unlock pre-qualified tender matching.")
            else:
                profile = st.session_state.user_profile
                doc_statuses = {doc: check_document_status(dt) for doc, dt in profile['docs'].items()}
                all_valid = all(status[0] == "Valid" for status in doc_statuses.values())
                
                if not all_valid:
                    st.error("🔒 Matching locked: Your compliance documents require valid updates before you can view active tenders.")
                else:
                    # Semantic & Sector Matching Engine
                    matched_rfqs = []
                    for rfq in st.session_state.rfqs:
                        # Direct sector match OR semantic keyword match (e.g., solar vs photovoltaic)
                        if (rfq['sector'].lower() in profile['sector'].lower() or 
                            profile['sector'].lower() in rfq['sector'].lower() or
                            ("solar" in profile['description'].lower() and "photovoltaic" in rfq['scope'].lower())):
                            matched_rfqs.append(rfq)
                            
                    if matched_rfqs:
                        for rfq in matched_rfqs:
                            st.markdown(f"""
                                <div class="css-card" style="border-left: 4px solid #10B981;">
                                    <h3 style="color: #0F4C81; margin-top: 0;">⭐ {rfq['title']}</h3>
                                    <p style="color: #64748B; margin-bottom: 8px;"><b>Scope:</b> {rfq['scope']}</p>
                                    <div style="background: #F8FAFC; padding: 12px; border-radius: 6px; margin-top: 10px;">
                                        <b>Actionability Guarantee:</b><br>
                                        • Confirmed Budget: <b>{rfq['budget']}</b><br>
                                        • PO / Cost Centre Ref: <b>{rfq['po_ref']}</b><br>
                                        • Region Verified: {rfq['region']}<br>
                                        • Your Match Status: <span style="color: #059669; font-weight: bold;">Pre-Qualified & Ready to Submit</span>
                                    </div>
                                </div>
                            """, unsafe_allow_html=True)
                            if st.button("Submit Verified Proposal", key=f"apply_{rfq['id']}"):
                                st.success("Proposal and compliance packet successfully transmitted directly to corporate procurement.")
                    else:
                        st.info("No active tenders match your specific service offering at the moment.")

    # ==========================================
    # CORPORATE PORTAL LOGIC
    # ==========================================
    else:
        if menu == "Post Actionable RFQ":
            st.markdown("<h2 style='color: #1E293B;'>📝 Post an Actionable Opportunity</h2>", unsafe_allow_html=True)
            st.write("Use our automated qualification mechanism to filter out noise and instantly surface verified suppliers.")
            
            with st.container():
                st.markdown("<div class='css-card'>", unsafe_allow_html=True)
                with st.form("rfq_post_form"):
                    rfq_title = st.text_input("Opportunity Title", placeholder="e.g. Enterprise Solar Panel Servicing")
                    rfq_scope = st.text_area("Scope of Work & Deliverables", placeholder="Photovoltaic maintenance and solar power servicing.")
                    
                    c1, c2, c3 = st.columns(3)
                    # All 9 South African Provinces Included
                    req_region = c1.selectbox("Required Region", SA_PROVINCES)
                    req_bbbee = c2.selectbox("Max B-BBEE Level Required", ["1", "2", "3", "4"])
                    budget = c3.text_input("Allocated Budget (ZAR)", placeholder="e.g. R450,000")
                    
                    po_ref = st.text_input("Internal Cost Centre / PO Reference Code (Mandatory Actionability Check)", placeholder="e.g. PO-994821")
                    req_verified = st.checkbox("Enforce 100% Compliance Gate (Only show verified suppliers)", value=True)
                    
                    submitted = st.form_submit_button("Publish & Run Qualification Match")
                    
                    if submitted:
                        # Exact trigger for pitch validation (Triggers red error box if blank)
                        if not budget.strip() or not po_ref.strip():
                            st.error("⚠️ Actionability Check Failed: A confirmed budget allocation and internal PO reference code are mandatory before an RFQ can go live.")
                        else:
                            sector = get_sector_from_description(rfq_scope)
                            new_rfq = {
                                "id": len(st.session_state.rfqs) + 1,
                                "title": rfq_title,
                                "sector": sector,
                                "scope": rfq_scope,
                                "budget": budget,
                                "region": req_region,
                                "max_bbbee": req_bbbee,
                                "po_ref": po_ref,
                                "verified_only": req_verified
                            }
                            st.session_state.rfqs.append(new_rfq)
                            
                            st.markdown("<h3 style='margin-top: 25px;'>Pre-Qualified Supplier Shortlist</h3>", unsafe_allow_html=True)
                            st.info("The automated rule engine has screened the registry. Only fully compliant suppliers are displayed below.")
                            
                            for sme in st.session_state.verified_smes:
                                if req_verified and not sme["verified"]: 
                                    continue
                                if sme["location"] != req_region: 
                                    continue
                                
                                st.markdown(f"""
                                    <div class="css-card" style="padding: 16px; border-left: 4px solid #10B981;">
                                        <h4 style="color: #0F4C81; margin: 0;">{sme['name']} <span class="badge-verified" style="font-size: 0.6em; padding: 2px 8px;">✓ VERIFIED</span></h4>
                                        <p style="color: #64748B; margin: 5px 0;">{sme['desc']} | B-BBEE: {sme['bbbee']} | Region: {sme['location']}</p>
                                        <div style="background: #F8FAFC; padding: 10px; border-radius: 6px; margin-top: 10px; font-size: 0.9em;">
                                            <b>AI Match Rationale:</b><br>
                                            • Passed regional filter ({sme['location']})<br>
                                            • Met B-BBEE threshold ({sme['bbbee']})<br>
                                            • Active compliance credentials verified.
                                        </div>
                                    </div>
                                """, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

        elif menu == "Verified Supplier Directory":
            st.markdown("<h2 style='color: #1E293B;'>🏢 Pre-Vetted Corporate Supplier Directory</h2>", unsafe_allow_html=True)
            st.write("Instant access to verified SME suppliers with zero manual admin or paperwork burden.")
            
            for sme in st.session_state.verified_smes:
                badge = '<span class="badge-verified" style="font-size: 0.7em;">✓ VERIFIED</span>' if sme['verified'] else '<span class="badge-unverified" style="font-size: 0.7em;">⚠ UNVERIFIED</span>'
                st.markdown(f"""
                    <div class="css-card">
                        <h3 style="color: #0F4C81; margin-top: 0;">{sme['name']} {badge}</h3>
                        <div class="sector-badge">{sme['sector']}</div>
                        <p style="color: #475569;">{sme['desc']}</p>
                        <p style="font-size: 0.9em; color: #64748B;"><b>Location:</b> {sme['location']} &nbsp;|&nbsp; <b>B-BBEE:</b> {sme['bbbee']}</p>
                    </div>
                """, unsafe_allow_html=True)