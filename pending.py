import streamlit as st
import json
from utils.db import get_pending_invoices, update_invoice_irn, delete_invoice
from utils.nic_api import NICAPIClient, simulate_irn_generation

def show():
    st.markdown("<div class='section-header'>📋 Pending Invoices</div>", unsafe_allow_html=True)
    pending = get_pending_invoices()
    if not pending:
        st.success("🎉 No pending invoices. All done!")
        return

    api_cfg  = st.session_state.get("api_config", {})
    has_api  = bool(api_cfg.get("client_id") and api_cfg.get("client_secret"))

    if not has_api:
        st.warning("⚠️ No API credentials. Use **Test Mode (Simulated IRN)** for workflow testing, or configure credentials in 🔗 API Settings.")
    else:
        mode = "🟢 Sandbox" if api_cfg.get("sandbox") else "🔴 Production"
        st.info(f"API configured — Mode: **{mode}**")

    for inv_key, invoice in pending.items():
        doc  = invoice.get("DocDtls",  {})
        val  = invoice.get("ValDtls",  {})
        buy  = invoice.get("BuyerDtls",{})
        sel  = invoice.get("SellerDtls",{})

        with st.expander(f"⏳  {doc.get('Typ','')} | {doc.get('No','')} | {doc.get('Dt','')} | {buy.get('LglNm','')} | ₹{val.get('TotInvVal',0):,.2f}"):
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Doc Type", doc.get("Typ",""))
            c2.metric("Doc No",   doc.get("No",""))
            c3.metric("Date",     doc.get("Dt",""))
            c4.metric("Total",    f"₹{val.get('TotInvVal',0):,.2f}")
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Taxable", f"₹{val.get('AssVal',0):,.2f}")
            c2.metric("IGST",    f"₹{val.get('IgstVal',0):,.2f}")
            c3.metric("CGST",    f"₹{val.get('CgstVal',0):,.2f}")
            c4.metric("SGST",    f"₹{val.get('SgstVal',0):,.2f}")
            st.caption(f"Buyer: **{buy.get('LglNm','')}** | GSTIN: `{buy.get('Gstin','')}`")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("🚀 Live IRN", key=f"live_{inv_key}", disabled=not has_api, use_container_width=True):
                    with st.spinner("Connecting to NIC..."):
                        client = NICAPIClient(api_cfg["gstin"], api_cfg["client_id"],
                                              api_cfg["client_secret"], api_cfg["username"],
                                              api_cfg["password"], sandbox=api_cfg.get("sandbox",True))
                        clean = {k: v for k, v in invoice.items() if not k.startswith("_")}
                        res   = client.generate_irn(clean)
                    if res["success"]:
                        update_invoice_irn(inv_key, res)
                        st.success(f"✅ IRN: `{res['irn']}`"); st.rerun()
                    else:
                        st.error(f"❌ {res['error']}")
            with col2:
                if st.button("🧪 Test Mode", key=f"sim_{inv_key}", use_container_width=True):
                    clean = {k: v for k, v in invoice.items() if not k.startswith("_")}
                    res   = simulate_irn_generation(clean)
                    update_invoice_irn(inv_key, res)
                    st.success("✅ Simulated IRN generated (Test Mode)"); st.rerun()
            with col3:
                clean = {k: v for k, v in invoice.items() if not k.startswith("_")}
                st.download_button("⬇️ JSON", data=json.dumps(clean,indent=2),
                                    file_name=f"einv_{doc.get('No','')}.json",
                                    mime="application/json", key=f"dl_{inv_key}", use_container_width=True)
            with col4:
                if st.button("🗑️ Delete", key=f"del_{inv_key}", use_container_width=True):
                    delete_invoice(inv_key); st.rerun()
            with st.expander("View JSON"):
                st.json({k: v for k, v in invoice.items() if not k.startswith("_")})
