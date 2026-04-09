import streamlit as st
from utils.db import get_supplier, save_supplier
from utils.masters import STATES, STATE_CODES
from utils.nic_api import validate_gstin_format, fetch_gstin_details, parse_fetched

def show():
    st.markdown("<div class='section-header'>⚙️ Supplier / Owner Profile</div>", unsafe_allow_html=True)
    st.caption("One-time setup — auto-filled as seller details on every invoice.")

    supplier = get_supplier()

    # ── GSTIN Lookup ──────────────────────────────────────────────
    st.markdown("### 🔍 GSTIN Auto-fill from GST Portal")
    st.info("Enter your GSTIN and click **Fetch Details** — your registered name and full address will be pulled from the GST portal automatically.")

    col_g, col_b = st.columns([4, 1])
    with col_g:
        lookup_gstin = st.text_input("Enter Your GSTIN *", value=supplier.get("gstin",""),
                                      max_chars=15, placeholder="e.g. 29AAKCR9018A1ZB",
                                      key="sup_gstin_input")
    with col_b:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch_btn = st.button("🔍 Fetch Details", key="sup_fetch_btn",
                               use_container_width=True)

    fmt = validate_gstin_format(lookup_gstin) if lookup_gstin else {}

    if fetch_btn and lookup_gstin:
        if not fmt.get("valid"):
            st.error(f"❌ {fmt.get('error','Invalid GSTIN format')}")
        else:
            with st.spinner(f"Fetching {lookup_gstin.upper()} from GST portal..."):
                raw    = fetch_gstin_details(lookup_gstin.upper())
                parsed = parse_fetched(raw, lookup_gstin.upper())
            st.session_state["_sup_fetched"] = parsed

            if parsed.get("valid") and parsed.get("source") != "local":
                st.success(
                    f"✅ **{parsed.get('legal_name','')}**  |  "
                    f"Status: {parsed.get('status','')}  |  "
                    f"Source: {parsed.get('source','')}"
                )
                if parsed.get("addr"):
                    st.info(
                        f"📍 **Principal Place of Business:**  \n"
                        f"**{parsed.get('addr','')}**  \n"
                        f"{parsed.get('location','')} — {parsed.get('pincode','')}  \n"
                        f"State: **{parsed.get('state_name','')}**"
                    )
            else:
                st.warning(
                    f"⚠️ GSTIN format valid — **{fmt.get('state_name','')}** (State {fmt.get('state_code','')})  \n"
                    f"{parsed.get('error','Could not reach GST portal')}  \n"
                    f"Please fill address manually, or look it up at:  \n"
                    f"https://services.gst.gov.in/services/searchtp"
                )
    elif lookup_gstin and fmt.get("valid"):
        st.caption(f"ℹ️ State from GSTIN: **{fmt.get('state_name','')}** (Code: {fmt.get('state_code','')})")

    fetched = st.session_state.get("_sup_fetched", {})

    def _f(key_f, key_s, default=""):
        if fetched.get("valid") and fetched.get(key_f):
            return fetched[key_f]
        return supplier.get(key_s, default)

    full_addr     = fetched.get("addr","") if fetched.get("valid") else ""
    addr1_default = supplier.get("addr1") or fetched.get("addr1","")
    addr2_default = supplier.get("addr2") or fetched.get("addr2","")
    loc_default   = supplier.get("location") or fetched.get("location","")
    pin_default   = supplier.get("pincode") or fetched.get("pincode","")

    sc_input   = lookup_gstin[:2] if len(lookup_gstin)>=2 else ""
    sc_saved   = supplier.get("state_code","")
    sc_fetched = fetched.get("state_code","") if fetched.get("valid") else ""
    eff_sc     = sc_fetched or sc_saved or sc_input or "29"
    sn_default = STATES.get(eff_sc, "Karnataka")

    # ── Form ─────────────────────────────────────────────────────
    st.markdown("### ✏️ Supplier Details")
    with st.form("supplier_form_v5"):
        c1, c2 = st.columns(2)
        with c1:
            gstin      = st.text_input("GSTIN *", value=lookup_gstin or supplier.get("gstin",""), max_chars=15)
            legal_name = st.text_input("Legal Name *", value=_f("legal_name","legal_name"))
            trade_name = st.text_input("Trade Name",   value=_f("trade_name","trade_name"))
        with c2:
            phone = st.text_input("Phone", value=supplier.get("phone",""))
            email = st.text_input("Email", value=supplier.get("email",""))

        st.markdown("**📍 Registered Address (Principal Place of Business)**")
        c1, c2 = st.columns(2)
        with c1:
            addr1    = st.text_input("Address Line 1 *", value=addr1_default)
            addr2    = st.text_input("Address Line 2",   value=addr2_default)
            location = st.text_input("City / Location *", value=loc_default)
        with c2:
            sl = list(STATES.values())
            idx = sl.index(sn_default) if sn_default in sl else 0
            state_name = st.selectbox("State *", sl, index=idx)
            state_code = STATE_CODES.get(state_name, "29")
            pincode    = st.text_input("Pincode *", value=str(pin_default), max_chars=6)
            st.text_input("State Code (auto)", value=state_code, disabled=True)

        if full_addr:
            st.caption(f"📍 Full address from GST portal: *{full_addr}*")

        if st.form_submit_button("💾 Save Supplier Profile", type="primary", use_container_width=True):
            if not all([gstin, legal_name, addr1, location, pincode]):
                st.error("Fill all required (*) fields.")
            elif len(gstin.strip()) != 15:
                st.error("GSTIN must be 15 characters.")
            else:
                save_supplier({"gstin": gstin.upper(), "legal_name": legal_name,
                                "trade_name": trade_name, "phone": phone, "email": email,
                                "addr1": addr1, "addr2": addr2, "location": location,
                                "state_code": state_code, "pincode": str(pincode)})
                st.success("✅ Supplier profile saved!")
                st.session_state["_sup_fetched"] = {}
                st.rerun()
