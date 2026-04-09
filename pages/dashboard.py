import streamlit as st
import pandas as pd
from utils.db import get_invoices, get_supplier, get_recipients, get_hsn_master

def show():
    st.markdown("""<div class='main-header'>
    <h1>🧾 GePP Tool — GST e-Invoice Preparing & Printing</h1>
    <p>Python Edition · macOS / Linux / Windows · NIC IRP Compatible</p>
    </div>""", unsafe_allow_html=True)

    invoices   = get_invoices()
    supplier   = get_supplier()
    recipients = get_recipients()
    hsn        = get_hsn_master()
    pending    = sum(1 for v in invoices.values() if v.get("_status")=="PENDING")
    generated  = sum(1 for v in invoices.values() if v.get("_status")=="IRN_GENERATED")

    c1,c2,c3,c4 = st.columns(4)
    for col, num, label in [(c1,pending,"⏳ Pending"),(c2,generated,"✅ IRN Generated"),
                             (c3,len(recipients),"👥 Recipients"),(c4,len(hsn),"📦 HSN Codes")]:
        col.markdown(f"<div class='metric-card'><div class='metric-num'>{num}</div><div class='metric-label'>{label}</div></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<div class='section-header'>🏢 Supplier Profile</div>", unsafe_allow_html=True)
        if supplier:
            st.success(f"**{supplier.get('legal_name','')}**  \nGSTIN: `{supplier.get('gstin','')}` | {supplier.get('location','')} | State: {supplier.get('state_code','')}")
        else:
            st.warning("⚠️ Supplier profile not configured. Please set it up first.")
    with col2:
        st.markdown("<div class='section-header'>📋 Quick Start</div>", unsafe_allow_html=True)
        st.info("1️⃣ **⚙️ Supplier Profile** → set your GSTIN & address\n\n2️⃣ **👥 Recipients** → add buyer masters\n\n3️⃣ **📦 HSN Master** → add your HSN/SAC codes\n\n4️⃣ **📝 Create Invoice** → fill & generate JSON\n\n5️⃣ **📋 Pending** → submit to NIC & get IRN\n\n6️⃣ **✅ Generated** → download e-Invoice PDF")

    if invoices:
        st.markdown("<div class='section-header'>🕐 Recent Invoices</div>", unsafe_allow_html=True)
        rows = []
        for k, v in list(invoices.items())[-15:]:
            doc = v.get("DocDtls",{}); val = v.get("ValDtls",{}); irn_d = v.get("_irn_data",{})
            rows.append({"Type": doc.get("Typ",""), "Doc No": doc.get("No",""),
                "Date": doc.get("Dt",""), "Buyer": v.get("BuyerDtls",{}).get("LglNm","")[:30],
                "Amount": f"₹{val.get('TotInvVal',0):,.2f}",
                "Status": "✅ IRN Generated" if v.get("_status")=="IRN_GENERATED" else "⏳ Pending",
                "IRN": (irn_d.get("irn","")[:16]+"...") if irn_d.get("irn") else "—"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
