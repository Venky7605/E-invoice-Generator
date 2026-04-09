import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import Image as RLImage

HDR  = colors.HexColor("#1a3c5e")
LBG  = colors.HexColor("#f0f4f8")
ACC  = colors.HexColor("#2563eb")
BDR  = colors.HexColor("#cbd5e1")
RED  = colors.HexColor("#dc2626")
GRN  = colors.HexColor("#16a34a")
W    = colors.white

def _qr_img(data, size=28):
    import qrcode  # lazy import
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=3, border=2)
    qr.add_data(data); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO(); img.save(buf, "PNG"); buf.seek(0)
    return RLImage(buf, width=size*mm, height=size*mm)

def _s(name, **kw):
    styles = getSampleStyleSheet()
    base = {"fontName": "Helvetica", "fontSize": 8, "textColor": colors.HexColor("#1e293b")}
    base.update(kw)
    return ParagraphStyle(name, parent=styles["Normal"], **base)

def generate_einvoice_pdf(invoice_data, irn_data=None):
    buf  = io.BytesIO()
    PW   = A4[0] - 20*mm
    doc  = SimpleDocTemplate(buf, pagesize=A4,
                              topMargin=8*mm, bottomMargin=8*mm,
                              leftMargin=10*mm, rightMargin=10*mm)
    story = []
    inv   = invoice_data
    sel   = inv.get("SellerDtls", {})
    buy   = inv.get("BuyerDtls",  {})
    ddtls = inv.get("DocDtls",    {})
    tran  = inv.get("TranDtls",   {})
    items = inv.get("ItemList",   [])
    val   = inv.get("ValDtls",    {})
    irn   = irn_data or {}

    # styles
    T  = _s("T",  fontName="Helvetica-Bold", fontSize=13, textColor=W, alignment=TA_CENTER)
    H  = _s("H",  fontName="Helvetica-Bold", fontSize=8,  textColor=W)
    HB = _s("HB", fontName="Helvetica-Bold", fontSize=8,  textColor=colors.HexColor("#1e293b"))
    N  = _s("N",  fontSize=7.5)
    NB = _s("NB", fontName="Helvetica-Bold", fontSize=7.5)
    SM = _s("SM", fontSize=6.8, textColor=colors.HexColor("#475569"))
    BL = _s("BL", fontName="Helvetica-Bold", fontSize=8,  textColor=ACC)
    IR = _s("IR", fontSize=6.5, textColor=ACC)
    WN = _s("WN", fontSize=7,   textColor=RED)
    RT = _s("RT", fontName="Helvetica-Bold", fontSize=8,  alignment=TA_RIGHT)

    # ── 1. Header ──────────────────────────────────────────────────
    hdr = Table([[Paragraph("GST e-INVOICE", T)]], colWidths=[PW])
    hdr.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),HDR),
                              ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
                              ("ROUNDEDCORNERS",[4])]))
    story += [hdr, Spacer(1,3*mm)]

    # ── 2. IRN block ───────────────────────────────────────────────
    if irn.get("irn"):
        qr_data = irn.get("signed_qr_code") or f"IRN:{irn['irn']}"
        qr = _qr_img(qr_data, 30)
        sim_row = []
        if irn.get("simulated"):
            sim_row = [[Paragraph("⚠️  SIMULATED IRN — Test Mode only. NOT valid for GST compliance.", WN)]]
        left = Table([
            [Paragraph("IRN (Invoice Reference Number)", NB)],
            [Paragraph(irn.get("irn",""), IR)],
            [Paragraph(f"Ack No: <b>{irn.get('ack_no','')}</b>     Ack Date: <b>{irn.get('ack_dt','')}</b>", N)],
        ] + sim_row, colWidths=[PW-34*mm])
        left.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),("LEFTPADDING",(0,0),(-1,-1),5)]))
        blk = Table([[left, qr]], colWidths=[PW-34*mm, 34*mm])
        blk.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),LBG),("BOX",(0,0),(-1,-1),.5,BDR),
                                  ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                                  ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
        story += [blk, Spacer(1,3*mm)]

    # ── 3. Seller / Buyer ──────────────────────────────────────────
    def party_block(title, p, w):
        rows = [
            [Paragraph(title, H)],
            [Paragraph(f"<b>{p.get('LglNm','')}</b>", NB)],
            [Paragraph(f"GSTIN: <b>{p.get('Gstin','')}</b>", N)],
            [Paragraph(f"{p.get('Addr1','')} {p.get('Addr2','')}", SM)],
            [Paragraph(f"{p.get('Loc','')} – {p.get('Pin','')} | State: {p.get('Stcd','')}", SM)],
        ]
        if p.get("Ph") or p.get("Em"):
            rows.append([Paragraph(f"Ph: {p.get('Ph','')}   Email: {p.get('Em','')}", SM)])
        t = Table(rows, colWidths=[w])
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(0,0),HDR),("BACKGROUND",(0,1),(0,-1),W),
                                ("BOX",(0,0),(-1,-1),.5,BDR),("TOPPADDING",(0,0),(-1,-1),3),
                                ("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),5)]))
        return t
    half = PW/2 - 1.5*mm
    pr = Table([[party_block("SUPPLIER", sel, half), party_block("BUYER / RECIPIENT", buy, half)]],
               colWidths=[PW/2, PW/2])
    pr.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(1,0),(1,0),3)]))
    story += [pr, Spacer(1,3*mm)]

    # ── 4. Doc details ─────────────────────────────────────────────
    w4 = PW/4
    dd = Table([
        [Paragraph("Doc Type",NB), Paragraph("Doc Number",NB), Paragraph("Doc Date",NB), Paragraph("Supply Type",NB)],
        [Paragraph(ddtls.get("Typ",""),N), Paragraph(ddtls.get("No",""),N),
         Paragraph(ddtls.get("Dt",""),N), Paragraph(tran.get("SupTyp",""),N)],
        [Paragraph("Rev. Charge",NB), Paragraph("Place of Supply",NB), Paragraph("IGST on Intra",NB), Paragraph("",NB)],
        [Paragraph(tran.get("RegRev","N"),N), Paragraph(buy.get("Pos",""),N),
         Paragraph(tran.get("IgstOnIntra","N"),N), Paragraph("",N)],
    ], colWidths=[w4]*4)
    dd.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),LBG),("BACKGROUND",(0,2),(-1,2),LBG),
                             ("BOX",(0,0),(-1,-1),.5,BDR),("INNERGRID",(0,0),(-1,-1),.3,BDR),
                             ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
                             ("LEFTPADDING",(0,0),(-1,-1),5)]))
    story += [dd, Spacer(1,3*mm)]

    # ── 5. Line items ──────────────────────────────────────────────
    cw = [7*mm, 48*mm, 16*mm, 14*mm, 10*mm, 16*mm, 9*mm, 18*mm, 20*mm, 22*mm]
    ih = [Paragraph(h, H) for h in ["#","Description","HSN/SAC","Qty","Unit","Unit Price","GST%","Taxable Amt","Tax Amt","Item Total"]]
    irows = [ih]
    for item in items:
        tax = float(item.get("IgstAmt",0)) + float(item.get("CgstAmt",0)) + float(item.get("SgstAmt",0))
        irows.append([
            Paragraph(item.get("SlNo",""),N),
            Paragraph(item.get("PrdDesc",""),N),
            Paragraph(item.get("HsnCd",""),N),
            Paragraph(f"{item.get('Qty',0):,.3f}",N),
            Paragraph(item.get("Unit",""),N),
            Paragraph(f"₹{float(item.get('UnitPrice',0)):,.2f}",N),
            Paragraph(f"{item.get('GstRt',0)}%",N),
            Paragraph(f"₹{float(item.get('AssAmt',0)):,.2f}",N),
            Paragraph(f"₹{tax:,.2f}",N),
            Paragraph(f"₹{float(item.get('TotItemVal',0)):,.2f}",N),
        ])
    it = Table(irows, colWidths=cw)
    it.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),HDR),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[W,LBG]),
        ("BOX",(0,0),(-1,-1),.5,BDR),("INNERGRID",(0,0),(-1,-1),.3,BDR),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]))
    story += [it, Spacer(1,3*mm)]

    # ── 6. Totals ──────────────────────────────────────────────────
    EMPTY = _s("EMPTY", fontSize=7)
    def trow(lbl, amt, bold=False):
        s = NB if bold else N
        return [Paragraph("",EMPTY),Paragraph("",EMPTY),Paragraph("",EMPTY),Paragraph("",EMPTY),
                Paragraph("",EMPTY),Paragraph("",EMPTY),Paragraph("",EMPTY),Paragraph("",EMPTY),
                Paragraph(lbl,s),Paragraph(f"₹{amt:,.2f}",s)]
    tdata = [
        trow("Taxable Value",  val.get("AssVal",0)),
        trow("CGST",           val.get("CgstVal",0)),
        trow("SGST",           val.get("SgstVal",0)),
        trow("IGST",           val.get("IgstVal",0)),
        trow("Cess",           val.get("CesVal",0)),
        trow("Other Charges",  val.get("OthChrg",0)),
        trow("Discount",       -val.get("Discount",0)),
        trow("Round Off",      val.get("RndOffAmt",0)),
        trow("TOTAL INVOICE VALUE", val.get("TotInvVal",0), bold=True),
    ]
    tt = Table(tdata, colWidths=cw)
    tt.setStyle(TableStyle([
        ("BACKGROUND",(8,-1),(9,-1),HDR),("TEXTCOLOR",(8,-1),(9,-1),W),
        ("BOX",(0,0),(-1,-1),.5,BDR),("INNERGRID",(0,0),(-1,-1),.3,BDR),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),4),
    ]))
    story.append(tt)

    # ── 7. Amount in words ─────────────────────────────────────────
    amt_words = _num_to_words(val.get("TotInvVal",0))
    story += [Spacer(1,2*mm),
              Paragraph(f"<b>Amount in Words:</b> {amt_words}", N),
              Spacer(1,4*mm)]

    # ── 8. Footer ──────────────────────────────────────────────────
    footer = _s("FT", fontSize=6.5, textColor=colors.grey, alignment=TA_CENTER)
    story.append(Paragraph(
        "This is a computer-generated e-Invoice. IRN is digitally signed by the Invoice Registration Portal (IRP) of GSTN. "
        "Generated using GePP Python Tool.", footer))

    doc.build(story)
    buf.seek(0)
    return buf

def _num_to_words(n):
    """Convert number to Indian rupee words."""
    try:
        n = round(float(n), 2)
        ones = ["","One","Two","Three","Four","Five","Six","Seven","Eight","Nine",
                "Ten","Eleven","Twelve","Thirteen","Fourteen","Fifteen","Sixteen",
                "Seventeen","Eighteen","Nineteen"]
        tens = ["","","Twenty","Thirty","Forty","Fifty","Sixty","Seventy","Eighty","Ninety"]
        def _w(num):
            if num == 0: return ""
            elif num < 20: return ones[num]
            elif num < 100: return tens[num//10] + (" " + ones[num%10] if num%10 else "")
            else: return ones[num//100] + " Hundred" + (" " + _w(num%100) if num%100 else "")
        rupees = int(n); paise = round((n - rupees) * 100)
        parts = []
        cr = rupees // 10000000; rupees %= 10000000
        lac = rupees // 100000;  rupees %= 100000
        th  = rupees // 1000;    rupees %= 1000
        if cr:  parts.append(_w(cr)  + " Crore")
        if lac: parts.append(_w(lac) + " Lakh")
        if th:  parts.append(_w(th)  + " Thousand")
        if rupees: parts.append(_w(rupees))
        result = " ".join(parts) + " Rupees"
        if paise: result += f" and {_w(paise)} Paise"
        return result + " Only"
    except:
        return "Amount in words unavailable"
