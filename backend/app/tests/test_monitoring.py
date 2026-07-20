import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_metrics_endpoint(client: AsyncClient):
    # 1. Hit a regular endpoint to trigger metrics recording
    health_response = await client.get("/health")
    assert health_response.status_code == 200

    # 2. Query metrics
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")

    content = response.text
    
    # 3. Assert correct prometheus tags and custom counters exist
    assert "crm_db_connection_healthy" in content
    assert "crm_process_memory_usage_bytes" in content
    assert "crm_process_cpu_seconds_total" in content
    assert "crm_http_requests_total" in content
    assert "crm_http_request_latency_seconds_sum" in content
    assert "crm_http_request_latency_seconds_count" in content

    # Assert that the health endpoint query we made was tracked
    assert 'crm_http_requests_total{method="GET",path="/health",status="200"}' in content
