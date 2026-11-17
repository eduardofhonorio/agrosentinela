-- =====================================================================
-- AgroSentinela - Banco transacional (MySQL)
-- Representa o "ERP agrícola" da cooperativa / consultoria:
-- cadastro de produtores, propriedades, talhões, culturas e operações.
-- A tabela clima_diario é a área de staging alimentada pelo Apache Hop
-- (pipeline hop/pipelines/coleta_clima.hpl) com dados da API Open-Meteo.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS agrosentinela
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE agrosentinela;

-- ---------------------------------------------------------------------
-- Culturas e seus parâmetros agronômicos (usados nas regras de alerta)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS culturas (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    nome             VARCHAR(60)  NOT NULL UNIQUE,
    kc               DECIMAL(4,2) NOT NULL COMMENT 'Coeficiente de cultura (ETc = ET0 x Kc)',
    temp_base        DECIMAL(4,1) NOT NULL COMMENT 'Temperatura base para graus-dia',
    temp_geada       DECIMAL(4,1) NOT NULL COMMENT 'Temperatura mínima do ar que indica risco de geada para a cultura',
    cad_mm           DECIMAL(5,1) NOT NULL COMMENT 'Capacidade de água disponível no solo (mm)',
    doenca           VARCHAR(80)  NOT NULL COMMENT 'Principal doença favorecida pelo clima',
    doenca_tmin      DECIMAL(4,1) NOT NULL,
    doenca_tmax      DECIMAL(4,1) NOT NULL,
    doenca_umid      DECIMAL(4,1) NOT NULL COMMENT 'Umidade relativa média mínima (%) que favorece a doença'
);

CREATE TABLE IF NOT EXISTS produtores (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    nome       VARCHAR(120) NOT NULL,
    telefone   VARCHAR(20),
    email      VARCHAR(120),
    criado_em  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS propriedades (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    produtor_id  INT NOT NULL,
    nome         VARCHAR(120) NOT NULL,
    cep          VARCHAR(9),
    logradouro   VARCHAR(200),
    bairro       VARCHAR(100),
    cidade       VARCHAR(100) NOT NULL,
    uf           CHAR(2) NOT NULL,
    ibge         VARCHAR(7)   COMMENT 'Código IBGE do município (via ViaCEP)',
    latitude     DECIMAL(9,6) NOT NULL,
    longitude    DECIMAL(9,6) NOT NULL,
    criado_em    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_prop_produtor FOREIGN KEY (produtor_id) REFERENCES produtores(id)
);

CREATE TABLE IF NOT EXISTS talhoes (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    propriedade_id  INT NOT NULL,
    codigo          VARCHAR(12) NOT NULL UNIQUE COMMENT 'Código usado no caderno de campo (ex.: SJB-01)',
    nome            VARCHAR(80) NOT NULL,
    cultura_id      INT NOT NULL,
    area_ha         DECIMAL(8,2) NOT NULL,
    data_plantio    DATE,
    irrigado        BOOLEAN NOT NULL DEFAULT FALSE,
    latitude        DECIMAL(9,6) NOT NULL,
    longitude       DECIMAL(9,6) NOT NULL,
    ativo           BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_talhao_prop    FOREIGN KEY (propriedade_id) REFERENCES propriedades(id),
    CONSTRAINT fk_talhao_cultura FOREIGN KEY (cultura_id)     REFERENCES culturas(id)
);

-- ---------------------------------------------------------------------
-- Operações de campo lançadas no escritório
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operacoes (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    talhao_id   INT NOT NULL,
    data        DATE NOT NULL,
    tipo        ENUM('IRRIGACAO','PULVERIZACAO','ADUBACAO','COLHEITA','PLANTIO') NOT NULL,
    descricao   VARCHAR(200),
    quantidade  DECIMAL(10,2) COMMENT 'mm (irrigação), L/ha (pulverização), kg/ha (adubação), sacas (colheita)',
    unidade     VARCHAR(10),
    custo       DECIMAL(12,2) NOT NULL DEFAULT 0,
    CONSTRAINT fk_oper_talhao FOREIGN KEY (talhao_id) REFERENCES talhoes(id),
    INDEX idx_oper_talhao_data (talhao_id, data)
);

-- ---------------------------------------------------------------------
-- STAGING: clima diário por talhão (carregado pelo Apache Hop)
-- 30 dias de histórico + 7 dias de previsão da API Open-Meteo
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clima_diario (
    talhao_id      INT  NOT NULL,
    data           DATE NOT NULL,
    temp_max       DECIMAL(5,2),
    temp_min       DECIMAL(5,2),
    chuva_mm       DECIMAL(6,2),
    et0_mm         DECIMAL(5,2),
    vento_max_kmh  DECIMAL(5,2),
    umidade_media  DECIMAL(5,2),
    prob_chuva     DECIMAL(5,2),
    fonte          VARCHAR(20) NOT NULL DEFAULT 'open-meteo',
    carregado_por  VARCHAR(20) NOT NULL DEFAULT 'apache-hop',
    atualizado_em  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (talhao_id, data),
    CONSTRAINT fk_clima_talhao FOREIGN KEY (talhao_id) REFERENCES talhoes(id)
);

-- ---------------------------------------------------------------------
-- View usada pelo Apache Hop (Table Input) para montar as chamadas à API
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_talhoes_coordenadas AS
SELECT t.id AS talhao_id,
       t.codigo,
       t.latitude,
       t.longitude
FROM talhoes t
WHERE t.ativo = TRUE;
