import copy
import streamlit as st
import json
import pandas as pd
from datetime import date, datetime
from utils.db import (
    get_invoices, get_generated_invoices, get_pending_invoices,
    clone_invoice, delete_invoice, save_invoice,
    get_templates, save_template, delete_template
)
from utils.excel_export import export_invoices_excel, export_pdfs_zip
from utils.pdf_gen import generate_einvoice_pdf


def show():
    st.markdown("<div class='main-header'><h1>⚡ Bulk Operations</h1>"
                "<p>Clone invoices · Bulk export · Templates · Mass actions</p></div>",
                unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Clone Invoice",
        "⬇️ Bulk Export",
        "📄 Templates",
        "🗑️ Manage Invoices",
    ])

    # ── Tab 1: Clone Invoice ─────────────────────────────────────────
    with tab1:
        _render_clone()

    # ── Tab 2: Bulk Export ───────────────────────────────────────────
    with tab2:
        _render_bulk_export()

    # ── Tab 3: Templates ─────────────────────────────────────────────
    with tab3:
        _render_templates()

    # ── Tab 4: Manage Invoices ───────────────────────────────────────
    with tab4:
        _render_manage()


def _render_clone():
    st.markdown("<div class='section-header'>Clone / Duplicate Invoice</div>",
                unsafe_allow_html=True)
    st.caption("Create a new invoice as a copy of an existing one — same buyer, items, and amounts. Only the document number and date change.")

    invoices = get_invoices()
    if not invoices:
        st.info("No invoices to clone.")
        return

    options = {}
    for k, v in invoices.items():
        doc  = v.get("DocDtls", {})
        buy  = v.get("BuyerDtls", {})
        val  = v.get("ValDtls", {})
        label = (f"{doc.get('Typ','')}  |  {doc.get('No','')}  |  "
                 f"{doc.get('Dt','')}  |  {buy.get('LglNm','')[:25]}  |  "
                 f"₹{float(val.get('TotInvVal',0)):,.2f}")
        options[label] = k

    sel_label = st.selectbox("Select Source Invoice", list(options.keys()), key="clone_src")
    sel_key   = options[sel_label]
    sel_inv   = invoices[sel_key]

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        new_doc_no = st.text_input(
            "New Document Number *",
            placeholder="e.g. INV/2025-26/004",
            key="clone_doc_no"
        )
    with c2:
        new_date = st.date_input("New Document Date *", value=date.today(), key="clone_date")

    if st.button("📋 Clone Invoice", type="primary", disabled=not new_doc_no,
                 use_container_width=True, key="clone_btn"):
        new_key = clone_invoice(sel_key, new_doc_no, new_date.strftime("%d/%m/%Y"))
        if new_key:
            st.success(f"Invoice cloned successfully! New key: `{new_key}`")
            st.caption("The cloned invoice has been added to Pending Invoices.")
        else:
            st.error("Clone failed. Source invoice not found.")

    if not new_doc_no:
        st.caption("Enter a new document number to enable cloning.")

    with st.expander("Preview Source Invoice"):
        doc = sel_inv.get("DocDtls", {})
        val = sel_inv.get("ValDtls", {})
        buy = sel_inv.get("BuyerDtls", {})
        st.write(f"**Buyer:** {buy.get('LglNm','')} ({buy.get('Gstin','')})")
        st.write(f"**Total Value:** ₹{float(val.get('TotInvVal',0)):,.2f}")
        st.write(f"**Items:** {len(sel_inv.get('ItemList',[]))} line item(s)")
        st.write(f"**Tax:** IGST ₹{float(val.get('IgstVal',0)):,.2f} | "
                 f"CGST ₹{float(val.get('CgstVal',0)):,.2f} | "
                 f"SGST ₹{float(val.get('SgstVal',0)):,.2f}")


def _render_bulk_export():
    st.markdown("<div class='section-header'>Bulk Download</div>", unsafe_allow_html=True)

    invoices  = get_invoices()
    generated = get_generated_invoices()

    if not invoices:
        st.info("No invoices to export.")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**All Invoices — Excel**")
        st.caption("Complete invoice register with 3 sheets: Invoice Register, Line Items, HSN Summary")
        if st.button("Generate Excel", use_container_width=True, key="bulk_excel_btn"):
            with st.spinner("Building Excel workbook..."):
                excel_bytes = export_invoices_excel(invoices)
                st.session_state["_bulk_excel"] = excel_bytes
        if "_bulk_excel" in st.session_state:
            st.download_button(
                "⬇️ Download Excel",
                data=st.session_state["_bulk_excel"],
                file_name=f"all_invoices_{date.today().isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="dl_bulk_excel",
            )

    with col2:
        st.markdown("**IRN Invoices — PDF ZIP**")
        st.caption(f"ZIP of all {len(generated)} IRN-generated e-invoice PDFs")
        if generated:
            if st.button("Generate PDF ZIP", use_container_width=True, key="bulk_zip_btn"):
                with st.spinner(f"Generating {len(generated)} PDFs..."):
                    zip_bytes = export_pdfs_zip(generated, generate_einvoice_pdf)
                    st.session_state["_bulk_zip"] = zip_bytes
            if "_bulk_zip" in st.session_state:
                st.download_button(
                    "⬇️ Download ZIP",
                    data=st.session_state["_bulk_zip"],
                    file_name=f"einvoices_{date.today().isoformat()}.zip",
                    mime="application/zip",
                    use_container_width=True,
                    key="dl_bulk_zip",
                )
        else:
            st.info("No IRN-generated invoices yet.")

    with col3:
        st.markdown("**All Invoices — JSON**")
        st.caption("Complete invoice database as JSON — useful for backup or migration")
        clean_all = {
            k: {fk: fv for fk, fv in v.items() if not fk.startswith("_")}
            for k, v in invoices.items()
        }
        st.download_button(
            "⬇️ Download All JSON",
            data=json.dumps(clean_all, indent=2),
            file_name=f"invoices_backup_{date.today().isoformat()}.json",
            mime="application/json",
            use_container_width=True,
            key="dl_all_json",
        )


def _render_templates():
    st.markdown("<div class='section-header'>Invoice Templates</div>", unsafe_allow_html=True)
    st.caption("Save an existing invoice as a template to quickly create recurring invoices.")

    invoices  = get_invoices()
    templates = get_templates()

    t1, t2 = st.tabs(["💾 Save as Template", "📂 My Templates"])

    with t1:
        if not invoices:
            st.info("No invoices available to save as template.")
        else:
            opts = {}
            for k, v in invoices.items():
                doc   = v.get("DocDtls", {})
                buy   = v.get("BuyerDtls", {})
                label = f"{doc.get('Typ','')} | {doc.get('No','')} | {buy.get('LglNm','')[:25]}"
                opts[label] = k

            sel_lbl  = st.selectbox("Source Invoice", list(opts.keys()), key="tmpl_src")
            tmpl_name = st.text_input("Template Name *", placeholder="e.g. Monthly IT Services — ABC Ltd",
                                      key="tmpl_name")

            if st.button("💾 Save as Template", type="primary",
                         disabled=not tmpl_name, use_container_width=True, key="save_tmpl_btn"):
                src     = copy.deepcopy(invoices[opts[sel_lbl]])
                clean   = {fk: fv for fk, fv in src.items() if not fk.startswith("_")}
                save_template(tmpl_name, clean)
                st.success(f"Template '{tmpl_name}' saved!")
                st.rerun()

    with t2:
        templates = get_templates()
        if not templates:
            st.info("No templates saved yet.")
        else:
            for tmpl_key, tmpl in templates.items():
                doc = tmpl.get("DocDtls", {})
                buy = tmpl.get("BuyerDtls", {})
                val = tmpl.get("ValDtls", {})
                with st.expander(f"📄 {tmpl_key}"):
                    st.caption(f"Based on: {doc.get('Typ','')} {doc.get('No','')} | "
                               f"Buyer: {buy.get('LglNm','')} | "
                               f"Value: ₹{float(val.get('TotInvVal',0)):,.2f}")

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        new_no = st.text_input("New Doc No *", key=f"tmpl_no_{tmpl_key}",
                                               placeholder="INV/2025-26/005")
                    with c2:
                        new_dt = st.date_input("New Date", value=date.today(),
                                               key=f"tmpl_dt_{tmpl_key}")
                    with c3:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("Create Invoice", type="primary",
                                     disabled=not new_no,
                                     key=f"use_tmpl_{tmpl_key}", use_container_width=True):
                            new_inv = copy.deepcopy(tmpl)
                            for fk in list(new_inv.keys()):
                                if fk.startswith("_"):
                                    del new_inv[fk]
                            new_inv["DocDtls"]["No"] = new_no
                            new_inv["DocDtls"]["Dt"] = new_dt.strftime("%d/%m/%Y")
                            new_inv["_status"] = "PENDING"
                            new_key = save_invoice(new_inv)
                            st.success(f"Invoice created from template! Key: `{new_key}`")

                    if st.button("🗑️ Delete Template", key=f"del_tmpl_{tmpl_key}",
                                 use_container_width=True):
                        delete_template(tmpl_key)
                        st.rerun()


def _render_manage():
    st.markdown("<div class='section-header'>Manage All Invoices</div>", unsafe_allow_html=True)

    invoices = get_invoices()
    if not invoices:
        st.info("No invoices found.")
        return

    st.markdown(f"Total invoices: **{len(invoices)}** | "
                f"Pending: **{sum(1 for v in invoices.values() if v.get('_status')=='PENDING')}** | "
                f"Generated: **{sum(1 for v in invoices.values() if v.get('_status')=='IRN_GENERATED')}** | "
                f"Cancelled: **{sum(1 for v in invoices.values() if v.get('_status')=='CANCELLED')}**")

    st.divider()
    st.markdown("**Bulk Delete Pending Invoices**")
    pending = get_pending_invoices()
    if pending:
        st.warning(f"This will permanently delete **{len(pending)}** pending invoices. This cannot be undone.")
        col1, col2 = st.columns(2)
        with col1:
            confirm = st.checkbox("I understand this is irreversible", key="bulk_del_confirm")
        with col2:
            if st.button("🗑️ Delete All Pending",
                         disabled=not confirm, type="primary",
                         use_container_width=True, key="bulk_del_pending"):
                for k in list(pending.keys()):
                    delete_invoice(k)
                st.success(f"Deleted {len(pending)} pending invoices.")
                st.rerun()
    else:
        st.info("No pending invoices to delete.")

    st.divider()
    st.markdown("**Invoice Search & Quick Actions**")
    search_q = st.text_input("Search by doc number or buyer name", key="mgmt_search",
                              placeholder="e.g. INV-001 or ABC Ltd")

    rows = []
    for k, v in invoices.items():
        doc = v.get("DocDtls", {})
        buy = v.get("BuyerDtls", {})
        val = v.get("ValDtls", {})
        if search_q:
            term = search_q.lower()
            if term not in doc.get("No","").lower() and term not in buy.get("LglNm","").lower():
                continue
        rows.append({
            "_key":  k,
            "Status": v.get("_status",""),
            "Type":   doc.get("Typ",""),
            "Doc No": doc.get("No",""),
            "Date":   doc.get("Dt",""),
            "Buyer":  buy.get("LglNm","")[:30],
            "Total":  f"₹{float(val.get('TotInvVal',0)):,.2f}",
        })

    if rows:
        df = pd.DataFrame([{k: v for k, v in r.items() if k != "_key"} for r in rows])
        st.dataframe(df, use_container_width=True, hide_index=True)

        opts     = [f"{r['Doc No']} — {r['Buyer']} [{r['Status']}]" for r in rows]
        sel_opt  = st.selectbox("Select to Delete", opts, key="mgmt_del_sel")
        sel_idx  = opts.index(sel_opt)
        sel_key  = rows[sel_idx]["_key"]

        if st.button(f"🗑️ Delete Selected Invoice", use_container_width=True, key="mgmt_del_btn"):
            delete_invoice(sel_key)
            st.success("Invoice deleted.")
            st.rerun()
    elif search_q:
        st.info("No invoices match your search.")
