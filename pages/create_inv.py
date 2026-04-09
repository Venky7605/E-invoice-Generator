import streamlit as st
import json
from datetime import date
from utils.db import get_supplier, get_recipients, get_hsn_master, save_invoice
from utils.masters import STATES, STATE_CODES, DOC_TYPES, SUPPLY_TYPES, UQC_CODES, GST_RATES, determine_tax_type
from utils.json_builder import build_invoice_json, calculate_item_taxes, calculate_totals
from utils.nic_api import verify_gstin

def show():
    st.markdown("<div class='section-header'>📝 Create New e-Invoice</div>", unsafe_allow_html=True)

    supplier = get_supplier()
    if not supplier:
        st.error("⚠️ Set up your Supplier Profile first (⚙️ in the sidebar).")
        return

    recipients = get_recipients()
    hsn_master = get_hsn_master()

    # ── Recipient picker — drives all buyer fields ────────────────────
    rec_opts = ["-- Enter Manually --"] + [f"{v['legal_name']}  ({k})" for k, v in recipients.items()]
    sel_rec  = st.selectbox("📌 Select Buyer from Recipient Master", rec_opts, key="sel_rec_main")

    # Reset buyer cache when recipient changes
    prev_rec = st.session_state.get("_prev_rec", "")
    if sel_rec != prev_rec:
        st.session_state["_prev_rec"]        = sel_rec
        st.session_state["_buyer_data"]      = {}
        st.session_state["_gstin_verified"]  = {}
        if sel_rec != "-- Enter Manually --":
            gstin_key = sel_rec.split("(")[-1].rstrip(")")
            st.session_state["_buyer_data"]  = recipients.get(gstin_key, {})

    buyer_prefill = st.session_state.get("_buyer_data", {})
    vd            = st.session_state.get("_gstin_verified", {})

    # ── Section 1: Document Details ─────────────────────────────────
    with st.expander("📄 Document Details", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1: doc_type    = st.selectbox("Document Type *", DOC_TYPES, key="doc_type")
        with c2: doc_no      = st.text_input("Document Number *", placeholder="2025-26/03/0001", key="doc_no")
        with c3: doc_date    = st.date_input("Document Date *", value=date.today(), key="doc_date")
        with c4: supply_type = st.selectbox("Supply Type *", list(SUPPLY_TYPES.keys()),
                                             format_func=lambda x: f"{x} — {SUPPLY_TYPES[x]}", key="supply_type")
        c1, c2, c3 = st.columns(3)
        with c1: reverse_charge = st.selectbox("Reverse Charge", ["N","Y"], key="rev_chrg")
        with c2: igst_on_intra  = st.selectbox("IGST on Intra", ["N","Y"], key="igst_intra")
        with c3: ecom_gstin     = st.text_input("E-Commerce GSTIN (if any)", max_chars=15, key="ecom_gstin")

    # ── Section 2: Buyer Details ─────────────────────────────────────
    with st.expander("🏢 Buyer / Recipient Details", expanded=True):
        col_g, col_b = st.columns([4, 1])
        with col_g:
            b_gstin = st.text_input("Buyer GSTIN *",
                                     value=buyer_prefill.get("gstin", ""),
                                     max_chars=15, key="b_gstin")
        with col_b:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔍 Verify GSTIN", key="verify_b", use_container_width=True):
                if b_gstin:
                    with st.spinner("Checking GST portal..."):
                        api_cfg = st.session_state.get("api_config",{})
                    res = verify_gstin(b_gstin.upper(), api_cfg)
                    if res["valid"]:
                        st.session_state["_gstin_verified"] = res
                        vd = res
                        st.success(f"✅ {res['legal_name']} — {res['status']}")
                    else:
                        st.error(f"❌ {res['error']}")

        # Auto tax detection
        eff_gstin = b_gstin or buyer_prefill.get("gstin", "")
        auto_tax  = determine_tax_type(supplier.get("gstin",""), eff_gstin)
        st.info(f"🔄 Tax type auto-detected from GSTINs: **{auto_tax}** "
                f"({'Same state → CGST+SGST' if auto_tax=='CGST+SGST' else 'Inter-state → IGST'})")
        tax_type = st.radio("Override Tax Type if needed", ["IGST","CGST+SGST"],
                             index=0 if auto_tax=="IGST" else 1,
                             horizontal=True, key="tax_type_radio")

        c1, c2 = st.columns(2)
        with c1:
            b_legal = st.text_input("Legal Name *",
                                     value=buyer_prefill.get("legal_name") or vd.get("legal_name",""),
                                     key="b_legal")
            b_trade = st.text_input("Trade Name",
                                     value=buyer_prefill.get("trade_name") or vd.get("trade_name",""),
                                     key="b_trade")
            b_phone = st.text_input("Phone",  value=buyer_prefill.get("phone",""),  key="b_phone")
            b_email = st.text_input("Email",  value=buyer_prefill.get("email",""),  key="b_email")
        with c2:
            raw_addr = vd.get("addr","")
            b_addr1  = st.text_input("Address Line 1 *",
                                      value=buyer_prefill.get("addr1") or (raw_addr[:60] if raw_addr else ""),
                                      key="b_addr1")
            b_addr2  = st.text_input("Address Line 2",
                                      value=buyer_prefill.get("addr2") or (raw_addr[60:120] if len(raw_addr)>60 else ""),
                                      key="b_addr2")
            b_loc    = st.text_input("City / Location *",
                                      value=buyer_prefill.get("location",""),
                                      key="b_loc")

            # State — derive from GSTIN first 2 digits, fallback to saved, fallback to KA
            state_list   = list(STATES.values())
            gstin_sc     = eff_gstin[:2] if len(eff_gstin) >= 2 else ""
            saved_sc     = buyer_prefill.get("state_code","")
            effective_sc = saved_sc or gstin_sc or "29"
            state_default = STATES.get(effective_sc, "Karnataka")
            state_idx     = state_list.index(state_default) if state_default in state_list else 0
            b_state_name  = st.selectbox("State *", state_list, index=state_idx, key="b_state")
            b_state_code  = STATE_CODES.get(b_state_name, "29")

            b_pincode = st.text_input("Pincode *",
                                       value=str(buyer_prefill.get("pincode","")),
                                       max_chars=6, key="b_pincode")
            b_pos     = st.text_input("Place of Supply (State Code)",
                                       value=b_state_code, max_chars=2, key="b_pos")

        if gstin_sc:
            st.caption(f"ℹ️ GSTIN `{eff_gstin[:2]}` → State: **{STATES.get(gstin_sc,'Unknown')}**  |  "
                       f"Supplier state: **{STATES.get(supplier.get('state_code',''),'Unknown')}**")

    # ── Section 3: Line Items ─────────────────────────────────────────
    st.markdown("<div class='section-header'>📦 Invoice Line Items</div>", unsafe_allow_html=True)

    if "line_items_v2" not in st.session_state:
        st.session_state.line_items_v2 = [{}]

    col_add, _ = st.columns([1,5])
    with col_add:
        if st.button("➕ Add Item", use_container_width=True):
            st.session_state.line_items_v2.append({})
            st.rerun()

    hsn_code_opts = ["-- Select from Master --"] + [f"{k} — {v['description']}" for k, v in hsn_master.items()]
    hsn_desc_opts = ["-- Select Description --"] + [v["description"] for v in hsn_master.values()]
    desc_to_code  = {v["description"]: k for k, v in hsn_master.items()}
    code_to_meta  = dict(hsn_master)

    items_data = []
    for idx in range(len(st.session_state.line_items_v2)):
        with st.expander(f"Item {idx+1}", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                sel_code = st.selectbox("Select by HSN Code", hsn_code_opts, key=f"hsn_sel_{idx}")
            with c2:
                sel_desc = st.selectbox("Select by Description", hsn_desc_opts, key=f"desc_sel_{idx}")

            # Resolve prefill
            pf = {}
            if sel_code != "-- Select from Master --":
                pf = code_to_meta.get(sel_code.split(" — ")[0], {})
            elif sel_desc != "-- Select Description --":
                pf = code_to_meta.get(desc_to_code.get(sel_desc,""), {})

            c1, c2, c3 = st.columns(3)
            with c1:
                description = st.text_input("Description *",
                                             value=pf.get("description",""),
                                             key=f"desc_{idx}")
                hsn_code    = st.text_input("HSN / SAC Code *",
                                             value=pf.get("code",""),
                                             key=f"hsn_{idx}")
            with c2:
                is_service  = st.selectbox("Goods / Service",
                                            ["N — Goods","Y — Service"],
                                            index=1 if pf.get("is_service") else 0,
                                            key=f"svc_{idx}")
                uqc_default = pf.get("uqc","UNT")
                uqc_idx     = UQC_CODES.index(uqc_default) if uqc_default in UQC_CODES else 0
                uqc         = st.selectbox("UQC (Unit of Measure) *", UQC_CODES,
                                            index=uqc_idx, key=f"uqc_{idx}",
                                            help="UNT=Units  CNT=Count  NOS=Numbers  KGS=Kg  LTR=Litres…")
            with c3:
                qty        = st.number_input("Quantity *", min_value=0.0, value=1.0,
                                              step=1.0, format="%.3f", key=f"qty_{idx}")
                unit_price = st.number_input("Unit Price (₹) *", min_value=0.0, value=0.0,
                                              step=0.01, format="%.4f", key=f"price_{idx}",
                                              help="Supports decimal prices like 2.50")

            c1, c2, c3, c4 = st.columns(4)
            with c1: discount   = st.number_input("Discount (₹)",     min_value=0.0, value=0.0, step=0.01, key=f"disc_{idx}")
            with c2:
                gst_default = pf.get("gst_rate",18)
                gst_idx     = GST_RATES.index(gst_default) if gst_default in GST_RATES else 7
                gst_rate    = st.selectbox("GST Rate (%)", GST_RATES, index=gst_idx, key=f"gst_{idx}")
            with c3: cess_rate  = st.number_input("Cess Rate (%)",    min_value=0.0, value=0.0, step=0.01, key=f"cess_{idx}")
            with c4: other_chrg = st.number_input("Other Charges (₹)",min_value=0.0, value=0.0, step=0.01, key=f"ochrg_{idx}")

            if unit_price > 0:
                taxes = calculate_item_taxes(unit_price, qty, discount, gst_rate, cess_rate, tax_type)
                m1,m2,m3,m4,m5 = st.columns(5)
                m1.metric("Taxable", f"₹{taxes['ass_amt']:,.2f}")
                if tax_type=="IGST":
                    m2.metric("IGST", f"₹{taxes['igst_amt']:,.2f}"); m3.metric("CGST","₹0.00"); m4.metric("SGST","₹0.00")
                else:
                    m2.metric("IGST","₹0.00"); m3.metric("CGST",f"₹{taxes['cgst_amt']:,.2f}"); m4.metric("SGST",f"₹{taxes['sgst_amt']:,.2f}")
                m5.metric("Item Total", f"₹{taxes['tot_item_val']:,.2f}")
                items_data.append({"description":description,"hsn":hsn_code,"is_service":is_service[0],
                                    "qty":qty,"uqc":uqc,"unit_price":unit_price,"gst_rate":gst_rate,
                                    "cess_rate":cess_rate,"discount":discount,"other_charges":other_chrg,**taxes})
            else:
                st.caption("⬆️ Enter Unit Price to see live tax breakdown")

            _, rb = st.columns([5,1])
            with rb:
                if st.button("🗑️ Remove", key=f"del_{idx}") and len(st.session_state.line_items_v2)>1:
                    st.session_state.line_items_v2.pop(idx); st.rerun()

    # ── Section 4: Totals ─────────────────────────────────────────────
    totals = {}
    if items_data:
        st.markdown("<div class='section-header'>💰 Invoice Totals</div>", unsafe_allow_html=True)
        c1,c2,c3 = st.columns(3)
        with c1: other_charges = st.number_input("Other Charges — Invoice Level (₹)", min_value=0.0,value=0.0,step=0.01,key="inv_oc")
        with c2: inv_discount  = st.number_input("Discount — Invoice Level (₹)",      min_value=0.0,value=0.0,step=0.01,key="inv_disc")
        with c3: round_off     = st.number_input("Round Off (₹)", value=0.0,step=0.01,min_value=-10.0,max_value=10.0,key="inv_ro")
        totals = calculate_totals(items_data, other_charges, inv_discount, round_off)
        t1,t2,t3,t4,t5 = st.columns(5)
        t1.metric("Taxable Value",    f"₹{totals['ass_val']:,.2f}")
        t2.metric("IGST",             f"₹{totals['igst_val']:,.2f}")
        t3.metric("CGST",             f"₹{totals['cgst_val']:,.2f}")
        t4.metric("SGST",             f"₹{totals['sgst_val']:,.2f}")
        t5.metric("🧾 Total Invoice", f"₹{totals['tot_inv_val']:,.2f}")

        # ── Preview ───────────────────────────────────────────────────
        st.markdown("<div class='section-header'>👁️ Invoice Preview</div>", unsafe_allow_html=True)
        with st.expander("🔎 Click to preview before saving", expanded=False):
            _render_preview(
                supplier,
                {"gstin":b_gstin,"legal_name":b_legal,"trade_name":b_trade,
                 "addr1":b_addr1,"addr2":b_addr2,"location":b_loc,
                 "state_code":b_state_code,"pincode":b_pincode},
                {"doc_type":doc_type,"doc_no":doc_no,
                 "doc_date":doc_date.strftime("%d/%m/%Y"),"supply_type":supply_type},
                items_data, totals, tax_type
            )

    # ── Save / Download ───────────────────────────────────────────────
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Save Invoice & Generate JSON", type="primary", use_container_width=True):
            errs = []
            if not doc_no:     errs.append("Document Number required")
            if not b_gstin:    errs.append("Buyer GSTIN required")
            if not b_legal:    errs.append("Buyer Legal Name required")
            if not b_addr1:    errs.append("Buyer Address Line 1 required")
            if not b_pincode:  errs.append("Buyer Pincode required")
            if not items_data: errs.append("Add at least one line item with a unit price")
            if errs:
                for e in errs: st.error(e)
            else:
                form_data = {
                    "supplier": supplier,
                    "buyer": {"gstin":b_gstin.upper(),"legal_name":b_legal,"trade_name":b_trade,
                               "addr1":b_addr1,"addr2":b_addr2,"location":b_loc,
                               "state_code":b_state_code,"pincode":b_pincode,
                               "phone":b_phone,"email":b_email,"pos":b_pos},
                    "doc":  {"doc_type":doc_type,"doc_no":doc_no,
                              "doc_date":doc_date.strftime("%d/%m/%Y"),
                              "supply_type":supply_type,"reverse_charge":reverse_charge,
                              "igst_on_intra":igst_on_intra,
                              "ecom_gstin":ecom_gstin if ecom_gstin else None},
                    "items": items_data, "val": totals
                }
                inv_json = build_invoice_json(form_data)
                key = save_invoice(inv_json)
                st.success(f"✅ Saved! Key: `{key}` → Go to 📋 Pending Invoices to get IRN")
                st.session_state["last_inv_json"] = inv_json
                st.session_state["last_inv_key"]  = key
                st.session_state.line_items_v2    = [{}]
                st.session_state["_buyer_data"]   = {}
                st.session_state["_gstin_verified"] = {}

    with col2:
        if "last_inv_json" in st.session_state:
            st.download_button("⬇️ Download JSON",
                                data=json.dumps(st.session_state["last_inv_json"],indent=2),
                                file_name=f"einvoice_{doc_no or 'inv'}.json",
                                mime="application/json", use_container_width=True)

    if "last_inv_json" in st.session_state:
        with st.expander("📄 View Generated JSON"):
            st.json(st.session_state["last_inv_json"])


def _render_preview(supplier, buyer, doc, items, totals, tax_type):
    rows_html = ""
    for i, item in enumerate(items, 1):
        tax = item.get("igst_amt",0)+item.get("cgst_amt",0)+item.get("sgst_amt",0)
        rows_html += f"""<tr>
        <td style='text-align:center'>{i}</td>
        <td>{item.get('description','')}</td>
        <td style='text-align:center'>{item.get('hsn','')}</td>
        <td style='text-align:right'>{float(item.get('qty',0)):,.3f} {item.get('uqc','')}</td>
        <td style='text-align:right'>₹{float(item.get('unit_price',0)):,.4f}</td>
        <td style='text-align:center'>{item.get('gst_rate',0)}%</td>
        <td style='text-align:right'>₹{float(item.get('ass_amt',0)):,.2f}</td>
        <td style='text-align:right'>₹{float(tax):,.2f}</td>
        <td style='text-align:right'><b>₹{float(item.get('tot_item_val',0)):,.2f}</b></td></tr>"""
    tax_label = "IGST" if tax_type=="IGST" else "CGST / SGST"
    tax_val   = (f"₹{totals.get('igst_val',0):,.2f}" if tax_type=="IGST"
                 else f"₹{totals.get('cgst_val',0):,.2f} / ₹{totals.get('sgst_val',0):,.2f}")
    html = f"""<style>
    .prev table{{border-collapse:collapse;width:100%;font-size:.81rem;margin-bottom:8px}}
    .prev th,.prev td{{border:1px solid #cbd5e1;padding:5px 8px}}
    .prev th{{background:#1a3c5e;color:white}}
    .prev .badge{{background:#f0f4f8;padding:5px 10px;border-radius:5px;font-weight:600;
    font-size:.84rem;margin-bottom:8px;display:inline-block}}
    </style>
    <div class='prev'>
    <div class='badge'>📄 {doc['doc_type']} &nbsp;|&nbsp; {doc['doc_no']} &nbsp;|&nbsp;
     {doc['doc_date']} &nbsp;|&nbsp; {doc['supply_type']}</div>
    <table><tr><th width='50%'>SUPPLIER</th><th width='50%'>BUYER</th></tr><tr>
      <td><b>{supplier.get('legal_name','')}</b><br>GSTIN: <code>{supplier.get('gstin','')}</code><br>
          {supplier.get('addr1','')}, {supplier.get('location','')} — {STATES.get(supplier.get('state_code',''),'')}</td>
      <td><b>{buyer.get('legal_name','')}</b><br>GSTIN: <code>{buyer.get('gstin','')}</code><br>
          {buyer.get('addr1','')}, {buyer.get('location','')} — {STATES.get(buyer.get('state_code',''),'')}</td>
    </tr></table>
    <table><tr><th>#</th><th>Description</th><th>HSN</th><th>Qty</th><th>Unit Price</th>
    <th>GST%</th><th>Taxable</th><th>Tax</th><th>Total</th></tr>{rows_html}</table>
    <table><tr><th>Taxable</th><th>{tax_label}</th><th>Cess</th><th>Other</th>
    <th>Round Off</th><th style='background:#1a3c5e;color:white'>TOTAL</th></tr>
    <tr><td>₹{totals.get('ass_val',0):,.2f}</td><td>{tax_val}</td>
    <td>₹{totals.get('cess_val',0):,.2f}</td><td>₹{totals.get('other_charges',0):,.2f}</td>
    <td>₹{totals.get('round_off',0):,.2f}</td>
    <td style='background:#1a3c5e;color:white'><b>₹{totals.get('tot_inv_val',0):,.2f}</b></td>
    </tr></table></div>"""
    st.markdown(html, unsafe_allow_html=True)
