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


def _rows(items: list, sym: str) -> str:
    out = []
    for it in (items or []):
        out.append(
            f"<tr><td>{escape(str(it.get('description', '')))}</td>"
            f"<td style='text-align:right'>{it.get('quantity', 0)}</td>"
            f"<td style='text-align:right'>{sym}{float(it.get('unit_price', 0) or 0):.2f}</td>"
            f"<td style='text-align:right'>{sym}{float(it.get('amount', 0) or 0):.2f}</td></tr>"
        )
    return "".join(out) or "<tr><td colspan='4' style='color:#94a3b8'>No line items</td></tr>"


def _issuer_block(s) -> str:
    """The clinic / seller identity from tenant settings."""
    if not s:
        return ""
    lines = []
    logo = f"<img src='{escape(s.logo_url)}' style='max-height:56px;margin-bottom:8px'/>" if getattr(s, "logo_url", None) else ""
    if s.legal_name:
        lines.append(f"<div style='font-size:18px;font-weight:bold;color:#0f172a'>{escape(s.legal_name)}</div>")
    if s.address:
        lines.append(f"<div class='muted'>{escape(s.address).replace(chr(10), '<br/>')}</div>")
    contact = " · ".join(x for x in [s.phone, s.email, s.website] if x)
    if contact:
        lines.append(f"<div class='muted'>{escape(contact)}</div>")
    stat = " · ".join(x for x in [f"GSTIN: {s.gst_number}" if s.gst_number else "",
                                  f"PAN: {s.pan}" if s.pan else ""] if x)
    if stat:
        lines.append(f"<div class='muted' style='margin-top:4px'>{escape(stat)}</div>")
    return logo + "".join(lines)


def _pay_block(s) -> str:
    if not s:
        return ""
    parts = []
    bank = [x for x in [
        f"Bank: {s.bank_name}" if s.bank_name else "",
        f"A/C: {s.account_holder} — {s.account_number}" if s.account_number else "",
        f"IFSC: {s.ifsc}" if s.ifsc else "",
        f"UPI: {s.upi_id}" if s.upi_id else "",
    ] if x]
    if bank:
        parts.append("<div style='margin-top:16px'><strong>Payment details</strong><br/>" +
                     "<br/>".join(escape(b) for b in bank) + "</div>")
    if s.payment_terms:
        parts.append(f"<div class='muted' style='margin-top:10px'>{escape(s.payment_terms)}</div>")
    return "".join(parts)


def _html(invoice, company, s=None) -> str:
    sym = (getattr(s, "currency_symbol", None) or invoice.currency + " ")
    tax_label = getattr(s, "tax_label", None) or "Tax"
    footer = f"<div class='muted' style='margin-top:28px;text-align:center;border-top:1px solid #e2e8f0;padding-top:8px'>{escape(s.footer_text)}</div>" if (s and s.footer_text) else ""
    return f"""
    <html><head><style>
      body {{ font-family: Arial, sans-serif; color: #1e293b; font-size: 12px; }}
      .muted {{ color: #64748b; }}
      .head {{ display:flex; justify-content:space-between; align-items:flex-start; }}
      .inv-title {{ font-size: 26px; font-weight:bold; color:#0f172a; margin:0; }}
      table.items {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
      table.items th, table.items td {{ border-bottom: 1px solid #e2e8f0; padding: 7px 8px; text-align: left; }}
      table.items th {{ background: #f1f5f9; text-transform:uppercase; font-size:10px; letter-spacing:.05em; }}
      .totals td {{ border: none; padding: 3px 8px; }}
    </style></head><body>
      <div class="head">
        <div>{_issuer_block(s)}</div>
        <div style="text-align:right">
          <p class="inv-title">INVOICE</p>
          <div class="muted">{escape(invoice.invoice_number)}</div>
          <div class="muted" style="margin-top:6px">Status: {escape(invoice.status)}</div>
          <div class="muted">Issued: {invoice.issue_date.date() if invoice.issue_date else '-'}</div>
          <div class="muted">Due: {invoice.due_date.date() if invoice.due_date else '-'}</div>
        </div>
      </div>

      <div style="margin-top:18px"><span class="muted">Bill to</span><br/>
        <strong>{escape(company.name)}</strong></div>

      <table class="items">
        <thead><tr><th>Description</th><th style="text-align:right">Qty</th><th style="text-align:right">Unit</th><th style="text-align:right">Amount</th></tr></thead>
        <tbody>{_rows(invoice.items, sym)}</tbody>
      </table>

      <table class="totals" style="margin-top:14px; width: 280px; float:right;">
        <tr><td>Subtotal</td><td style="text-align:right">{sym}{float(invoice.subtotal):.2f}</td></tr>
        <tr><td>{escape(tax_label)}</td><td style="text-align:right">{sym}{float(invoice.tax_amount):.2f}</td></tr>
        <tr><td>Discount</td><td style="text-align:right">-{sym}{float(invoice.discount_amount):.2f}</td></tr>
        <tr><td style="border-top:1px solid #e2e8f0"><strong>Total</strong></td><td style="text-align:right;border-top:1px solid #e2e8f0"><strong>{sym}{float(invoice.total_amount):.2f}</strong></td></tr>
        <tr><td>Paid</td><td style="text-align:right">{sym}{float(invoice.amount_paid):.2f}</td></tr>
        <tr><td><strong>Balance Due</strong></td><td style="text-align:right"><strong>{sym}{float(invoice.balance_due):.2f}</strong></td></tr>
      </table>
      <div style="clear:both"></div>
      {_pay_block(s)}
      {footer}
    </body></html>
    """


def build_invoice_pdf(invoice, company, settings=None) -> bytes:
    if not WEASYPRINT_AVAILABLE:
        return DUMMY_PDF_BYTES
    try:
        return weasyprint.HTML(string=_html(invoice, company, settings)).write_pdf()
    except Exception as e:  # pragma: no cover
        logger.error("Customer invoice PDF render failed: %s", str(e))
        return DUMMY_PDF_BYTES
