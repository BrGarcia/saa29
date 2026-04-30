import asyncio
import uuid
from app.bootstrap.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

response = client.post("/auth/login", data={"username": "encarregado", "password": "password"})
cookies = response.cookies

response = client.get("/inspecoes/", cookies=cookies)
print(response.status_code)
if response.status_code == 200:
    for item in response.json():
        print(item.get("id"))
