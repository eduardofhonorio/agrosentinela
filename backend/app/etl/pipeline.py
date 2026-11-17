"""Pipeline completo de integração do AgroSentinela.

    python -m app.etl.pipeline                 # coleta + consolidação
    python -m app.etl.pipeline --pular-coleta  # só consolidação (usado pelo workflow do Hop)
    python -m app.etl.pipeline --cenario geada # simulação de frente fria (demonstração)

Etapas
  1. COLETA      Open-Meteo -> MySQL.clima_diario  (Apache Hop ou coletor Python)
  2. EXTRAÇÃO    MySQL (cadastro, operações, clima) + SQLite (caderno de campo)
  3. LIMPEZA     padronização e validação do caderno de campo; rejeitados -> MongoDB
  4. INTEGRAÇÃO  junção das fontes por talhão/dia + fusão pluviômetro x API
  5. INDICADORES balanço hídrico, riscos de geada/doença, janela de pulverização
  6. CARGA DW    DuckDB (modelo estrela)
  7. ALERTAS     documentos de recomendação -> MongoDB
"""
from __future__ import annotations

import argparse
import time
import uuid
from datetime import date, datetime

import pandas as pd

from app.db import conexoes
from app.etl import coleta_clima, limpeza
from app.services import agronomia

SQL_TALHOES = """
SELECT t.id, t.codigo, t.nome, t.area_ha, t.irrigado, t.data_plantio, t.latitude, t.longitude,
       c.nome AS cultura, c.kc, c.temp_base, c.temp_geada, c.cad_mm, c.doenca,
       c.doenca_tmin, c.doenca_tmax, c.doenca_umid,
       p.nome AS propriedade, p.cidade, p.uf, p.ibge, pr.nome AS produtor
FROM talhoes t
JOIN culturas c      ON c.id = t.cultura_id
JOIN propriedades p  ON p.id = t.propriedade_id
JOIN produtores pr   ON pr.id = p.produtor_id
WHERE t.ativo = TRUE
"""


class Execucao:
    """Registra etapas, tempos e auditoria da execução (vai para o MongoDB)."""

    def __init__(self, cenario, log):
        self.id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self.inicio = datetime.now()
        self.cenario = cenario
        self.etapas = []
        self._log = log

    def log(self, msg):
        self._log(msg)

    def etapa(self, nome, detalhes, t0):
        self.etapas.append({"etapa": nome, "duracao_s": round(time.time() - t0, 2), "detalhes": detalhes})
        self.log(f"[OK] {nome} ({time.time() - t0:.1f}s) {detalhes if isinstance(detalhes, str) else ''}")


def aplicar_cenario(clima: pd.DataFrame, cenario: str | None, hoje: date) -> pd.DataFrame:
    """Simulação didática: frente fria polar entre o 2º e o 4º dia de previsão."""
    if cenario != "geada":
        return clima
    clima = clima.copy()
    alvo = clima["data"].between(pd.Timestamp(hoje) + pd.Timedelta(days=2), pd.Timestamp(hoje) + pd.Timedelta(days=4))
    clima.loc[alvo, "temp_min"] = clima.loc[alvo, "temp_min"] - 15
    clima.loc[alvo, "temp_max"] = clima.loc[alvo, "temp_max"] - 9
    return clima


def executar(cenario: str | None = None, pular_coleta: bool = False, log=print) -> dict:
    ex = Execucao(cenario, log)
    hoje = date.today()
    mongo = conexoes.mongo()
    log(f"=== Execução {ex.id} ===")
    try:
        # 1) COLETA -------------------------------------------------------------
        t0 = time.time()
        if pular_coleta:
            ex.etapa("1. Coleta de clima", {"motor": "externo (Apache Hop workflow)"}, t0)
        else:
            res = coleta_clima.coletar(log)
            ex.etapa("1. Coleta de clima", res, t0)

        # 2) EXTRAÇÃO -----------------------------------------------------------
        t0 = time.time()
        eng = conexoes.mysql()
        talhoes = pd.read_sql(SQL_TALHOES, eng)
        clima = pd.read_sql("SELECT * FROM clima_diario", eng, parse_dates=["data"])
        operacoes = pd.read_sql("SELECT * FROM operacoes", eng, parse_dates=["data"])
        con_sqlite = conexoes.sqlite()
        pluv_bruto = pd.read_sql("SELECT * FROM leituras_pluviometro", con_sqlite)
        obs_bruto = pd.read_sql("SELECT * FROM observacoes_campo", con_sqlite)
        con_sqlite.close()
        # Landing zone: cópia fiel do que veio do campo (antes da limpeza)
        mongo["bruto_caderno_campo"].delete_many({})
        mongo["bruto_caderno_campo"].insert_many(
            [{"tipo": "pluviometro", **r} for r in pluv_bruto.astype(object).where(pluv_bruto.notna(), None).to_dict("records")]
            + [{"tipo": "observacao", **r} for r in obs_bruto.astype(object).where(obs_bruto.notna(), None).to_dict("records")]
        )
        ex.etapa("2. Extração", {
            "mysql_talhoes": len(talhoes), "mysql_clima_diario": len(clima), "mysql_operacoes": len(operacoes),
            "sqlite_pluviometro": len(pluv_bruto), "sqlite_observacoes": len(obs_bruto),
        }, t0)
        if clima.empty:
            raise RuntimeError("Nenhum dado de clima em clima_diario. Verifique a coleta (Hop/API).")

        # 3) LIMPEZA ------------------------------------------------------------
        t0 = time.time()
        rejeitados: list = []
        codigos = set(talhoes["codigo"])
        pluv, aud_pluv = limpeza.limpar_pluviometro(pluv_bruto, codigos, rejeitados)
        pragas, aud_obs = limpeza.limpar_observacoes(obs_bruto, codigos, rejeitados)
        mongo["rejeitados"].delete_many({})
        if rejeitados:
            mongo["rejeitados"].insert_many([{**r, "execucao_id": ex.id} for r in rejeitados])
        ex.etapa("3. Limpeza do caderno de campo", {
            "pluviometro": aud_pluv, "observacoes": aud_obs, "rejeitados": len(rejeitados)}, t0)

        # 4) INTEGRAÇÃO + 5) INDICADORES ------------------------------------------
        t0 = time.time()
        clima = aplicar_cenario(clima, cenario, hoje)
        mapa_id = dict(zip(talhoes["codigo"], talhoes["id"]))
        pluv["talhao_id"] = pluv["codigo"].map(mapa_id)
        pragas["talhao_id"] = pragas["codigo"].map(mapa_id)
        irrig = (operacoes[operacoes["tipo"] == "IRRIGACAO"]
                 .groupby(["talhao_id", "data"], as_index=False)["quantidade"].sum()
                 .rename(columns={"quantidade": "irrigacao_mm"}))

        series, todos_alertas = [], []
        for t in talhoes.to_dict("records"):
            base = clima[clima["talhao_id"] == t["id"]].rename(columns={"chuva_mm": "chuva_api"})
            if base.empty:
                continue
            base = (base.merge(pluv[pluv["talhao_id"] == t["id"]][["data", "mm"]]
                               .rename(columns={"mm": "chuva_pluviometro"}), on="data", how="left")
                        .merge(irrig[irrig["talhao_id"] == t["id"]][["data", "irrigacao_mm"]], on="data", how="left"))
            for col in ["temp_max", "temp_min", "chuva_api", "et0_mm", "vento_max_kmh", "umidade_media",
                        "prob_chuva", "chuva_pluviometro", "irrigacao_mm"]:
                base[col] = pd.to_numeric(base[col], errors="coerce").astype(float)
            cultura = {**t, "nome": t["cultura"]}
            ind = agronomia.calcular_indicadores(base, cultura, hoje)
            ind["talhao_id"] = t["id"]
            series.append(ind)
            todos_alertas += agronomia.gerar_alertas(
                ind, t, cultura,
                pragas[pragas["talhao_id"] == t["id"]],
                operacoes[operacoes["talhao_id"] == t["id"]],
                hoje,
            )
        fato_clima = pd.concat(series, ignore_index=True)
        ex.etapa("4-5. Integração e indicadores", {
            "talhoes_processados": len(series), "linhas_fato": len(fato_clima),
            "dias_com_pluviometro": int((fato_clima["fonte_chuva"] == "pluviometro").sum()),
            "alertas": len(todos_alertas)}, t0)

        # 6) CARGA NO DATA WAREHOUSE (DuckDB) -----------------------------------
        t0 = time.time()
        carregar_dw(talhoes, fato_clima, operacoes, pragas)
        ex.etapa("6. Carga do Data Warehouse (DuckDB)", "modelo estrela recriado", t0)

        # 7) ALERTAS (MongoDB) ---------------------------------------------------
        t0 = time.time()
        agora = datetime.now()
        for a in todos_alertas:
            a.update({"execucao_id": ex.id, "gerado_em": agora, "cenario": cenario})
        mongo["alertas"].delete_many({"execucao_id": {"$ne": ex.id}, "gerado_em": {"$lt": agora - pd.Timedelta(days=30)}})
        if todos_alertas:
            mongo["alertas"].insert_many(todos_alertas)
        mongo["alertas"].create_index([("execucao_id", 1), ("severidade", 1)])
        ex.etapa("7. Alertas gravados no MongoDB", {"documentos": len(todos_alertas)}, t0)
        status = "SUCESSO"
        erro = None
    except Exception as e:  # noqa: BLE001
        status, erro = "FALHA", f"{e.__class__.__name__}: {e}"
        log(f"[ERRO] {erro}")

    fim = datetime.now()
    doc = {
        "_id": ex.id, "inicio": ex.inicio, "fim": fim,
        "duracao_s": round((fim - ex.inicio).total_seconds(), 2),
        "status": status, "erro": erro, "cenario": cenario, "etapas": ex.etapas,
    }
    try:
        mongo["execucoes_etl"].insert_one(_jsonavel(doc))
    except Exception as e:  # noqa: BLE001
        log(f"[ERRO] não foi possível registrar a execução no MongoDB: {e}")
    log(f"=== {status} em {doc['duracao_s']}s ===")
    return doc


def _jsonavel(obj):
    """Converte tipos numpy/pandas para tipos nativos (MongoDB/JSON)."""
    import numpy as np
    if isinstance(obj, dict):
        return {k: _jsonavel(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonavel(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def carregar_dw(talhoes, fato_clima, operacoes, pragas):
    datas = pd.concat([fato_clima["data"], operacoes["data"], pragas["data"]]).dropna().drop_duplicates()
    dim_tempo = pd.DataFrame({"data": sorted(datas)})
    dim_tempo["data_key"] = dim_tempo["data"].dt.strftime("%Y%m%d").astype(int)
    dim_tempo["ano"] = dim_tempo["data"].dt.year
    dim_tempo["mes"] = dim_tempo["data"].dt.month
    dim_tempo["dia"] = dim_tempo["data"].dt.day
    dim_tempo["trimestre"] = dim_tempo["data"].dt.quarter
    dim_tempo["dia_semana"] = dim_tempo["data"].dt.dayofweek
    nomes_mes = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    dim_tempo["nome_mes"] = dim_tempo["mes"].map(lambda m: nomes_mes[m - 1])

    dim_talhao = talhoes.rename(columns={"id": "talhao_key"})[[
        "talhao_key", "codigo", "nome", "cultura", "kc", "cad_mm", "temp_geada", "doenca", "area_ha",
        "irrigado", "data_plantio", "propriedade", "produtor", "cidade", "uf", "ibge", "latitude", "longitude"]]
    for c in ["kc", "cad_mm", "temp_geada", "area_ha", "latitude", "longitude"]:
        dim_talhao[c] = dim_talhao[c].astype(float)
    dim_talhao["irrigado"] = dim_talhao["irrigado"].astype(bool)

    fc = fato_clima.copy()
    fc["talhao_key"] = fc["talhao_id"]
    fc["data_key"] = fc["data"].dt.strftime("%Y%m%d").astype(int)
    fato_clima_dw = fc[[
        "talhao_key", "data_key", "is_previsao", "temp_max", "temp_min", "temp_media", "chuva_api",
        "chuva_pluviometro", "chuva_consolidada", "fonte_chuva", "et0_mm", "etc_mm", "irrigacao_mm",
        "chuva_efetiva", "balanco_mm", "armazenamento_mm", "agua_disponivel_pct", "umidade_media",
        "vento_max_kmh", "prob_chuva", "risco_geada", "risco_doenca", "dia_favoravel_doenca",
        "janela_pulverizacao", "graus_dia"]]

    op = operacoes.copy()
    op["talhao_key"] = op["talhao_id"]
    op["data_key"] = op["data"].dt.strftime("%Y%m%d").astype(int)
    fato_op = op[["talhao_key", "data_key", "tipo", "descricao", "quantidade", "unidade", "custo"]].copy()
    fato_op["quantidade"] = fato_op["quantidade"].astype(float)
    fato_op["custo"] = fato_op["custo"].astype(float)

    pg = pragas.copy()
    pg["talhao_key"] = pg["talhao_id"].astype(int)
    pg["data_key"] = pg["data"].dt.strftime("%Y%m%d").astype(int)
    fato_pragas = pg[["talhao_key", "data_key", "praga", "nivel", "tecnico", "observacao"]]

    with conexoes.duck_escrita_temporaria() as duck:
        for nome, df in [("dim_tempo", dim_tempo), ("dim_talhao", dim_talhao),
                         ("fato_clima_talhao", fato_clima_dw), ("fato_operacoes", fato_op),
                         ("fato_pragas", fato_pragas)]:
            duck.register("df_tmp", df)
            duck.execute(f"CREATE TABLE {nome} AS SELECT * FROM df_tmp")
            duck.unregister("df_tmp")
        duck.execute(open(_sql_views(), encoding="utf-8").read())


def _sql_views():
    from app import config
    return config.RAIZ / "database" / "duckdb" / "views_dw.sql"


def main():
    import sys
    for fluxo in (sys.stdout, sys.stderr):        # evita erro de acentuação no console do Windows
        try:
            fluxo.reconfigure(errors="replace")
        except AttributeError:
            pass
    ap = argparse.ArgumentParser(description="Pipeline de integração AgroSentinela")
    ap.add_argument("--pular-coleta", action="store_true", help="não coleta clima (já feito pelo Apache Hop)")
    ap.add_argument("--cenario", choices=["geada"], help="aplica cenário simulado para demonstração")
    args = ap.parse_args()
    r = executar(cenario=args.cenario, pular_coleta=args.pular_coleta)
    raise SystemExit(0 if r["status"] == "SUCESSO" else 1)


if __name__ == "__main__":
    main()
