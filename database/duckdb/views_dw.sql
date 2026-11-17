-- =====================================================================
-- AgroSentinela - Data Warehouse (DuckDB) - modelo estrela
--
--                    dim_tempo
--                        |
--  dim_talhao --- fato_clima_talhao      (grão: talhão x dia, 30 dias + 7 de previsão)
--      |    \---- fato_operacoes         (grão: operação de campo - ERP)
--      |     \--- fato_pragas            (grão: observação do caderno de campo)
--
-- As tabelas são recriadas a cada execução do pipeline (app/etl/pipeline.py).
-- As views abaixo respondem às perguntas de negócio exibidas no painel.
-- =====================================================================

-- Situação atual (hoje) de cada talhão
CREATE OR REPLACE VIEW vw_status_atual AS
SELECT d.talhao_key, d.codigo, d.nome, d.cultura, d.propriedade, d.produtor, d.cidade, d.uf,
       d.area_ha, d.irrigado, d.latitude, d.longitude,
       f.temp_max, f.temp_min, f.chuva_consolidada, f.agua_disponivel_pct, f.armazenamento_mm,
       f.risco_geada, f.risco_doenca, f.janela_pulverizacao
FROM dim_talhao d
JOIN fato_clima_talhao f ON f.talhao_key = d.talhao_key
JOIN dim_tempo t         ON t.data_key   = f.data_key
WHERE t.data = current_date;

-- Resumo de 30 dias x previsão de 7 dias por talhão
CREATE OR REPLACE VIEW vw_resumo_talhao AS
SELECT d.talhao_key, d.codigo, d.nome, d.cultura, d.cidade,
       SUM(CASE WHEN NOT f.is_previsao THEN f.chuva_consolidada END)  AS chuva_30d,
       SUM(CASE WHEN NOT f.is_previsao THEN f.etc_mm END)             AS etc_30d,
       SUM(CASE WHEN NOT f.is_previsao THEN f.irrigacao_mm END)       AS irrigacao_30d,
       SUM(CASE WHEN f.is_previsao THEN f.chuva_consolidada END)      AS chuva_prev_7d,
       MIN(CASE WHEN f.is_previsao THEN f.temp_min END)               AS temp_min_prev_7d,
       SUM(CASE WHEN NOT f.is_previsao THEN f.graus_dia END)          AS graus_dia_30d,
       SUM(CASE WHEN f.is_previsao AND f.janela_pulverizacao THEN 1 ELSE 0 END) AS dias_pulverizacao_7d
FROM dim_talhao d
JOIN fato_clima_talhao f ON f.talhao_key = d.talhao_key
GROUP BY ALL;

-- Qualidade de dado / integração: pluviômetro da fazenda x estimativa da API
CREATE OR REPLACE VIEW vw_pluviometro_vs_api AS
SELECT d.codigo, d.nome, d.cidade,
       COUNT(*)                                   AS dias_comparados,
       ROUND(SUM(f.chuva_pluviometro), 1)         AS chuva_pluviometro,
       ROUND(SUM(f.chuva_api), 1)                 AS chuva_api,
       ROUND(100.0 * (SUM(f.chuva_pluviometro) - SUM(f.chuva_api)) / NULLIF(SUM(f.chuva_api), 0), 1) AS diferenca_pct
FROM dim_talhao d
JOIN fato_clima_talhao f ON f.talhao_key = d.talhao_key
WHERE f.chuva_pluviometro IS NOT NULL AND NOT f.is_previsao
GROUP BY ALL;

-- Custos das operações por hectare (ERP) nos últimos 90 dias
CREATE OR REPLACE VIEW vw_custo_hectare AS
SELECT d.codigo, d.nome, d.cultura, d.area_ha, o.tipo,
       ROUND(SUM(o.custo), 2)                 AS custo_total,
       ROUND(SUM(o.custo) / d.area_ha, 2)     AS custo_por_ha,
       COUNT(*)                               AS qtd_operacoes
FROM fato_operacoes o
JOIN dim_talhao d ON d.talhao_key = o.talhao_key
GROUP BY d.codigo, d.nome, d.cultura, d.area_ha, o.tipo;

-- Chuva acumulada por município (30 dias, dado consolidado)
CREATE OR REPLACE VIEW vw_chuva_municipio AS
SELECT d.cidade, d.uf,
       ROUND(AVG(s.chuva_30d), 1) AS chuva_media_30d,
       ROUND(AVG(s.etc_30d), 1)   AS etc_media_30d
FROM dim_talhao d
JOIN vw_resumo_talhao s ON s.talhao_key = d.talhao_key
GROUP BY ALL;

-- Ranking de pragas (caderno de campo) nos últimos 30 dias
CREATE OR REPLACE VIEW vw_ranking_pragas AS
SELECT p.praga, d.cultura,
       COUNT(*)                     AS ocorrencias,
       ROUND(AVG(p.nivel), 2)       AS nivel_medio,
       MAX(p.nivel)                 AS nivel_maximo,
       COUNT(DISTINCT p.talhao_key) AS talhoes_afetados
FROM fato_pragas p
JOIN dim_talhao d ON d.talhao_key = p.talhao_key
JOIN dim_tempo t  ON t.data_key   = p.data_key
WHERE t.data >= current_date - INTERVAL 30 DAY
GROUP BY ALL;
