import streamlit as st
import json
import pandas as pd
from datetime import datetime, date
from utils.db import (
    get_invoices, get_pending_invoices, get_generated_invoices,
    update_invoice_irn, delete_invoice, get_supplier
)
from utils.nic_api import NICAPIClient, simulate_irn_generation
from utils.pdf_gen import generate_einvoice_pdf


def show():
    st.markdown("<div class='main-header'><h1>🏛️ Government Portal Processing (GPP)</h1>"
                "<p>Batch IRN submission · Status tracking · Lifecycle management</p></div>",
                unsafe_allow_html=True)

    supplier = get_supplier()
    if not supplier:
        st.error("Set up your Supplier Profile first (Supplier Profile in the sidebar).")
        return

    invoices  = get_invoices()
    pending   = {k: v for k, v in invoices.items() if v.get("_status") == "PENDING"}
    generated = {k: v for k, v in invoices.items() if v.get("_status") == "IRN_GENERATED"}

    api_cfg = st.session_state.get("api_config", {})
    has_api = bool(api_cfg.get("client_id") and api_cfg.get("client_secret"))

    _render_stats(invoices, pending, generated)

    tab1, tab2, tab3 = st.tabs(["📤 Batch Submit to Portal", "📊 All Invoices", "📈 Summary Report"])

    with tab1:
        _render_batch_submit(pending, api_cfg, has_api)

    with tab2:
        _render_all_invoices(invoices, api_cfg, has_api)

    with tab3:
        _render_summary_report(invoices)


def _render_stats(invoices, pending, generated):
    total_pending_val   = sum(float(v.get("ValDtls", {}).get("TotInvVal", 0)) for v in pending.values())
    total_generated_val = sum(float(v.get("ValDtls", {}).get("TotInvVal", 0)) for v in generated.values())
    today_str = date.today().strftime("%d/%m/%Y")
    today_count = sum(1 for v in invoices.values() if v.get("DocDtls", {}).get("Dt") == today_str)

    c1, c2, c3, c4, c5 = st.columns(5)
    _stat(c1, len(pending),   "Pending IRN",       "#fef3c7", "#92400e")
    _stat(c2, len(generated), "IRN Generated",     "#d1fae5", "#065f46")
    _stat(c3, len(invoices),  "Total Invoices",    "#dbeafe", "#1e40af")
    _stat(c4, today_count,    "Today's Invoices",  "#f3e8ff", "#6b21a8") if False else \
         _stat(c4, today_count, "Today's Invoices", "#e0f2fe", "#0369a1")
    _stat(c5, f"₹{(total_pending_val + total_generated_val):,.0f}", "Total Value", "#fce7f3", "#9d174d")
    st.markdown("<br>", unsafe_allow_html=True)


def _stat(col, value, label, bg, color):
    col.markdown(
        f"<div style='background:{bg};border-radius:8px;padding:.8rem;text-align:center'>"
        f"<div style='font-size:1.6rem;font-weight:700;color:{color}'>{value}</div>"
        f"<div style='font-size:.72rem;color:{color};opacity:.8;margin-top:.2rem'>{label}</div>"
        f"</div>",
        unsafe_allow_html=True
    )


def _render_batch_submit(pending, api_cfg, has_api):
    st.markdown("<div class='section-header'>Select Invoices for Batch Submission</div>",
                unsafe_allow_html=True)

    if not pending:
        st.success("No pending invoices. All invoices have IRN.")
        return

    if not has_api:
        st.warning("No API credentials configured. You can use Test Mode (simulated IRN) or "
                   "configure live credentials in API Settings.")
    else:
        mode = "Sandbox" if api_cfg.get("sandbox") else "Production"
        badge_color = "#fef3c7" if api_cfg.get("sandbox") else "#d1fae5"
        text_color  = "#92400e" if api_cfg.get("sandbox") else "#065f46"
        st.markdown(
            f"<span style='background:{badge_color};color:{text_color};padding:3px 10px;"
            f"border-radius:10px;font-size:.8rem;font-weight:600'>API Mode: {mode}</span>",
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    select_all = st.checkbox("Select All Pending Invoices", key="gpp_select_all")

    selected_keys = []
    for inv_key, invoice in pending.items():
        doc = invoice.get("DocDtls", {})
        val = invoice.get("ValDtls", {})
        buy = invoice.get("BuyerDtls", {})
        label = (f"{doc.get('Typ', '')}  |  {doc.get('No', '')}  |  "
                 f"{doc.get('Dt', '')}  |  {buy.get('LglNm', '')}  |  "
                 f"₹{float(val.get('TotInvVal', 0)):,.2f}")
        checked = st.checkbox(label, value=select_all, key=f"gpp_chk_{inv_key}")
        if checked:
            selected_keys.append(inv_key)

    st.divider()

    if not selected_keys:
        st.info(f"Select invoices above to submit. {len(pending)} pending invoice(s) available.")
        return

    st.markdown(f"**{len(selected_keys)} invoice(s) selected**")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🚀 Submit Selected to NIC Portal",
                     type="primary", disabled=not has_api, use_container_width=True,
                     key="gpp_live_batch"):
            _batch_submit(selected_keys, pending, api_cfg, live=True)

    with col2:
        if st.button("🧪 Test Mode — Simulate IRN for Selected",
                     use_container_width=True, key="gpp_sim_batch"):
            _batch_submit(selected_keys, pending, api_cfg, live=False)


def _batch_submit(selected_keys, pending, api_cfg, live):
    progress = st.progress(0, text="Initialising...")
    results  = {"success": [], "failed": []}
    client   = None

    if live:
        client = NICAPIClient(
            api_cfg["gstin"], api_cfg["client_id"], api_cfg["client_secret"],
            api_cfg["username"], api_cfg["password"],
            sandbox=api_cfg.get("sandbox", True)
        )
        auth = client.authenticate()
        if not auth["success"]:
            st.error(f"Authentication failed: {auth['error']}")
            return

    total = len(selected_keys)
    for idx, inv_key in enumerate(selected_keys):
        invoice = pending[inv_key]
        doc     = invoice.get("DocDtls", {})
        progress.progress((idx + 1) / total,
                          text=f"Processing {doc.get('No', inv_key)} ({idx+1}/{total})...")
        clean = {k: v for k, v in invoice.items() if not k.startswith("_")}
        if live:
            res = client.generate_irn(clean)
        else:
            res = simulate_irn_generation(clean)

        if res.get("success"):
            update_invoice_irn(inv_key, res)
            results["success"].append(doc.get("No", inv_key))
        else:
            results["failed"].append((doc.get("No", inv_key), res.get("error", "Unknown error")))

    progress.empty()

    if results["success"]:
        st.success(f"IRN obtained for {len(results['success'])} invoice(s): "
                   f"{', '.join(results['success'])}")
    if results["failed"]:
        for doc_no, err in results["failed"]:
            st.error(f"{doc_no}: {err}")

    st.rerun()


def _render_all_invoices(invoices, api_cfg, has_api):
    st.markdown("<div class='section-header'>All Invoices</div>", unsafe_allow_html=True)

    if not invoices:
        st.info("No invoices found. Create invoices from the Create Invoice page.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        search_term = st.text_input("Search by Doc No or Buyer", placeholder="e.g. INV-001 or ABC Ltd",
                                     key="gpp_search")
    with col2:
        status_filter = st.selectbox("Filter by Status", ["All", "Pending IRN", "IRN Generated"],
                                      key="gpp_status")
    with col3:
        doc_type_filter = st.selectbox(
            "Filter by Doc Type", ["All", "INV", "CRN", "DBN"], key="gpp_dtype"
        )

    rows  = []
    items = list(invoices.items())
    items.sort(key=lambda x: x[1].get("_saved_at", ""), reverse=True)

    for k, v in items:
        doc   = v.get("DocDtls", {})
        val   = v.get("ValDtls", {})
        buy   = v.get("BuyerDtls", {})
        irn_d = v.get("_irn_data", {})
        status = v.get("_status", "PENDING")

        if status_filter == "Pending IRN"   and status != "PENDING":       continue
        if status_filter == "IRN Generated" and status != "IRN_GENERATED": continue
        if doc_type_filter != "All"         and doc.get("Typ") != doc_type_filter: continue
        if search_term:
            term = search_term.lower()
            if term not in doc.get("No", "").lower() and term not in buy.get("LglNm", "").lower():
                continue

        rows.append({
            "_key":    k,
            "Type":    doc.get("Typ", ""),
            "Doc No":  doc.get("No", ""),
            "Date":    doc.get("Dt", ""),
            "Buyer":   buy.get("LglNm", "")[:35],
            "GSTIN":   buy.get("Gstin", ""),
            "Taxable": f"₹{float(val.get('AssVal', 0)):,.2f}",
            "Total":   f"₹{float(val.get('TotInvVal', 0)):,.2f}",
            "Status":  "IRN Generated" if status == "IRN_GENERATED" else "Pending",
            "Mode":    ("Test" if irn_d.get("simulated") else "Live") if irn_d else "—",
            "IRN":     (irn_d.get("irn", "")[:20] + "...") if irn_d.get("irn") else "—",
        })

    if not rows:
        st.info("No invoices match the current filters.")
        return

    df = pd.DataFrame([{k: v for k, v in r.items() if k != "_key"} for r in rows])
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"Showing {len(rows)} invoice(s)")

    st.divider()
    st.markdown("<div class='section-header'>Invoice Actions</div>", unsafe_allow_html=True)

    inv_options = [f"{r['Doc No']} — {r['Buyer']} — {r['Status']}" for r in rows]
    sel_label   = st.selectbox("Select Invoice", inv_options, key="gpp_inv_sel")
    sel_idx     = inv_options.index(sel_label)
    sel_key     = rows[sel_idx]["_key"]
    sel_inv     = invoices[sel_key]
    sel_status  = sel_inv.get("_status", "PENDING")
    sel_irn_d   = sel_inv.get("_irn_data", {})
    sel_doc     = sel_inv.get("DocDtls", {})

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        if sel_status == "PENDING":
            if st.button("🚀 Get IRN (Live)", disabled=not has_api,
                         use_container_width=True, key="gpp_act_live"):
                with st.spinner("Connecting to NIC..."):
                    client = NICAPIClient(
                        api_cfg["gstin"], api_cfg["client_id"], api_cfg["client_secret"],
                        api_cfg["username"], api_cfg["password"],
                        sandbox=api_cfg.get("sandbox", True)
                    )
                    clean = {k: v for k, v in sel_inv.items() if not k.startswith("_")}
                    res   = client.generate_irn(clean)
                if res["success"]:
                    update_invoice_irn(sel_key, res)
                    st.success(f"IRN: {res['irn'][:20]}..."); st.rerun()
                else:
                    st.error(res["error"])
        else:
            st.markdown("<div style='font-size:.78rem;color:#065f46;padding:.5rem;background:#d1fae5;"
                        "border-radius:5px;text-align:center'>IRN Obtained</div>",
                        unsafe_allow_html=True)

    with col2:
        if sel_status == "PENDING":
            if st.button("🧪 Test IRN", use_container_width=True, key="gpp_act_sim"):
                clean = {k: v for k, v in sel_inv.items() if not k.startswith("_")}
                res   = simulate_irn_generation(clean)
                update_invoice_irn(sel_key, res)
                st.success("Test IRN generated"); st.rerun()

    with col3:
        if sel_status == "IRN_GENERATED":
            if st.button("🖨️ PDF", type="primary", use_container_width=True, key="gpp_act_pdf"):
                with st.spinner("Generating PDF..."):
                    try:
                        pdf_buf = generate_einvoice_pdf(sel_inv, sel_irn_d)
                        fname   = f"einvoice_{sel_doc.get('No','inv').replace('/','_')}.pdf"
                        st.download_button("Download PDF", data=pdf_buf.getvalue(),
                                           file_name=fname, mime="application/pdf",
                                           key="gpp_dl_pdf", use_container_width=True)
                    except Exception as e:
                        st.error(f"PDF error: {e}")

    with col4:
        clean = {k: v for k, v in sel_inv.items() if not k.startswith("_")}
        st.download_button("⬇️ JSON", data=json.dumps(clean, indent=2),
                           file_name=f"einv_{sel_doc.get('No','')}.json",
                           mime="application/json", key="gpp_act_json",
                           use_container_width=True)

    with col5:
        if st.button("🗑️ Delete", use_container_width=True, key="gpp_act_del"):
            delete_invoice(sel_key); st.rerun()

    if sel_irn_d:
        with st.expander("IRN Details"):
            c1, c2 = st.columns(2)
            c1.write(f"**IRN:** `{sel_irn_d.get('irn','')}`")
            c1.write(f"**Ack No:** {sel_irn_d.get('ack_no','')}")
            c1.write(f"**Ack Date:** {sel_irn_d.get('ack_dt','')}")
            c2.write(f"**Mode:** {'Test (Simulated)' if sel_irn_d.get('simulated') else 'Live'}")
            c2.write(f"**QR Data:** {str(sel_irn_d.get('signed_qr_code',''))[:60]}...")


def _render_summary_report(invoices):
    st.markdown("<div class='section-header'>Invoice Summary Report</div>", unsafe_allow_html=True)

    if not invoices:
        st.info("No invoices available.")
        return

    by_type   = {}
    by_status = {"PENDING": 0, "IRN_GENERATED": 0}
    by_buyer  = {}
    total_val = 0.0
    total_tax = 0.0

    for v in invoices.values():
        doc    = v.get("DocDtls", {})
        val    = v.get("ValDtls", {})
        buy    = v.get("BuyerDtls", {})
        status = v.get("_status", "PENDING")

        dtype  = doc.get("Typ", "UNK")
        by_type[dtype]    = by_type.get(dtype, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1

        buyer_name = buy.get("LglNm", "Unknown")[:30]
        inv_val    = float(val.get("TotInvVal", 0))
        tax_val    = (float(val.get("IgstVal", 0)) +
                      float(val.get("CgstVal", 0)) +
                      float(val.get("SgstVal", 0)))

        if buyer_name not in by_buyer:
            by_buyer[buyer_name] = {"count": 0, "value": 0.0, "tax": 0.0}
        by_buyer[buyer_name]["count"] += 1
        by_buyer[buyer_name]["value"] += inv_val
        by_buyer[buyer_name]["tax"]   += tax_val

        total_val += inv_val
        total_tax += tax_val

    st.markdown("**Overall Totals**")
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Total Invoices",    len(invoices))
    mc2.metric("Pending IRN",       by_status.get("PENDING", 0))
    mc3.metric("Total Invoice Value", f"₹{total_val:,.2f}")
    mc4.metric("Total Tax",           f"₹{total_tax:,.2f}")

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**By Document Type**")
        type_rows = [{"Type": k, "Count": v} for k, v in by_type.items()]
        st.dataframe(pd.DataFrame(type_rows), use_container_width=True, hide_index=True)

    with col2:
        st.markdown("**By Status**")
        status_rows = [
            {"Status": "Pending IRN",   "Count": by_status.get("PENDING", 0)},
            {"Status": "IRN Generated", "Count": by_status.get("IRN_GENERATED", 0)},
        ]
        st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**By Buyer**")
    buyer_rows = [
        {"Buyer": k, "Invoices": v["count"],
         "Total Value": f"₹{v['value']:,.2f}", "Total Tax": f"₹{v['tax']:,.2f}"}
        for k, v in sorted(by_buyer.items(), key=lambda x: -x[1]["value"])
    ]
    st.dataframe(pd.DataFrame(buyer_rows), use_container_width=True, hide_index=True)

    report_data = {
        "generated_at": datetime.now().isoformat(),
        "totals": {"invoices": len(invoices), "value": round(total_val, 2), "tax": round(total_tax, 2)},
        "by_type": by_type, "by_status": by_status,
        "by_buyer": {k: {**v, "value": round(v["value"], 2), "tax": round(v["tax"], 2)}
                     for k, v in by_buyer.items()}
    }
    st.download_button("Download Report as JSON",
                       data=json.dumps(report_data, indent=2),
                       file_name=f"gpp_report_{date.today().isoformat()}.json",
                       mime="application/json", key="gpp_report_dl")
