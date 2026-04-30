import asyncio
from fastapi.testclient import TestClient
from app.bootstrap.main import app

client = TestClient(app)

response = client.get("/inspecoes/123e4567-e89b-12d3-a456-426614174000/detalhes")
print(response.status_code)
print(response.text[:200])

response_lista = client.get("/inspecoes")
print(response_lista.status_code)
print(response_lista.text[:200])
