import logging
from html import escape

logger = logging.getLogger(__name__)

WEASYPRINT_AVAILABLE = False
try:
    import weasyprint
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError) as e:  # pragma: no cover
    logger.warning("WeasyPrint not available for customer invoices. Using fallback. Error: %s", str(e))

DUMMY_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    b"xref\n0 4\n0000000000 65535 f \n"
    b"trailer\n<< /Root 1 0 R /Size 4 >>\nstartxref\n0\n%%EOF"
)


def _rows(items: list) -> str:
    out = []
    for it in (items or []):
        out.append(
            f"<tr><td>{escape(str(it.get('description', '')))}</td>"
            f"<td style='text-align:right'>{it.get('quantity', 0)}</td>"
            f"<td style='text-align:right'>{it.get('unit_price', 0)}</td>"
            f"<td style='text-align:right'>{it.get('amount', 0)}</td></tr>"
        )
    return "".join(out)


def _html(invoice, company) -> str:
    cur = invoice.currency
    return f"""
    <html><head><style>
      body {{ font-family: Arial, sans-serif; color: #1e293b; font-size: 12px; }}
      h1 {{ font-size: 22px; margin-bottom: 0; }}
      .muted {{ color: #64748b; }}
      table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
      th, td {{ border-bottom: 1px solid #e2e8f0; padding: 6px 8px; text-align: left; }}
      th {{ background: #f1f5f9; }}
      .totals td {{ border: none; }}
    </style></head><body>
      <h1>Invoice {escape(invoice.invoice_number)}</h1>
      <p class="muted">Status: {escape(invoice.status)} &nbsp;|&nbsp; Issued: {invoice.issue_date.date() if invoice.issue_date else '-'} &nbsp;|&nbsp; Due: {invoice.due_date.date() if invoice.due_date else '-'}</p>
      <p><strong>Bill to:</strong> {escape(company.name)}</p>
      <table>
        <thead><tr><th>Description</th><th style="text-align:right">Qty</th><th style="text-align:right">Unit</th><th style="text-align:right">Amount</th></tr></thead>
        <tbody>{_rows(invoice.items)}</tbody>
      </table>
      <table class="totals" style="margin-top:12px; width: 260px; float:right;">
        <tr><td>Subtotal</td><td style="text-align:right">{cur} {float(invoice.subtotal):.2f}</td></tr>
        <tr><td>Tax</td><td style="text-align:right">{cur} {float(invoice.tax_amount):.2f}</td></tr>
        <tr><td>Discount</td><td style="text-align:right">-{cur} {float(invoice.discount_amount):.2f}</td></tr>
        <tr><td><strong>Total</strong></td><td style="text-align:right"><strong>{cur} {float(invoice.total_amount):.2f}</strong></td></tr>
        <tr><td>Paid</td><td style="text-align:right">{cur} {float(invoice.amount_paid):.2f}</td></tr>
        <tr><td><strong>Balance Due</strong></td><td style="text-align:right"><strong>{cur} {invoice.balance_due:.2f}</strong></td></tr>
      </table>
    </body></html>
    """


def build_invoice_pdf(invoice, company) -> bytes:
    if not WEASYPRINT_AVAILABLE:
        return DUMMY_PDF_BYTES
    try:
        return weasyprint.HTML(string=_html(invoice, company)).write_pdf()
    except Exception as e:  # pragma: no cover
        logger.error("Customer invoice PDF render failed: %s", str(e))
        return DUMMY_PDF_BYTES
