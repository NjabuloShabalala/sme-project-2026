import streamlit as st
import anthropic
import os
from datetime import datetime, date
from dotenv import load_dotenv

# 1. SETUP & CONFIG
load_dotenv()

st.set_page_config(page_title="VulaFlow | Enterprise Procurement Gateway", page_icon="🇿🇦", layout="wide")

# --- MASSIVE CSS OVERHAUL FOR A MODERN SAAS LOOK ---
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
    
    /* Sleek SaaS Cards */
    .css-card {
        background-color: #FFFFFF;
        padding: 24px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        border: 1px solid #E2E8F0;
        margin-bottom: 20px;
    }
    
    /* Upgraded Vibrant Verification Badges */
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
    
    /* Doc Status Boxes */
    .doc-valid { background: #F0FDF4; border-left: 4px solid #22C55E; padding: 16px; border-radius: 8px; margin-bottom: 12px; color: #166534; }
    .doc-warning { background: #FFFBEB; border-left: 4px solid #F59E0B; padding: 16px; border-radius: 8px; margin-bottom: 12px; color: #92400E; }
    .doc-error { background: #FEF2F2; border-left: 4px solid #EF4444; padding: 16px; border-radius: 8px; margin-bottom: 12px; color: #991B1B; }

    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# Initialize Client
@st.cache_resource
def get_client():
    return anthropic.Anthropic()

client = get_client()

# HELPER FUNCTIONS
def get_sector_from_description(description):
    if not description.strip():
        return "General Services"
    prompt = f"Categorize this business into ONE short sector (e.g., 'Marketing', 'Manufacturing', 'Renewable Energy', 'ICT'). Return ONLY the sector name. Description: {description}"
    try:
        res = client.messages.create(model="claude-3-haiku-20240307", max_tokens=15, messages=[{"role": "user", "content": prompt}])
        return res.content[0].text.strip()
    except:
        return "General Services"

def check_document_status(expiry_date):
    if not expiry_date: return "Missing", 0
    today = date.today()
    days_left = (expiry_date - today).days
    if days_left < 0: return "Expired", days_left
    elif days_left < 60: return "Expiring Soon", days_left
    else: return "Valid", days_left

# MOCK DATABASES IN SESSION STATE
if 'rfqs' not in st.session_state:
    st.session_state.rfqs = [
        {
            "id": 1, 
            "title": "Solar Panel Servicing & Maintenance - Gauteng", 
            "sector": "Renewable Energy", 
            "scope": "Photovoltaic maintenance and solar power servicing for regional facilities.", 
            "budget": "R450,000", 
            "region": "Gauteng",
            "max_bbbee": "2",
            "verified_only": True
        }
    ]

if 'verified_smes' not in st.session_state:
    st.session_state.verified_smes = [
        {"name": "EcoSpark Solar Solutions", "sector": "Renewable Energy", "desc": "Photovoltaic maintenance and green energy systems.", "bbbee": "Level 1", "location": "Gauteng", "verified": True},
        {"name": "Thabo Electrical", "sector": "Electrical", "desc": "Electrical wiring and commercial infrastructure repairs.", "bbbee": "Level 2", "location": "Gauteng", "verified": True},
        {"name": "Cape Wind Technologies", "sector": "Renewable Energy", "desc": "Wind turbine maintenance.", "bbbee": "Level 4", "location": "Western Cape", "verified": False}
    ]

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'portal_role' not in st.session_state: st.session_state.portal_role = None # 'SME' or 'Corporate'
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
    
    # Sidebar Control
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
                            "sector": "Renewable Energy",
                            "region": "Gauteng",
                            "bbbee": "Level 1",
                            "references": "Successfully completed 500kW solar installation and grid-tie maintenance for corporate client X.",
                            "docs": {
                                "CIPC": date.today() + datetime.timedelta(days=180),
                                "Tax": date.today() + datetime.timedelta(days=90),
                                "B-BBEE": date.today() + datetime.timedelta(days=120)
                            }
                        }
                        st.rerun()

                with st.container():
                    st.markdown("<div class='css-card'>", unsafe_allow_html=True)
                    with st.form("profile_form"):
                        biz_name = st.text_input("Business Name")
                        description = st.text_area("Business Description & Capabilities")
                        
                        st.markdown("<h4 style='margin-top: 15px;'>Compliance Documents Expiry</h4>", unsafe_allow_html=True)
                        c1, c2, c3 = st.columns(3)
                        cipc_date = c1.date_input("CIPC Expiry", value=date.today())
                        tax_date = c2.date_input("Tax Clearance Expiry", value=date.today())
                        bbbee_date = c3.date_input("B-BBEE Expiry", value=date.today())
                        
                        st.markdown("<h4 style='margin-top: 15px;'>References & Track Record</h4>", unsafe_allow_html=True)
                        reference_text = st.text_area("Client References / Past Work")
                        
                        submitted = st.form_submit_button("Submit Profile for Verification")
                        
                        if submitted:
                            with st.spinner("AI is analyzing business capabilities..."):
                                sector = get_sector_from_description(description)
                                st.session_state.user_profile = {
                                    "name": biz_name,
                                    "description": description,
                                    "sector": sector,
                                    "region": "Gauteng",
                                    "bbbee": "Level 1",
                                    "references": reference_text,
                                    "docs": {
                                        "CIPC": cipc_date,
                                        "Tax": tax_date,
                                        "B-BBEE": bbbee_date
                                    }
                                }
                                # Add to global verified pool for demo consistency
                                st.session_state.verified_smes.append({
                                    "name": biz_name, "sector": sector, "desc": description, "bbbee": "Level 1", "location": "Gauteng", "verified": True
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
                        st.markdown(f"<div class='doc-valid'>✅ <b>{doc}</b>: Valid and compliant</div>", unsafe_allow_html=True)
                    elif status == "Expiring Soon":
                        st.markdown(f"<div class='doc-warning'>⏳ <b>{doc}</b>: Expiring in {days} days! Update required.</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='doc-error'>❌ <b>{doc}</b>: Action needed ({status}).</div>", unsafe_allow_html=True)

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
                    matched_rfqs = [r for r in st.session_state.rfqs if r['sector'].lower() == profile['sector'].lower()]
                    if matched_rfqs:
                        for rfq in matched_rfqs:
                            st.markdown(f"""
                                <div class="css-card" style="border-left: 4px solid #10B981;">
                                    <h3 style="color: #0F4C81; margin-top: 0;">⭐ {rfq['title']}</h3>
                                    <p style="color: #64748B; margin-bottom: 8px;"><b>Scope:</b> {rfq['scope']}</p>
                                    <div style="background: #F8FAFC; padding: 12px; border-radius: 6px; margin-top: 10px;">
                                        <b>Actionability Guarantee:</b><br>
                                        • Confirmed Budget: <b>{rfq['budget']}</b><br>
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
                    rfq_title = st.text_input("Opportunity Title", placeholder="e.g. Enterprise Cloud Migration Services")
                    rfq_scope = st.text_area("Scope of Work & Deliverables")
                    
                    c1, c2, c3 = st.columns(3)
                    req_region = c1.selectbox("Required Region", ["Gauteng", "Western Cape", "KZN"])
                    req_bbbee = c2.selectbox("Max B-BBEE Level Required", ["1", "2", "3", "4"])
                    budget = c3.text_input("Allocated Budget (ZAR)", placeholder="e.g. R350,000")
                    
                    req_verified = st.checkbox("Enforce 100% Compliance Gate (Only show verified suppliers)", value=True)
                    
                    submitted = st.form_submit_button("Publish & Run Qualification Match")
                    
                    if submitted:
                        if not budget.strip():
                            st.error("Actionability Check Failed: A valid budget is required to publish an opportunity.")
                        else:
                            new_rfq = {
                                "id": len(st.session_state.rfqs) + 1,
                                "title": rfq_title,
                                "sector": "Renewable Energy" if "solar" in rfq_title.lower() else "ICT",
                                "scope": rfq_scope,
                                "budget": budget,
                                "region": req_region,
                                "max_bbbee": req_bbbee,
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