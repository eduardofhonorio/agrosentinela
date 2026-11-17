"""Configurações centrais lidas do arquivo .env (raiz do projeto)."""
from pathlib import Path
import os

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]          # pasta agrosentinela/
load_dotenv(RAIZ / ".env")


def _caminho(valor: str) -> Path:
    p = Path(valor)
    return p if p.is_absolute() else RAIZ / p


MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
MYSQL_DB = os.getenv("MYSQL_DB", "agrosentinela")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "agrosentinela")

SQLITE_PATH = _caminho(os.getenv("SQLITE_PATH", "dados/caderno_campo.db"))
DUCKDB_PATH = _caminho(os.getenv("DUCKDB_PATH", "dados/dw_agrosentinela.duckdb"))

HOP_HOME = os.getenv("HOP_HOME", "").strip()
HOP_PROJECT_DIR = RAIZ / "hop"

OPEN_METEO_URL = os.getenv("OPEN_METEO_URL", "").strip() or "https://api.open-meteo.com/v1/forecast"

TIMEZONE = "America/Sao_Paulo"
DIAS_HISTORICO = 30
DIAS_PREVISAO = 8          # inclui hoje: 7 dias futuros completos
