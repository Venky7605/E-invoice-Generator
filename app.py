import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(page_title="GePP Tool — GST e-Invoice", page_icon="🧾",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
.main-header{background:linear-gradient(135deg,#1a3c5e 0%,#2563eb 100%);padding:1rem 1.5rem;
border-radius:10px;margin-bottom:1.2rem;color:white}
.main-header h1{margin:0;font-size:1.5rem;color:white}
.main-header p{margin:.2rem 0 0 0;font-size:.82rem;opacity:.85;color:white}
.metric-card{background:white;border:1px solid #e2e8f0;border-radius:8px;padding:.9rem;
text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.metric-num{font-size:1.9rem;font-weight:700;color:#1a3c5e}
.metric-label{font-size:.75rem;color:#64748b;margin-top:.2rem}
.section-header{font-size:1rem;font-weight:700;color:#1a3c5e;border-bottom:2px solid #2563eb;
padding-bottom:.35rem;margin-bottom:.9rem}
.tag-igst{background:#dbeafe;color:#1e40af;padding:2px 8px;border-radius:10px;font-size:.75rem;font-weight:600}
.tag-cgst{background:#dcfce7;color:#166534;padding:2px 8px;border-radius:10px;font-size:.75rem;font-weight:600}
.tag-pending{background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:10px;font-size:.75rem;font-weight:600}
.tag-irn{background:#d1fae5;color:#065f46;padding:2px 8px;border-radius:10px;font-size:.75rem;font-weight:600}
div[data-testid="stSidebar"]{background:#f8fafc}
.stButton>button{border-radius:6px;font-weight:600}
</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("""<div style='text-align:center;padding:.8rem 0 .4rem'>
    <div style='font-size:2.2rem'>🧾</div>
    <div style='font-weight:700;font-size:1rem;color:#1a3c5e'>GePP Tool</div>
    <div style='font-size:.72rem;color:#64748b'>GST e-Invoice · Python Edition</div>
    </div>""", unsafe_allow_html=True)
    st.divider()
    st.markdown("<div style='font-size:.65rem;font-weight:700;color:#94a3b8;letter-spacing:.08em;padding:.4rem 0 .1rem'>INVOICING</div>", unsafe_allow_html=True)
    page = st.radio("Navigation", [
        "🏠  Dashboard",
        "⚙️  Supplier Profile",
        "📝  Create Invoice",
        "📥  Import from Excel",
        "📋  Pending Invoices",
        "🏛️  GPP — Portal Processing",
        "✅  Generated Invoices",
        "🚫  IRN Cancellation",
        "─── COMPLIANCE ───",
        "📊  GSTR-1 Export",
        "📈  Analytics",
        "⚡  Bulk Operations",
        "─── MASTER DATA ───",
        "👥  Recipient Master",
        "📦  HSN Master",
        "🔗  API Settings",
    ], label_visibility="collapsed")
    st.divider()
    st.markdown("<div style='font-size:.68rem;color:#94a3b8;text-align:center'>GePP Python v2.0<br>NIC e-Invoice API Compatible</div>", unsafe_allow_html=True)

if   "Dashboard"          in page: from pages import dashboard;    dashboard.show()
elif "Supplier Profile"   in page: from pages import supplier;     supplier.show()
elif "Create Invoice"     in page: from pages import create_inv;   create_inv.show()
elif "Import from Excel"  in page: from pages import excel_page;   excel_page.show()
elif "Pending Invoices"   in page: from pages import pending;      pending.show()
elif "GPP"                in page: from pages import gpp;          gpp.show()
elif "Generated Invoices" in page: from pages import generated;    generated.show()
elif "IRN Cancellation"   in page: from pages import irn_cancel;   irn_cancel.show()
elif "GSTR-1"             in page: from pages import gstr1;        gstr1.show()
elif "Analytics"          in page: from pages import analytics;    analytics.show()
elif "Bulk Operations"    in page: from pages import bulk_ops;     bulk_ops.show()
elif "Recipient Master"   in page: from pages import recipients;   recipients.show()
elif "HSN Master"         in page: from pages import hsn;          hsn.show()
elif "API Settings"       in page: from pages import api_settings; api_settings.show()
elif "───"               in page:
    st.info("Select a page from the sidebar.")
