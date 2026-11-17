"""Limpeza dos dados do caderno de campo (SQLite).

Problemas tratados (mesmas técnicas vistas na disciplina, agora em pandas):
* códigos de talhão com espaços, minúsculas ou sem hífen  -> TRIM/UPPER/padronização
* datas em 3 formatos (aaaa-mm-dd, dd/mm/aaaa, dd-mm-aaaa) -> data única
* milímetros com vírgula decimal, vazios, negativos ou absurdos
* nomes de pragas escritos de formas diferentes            -> nome canônico
* nível de infestação fora da escala 0-5 ou nulo
* registros duplicados (sincronização repetida do aplicativo)
* talhões inexistentes no cadastro (MySQL)                 -> rejeitados + log
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd

PRAGAS_CANONICAS = {
    "bicho mineiro": "BICHO-MINEIRO",
    "broca do cafe": "BROCA-DO-CAFÉ",
    "acaro vermelho": "ÁCARO-VERMELHO",
    "mosca branca": "MOSCA-BRANCA",
    "traca da batata": "TRAÇA-DA-BATATA",
    "vaquinha": "VAQUINHA",
    "lagarta do cartucho": "LAGARTA-DO-CARTUCHO",
    "cigarrinha do milho": "CIGARRINHA-DO-MILHO",
    "psilideo": "PSILÍDEO",
    "acaro da leprose": "ÁCARO-DA-LEPROSE",
    "broca da cana": "BROCA-DA-CANA",
    "cigarrinha das raizes": "CIGARRINHA-DAS-RAÍZES",
}


def _sem_acento(txt: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn")


def padronizar_codigo(cod) -> str | None:
    if cod is None or pd.isna(cod):
        return None
    c = str(cod).strip().upper().replace(" ", "")
    m = re.fullmatch(r"([A-Z]{3})-?(\d{2})", c)
    return f"{m.group(1)}-{m.group(2)}" if m else c


def padronizar_data(valor) -> pd.Timestamp | None:
    if valor is None or pd.isna(valor):
        return None
    v = str(valor).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return pd.to_datetime(v, format=fmt)
        except ValueError:
            continue
    return None


def padronizar_praga(nome) -> str | None:
    if nome is None or pd.isna(nome) or not str(nome).strip():
        return None
    chave = _sem_acento(str(nome)).lower().replace("-", " ").strip()
    chave = re.sub(r"\s+", " ", chave)
    return PRAGAS_CANONICAS.get(chave, str(nome).strip().upper())


def _rejeitar(df: pd.DataFrame, mascara, motivo: str, origem: str, rejeitados: list):
    for reg in df[mascara].to_dict("records"):
        rejeitados.append({"origem": origem, "motivo": motivo,
                           "registro": {k: (None if pd.isna(v) else str(v)) for k, v in reg.items()}})
    return df[~mascara]


def limpar_pluviometro(df: pd.DataFrame, codigos_validos: set, rejeitados: list) -> tuple[pd.DataFrame, dict]:
    auditoria = {"lidos": len(df)}
    df = df.copy()
    df["codigo"] = df["talhao"].map(padronizar_codigo)
    df["data"] = df["data_leitura"].map(padronizar_data)
    df["mm"] = pd.to_numeric(df["milimetros"].astype(str).str.strip().str.replace(",", ".", regex=False),
                             errors="coerce")

    df = _rejeitar(df, ~df["codigo"].isin(codigos_validos), "talhão inexistente no cadastro", "pluviometro", rejeitados)
    df = _rejeitar(df, df["data"].isna(), "data inválida", "pluviometro", rejeitados)
    df = _rejeitar(df, df["mm"].isna(), "milímetros não numérico/vazio", "pluviometro", rejeitados)
    df = _rejeitar(df, (df["mm"] < 0) | (df["mm"] > 250), "milímetros fora da faixa 0-250", "pluviometro", rejeitados)

    antes = len(df)
    df = df.drop_duplicates(subset=["codigo", "data"], keep="last")
    auditoria["duplicados_removidos"] = antes - len(df)
    auditoria["validos"] = len(df)
    return df[["codigo", "data", "mm", "tecnico"]], auditoria


def limpar_observacoes(df: pd.DataFrame, codigos_validos: set, rejeitados: list) -> tuple[pd.DataFrame, dict]:
    auditoria = {"lidos": len(df)}
    df = df.copy()
    df["codigo"] = df["talhao"].map(padronizar_codigo)
    df["data"] = df["data_obs"].map(padronizar_data)
    df["praga"] = df["praga"].map(padronizar_praga)
    df["nivel"] = pd.to_numeric(df["nivel"], errors="coerce")

    df = _rejeitar(df, ~df["codigo"].isin(codigos_validos), "talhão inexistente no cadastro", "observacoes", rejeitados)
    df = _rejeitar(df, df["data"].isna(), "data inválida", "observacoes", rejeitados)
    df = _rejeitar(df, df["praga"].isna(), "praga não informada", "observacoes", rejeitados)
    df = _rejeitar(df, df["nivel"].isna() | ~df["nivel"].between(0, 5), "nível fora da escala 0-5", "observacoes", rejeitados)

    antes = len(df)
    df = df.drop_duplicates(subset=["codigo", "data", "praga"], keep="last")
    auditoria["duplicados_removidos"] = antes - len(df)
    auditoria["validos"] = len(df)
    df["nivel"] = df["nivel"].astype(int)
    return df[["codigo", "data", "praga", "nivel", "observacao", "tecnico"]], auditoria
