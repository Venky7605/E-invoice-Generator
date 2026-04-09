STATES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
    "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana",
    "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh",
    "13": "Nagaland", "14": "Manipur", "15": "Mizoram",
    "16": "Tripura", "17": "Meghalaya", "18": "Assam",
    "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
    "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra",
    "28": "Andhra Pradesh", "29": "Karnataka", "30": "Goa",
    "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
    "34": "Puducherry", "35": "Andaman and Nicobar Islands",
    "36": "Telangana", "37": "Andhra Pradesh (New)",
    "38": "Ladakh", "97": "Other Territory", "99": "Centre Jurisdiction"
}
STATE_CODES = {v: k for k, v in STATES.items()}

# UQC list — UNT and CNT added as required
UQC_CODES = [
    "UNT", "CNT", "NOS", "BAG", "BAL", "BDL", "BKL", "BOU", "BOX",
    "BTL", "BUN", "CAN", "CBM", "CCM", "CMS", "CTN", "DOZ", "DRM",
    "GGK", "GMS", "GRS", "GYD", "KGS", "KLR", "KME", "LTR", "MLT",
    "MTR", "MTS", "OTH", "PAC", "PCS", "PRS", "QTL", "ROL", "SET",
    "SQF", "SQM", "SQY", "TBS", "TGM", "THD", "TON", "TUB", "UGS", "YDS"
]
UQC_LABELS = {
    "UNT": "UNT — Units", "CNT": "CNT — Count", "NOS": "NOS — Numbers",
    "BAG": "BAG — Bags", "BAL": "BAL — Bales", "BOX": "BOX — Box",
    "BTL": "BTL — Bottles", "KGS": "KGS — Kilograms", "LTR": "LTR — Litres",
    "MTR": "MTR — Metres", "MTS": "MTS — Metric Tonnes", "NOS": "NOS — Numbers",
    "PCS": "PCS — Pieces", "SET": "SET — Set", "TON": "TON — Tonnes",
    "SQM": "SQM — Sq Metres", "CBM": "CBM — Cubic Metres", "DOZ": "DOZ — Dozen",
    "OTH": "OTH — Others", "PRS": "PRS — Pairs", "ROL": "ROL — Rolls",
}

DOC_TYPES = ["INV", "CRN", "DBN"]
SUPPLY_TYPES = {
    "B2B": "Business to Business",
    "SEZWP": "SEZ with Payment",
    "SEZWOP": "SEZ without Payment",
    "EXPWP": "Export with Payment",
    "EXPWOP": "Export without Payment",
    "DEXP": "Deemed Export"
}
GST_RATES = [0, 0.1, 0.25, 1.5, 3, 5, 12, 18, 28]

COMMON_HSN = {
    "998319": {"desc": "Other Information Technology Services", "rate": 18, "type": "S"},
    "998311": {"desc": "IT Design and Development Services", "rate": 18, "type": "S"},
    "998314": {"desc": "IT Consulting and Support Services", "rate": 18, "type": "S"},
    "998313": {"desc": "IT Infrastructure Provisioning Services", "rate": 18, "type": "S"},
    "9983":   {"desc": "Other Professional Services", "rate": 18, "type": "S"},
    "9954":   {"desc": "Construction Services", "rate": 18, "type": "S"},
    "9961":   {"desc": "Wholesale Trade Services", "rate": 18, "type": "S"},
    "9962":   {"desc": "Retail Trade Services", "rate": 18, "type": "S"},
    "4901":   {"desc": "Books, Brochures, Leaflets", "rate": 0,  "type": "G"},
    "6203":   {"desc": "Garments / Apparel", "rate": 12, "type": "G"},
    "8471":   {"desc": "Computers / Laptops", "rate": 18, "type": "G"},
    "8517":   {"desc": "Mobile Phones / Telephones", "rate": 18, "type": "G"},
    "3004":   {"desc": "Medicines / Pharmaceuticals", "rate": 12, "type": "G"},
    "8501":   {"desc": "Electric Motors and Generators", "rate": 18, "type": "G"},
    "8703":   {"desc": "Passenger Motor Vehicles", "rate": 28, "type": "G"},
    "7208":   {"desc": "Flat-rolled Steel Products", "rate": 18, "type": "G"},
    "2710":   {"desc": "Petroleum Oils", "rate": 0,  "type": "G"},
}

def determine_tax_type(supplier_gstin: str, buyer_gstin: str) -> str:
    """Auto-determine IGST vs CGST+SGST based on state codes in GSTINs."""
    if not supplier_gstin or not buyer_gstin or len(supplier_gstin) < 2 or len(buyer_gstin) < 2:
        return "IGST"
    s_state = supplier_gstin[:2]
    b_state = buyer_gstin[:2]
    return "CGST+SGST" if s_state == b_state else "IGST"
