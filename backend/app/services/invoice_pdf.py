import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Try importing WeasyPrint. If system-level pango/cairo dependencies are missing, 
# it will fail with ImportError or OSError.
WEASYPRINT_AVAILABLE = False
try:
    import weasyprint
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError) as e:
    logger.warning("WeasyPrint not available. Using dummy PDF fallback. Error: %s", str(e))

# A minimal valid PDF-1.4 byte stream
DUMMY_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
    b"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>\nendobj\n"
    b"4 0 obj\n<< /Length 99 >>\n"
    b"stream\n"
    b"BT\n"
    b"/F1 24 Tf\n"
    b"70 700 Td\n"
    b"(INVOICE PDF GENERATION FALLBACK) Tj\n"
    b"0 -40 Td\n"
    b"/F1 14 Tf\n"
    b"(This is a mock PDF generated because WeasyPrint is not fully installed on this system.) Tj\n"
    b"ET\n"
    b"endstream\n"
    b"endobj\n"
    b"xref\n"
    b"0 5\n"
    b"0000000000 65535 f\n"
    b"0000000009 00000 n\n"
    b"0000000058 00000 n\n"
    b"0000000115 00000 n\n"
    b"0000000252 00000 n\n"
    b"trailer\n"
    b"<< /Size 5 /Root 1 0 R >>\n"
    b"startxref\n"
    b"402\n"
    b"%%EOF\n"
)

def generate_invoice_pdf(invoice) -> bytes:
    """
    Generates a PDF for the given Invoice model instance.
    If WeasyPrint is not available, returns a valid minimal dummy PDF.
    """
    if not WEASYPRINT_AVAILABLE:
        return DUMMY_PDF_BYTES

    # Build responsive clean HTML invoice template
    org_name = invoice.organization.name if invoice.organization else "N/A"
    plan_name = invoice.plan_name or "Standard Subscription"
    amount = invoice.amount_inr if invoice.amount_inr is not None else invoice.amount
    currency = invoice.currency or "INR"
    issue_date_str = invoice.issue_date.strftime("%B %d, %Y") if hasattr(invoice.issue_date, "strftime") else str(invoice.issue_date)
    due_date_str = invoice.due_date.strftime("%B %d, %Y") if hasattr(invoice.due_date, "strftime") else str(invoice.due_date)
    payment_status = (invoice.payment_status or invoice.status or "unpaid").upper()

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Invoice {invoice.invoice_number}</title>
        <style>
            @page {{
                size: A4;
                margin: 20mm;
            }}
            body {{
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                color: #333;
                line-height: 1.4;
                margin: 0;
            }}
            .header {{
                display: flex;
                justify-content: space-between;
                border-bottom: 2px solid #eaeaea;
                padding-bottom: 15px;
                margin-bottom: 30px;
            }}
            .logo {{
                font-size: 24px;
                font-weight: bold;
                color: #2563eb;
            }}
            .invoice-title {{
                font-size: 28px;
                font-weight: 300;
                text-align: right;
            }}
            .details {{
                margin-bottom: 30px;
            }}
            .details-cols {{
                display: table;
                width: 100%;
            }}
            .details-col {{
                display: table-cell;
                width: 50%;
            }}
            .details-label {{
                font-size: 12px;
                color: #777;
                text-transform: uppercase;
                margin-bottom: 5px;
            }}
            .details-value {{
                font-size: 14px;
                margin-bottom: 15px;
            }}
            .table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 40px;
            }}
            .table th {{
                background-color: #f8fafc;
                border-bottom: 2px solid #eaeaea;
                font-weight: bold;
                text-align: left;
                padding: 10px;
                font-size: 14px;
            }}
            .table td {{
                border-bottom: 1px solid #eaeaea;
                padding: 12px 10px;
                font-size: 14px;
            }}
            .total-box {{
                float: right;
                width: 300px;
                margin-top: 20px;
            }}
            .total-row {{
                display: flex;
                justify-content: space-between;
                padding: 5px 0;
            }}
            .total-grand {{
                font-size: 18px;
                font-weight: bold;
                border-top: 2px solid #eaeaea;
                padding-top: 10px;
                margin-top: 10px;
            }}
            .status-badge {{
                display: inline-block;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }}
            .status-PAID {{
                background-color: #dcfce7;
                color: #166534;
            }}
            .status-UNPAID {{
                background-color: #fee2e2;
                color: #991b1b;
            }}
            .status-OVERDUE {{
                background-color: #fef3c7;
                color: #92400e;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="logo">TeleCRM SaaS</div>
            <div class="invoice-title">
                INVOICE<br>
                <span style="font-size: 14px; color: #777;">#{invoice.invoice_number}</span>
            </div>
        </div>
        
        <div class="details">
            <div class="details-cols">
                <div class="details-col">
                    <div class="details-label">Billed To</div>
                    <div class="details-value">
                        <strong>{org_name}</strong><br>
                        Tenant Organization
                    </div>
                </div>
                <div class="details-col" style="text-align: right;">
                    <div class="details-label">Invoice Details</div>
                    <div class="details-value">
                        <strong>Issue Date:</strong> {issue_date_str}<br>
                        <strong>Due Date:</strong> {due_date_str}<br>
                        <strong>Status:</strong> <span class="status-badge status-{payment_status}">{payment_status}</span>
                    </div>
                </div>
            </div>
        </div>

        <table class="table">
            <thead>
                <tr>
                    <th>Description</th>
                    <th style="text-align: right;">Price</th>
                    <th style="text-align: right;">Total</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>
                        <strong>SaaS Subscription - {plan_name}</strong><br>
                        <span style="font-size: 12px; color: #777;">Access to CRM platform features and user limits as per plan specifications.</span>
                    </td>
                    <td style="text-align: right;">{currency} {amount:,.2f}</td>
                    <td style="text-align: right;">{currency} {amount:,.2f}</td>
                </tr>
            </tbody>
        </table>

        <div style="clear: both;"></div>

        <div class="total-box">
            <div class="total-row">
                <span>Subtotal:</span>
                <span>{currency} {amount:,.2f}</span>
            </div>
            <div class="total-row">
                <span>Tax (0%):</span>
                <span>{currency} 0.00</span>
            </div>
            <div class="total-row total-grand">
                <span>Grand Total:</span>
                <span>{currency} {amount:,.2f}</span>
            </div>
        </div>
    </body>
    </html>
    """
    
    try:
        pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
        return pdf_bytes
    except Exception as e:
        logger.error("Weasyprint failed to render PDF: %s. Falling back to dummy PDF.", str(e))
        return DUMMY_PDF_BYTES
