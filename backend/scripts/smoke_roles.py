"""PR-1 role/API smoke walk. For each seeded persona, mint a JWT and hit every
no-path-param GET endpoint under /api/v1, then report the status matrix. A 5xx
is a real defect; 401/403 (permission) and 422 (needs query params) are expected
for some routes and are counted separately, not treated as failures.

Run:  docker exec -w /app crm-backend python scripts/smoke_roles.py
"""
import asyncio
from collections import defaultdict

from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from main import app
from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.models.user import User

PERSONAS = {
    "Director":    "director@abcprops-demo.com",
    "Manager":     "sales.manager1@abcprops-demo.com",
    "Executive":   "sales.exec1@abcprops-demo.com",
    "Collections": "collections1@abcprops-demo.com",
    "Support":     "support1@abcprops-demo.com",
}


def get_paths():
    spec = app.openapi()
    return sorted(
        p for p, ops in spec.get("paths", {}).items()
        if "get" in ops and p.startswith("/api/v1") and "{" not in p
    )


async def main():
    paths = get_paths()
    async with async_session_maker() as db:
        tokens = {}
        for label, email in PERSONAS.items():
            u = (await db.execute(select(User).filter(User.email == email))).scalars().first()
            if not u:
                print(f"  ! persona {label} ({email}) not found — did the seeder run?")
                continue
            tokens[label] = create_access_token(u.id, u.token_version)

    transport = ASGITransport(app=app)
    server_errors = []
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        print(f"Probing {len(paths)} no-param GET endpoints across {len(tokens)} personas...\n")
        for label, token in tokens.items():
            buckets = defaultdict(int)
            h = {"Authorization": f"Bearer {token}"}
            for p in paths:
                try:
                    r = await client.get(p, headers=h)
                    code = r.status_code
                except Exception as e:
                    code = 599
                    server_errors.append((label, p, f"exception: {e}"))
                    continue
                if code >= 500:
                    server_errors.append((label, p, code))
                bucket = "2xx" if code < 300 else "3xx" if code < 400 else \
                         "401/403" if code in (401, 403) else "404" if code == 404 else \
                         "422" if code == 422 else "429(ratelimit)" if code == 429 else \
                         "4xx" if code < 500 else "5xx"
                buckets[bucket] += 1
            summary = " ".join(f"{k}={v}" for k, v in sorted(buckets.items()))
            print(f"  {label:12} {summary}")

    print("\n" + ("=" * 60))
    if server_errors:
        print(f"SERVER ERRORS (5xx) — {len(server_errors)} — THESE ARE REAL BUGS:")
        for label, p, code in server_errors:
            print(f"  [{label}] {code}  {p}")
    else:
        print("No 5xx server errors across any persona / endpoint. ✓")


asyncio.run(main())
