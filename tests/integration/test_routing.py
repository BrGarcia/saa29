import uuid
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient

app = FastAPI()

inspecoes_router = APIRouter()
@inspecoes_router.get("/{inspecao_id}")
def get_inspecao(inspecao_id: uuid.UUID):
    return {"msg": "backend get"}

@inspecoes_router.get("/{inspecao_id}/tarefas")
def get_tarefas(inspecao_id: uuid.UUID):
    return {"msg": "backend tarefas"}

pages_router = APIRouter()
@pages_router.get("/inspecoes/{id}/detalhes")
def get_page(id: str):
    return {"msg": "frontend page"}

app.include_router(inspecoes_router, prefix="/inspecoes")
app.include_router(pages_router)

client = TestClient(app)

response = client.get("/inspecoes/123e4567-e89b-12d3-a456-426614174000/detalhes")
print(response.status_code)
print(response.json())
