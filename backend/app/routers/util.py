import json

import pandas as pd
from fastapi import HTTPException

from app.db import conexoes


def registros(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> lista de dicts serializáveis (datas ISO, NaN -> null)."""
    return json.loads(df.to_json(orient="records", date_format="iso", force_ascii=False))


def consulta_dw(sql: str, params: list | None = None) -> list[dict]:
    try:
        with conexoes.duck_leitura() as con:
            return registros(con.execute(sql, params or []).df())
    except FileNotFoundError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


def ultima_execucao_ok() -> dict | None:
    return conexoes.mongo()["execucoes_etl"].find_one({"status": "SUCESSO"}, sort=[("inicio", -1)])


def limpar_mongo(doc: dict) -> dict:
    doc = dict(doc)
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    for k, v in doc.items():
        if hasattr(v, "isoformat"):
            doc[k] = v.isoformat()
    return doc
