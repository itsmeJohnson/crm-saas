import contextvars

mask_phone_ctx = contextvars.ContextVar("mask_phone_ctx", default=False)
