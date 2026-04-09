"""
GSTR-1 JSON builder — converts stored invoices into NIC GSTR-1 upload format.
Supports: B2B, CDNR, HSN summary, Doc Issue summary.
"""

from datetime import datetime


def _dt_to_gstr(dt_str: str) -> str:
    """Convert DD/MM/YYYY → DD-MM-YYYY for GSTR-1."""
    return dt_str.replace("/", "-") if "/" in dt_str else dt_str


def _period(year: int, month: int) -> str:
    """Return GSTR-1 filing period string MMYYYY."""
    return f"{month:02d}{year}"


def build_gstr1(invoices: dict, gstin: str, year: int, month: int) -> dict:
    """
    Build GSTR-1 JSON payload from invoices dict.
    Filters to invoices whose DocDtls.Dt falls in the given month/year.
    """
    fp = _period(year, month)
    month_prefix_dd = f"/{month:02d}/{year}"   # matches DD/MM/YYYY ending

    b2b_map   = {}
    cdnr_map  = {}
    hsn_map   = {}
    doc_inv   = 0
    doc_crn   = 0
    doc_dbn   = 0

    for inv_key, inv in invoices.items():
        status = inv.get("_status", "PENDING")
        if status not in ("IRN_GENERATED", "CANCELLED"):
            continue

        doc   = inv.get("DocDtls", {})
        val   = inv.get("ValDtls", {})
        buy   = inv.get("BuyerDtls", {})
        items = inv.get("ItemList", [])
        tran  = inv.get("TranDtls", {})

        doc_dt  = doc.get("Dt", "")
        doc_typ = doc.get("Typ", "INV")
        doc_no  = doc.get("No", "")

        # Date filter
        parts = doc_dt.split("/")
        if len(parts) == 3:
            d_month = int(parts[1])
            d_year  = int(parts[2])
            if d_month != month or d_year != year:
                continue
        else:
            continue

        buyer_gstin = buy.get("Gstin", "")
        pos         = buy.get("Pos", buy.get("Stcd", ""))
        rchrg       = tran.get("RegRev", "N")

        total_val   = float(val.get("TotInvVal", 0))
        taxable_val = float(val.get("AssVal", 0))
        igst        = float(val.get("IgstVal", 0))
        cgst        = float(val.get("CgstVal", 0))
        sgst        = float(val.get("SgstVal", 0))
        cess        = float(val.get("CesVal", 0))

        # Build itms from ItemList
        rate_map = {}
        for item in items:
            rt   = float(item.get("GstRt", 0))
            txv  = float(item.get("AssAmt", 0))
            iamt = float(item.get("IgstAmt", 0))
            camt = float(item.get("CgstAmt", 0))
            samt = float(item.get("SgstAmt", 0))
            csmt = float(item.get("CesAmt", 0))
            if rt not in rate_map:
                rate_map[rt] = {"txval": 0, "iamt": 0, "camt": 0, "samt": 0, "csamt": 0}
            rate_map[rt]["txval"] += txv
            rate_map[rt]["iamt"]  += iamt
            rate_map[rt]["camt"]  += camt
            rate_map[rt]["samt"]  += samt
            rate_map[rt]["csamt"] += csmt

            # HSN aggregation
            hsn  = item.get("HsnCd", "")
            desc = item.get("PrdDesc", "")
            uqc  = item.get("Unit", "OTH")
            qty  = float(item.get("Qty", 0))
            itmv = float(item.get("TotItemVal", 0))
            if hsn not in hsn_map:
                hsn_map[hsn] = {"desc": desc, "uqc": uqc, "qty": 0,
                                "val": 0, "txval": 0, "iamt": 0,
                                "camt": 0, "samt": 0, "csamt": 0}
            hsn_map[hsn]["qty"]   += qty
            hsn_map[hsn]["val"]   += itmv
            hsn_map[hsn]["txval"] += txv
            hsn_map[hsn]["iamt"]  += iamt
            hsn_map[hsn]["camt"]  += camt
            hsn_map[hsn]["samt"]  += samt
            hsn_map[hsn]["csamt"] += csmt

        itms = [
            {"num": i + 1, "itm_det": {
                "rt": round(rt, 2),
                "txval": round(v["txval"], 2),
                "iamt":  round(v["iamt"], 2),
                "camt":  round(v["camt"], 2),
                "samt":  round(v["samt"], 2),
                "csamt": round(v["csamt"], 2),
            }}
            for i, (rt, v) in enumerate(rate_map.items())
        ]

        inv_entry = {
            "inum":     doc_no,
            "idt":      _dt_to_gstr(doc_dt),
            "val":      round(total_val, 2),
            "pos":      str(pos).zfill(2) if pos else "00",
            "rchrg":    rchrg,
            "inv_typ":  "R",
            "itms":     itms,
        }

        if doc_typ == "INV":
            doc_inv += 1
            if buyer_gstin not in b2b_map:
                b2b_map[buyer_gstin] = {"ctin": buyer_gstin, "inv": []}
            b2b_map[buyer_gstin]["inv"].append(inv_entry)

        elif doc_typ in ("CRN", "DBN"):
            if doc_typ == "CRN":
                doc_crn += 1
            else:
                doc_dbn += 1
            nt_entry = {
                "nt_num":  doc_no,
                "nt_dt":   _dt_to_gstr(doc_dt),
                "val":     round(total_val, 2),
                "ntty":    "C" if doc_typ == "CRN" else "D",
                "rchrg":   rchrg,
                "itms":    itms,
            }
            if buyer_gstin not in cdnr_map:
                cdnr_map[buyer_gstin] = {"ctin": buyer_gstin, "nt": []}
            cdnr_map[buyer_gstin]["nt"].append(nt_entry)

    hsn_data = [
        {
            "num":    i + 1,
            "hsn_sc": hsn,
            "desc":   v["desc"],
            "uqc":    v["uqc"],
            "qty":    round(v["qty"], 3),
            "val":    round(v["val"], 2),
            "txval":  round(v["txval"], 2),
            "iamt":   round(v["iamt"], 2),
            "camt":   round(v["camt"], 2),
            "samt":   round(v["samt"], 2),
            "csamt":  round(v["csamt"], 2),
        }
        for i, (hsn, v) in enumerate(hsn_map.items())
    ]

    doc_issue = {
        "doc_det": [
            {"doc_num": 1, "docs": [{"num": 1, "from": "", "to": "",
                                      "totnum": doc_inv, "cancel": 0, "net_issue": doc_inv}]},
        ]
    }

    payload = {
        "gstin": gstin,
        "fp":    fp,
    }
    if b2b_map:
        payload["b2b"] = list(b2b_map.values())
    if cdnr_map:
        payload["cdnr"] = list(cdnr_map.values())
    if hsn_data:
        payload["hsn"] = {"data": hsn_data}
    payload["doc_issue"] = doc_issue

    return payload


def build_b2b_summary(invoices: dict, year: int, month: int) -> list:
    """Return flat list of dicts for display/Excel — one row per invoice."""
    rows = []
    for inv_key, inv in invoices.items():
        if inv.get("_status") not in ("IRN_GENERATED", "CANCELLED"):
            continue
        doc  = inv.get("DocDtls", {})
        val  = inv.get("ValDtls", {})
        buy  = inv.get("BuyerDtls", {})
        irnd = inv.get("_irn_data", {})

        doc_dt = doc.get("Dt", "")
        parts  = doc_dt.split("/")
        if len(parts) == 3 and (int(parts[1]) != month or int(parts[2]) != year):
            continue

        rows.append({
            "GSTIN of Buyer":    buy.get("Gstin", ""),
            "Receiver Name":     buy.get("LglNm", ""),
            "Invoice Number":    doc.get("No", ""),
            "Invoice Date":      doc_dt,
            "Invoice Type":      doc.get("Typ", "INV"),
            "Place of Supply":   buy.get("Pos", buy.get("Stcd", "")),
            "Reverse Charge":    inv.get("TranDtls", {}).get("RegRev", "N"),
            "Invoice Value":     round(float(val.get("TotInvVal", 0)), 2),
            "Taxable Value":     round(float(val.get("AssVal", 0)), 2),
            "IGST":              round(float(val.get("IgstVal", 0)), 2),
            "CGST":              round(float(val.get("CgstVal", 0)), 2),
            "SGST":              round(float(val.get("SgstVal", 0)), 2),
            "Cess":              round(float(val.get("CesVal", 0)), 2),
            "IRN":               irnd.get("irn", ""),
            "Ack No":            irnd.get("ack_no", ""),
            "Ack Date":          irnd.get("ack_dt", ""),
        })
    return rows
