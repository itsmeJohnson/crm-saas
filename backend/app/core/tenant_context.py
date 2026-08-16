import contextvars
import uuid

class TenantContextError(ValueError):
    """Raised when tenant context is missing or invalid."""
    pass

_current_tenant_id: contextvars.ContextVar[uuid.UUID] = contextvars.ContextVar("current_tenant_id")

class TenantContext:
    @staticmethod
    def set_tenant_id(tenant_id: uuid.UUID) -> contextvars.Token:
        if not isinstance(tenant_id, uuid.UUID):
            raise TenantContextError("Tenant ID must be a valid UUID.")
        return _current_tenant_id.set(tenant_id)

    @staticmethod
    def reset_tenant_id(token: contextvars.Token) -> None:
        _current_tenant_id.reset(token)

    @staticmethod
    def get_tenant_id() -> uuid.UUID:
        try:
            return _current_tenant_id.get()
        except LookupError:
            raise TenantContextError("Tenant context is missing (fail closed).")
