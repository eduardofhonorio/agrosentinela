"""AgroSentinela - API (FastAPI).

    uvicorn app.main:app --reload        (dentro da pasta backend)
    Documentação interativa: http://localhost:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import cadastro, etl, painel

app = FastAPI(
    title="AgroSentinela API",
    description="Inteligência climática para o produtor rural - integração MySQL, SQLite, "
                "MongoDB, DuckDB, Apache Hop, Open-Meteo e ViaCEP.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(painel.router)
app.include_router(cadastro.router)
app.include_router(etl.router)


@app.get("/", include_in_schema=False)
def raiz():
    return {"app": "AgroSentinela", "docs": "/docs"}
