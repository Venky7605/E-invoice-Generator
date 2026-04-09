import streamlit as st
import pandas as pd
from utils.db import get_hsn_master, save_hsn, delete_hsn
from utils.masters import COMMON_HSN, UQC_CODES, GST_RATES

def show():
    st.markdown("<div class='section-header'>📦 HSN / SAC Master</div>", unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["➕ Add / Edit", "📋 My Codes", "📖 Common Reference"])

    with tab1:
        hsn_data = get_hsn_master()
        opts = ["-- New --"] + list(hsn_data.keys())
        sel  = st.selectbox("Load existing", opts)
        ex   = hsn_data.get(sel, {}) if sel != "-- New --" else {}
        with st.form("hsn_form"):
            c1, c2 = st.columns(2)
            with c1:
                code = st.text_input("HSN / SAC Code *", value=ex.get("code", sel if sel != "-- New --" else ""), max_chars=8)
                desc = st.text_input("Description *", value=ex.get("description",""))
            with c2:
                rate = st.selectbox("GST Rate (%)", GST_RATES, index=GST_RATES.index(ex.get("gst_rate",18)) if ex.get("gst_rate",18) in GST_RATES else 7)
                uqc  = st.selectbox("Default UQC", UQC_CODES, index=UQC_CODES.index(ex.get("uqc","UNT")) if ex.get("uqc","UNT") in UQC_CODES else 0)
                is_s = st.checkbox("Service (SAC code)", value=ex.get("is_service", False))
            c1, c2 = st.columns([3,1])
            with c1: save   = st.form_submit_button("💾 Save", type="primary", use_container_width=True)
            with c2: delete = st.form_submit_button("🗑️ Delete", use_container_width=True)
            if save:
                if not code or not desc: st.error("Code and description required.")
                else:
                    save_hsn(code, {"code": code, "description": desc, "gst_rate": rate, "uqc": uqc, "is_service": is_s})
                    st.success(f"✅ Saved {code}"); st.rerun()
            if delete and sel != "-- New --":
                delete_hsn(sel); st.success("Deleted"); st.rerun()

    with tab2:
        hsn_data = get_hsn_master()
        if not hsn_data:
            st.info("No HSN codes saved.")
        else:
            rows = [{"Code": k, "Description": v.get("description",""), "GST%": f"{v.get('gst_rate',0)}%",
                     "UQC": v.get("uqc",""), "Type": "Service" if v.get("is_service") else "Goods"}
                    for k, v in hsn_data.items()]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab3:
        st.markdown("**Common HSN/SAC codes — click Import to add all**")
        rows = [{"Code": k, "Description": v["desc"], "GST%": f"{v['rate']}%", "Type": "Service" if v["type"]=="S" else "Goods"}
                for k, v in COMMON_HSN.items()]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        if st.button("📥 Import all common codes to my master", type="primary"):
            for k, v in COMMON_HSN.items():
                save_hsn(k, {"code": k, "description": v["desc"], "gst_rate": v["rate"],
                              "uqc": "UNT" if v["type"]=="S" else "NOS", "is_service": v["type"]=="S"})
            st.success("✅ Imported!"); st.rerun()
