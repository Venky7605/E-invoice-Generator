import streamlit as st
import pandas as pd
import json
from utils.excel_import import import_from_excel
from utils.db import save_recipient, get_recipients, save_invoice, get_supplier
from utils.masters import STATES, determine_tax_type
from utils.json_builder import build_invoice_json, calculate_item_taxes, calculate_totals

DEFAULT_HSN  = "998319"
DEFAULT_DESC = "Other Information Technology Services"
DEFAULT_UQC  = "UNT"

def show():
    st.markdown("<div class='section-header'>📥 Import Invoices from Excel</div>", unsafe_allow_html=True)
    st.caption("Upload your invoice Excel — all invoices, GSTINs and details are extracted automatically.")

    uploaded = st.file_uploader("Upload Excel (.xlsx / .xls) or CSV", type=["xlsx","xls","csv"])
    if not uploaded:
        st.info("""**Supported format (RBIH invoice sheet):**

| Column | Example |
|--------|---------|
| Service Receiver | Cholamandalam Investment... |
| Billing Period | 01-Feb-26 - 28-Feb-26 |
| Date of Invoice | 2026-03-30 |
| GSTIN | 33AAACC1226H3Z9 |
| Invoice No | 2025-26/03/0001 |
| Taxable amount | 264737.5 |
| IGST / CGST / SGST | 47652.75 / 0 / 0 |
| Round off | 0.75 |
| Invoice Amount | 312391 |
| COUNTS | 105895 |
| UNIT PRICE | 2.5 |

Upload your file to parse all invoices at once.""")
        return

    with st.spinner("Parsing file..."):
        result = import_from_excel(uploaded.read())

    if result["errors"]:
        st.error("Parse errors: " + "; ".join(result["errors"]))

    fmt = result.get("format","unknown")
    st.success(f"✅ Format detected: **{'RBIH Invoice Sheet' if fmt=='rbih' else 'Generic Excel'}** — "
               f"{len(result['invoices'])} invoices, {len(result['recipients'])} unique GSTINs")

    tab1, tab2, tab3 = st.tabs([
        f"🧾 Invoices ({len(result['invoices'])})",
        f"👥 Recipients ({len(result['recipients'])})",
        "📊 Raw Data"
    ])

    supplier = get_supplier()

    # ── Tab 1: Invoices ───────────────────────────────────────────────
    with tab1:
        if not result["invoices"]:
            st.info("No invoices parsed. Check the raw data tab.")
        else:
            invs = result["invoices"]
            df_show = pd.DataFrame([{
                "✓":          False,
                "Doc Type":   i["doc_type"],
                "Invoice No": i["inv_no"],
                "Date":       i["inv_date"],
                "Recipient":  i["name"][:35],
                "GSTIN":      i["gstin"],
                "Tax Type":   i["tax_type"],
                "Taxable":    f"₹{i['taxable']:,.2f}",
                "IGST":       f"₹{i['igst']:,.2f}",
                "CGST":       f"₹{i['cgst']:,.2f}",
                "SGST":       f"₹{i['sgst']:,.2f}",
                "Round Off":  f"₹{i['round_off']:,.2f}",
                "Total":      f"₹{i['inv_amt']:,.2f}",
                "Count":      i["counts"],
                "Unit Price": f"₹{i['unit_price']:,.4f}",
                "Period":     i["period"],
            } for i in invs])

            st.markdown("**Review parsed invoices — select which ones to import:**")
            edited = st.data_editor(df_show, use_container_width=True, hide_index=True,
                                     column_config={"✓": st.column_config.CheckboxColumn("Import?", default=False)},
                                     disabled=[c for c in df_show.columns if c != "✓"])

            selected_idx = [i for i, row in edited.iterrows() if row["✓"]]
            st.caption(f"{len(selected_idx)} of {len(invs)} selected")

            # HSN / SAC for import
            st.markdown("**HSN/SAC details to apply to all selected invoices:**")
            c1, c2, c3 = st.columns(3)
            with c1: imp_hsn  = st.text_input("HSN / SAC Code", value=DEFAULT_HSN)
            with c2: imp_desc = st.text_input("Description",    value=DEFAULT_DESC)
            with c3: imp_uqc  = st.text_input("UQC",            value=DEFAULT_UQC)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("📥 Import Selected as Invoices", type="primary",
                              use_container_width=True, disabled=not selected_idx or not supplier):
                    if not supplier:
                        st.error("Set up Supplier Profile first.")
                    else:
                        saved_keys = []
                        errors     = []
                        for idx in selected_idx:
                            inv = invs[idx]
                            try:
                                _save_invoice_from_row(inv, supplier, imp_hsn, imp_desc, imp_uqc)
                                saved_keys.append(inv["inv_no"])
                            except Exception as e:
                                errors.append(f"{inv['inv_no']}: {e}")
                        if saved_keys:
                            st.success(f"✅ {len(saved_keys)} invoice(s) saved to Pending Invoices:\n" +
                                       "\n".join(f"• {k}" for k in saved_keys))
                        if errors:
                            for e in errors: st.error(e)
                        st.rerun()

            with col2:
                if st.button("📥 Import ALL as Invoices", use_container_width=True,
                              disabled=not supplier):
                    if not supplier:
                        st.error("Set up Supplier Profile first.")
                    else:
                        saved_keys = []
                        for inv in invs:
                            try:
                                _save_invoice_from_row(inv, supplier, imp_hsn, imp_desc, imp_uqc)
                                saved_keys.append(inv["inv_no"])
                            except Exception as e:
                                st.warning(f"Skipped {inv.get('inv_no','')} — {e}")
                        st.success(f"✅ {len(saved_keys)} invoice(s) imported → go to 📋 Pending Invoices")
                        st.rerun()

            if not supplier:
                st.warning("⚠️ Set up Supplier Profile first before importing invoices.")

    # ── Tab 2: Recipients ─────────────────────────────────────────────
    with tab2:
        if not result["recipients"]:
            st.info("No GSTINs found.")
        else:
            existing = get_recipients()
            st.markdown(f"**{len(result['recipients'])} unique GSTIN(s) found:**")
            for i, rec in enumerate(result["recipients"]):
                gstin = rec["gstin"]
                name  = rec.get("name","")
                sc    = rec.get("state_code", gstin[:2])
                state = STATES.get(sc, "Unknown")
                is_new = gstin not in existing
                badge  = "🆕 New" if is_new else "✅ Already saved"
                with st.expander(f"{badge} — **{gstin}** | {name[:40]} | {state}"):
                    if is_new:
                        with st.form(f"rec_form_{i}"):
                            c1, c2 = st.columns(2)
                            with c1:
                                legal = st.text_input("Legal Name *", value=name, key=f"rl_{i}")
                                addr1 = st.text_input("Address Line 1", key=f"ra1_{i}")
                                loc   = st.text_input("City", key=f"rloc_{i}")
                            with c2:
                                trade = st.text_input("Trade Name", value=name, key=f"rt_{i}")
                                pin   = st.text_input("Pincode *", key=f"rpin_{i}", max_chars=6)
                                phone = st.text_input("Phone", key=f"rph_{i}")
                            if st.form_submit_button("💾 Save to Recipient Master", type="primary"):
                                if legal and pin:
                                    save_recipient(gstin, {"gstin": gstin, "legal_name": legal,
                                        "trade_name": trade, "addr1": addr1, "addr2": "",
                                        "location": loc, "state_code": sc, "pincode": pin,
                                        "phone": phone, "email": ""})
                                    st.success(f"✅ {gstin} saved!"); st.rerun()
                                else:
                                    st.error("Legal Name and Pincode required.")
                    else:
                        d = existing[gstin]
                        st.write(f"**Name:** {d.get('legal_name','')}  |  "
                                 f"**Location:** {d.get('location','')}  |  "
                                 f"**State:** {STATES.get(d.get('state_code',''),'')}")

    # ── Tab 3: Raw Data ───────────────────────────────────────────────
    with tab3:
        for sheet_data in result["raw_rows"]:
            st.markdown(f"**Sheet: {sheet_data['sheet']}**")
            df_raw = pd.DataFrame(sheet_data["rows"])
            st.dataframe(df_raw.head(50), use_container_width=True, hide_index=True)
            if len(sheet_data["rows"]) > 50:
                st.caption(f"Showing first 50 of {len(sheet_data['rows'])} rows")


def _save_invoice_from_row(inv, supplier, hsn, desc, uqc):
    """Build and save a full e-Invoice JSON from a parsed Excel row."""
    existing_recs = get_recipients()
    buyer_rec     = existing_recs.get(inv["gstin"], {})

    # Determine tax type from GSTINs
    tax_type = determine_tax_type(supplier.get("gstin",""), inv["gstin"])
    # Cross-check with actual values in Excel
    if inv.get("igst", 0) > 0:
        tax_type = "IGST"
    elif inv.get("cgst", 0) > 0 or inv.get("sgst", 0) > 0:
        tax_type = "CGST+SGST"

    # Build line item from COUNTS * UNIT PRICE
    counts     = float(inv.get("counts", 1) or 1)
    unit_price = float(inv.get("unit_price", 0) or 0)
    taxable    = float(inv.get("taxable", 0) or 0)

    # GST rate from taxable + tax amount
    igst = float(inv.get("igst",0)); cgst = float(inv.get("cgst",0)); sgst = float(inv.get("sgst",0))
    total_tax = igst + cgst + sgst
    gst_rate  = round((total_tax / taxable * 100), 0) if taxable > 0 else 18.0
    # Snap to nearest standard rate
    for std in [0, 0.1, 0.25, 1.5, 3, 5, 12, 18, 28]:
        if abs(gst_rate - std) < 1:
            gst_rate = std; break

    # Build taxes manually from Excel values (trust Excel over recalculation)
    if tax_type == "IGST":
        taxes = {"total_amt": taxable, "ass_amt": taxable,
                 "igst_amt": igst, "cgst_amt": 0.0, "sgst_amt": 0.0,
                 "cess_amt": 0.0, "tot_item_val": round(taxable + igst, 2)}
    else:
        taxes = {"total_amt": taxable, "ass_amt": taxable,
                 "igst_amt": 0.0, "cgst_amt": cgst, "sgst_amt": sgst,
                 "cess_amt": 0.0, "tot_item_val": round(taxable + cgst + sgst, 2)}

    items = [{
        "description": desc, "hsn": hsn, "is_service": "Y",
        "qty": counts, "uqc": uqc, "unit_price": unit_price,
        "gst_rate": gst_rate, "cess_rate": 0,
        "discount": 0, "other_charges": 0,
        **taxes
    }]

    totals = {
        "ass_val": taxable, "igst_val": igst, "cgst_val": cgst,
        "sgst_val": sgst, "cess_val": 0.0, "st_cess_val": 0.0,
        "other_charges": 0.0, "discount": 0.0,
        "round_off": float(inv.get("round_off", 0) or 0),
        "tot_inv_val": round(taxable + total_tax + float(inv.get("round_off",0) or 0), 2)
    }

    buyer_sc = inv["gstin"][:2]
    buyer = {
        "gstin":       inv["gstin"],
        "legal_name":  buyer_rec.get("legal_name", inv["name"]),
        "trade_name":  buyer_rec.get("trade_name", inv["name"]),
        "addr1":       buyer_rec.get("addr1", "As per records"),
        "addr2":       buyer_rec.get("addr2", ""),
        "location":    buyer_rec.get("location", ""),
        "state_code":  buyer_rec.get("state_code", buyer_sc),
        "pincode":     buyer_rec.get("pincode", "000000"),
        "phone":       buyer_rec.get("phone", ""),
        "email":       buyer_rec.get("email", ""),
        "pos":         buyer_rec.get("state_code", buyer_sc),
    }

    form_data = {
        "supplier": supplier,
        "buyer":    buyer,
        "doc": {
            "doc_type":       inv.get("doc_type","INV"),
            "doc_no":         inv["inv_no"],
            "doc_date":       inv["inv_date"],
            "supply_type":    "B2B",
            "reverse_charge": "N",
            "igst_on_intra":  "N",
            "ecom_gstin":     None
        },
        "items": items,
        "val":   totals
    }
    inv_json = build_invoice_json(form_data)
    save_invoice(inv_json)
