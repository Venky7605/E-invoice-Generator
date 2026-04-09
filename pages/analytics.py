import streamlit as st
import pandas as pd
from collections import defaultdict
from utils.db import get_invoices, get_supplier, get_recipients

MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def show():
    st.markdown("<div class='main-header'><h1>📈 Analytics & Insights</h1>"
                "<p>Visual breakdown of your invoicing activity and tax liability</p></div>",
                unsafe_allow_html=True)

    invoices   = get_invoices()
    supplier   = get_supplier()
    recipients = get_recipients()

    if not invoices:
        st.info("No invoice data yet. Create invoices to see analytics.")
        return

    # ── Pre-compute data ─────────────────────────────────────────────
    total_inv_val  = 0.0
    total_taxable  = 0.0
    total_igst     = 0.0
    total_cgst     = 0.0
    total_sgst     = 0.0
    total_cess     = 0.0
    by_month_val   = defaultdict(float)
    by_month_count = defaultdict(int)
    by_buyer_val   = defaultdict(float)
    by_buyer_cnt   = defaultdict(int)
    by_status      = defaultdict(int)
    by_type        = defaultdict(int)
    by_hsn         = defaultdict(lambda: {"val": 0, "txval": 0, "desc": ""})
    by_rate        = defaultdict(float)

    for inv in invoices.values():
        doc   = inv.get("DocDtls", {})
        val   = inv.get("ValDtls", {})
        buy   = inv.get("BuyerDtls", {})
        items = inv.get("ItemList", [])
        st_   = inv.get("_status", "PENDING")

        inv_val    = float(val.get("TotInvVal", 0))
        taxable    = float(val.get("AssVal", 0))
        igst       = float(val.get("IgstVal", 0))
        cgst       = float(val.get("CgstVal", 0))
        sgst       = float(val.get("SgstVal", 0))
        cess       = float(val.get("CesVal", 0))

        total_inv_val  += inv_val
        total_taxable  += taxable
        total_igst     += igst
        total_cgst     += cgst
        total_sgst     += sgst
        total_cess     += cess

        dt_parts = doc.get("Dt", "").split("/")
        if len(dt_parts) == 3:
            month_key = f"{MONTHS_SHORT[int(dt_parts[1])-1]} {dt_parts[2]}"
            by_month_val[month_key]   += inv_val
            by_month_count[month_key] += 1

        buyer_name = buy.get("LglNm", "Unknown")[:30]
        by_buyer_val[buyer_name] += inv_val
        by_buyer_cnt[buyer_name] += 1

        by_status[st_] += 1
        by_type[doc.get("Typ", "?")] += 1

        for item in items:
            hsn  = item.get("HsnCd", "UNK")
            desc = item.get("PrdDesc", "")[:30]
            rt   = float(item.get("GstRt", 0))
            txv  = float(item.get("AssAmt", 0))
            itmv = float(item.get("TotItemVal", 0))
            by_hsn[hsn]["val"]   += itmv
            by_hsn[hsn]["txval"] += txv
            by_hsn[hsn]["desc"]  = desc
            by_rate[rt]          += txv

    # ── KPI Row ──────────────────────────────────────────────────────
    total_tax = total_igst + total_cgst + total_sgst
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    _kpi(k1, len(invoices),         "Total Invoices",  "#dbeafe", "#1e40af")
    _kpi(k2, by_status.get("PENDING", 0),      "Pending",  "#fef3c7", "#92400e")
    _kpi(k3, by_status.get("IRN_GENERATED", 0),"IRN Obtained", "#d1fae5", "#065f46")
    _kpi(k4, f"₹{total_inv_val/1e5:,.1f}L",    "Total Value", "#e0f2fe", "#0369a1")
    _kpi(k5, f"₹{total_tax/1e5:,.1f}L",        "Total Tax",   "#fce7f3", "#9d174d")
    _kpi(k6, len(recipients),       "Recipients",      "#f3f4f6", "#374151")

    st.markdown("<br>", unsafe_allow_html=True)
    st.divider()

    # ── Row 1: Monthly trend + Status donut ─────────────────────────
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("**Monthly Invoice Value (₹)**")
        if by_month_val:
            sorted_months = sorted(by_month_val.keys(),
                                   key=lambda x: _month_sort_key(x))
            df_month = pd.DataFrame({
                "Month": sorted_months,
                "Invoice Value (₹)": [round(by_month_val[m], 2) for m in sorted_months],
                "Count": [by_month_count[m] for m in sorted_months],
            })
            st.bar_chart(df_month.set_index("Month")["Invoice Value (₹)"],
                         color="#2563eb", use_container_width=True)
        else:
            st.info("No date data available.")

    with col2:
        st.markdown("**Invoices by Status**")
        status_data = {
            "Status": ["Pending", "IRN Generated", "Cancelled"],
            "Count": [
                by_status.get("PENDING", 0),
                by_status.get("IRN_GENERATED", 0),
                by_status.get("CANCELLED", 0),
            ],
        }
        df_status = pd.DataFrame(status_data)
        df_status = df_status[df_status["Count"] > 0]
        st.dataframe(df_status, use_container_width=True, hide_index=True)

        st.markdown("**By Document Type**")
        df_type = pd.DataFrame({
            "Type": list(by_type.keys()),
            "Count": list(by_type.values()),
        })
        st.dataframe(df_type, use_container_width=True, hide_index=True)

    st.divider()

    # ── Row 2: Tax breakdown + Top buyers ───────────────────────────
    col3, col4 = st.columns([1, 2])

    with col3:
        st.markdown("**Tax Breakdown (₹)**")
        tax_rows = [
            {"Component": "IGST",  "Amount (₹)": round(total_igst, 2)},
            {"Component": "CGST",  "Amount (₹)": round(total_cgst, 2)},
            {"Component": "SGST",  "Amount (₹)": round(total_sgst, 2)},
            {"Component": "Cess",  "Amount (₹)": round(total_cess, 2)},
            {"Component": "Total Tax", "Amount (₹)": round(total_tax, 2)},
            {"Component": "Taxable",   "Amount (₹)": round(total_taxable, 2)},
        ]
        st.dataframe(pd.DataFrame(tax_rows), use_container_width=True, hide_index=True)

        if by_rate:
            st.markdown("**Taxable Value by GST Rate**")
            rate_df = pd.DataFrame({
                "GST Rate (%)": [f"{r}%" for r in sorted(by_rate.keys())],
                "Taxable (₹)": [round(by_rate[r], 2) for r in sorted(by_rate.keys())],
            })
            st.bar_chart(rate_df.set_index("GST Rate (%)")["Taxable (₹)"],
                         color="#10b981", use_container_width=True)

    with col4:
        st.markdown("**Top Buyers by Invoice Value**")
        top_buyers = sorted(by_buyer_val.items(), key=lambda x: -x[1])[:15]
        if top_buyers:
            df_buyers = pd.DataFrame({
                "Buyer": [b for b, _ in top_buyers],
                "Invoice Value (₹)": [round(v, 2) for _, v in top_buyers],
                "Invoices": [by_buyer_cnt[b] for b, _ in top_buyers],
            })
            st.bar_chart(df_buyers.set_index("Buyer")["Invoice Value (₹)"],
                         color="#f59e0b", use_container_width=True)
            st.dataframe(df_buyers, use_container_width=True, hide_index=True)

    st.divider()

    # ── Row 3: HSN Summary ───────────────────────────────────────────
    st.markdown("**HSN/SAC-wise Sales Summary**")
    if by_hsn:
        hsn_rows = sorted(
            [{"HSN": h, "Description": v["desc"],
              "Total Value (₹)": round(v["val"], 2),
              "Taxable (₹)": round(v["txval"], 2)}
             for h, v in by_hsn.items()],
            key=lambda x: -x["Total Value (₹)"]
        )
        st.dataframe(pd.DataFrame(hsn_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No HSN data available.")

    st.divider()

    # ── Row 4: Monthly count trend ───────────────────────────────────
    if by_month_count:
        st.markdown("**Invoice Count by Month**")
        sorted_months = sorted(by_month_count.keys(), key=_month_sort_key)
        df_cnt = pd.DataFrame({
            "Month": sorted_months,
            "Invoice Count": [by_month_count[m] for m in sorted_months],
        })
        st.line_chart(df_cnt.set_index("Month")["Invoice Count"],
                      color="#8b5cf6", use_container_width=True)


def _kpi(col, value, label, bg, color):
    col.markdown(
        f"<div style='background:{bg};border-radius:8px;padding:.8rem;text-align:center'>"
        f"<div style='font-size:1.4rem;font-weight:700;color:{color}'>{value}</div>"
        f"<div style='font-size:.7rem;color:{color};opacity:.8;margin-top:.2rem'>{label}</div>"
        f"</div>",
        unsafe_allow_html=True
    )


def _month_sort_key(label: str) -> tuple:
    parts = label.split()
    if len(parts) == 2:
        try:
            return (int(parts[1]), MONTHS_SHORT.index(parts[0]))
        except (ValueError, IndexError):
            pass
    return (9999, 0)
