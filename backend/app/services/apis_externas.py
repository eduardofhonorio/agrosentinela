"""Consumo das APIs externas públicas (sem necessidade de chave).

* Open-Meteo Forecast  - histórico recente + previsão do tempo por coordenada
* Open-Meteo Geocoding - transforma o nome do município em latitude/longitude
* ViaCEP               - transforma o CEP em endereço completo + código IBGE
"""
from __future__ import annotations

import re
import time
import unicodedata

import requests

from app import config

URL_PREVISAO = config.OPEN_METEO_URL
URL_GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"
URL_VIACEP = "https://viacep.com.br/ws/{cep}/json/"

VARIAVEIS_DIARIAS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "et0_fao_evapotranspiration",
    "wind_speed_10m_max",
    "relative_humidity_2m_mean",
    "precipitation_probability_max",
]

TIMEOUT = 20


class ErroApiExterna(Exception):
    pass


def _get_com_retentativa(url: str, params: dict, tentativas: int = 4) -> requests.Response:
    """GET com novas tentativas em caso de limite de requisições (HTTP 429) ou falha de rede."""
    espera = 2
    for i in range(tentativas):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)
            if r.status_code == 429 and i < tentativas - 1:
                time.sleep(espera)
                espera *= 2
                continue
            r.raise_for_status()
            return r
        except requests.ConnectionError:
            if i == tentativas - 1:
                raise
            time.sleep(espera)
            espera *= 2
    raise requests.HTTPError("limite de tentativas atingido")


def previsao_diaria(latitude: float, longitude: float) -> dict:
    """Retorna o JSON bruto da Open-Meteo: 30 dias passados + 7 de previsão."""
    return previsao_diaria_lote([(latitude, longitude)])[0]


def previsao_diaria_lote(coordenadas: list[tuple[float, float]]) -> list[dict]:
    """Uma única chamada para vários pontos (a Open-Meteo aceita listas de
    coordenadas separadas por vírgula e devolve uma lista de respostas)."""
    params = {
        "latitude": ",".join(f"{lat:.4f}" for lat, _ in coordenadas),
        "longitude": ",".join(f"{lon:.4f}" for _, lon in coordenadas),
        "daily": ",".join(VARIAVEIS_DIARIAS),
        "past_days": config.DIAS_HISTORICO,
        "forecast_days": config.DIAS_PREVISAO,
        "timezone": config.TIMEZONE,
    }
    try:
        r = _get_com_retentativa(URL_PREVISAO, params)
    except requests.RequestException as e:
        raise ErroApiExterna(f"Open-Meteo indisponível: {e}") from e
    dados = r.json()
    return dados if isinstance(dados, list) else [dados]


def consultar_cep(cep: str) -> dict:
    cep_limpo = re.sub(r"\D", "", cep or "")
    if len(cep_limpo) != 8:
        raise ErroApiExterna("CEP deve conter 8 dígitos")
    try:
        r = requests.get(URL_VIACEP.format(cep=cep_limpo), timeout=TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        raise ErroApiExterna(f"ViaCEP indisponível: {e}") from e
    dados = r.json()
    if dados.get("erro"):
        raise ErroApiExterna("CEP não encontrado")
    return dados


def _sem_acento(txt: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn").lower()


def geocodificar_municipio(cidade: str, uf: str) -> dict:
    """Busca coordenadas do município na Open-Meteo, filtrando pela UF correta
    (há vários 'São João da Boa Vista' no Brasil)."""
    estados = {
        "AC": "acre", "AL": "alagoas", "AP": "amapa", "AM": "amazonas", "BA": "bahia",
        "CE": "ceara", "DF": "distrito federal", "ES": "espirito santo", "GO": "goias",
        "MA": "maranhao", "MT": "mato grosso", "MS": "mato grosso do sul", "MG": "minas gerais",
        "PA": "para", "PB": "paraiba", "PR": "parana", "PE": "pernambuco", "PI": "piaui",
        "RJ": "rio de janeiro", "RN": "rio grande do norte", "RS": "rio grande do sul",
        "RO": "rondonia", "RR": "roraima", "SC": "santa catarina", "SP": "sao paulo",
        "SE": "sergipe", "TO": "tocantins",
    }
    try:
        r = requests.get(
            URL_GEOCODING,
            params={"name": cidade, "count": 10, "language": "pt", "countryCode": "BR"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        raise ErroApiExterna(f"Geocodificação indisponível: {e}") from e
    resultados = r.json().get("results") or []
    estado = estados.get(uf.upper(), "")
    for item in resultados:
        if _sem_acento(item.get("admin1", "")) == estado:
            return {"latitude": item["latitude"], "longitude": item["longitude"], "elevacao": item.get("elevation")}
    if resultados:
        item = resultados[0]
        return {"latitude": item["latitude"], "longitude": item["longitude"], "elevacao": item.get("elevation")}
    raise ErroApiExterna("Município não localizado")
