import io
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.audit_log import AuditLog
from app.services.document_intelligence_service import (
    classify_document, extract_invoice, extract_contract, extract_identity, extract_resume,
    extract_tables_from_text, extract_from_bytes, capabilities,
)
from app.core.redis import redis_client


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    store = {}
    async def g(k): return store.get(k)
    async def s(k, v, ex=300): store[k] = v; return True
    async def d(k): store.pop(k, None); return True
    monkeypatch.setattr(redis_client, "get", g)
    monkeypatch.setattr(redis_client, "set", s)
    monkeypatch.setattr(redis_client, "delete", d)
    from app.dependencies import feature_guard
    async def feats(*a, **k): return ["LEAD_MANAGEMENT", "ROLE_BASED_ACCESS"]
    monkeypatch.setattr(feature_guard, "get_active_features", feats)
    return store


@pytest.fixture
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "DI Org", "slug": "di-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@di.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@di.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


INVOICE_TEXT = """Acme Software Pvt Ltd
TAX INVOICE
Invoice No: INV-2026-0042
Invoice Date: 05/07/2026
Due Date: 20/07/2026
Bill To: Globex Industries
GSTIN: 29ABCDE1234F1Z5

Item                Qty     Rate      Amount
CRM Licence         10      ₹1,000    ₹10,000
Support Plan        1       ₹2,000    ₹2,000

Subtotal: ₹12,000
GST @ 18%: ₹2,160
Total Due: ₹14,160
"""

CONTRACT_TEXT = """SERVICE AGREEMENT

This Agreement is entered into between Acme Software Pvt Ltd and Globex Industries.
WHEREAS the parties wish to define the terms of service delivery.
Effective Date: 1 August 2026
The Agreement shall remain in force for a term of 12 months and shall auto-renew
unless either party gives 30 days written notice of termination.
Payment Terms: Net 30
Governing Law: the laws of India
All information shared shall remain confidential.
IN WITNESS WHEREOF the parties execute this Agreement.
"""

RESUME_TEXT = """Priya Sharma
Email: priya.sharma@example.com | Phone: +91 98765 43210
Career Objective: Sales professional with 7 years of experience in CRM and negotiation.

Work Experience
Senior Sales Manager, Initech (2021-2026)

Education
MBA in Marketing, IIM Bangalore
B.Com, Delhi University

Skills: CRM, negotiation, communication, excel, leadership
"""

IDENTITY_TEXT = """GOVERNMENT OF INDIA
Permanent Account Number Card
Name: RAHUL VERMA
Date of Birth: 12/03/1990
ABCDE1234F
"""


# ---------- pure pipeline units ----------
def test_classification_covers_types():
    assert classify_document(INVOICE_TEXT)[0] == "invoice"
    assert classify_document(CONTRACT_TEXT)[0] == "contract"
    assert classify_document(RESUME_TEXT)[0] == "resume"
    assert classify_document(IDENTITY_TEXT)[0] == "identity"
    kind, conf, _ = classify_document("hello world nothing here")
    assert kind == "other" and conf == 0.0


def test_invoice_extraction():
    inv = extract_invoice(INVOICE_TEXT)
    assert inv["invoice_number"] == "INV-2026-0042"
    assert inv["gstin"] == "29ABCDE1234F1Z5"
    assert inv["total"] == 14160.0
    assert inv["tax"] == 2160.0
    assert inv["currency"] == "INR"
    assert inv["bill_to"].startswith("Globex")


def test_contract_extraction():
    c = extract_contract(CONTRACT_TEXT)
    assert c["parties"] and "Acme" in c["parties"][0] and "Globex" in c["parties"][1]
    assert c["term"] == "12 months"
    assert c["termination_notice_days"] == 30
    assert c["auto_renewal"] is True and c["confidentiality"] is True
    assert "India" in (c["governing_law"] or "")


def test_identity_extraction_masks_numbers():
    ident = extract_identity(IDENTITY_TEXT)
    assert ident["document_kind"] == "pan"
    assert ident["id_numbers"] and ident["id_numbers"][0]["type"] == "pan"
    masked = ident["id_numbers"][0]["number_masked"]
    assert masked.endswith("234F") and masked.startswith("*") and "ABCDE" not in masked
    assert ident["date_of_birth"].startswith("12/03/1990")


def test_resume_extraction():
    r = extract_resume(RESUME_TEXT)
    assert r["name"] == "Priya Sharma"
    assert r["email"] == "priya.sharma@example.com"
    assert r["experience_years"] == 7
    assert "crm" in r["skills"] and "negotiation" in r["skills"]
    assert any("MBA" in e for e in r["education"])


def test_table_extraction_from_text():
    tables = extract_tables_from_text(INVOICE_TEXT)
    assert tables, "columns separated by 3+ spaces should be detected"
    t = tables[0]
    assert t["headers"][0] == "Item" and "Qty" in t["headers"]
    assert any("CRM Licence" in r[0] for r in t["rows"])
    md = "| Name | Amount |\n|---|---|\n| Alpha | 10 |\n| Beta | 20 |"
    mdt = extract_tables_from_text(md)
    assert mdt and mdt[0]["headers"] == ["Name", "Amount"] and mdt[0]["rows"][0] == ["Alpha", "10"]


def test_capabilities_report():
    caps = capabilities()
    assert caps["pdf"] is True and caps["xlsx"] is True and caps["docx"] is True
    assert isinstance(caps["ocr"], bool)


def test_pdf_and_xlsx_parsers():
    # blank-page PDF -> parsed, but flagged as needing OCR (no text layer)
    from pypdf import PdfWriter
    buf = io.BytesIO()
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    w.write(buf)
    parsed = extract_from_bytes("scan.pdf", buf.getvalue())
    assert parsed["page_count"] == 1 and parsed.get("needs_ocr") is True

    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Pipeline"
    ws.append(["Stage", "Count"])
    ws.append(["New", 12])
    ws.append(["Won", 4])
    xbuf = io.BytesIO()
    wb.save(xbuf)
    parsed = extract_from_bytes("pipeline.xlsx", xbuf.getvalue())
    assert parsed["tables"] and parsed["tables"][0]["headers"] == ["Stage", "Count"]
    assert "Won | 4" in parsed["text"]


# ---------- API flow ----------
@pytest.mark.asyncio
async def test_upload_classify_extract_flow(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/document-intelligence/upload", headers=setup["h_emp"],
                          files={"file": ("invoice.txt", INVOICE_TEXT.encode(), "text/plain")})
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["doc_type"] == "invoice" and doc["status"] == "processed"
    assert doc["extraction"]["invoice"]["invoice_number"] == "INV-2026-0042"
    assert doc["tables"], "invoice line items should be extracted as a table"
    audits = (await db.execute(select(AuditLog).filter(
        AuditLog.organization_id == setup["org"].id,
        AuditLog.action == "DOCUMENT_PROCESSED"))).scalars().all()
    assert len(audits) == 1


@pytest.mark.asyncio
async def test_process_text_and_summarize(client: AsyncClient, setup):
    r = await client.post("/api/v1/document-intelligence/process-text", headers=setup["h_admin"],
                          json={"text": CONTRACT_TEXT, "filename": "msa.txt"})
    assert r.status_code == 201
    doc = r.json()
    assert doc["doc_type"] == "contract" and doc["extraction"]["contract"]["term"] == "12 months"
    r = await client.post(f"/api/v1/document-intelligence/documents/{doc['id']}/summarize",
                          headers=setup["h_admin"], json={"length": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["summary"] and body["provider"] == "mock"
    got = (await client.get(f"/api/v1/document-intelligence/documents/{doc['id']}",
                            headers=setup["h_admin"])).json()
    assert got["summary"] == body["summary"]


@pytest.mark.asyncio
async def test_visibility_and_permissions(client: AsyncClient, setup):
    r = await client.post("/api/v1/document-intelligence/process-text", headers=setup["h_admin"],
                          json={"text": RESUME_TEXT, "filename": "priya-cv.txt"})
    doc_id = r.json()["id"]
    # employee cannot see the admin's document
    assert (await client.get(f"/api/v1/document-intelligence/documents/{doc_id}",
                             headers=setup["h_emp"])).status_code == 403
    listed = (await client.get("/api/v1/document-intelligence/documents",
                               headers=setup["h_emp"])).json()
    assert listed["total"] == 0
    # manager sees all; employee export blocked
    listed = (await client.get("/api/v1/document-intelligence/documents",
                               headers=setup["h_admin"])).json()
    assert listed["total"] == 1
    assert (await client.get("/api/v1/document-intelligence/export",
                             headers=setup["h_emp"])).status_code == 403
    r = await client.get("/api/v1/document-intelligence/export", headers=setup["h_admin"])
    assert r.status_code == 200 and "priya-cv.txt" in r.text


@pytest.mark.asyncio
async def test_document_search(client: AsyncClient, setup):
    for name, text in (("invoice.txt", INVOICE_TEXT), ("contract.txt", CONTRACT_TEXT),
                       ("cv.txt", RESUME_TEXT)):
        await client.post("/api/v1/document-intelligence/process-text", headers=setup["h_admin"],
                          json={"text": text, "filename": name})
    r = await client.post("/api/v1/document-intelligence/search", headers=setup["h_admin"],
                          json={"query": "GST invoice total due"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1 and body["results"][0]["filename"] == "invoice.txt"
    r = await client.post("/api/v1/document-intelligence/search", headers=setup["h_admin"],
                          json={"query": "termination notice governing law"})
    assert r.json()["results"][0]["filename"] == "contract.txt"
    # unrelated query yields nothing
    r = await client.post("/api/v1/document-intelligence/search", headers=setup["h_admin"],
                          json={"query": "zzqx interstellar warp drive"})
    assert r.json()["count"] == 0


@pytest.mark.asyncio
async def test_dashboard_and_delete_audit(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/document-intelligence/process-text", headers=setup["h_admin"],
                          json={"text": INVOICE_TEXT, "filename": "inv.txt"})
    doc_id = r.json()["id"]
    dash = (await client.get("/api/v1/document-intelligence/dashboard",
                             headers=setup["h_admin"])).json()
    assert dash["totals"]["documents"] == 1
    assert dash["totals"]["by_type"]["invoice"] == 1
    assert dash["totals"]["with_structured_extraction"] == 1
    assert dash["capabilities"]["pdf"] is True
    r = await client.delete(f"/api/v1/document-intelligence/documents/{doc_id}",
                            headers=setup["h_admin"])
    assert r.json()["deleted"] is True
    audits = (await db.execute(select(AuditLog).filter(
        AuditLog.organization_id == setup["org"].id,
        AuditLog.action == "DOCUMENT_DELETED"))).scalars().all()
    assert len(audits) == 1
    dash = (await client.get("/api/v1/document-intelligence/dashboard",
                             headers=setup["h_admin"])).json()
    assert dash["totals"]["documents"] == 0


@pytest.mark.asyncio
async def test_image_understanding(client: AsyncClient, setup):
    from PIL import Image
    img = Image.new("RGB", (320, 200), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    r = await client.post("/api/v1/document-intelligence/upload", headers=setup["h_admin"],
                          files={"file": ("photo.png", buf.getvalue(), "image/png")})
    assert r.status_code == 201, r.text
    doc = r.json()
    info = doc["image_info"]
    assert info["width"] == 320 and info["height"] == 200 and info["orientation"] == "landscape"
    caps = (await client.get("/api/v1/document-intelligence/capabilities",
                             headers=setup["h_admin"])).json()
    if caps["ocr"]:
        assert doc["ocr_used"] is True and doc["status"] == "processed"
    else:
        assert doc["status"] == "needs_ocr"


@pytest.mark.asyncio
async def test_scanned_pdf_flags_needs_ocr(client: AsyncClient, setup):
    from pypdf import PdfWriter
    buf = io.BytesIO()
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    w.write(buf)
    r = await client.post("/api/v1/document-intelligence/upload", headers=setup["h_admin"],
                          files={"file": ("scan.pdf", buf.getvalue(), "application/pdf")})
    assert r.status_code == 201
    doc = r.json()
    assert doc["status"] == "needs_ocr" and doc["page_count"] == 1
