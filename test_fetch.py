import asyncio
from app.bootstrap.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# Login first
response = client.post("/auth/login", data={"username": "encarregado", "password": "password"})
cookies = response.cookies

# Get inspecoes
response = client.get("/inspecoes/", cookies=cookies)
print(response.status_code)
if response.status_code == 200:
    data = response.json()
    print(data[:2])
else:
    print(response.text)
