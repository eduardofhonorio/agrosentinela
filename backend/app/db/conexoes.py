"""Conexões com as quatro tecnologias de armazenamento do projeto.

| Banco    | Papel na solução                                                    |
|----------|---------------------------------------------------------------------|
| MySQL    | Sistema transacional (cadastro, operações) + staging do clima (Hop) |
| SQLite   | Caderno de campo offline usado pelo técnico no celular              |
| MongoDB  | Documentos: alertas gerados, dados brutos e log das execuções       |
| DuckDB   | Data Warehouse analítico (modelo estrela) que alimenta o painel     |
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from urllib.parse import quote_plus

import duckdb
from pymongo import MongoClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app import config

# --------------------------------------------------------------------- MySQL
_engine: Engine | None = None


def mysql_url(com_banco: bool = True) -> str:
    banco = f"/{config.MYSQL_DB}" if com_banco else "/"
    return (
        f"mysql+pymysql://{config.MYSQL_USER}:{quote_plus(config.MYSQL_PASSWORD)}"
        f"@{config.MYSQL_HOST}:{config.MYSQL_PORT}{banco}?charset=utf8mb4"
    )


def mysql() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(mysql_url(), pool_pre_ping=True, pool_recycle=1800)
    return _engine


def mysql_sem_banco() -> Engine:
    """Conexão sem selecionar banco (usada para criar o schema)."""
    return create_engine(mysql_url(com_banco=False))


# ------------------------------------------------------------------- MongoDB
_mongo: MongoClient | None = None


def mongo():
    global _mongo
    if _mongo is None:
        _mongo = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)
    return _mongo[config.MONGO_DB]


# -------------------------------------------------------------------- SQLite
def sqlite() -> sqlite3.Connection:
    config.SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.SQLITE_PATH)
    con.row_factory = sqlite3.Row
    return con


# -------------------------------------------------------------------- DuckDB
# O DuckDB permite apenas um processo escrevendo no arquivo. Para que o painel
# continue respondendo durante a carga, o ETL grava em um arquivo temporário e
# depois o substitui (troca atômica). As leituras usam conexões curtas.
_trava_duck = threading.Lock()


@contextmanager
def duck_leitura():
    if not config.DUCKDB_PATH.exists():
        raise FileNotFoundError(
            "Data Warehouse ainda não foi gerado. Execute a integração (POST /api/etl/executar)."
        )
    with _trava_duck:
        con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
        try:
            yield con
        finally:
            con.close()


@contextmanager
def duck_escrita_temporaria():
    """Abre um DuckDB novo em arquivo temporário; ao final substitui o oficial."""
    config.DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = config.DUCKDB_PATH.with_suffix(".tmp.duckdb")
    if tmp.exists():
        tmp.unlink()
    con = duckdb.connect(str(tmp))
    try:
        yield con
        con.close()
        for tentativa in range(10):          # no Windows o arquivo pode estar em uso
            try:
                with _trava_duck:
                    os.replace(tmp, config.DUCKDB_PATH)
                break
            except PermissionError:
                if tentativa == 9:
                    raise
                time.sleep(0.5)
    except Exception:
        con.close()
        if tmp.exists():
            tmp.unlink()
        raise


def status_conexoes() -> dict:
    """Verifica se cada banco está acessível (usado na tela de Integração)."""
    st = {}
    try:
        with mysql().connect() as c:
            c.execute(text("SELECT 1"))
        st["mysql"] = "ok"
    except Exception as e:  # noqa: BLE001
        st["mysql"] = f"erro: {e.__class__.__name__}"
    try:
        mongo().command("ping")
        st["mongodb"] = "ok"
    except Exception as e:  # noqa: BLE001
        st["mongodb"] = f"erro: {e.__class__.__name__}"
    st["sqlite"] = "ok" if config.SQLITE_PATH.exists() else "arquivo não encontrado"
    st["duckdb"] = "ok" if config.DUCKDB_PATH.exists() else "aguardando 1ª integração"
    return st
