"""Regras agronômicas que transformam dados integrados em recomendações.

Os cálculos seguem metodologias simplificadas e amplamente usadas:
* Evapotranspiração da cultura: ETc = ET0 (FAO-56, vinda da API) x Kc (cadastro)
* Balanço hídrico sequencial (Thornthwaite & Mather simplificado) com a
  capacidade de água disponível do solo (CAD) da cultura
* Risco de geada pela temperatura mínima prevista x limite da cultura
* Risco de doença pela combinação temperatura média + umidade relativa
* Janela de pulverização: vento < 15 km/h, sem chuva e baixa chance de chuva
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

LIMITE_ARM = 0.5        # abaixo de 50% da CAD a planta entra em estresse
VENTO_MAX_PULV = 15.0   # km/h
PROB_MAX_PULV = 40.0    # %

RECOMENDACAO_GEADA = {
    "CAFÉ ARÁBICA": "Irrigar na tarde anterior (solo úmido libera calor à noite), "
                    "chegar terra no tronco de plantas jovens e evitar capina nas entrelinhas.",
    "BATATA": "Irrigar por aspersão no fim da tarde e, se possível, antecipar a colheita "
              "dos talhões em ponto de colheita.",
    "MILHO": "Monitorar baixadas; avaliar seguro agrícola e registrar a ocorrência para laudo.",
    "LARANJA": "Proteger mudas novas (cobertura) e manter o solo limpo e úmido sob a copa.",
    "CANA-DE-AÇÚCAR": "Priorizar a colheita de talhões maduros nas áreas de baixada.",
}


def chuva_efetiva(chuva: pd.Series) -> pd.Series:
    """Parte da chuva que realmente infiltra e fica disponível (critério simplificado)."""
    return np.where(chuva < 2, 0.0, chuva * 0.8)


def calcular_indicadores(df: pd.DataFrame, cultura: dict, hoje: date) -> pd.DataFrame:
    """Recebe a série diária de UM talhão e devolve com os indicadores calculados.

    Colunas esperadas: data, temp_max, temp_min, chuva_api, chuva_pluviometro,
    et0_mm, vento_max_kmh, umidade_media, prob_chuva, irrigacao_mm
    """
    df = df.sort_values("data").reset_index(drop=True).copy()
    df["is_previsao"] = df["data"] > pd.Timestamp(hoje)

    # 1) Fusão de fontes: pluviômetro da fazenda (medição local) tem prioridade
    #    sobre a estimativa da API; para dias futuros só existe a previsão.
    df["chuva_consolidada"] = np.where(
        df["chuva_pluviometro"].notna() & ~df["is_previsao"],
        df["chuva_pluviometro"],
        df["chuva_api"].fillna(0),
    )
    df["fonte_chuva"] = np.where(
        df["chuva_pluviometro"].notna() & ~df["is_previsao"], "pluviometro", "api"
    )

    # 2) Demanda hídrica e balanço
    kc = float(cultura["kc"])
    cad = float(cultura["cad_mm"])
    df["etc_mm"] = (df["et0_mm"].fillna(0) * kc).round(2)
    df["chuva_efetiva"] = chuva_efetiva(df["chuva_consolidada"])
    df["irrigacao_mm"] = df["irrigacao_mm"].fillna(0)

    armazenamento = []
    arm = cad * 0.7                       # condição inicial: solo com 70% da CAD
    for _, linha in df.iterrows():
        arm = arm + linha["chuva_efetiva"] + linha["irrigacao_mm"] - linha["etc_mm"]
        arm = min(max(arm, 0.0), cad)
        armazenamento.append(round(arm, 2))
    df["armazenamento_mm"] = armazenamento
    df["agua_disponivel_pct"] = (df["armazenamento_mm"] / cad * 100).round(1)
    df["balanco_mm"] = (df["chuva_efetiva"] + df["irrigacao_mm"] - df["etc_mm"]).round(2)

    # 3) Riscos
    tgeada = float(cultura["temp_geada"])
    df["risco_geada"] = np.select(
        [df["temp_min"] <= tgeada, df["temp_min"] <= tgeada + 2],
        ["ALTO", "MEDIO"],
        default="BAIXO",
    )

    df["temp_media"] = ((df["temp_max"] + df["temp_min"]) / 2).round(2)
    favoravel = (
        df["temp_media"].between(float(cultura["doenca_tmin"]), float(cultura["doenca_tmax"]))
        & (df["umidade_media"] >= float(cultura["doenca_umid"]))
    )
    df["dia_favoravel_doenca"] = favoravel
    # dias consecutivos favoráveis (janela móvel de 3 dias)
    seq = favoravel.astype(int).rolling(3, min_periods=1).sum()
    df["risco_doenca"] = np.select([seq >= 3, seq >= 2], ["ALTO", "MEDIO"], default="BAIXO")

    df["janela_pulverizacao"] = (
        (df["vento_max_kmh"] < VENTO_MAX_PULV)
        & (df["chuva_consolidada"] < 1)
        & (df["prob_chuva"].fillna(0) < PROB_MAX_PULV)
    )

    df["graus_dia"] = (df["temp_media"] - float(cultura["temp_base"])).clip(lower=0).round(2)
    return df


def br(valor: float, casas: int = 0) -> str:
    """Formata número no padrão brasileiro: 12800.5 -> '12.800,5'."""
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt(d) -> str:
    return pd.Timestamp(d).strftime("%d/%m")


def gerar_alertas(df: pd.DataFrame, talhao: dict, cultura: dict, pragas: pd.DataFrame,
                  operacoes: pd.DataFrame, hoje: date) -> list[dict]:
    """Gera a lista de alertas/recomendações de um talhão."""
    alertas: list[dict] = []
    hoje_ts = pd.Timestamp(hoje)
    futuro = df[df["is_previsao"]]
    hoje_linha = df[df["data"] == hoje_ts]
    atual = hoje_linha.iloc[0] if not hoje_linha.empty else df[~df["is_previsao"]].iloc[-1]
    janelas = futuro[futuro["janela_pulverizacao"]]["data"].tolist()
    melhor_janela = _fmt(janelas[0]) if janelas else None
    nome_cultura = cultura["nome"]

    def novo(tipo, severidade, titulo, mensagem, recomendacao, data_ref, extra=None):
        alertas.append({
            "tipo": tipo,
            "severidade": severidade,
            "titulo": titulo,
            "mensagem": mensagem,
            "recomendacao": recomendacao,
            "data_referencia": pd.Timestamp(data_ref).strftime("%Y-%m-%d"),
            "dados": extra or {},
        })

    # --- GEADA ---------------------------------------------------------------
    geada = futuro[futuro["risco_geada"] != "BAIXO"]
    if not geada.empty:
        pior = geada.sort_values("temp_min").iloc[0]
        sev = "CRITICO" if pior["risco_geada"] == "ALTO" else "ATENCAO"
        novo(
            "GEADA", sev,
            f"Risco de geada em {_fmt(pior['data'])}",
            f"Mínima prevista de {pior['temp_min']:.1f} °C (limite para {nome_cultura.lower()}: "
            f"{float(cultura['temp_geada']):.1f} °C).",
            RECOMENDACAO_GEADA.get(nome_cultura, "Adotar medidas de proteção contra geada."),
            pior["data"],
            {"temp_min": float(pior["temp_min"]), "dias_risco": int(len(geada))},
        )

    # --- DÉFICIT HÍDRICO -------------------------------------------------------
    cad = float(cultura["cad_mm"])
    prox3 = futuro.head(3)
    chuva_prox3 = float(prox3["chuva_consolidada"].sum())
    etc_prox3 = float(prox3["etc_mm"].sum())
    if atual["agua_disponivel_pct"] < LIMITE_ARM * 100 and chuva_prox3 < etc_prox3:
        # repõe o solo até 90% da CAD (o excesso seria perdido por percolação)
        lamina = round(cad * 0.9 - float(atual["armazenamento_mm"]), 1)
        if talhao["irrigado"]:
            novo(
                "DEFICIT_HIDRICO", "CRITICO" if atual["agua_disponivel_pct"] < 30 else "ATENCAO",
                f"Irrigar {lamina:.0f} mm",
                f"Água disponível no solo em {atual['agua_disponivel_pct']:.0f}% da capacidade. "
                f"Previsão de {chuva_prox3:.1f} mm de chuva para consumo de {etc_prox3:.1f} mm nos próximos 3 dias.",
                f"Aplicar lâmina de {lamina:.0f} mm (≈ {br(lamina * 10 * float(talhao['area_ha']))} m³ "
                f"para {br(float(talhao['area_ha']), 1)} ha), preferencialmente à noite.",
                hoje_ts,
                {"agua_disponivel_pct": float(atual["agua_disponivel_pct"]), "lamina_mm": lamina},
            )
        else:
            novo(
                "DEFICIT_HIDRICO", "ATENCAO",
                "Estresse hídrico (talhão sem irrigação)",
                f"Água disponível no solo em {atual['agua_disponivel_pct']:.0f}% da capacidade e pouca chuva prevista.",
                "Adiar adubação de cobertura até a próxima chuva e manter cobertura morta nas entrelinhas.",
                hoje_ts,
                {"agua_disponivel_pct": float(atual["agua_disponivel_pct"])},
            )

    # --- EXCESSO DE CHUVA -----------------------------------------------------
    if chuva_prox3 >= 60:
        novo(
            "EXCESSO_CHUVA", "ATENCAO",
            f"{chuva_prox3:.0f} mm previstos em 3 dias",
            "Volume elevado de chuva pode causar erosão e perda de adubo por lixiviação.",
            "Adiar adubação e aplicações; verificar terraços e curvas de nível.",
            prox3["data"].iloc[0],
            {"chuva_prevista_3d": chuva_prox3},
        )

    # --- DOENÇA ---------------------------------------------------------------
    janela_doenca = df[(df["data"] >= hoje_ts - pd.Timedelta(days=2)) & (df["risco_doenca"] != "BAIXO")]
    if not janela_doenca.empty:
        alto = (janela_doenca["risco_doenca"] == "ALTO").any()
        rec = f"Programar fungicida preventivo para {cultura['doenca'].lower()}"
        rec += f" na janela de pulverização de {melhor_janela}." if melhor_janela else \
               ". Não há janela de pulverização adequada nos próximos 7 dias - monitorar."
        novo(
            "DOENCA", "CRITICO" if alto else "ATENCAO",
            f"Clima favorável a {cultura['doenca']}",
            f"{int(janela_doenca['dia_favoravel_doenca'].sum())} dia(s) com temperatura média entre "
            f"{float(cultura['doenca_tmin']):.0f}-{float(cultura['doenca_tmax']):.0f} °C e umidade ≥ "
            f"{float(cultura['doenca_umid']):.0f}%.",
            rec,
            janela_doenca["data"].iloc[0],
            {"doenca": cultura["doenca"], "janela": melhor_janela},
        )

    # --- PRAGAS (caderno de campo / SQLite) ------------------------------------
    if not pragas.empty:
        recentes = pragas[(pragas["data"] >= hoje_ts - pd.Timedelta(days=14)) & (pragas["nivel"] >= 3)]
        for praga, grupo in recentes.groupby("praga"):
            ult = grupo.sort_values("data").iloc[-1]
            novo(
                "PRAGA", "CRITICO" if ult["nivel"] >= 4 else "ATENCAO",
                f"{praga.capitalize()} - nível {int(ult['nivel'])}/5",
                f"Infestação registrada no caderno de campo em {_fmt(ult['data'])}"
                f" ({len(grupo)} registro(s) acima do nível de controle nas últimas 2 semanas).",
                "Realizar inspeção de confirmação e controle"
                + (f" na janela de pulverização de {melhor_janela}." if melhor_janela else
                   " assim que houver janela de pulverização (vento e chuva desfavoráveis nos próximos dias)."),
                ult["data"],
                {"praga": praga, "nivel": int(ult["nivel"])},
            )

    # --- EFICIÊNCIA: irrigação em dia de chuva (ERP x clima) -------------------
    if not operacoes.empty:
        irrig = operacoes[(operacoes["tipo"] == "IRRIGACAO") & (operacoes["data"] >= hoje_ts - pd.Timedelta(days=30))]
        if not irrig.empty:
            cruz = irrig.merge(df[["data", "chuva_consolidada"]], on="data", how="left")
            desperdicio = cruz[cruz["chuva_consolidada"] >= 10]
            if not desperdicio.empty:
                custo = float(desperdicio["custo"].sum())
                novo(
                    "EFICIENCIA", "INFO",
                    f"{len(desperdicio)} irrigação(ões) em dias de chuva",
                    f"Nos últimos 30 dias houve irrigação em dias com ≥ 10 mm de chuva "
                    f"({', '.join(_fmt(d) for d in desperdicio['data'])}). Custo: R$ {br(custo, 2)}.",
                    "Consultar a previsão no AgroSentinela antes de programar a irrigação.",
                    desperdicio["data"].iloc[-1],
                    {"custo_evitavel": custo},
                )

    # --- JANELA DE PULVERIZAÇÃO (informativo) ----------------------------------
    if janelas:
        novo(
            "PULVERIZACAO", "INFO",
            f"Melhor janela de pulverização: {melhor_janela}",
            f"{len(janelas)} dia(s) adequados nos próximos 7 dias: {', '.join(_fmt(d) for d in janelas)}.",
            "Aplicar nas horas mais frescas (até 10h ou após 16h).",
            janelas[0],
            {"dias": [_fmt(d) for d in janelas]},
        )

    for a in alertas:
        a.update({
            "talhao_id": int(talhao["id"]),
            "talhao_codigo": talhao["codigo"],
            "talhao_nome": talhao["nome"],
            "cultura": nome_cultura,
            "propriedade": talhao["propriedade"],
            "produtor": talhao["produtor"],
            "cidade": talhao["cidade"],
            "latitude": float(talhao["latitude"]),
            "longitude": float(talhao["longitude"]),
        })
    return alertas
