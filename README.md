# 🧾 GePP Tool — Python Edition v2.0
## GST e-Invoice Preparing and Printing Tool

Full Python/Streamlit replacement for NIC's Excel-based GePP tool.
Works natively on **macOS, Linux, and Windows** — no Excel, no ActiveX required.

---

## ✅ Features

| Feature | Details |
|---------|---------|
| Invoice Creation | Doc details, buyer, line items, taxes |
| Auto Tax Detection | IGST vs CGST+SGST based on GSTIN state codes |
| GSTIN Verification | Live check via GST portal |
| HSN/SAC Master | With description + code auto-fill |
| Recipient Master | Save buyers, auto-fill in invoices |
| Invoice Preview | HTML preview before saving |
| JSON Generation | NIC-compliant e-Invoice JSON |
| IRN via API | Direct NIC IRP integration |
| Test/Simulate IRN | Full workflow without API credentials |
| PDF e-Invoice | IRN, QR code, all details, amount in words |
| Excel/CSV Import | Auto-extract GSTINs, line items from Excel |
| UNT / CNT UQC | Units and Count in UQC dropdown |
| Dashboard | Invoice stats and recent history |

---

## 🚀 Setup & Run (macOS)

```bash
# Step 1: Move downloaded ZIP to Downloads and unzip
cd ~/Downloads
unzip gepp_tool_python.zip
cd gepp_tool

# Step 2: Create virtual environment (fixes Mac externally-managed error)
python3 -m venv venv
source venv/bin/activate

# Step 3: Install dependencies
pip install -r requirements.txt

# Step 4: Launch
streamlit run app.py
```

Browser opens automatically at **http://localhost:8501**

---

## 🔄 Run Again (after closing terminal)

```bash
cd ~/Downloads/gepp_tool
source venv/bin/activate
streamlit run app.py
```

---

## 📁 Project Structure

```
gepp_tool/
├── app.py                    ← Main Streamlit app
├── requirements.txt
├── README.md
├── data/                     ← Auto-created local storage
│   ├── supplier.json         ← Your GSTIN & address
│   ├── recipients.json       ← Buyer masters
│   ├── hsn_master.json       ← HSN/SAC codes
│   └── invoices.json         ← All invoices (pending + generated)
├── pages/
│   ├── dashboard.py          ← Home dashboard
│   ├── supplier.py           ← Supplier profile setup
│   ├── create_inv.py         ← Invoice creation form
│   ├── excel_page.py         ← Excel/CSV importer
│   ├── pending.py            ← Pending invoices + IRN submission
│   ├── generated.py          ← Generated invoices + PDF download
│   ├── recipients.py         ← Recipient master with GSTIN verify
│   ├── hsn.py                ← HSN/SAC master
│   └── api_settings.py       ← NIC API credentials
└── utils/
    ├── masters.py            ← State codes, UQC, HSN reference, tax type logic
    ├── db.py                 ← Local JSON data store
    ├── json_builder.py       ← NIC-compliant JSON builder
    ├── nic_api.py            ← NIC IRP API client + GSTIN verifier
    ├── pdf_gen.py            ← e-Invoice PDF with QR code
    └── excel_import.py       ← Excel/CSV data extractor
```

---

## 🔗 Getting API Credentials (for Live IRN)

1. Go to **https://einvoice1.gst.gov.in**
2. Login with your GSTIN credentials
3. Navigate to **User Credentials → Create API User**
4. Note down: **Client ID**, **Client Secret**
5. Set API Username and Password
6. Enter these in **🔗 API Settings** page

> Without API credentials, use **Test Mode** to simulate the full workflow.
> Simulated IRNs are NOT valid for GST compliance.

---

## ⚠️ Disclaimer

This tool interfaces with NIC's e-Invoice APIs.
Always verify compliance requirements with your CA or tax professional.
