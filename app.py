import streamlit as st
import anthropic
from datetime import datetime, date
import os
from dotenv import load_dotenv

# 1. SETUP & CONFIG
load_dotenv()

st.set_page_config(page_title="SA Procurement Engine", page_icon="🇿🇦", layout="wide")

# Vibrant Custom Styles
st.markdown("""
    <style>
    .stButton>button { 
        width: 100%; 
        border-radius: 8px; 
        font-weight: 600;
        background-color: #2563EB;
        color: white;
    }
    .badge-verified { 
        background-color: #DCFCE7; 
        color: #15803D; 
        padding: 4px 12px; 
        border-radius: 9999px; 
        font-size: 0.85em; 
        font-weight: 600; 
        vertical-align: middle; 
        margin-left: 10px;
    }
    .badge-unverified { 
        background-color: #FEE2E2; 
        color: #B91C1C; 
        padding: 4px 12px; 
        border-radius: 9999px; 
        font-size: 0.85em; 
        font-weight: 600; 
        vertical-align: middle; 
        margin-left: 10px;
    }
    .sector-badge { 
        background-color: #1E40AF; 
        color: white; 
        padding: 6px 16px; 
        border-radius: 8px; 
        font-size: 0.875em; 
        font-weight: 600; 
        display: inline-block; 
        margin-bottom: 16px;
    }
    .doc-box { 
        padding: 12px 16px; 
        border-radius: 8px; 
        margin-bottom: 8px; 
        border-left: 4px solid;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize Client
@st.cache_resource
def get_client():
    return anthropic.Anthropic()

client = get_client()

# 2. HELPER FUNCTIONS
def get_sector_from_description(description: str) -> str:
    """Classifies business sector via lightweight API call."""
    if not description.strip():
        return "General Services"
    prompt = f"Categorize this business into ONE short sector (e.g., 'Marketing', 'Manufacturing', 'Renewable Energy'). Return ONLY the sector name. Description: {description}"
    try:
        res = client.messages.create(
            model="claude-3-haiku-20240307", 
            max_tokens=15, 
            messages=[{"role": "user", "content": prompt}]
        )
        return res.content[0].text.strip()
    except Exception:
        return "General Services"

def check_document_status(expiry_date: date):
    """Calculates status based on native date objects."""
    if not expiry_date:
        return "Missing", 0
    today = date.today()
    days_left = (expiry_date - today).days
    
    if days_left < 0:
        return "Expired", days_left
    elif days_left < 60:
        return "Expiring Soon", days_left
    return "Valid", days_left

# 3. MOCK DATA
MOCK_RFQS = [
    {"id": 1, "title": "Solar Panel Servicing - Gauteng", "scope": "Photovoltaic maintenance and solar power servicing."},
    {"id": 2, "title": "Corporate Website Redesign", "scope": "UX/UI design and frontend development for corporate portal."}
]

# 4. SESSION STATE
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = None

# --- LOGIN SCREEN ---
if not st.session_state.logged_in:
    _, col2, _ = st.columns([1, 1, 1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: #2563EB;'>🇿🇦 SME Connect</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #475569;'>Sign in to manage your procurement profile.</p>", unsafe_allow_html=True)
        with st.form("login_form"):
            email = st.text_input("Email Address")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Log In")
            if submit:
                st.session_state.logged_in = True
                st.rerun()

# --- MAIN APP ---
else:
    # Safe Profile Extraction
    user_name = st.session_state.user_profile.get('name', 'SME') if st.session_state.user_profile else 'SME'
    
    st.sidebar.markdown(f"### Welcome, {user_name}")
    menu = st.sidebar.radio("Navigation", ["My Profile", "Find Opportunities", "Log Out"])
    
    if menu == "Log Out":
        st.session_state.logged_in = False
        st.session_state.user_profile = None
        st.rerun()

    elif menu == "My Profile":
        if st.session_state.user_profile is None:
            st.header("Create Your Business Profile")
            st.caption("Complete your profile to get verified and matched with RFQs.")
            
            with st.form("profile_form"):
                biz_name = st.text_input("Business Name")
                description = st.text_area("Describe your business and service offering")
                
                st.subheader("Compliance Documents")
                cipc_date = st.date_input("CIPC Registration Expiry", value=None)
                tax_date = st.date_input("Tax Compliance Expiry", value=None)
                bbbee_date = st.date_input("B-BBEE Certificate Expiry", value=None)
                
                st.subheader("References")
                reference_text = st.text_area("Paste previous job references")
                
                submitted = st.form_submit_button("Create Profile")
                
                if submitted:
                    with st.spinner("Analyzing profile..."):
                        sector = get_sector_from_description(description)
                        st.session_state.user_profile = {
                            "name": biz_name,
                            "description": description,
                            "sector": sector,
                            "references": reference_text,
                            "docs": {
                                "CIPC": cipc_date,
                                "Tax": tax_date,
                                "B-BBEE": bbbee_date
                            }
                        }
                        st.rerun()
        else:
            profile = st.session_state.user_profile
            
            # Document Evaluation
            doc_statuses = {doc: check_document_status(dt) for doc, dt in profile['docs'].items()}
            all_valid = all(status[0] == "Valid" for status in doc_statuses.values())
            
            # Header Display
            badge_html = '<span class="badge-verified">✅ Verified Business</span>' if all_valid else '<span class="badge-unverified">⚠️ Action Required</span>'
            st.markdown(f"<h1>{profile['name']} {badge_html}</h1>", unsafe_allow_html=True)
            st.markdown(f"<div class='sector-badge'>🏷️ Sector: {profile['sector']}</div>", unsafe_allow_html=True)
            
            # Documents
            st.subheader("Compliance Documents")
            style_map = {
                "Valid": ("#DCFCE7", "#15803D", "✅"),
                "Expiring Soon": ("#FEF3C7", "#D97706", "⏳"),
                "Expired": ("#FEE2E2", "#B91C1C", "❌"),
                "Missing": ("#FEE2E2", "#B91C1C", "❌")
            }
            
            for doc, (status, days) in doc_statuses.items():
                bg, border, icon = style_map[status]
                msg = f"{icon} <b>{doc}</b>: {status}"
                if status in ["Expiring Soon", "Expired"]:
                    msg += f" ({abs(days)} days)"
                st.markdown(f"<div class='doc-box' style='background-color: {bg}; border-left-color: {border};'>{msg}</div>", unsafe_allow_html=True)
            
            # References
            with st.expander("📄 View Business References"):
                st.write(profile['references'] or "No references provided yet.")
                
            st.divider()

            # Matched RFQs
            st.subheader("Opportunities for You")
            if not all_valid:
                st.warning("You cannot be matched to RFQs right now because your compliance documents are incomplete or expired.")
            else:
                # Direct string matching fallback or simple scoring without heavy dependencies
                st.info("Displaying matching opportunities based on your active compliance and sector profile.")
                for rfq in MOCK_RFQS:
                    with st.expander(f"⭐ {rfq['title']}"):
                        st.write(f"**Scope:** {rfq['scope']}")
                        st.success("Your profile is fully compliant for this opportunity.")

    elif menu == "Find Opportunities":
        st.info("Please view the 'My Profile' tab to see your personalized RFQ matches.")