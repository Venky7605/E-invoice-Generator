import requests, json, hashlib, base64, random, string, re, threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

NIC_PROD_URL    = "https://einvoice1.gst.gov.in/eicore/v1"
NIC_SANDBOX_URL = "https://einv-apisandbox.nic.in/eicore/v1"
PROXY_PORT      = 8765

GSTIN_RE = re.compile(r'^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$')

STATE_NAMES = {
    "01":"Jammu and Kashmir","02":"Himachal Pradesh","03":"Punjab","04":"Chandigarh",
    "05":"Uttarakhand","06":"Haryana","07":"Delhi","08":"Rajasthan","09":"Uttar Pradesh",
    "10":"Bihar","11":"Sikkim","12":"Arunachal Pradesh","13":"Nagaland","14":"Manipur",
    "15":"Mizoram","16":"Tripura","17":"Meghalaya","18":"Assam","19":"West Bengal",
    "20":"Jharkhand","21":"Odisha","22":"Chhattisgarh","23":"Madhya Pradesh",
    "24":"Gujarat","26":"Dadra and Nagar Haveli and Daman and Diu","27":"Maharashtra",
    "28":"Andhra Pradesh","29":"Karnataka","30":"Goa","31":"Lakshadweep","32":"Kerala",
    "33":"Tamil Nadu","34":"Puducherry","35":"Andaman and Nicobar Islands",
    "36":"Telangana","37":"Andhra Pradesh (New)","38":"Ladakh",
    "97":"Other Territory","99":"Centre Jurisdiction"
}

# ── Local CORS proxy server ────────────────────────────────────────
_proxy_started = False

class _GSTProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass  # Suppress logs

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        try:
            # Path: /gstin/GSTIN_NUMBER
            parts = self.path.strip("/").split("/")
            if len(parts) >= 2 and parts[0] == "gstin":
                gstin = parts[1].upper()
                result = _fetch_gstin_server_side(gstin)
                body = json.dumps(result).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self._cors()
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()
        except Exception as e:
            body = json.dumps({"success": False, "error": str(e)}).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self._cors()
            self.end_headers()
            self.wfile.write(body)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def start_proxy():
    """Start the GSTIN proxy server in a background thread (idempotent)."""
    global _proxy_started
    if _proxy_started:
        return
    try:
        server = HTTPServer(("127.0.0.1", PROXY_PORT), _GSTProxyHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        _proxy_started = True
    except OSError:
        # Port already in use — proxy already running
        _proxy_started = True


def _fetch_gstin_server_side(gstin: str) -> dict:
    """Server-side GSTIN fetch — tries multiple APIs."""
    sc = gstin[:2]
    sn = STATE_NAMES.get(sc, "Unknown")

    browser_hdrs = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://services.gst.gov.in/services/searchtp",
        "Origin": "https://services.gst.gov.in",
    }

    # ── Source 1: gstincheck.co.in ──────────────────────────────────
    for api_key in ["demo", "free", "test"]:
        try:
            r = requests.get(
                f"https://sheet.gstincheck.co.in/check/{api_key}/{gstin}",
                headers=browser_hdrs, timeout=8
            )
            if r.status_code == 200 and r.text.strip():
                d = r.json()
                if d.get("flag") is True and d.get("data"):
                    data  = d["data"]
                    pradr = data.get("pradr", {})
                    addr  = pradr.get("addr", {})
                    parts = [str(addr.get(k,"")).strip()
                             for k in ["bnm","bno","flno","st","loc","dst"] if addr.get(k)]
                    full  = ", ".join(parts)
                    pin   = str(addr.get("pncd","")).strip()
                    loc   = addr.get("loc","") or addr.get("dst","")
                    return {
                        "success":    True,
                        "source":     "gstincheck.co.in",
                        "legal_name": data.get("lgnm",""),
                        "trade_name": data.get("tradeNam","") or data.get("lgnm",""),
                        "status":     data.get("sts","Active"),
                        "addr":       full,
                        "location":   loc,
                        "pincode":    pin,
                        "state_code": sc,
                        "state_name": sn,
                    }
        except Exception:
            continue

    # ── Source 2: GST Portal direct ─────────────────────────────────
    try:
        r = requests.get(
            f"https://services.gst.gov.in/services/api/search/taxpayerDetails?gstin={gstin}",
            headers=browser_hdrs, timeout=8
        )
        if r.status_code == 200 and r.text.strip():
            d = r.json()
            if not d.get("errorCode") and d.get("taxpayerInfo"):
                tp    = d["taxpayerInfo"]
                pradr = tp.get("pradr", {})
                full  = pradr.get("adr","")
                pin   = str(pradr.get("pncd",""))
                return {
                    "success":    True,
                    "source":     "GST Portal",
                    "legal_name": tp.get("lgnm",""),
                    "trade_name": tp.get("tradeNam","") or tp.get("lgnm",""),
                    "status":     tp.get("sts",""),
                    "addr":       full,
                    "location":   "",
                    "pincode":    pin,
                    "state_code": sc,
                    "state_name": sn,
                }
    except Exception:
        pass

    return {
        "success":    False,
        "state_code": sc,
        "state_name": sn,
        "error":      "Could not reach GST portal. Please fill address manually."
    }


# ── Public API ─────────────────────────────────────────────────────

def validate_gstin_format(gstin: str) -> dict:
    """Validate GSTIN format — always works offline."""
    gstin = gstin.strip().upper()
    if not gstin:
        return {"valid": False, "error": "GSTIN cannot be empty"}
    if len(gstin) != 15:
        return {"valid": False, "error": f"GSTIN must be 15 characters (got {len(gstin)})"}
    if not GSTIN_RE.match(gstin):
        return {"valid": False,
                "error": "Invalid format: 2 digits + 5 letters + 4 digits + 1 letter + 1 alphanumeric + Z + 1 alphanumeric"}
    sc = gstin[:2]
    return {"valid": True, "gstin": gstin,
            "state_code": sc, "state_name": STATE_NAMES.get(sc,"Unknown"),
            "pan": gstin[2:12]}


def fetch_gstin_details(gstin: str) -> dict:
    """
    Fetch GSTIN details — starts local proxy if needed, then calls it.
    The proxy runs on localhost:8765 and makes the actual HTTP requests
    to the GST portal from Python (no CORS restrictions).
    """
    start_proxy()
    fmt = validate_gstin_format(gstin)
    if not fmt["valid"]:
        return {"success": False, "error": fmt["error"]}
    try:
        r = requests.get(f"http://127.0.0.1:{PROXY_PORT}/gstin/{gstin.upper()}",
                         timeout=15)
        return r.json()
    except Exception as e:
        return {"success": False, "error": str(e),
                "state_code": gstin[:2],
                "state_name": STATE_NAMES.get(gstin[:2],"Unknown")}


def parse_fetched(result: dict, gstin: str) -> dict:
    """Normalise fetched result into standard form used by pages."""
    sc = gstin[:2] if len(gstin) >= 2 else ""
    sn = STATE_NAMES.get(sc,"Unknown")
    if not result or not result.get("success"):
        return {"valid": False,
                "source":     "failed",
                "state_code": result.get("state_code", sc) if result else sc,
                "state_name": result.get("state_name", sn) if result else sn,
                "error":      result.get("error","Could not fetch from GST portal") if result else "No response"}
    full = result.get("addr","")
    return {
        "valid":       True,
        "source":      result.get("source","GST Portal"),
        "gstin":       gstin.upper(),
        "legal_name":  result.get("legal_name",""),
        "trade_name":  result.get("trade_name","") or result.get("legal_name",""),
        "status":      result.get("status","Active"),
        "state_code":  result.get("state_code", sc),
        "state_name":  result.get("state_name", sn),
        "addr":        full,
        "addr1":       full[:60].strip(),
        "addr2":       full[60:120].strip() if len(full)>60 else "",
        "location":    result.get("location",""),
        "pincode":     result.get("pincode",""),
    }


# Legacy compat
def verify_gstin(gstin: str, api_config: dict = None) -> dict:
    result = fetch_gstin_details(gstin)
    parsed = parse_fetched(result, gstin)
    if not parsed.get("valid"):
        fmt = validate_gstin_format(gstin)
        if fmt.get("valid"):
            return {"valid": True, "source": "local",
                    "gstin": gstin.upper(), "legal_name": "", "trade_name": "",
                    "status": "Format valid — not verified online",
                    "state_code": fmt["state_code"], "state_name": fmt["state_name"],
                    "addr": "", "addr1": "", "addr2": "", "location": "", "pincode": "",
                    "note": f"GSTIN format valid. State: {fmt['state_name']}. Fill address manually."}
        return {"valid": False, "error": fmt.get("error","Invalid GSTIN")}
    return parsed


# ── NIC IRN client ─────────────────────────────────────────────────
class NICAPIClient:
    def __init__(self, gstin, client_id, client_secret, username, password, sandbox=False):
        self.gstin=gstin; self.client_id=client_id; self.client_secret=client_secret
        self.username=username; self.password=password
        self.base_url = NIC_SANDBOX_URL if sandbox else NIC_PROD_URL
        self.auth_token = None

    def _headers(self, auth=True):
        h = {"client_id": self.client_id, "client_secret": self.client_secret,
             "gstin": self.gstin, "user_name": self.username, "Content-Type": "application/json"}
        if auth and self.auth_token: h["AuthToken"] = self.auth_token
        return h

    def authenticate(self):
        app_key = base64.b64encode(
            hashlib.sha256(f"{self.client_id}{self.client_secret}{self.username}".encode()).digest()
        ).decode()
        try:
            r = requests.post(f"{self.base_url}/user/authtoken",
                json={"UserName": self.username, "Password": self.password,
                      "AppKey": app_key, "ForceRefreshAccessToken": True},
                headers=self._headers(auth=False), timeout=30)
            d = r.json()
            if d.get("Status")==1:
                self.auth_token = d["AuthToken"]; return {"success": True}
            return {"success": False, "error": d.get("ErrorDetails",[{}])[0].get("ErrorMessage","Auth failed")}
        except Exception as e: return {"success": False, "error": str(e)}

    def generate_irn(self, invoice_json):
        if not self.auth_token:
            auth = self.authenticate()
            if not auth["success"]: return auth
        try:
            r = requests.post(f"{self.base_url}/Invoice/eInvoice",
                              data=json.dumps(invoice_json), headers=self._headers(), timeout=30)
            d = r.json()
            if d.get("Status")==1:
                info = d.get("InfoDtls",[{}])[0]
                return {"success": True, "irn": info.get("Irn"), "ack_no": info.get("AckNo"),
                        "ack_dt": info.get("AckDt"), "signed_qr_code": info.get("SignedQRCode")}
            return {"success": False, "error": "; ".join(e.get("ErrorMessage","") for e in d.get("ErrorDetails",[{}]))}
        except Exception as e: return {"success": False, "error": str(e)}

    def cancel_irn(self, irn, reason_code, remark):
        try:
            r = requests.post(f"{self.base_url}/Invoice/eInvoice/Cancel",
                              json={"Irn": irn, "CnlRsn": reason_code, "CnlRem": remark},
                              headers=self._headers(), timeout=30)
            d = r.json(); return {"success": d.get("Status")==1, "data": d}
        except Exception as e: return {"success": False, "error": str(e)}


def simulate_irn_generation(invoice_json):
    irn    = hashlib.sha256(json.dumps(invoice_json, sort_keys=True).encode()).hexdigest()
    ack_no = ''.join(random.choices(string.digits, k=15))
    ack_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    qr_data = f"IRN:{irn}|AckNo:{ack_no}|AckDt:{ack_dt}|GSTIN:{invoice_json.get('SellerDtls',{}).get('Gstin','')}"
    return {"success": True, "irn": irn, "ack_no": ack_no, "ack_dt": ack_dt,
            "signed_qr_code": qr_data, "simulated": True}
