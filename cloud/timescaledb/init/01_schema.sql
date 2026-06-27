-- ============================================================
-- Esquema de telemetria do robô (TimescaleDB)
-- ------------------------------------------------------------
-- Executado AUTOMATICAMENTE pelo entrypoint da imagem na PRIMEIRA
-- inicialização do banco (quando o volume de dados está vazio).
-- Para reaplicar, derrube o volume: `docker compose down -v`.
-- ============================================================

-- A extensão TimescaleDB já vem na imagem timescale/timescaledb; só ativamos.
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Uma tabela única e genérica guarda TODA a telemetria. O payload fica em
-- JSONB, então cada grupo (GPS, motores, bateria...) evolui o seu formato
-- sem exigir migração de schema. O campo "tipo" (último segmento do tópico
-- robo/telemetria/<tipo>) permite filtrar/particionar por domínio.
CREATE TABLE IF NOT EXISTS telemetria (
    ts      TIMESTAMPTZ NOT NULL,
    tipo    TEXT        NOT NULL,
    topico  TEXT        NOT NULL,
    payload JSONB       NOT NULL
);

-- Transforma em hypertable: o Timescale particiona por tempo de forma
-- transparente, o que mantém inserções e consultas por período rápidas
-- mesmo com milhões de linhas.
SELECT create_hypertable('telemetria', 'ts', if_not_exists => TRUE);

-- Consulta típica: "últimas posições do GPS" -> filtra por tipo, ordena por
-- tempo decrescente. Este índice serve exatamente esse padrão.
CREATE INDEX IF NOT EXISTS telemetria_tipo_ts_idx
    ON telemetria (tipo, ts DESC);

-- Retenção opcional: descarta automaticamente dados com mais de 90 dias.
-- Descomente se quiser limitar o crescimento do banco.
-- SELECT add_retention_policy('telemetria', INTERVAL '90 days');
