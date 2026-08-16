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

_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
         "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
         "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")).strip()


def _three(n: int) -> str:
    h, rest = divmod(n, 100)
    out = ""
    if h:
        out += _ONES[h] + " Hundred"
        if rest:
            out += " "
    if rest:
        out += _two(rest)
    return out


def amount_in_words_inr(amount: float) -> str:
    """Indian-numbering amount in words, e.g. 105000 -> 'One Lakh Five Thousand Rupees Only'."""
    try:
        amount = float(amount or 0)
    except (TypeError, ValueError):
        amount = 0.0
    rupees = int(round(amount))
    if rupees == 0:
        return "Zero Rupees Only"
    parts = []
    crore, rem = divmod(rupees, 10000000)
    lakh, rem = divmod(rem, 100000)
    thousand, rem = divmod(rem, 1000)
    hundred = rem
    if crore:
        parts.append(_two(crore) + " Crore" if crore < 100 else _three(crore) + " Crore")
    if lakh:
        parts.append(_two(lakh) + " Lakh")
    if thousand:
        parts.append(_two(thousand) + " Thousand")
    if hundred:
        parts.append(_three(hundred))
    return " ".join(p for p in parts if p).strip() + " Rupees Only"


def _clinic_name(company, s) -> str:
    return (getattr(s, "legal_name", None) or getattr(company, "name", None) or "Clinic")


def _rows(items: list, sym: str) -> str:
    out = []
    for i, it in enumerate(items or [], start=1):
        qty = it.get("quantity", 0) or 0
        price = float(it.get("unit_price", 0) or 0)
        gross = float(it.get("amount", price * float(qty or 0)) or 0)
        line_disc = float(it.get("discount", 0) or 0)
        total = gross - line_disc
        out.append(
            f"<tr>"
            f"<td style='text-align:center'>{i}</td>"
            f"<td>{escape(str(it.get('description', '')))}</td>"
            f"<td style='text-align:right'>{qty}</td>"
            f"<td style='text-align:right'>{sym}{price:,.0f}</td>"
            f"<td style='text-align:right'>{sym}{line_disc:,.0f}</td>"
            f"<td style='text-align:right'>{sym}{total:,.0f}</td>"
            f"</tr>"
        )
    return "".join(out) or "<tr><td colspan='6' style='color:#94a3b8;text-align:center'>No line items</td></tr>"


def _meta_cell(label: str, value: str) -> str:
    return (f"<td style='padding:6px 10px;vertical-align:top'>"
            f"<div style='color:#64748b;font-size:10px'>{escape(label)}</div>"
            f"<div style='font-weight:bold'>{escape(value or '-')}</div></td>")


def _html(invoice, company, s=None, patient=None, consultant=None) -> str:
    sym = (getattr(s, "currency_symbol", None) or (invoice.currency + " "))
    name = _clinic_name(company, s)
    addr = escape(getattr(s, "address", "") or "").replace(chr(10), "<br/>")
    phone = escape(getattr(s, "phone", "") or "")
    logo = (f"<img src='{escape(s.logo_url)}' style='max-height:54px;margin-bottom:6px'/>"
            if getattr(s, "logo_url", None) else "")

    p = patient or {}
    pname = p.get("name") or getattr(company, "name", "") or "-"
    age = p.get("age")
    gender = p.get("gender")
    age_gender = " / ".join(str(x) for x in [age, gender] if x) or "-"
    mobile = p.get("phone") or "-"

    from datetime import datetime, timezone
    printed = datetime.now(timezone.utc).strftime("%d %b %Y, %I:%M %p")
    bill_date = invoice.issue_date.strftime("%d %b %Y") if invoice.issue_date else "-"

    total = float(invoice.total_amount or 0)
    paid = float(invoice.amount_paid or 0)
    balance = float(invoice.balance_due)
    discount = float(invoice.discount_amount or 0)
    tax = float(invoice.tax_amount or 0)
    tax_label = getattr(s, "tax_label", None) or "Tax"
    remarks = escape(invoice.notes) if invoice.notes else "No remarks"
    footer = (f"<div class='muted' style='margin-top:22px;text-align:center;border-top:1px solid #e2e8f0;padding-top:8px'>{escape(s.footer_text)}</div>"
              if (s and getattr(s, "footer_text", None)) else "")

    tax_row = (f"<tr><td>{escape(tax_label)}</td><td style='text-align:right'>{sym}{tax:,.0f}</td></tr>"
               if tax > 0 else "")

    return f"""
    <html><head><style>
      @page {{ margin: 28px 34px; }}
      body {{ font-family: Arial, sans-serif; color: #1e293b; font-size: 12px; }}
      .muted {{ color: #64748b; }}
      .clinic {{ text-align:center; }}
      .clinic .nm {{ font-size: 20px; font-weight: bold; color:#0f172a; }}
      .rule {{ border-top: 1px solid #cbd5e1; margin: 10px 0; }}
      table.meta {{ width:100%; border-collapse:collapse; }}
      table.items {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
      table.items th, table.items td {{ border-bottom: 1px solid #e2e8f0; padding: 7px 8px; }}
      table.items th {{ background: #f1f5f9; text-transform:uppercase; font-size:10px; letter-spacing:.04em; text-align:left; }}
      table.items th.r, table.items td.r {{ text-align:right; }}
      .totals td {{ border: none; padding: 3px 8px; }}
      .sign {{ margin-top: 42px; text-align:right; }}
      .sign .line {{ display:inline-block; border-top:1px solid #334155; width:180px; padding-top:4px; }}
    </style></head><body>

      <div class="clinic">
        {logo}
        <div class="nm">{escape(name)}</div>
        {f'<div class="muted">{addr}</div>' if addr else ''}
        {f'<div class="muted">Phone: {phone}</div>' if phone else ''}
      </div>

      <div class="rule"></div>
      <table class="meta">
        <tr>
          {_meta_cell("Consultant", consultant or "-")}
          {_meta_cell("Bill Date", bill_date)}
          {_meta_cell("Bill ID", invoice.invoice_number)}
          {_meta_cell("Printed At", printed)}
        </tr>
      </table>
      <div class="rule"></div>
      <table class="meta">
        <tr>
          {_meta_cell("Name", pname)}
          {_meta_cell("Age / Gender", age_gender)}
          {_meta_cell("Mobile", mobile)}
        </tr>
      </table>

      <table class="items">
        <thead><tr>
          <th style="text-align:center">SL.NO</th><th>Particulars</th>
          <th class="r">Qty</th><th class="r">Price</th><th class="r">Discount</th><th class="r">Total</th>
        </tr></thead>
        <tbody>{_rows(invoice.items, sym)}</tbody>
      </table>

      <table class="totals" style="margin-top:12px; width: 300px; float:right;">
        {tax_row}
        <tr><td>Discount</td><td style="text-align:right">{sym}{discount:,.0f}</td></tr>
        <tr><td style="border-top:1px solid #cbd5e1"><strong>Grand Total</strong></td><td style="text-align:right;border-top:1px solid #cbd5e1"><strong>{sym}{total:,.0f}</strong></td></tr>
        <tr><td>Paid Amount</td><td style="text-align:right">{sym}{paid:,.0f}</td></tr>
        <tr><td><strong>Balance Due</strong></td><td style="text-align:right"><strong>{sym}{balance:,.0f}</strong></td></tr>
      </table>
      <div style="clear:both"></div>

      <div class="sign"><span class="line">Signature</span></div>

      <div style="margin-top:18px"><strong>Amount in Words:</strong> {escape(amount_in_words_inr(total))}</div>
      <div style="margin-top:6px"><strong>Remarks:</strong> {remarks}</div>
      {footer}
    </body></html>
    """


def build_invoice_pdf(invoice, company, settings=None, patient=None, consultant=None) -> bytes:
    if not WEASYPRINT_AVAILABLE:
        return DUMMY_PDF_BYTES
    try:
        return weasyprint.HTML(string=_html(invoice, company, settings, patient, consultant)).write_pdf()
    except Exception as e:  # pragma: no cover
        logger.error("Customer invoice PDF render failed: %s", str(e))
        return DUMMY_PDF_BYTES
