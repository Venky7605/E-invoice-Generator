import streamlit as st
import json
import pandas as pd
from utils.db import get_generated_invoices, get_cancelled_invoices, cancel_invoice
from utils.nic_api import NICAPIClient

CANCEL_REASONS = {
    "1": "Duplicate",
    "2": "Data Entry Mistake",
    "3": "Order Cancelled",
    "4": "Others",
}


def show():
    st.markdown("<div class='main-header'><h1>🚫 IRN Cancellation</h1>"
                "<p>Cancel e-invoices registered on the NIC portal within the allowed window</p></div>",
                unsafe_allow_html=True)

    st.warning(
        "IRN cancellation is only permitted **within 24 hours** of generation. "
        "After 24 hours, the IRN is permanently valid and cannot be cancelled. "
        "Use Credit/Debit Notes for adjustments after 24 hours."
    )

    api_cfg  = st.session_state.get("api_config", {})
    has_api  = bool(api_cfg.get("client_id") and api_cfg.get("client_secret"))
    generated = get_generated_invoices()
    cancelled = get_cancelled_invoices()

    tab1, tab2 = st.tabs(["🚫 Cancel IRN", "📋 Cancelled Invoices"])

    with tab1:
        if not generated:
            st.info("No IRN-generated invoices available to cancel.")
            return

        if not has_api:
            st.error("API credentials required to cancel IRN. Configure them in API Settings.")

        st.markdown("<div class='section-header'>Select Invoice to Cancel</div>",
                    unsafe_allow_html=True)

        rows = []
        for k, v in generated.items():
            doc  = v.get("DocDtls", {})
            val  = v.get("ValDtls", {})
            buy  = v.get("BuyerDtls", {})
            irnd = v.get("_irn_data", {})
            rows.append({
                "_key":  k,
                "Type":  doc.get("Typ", ""),
                "Doc No": doc.get("No", ""),
                "Date":  doc.get("Dt", ""),
                "Buyer": buy.get("LglNm", "")[:35],
                "Total": f"₹{float(val.get('TotInvVal', 0)):,.2f}",
                "Mode":  "Test" if irnd.get("simulated") else "Live",
                "IRN":   (irnd.get("irn", "")[:24] + "...") if irnd.get("irn") else "—",
                "Ack Date": irnd.get("ack_dt", ""),
            })

        df_disp = pd.DataFrame([{k: v for k, v in r.items() if k != "_key"} for r in rows])
        st.dataframe(df_disp, use_container_width=True, hide_index=True)
        st.divider()

        opts     = [f"{r['Doc No']}  —  {r['Buyer']}  —  {r['Date']}" for r in rows]
        sel_lbl  = st.selectbox("Choose Invoice to Cancel", opts, key="cancel_sel")
        sel_idx  = opts.index(sel_lbl)
        sel_key  = rows[sel_idx]["_key"]
        sel_inv  = generated[sel_key]
        sel_irnd = sel_inv.get("_irn_data", {})
        sel_irn  = sel_irnd.get("irn", "")
        sel_doc  = sel_inv.get("DocDtls", {})

        st.markdown("**Selected Invoice Details**")
        c1, c2, c3 = st.columns(3)
        c1.info(f"**IRN:** `{sel_irn[:30]}...`")
        c2.info(f"**Ack No:** {sel_irnd.get('ack_no','')}")
        c3.info(f"**Ack Date:** {sel_irnd.get('ack_dt','')}")

        if sel_irnd.get("simulated"):
            st.warning("This is a simulated (test) IRN. Cancellation will be processed locally only.")

        st.divider()
        st.markdown("**Cancellation Details**")
        cc1, cc2 = st.columns(2)
        with cc1:
            reason_label = st.selectbox(
                "Cancellation Reason *",
                list(CANCEL_REASONS.values()),
                key="cancel_reason"
            )
            reason_code = {v: k for k, v in CANCEL_REASONS.items()}[reason_label]
        with cc2:
            remark = st.text_input(
                "Cancellation Remark *",
                placeholder="Brief reason for cancellation",
                max_chars=100,
                key="cancel_remark"
            )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚫 Cancel IRN on NIC Portal",
                         type="primary", disabled=not has_api or not remark,
                         use_container_width=True, key="cancel_live_btn"):
                with st.spinner("Cancelling IRN on NIC Portal..."):
                    client = NICAPIClient(
                        api_cfg["gstin"], api_cfg["client_id"],
                        api_cfg["client_secret"], api_cfg["username"],
                        api_cfg["password"], sandbox=api_cfg.get("sandbox", True)
                    )
                    auth = client.authenticate()
                    if not auth["success"]:
                        st.error(f"Auth failed: {auth['error']}")
                    else:
                        res = client.cancel_irn(sel_irn, reason_code, remark)
                        if res["success"]:
                            cancel_data = {
                                "irn": sel_irn,
                                "reason_code": reason_code,
                                "reason_label": reason_label,
                                "remark": remark,
                                "live": True,
                                "api_response": res.get("data", {}),
                            }
                            cancel_invoice(sel_key, cancel_data)
                            st.success("IRN cancelled successfully on NIC Portal.")
                            st.rerun()
                        else:
                            st.error(f"Cancellation failed: {res.get('error','Unknown error')}")

        with col2:
            if st.button("🧪 Mark as Cancelled (Local Only)",
                         disabled=not remark,
                         use_container_width=True, key="cancel_local_btn"):
                cancel_data = {
                    "irn": sel_irn,
                    "reason_code": reason_code,
                    "reason_label": reason_label,
                    "remark": remark,
                    "live": False,
                    "simulated": sel_irnd.get("simulated", False),
                }
                cancel_invoice(sel_key, cancel_data)
                st.success("Invoice marked as cancelled locally.")
                st.rerun()

        if not remark:
            st.caption("Enter a cancellation remark to enable the cancel buttons.")

    with tab2:
        st.markdown("<div class='section-header'>Cancelled Invoices</div>",
                    unsafe_allow_html=True)
        if not cancelled:
            st.info("No cancelled invoices.")
        else:
            cancel_rows = []
            for k, v in cancelled.items():
                doc  = v.get("DocDtls", {})
                val  = v.get("ValDtls", {})
                buy  = v.get("BuyerDtls", {})
                cd   = v.get("_cancel_data", {})
                cancel_rows.append({
                    "Doc No":         doc.get("No", ""),
                    "Date":           doc.get("Dt", ""),
                    "Buyer":          buy.get("LglNm", "")[:35],
                    "Total":          f"₹{float(val.get('TotInvVal', 0)):,.2f}",
                    "Cancel Reason":  cd.get("reason_label", ""),
                    "Remark":         cd.get("remark", ""),
                    "Cancelled At":   v.get("_cancelled_at", "")[:19],
                    "Live Cancel":    "Yes" if cd.get("live") else "Local Only",
                })
            st.dataframe(pd.DataFrame(cancel_rows), use_container_width=True, hide_index=True)
            st.caption(f"{len(cancelled)} cancelled invoice(s)")

            st.divider()
            for k, v in cancelled.items():
                doc = v.get("DocDtls", {}); cd = v.get("_cancel_data", {})
                with st.expander(f"{doc.get('No','')} — {v.get('BuyerDtls',{}).get('LglNm','')}"):
                    st.code(cd.get("irn", ""), language=None)
                    st.write(f"Reason: **{cd.get('reason_label','')}** | Remark: {cd.get('remark','')}")
                    st.download_button(
                        "Download Cancellation Record",
                        data=json.dumps(cd, indent=2),
                        file_name=f"cancel_{doc.get('No','').replace('/','_')}.json",
                        mime="application/json",
                        key=f"dl_cancel_{k}",
                    )
