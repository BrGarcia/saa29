import asyncio
import httpx
from app.bootstrap.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
response = client.get("/inspecoes/12345678-1234-1234-1234-123456789012/detalhes", allow_redirects=False, headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
print("STATUS CODE:", response.status_code)
print("HEADERS:", response.headers)
print("BODY SNIPPET:", response.text[:200])
