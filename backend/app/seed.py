"""Cria as estruturas e popula os dados de demonstração.

    python -m app.seed

1. MySQL  : executa database/mysql/01_schema.sql e insere culturas, produtores,
            propriedades e talhões reais da região da Média Mogiana (SP/MG),
            além de 90 dias de operações de campo.
2. SQLite : cria o "caderno de campo" offline (leituras de pluviômetro e
            observações de pragas) COM PROBLEMAS DE QUALIDADE propositais
            (datas em formatos diferentes, vírgula decimal, códigos com espaços,
            duplicidades, valores inválidos) que serão tratados pelo ETL.

Para que o pluviômetro tenha valores realistas, o seed consulta a API
Open-Meteo e aplica uma variação local (medição real x estimativa).
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from sqlalchemy import text

from app import config
from app.db import conexoes
from app.services import apis_externas

random.seed(2026)
HOJE = date.today()

CULTURAS = [
    # nome, kc, temp_base, temp_geada, cad, doença, tmin, tmax, umid
    ("CAFÉ ARÁBICA", 1.05, 10, 3.0, 100, "Ferrugem do cafeeiro", 21, 25, 82),
    ("BATATA", 1.10, 7, 2.0, 50, "Requeima", 12, 22, 85),
    ("MILHO", 1.15, 10, 1.0, 70, "Cercosporiose", 22, 30, 85),
    ("LARANJA", 0.70, 13, 0.0, 120, "Mancha preta dos citros", 20, 30, 85),
    ("CANA-DE-AÇÚCAR", 1.10, 10, 0.0, 90, "Ferrugem alaranjada", 20, 28, 88),
]

PRODUTORES = [
    ("Antônio Ribeiro", "(19) 99812-3344", "antonio.ribeiro@exemplo.com"),
    ("Marina Costa", "(19) 99701-2201", "marina.costa@exemplo.com"),
    ("José Carlos Moreira", "(19) 99655-8710", "jc.moreira@exemplo.com"),
    ("Luciana Ferreira", "(19) 99544-1029", "luciana.ferreira@exemplo.com"),
    ("Bento Agro Ltda.", "(19) 3656-2000", "contato@bentoagro.exemplo.com"),
    ("Paulo Henrique Souza", "(35) 99877-6650", "paulo.souza@exemplo.com"),
]

# produtor, nome, cep, logradouro, bairro, cidade, uf, ibge, lat, lon
PROPRIEDADES = [
    (1, "Sítio Boa Vista", "13870-000", "Estrada Municipal SJB-040, km 6", "Zona Rural",
     "São João da Boa Vista", "SP", "3549102", -21.9690, -46.7980),
    (2, "Fazenda Santa Clara", "13880-000", "Rodovia SP-215, km 12", "Zona Rural",
     "Vargem Grande do Sul", "SP", "3556404", -21.8320, -46.8940),
    (3, "Fazenda Pinhalense", "13990-000", "Estrada do Pinhal, km 4", "Zona Rural",
     "Espírito Santo do Pinhal", "SP", "3515186", -22.1910, -46.7480),
    (4, "Sítio Alto da Serra", "13770-000", "Estrada da Serra, km 9", "Zona Rural",
     "Caconde", "SP", "3508603", -21.5290, -46.6440),
    (5, "Fazenda São Benedito", "13730-000", "Rodovia SP-340, km 270", "Zona Rural",
     "Mococa", "SP", "3530508", -21.4680, -47.0050),
    (6, "Sítio Vale do Sol", "37795-000", "Estrada Andradas-Ibitiúra, km 3", "Zona Rural",
     "Andradas", "MG", "3102605", -22.0680, -46.5690),
]

# propriedade, codigo, nome, cultura, area, dias desde plantio, irrigado, dlat, dlon, tem pluviômetro
TALHOES = [
    (1, "SJB-01", "Café Catuaí - Baixada", "CAFÉ ARÁBICA", 12.0, 2900, True, 0.004, -0.003, True),
    (1, "SJB-02", "Café Mundo Novo - Encosta", "CAFÉ ARÁBICA", 8.5, 4200, False, -0.003, 0.004, False),
    (2, "VGS-01", "Batata Ágata - Pivô 1", "BATATA", 25.0, 55, True, 0.005, 0.002, True),
    (2, "VGS-02", "Milho Safra", "MILHO", 30.0, 40, False, -0.004, -0.005, True),
    (3, "ESP-01", "Café Arara - Gotejo", "CAFÉ ARÁBICA", 18.0, 1800, True, 0.003, 0.003, True),
    (3, "ESP-02", "Laranja Pera", "LARANJA", 10.0, 3100, False, -0.004, 0.002, False),
    (4, "CAC-01", "Café Bourbon Amarelo", "CAFÉ ARÁBICA", 6.0, 5100, False, 0.002, -0.002, True),
    (5, "MOC-01", "Cana Soca 3º corte", "CANA-DE-AÇÚCAR", 80.0, 900, False, 0.006, 0.004, True),
    (5, "MOC-02", "Café Catuaí Vermelho", "CAFÉ ARÁBICA", 15.0, 2400, True, -0.005, -0.003, False),
    (6, "AND-01", "Café Topázio", "CAFÉ ARÁBICA", 9.0, 3300, False, 0.003, 0.004, True),
    (6, "AND-02", "Batata Asterix", "BATATA", 7.0, 70, True, -0.003, -0.004, True),
    (6, "AND-03", "Milho Silagem", "MILHO", 12.0, 35, False, 0.004, -0.004, False),
]

PRAGAS_POR_CULTURA = {
    "CAFÉ ARÁBICA": ["Bicho-mineiro", "bicho mineiro", "BICHO-MINEIRO ", "Broca-do-café", "broca do cafe", "Ácaro vermelho"],
    "BATATA": ["Mosca-branca", "mosca branca", "Traça da batata", "traca-da-batata", "Vaquinha"],
    "MILHO": ["Lagarta-do-cartucho", "lagarta do cartucho", "LAGARTA-DO-CARTUCHO", "Cigarrinha-do-milho"],
    "LARANJA": ["Psilídeo", "psilideo", "Ácaro da leprose", "acaro-da-leprose"],
    "CANA-DE-AÇÚCAR": ["Broca-da-cana", "broca da cana", "Cigarrinha-das-raízes"],
}

TECNICOS = ["Rafael (técnico)", "Bruna (agrônoma)", "Diego (técnico)"]


def _executar_script_sql(caminho):
    sql = caminho.read_text(encoding="utf-8")
    eng = conexoes.mysql_sem_banco()
    with eng.begin() as con:
        for cmd in sql.split(";"):
            linhas = [ln for ln in cmd.splitlines() if not ln.strip().startswith("--")]
            cmd_limpo = "\n".join(linhas).strip()
            if cmd_limpo:
                con.execute(text(cmd_limpo))
    eng.dispose()


def chuva_api_por_propriedade() -> dict[int, dict[date, float]]:
    """Chuva diária dos últimos 30 dias por propriedade (1 chamada à Open-Meteo),
    usada para gerar leituras de pluviômetro realistas."""
    try:
        respostas = apis_externas.previsao_diaria_lote([(p[8], p[9]) for p in PROPRIEDADES])
        resultado = {}
        for i, resp in enumerate(respostas):
            d = resp["daily"]
            resultado[i + 1] = {date.fromisoformat(dia): (c or 0.0)
                                for dia, c in zip(d["time"], d["precipitation_sum"])
                                if date.fromisoformat(dia) <= HOJE}
        return resultado
    except apis_externas.ErroApiExterna as e:
        print(f"   ! {e} - usando chuva simulada para o pluviômetro")
        return {i + 1: {HOJE - timedelta(days=k): max(0.0, random.gauss(4, 8)) for k in range(30)}
                for i in range(len(PROPRIEDADES))}


def popular_mysql() -> dict:
    print("[MySQL] criando estrutura...")
    _executar_script_sql(config.RAIZ / "database" / "mysql" / "01_schema.sql")
    eng = conexoes.mysql()
    with eng.begin() as con:
        con.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for t in ["clima_diario", "operacoes", "talhoes", "propriedades", "produtores", "culturas"]:
            con.execute(text(f"TRUNCATE TABLE {t}"))
        con.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

        for c in CULTURAS:
            con.execute(text("""INSERT INTO culturas (nome,kc,temp_base,temp_geada,cad_mm,doenca,doenca_tmin,doenca_tmax,doenca_umid)
                                VALUES (:n,:kc,:tb,:tg,:cad,:d,:dmin,:dmax,:du)"""),
                        dict(n=c[0], kc=c[1], tb=c[2], tg=c[3], cad=c[4], d=c[5], dmin=c[6], dmax=c[7], du=c[8]))
        culturas = {r.nome: r.id for r in con.execute(text("SELECT id, nome FROM culturas"))}

        for p in PRODUTORES:
            con.execute(text("INSERT INTO produtores (nome, telefone, email) VALUES (:n,:t,:e)"),
                        dict(n=p[0], t=p[1], e=p[2]))
        for p in PROPRIEDADES:
            con.execute(text("""INSERT INTO propriedades (produtor_id,nome,cep,logradouro,bairro,cidade,uf,ibge,latitude,longitude)
                                VALUES (:pr,:n,:cep,:lg,:b,:c,:uf,:ibge,:lat,:lon)"""),
                        dict(pr=p[0], n=p[1], cep=p[2], lg=p[3], b=p[4], c=p[5], uf=p[6], ibge=p[7], lat=p[8], lon=p[9]))

        for t in TALHOES:
            prop = PROPRIEDADES[t[0] - 1]
            con.execute(text("""INSERT INTO talhoes (propriedade_id,codigo,nome,cultura_id,area_ha,data_plantio,irrigado,latitude,longitude)
                                VALUES (:p,:c,:n,:cu,:a,:dp,:i,:lat,:lon)"""),
                        dict(p=t[0], c=t[1], n=t[2], cu=culturas[t[3]], a=t[4], dp=HOJE - timedelta(days=t[5]),
                             i=t[6], lat=round(prop[8] + t[7], 6), lon=round(prop[9] + t[8], 6)))
        ids = {r.codigo: r.id for r in con.execute(text("SELECT id, codigo FROM talhoes"))}

    print("[API] consultando chuva recente na Open-Meteo para cada propriedade...")
    chuva_prop = chuva_api_por_propriedade()

    print("[MySQL] gerando 90 dias de operações de campo...")
    operacoes = []
    for t in TALHOES:
        tid, area, cultura, irrigado = ids[t[1]], t[4], t[3], t[6]
        chuva = chuva_prop[t[0]]
        dias_chuvosos = sorted((d for d, mm in chuva.items() if mm >= 12), key=lambda d: -chuva[d])[:2]
        if t[5] <= 90:
            operacoes.append((tid, HOJE - timedelta(days=t[5]), "PLANTIO", f"Plantio {cultura.lower()}", area, "ha", area * 1450))
        for d in range(90, 0, -1):
            dia = HOJE - timedelta(days=d)
            if d % 30 == 7:
                operacoes.append((tid, dia, "ADUBACAO", "Adubação de cobertura NPK 20-05-20", 300, "kg/ha", area * 420))
            if d % 21 == 3:
                operacoes.append((tid, dia, "PULVERIZACAO", "Aplicação preventiva", 200, "L/ha", area * 180))
            if irrigado:
                if dia in chuva:
                    seco = chuva[dia] < 2
                    # Irriga em dias secos a cada ~3 dias; nos 2 dias mais chuvosos do mês o
                    # operador irrigou "por rotina" (desperdício que o sistema vai apontar).
                    if (seco and d % 3 == 0) or dia in dias_chuvosos:
                        mm = 12.0
                        operacoes.append((tid, dia, "IRRIGACAO", "Irrigação programada", mm, "mm", round(mm * area * 4.5, 2)))
                elif d % 4 == 0:
                    operacoes.append((tid, dia, "IRRIGACAO", "Irrigação programada", 12.0, "mm", round(12 * area * 4.5, 2)))
    with eng.begin() as con:
        con.execute(text("""INSERT INTO operacoes (talhao_id,data,tipo,descricao,quantidade,unidade,custo)
                            VALUES (:t,:d,:tp,:ds,:q,:u,:c)"""),
                    [dict(t=o[0], d=o[1], tp=o[2], ds=o[3], q=o[4], u=o[5], c=o[6]) for o in operacoes])
    print(f"        {len(operacoes)} operações inseridas")
    return {"ids": ids, "chuva": chuva_prop}


def _formatar_data_baguncada(d: date) -> str:
    return random.choice([d.isoformat(), d.strftime("%d/%m/%Y"), d.strftime("%d-%m-%Y")])


def _codigo_baguncado(cod: str) -> str:
    return random.choice([cod, cod, cod.lower(), f" {cod} ", cod.replace("-", ""), cod + " "])


def popular_sqlite(chuva_prop: dict):
    print("[SQLite] criando caderno de campo offline...")
    if config.SQLITE_PATH.exists():
        config.SQLITE_PATH.unlink()
    con = conexoes.sqlite()
    con.executescript("""
        CREATE TABLE leituras_pluviometro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            talhao TEXT,
            data_leitura TEXT,
            milimetros TEXT,
            tecnico TEXT,
            sincronizado_em TEXT
        );
        CREATE TABLE observacoes_campo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            talhao TEXT,
            data_obs TEXT,
            praga TEXT,
            nivel INTEGER,
            observacao TEXT,
            tecnico TEXT
        );
    """)
    leituras, observacoes = [], []
    for t in TALHOES:
        cod, cultura = t[1], t[3]
        if t[9]:  # talhão com pluviômetro
            for dia, mm_api in sorted(chuva_prop[t[0]].items()):
                if random.random() < 0.2:      # técnico não leu nesse dia
                    continue
                mm = max(0.0, mm_api * random.uniform(0.7, 1.35) + (random.uniform(0, 3) if mm_api > 1 else 0))
                if random.random() < 0.03:
                    txt = random.choice(["-5", "999", "", "n/a"])   # erros de digitação
                else:
                    txt = f"{mm:.1f}".replace(".", random.choice([",", "."]))
                reg = (_codigo_baguncado(cod), _formatar_data_baguncada(dia), txt, random.choice(TECNICOS),
                       (dia + timedelta(days=random.randint(0, 2))).isoformat())
                leituras.append(reg)
                if random.random() < 0.08:          # sincronização duplicada
                    leituras.append(reg)
        # Observações de pragas: a cada ~5 dias, com tendência de aumento recente
        pragas = PRAGAS_POR_CULTURA[cultura]
        base = random.choice(pragas)
        for d in range(45, -1, -5):
            dia = HOJE - timedelta(days=d)
            nivel = min(5, max(0, int(round(random.gauss(1.5 + (45 - d) / 18 * (1 if t[1] in ("SJB-02", "VGS-02", "ESP-01", "AND-02") else 0.2), 0.8)))))
            if random.random() < 0.04:
                nivel = random.choice([None, 7, -1])
            praga = base if random.random() < 0.7 else random.choice(pragas)
            observacoes.append((_codigo_baguncado(cod), _formatar_data_baguncada(dia), praga, nivel,
                                random.choice(["Amostragem em 20 plantas", "Vistoria de rotina", "Armadilha verificada", ""]),
                                random.choice(TECNICOS)))
    # registros de talhão inexistente (serão rejeitados e registrados no log)
    leituras.append(("XYZ-99", HOJE.isoformat(), "10", "Diego (técnico)", HOJE.isoformat()))
    observacoes.append(("TESTE", HOJE.isoformat(), "Teste app", 2, "registro de teste", "Diego (técnico)"))

    con.executemany("INSERT INTO leituras_pluviometro (talhao,data_leitura,milimetros,tecnico,sincronizado_em) VALUES (?,?,?,?,?)", leituras)
    con.executemany("INSERT INTO observacoes_campo (talhao,data_obs,praga,nivel,observacao,tecnico) VALUES (?,?,?,?,?,?)", observacoes)
    con.commit()
    con.close()
    print(f"        {len(leituras)} leituras de pluviômetro e {len(observacoes)} observações de pragas")


def main():
    print("=" * 60)
    print("AgroSentinela - carga de dados de demonstração")
    print("=" * 60)
    r = popular_mysql()
    popular_sqlite(r["chuva"])
    print("\nConcluído! Próximo passo: executar a integração")
    print("   python -m app.etl.pipeline        (ou pelo botão na tela 'Integração')")


if __name__ == "__main__":
    main()
