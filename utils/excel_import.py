"""
Excel importer — handles both RBIH invoice format and generic formats.
RBIH format columns (row 0 = header):
  Service Receiver | Billing Period | Date of Invoice | GSTIN | Invoice No |
  Taxable amount | IGST | CGST | SGST | Round off | Invoice Amount |
  Debtor Amount | COUNTS | UNIT PRICE | TOTAL COST | Difference
"""
import io, re
from datetime import datetime
import pandas as pd

GSTIN_RE = re.compile(r'^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$')

def detect_gstin(val):
    v = str(val).strip().upper()
    return v if GSTIN_RE.match(v) else None

def _safe_float(v, default=0.0):
    try:
        return float(str(v).replace(",","").strip())
    except:
        return default

def _parse_date(v):
    v = str(v).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y",
                "%d-%b-%Y", "%d/%b/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(v.split(" ")[0], fmt).strftime("%d/%m/%Y")
        except:
            pass
    return v

def import_from_excel(file_bytes: bytes) -> dict:
    result = {
        "format":     "unknown",
        "invoices":   [],       # list of parsed invoice dicts (RBIH format)
        "recipients": [],       # list of {gstin, name}
        "line_items": [],       # generic line items
        "raw_rows":   [],
        "errors":     []
    }

    try:
        try:
            xf = pd.ExcelFile(io.BytesIO(file_bytes))
            sheets = xf.sheet_names
            dfs = {s: xf.parse(s, dtype=str).fillna("") for s in sheets}
        except Exception:
            df = pd.read_csv(io.BytesIO(file_bytes), dtype=str).fillna("")
            dfs = {"Sheet1": df}

        for sheet_name, df in dfs.items():
            df.columns = [str(c).strip() for c in df.columns]
            result["raw_rows"].append({
                "sheet":   sheet_name,
                "columns": list(df.columns),
                "rows":    df.to_dict("records")
            })

            # ── Detect RBIH format ─────────────────────────────────────
            # First row may be header; detect by checking for GSTIN column
            col_map = {c.lower().strip(): c for c in df.columns}

            # Try to find the actual header row (sometimes row 0 has headers)
            header_row_idx = None
            for i, row in df.iterrows():
                vals = [str(v).lower() for v in row.values]
                if any("gstin" in v or "service receiver" in v for v in vals):
                    header_row_idx = i
                    break

            if header_row_idx is not None:
                # Re-read with correct header
                df2 = df.iloc[header_row_idx+1:].copy()
                df2.columns = [str(v).strip() for v in df.iloc[header_row_idx].values]
                df2 = df2.fillna("").reset_index(drop=True)
            else:
                df2 = df.copy()

            # Build lowercase col map
            col_l = {str(c).lower().strip(): str(c) for c in df2.columns}

            def _get(row, *keys):
                for k in keys:
                    for ck, cv in col_l.items():
                        if k in ck:
                            val = str(row.get(cv,"")).strip()
                            if val: return val
                return ""

            is_rbih = any("gstin" in c.lower() or "invoice no" in c.lower() for c in df2.columns)

            if is_rbih:
                result["format"] = "rbih"
                seen_gstins = set()

                for _, row in df2.iterrows():
                    gstin = detect_gstin(_get(row, "gstin"))
                    if not gstin:
                        continue

                    name      = _get(row, "service receiver", "buyer", "recipient", "party")
                    inv_no    = _get(row, "invoice no", "invoice number", "doc no")
                    inv_date  = _get(row, "date of invoice", "invoice date", "date")
                    period    = _get(row, "billing period", "period", "bill period")
                    taxable   = _safe_float(_get(row, "taxable amount", "taxable"))
                    igst      = _safe_float(_get(row, "igst"))
                    cgst      = _safe_float(_get(row, "cgst"))
                    sgst      = _safe_float(_get(row, "sgst"))
                    round_off = _safe_float(_get(row, "round off", "roundoff", "round"))
                    inv_amt   = _safe_float(_get(row, "invoice amount", "debtor amount"))
                    counts    = _safe_float(_get(row, "counts", "count", "qty", "quantity"))
                    unit_price= _safe_float(_get(row, "unit price", "rate", "price"))
                    total_cost= _safe_float(_get(row, "total cost", "total"))
                    remarks   = _get(row, "difference", "remarks", "notes")

                    # Detect doc type from invoice number or remarks
                    doc_type = "CRN" if ("crn" in inv_no.lower() or "credit" in remarks.lower()) else "INV"

                    # Tax type: if IGST>0 → IGST, if CGST>0 → CGST+SGST
                    tax_type = "IGST" if igst > 0 else "CGST+SGST"

                    # Determine HSN/SAC from context (default RBIH = 998319)
                    state_code = gstin[:2]

                    parsed_inv = {
                        "gstin":       gstin,
                        "name":        name,
                        "inv_no":      inv_no,
                        "inv_date":    _parse_date(inv_date),
                        "period":      period,
                        "doc_type":    doc_type,
                        "tax_type":    tax_type,
                        "taxable":     taxable,
                        "igst":        igst,
                        "cgst":        cgst,
                        "sgst":        sgst,
                        "round_off":   round_off,
                        "inv_amt":     inv_amt,
                        "counts":      counts,
                        "unit_price":  unit_price,
                        "total_cost":  total_cost,
                        "state_code":  state_code,
                        "remarks":     remarks,
                    }
                    result["invoices"].append(parsed_inv)

                    if gstin not in seen_gstins:
                        seen_gstins.add(gstin)
                        result["recipients"].append({"gstin": gstin, "name": name,
                                                      "state_code": state_code})

            else:
                # Generic: scan for GSTINs and line items
                for _, row in df2.iterrows():
                    for v in row.values:
                        g = detect_gstin(str(v))
                        if g and g not in [r["gstin"] for r in result["recipients"]]:
                            name_col = next((c for c in df2.columns if "name" in c.lower()), None)
                            name = str(row.get(name_col,"")).strip() if name_col else ""
                            result["recipients"].append({"gstin": g, "name": name,
                                                          "state_code": g[:2]})

    except Exception as e:
        result["errors"].append(str(e))

    return result
