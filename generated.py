import streamlit as st
import json
import pandas as pd
from utils.db import get_generated_invoices
from utils.pdf_gen import generate_einvoice_pdf

def show():
    st.markdown("<div class='section-header'>✅ Generated Invoices (IRN Obtained)</div>", unsafe_allow_html=True)
    generated = get_generated_invoices()
    if not generated:
        st.info("No IRN-generated invoices yet. Submit pending invoices to get IRN.")
        return

    # Summary table
    rows = []
    for k, v in generated.items():
        doc   = v.get("DocDtls",{});  val   = v.get("ValDtls",{})
        buy   = v.get("BuyerDtls",{}); irn_d = v.get("_irn_data",{})
        rows.append({"Type": doc.get("Typ",""), "Doc No": doc.get("No",""), "Date": doc.get("Dt",""),
                     "Buyer": buy.get("LglNm","")[:35], "Total": f"₹{val.get('TotInvVal',0):,.2f}",
                     "IRN": (irn_d.get("irn","")[:20]+"...") if irn_d.get("irn") else "",
                     "Ack No": irn_d.get("ack_no",""), "Mode": "⚠️ Test" if irn_d.get("simulated") else "✅ Live"})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.divider()

    for inv_key, invoice in generated.items():
        doc   = invoice.get("DocDtls",{});  val   = invoice.get("ValDtls",{})
        buy   = invoice.get("BuyerDtls",{}); irn_d = invoice.get("_irn_data",{})
        tag   = "⚠️ TEST" if irn_d.get("simulated") else "✅"
        label = f"{tag}  {doc.get('Typ','')} | {doc.get('No','')} | {buy.get('LglNm','')} | ₹{val.get('TotInvVal',0):,.2f}"

        with st.expander(label):
            if irn_d.get("simulated"):
                st.warning("⚠️ Simulated IRN — NOT valid for GST compliance.")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**IRN Details**")
                st.code(irn_d.get("irn",""), language=None)
                st.write(f"Ack No: **{irn_d.get('ack_no','')}**")
                st.write(f"Ack Date: **{irn_d.get('ack_dt','')}**")
            with c2:
                st.markdown("**Value Summary**")
                st.write(f"Taxable: ₹{val.get('AssVal',0):,.2f}")
                st.write(f"IGST: ₹{val.get('IgstVal',0):,.2f}  |  CGST: ₹{val.get('CgstVal',0):,.2f}  |  SGST: ₹{val.get('SgstVal',0):,.2f}")
                st.write(f"**Total Invoice Value: ₹{val.get('TotInvVal',0):,.2f}**")

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("🖨️ Generate & Download PDF", key=f"pdf_{inv_key}", type="primary", use_container_width=True):
                    with st.spinner("Generating PDF..."):
                        try:
                            pdf_buf = generate_einvoice_pdf(invoice, irn_d)
                            fname   = f"einvoice_{doc.get('No','inv').replace('/','_')}.pdf"
                            st.download_button("⬇️ Download e-Invoice PDF", data=pdf_buf.getvalue(),
                                                file_name=fname, mime="application/pdf",
                                                key=f"dl_pdf_{inv_key}", use_container_width=True)
                        except Exception as e:
                            st.error(f"PDF error: {e}")
            with col2:
                clean = {k: v for k, v in invoice.items() if not k.startswith("_")}
                st.download_button("⬇️ Download JSON", data=json.dumps(clean,indent=2),
                                    file_name=f"einv_{doc.get('No','')}.json",
                                    mime="application/json", key=f"dl_j_{inv_key}", use_container_width=True)
            with col3:
                st.download_button("⬇️ IRN Data", data=json.dumps(irn_d,indent=2),
                                    file_name=f"irn_{doc.get('No','')}.json",
                                    mime="application/json", key=f"dl_i_{inv_key}", use_container_width=True)
