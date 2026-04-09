import streamlit as st
import pandas as pd
from utils.db import get_recipients, save_recipient, delete_recipient
from utils.masters import STATES, STATE_CODES
from utils.nic_api import validate_gstin_format, fetch_gstin_details, parse_fetched

def show():
    st.markdown("<div class='section-header'>👥 Recipient Master</div>", unsafe_allow_html=True)
    st.caption("Save buyers here — fetches full address from GST portal automatically.")

    tab1, tab2 = st.tabs(["➕ Add / Edit Recipient", "📋 All Recipients"])

    with tab1:
        recipients = get_recipients()
        opts = ["-- New Recipient --"] + list(recipients.keys())
        sel  = st.selectbox("Load existing to edit", opts, key="rec_load_sel")

        prev = st.session_state.get("_rec_prev_sel", "")
        if sel != prev:
            st.session_state["_rec_prev_sel"] = sel

        ex = recipients.get(sel, {}) if sel != "-- New Recipient --" else {}

        # ── GSTIN Auto-fetch ─────────────────────────────────────
        st.markdown("### 🔍 GSTIN Auto-fill from GST Portal")
        st.caption("Details auto-fetch from **services.gst.gov.in** as soon as all 15 characters are entered.")

        lookup_gstin = st.text_input(
            "Enter GSTIN *",
            value=ex.get("gstin", sel if sel != "-- New Recipient --" else ""),
            max_chars=15, placeholder="e.g. 33AAACC1226H3Z9",
            key="rec_lookup_gstin",
            help="Name & address will be fetched automatically from the GST portal"
        )

        gstin_upper    = lookup_gstin.strip().upper()
        fmt            = validate_gstin_format(gstin_upper) if gstin_upper else {}
        rec_cache_key  = f"_gst_auto_{gstin_upper}"

        if len(gstin_upper) == 15 and fmt.get("valid"):
            if st.session_state.get(rec_cache_key) is None:
                with st.spinner(f"Fetching {gstin_upper} from GST Portal..."):
                    raw    = fetch_gstin_details(gstin_upper)
                    parsed = parse_fetched(raw, gstin_upper)
                st.session_state[rec_cache_key] = parsed

            fetched = st.session_state.get(rec_cache_key, {})
            if fetched.get("valid") and fetched.get("source") != "local":
                st.success(
                    f"✅ **{fetched.get('legal_name','')}**  |  "
                    f"Status: **{fetched.get('status','')}**  |  "
                    f"Source: {fetched.get('source','')}"
                )
                if fetched.get("addr"):
                    st.info(
                        f"📍 **{fetched.get('addr','')}**  "
                        f"— {fetched.get('location','')} {fetched.get('pincode','')}  "
                        f"| State: **{fetched.get('state_name','')}**"
                    )
            else:
                st.warning(
                    f"⚠️ Could not fetch live data — "
                    f"{fetched.get('error', 'GST portal unreachable')}. "
                    f"Fill address manually or visit "
                    f"[services.gst.gov.in/services/searchtp](https://services.gst.gov.in/services/searchtp)"
                )
        elif gstin_upper and len(gstin_upper) >= 2:
            st.caption(f"State: **{fmt.get('state_name', '')}** (Code {fmt.get('state_code', '')})")

        fetched = st.session_state.get(rec_cache_key, {}) if len(gstin_upper) == 15 else {}

        def _f(key_f, key_ex, default=""):
            if fetched.get("valid") and fetched.get(key_f):
                return fetched[key_f]
            return ex.get(key_ex, default)

        full_addr     = fetched.get("addr", "") if fetched.get("valid") else ""
        addr1_default = _f("addr1", "addr1")
        addr2_default = _f("addr2", "addr2")
        loc_default   = _f("location", "location")
        pin_default   = _f("pincode", "pincode")

        sc_input   = gstin_upper[:2] if len(gstin_upper) >= 2 else ""
        sc_saved   = ex.get("state_code", "")
        sc_fetched = fetched.get("state_code", "") if fetched.get("valid") else ""
        eff_sc     = sc_fetched or sc_saved or sc_input or "29"
        sn_default = STATES.get(eff_sc, "Karnataka")

        # ── Form ─────────────────────────────────────────────────
        st.markdown("### ✏️ Recipient Details")
        with st.form("rec_form_v5"):
            c1, c2 = st.columns(2)
            with c1:
                gstin      = st.text_input("GSTIN *", value=_f("gstin","gstin", lookup_gstin), max_chars=15)
                legal_name = st.text_input("Legal Name *", value=_f("legal_name","legal_name"))
                trade_name = st.text_input("Trade Name",   value=_f("trade_name","trade_name"))
            with c2:
                phone = st.text_input("Phone", value=ex.get("phone",""))
                email = st.text_input("Email", value=ex.get("email",""))

            st.markdown("**📍 Registered Address (Principal Place of Business)**")
            c1, c2 = st.columns(2)
            with c1:
                addr1    = st.text_input("Address Line 1 *", value=addr1_default)
                addr2    = st.text_input("Address Line 2",   value=addr2_default)
                location = st.text_input("City / Location *", value=loc_default)
            with c2:
                sl  = list(STATES.values())
                idx = sl.index(sn_default) if sn_default in sl else 0
                state_name = st.selectbox("State *", sl, index=idx)
                state_code = STATE_CODES.get(state_name, "29")
                pincode    = st.text_input("Pincode *", value=str(pin_default), max_chars=6)
                st.text_input("State Code (auto)", value=state_code, disabled=True)

            if full_addr:
                st.caption(f"📍 Full address from GST portal: *{full_addr}*")

            col1, col2 = st.columns([3, 1])
            with col1: save   = st.form_submit_button("💾 Save to Recipient Master", type="primary", use_container_width=True)
            with col2: delete = st.form_submit_button("🗑️ Delete", use_container_width=True)

            if save:
                if not all([gstin, legal_name, addr1, location, pincode]):
                    st.error("Fill all required (*) fields.")
                elif len(gstin.strip()) != 15:
                    st.error("GSTIN must be 15 characters.")
                elif not str(pincode).strip().isdigit() or len(str(pincode).strip()) != 6:
                    st.error("Pincode must be 6 digits.")
                else:
                    save_recipient(gstin.upper(), {
                        "gstin": gstin.upper(), "legal_name": legal_name,
                        "trade_name": trade_name, "phone": phone, "email": email,
                        "addr1": addr1, "addr2": addr2, "location": location,
                        "state_code": state_code, "pincode": str(pincode)
                    })
                    st.success(f"✅ Recipient **{gstin.upper()}** saved!")
                    st.rerun()

            if delete and sel != "-- New Recipient --":
                delete_recipient(sel)
                st.success(f"Deleted {sel}")
                st.rerun()

    with tab2:
        recipients = get_recipients()
        if not recipients:
            st.info("No recipients saved yet.")
        else:
            rows = [{"GSTIN": k, "Legal Name": v.get("legal_name",""),
                     "Address": f"{v.get('addr1','')} {v.get('addr2','')}".strip()[:50],
                     "Location": v.get("location",""),
                     "State": STATES.get(v.get("state_code",""),""),
                     "Pincode": v.get("pincode",""), "Phone": v.get("phone","")}
                    for k, v in recipients.items()]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.caption(f"Total: {len(recipients)} recipients")
