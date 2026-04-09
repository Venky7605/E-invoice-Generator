import json

def build_invoice_json(form_data):
    sup  = form_data["supplier"]
    buy  = form_data["buyer"]
    doc  = form_data["doc"]
    items= form_data["items"]
    val  = form_data["val"]

    payload = {
        "Version": "1.1",
        "TranDtls": {
            "TaxSch": "GST",
            "SupTyp": doc["supply_type"],
            "RegRev": doc.get("reverse_charge", "N"),
            "IgstOnIntra": doc.get("igst_on_intra", "N")
        },
        "DocDtls": {"Typ": doc["doc_type"], "No": doc["doc_no"], "Dt": doc["doc_date"]},
        "SellerDtls": {
            "Gstin": sup["gstin"], "LglNm": sup["legal_name"],
            "TrdNm": sup.get("trade_name", sup["legal_name"]),
            "Addr1": sup["addr1"], "Addr2": sup.get("addr2",""),
            "Loc": sup["location"], "Pin": int(sup["pincode"]),
            "Stcd": sup["state_code"], "Ph": sup.get("phone",""), "Em": sup.get("email","")
        },
        "BuyerDtls": {
            "Gstin": buy["gstin"], "LglNm": buy["legal_name"],
            "TrdNm": buy.get("trade_name", buy["legal_name"]),
            "Pos": buy.get("pos", buy["state_code"]),
            "Addr1": buy["addr1"], "Addr2": buy.get("addr2",""),
            "Loc": buy["location"], "Pin": int(buy["pincode"]),
            "Stcd": buy["state_code"], "Ph": buy.get("phone",""), "Em": buy.get("email","")
        },
        "ItemList": _build_items(items),
        "ValDtls": {
            "AssVal":    round(val["ass_val"], 2),
            "CgstVal":   round(val.get("cgst_val", 0), 2),
            "SgstVal":   round(val.get("sgst_val", 0), 2),
            "IgstVal":   round(val.get("igst_val", 0), 2),
            "CesVal":    round(val.get("cess_val", 0), 2),
            "StCesVal":  round(val.get("st_cess_val", 0), 2),
            "Discount":  round(val.get("discount", 0), 2),
            "OthChrg":   round(val.get("other_charges", 0), 2),
            "RndOffAmt": round(val.get("round_off", 0), 2),
            "TotInvVal": round(val["tot_inv_val"], 2),
        }
    }
    if doc.get("ecom_gstin"):
        payload["TranDtls"]["EcmGstin"] = doc["ecom_gstin"]
    return payload

def _build_items(items):
    out = []
    for i, item in enumerate(items, 1):
        out.append({
            "SlNo": str(i),
            "PrdDesc": item["description"],
            "IsServc": item.get("is_service", "N"),
            "HsnCd":  item["hsn"],
            "Qty":    round(float(item.get("qty", 0)), 3),
            "Unit":   item.get("uqc", "NOS"),
            "UnitPrice":  round(float(item["unit_price"]), 2),
            "TotAmt":     round(float(item["total_amt"]), 2),
            "Discount":   round(float(item.get("discount", 0)), 2),
            "AssAmt":     round(float(item["ass_amt"]), 2),
            "GstRt":      round(float(item["gst_rate"]), 2),
            "IgstAmt":    round(float(item.get("igst_amt", 0)), 2),
            "CgstAmt":    round(float(item.get("cgst_amt", 0)), 2),
            "SgstAmt":    round(float(item.get("sgst_amt", 0)), 2),
            "CesRt":      round(float(item.get("cess_rate", 0)), 2),
            "CesAmt":     round(float(item.get("cess_amt", 0)), 2),
            "CesNonAdvlAmt":    round(float(item.get("cess_non_adv_amt", 0)), 2),
            "StateCesRt":       round(float(item.get("state_cess_rate", 0)), 2),
            "StateCesAmt":      round(float(item.get("state_cess_amt", 0)), 2),
            "StateCesNonAdvlAmt": round(float(item.get("state_cess_non_adv_amt", 0)), 2),
            "OthChrg":    round(float(item.get("other_charges", 0)), 2),
            "TotItemVal": round(float(item["tot_item_val"]), 2),
        })
    return out

def calculate_item_taxes(unit_price, qty, discount, gst_rate, cess_rate, tax_type):
    total_amt = round(unit_price * qty, 2)
    ass_amt   = round(total_amt - discount, 2)
    gst_amt   = round(ass_amt * gst_rate / 100, 2)
    cess_amt  = round(ass_amt * cess_rate / 100, 2)
    igst_amt = cgst_amt = sgst_amt = 0.0
    if tax_type == "IGST":
        igst_amt = gst_amt
    else:
        cgst_amt = round(gst_amt / 2, 2)
        sgst_amt = round(gst_amt / 2, 2)
    tot_item_val = round(ass_amt + gst_amt + cess_amt, 2)
    return {"total_amt": total_amt, "ass_amt": ass_amt,
            "igst_amt": igst_amt, "cgst_amt": cgst_amt, "sgst_amt": sgst_amt,
            "cess_amt": cess_amt, "tot_item_val": tot_item_val}

def calculate_totals(items, other_charges=0, discount=0, round_off=0):
    ass_val   = round(sum(float(i["ass_amt"])          for i in items), 2)
    igst_val  = round(sum(float(i.get("igst_amt",0))   for i in items), 2)
    cgst_val  = round(sum(float(i.get("cgst_amt",0))   for i in items), 2)
    sgst_val  = round(sum(float(i.get("sgst_amt",0))   for i in items), 2)
    cess_val  = round(sum(float(i.get("cess_amt",0))   for i in items), 2)
    st_cess   = round(sum(float(i.get("state_cess_amt",0)) for i in items), 2)
    tot_inv_val = round(ass_val + igst_val + cgst_val + sgst_val +
                        cess_val + st_cess + other_charges - discount + round_off, 2)
    return {"ass_val": ass_val, "igst_val": igst_val, "cgst_val": cgst_val,
            "sgst_val": sgst_val, "cess_val": cess_val, "st_cess_val": st_cess,
            "other_charges": other_charges, "discount": discount,
            "round_off": round_off, "tot_inv_val": tot_inv_val}
