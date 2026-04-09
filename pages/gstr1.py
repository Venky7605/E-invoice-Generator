import streamlit as st
import json
import pandas as pd
from datetime import date
from utils.db import get_invoices, get_supplier
from utils.gstr1_builder import build_gstr1, build_b2b_summary
from utils.excel_export import export_invoices_excel

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
QUARTERS = {
    "Q1 (Apr–Jun)":  [4, 5, 6],
    "Q2 (Jul–Sep)":  [7, 8, 9],
    "Q3 (Oct–Dec)":  [10, 11, 12],
    "Q4 (Jan–Mar)":  [1, 2, 3],
}


def show():
    st.markdown("<div class='main-header'><h1>📊 GSTR-1 Report & Export</h1>"
                "<p>Generate GSTR-1 compatible data for GST portal upload</p></div>",
                unsafe_allow_html=True)

    supplier = get_supplier()
    if not supplier:
        st.error("Set up your Supplier Profile first.")
        return

    gstin    = supplier.get("gstin", "")
    invoices = get_invoices()
    if not invoices:
        st.info("No invoices found. Create invoices first.")
        return

    st.markdown("<div class='section-header'>Filing Period</div>", unsafe_allow_html=True)
    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        sel_year  = st.selectbox("Financial Year", [2024, 2025, 2026, 2027], index=1, key="g1_year")
    with cc2:
        period_type = st.radio("Period", ["Monthly", "Quarterly"], horizontal=True, key="g1_ptype")
    with cc3:
        if period_type == "Monthly":
            sel_month = st.selectbox("Month", MONTHS, index=date.today().month - 1, key="g1_month")
            months    = [MONTHS.index(sel_month) + 1]
        else:
            sel_qtr   = st.selectbox("Quarter", list(QUARTERS.keys()), key="g1_qtr")
            months    = QUARTERS[sel_qtr]

    st.divider()

    all_rows = []
    for m in months:
        all_rows.extend(build_b2b_summary(invoices, sel_year, m))

    if not all_rows:
        st.warning(f"No eligible invoices found for the selected period.")
        return

    tab1, tab2, tab3 = st.tabs(["📋 B2B Invoices", "📦 HSN Summary", "⬇️ Export"])

    with tab1:
        st.markdown(f"**{len(all_rows)} invoices for the selected period**")

        df = pd.DataFrame(all_rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        inv_total     = sum(r["Invoice Value"] for r in all_rows)
        taxable_total = sum(r["Taxable Value"] for r in all_rows)
        igst_total    = sum(r["IGST"] for r in all_rows)
        cgst_total    = sum(r["CGST"] for r in all_rows)
        sgst_total    = sum(r["SGST"] for r in all_rows)

        st.divider()
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Invoice Value",  f"₹{inv_total:,.2f}")
        m2.metric("Taxable Value",  f"₹{taxable_total:,.2f}")
        m3.metric("IGST",           f"₹{igst_total:,.2f}")
        m4.metric("CGST",           f"₹{cgst_total:,.2f}")
        m5.metric("SGST",           f"₹{sgst_total:,.2f}")

    with tab2:
        hsn_map = {}
        for inv in invoices.values():
            doc_dt = inv.get("DocDtls", {}).get("Dt", "")
            parts  = doc_dt.split("/")
            if len(parts) != 3:
                continue
            if int(parts[1]) not in months or int(parts[2]) != sel_year:
                continue
            if inv.get("_status") not in ("IRN_GENERATED", "CANCELLED"):
                continue
            for item in inv.get("ItemList", []):
                hsn  = item.get("HsnCd", "")
                desc = item.get("PrdDesc", "")
                uqc  = item.get("Unit", "OTH")
                if hsn not in hsn_map:
                    hsn_map[hsn] = {"HSN/SAC": hsn, "Description": desc, "UQC": uqc,
                                    "Qty": 0, "Total Value": 0, "Taxable": 0,
                                    "IGST": 0, "CGST": 0, "SGST": 0, "Cess": 0}
                hsn_map[hsn]["Qty"]         += float(item.get("Qty", 0))
                hsn_map[hsn]["Total Value"] += float(item.get("TotItemVal", 0))
                hsn_map[hsn]["Taxable"]     += float(item.get("AssAmt", 0))
                hsn_map[hsn]["IGST"]        += float(item.get("IgstAmt", 0))
                hsn_map[hsn]["CGST"]        += float(item.get("CgstAmt", 0))
                hsn_map[hsn]["SGST"]        += float(item.get("SgstAmt", 0))
                hsn_map[hsn]["Cess"]        += float(item.get("CesAmt", 0))

        if hsn_map:
            hsn_df = pd.DataFrame(list(hsn_map.values()))
            for col in ["Qty", "Total Value", "Taxable", "IGST", "CGST", "SGST", "Cess"]:
                hsn_df[col] = hsn_df[col].round(2)
            st.dataframe(hsn_df, use_container_width=True, hide_index=True)
        else:
            st.info("No HSN data for the selected period.")

    with tab3:
        st.markdown("<div class='section-header'>Download Options</div>", unsafe_allow_html=True)
        st.caption("Generate and download GSTR-1 data in multiple formats.")

        d1, d2, d3 = st.columns(3)

        with d1:
            st.markdown("**GSTR-1 JSON**")
            st.caption("Upload directly to GST portal → Returns → GSTR-1 → Upload JSON")
            if st.button("Generate GSTR-1 JSON", use_container_width=True, key="gen_g1_json"):
                with st.spinner("Building GSTR-1 JSON..."):
                    all_inv_for_period = {}
                    for k, v in invoices.items():
                        doc_dt = v.get("DocDtls", {}).get("Dt", "")
                        parts  = doc_dt.split("/")
                        if len(parts) == 3 and int(parts[1]) in months and int(parts[2]) == sel_year:
                            all_inv_for_period[k] = v

                    gstr1_payloads = []
                    for m in months:
                        payload = build_gstr1(all_inv_for_period, gstin, sel_year, m)
                        gstr1_payloads.append(payload)

                    final = gstr1_payloads[0] if len(gstr1_payloads) == 1 else {
                        "gstin": gstin,
                        "months": gstr1_payloads,
                    }
                    st.session_state["_gstr1_json"] = final

            if "_gstr1_json" in st.session_state:
                period_str = f"{sel_year}_{'-'.join(str(m) for m in months)}"
                st.download_button(
                    "⬇️ Download GSTR-1 JSON",
                    data=json.dumps(st.session_state["_gstr1_json"], indent=2),
                    file_name=f"GSTR1_{gstin}_{period_str}.json",
                    mime="application/json",
                    use_container_width=True,
                    key="dl_gstr1_json",
                )

        with d2:
            st.markdown("**Invoice Register (Excel)**")
            st.caption("Full invoice data with line items and HSN summary in Excel")
            if st.button("Generate Excel Report", use_container_width=True, key="gen_excel"):
                with st.spinner("Building Excel workbook..."):
                    period_invs = {
                        k: v for k, v in invoices.items()
                        if _in_period(v, months, sel_year)
                    }
                    excel_bytes = export_invoices_excel(period_invs)
                    st.session_state["_gstr1_excel"] = excel_bytes

            if "_gstr1_excel" in st.session_state:
                period_str = f"{sel_year}_{'-'.join(str(m) for m in months)}"
                st.download_button(
                    "⬇️ Download Excel Report",
                    data=st.session_state["_gstr1_excel"],
                    file_name=f"InvoiceRegister_{gstin}_{period_str}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="dl_gstr1_excel",
                )

        with d3:
            st.markdown("**B2B Summary (CSV)**")
            st.caption("Simplified CSV of all B2B invoices for the period")
            if all_rows:
                csv_buf = pd.DataFrame(all_rows).to_csv(index=False)
                period_str = f"{sel_year}_{'-'.join(str(m) for m in months)}"
                st.download_button(
                    "⬇️ Download CSV",
                    data=csv_buf,
                    file_name=f"B2B_{gstin}_{period_str}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="dl_gstr1_csv",
                )

        st.divider()
        st.markdown("**How to file GSTR-1 on GST Portal:**")
        st.markdown("""
1. Login to [GST Portal](https://www.gst.gov.in) → Services → Returns → Returns Dashboard
2. Select the Filing Period and click **GSTR-1**
3. Click **Upload JSON** and upload the GSTR-1 JSON downloaded above
4. Review the data and click **Submit** / **File**
5. File with DSC or EVC as applicable
        """)


def _in_period(inv, months, year):
    doc_dt = inv.get("DocDtls", {}).get("Dt", "")
    parts  = doc_dt.split("/")
    if len(parts) != 3:
        return False
    return int(parts[1]) in months and int(parts[2]) == year
