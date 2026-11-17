"""Coleta de clima - versão Python do pipeline Apache Hop (hop/pipelines/coleta_clima.hpl).

Fluxo idêntico ao do Hop:
    MySQL (vw_talhoes_coordenadas) -> REST Open-Meteo -> JSON -> MySQL (clima_diario)

Adicionalmente guarda a resposta JSON bruta no MongoDB (coleção bruto_open_meteo),
mantendo o dado original disponível para reprocessamentos (conceito de ELT/data lake).

Uso direto:  python -m app.etl.coleta_clima
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from app import config
from app.db import conexoes
from app.services import apis_externas

SQL_UPSERT = text("""
    INSERT INTO clima_diario (talhao_id, data, temp_max, temp_min, chuva_mm, et0_mm,
                              vento_max_kmh, umidade_media, prob_chuva, fonte, carregado_por)
    VALUES (:talhao_id, :data, :temp_max, :temp_min, :chuva_mm, :et0_mm,
            :vento_max_kmh, :umidade_media, :prob_chuva, 'open-meteo', 'python')
    ON DUPLICATE KEY UPDATE
        temp_max = VALUES(temp_max), temp_min = VALUES(temp_min), chuva_mm = VALUES(chuva_mm),
        et0_mm = VALUES(et0_mm), vento_max_kmh = VALUES(vento_max_kmh),
        umidade_media = VALUES(umidade_media), prob_chuva = VALUES(prob_chuva),
        carregado_por = 'python'
""")


def json_para_linhas(talhao_id: int, resposta: dict) -> list[dict]:
    d = resposta["daily"]
    linhas = []
    for i, dia in enumerate(d["time"]):
        linhas.append({
            "talhao_id": talhao_id,
            "data": dia,
            "temp_max": d["temperature_2m_max"][i],
            "temp_min": d["temperature_2m_min"][i],
            "chuva_mm": d["precipitation_sum"][i],
            "et0_mm": d["et0_fao_evapotranspiration"][i],
            "vento_max_kmh": d["wind_speed_10m_max"][i],
            "umidade_media": d["relative_humidity_2m_mean"][i],
            "prob_chuva": d["precipitation_probability_max"][i],
        })
    return linhas


def coletar_python(log=print) -> dict:
    talhoes = pd.read_sql("SELECT * FROM vw_talhoes_coordenadas", conexoes.mysql())
    if talhoes.empty:
        return {"motor": "python", "talhoes": 0, "registros": 0, "erros": []}
    coords = [(float(t.latitude), float(t.longitude)) for t in talhoes.itertuples()]
    try:
        respostas = apis_externas.previsao_diaria_lote(coords)     # 1 requisição para todos
    except apis_externas.ErroApiExterna as e:
        log(f"   ! {e} - mantidos os dados de clima já existentes no MySQL")
        return {"motor": "python", "talhoes": len(talhoes), "registros": 0, "erros": [str(e)]}

    agora = datetime.now()
    conexoes.mongo()["bruto_open_meteo"].insert_many([
        {"talhao_id": int(t.talhao_id), "codigo": t.codigo, "coletado_em": agora, "resposta": resp}
        for t, resp in zip(talhoes.itertuples(), respostas)
    ])
    total = 0
    with conexoes.mysql().begin() as con:
        for t, resp in zip(talhoes.itertuples(), respostas):
            linhas = json_para_linhas(int(t.talhao_id), resp)
            con.execute(SQL_UPSERT, linhas)
            total += len(linhas)
            log(f"   {t.codigo}: {len(linhas)} dias gravados")
    return {"motor": "python", "talhoes": len(talhoes), "registros": total, "erros": []}


def _hop_script(nome: str) -> Path:
    ext = ".bat" if sys.platform.startswith("win") else ".sh"
    return Path(config.HOP_HOME) / f"{nome}{ext}"


def hop_disponivel() -> bool:
    return bool(config.HOP_HOME) and _hop_script("hop-run").exists()


def _executar(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=config.HOP_HOME, capture_output=True, text=True,
                          timeout=timeout, encoding="utf-8", errors="replace")


def garantir_projeto_hop():
    """Registra o projeto 'agrosentinela' no Hop (equivale a 'Add project' na GUI)."""
    proj = str(config.HOP_PROJECT_DIR)
    lista = _executar([str(_hop_script("hop-conf")), "--projects-list"]).stdout
    if f"agrosentinela : {proj}" in lista:
        return
    acao = "--project-modify" if "agrosentinela :" in lista else "--project-create"
    _executar([str(_hop_script("hop-conf")), acao, "--project", "agrosentinela",
               "--project-home", proj, "--project-config-file", "project-config.json"])


def coletar_hop(log=print) -> dict:
    """Executa o pipeline do Apache Hop em modo headless (hop-run)."""
    garantir_projeto_hop()
    parametros = ",".join([
        f"MYSQL_HOST={config.MYSQL_HOST}", f"MYSQL_PORT={config.MYSQL_PORT}",
        f"MYSQL_DB={config.MYSQL_DB}", f"MYSQL_USER={config.MYSQL_USER}",
        f"MYSQL_PASSWORD={config.MYSQL_PASSWORD}", f"OPEN_METEO_URL={config.OPEN_METEO_URL}",
    ])
    cmd = [str(_hop_script("hop-run")), "--project=agrosentinela",
           "--file=${PROJECT_HOME}/pipelines/coleta_clima.hpl",
           "--runconfig=local", "--level=Basic", f"--parameters={parametros}"]
    log("   executando Apache Hop: pipelines/coleta_clima.hpl")
    proc = _executar(cmd)
    saida = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0 or "ERROR" in saida:
        raise RuntimeError("Apache Hop falhou:\n" + saida[-2000:])
    resumo = [ln.split(" - ", 1)[-1] for ln in saida.splitlines() if "Finished processing" in ln]
    for ln in resumo:
        log(f"   [hop] {ln}")
    with conexoes.mysql().connect() as con:
        total = con.execute(text(
            "SELECT COUNT(*) FROM clima_diario WHERE carregado_por='apache-hop' "
            "AND atualizado_em >= NOW() - INTERVAL 15 MINUTE")).scalar()
    return {"motor": "apache-hop", "registros": int(total), "transforms": resumo}


def coletar(log=print) -> dict:
    if hop_disponivel():
        try:
            return coletar_hop(log)
        except Exception as e:  # noqa: BLE001
            log(f"   ! Hop indisponível ({str(e)[:200]}). Usando coletor Python.")
    return coletar_python(log)


if __name__ == "__main__":
    print(coletar())
