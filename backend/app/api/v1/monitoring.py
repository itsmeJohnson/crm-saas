import sys
import time
import os
import resource
import uuid
import re
from fastapi import APIRouter, Response, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db

router = APIRouter()

# Global metrics storage
HTTP_REQUESTS_TOTAL = {} # (method, path, status_code) -> count
HTTP_REQUEST_LATENCY_SECONDS_SUM = {} # (method, path, status_code) -> sum of latency
HTTP_REQUEST_LATENCY_SECONDS_COUNT = {} # (method, path, status_code) -> count

def record_http_request(method: str, path: str, status_code: int, latency: float):
    # Simple regex path sanitization: replace UUIDs/IDs with {id}
    sanitized_path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', path)
    sanitized_path = re.sub(r'/\d+', '/{id}', sanitized_path)
    
    key = (method, sanitized_path, status_code)
    HTTP_REQUESTS_TOTAL[key] = HTTP_REQUESTS_TOTAL.get(key, 0) + 1
    HTTP_REQUEST_LATENCY_SECONDS_SUM[key] = HTTP_REQUEST_LATENCY_SECONDS_SUM.get(key, 0.0) + latency
    HTTP_REQUEST_LATENCY_SECONDS_COUNT[key] = HTTP_REQUEST_LATENCY_SECONDS_COUNT.get(key, 0) + 1

@router.get("/metrics")
async def get_metrics(db: AsyncSession = Depends(get_db)):
    lines = []
    
    # 1. DB connection health
    db_healthy = 1
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_healthy = 0
    lines.append("# HELP crm_db_connection_healthy Database connection status (1 for healthy, 0 for unhealthy)")
    lines.append("# TYPE crm_db_connection_healthy gauge")
    lines.append(f"crm_db_connection_healthy {db_healthy}")
    
    # 2. Process memory usage (in bytes)
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        memory_bytes = usage.ru_maxrss
        if sys.platform != 'darwin': # macOS is bytes, others are KB
            memory_bytes *= 1024
    except Exception:
        memory_bytes = 0
        
    lines.append("# HELP crm_process_memory_usage_bytes Process memory usage in bytes")
    lines.append("# TYPE crm_process_memory_usage_bytes gauge")
    lines.append(f"crm_process_memory_usage_bytes {memory_bytes}")
    
    # 3. CPU time
    try:
        cpu_time = time.process_time()
    except Exception:
        cpu_time = 0.0
    lines.append("# HELP crm_process_cpu_seconds_total Total user and system CPU time spent in seconds")
    lines.append("# TYPE crm_process_cpu_seconds_total counter")
    lines.append(f"crm_process_cpu_seconds_total {cpu_time}")
    
    # 4. HTTP requests count
    lines.append("# HELP crm_http_requests_total Total number of HTTP requests processed")
    lines.append("# TYPE crm_http_requests_total counter")
    for (method, path, status_code), count in HTTP_REQUESTS_TOTAL.items():
        lines.append(f'crm_http_requests_total{{method="{method}",path="{path}",status="{status_code}"}} {count}')
        
    # 5. HTTP requests latency
    lines.append("# HELP crm_http_request_latency_seconds_sum Sum of HTTP request durations in seconds")
    lines.append("# TYPE crm_http_request_latency_seconds_sum counter")
    for (method, path, status_code), val in HTTP_REQUEST_LATENCY_SECONDS_SUM.items():
        lines.append(f'crm_http_request_latency_seconds_sum{{method="{method}",path="{path}",status="{status_code}"}} {val:.6f}')
        
    lines.append("# HELP crm_http_request_latency_seconds_count Count of HTTP request durations in seconds")
    lines.append("# TYPE crm_http_request_latency_seconds_count counter")
    for (method, path, status_code), count in HTTP_REQUEST_LATENCY_SECONDS_COUNT.items():
        lines.append(f'crm_http_request_latency_seconds_count{{method="{method}",path="{path}",status="{status_code}"}} {count}')
        
    return Response(content="\n".join(lines) + "\n", media_type="text/plain")
