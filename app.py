import streamlit as st
import anthropic
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer, util

# 1. SETUP & CONFIG
load_dotenv()
client = anthropic.Anthropic()

st.set_page_config(page_title="SA Procurement Engine", page_icon="🇿🇦", layout="wide")

# Custom CSS for extra polish
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    .badge-verified { background-color: #E8F5E9; color: #007A4D; padding: 5px 10px; border-radius: 15px; font-size: 0.8em; font-weight: bold; vertical-align: middle; margin-left: 10px;}
    .badge-unverified { background-color: #FFEBEE; color: #D32F2F; padding: 5px 10px; border-radius: 15px; font-size: 0.8em; font-weight: bold; vertical-align: middle; margin-left: 10px;}
    .sector-badge { background-color: #003366; color: white; padding: 5px 15px; border-radius: 20px; font-size: 0.9em; font-weight: bold; display: inline-block; margin-bottom: 20px;}
    .doc-box { padding: 10px; border-radius: 5px; margin-bottom: 10px; border-left: 5px solid;}
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def load_model():
    return SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
model = load_model()

# 2. HELPER FUNCTIONS
def get_sector_from_description(description):
    """Uses AI to assign a sector badge"""
    prompt = f"Categorize this business into ONE short sector (e.g., 'Marketing', 'Manufacturing', 'Renewable Energy'). Return ONLY the sector name. Description: {description}"
    try:
        res = client.messages.create(model="claude-3-haiku-20240307", max_tokens=10, messages=[{"role": "user", "content": prompt}])
        return res.content[0].text.strip()
    except:
        return "General Services"

def check_document_status(expiry_date_str):
    """Returns status and days left for a document"""
    if not expiry_date_str: return "Missing", 0
    try:
        expiry = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
        today = datetime.today().date()
        days_left = (expiry - today).days
        
        if days_left < 0: return "Expired", days_left
        elif days_left < 60: return "Expiring Soon", days_left
        else: return "Valid", days_left
    except:
        return "Invalid Format", 0

# 3. MOCK DATABASE
MOCK_RFQS = [
    {"id": 1, "title": "Solar Panel Servicing - Gauteng", "scope": "Photovoltaic maintenance and solar power servicing."},
    {"id": 2, "title": "Corporate Website Redesign", "scope": "UX/UI design and frontend development for corporate portal."}
]

# 4. SESSION STATE (Handles Login & Profile Data)
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_profile' not in st.session_state: st.session_state.user_profile = None

# --- LOGIN SCREEN ---
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: #003366;'>🇿🇦 SME Connect</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Sign in to manage your procurement profile.</p>", unsafe_allow_html=True)
        with st.form("login_form"):
            email = st.text_input("Email Address")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Log In")
            if submit:
                st.session_state.logged_in = True
                st.rerun()

# --- MAIN APP ---
else:
    # Sidebar Navigation
    st.sidebar.markdown(f"### Welcome, {st.session_state.user_profile['name'] if st.session_state.user_profile else 'SME'}")
    menu = st.sidebar.radio("Navigation", ["My Profile", "Find Opportunities", "Log Out"])
    
    if menu == "Log Out":
        st.session_state.logged_in = False
        st.session_state.user_profile = None
        st.rerun()

    # --- PROFILE CREATION / VIEW ---
    elif menu == "My Profile":
        if st.session_state.user_profile is None:
            st.header("Create Your Business Profile")
            st.write("Complete your profile to get verified and matched with RFQs.")
            
            with st.form("profile_form"):
                biz_name = st.text_input("Business Name")
                description = st.text_area("Describe your business and service offering (This helps our AI match you accurately)")
                
                st.subheader("Compliance Documents")
                # For the demo, we use date inputs to simulate document expiry
                cipc_date = st.date_input("CIPC Registration Expiry (or leave blank if missing)")
                tax_date = st.date_input("Tax Compliance Expiry")
                bbbee_date = st.date_input("B-BBEE Certificate Expiry")
                
                st.subheader("References")
                reference_text = st.text_area("Paste previous job references (e.g., 'Completed solar install for Corp X')")
                
                submitted = st.form_submit_button("Create Profile")
                
                if submitted:
                    with st.spinner("AI is analyzing your business to assign a sector..."):
                        sector = get_sector_from_description(description)
                        
                        st.session_state.user_profile = {
                            "name": biz_name,
                            "description": description,
                            "sector": sector,
                            "references": reference_text,
                            "docs": {
                                "CIPC": str(cipc_date) if cipc_date else None,
                                "Tax": str(tax_date) if tax_date else None,
                                "B-BBEE": str(bbbee_date) if bbbee_date else None
                            }
                        }
                        st.rerun()
        else:
            # --- THE PROFILE VIEW ---
            profile = st.session_state.user_profile
            
            # 1. Evaluate Docs
            doc_statuses = {doc: check_document_status(date) for doc, date in profile['docs'].items()}
            all_valid = all(status[0] == "Valid" for status in doc_statuses.values())
            
            # 2. Header
            badge_html = '<span class="badge-verified">✅ Verified Business</span>' if all_valid else '<span class="badge-unverified">⚠️ Action Required</span>'
            st.markdown(f"<h1>{profile['name']} {badge_html}</h1>", unsafe_allow_html=True)
            
            # 3. Sector Badge
            st.markdown(f"<div class='sector-badge'>🏷️ Sector: {profile['sector']}</div>", unsafe_allow_html=True)
            
            # 4. Documents Section
            st.subheader("Compliance Documents")
            for doc, (status, days) in doc_statuses.items():
                if status == "Valid":
                    st.markdown(f"<div class='doc-box' style='background-color: #E8F5E9; border-left-color: #007A4D;'>✅ <b>{doc}</b>: Valid</div>", unsafe_allow_html=True)
                elif status == "Expiring Soon":
                    st.markdown(f"<div class='doc-box' style='background-color: #FFF3E0; border-left-color: #FF9800;'>⏳ <b>{doc}</b>: Expiring in {days} days! Please update.</div>", unsafe_allow_html=True)
                elif status == "Expired":
                    st.markdown(f"<div class='doc-box' style='background-color: #FFEBEE; border-left-color: #D32F2F;'>❌ <b>{doc}</b>: Expired {abs(days)} days ago. Please upload a new one.</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='doc-box' style='background-color: #FFEBEE; border-left-color: #D32F2F;'>❌ <b>{doc}</b>: Missing. Please upload.</div>", unsafe_allow_html=True)
            
            # 5. References Section
            with st.expander("📄 View Business References"):
                st.write(profile['references'] if profile['references'] else "No references provided yet.")
                
            st.write("---")

            # 6. Matched RFQs
            st.subheader("Opportunities for You")
            
            if not all_valid:
                st.warning("You cannot be matched to RFQs right now because your compliance documents are not all valid. Please update the missing/expired documents above.")
            else:
                with st.spinner("Matching your profile against available RFQs..."):
                    rfq_texts = [f"{r['title']} - {r['scope']}" for r in MOCK_RFQS]
                    rfq_embs = model.encode(rfq_texts)
                    profile_emb = model.encode(profile['description'])
                    
                    sims = util.cos_sim(profile_emb, rfq_embs)[0]
                    results = [{"rfq": MOCK_RFQS[i], "score": float(sims[i])} for i in range(len(MOCK_RFQS))]
                    results.sort(key=lambda x: x['score'], reverse=True)
                    
                    matches_found = False
                    for res in results:
                        if res['score'] > 0.3: # Threshold for matching
                            matches_found = True
                            with st.expander(f"⭐ {res['rfq']['title']} (Match: {res['score']:.2f})"):
                                st.write(f"**Scope:** {res['rfq']['scope']}")
                                st.success("Your profile matches this opportunity. You can apply.")
                    
                    if not matches_found:
                        st.info("There are currently no RFQs that match your specific service offering. Check back soon!")

    # --- OPPORTUNITIES VIEW (Duplicate for Demo purposes) ---
    elif menu == "Find Opportunities":
        st.info("Please view the 'My Profile' tab to see your personalized RFQ matches.")