from pydantic import BaseModel, Field


class TokenCreate(BaseModel):
    name: str = Field(..., max_length=120)
    datasets: list[str] | None = None


class TokenUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    datasets: list[str] | None = None
    is_active: bool | None = None


class SettingsUpdate(BaseModel):
    storage_provider: str | None = None
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_prefix: str | None = None


class WebhookExportRequest(BaseModel):
    source_type: str = "dataset"
    source_key: str
    url: str = Field(..., max_length=500)
    format: str = "json"


class CloudExportRequest(BaseModel):
    source_type: str = "dataset"
    source_key: str
    format: str = "csv"
    path_prefix: str | None = Field(None, max_length=200)


class SyncCreate(BaseModel):
    name: str = Field(..., max_length=150)
    source_type: str = "dataset"
    source_key: str
    format: str = "json"
    destination: str = "webhook"
    target_url: str | None = Field(None, max_length=500)
    path_prefix: str | None = Field(None, max_length=200)
    mode: str = "full"
    frequency: str = "daily"
    is_active: bool = True


class SyncUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    format: str | None = None
    destination: str | None = None
    target_url: str | None = Field(None, max_length=500)
    path_prefix: str | None = Field(None, max_length=200)
    mode: str | None = None
    frequency: str | None = None
    is_active: bool | None = None
