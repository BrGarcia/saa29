import asyncio
from app.bootstrap.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

response = client.get("/inspecoes/550e8400-e29b-41d4-a716-446655440000/detalhes", headers={"Accept": "text/html"}, allow_redirects=True)
print("STATUS:", response.status_code)
print("BODY_LEN:", len(response.text))
if len(response.text) < 1000:
    print(response.text)
