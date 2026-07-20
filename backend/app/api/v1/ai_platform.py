import json
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.services.ai_gateway_service import AIGatewayService
from app.middleware.permissions import require_active_user

router = APIRouter()


class GenerateRequest(BaseModel):
    prompt: str | None = None
    messages: list[dict] | None = None
    task_type: str = "general"
    template_key: str | None = None
    variables: dict | None = None
    context_type: str | None = None
    context_id: str | None = None
    conversation_id: uuid.UUID | None = None
    provider: str | None = None
    model: str | None = None
    temperature: float | None = Field(None, ge=0, le=2)
    max_tokens: int | None = Field(None, ge=1, le=8192)


class ChatRequest(BaseModel):
    message: str
    conversation_id: uuid.UUID | None = None
    title: str | None = None
    context_type: str | None = None
    context_id: str | None = None
    provider: str | None = None
    model: str | None = None


class ProviderCreate(BaseModel):
    provider: str
    name: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    deployment: str | None = None
    api_version: str | None = None
    default_model: str = "mock-ai"
    models: list[dict] | None = None
    priority: int = Field(1, ge=1, le=20)
    is_active: bool = True


class ProviderUpdate(BaseModel):
    name: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    deployment: str | None = None
    api_version: str | None = None
    default_model: str | None = None
    models: list[dict] | None = None
    priority: int | None = Field(None, ge=1, le=20)
    is_active: bool | None = None


class TemplateCreate(BaseModel):
    key: str = Field(..., max_length=60)
    name: str = Field(..., max_length=150)
    task_type: str = "general"
    system_prompt: str | None = None
    template: str
    model_override: str | None = None
    provider_override: str | None = None
    temperature: float | None = Field(None, ge=0, le=2)


class TemplateUpdate(BaseModel):
    name: str | None = None
    task_type: str | None = None
    system_prompt: str | None = None
    template: str | None = None
    model_override: str | None = None
    provider_override: str | None = None
    temperature: float | None = Field(None, ge=0, le=2)
    is_active: bool | None = None


class SettingsUpdate(BaseModel):
    is_enabled: bool | None = None
    default_provider: str | None = None
    default_model: str | None = None
    temperature: float | None = Field(None, ge=0, le=2)
    max_tokens: int | None = Field(None, ge=1, le=8192)
    daily_request_limit: int | None = Field(None, ge=1, le=100000)
    monthly_budget_usd: float | None = Field(None, ge=0)
    cache_enabled: bool | None = None
    cache_ttl_minutes: int | None = Field(None, ge=1, le=10080)
    streaming_enabled: bool | None = None
    memory_messages: int | None = Field(None, ge=1, le=50)
    context_max_chars: int | None = Field(None, ge=500, le=20000)


class DraftRequest(BaseModel):
    context_type: str
    context_id: str
    goal: str = "follow up"


class KBRequest(BaseModel):
    question: str


class SummarizeRequest(BaseModel):
    text: str
    length: int = Field(5, ge=1, le=10)


def _svc(db):
    return AIGatewayService(db)


# ================= gateway =================
@router.post("/generate")
async def generate(req: GenerateRequest, actor: Annotated[User, Depends(require_active_user)],
                   db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).generate(actor, **req.model_dump())


@router.post("/generate/stream")
async def generate_stream(req: GenerateRequest, actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    svc = _svc(db)

    async def sse():
        async for chunk in svc.stream_generate(actor, **req.model_dump()):
            yield f"data: {json.dumps({'delta': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")


@router.post("/chat")
async def chat(req: ChatRequest, actor: Annotated[User, Depends(require_active_user)],
               db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).chat(actor, req.model_dump())


# ================= conversations (memory) =================
@router.get("/conversations")
async def conversations(actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).list_conversations(actor)


@router.get("/conversations/{conversation_id}/messages")
async def conversation_messages(conversation_id: uuid.UUID,
                                actor: Annotated[User, Depends(require_active_user)],
                                db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).conversation_messages(actor, conversation_id)


# ================= admin: settings / providers / templates =================
@router.get("/settings")
async def get_settings(actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).get_settings(actor)


@router.patch("/settings")
async def update_settings(req: SettingsUpdate, actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update_settings(actor, req.model_dump(exclude_unset=True))


@router.get("/providers")
async def list_providers(actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).list_providers(actor)


@router.post("/providers", status_code=status.HTTP_201_CREATED)
async def create_provider(req: ProviderCreate, actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).create_provider(actor, req.model_dump())


@router.patch("/providers/{provider_id}")
async def update_provider(provider_id: uuid.UUID, req: ProviderUpdate,
                          actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update_provider(actor, provider_id, req.model_dump(exclude_unset=True))


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(provider_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    await _svc(db).delete_provider(actor, provider_id)


@router.post("/providers/{provider_id}/test")
async def test_provider(provider_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).test_provider(actor, provider_id)


@router.get("/templates")
async def list_templates(actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).list_templates(actor)


@router.post("/templates", status_code=status.HTTP_201_CREATED)
async def create_template(req: TemplateCreate, actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).create_template(actor, req.model_dump())


@router.patch("/templates/{template_id}")
async def update_template(template_id: uuid.UUID, req: TemplateUpdate,
                          actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update_template(actor, template_id, req.model_dump(exclude_unset=True))


# ================= monitoring =================
@router.get("/usage/dashboard")
async def usage_dashboard(actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)],
                          days: int = Query(30, ge=1, le=365)):
    return await _svc(db).usage_dashboard(actor, days=days)


@router.get("/usage/logs")
async def usage_logs(actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)],
                     limit: int = Query(100, ge=1, le=300)):
    return await _svc(db).usage_logs(actor, limit=limit)


# ================= platform integrations =================
@router.post("/crm/summarize")
async def crm_summarize(req: DraftRequest, actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).crm_summarize(actor, req.context_type, req.context_id)


@router.post("/crm/draft-email")
async def crm_draft_email(req: DraftRequest, actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).crm_draft_email(actor, req.context_type, req.context_id, req.goal)


@router.post("/crm/call-script")
async def crm_call_script(req: DraftRequest, actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).crm_call_script(actor, req.context_type, req.context_id, req.goal)


@router.post("/reports/{report_id}/narrative")
async def report_narrative(report_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                           db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).report_narrative(actor, report_id)


@router.post("/communication/{activity_id}/draft-reply")
async def draft_reply(activity_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).draft_reply(actor, activity_id)


@router.post("/knowledge/ask")
async def kb_ask(req: KBRequest, actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).kb_answer(actor, req.question)


@router.post("/documents/summarize")
async def summarize(req: SummarizeRequest, actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).summarize_text(actor, req.text, length=req.length)
