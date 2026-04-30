from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
import uuid

app = FastAPI()

r1 = APIRouter(prefix="/inspecoes")
@r1.get("/{inspecao_id}")
def backend(inspecao_id: uuid.UUID):
    return {"msg": "backend"}

r2 = APIRouter()
@r2.get("/inspecoes/{id}/detalhes")
def frontend(id: str):
    return {"msg": "frontend"}

app.include_router(r1)
app.include_router(r2)

client = TestClient(app)
print(client.get("/inspecoes/550e8400-e29b-41d4-a716-446655440000/detalhes").json())
