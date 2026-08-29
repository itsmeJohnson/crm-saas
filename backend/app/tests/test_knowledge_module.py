import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.knowledge_base import KBArticle, KBChunk, KBEvent, KBArticleVersion
from app.models.audit_log import AuditLog
from app.services.knowledge_base_service import embed_text, cosine, chunk_text, EMBED_DIM
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
    async def feats(*a, **k): return ["LEAD_MANAGEMENT","CONTACT_MANAGEMENT","FOLLOW_UP_TASKS","SALES_PIPELINE","CLICK_TO_CALL","BASIC_DASHBOARD","DASHBOARD_REPORTS","BULK_IMPORT","GOOGLE_SHEETS_IMPORT","BULK_ASSIGNMENT","ROLE_BASED_ACCESS","CUSTOM_PIPELINE","LEAD_DISTRIBUTION","KPI_DASHBOARD","TARGET_MANAGEMENT","MANAGER_DASHBOARD","TEAM_LEADER_DASHBOARD","CALL_RECORDING","INBOUND_CALLING","OUTBOUND_CALLING","SMS_MESSAGING","EMAIL_MESSAGING","WHATSAPP_MESSAGING","CAMPAIGN_MANAGEMENT","VOICE_BROADCAST","LEAD_CAPTURE","ADVANCED_PIPELINE","LEAD_TRANSFERS","BULK_TRANSFER","SMART_DISTRIBUTION","TEAM_MONITORING","CALL_DISPOSITION","AI_CALL_SUMMARY","AI_FOLLOW_UP","ADVANCED_ANALYTICS","CONVERSION_ANALYTICS","CUSTOM_REPORTS","PRIORITY_SUPPORT","WHITE_LABEL","API_ACCESS"]
    monkeypatch.setattr(feature_guard, "get_active_features", feats)
    return store


@pytest.fixture
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "KB Org", "slug": "kb-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@kb.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@kb.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


REFUND_TEXT = ("Refund policy overview.\n\nCustomers can request a refund within 14 days of purchase. "
               "Refunds are processed to the original payment method within 5 business days. "
               "Setup charges are non-refundable.")
SHIPPING_TEXT = ("Shipping and delivery guide.\n\nOrders ship within 2 business days. "
                 "Delivery typically takes 5-7 days across India. Express delivery is available "
                 "on the Professional plan.")


async def _publish(client, headers, article_id):
    r = await client.post(f"/api/v1/knowledge/articles/{article_id}/approve", headers=headers, json={})
    assert r.status_code == 200, r.text
    return r.json()


# ---------- embedding pipeline (pure) ----------
def test_embedding_pipeline_deterministic():
    v1 = embed_text(REFUND_TEXT)
    v2 = embed_text(REFUND_TEXT)
    assert v1 == v2 and len(v1) == EMBED_DIM
    norm = sum(x * x for x in v1) ** 0.5
    assert abs(norm - 1.0) < 0.01
    q = embed_text("how do I get a refund for my purchase?")
    assert cosine(q, v1) > cosine(q, embed_text(SHIPPING_TEXT))


def test_chunking_respects_paragraphs_and_budget():
    long_text = "\n\n".join(f"Paragraph {i}: " + ("knowledge " * 40) for i in range(10))
    chunks = chunk_text(long_text, max_chars=900)
    assert len(chunks) > 1
    assert all(len(c) <= 900 for c in chunks)
    assert "Paragraph 0" in chunks[0]


# ---------- categories ----------
@pytest.mark.asyncio
async def test_category_crud_and_permissions(client: AsyncClient, setup):
    r = await client.post("/api/v1/knowledge/categories", headers=setup["h_admin"],
                          json={"name": "Billing", "description": "Money things"})
    assert r.status_code == 201, r.text
    cat_id = r.json()["id"]
    # duplicate name blocked
    r = await client.post("/api/v1/knowledge/categories", headers=setup["h_admin"], json={"name": "Billing"})
    assert r.status_code == 400
    # employees cannot manage categories
    r = await client.post("/api/v1/knowledge/categories", headers=setup["h_emp"], json={"name": "Nope"})
    assert r.status_code == 403
    # child category + listing with counts
    r = await client.post("/api/v1/knowledge/categories", headers=setup["h_admin"],
                          json={"name": "Refunds", "parent_id": cat_id})
    assert r.status_code == 201
    cats = (await client.get("/api/v1/knowledge/categories", headers=setup["h_admin"])).json()
    assert {c["name"] for c in cats} == {"Billing", "Refunds"}
    # delete blocked while it has children
    r = await client.delete(f"/api/v1/knowledge/categories/{cat_id}", headers=setup["h_admin"])
    assert r.status_code == 400


# ---------- repository, versioning, approval ----------
@pytest.mark.asyncio
async def test_article_lifecycle_versioning_and_approval(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/knowledge/articles", headers=setup["h_emp"],
                          json={"title": "Refund policy", "content": REFUND_TEXT, "tags": ["billing"]})
    assert r.status_code == 201, r.text
    art = r.json()
    assert art["status"] == "draft" and art["is_indexed"] is True and art["chunk_count"] >= 1

    # employee cannot approve
    r = await client.post(f"/api/v1/knowledge/articles/{art['id']}/approve", headers=setup["h_emp"], json={})
    assert r.status_code == 403
    # author submits, admin approves
    r = await client.post(f"/api/v1/knowledge/articles/{art['id']}/submit", headers=setup["h_emp"])
    assert r.status_code == 200 and r.json()["status"] == "pending_review"
    out = await _publish(client, setup["h_admin"], art["id"])
    assert out["status"] == "published"
    audit = (await db.execute(select(AuditLog).filter(
        AuditLog.organization_id == setup["org"].id,
        AuditLog.action == "KB_ARTICLE_PUBLISHED"))).scalars().all()
    assert len(audit) == 1

    # edit snapshots a version and bumps the article version
    r = await client.patch(f"/api/v1/knowledge/articles/{art['id']}", headers=setup["h_emp"],
                           json={"content": REFUND_TEXT + "\n\nUpdate: refunds now take 3 days.",
                                 "change_note": "faster refunds"})
    assert r.status_code == 200 and r.json()["version"] == 2
    versions = (await client.get(f"/api/v1/knowledge/articles/{art['id']}/versions",
                                 headers=setup["h_emp"])).json()
    assert len(versions) == 1 and versions[0]["version"] == 1 and versions[0]["change_note"] == "faster refunds"

    # restore v1 brings old content back as a new version
    r = await client.post(f"/api/v1/knowledge/articles/{art['id']}/versions/1/restore", headers=setup["h_emp"])
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == 3 and "3 days" not in body["content"]
    snaps = (await db.execute(select(KBArticleVersion).filter(
        KBArticleVersion.article_id.in_([a.id for a in (await db.execute(
            select(KBArticle).filter(KBArticle.organization_id == setup["org"].id))).scalars().all()])
    ))).scalars().all()
    assert len(snaps) == 2


@pytest.mark.asyncio
async def test_reject_flow(client: AsyncClient, setup):
    r = await client.post("/api/v1/knowledge/articles", headers=setup["h_emp"],
                          json={"title": "Rough draft", "content": "Needs work on the details."})
    art_id = r.json()["id"]
    await client.post(f"/api/v1/knowledge/articles/{art_id}/submit", headers=setup["h_emp"])
    r = await client.post(f"/api/v1/knowledge/articles/{art_id}/reject", headers=setup["h_admin"],
                          json={"note": "too thin"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    got = (await client.get(f"/api/v1/knowledge/articles/{art_id}", headers=setup["h_emp"])).json()
    assert got["review_note"] == "too thin"
    # rejected can be resubmitted
    r = await client.post(f"/api/v1/knowledge/articles/{art_id}/submit", headers=setup["h_emp"])
    assert r.status_code == 200 and r.json()["status"] == "pending_review"


# ---------- FAQ ----------
@pytest.mark.asyncio
async def test_faq_listing(client: AsyncClient, setup):
    r = await client.post("/api/v1/knowledge/articles", headers=setup["h_admin"],
                          json={"title": "How long do refunds take?",
                                "content": "Refunds are processed within 5 business days.",
                                "article_type": "faq"})
    await _publish(client, setup["h_admin"], r.json()["id"])
    faqs = (await client.get("/api/v1/knowledge/faq", headers=setup["h_emp"])).json()
    assert len(faqs) == 1
    assert faqs[0]["question"] == "How long do refunds take?"
    assert "5 business days" in faqs[0]["answer"]


# ---------- semantic search + visibility ----------
@pytest.mark.asyncio
async def test_semantic_search_ranks_and_filters_visibility(client: AsyncClient, setup, db: AsyncSession):
    r1 = await client.post("/api/v1/knowledge/articles", headers=setup["h_admin"],
                           json={"title": "Refund policy", "content": REFUND_TEXT})
    r2 = await client.post("/api/v1/knowledge/articles", headers=setup["h_admin"],
                           json={"title": "Shipping guide", "content": SHIPPING_TEXT})
    r3 = await client.post("/api/v1/knowledge/articles", headers=setup["h_admin"],
                           json={"title": "Manager playbook", "content": "Escalation matrix for refund disputes.",
                                 "visibility": "managers"})
    for r in (r1, r2, r3):
        await _publish(client, setup["h_admin"], r.json()["id"])

    r = await client.post("/api/v1/knowledge/search", headers=setup["h_emp"],
                          json={"query": "how do I refund a customer purchase?"})
    assert r.status_code == 200
    body = r.json()
    assert body["search_type"] == "semantic_hybrid" and body["count"] >= 1
    assert body["results"][0]["title"] == "Refund policy"
    # managers-only article is invisible to employees
    assert all(res["title"] != "Manager playbook" for res in body["results"])
    r = await client.post("/api/v1/knowledge/search", headers=setup["h_admin"],
                          json={"query": "escalation matrix refund disputes"})
    assert any(res["title"] == "Manager playbook" for res in r.json()["results"])
    # employee list excludes the managers-only article too
    listed = (await client.get("/api/v1/knowledge/articles", headers=setup["h_emp"])).json()
    assert all(i["title"] != "Manager playbook" for i in listed["items"])
    # search events logged
    events = (await db.execute(select(KBEvent).filter(
        KBEvent.organization_id == setup["org"].id, KBEvent.event_type == "search"))).scalars().all()
    assert len(events) == 2


# ---------- context retrieval + RAG ask ----------
@pytest.mark.asyncio
async def test_retrieve_and_grounded_ask(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/knowledge/articles", headers=setup["h_admin"],
                          json={"title": "Refund policy", "content": REFUND_TEXT})
    await _publish(client, setup["h_admin"], r.json()["id"])

    r = await client.post("/api/v1/knowledge/retrieve", headers=setup["h_emp"],
                          json={"query": "refund timeline"})
    assert r.status_code == 200
    ret = r.json()
    assert ret["rag_ready"] is True and ret["chunks"] and "Refund policy" in ret["context"]

    r = await client.post("/api/v1/knowledge/ask", headers=setup["h_emp"],
                          json={"question": "How many days does a refund take?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["grounded"] is True and body["answer"]
    assert body["provider"] == "mock" and body["sources"][0]["title"] == "Refund policy"
    events = (await db.execute(select(KBEvent).filter(
        KBEvent.organization_id == setup["org"].id, KBEvent.event_type == "ask"))).scalars().all()
    assert len(events) == 1 and events[0].results_count == 1


@pytest.mark.asyncio
async def test_ask_falls_back_when_kb_empty(client: AsyncClient, setup):
    r = await client.post("/api/v1/knowledge/ask", headers=setup["h_emp"],
                          json={"question": "What is the meaning of life?"})
    assert r.status_code == 200
    body = r.json()
    assert body["grounded"] is False and body["sources"] == [] and body["answer"]


# ---------- feedback + analytics dashboard + export ----------
@pytest.mark.asyncio
async def test_feedback_dashboard_and_export(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/knowledge/articles", headers=setup["h_admin"],
                          json={"title": "Refund policy", "content": REFUND_TEXT})
    art_id = r.json()["id"]
    await _publish(client, setup["h_admin"], art_id)

    # view + feedback
    got = (await client.get(f"/api/v1/knowledge/articles/{art_id}", headers=setup["h_emp"])).json()
    assert got["view_count"] == 1
    r = await client.post(f"/api/v1/knowledge/articles/{art_id}/feedback", headers=setup["h_emp"],
                          json={"helpful": True})
    assert r.json()["helpful_count"] == 1
    # a search with no matches → unanswered query
    await client.post("/api/v1/knowledge/search", headers=setup["h_emp"],
                      json={"query": "zzqx quantum flux capacitor"})

    dash = (await client.get("/api/v1/knowledge/dashboard", headers=setup["h_admin"])).json()
    assert dash["totals"]["articles"] == 1 and dash["totals"]["by_status"]["published"] == 1
    assert dash["totals"]["indexed"] == 1 and dash["totals"]["chunks"] >= 1
    assert dash["helpful_rate"] == 100.0
    assert dash["events_30d"].get("view") == 1 and dash["events_30d"].get("feedback") == 1
    assert any(u["query"].startswith("zzqx") for u in dash["unanswered_queries"])
    assert dash["top_articles"][0]["title"] == "Refund policy"

    # export is manager-gated CSV
    assert (await client.get("/api/v1/knowledge/export", headers=setup["h_emp"])).status_code == 403
    r = await client.get("/api/v1/knowledge/export", headers=setup["h_admin"])
    assert r.status_code == 200 and "Refund policy" in r.text


# ---------- gateway kb_answer now grounds in KB ----------
@pytest.mark.asyncio
async def test_gateway_kb_ask_uses_kb_articles(client: AsyncClient, setup):
    r = await client.post("/api/v1/knowledge/articles", headers=setup["h_admin"],
                          json={"title": "Refund policy", "content": REFUND_TEXT})
    await _publish(client, setup["h_admin"], r.json()["id"])
    r = await client.post("/api/v1/ai/knowledge/ask", headers=setup["h_admin"],
                          json={"question": "How many days for a refund?"})
    assert r.status_code == 200
    # mock provider echoes the prompt, which must carry the KB snippet marker
    assert "[kb:Refund policy]" in r.json()["text"]


# ---------- reindex ----------
@pytest.mark.asyncio
async def test_reindex_all(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/knowledge/articles", headers=setup["h_admin"],
                          json={"title": "Refund policy", "content": REFUND_TEXT})
    art_id = r.json()["id"]
    # wipe chunks to simulate a stale index
    for c in (await db.execute(select(KBChunk))).scalars().all():
        await db.delete(c)
    await db.commit()
    assert (await client.post("/api/v1/knowledge/reindex", headers=setup["h_emp"])).status_code == 403
    r = await client.post("/api/v1/knowledge/reindex", headers=setup["h_admin"])
    assert r.status_code == 200
    body = r.json()
    assert body["articles"] == 1 and body["chunks"] >= 1 and body["embedding_model"] == "hash_embed_v1"
    chunks = (await db.execute(select(KBChunk).filter(
        KBChunk.article_id == __import__("uuid").UUID(art_id)))).scalars().all()
    assert len(chunks) >= 1
