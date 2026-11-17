"""Disparo e acompanhamento do pipeline de integração."""
import threading
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app import config
from app.db import conexoes
from app.etl import coleta_clima, pipeline
from app.routers.util import limpar_mongo

router = APIRouter(prefix="/api", tags=["Integração"])

_estado = {"executando": False, "log": [], "inicio": None, "resultado": None}
_trava = threading.Lock()


def _rodar(cenario):
    def log(msg):
        _estado["log"].append(f"{datetime.now():%H:%M:%S} {msg}")
    try:
        _estado["resultado"] = pipeline._jsonavel(pipeline.executar(cenario=cenario, log=log))
        if _estado["resultado"]:
            _estado["resultado"] = {k: (v.isoformat() if hasattr(v, "isoformat") else v)
                                    for k, v in _estado["resultado"].items()}
    finally:
        _estado["executando"] = False


@router.post("/etl/executar", status_code=202)
def executar(cenario: str | None = None):
    if cenario not in (None, "", "geada"):
        raise HTTPException(400, "Cenário inválido")
    with _trava:
        if _estado["executando"]:
            raise HTTPException(409, "Já existe uma execução em andamento")
        _estado.update(executando=True, log=[], inicio=datetime.now().isoformat(), resultado=None)
    threading.Thread(target=_rodar, args=(cenario or None,), daemon=True).start()
    return {"mensagem": "Integração iniciada", "motor_coleta": "apache-hop" if coleta_clima.hop_disponivel() else "python"}


@router.get("/etl/status")
def status():
    return _estado


@router.get("/etl/execucoes")
def execucoes(limite: int = 10):
    docs = conexoes.mongo()["execucoes_etl"].find().sort("inicio", -1).limit(limite)
    return [limpar_mongo(d) for d in docs]


@router.get("/etl/rejeitados")
def rejeitados():
    return [limpar_mongo(d) for d in conexoes.mongo()["rejeitados"].find().limit(200)]


@router.get("/etl/amostras")
def amostras():
    """Exemplos de dados brutos (antes da integração) para a demonstração."""
    db = conexoes.mongo()
    bruto_api = db["bruto_open_meteo"].find_one(sort=[("coletado_em", -1)])
    if bruto_api:
        r = bruto_api["resposta"]
        r["daily"] = {k: v[:5] for k, v in r.get("daily", {}).items()}   # recorta para exibição
    caderno = list(db["bruto_caderno_campo"].find({}, {"_id": 0}).limit(8))
    return {"open_meteo": limpar_mongo(bruto_api) if bruto_api else None, "caderno_campo": caderno}


@router.get("/saude")
def saude():
    return {"bancos": conexoes.status_conexoes(),
            "apache_hop": "configurado" if coleta_clima.hop_disponivel() else "não configurado (coletor Python)",
            "hop_home": config.HOP_HOME or None}
