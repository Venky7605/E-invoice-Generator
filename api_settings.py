import streamlit as st

def show():
    st.markdown("<div class='section-header'>🔗 NIC e-Invoice API Settings</div>", unsafe_allow_html=True)
    with st.expander("ℹ️ How to get API credentials"):
        st.markdown("""
1. Login → **https://einvoice1.gst.gov.in**
2. Go to **User Credentials → Create API User**
3. Enter GSTIN, generate **Client ID** + **Client Secret**
4. Set a separate **API Username** + **Password**
5. Use **Sandbox** for testing first, then switch to Production
        """)
    cfg = st.session_state.get("api_config", {})
    with st.form("api_form"):
        c1,c2 = st.columns(2)
        with c1:
            gstin  = st.text_input("GSTIN *",        value=cfg.get("gstin",""),        max_chars=15)
            cid    = st.text_input("Client ID *",     value=cfg.get("client_id",""))
            uname  = st.text_input("API Username *",  value=cfg.get("username",""))
        with c2:
            csec   = st.text_input("Client Secret *", value=cfg.get("client_secret",""), type="password")
            pwd    = st.text_input("API Password *",  value=cfg.get("password",""),      type="password")
            sbx    = st.checkbox("Use Sandbox Mode",  value=cfg.get("sandbox", True))
        if sbx: st.info("🧪 Sandbox — test environment, IRNs not legally valid.")
        else:   st.warning("🔴 Production — live IRNs. Use carefully.")
        c1,c2 = st.columns(2)
        with c1: save = st.form_submit_button("💾 Save", type="primary", use_container_width=True)
        with c2: test = st.form_submit_button("🧪 Test Connection", use_container_width=True)
        if save:
            st.session_state["api_config"] = {"gstin": gstin.upper(), "client_id": cid,
                "client_secret": csec, "username": uname, "password": pwd, "sandbox": sbx}
            st.success("✅ API settings saved!")
        if test:
            if not all([gstin,cid,csec,uname,pwd]): st.error("Fill all fields first.")
            else:
                from utils.nic_api import NICAPIClient
                with st.spinner("Testing..."):
                    r = NICAPIClient(gstin, cid, csec, uname, pwd, sbx).authenticate()
                if r["success"]: st.success("✅ Authentication successful!")
                else:            st.error(f"❌ {r['error']}")

    st.divider()
    st.markdown("#### 🏛️ Alternate GSTN-Approved IRPs (browser-based, work on Mac)")
    st.markdown("""
| IRP | URL | Free |
|-----|-----|------|
| NIC Primary   | einvoice1.gst.gov.in | ✅ |
| NIC Secondary | einvoice2.gst.gov.in | ✅ |
| ClearIRP      | einvoice.clearirp.in | ✅ |
| IRIS IRP      | einvoice.iris-business.com | ✅ |
| Cygnet IRP    | einvoice.cygnet.one | ✅ |
    """)
