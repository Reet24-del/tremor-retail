"""Render supplier invoice PDFs and the cached validated extraction from invoices_truth.json.

Run after generate_demo_data.py.
"""
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from catalog import STORE_NAME, SUPPLIERS

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "demo"


def money(x):
    return f"{x:,.2f}"


def render(inv, path):
    s = SUPPLIERS[inv["supplier_key"]]
    st = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=A4, title=f"{s['name']} {inv['invoice_number']}",
                            leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    story = [Paragraph(f"<b>{s['name'].upper()}</b>", st["Title"]),
             Paragraph(f"{s['addr']} | GSTIN {s['gstin']}", st["Normal"]), Spacer(1, 8),
             Paragraph("<b>TAX INVOICE</b>", st["Heading3"]),
             Paragraph(f"Invoice No: {inv['invoice_number']}", st["Normal"]),
             Paragraph(f"Invoice Date: {inv['invoice_date']}", st["Normal"]),
             Paragraph(f"Bill To: {STORE_NAME}, Lucknow", st["Normal"]),
             Paragraph("Currency: INR (rates inclusive of GST)", st["Normal"]), Spacer(1, 10)]
    data = [["#", "Item Description", "Qty", "Unit", "Rate", "Amount"]]
    for i, l in enumerate(inv["line_items"], 1):
        data.append([str(i), l["raw_description"], str(l["quantity"]), l["unit"], money(l["unit_cost"]),
                     money(l["line_total"])])
    data.append(["", "TOTAL", "", "", "", money(inv["invoice_total"])])
    t = Table(data, colWidths=[22, 230, 40, 50, 70, 90])
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONT", (0, -1), (-1, -1), "Helvetica-Bold"),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                           ("ALIGN", (2, 1), (-1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    story += [t, Spacer(1, 16), Paragraph("Payment due within 15 days. Goods once sold will not be taken back.",
                                          st["Italic"])]
    doc.build(story)


def main():
    truth = json.loads((DEMO / "labels" / "invoices_truth.json").read_text())
    out = DEMO / "invoices"
    out.mkdir(exist_ok=True)
    cache = DEMO / "cached_extraction"
    cache.mkdir(exist_ok=True)
    for f in list(out.glob("*.pdf")) + list(cache.glob("*.json")):
        f.unlink()
    for inv in truth:
        fname = f"{inv['invoice_number']}.pdf"
        render(inv, out / fname)
        cached = {"source_file": fname, "supplier_name": inv["supplier_name"],
                  "invoice_number": inv["invoice_number"], "invoice_date": inv["invoice_date"], "currency": "INR",
                  "invoice_total": inv["invoice_total"], "extraction_method": "cached",
                  "line_items": [{"line_id": f"line_{i:02d}", "raw_description": l["raw_description"],
                                  "quantity": l["quantity"], "unit": l["unit"], "unit_cost": l["unit_cost"],
                                  "tax_amount": l["tax_amount"], "line_total": l["line_total"], "page_number": 1,
                                  "extraction_confidence": 0.99}
                                 for i, l in enumerate(inv["line_items"], 1)],
                  "extraction_warnings": []}
        (cache / f"{inv['invoice_number']}.json").write_text(json.dumps(cached, indent=2))
    print(f"rendered {len(truth)} invoices")


if __name__ == "__main__":
    main()
