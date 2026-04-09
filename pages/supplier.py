import streamlit as st
from utils.db import get_supplier, save_supplier
from utils.masters import STATES, STATE_CODES
from utils.nic_api import validate_gstin_format, fetch_gstin_details, parse_fetched

def _auto_fetch(gstin: str, cache_key: str) -> dict:
    """Fetch GSTIN details with session-state caching. Returns parsed dict or {}."""
    gstin = gstin.strip().upper()
    fmt   = validate_gstin_format(gstin)
    if not fmt.get("valid"):
        return {}
    cached = st.session_state.get(cache_key)
    if cached is not None:
        return cached
    with st.spinner(f"Fetching {gstin} from GST Portal (services.gst.gov.in)..."):
        raw    = fetch_gstin_details(gstin)
        parsed = parse_fetched(raw, gstin)
    st.session_state[cache_key] = parsed
    return parsed


def _show_fetch_result(fetched: dict, fmt: dict):
    """Render the inline result banner after an auto-fetch."""
    if not fetched:
        return
    if fetched.get("valid") and fetched.get("source") != "local":
        st.success(
            f"✅ **{fetched.get('legal_name','')}**  |  "
            f"Status: **{fetched.get('status','')}**  |  "
            f"Source: {fetched.get('source','')}"
        )
        if fetched.get("addr"):
            st.info(
                f"📍 **{fetched.get('addr','')}**  "
                f"{fetched.get('location','')} — {fetched.get('pincode','')}  |  "
                f"State: **{fetched.get('state_name','')}**"
            )
    else:
        st.warning(
            f"⚠️ Could not fetch live data — "
            f"{fetched.get('error', 'GST portal unreachable')}. "
            f"Fill address manually or visit "
            f"[services.gst.gov.in/services/searchtp](https://services.gst.gov.in/services/searchtp)"
        )


def show():
    st.markdown("<div class='section-header'>⚙️ Supplier / Owner Profile</div>", unsafe_allow_html=True)
    st.caption("One-time setup — auto-filled as seller details on every invoice.")

    supplier = get_supplier()

    # ── GSTIN Auto-fetch ──────────────────────────────────────────
    st.markdown("### 🔍 GSTIN Auto-fill from GST Portal")
    st.caption("Details auto-fetch from **services.gst.gov.in** as soon as you finish typing your 15-character GSTIN.")

    lookup_gstin = st.text_input(
        "Enter Your GSTIN *", value=supplier.get("gstin", ""),
        max_chars=15, placeholder="e.g. 29AAKCR9018A1ZB",
        key="sup_gstin_input"
    )
    gstin_upper = lookup_gstin.strip().upper()
    fmt         = validate_gstin_format(gstin_upper) if gstin_upper else {}

    if len(gstin_upper) == 15 and fmt.get("valid"):
        fetched = _auto_fetch(gstin_upper, f"_gst_auto_{gstin_upper}")
        _show_fetch_result(fetched, fmt)
    elif gstin_upper and len(gstin_upper) == 15:
        st.error(fmt.get("error", "Invalid GSTIN format"))
    elif gstin_upper and len(gstin_upper) >= 2:
        sc = gstin_upper[:2]
        sn = STATES.get(sc, "")
        if sn:
            st.caption(f"State from GSTIN prefix: **{sn}** (Code {sc})")

    fetched = st.session_state.get(f"_gst_auto_{gstin_upper}", {})

    def _f(key_f, key_s, default=""):
        if fetched.get("valid") and fetched.get(key_f):
            return fetched[key_f]
        return supplier.get(key_s, default)

    full_addr     = fetched.get("addr", "") if fetched.get("valid") else ""
    addr1_default = _f("addr1", "addr1")
    addr2_default = _f("addr2", "addr2")
    loc_default   = _f("location", "location")
    pin_default   = _f("pincode", "pincode")

    sc_input   = gstin_upper[:2] if len(gstin_upper) >= 2 else ""
    sc_saved   = supplier.get("state_code","")
    sc_fetched = fetched.get("state_code","") if fetched.get("valid") else ""
    eff_sc     = sc_fetched or sc_saved or sc_input or "29"
    sn_default = STATES.get(eff_sc, "Karnataka")

    # ── Form ─────────────────────────────────────────────────────
    st.markdown("### ✏️ Supplier Details")
    with st.form("supplier_form_v5"):
        c1, c2 = st.columns(2)
        with c1:
            gstin      = st.text_input("GSTIN *", value=gstin_upper or supplier.get("gstin",""), max_chars=15)
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
                st.rerun()
