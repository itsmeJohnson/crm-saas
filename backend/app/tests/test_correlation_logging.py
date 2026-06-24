import json
import logging
import pytest
from httpx import AsyncClient
from app.core.logging_config import JSONFormatter
from app.middleware.correlation import correlation_id_ctx

@pytest.mark.asyncio
async def test_correlation_id_header(client: AsyncClient):
    # Send a request with a custom correlation ID header
    response = await client.get("/health", headers={"X-Correlation-ID": "test-trace-uuid-999"})
    assert response.status_code == 200
    assert response.headers.get("X-Correlation-ID") == "test-trace-uuid-999"

    # Send a request without correlation ID -> should autogenerate one
    response_no_header = await client.get("/health")
    assert response_no_header.status_code == 200
    generated_id = response_no_header.headers.get("X-Correlation-ID")
    assert generated_id is not None
    assert len(generated_id) > 10

def test_json_formatter_with_correlation_id():
    # Set correlation ID in context
    token = correlation_id_ctx.set("formatter-trace-id")
    try:
        # Create a log record
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test_file.py",
            lineno=42,
            msg="This is a test message",
            args=(),
            exc_info=None
        )
        
        formatter = JSONFormatter()
        formatted_str = formatter.format(record)
        
        # Parse JSON output and verify keys
        log_json = json.loads(formatted_str)
        assert log_json["message"] == "This is a test message"
        assert log_json["level"] == "INFO"
        assert log_json["correlation_id"] == "formatter-trace-id"
    finally:
        correlation_id_ctx.reset(token)
