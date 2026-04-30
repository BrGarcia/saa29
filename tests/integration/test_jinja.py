import asyncio
from fastapi.testclient import TestClient
from app.bootstrap.main import app

client = TestClient(app)

response = client.post("/auth/login", data={"username": "encarregado", "password": "password"})
cookies = response.cookies

response = client.get("/inspecoes/550e8400-e29b-41d4-a716-446655440000/detalhes", cookies=cookies)
print("STATUS:", response.status_code)
html = response.text
lines = html.splitlines()
for i, line in enumerate(lines):
    if "window.INSPECAO_ID" in line:
        print(f"Line {i+1}: {line.strip()}")
