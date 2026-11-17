"""Endpoints de leitura analítica (DuckDB) e alertas (MongoDB)."""
from fastapi import APIRouter, HTTPException

from app.db import conexoes
from app.routers.util import consulta_dw, limpar_mongo, ultima_execucao_ok

router = APIRouter(prefix="/api", tags=["Painel"])

ORDEM_SEV = {"CRITICO": 0, "ATENCAO": 1, "INFO": 2}
# Dentro da mesma severidade, o que exige ação mais rápida vem primeiro
ORDEM_TIPO = {"GEADA": 0, "DEFICIT_HIDRICO": 1, "DOENCA": 2, "PRAGA": 3, "EXCESSO_CHUVA": 4, "EFICIENCIA": 5, "PULVERIZACAO": 6}


def _alertas_atuais(filtro: dict | None = None) -> list[dict]:
    ult = ultima_execucao_ok()
    if not ult:
        return []
    q = {"execucao_id": ult["_id"], **(filtro or {})}
    docs = [limpar_mongo(d) for d in conexoes.mongo()["alertas"].find(q)]
    return sorted(docs, key=lambda d: (ORDEM_SEV.get(d["severidade"], 9), ORDEM_TIPO.get(d["tipo"], 9), d["data_referencia"]))


@router.get("/painel")
def painel():
    talhoes = consulta_dw("""
        SELECT s.*, r.chuva_30d, r.etc_30d, r.chuva_prev_7d, r.temp_min_prev_7d, r.dias_pulverizacao_7d
        FROM vw_status_atual s JOIN vw_resumo_talhao r USING (talhao_key)
        ORDER BY s.codigo""")
    alertas = _alertas_atuais()
    pior = {}
    for a in alertas:
        atual = pior.get(a["talhao_id"])
        if atual is None or ORDEM_SEV[a["severidade"]] < ORDEM_SEV[atual]:
            pior[a["talhao_id"]] = a["severidade"]
    for t in talhoes:
        t["status"] = pior.get(t["talhao_key"], "OK")
        t["qtd_alertas"] = sum(1 for a in alertas if a["talhao_id"] == t["talhao_key"] and a["severidade"] != "INFO")
    ult = ultima_execucao_ok()
    kpis = {
        "talhoes": len(talhoes),
        "area_total_ha": round(sum(t["area_ha"] for t in talhoes), 1),
        "produtores": len({t["produtor"] for t in talhoes}),
        "alertas_criticos": sum(1 for a in alertas if a["severidade"] == "CRITICO"),
        "alertas_atencao": sum(1 for a in alertas if a["severidade"] == "ATENCAO"),
        "chuva_media_30d": round(sum(t["chuva_30d"] or 0 for t in talhoes) / max(len(talhoes), 1), 1),
        "chuva_prevista_7d": round(sum(t["chuva_prev_7d"] or 0 for t in talhoes) / max(len(talhoes), 1), 1),
        "menor_temp_prevista": min((t["temp_min_prev_7d"] for t in talhoes if t["temp_min_prev_7d"] is not None), default=None),
        "custo_evitavel": round(sum(a["dados"].get("custo_evitavel", 0) for a in alertas), 2),
        "ultima_atualizacao": ult["fim"].isoformat() if ult else None,
        "cenario": ult.get("cenario") if ult else None,
    }
    return {"kpis": kpis, "talhoes": talhoes, "alertas": alertas}


@router.get("/alertas")
def alertas(severidade: str | None = None, talhao_id: int | None = None, tipo: str | None = None):
    filtro = {}
    if severidade:
        filtro["severidade"] = severidade.upper()
    if talhao_id:
        filtro["talhao_id"] = talhao_id
    if tipo:
        filtro["tipo"] = tipo.upper()
    return _alertas_atuais(filtro)


@router.get("/talhoes")
def talhoes():
    return consulta_dw("SELECT * FROM dim_talhao ORDER BY codigo")


@router.get("/talhoes/{talhao_id}")
def detalhe_talhao(talhao_id: int):
    dim = consulta_dw("SELECT * FROM dim_talhao WHERE talhao_key = ?", [talhao_id])
    if not dim:
        raise HTTPException(404, "Talhão não encontrado no Data Warehouse")
    serie = consulta_dw("""
        SELECT t.data, f.* EXCLUDE (talhao_key, data_key)
        FROM fato_clima_talhao f JOIN dim_tempo t USING (data_key)
        WHERE f.talhao_key = ? ORDER BY t.data""", [talhao_id])
    operacoes = consulta_dw("""
        SELECT t.data, o.tipo, o.descricao, o.quantidade, o.unidade, o.custo
        FROM fato_operacoes o JOIN dim_tempo t USING (data_key)
        WHERE o.talhao_key = ? ORDER BY t.data DESC""", [talhao_id])
    pragas = consulta_dw("""
        SELECT t.data, p.praga, p.nivel, p.tecnico, p.observacao
        FROM fato_pragas p JOIN dim_tempo t USING (data_key)
        WHERE p.talhao_key = ? ORDER BY t.data""", [talhao_id])
    resumo = consulta_dw("SELECT * FROM vw_resumo_talhao WHERE talhao_key = ?", [talhao_id])
    return {
        "talhao": dim[0], "resumo": resumo[0] if resumo else {}, "serie": serie,
        "operacoes": operacoes, "pragas": pragas, "alertas": _alertas_atuais({"talhao_id": talhao_id}),
    }


@router.get("/analises")
def analises():
    return {
        "pluviometro_vs_api": consulta_dw("SELECT * FROM vw_pluviometro_vs_api ORDER BY codigo"),
        "custo_hectare": consulta_dw("""
            SELECT codigo, nome, cultura, area_ha,
                   SUM(custo_total) AS custo_total, SUM(custo_por_ha) AS custo_por_ha,
                   SUM(CASE WHEN tipo='IRRIGACAO' THEN custo_por_ha ELSE 0 END)    AS irrigacao,
                   SUM(CASE WHEN tipo='PULVERIZACAO' THEN custo_por_ha ELSE 0 END) AS pulverizacao,
                   SUM(CASE WHEN tipo='ADUBACAO' THEN custo_por_ha ELSE 0 END)     AS adubacao,
                   SUM(CASE WHEN tipo='PLANTIO' THEN custo_por_ha ELSE 0 END)      AS plantio
            FROM vw_custo_hectare GROUP BY ALL ORDER BY custo_por_ha DESC"""),
        "chuva_municipio": consulta_dw("SELECT * FROM vw_chuva_municipio ORDER BY chuva_media_30d DESC"),
        "ranking_pragas": consulta_dw("SELECT * FROM vw_ranking_pragas ORDER BY nivel_medio DESC, ocorrencias DESC"),
        "balanco_cultura": consulta_dw("""
            SELECT d.cultura,
                   ROUND(AVG(CASE WHEN NOT f.is_previsao THEN f.agua_disponivel_pct END), 1) AS agua_media_pct,
                   ROUND(SUM(CASE WHEN NOT f.is_previsao THEN f.etc_mm END) / COUNT(DISTINCT d.talhao_key), 1) AS etc_30d,
                   ROUND(SUM(CASE WHEN NOT f.is_previsao THEN f.chuva_consolidada END) / COUNT(DISTINCT d.talhao_key), 1) AS chuva_30d
            FROM fato_clima_talhao f JOIN dim_talhao d USING (talhao_key)
            GROUP BY d.cultura ORDER BY d.cultura"""),
    }
