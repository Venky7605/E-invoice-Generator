import json, os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

def _load(filename):
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}

def _save(filename, data):
    with open(os.path.join(DATA_DIR, filename), "w") as f:
        json.dump(data, f, indent=2)

def get_supplier():      return _load("supplier.json")
def save_supplier(d):    _save("supplier.json", d)

def get_recipients():    return _load("recipients.json")
def save_recipient(gstin, d):
    r = get_recipients(); r[gstin] = d; _save("recipients.json", r)
def delete_recipient(gstin):
    r = get_recipients(); r.pop(gstin, None); _save("recipients.json", r)

def get_hsn_master():    return _load("hsn_master.json")
def save_hsn(code, d):
    h = get_hsn_master(); h[code] = d; _save("hsn_master.json", h)
def delete_hsn(code):
    h = get_hsn_master(); h.pop(code, None); _save("hsn_master.json", h)

def get_invoices():      return _load("invoices.json")
def save_invoice(inv):
    invs = get_invoices()
    key = f"{inv['DocDtls']['Typ']}_{inv['DocDtls']['No']}_{inv['DocDtls']['Dt']}".replace("/","_")
    inv["_status"] = inv.get("_status", "PENDING")
    inv["_saved_at"] = datetime.now().isoformat()
    invs[key] = inv; _save("invoices.json", invs); return key
def update_invoice_irn(key, irn_data):
    invs = get_invoices()
    if key in invs:
        invs[key]["_irn_data"] = irn_data
        invs[key]["_status"] = "IRN_GENERATED"
        _save("invoices.json", invs)
def get_pending_invoices():
    return {k: v for k, v in get_invoices().items() if v.get("_status") == "PENDING"}
def get_generated_invoices():
    return {k: v for k, v in get_invoices().items() if v.get("_status") == "IRN_GENERATED"}
def get_cancelled_invoices():
    return {k: v for k, v in get_invoices().items() if v.get("_status") == "CANCELLED"}
def delete_invoice(key):
    invs = get_invoices(); invs.pop(key, None); _save("invoices.json", invs)
def cancel_invoice(key, cancel_data):
    invs = get_invoices()
    if key in invs:
        invs[key]["_cancel_data"] = cancel_data
        invs[key]["_status"] = "CANCELLED"
        invs[key]["_cancelled_at"] = datetime.now().isoformat()
        _save("invoices.json", invs)
def clone_invoice(key, new_doc_no, new_date):
    invs = get_invoices()
    if key not in invs:
        return None
    import copy
    cloned = copy.deepcopy(invs[key])
    cloned["DocDtls"]["No"] = new_doc_no
    cloned["DocDtls"]["Dt"] = new_date
    cloned.pop("_irn_data", None)
    cloned.pop("_cancel_data", None)
    cloned.pop("_cancelled_at", None)
    cloned["_status"] = "PENDING"
    cloned["_cloned_from"] = key
    return save_invoice(cloned)
def get_templates():
    return _load("templates.json")
def save_template(name, inv_data):
    t = get_templates()
    t[name] = {"_name": name, "_saved_at": datetime.now().isoformat(), **inv_data}
    _save("templates.json", t)
def delete_template(name):
    t = get_templates(); t.pop(name, None); _save("templates.json", t)
