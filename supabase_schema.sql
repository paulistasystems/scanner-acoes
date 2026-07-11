-- supabase_schema.sql — Schema para Gestão Dinâmica de Símbolos
-- Rodar UMA vez no SQL Editor do Supabase (Dashboard → SQL → New query).
-- Cria 3 tabelas (symbols, symbol_tests, symbol_status_log) + RLS.
--
-- Modelo de chaves:
--   - anon (publishable): leitura (RLS SELECT habilitado) — usado no path quente dos scans.
--   - service_role: escrita (bypassa RLS) — só no job/regras admin (botão in-app).
-- As barras OHLCV continuam no SQLite local (data_layer.py) — NÃO migram para cá.

-- =============================================================================
-- Tabela 1: catálogo de símbolos (fonte de verdade do universo)
-- =============================================================================
CREATE TABLE IF NOT EXISTS symbols (
    symbol          TEXT PRIMARY KEY,                 -- 'PETR4.SA' (ticker Yahoo vigente)
    name            TEXT NOT NULL,                    -- 'Petrobras'
    category        TEXT,                             -- 'Bancos', 'BDR Tech', 'ETF', ...
    asset_type      TEXT,                             -- 'Ação' | 'BDR' | 'ETF' | 'FII'
    liquidity_tier  TEXT DEFAULT 'universal',         -- 'blue_chip' | 'mid_small' | 'universal'
    status          TEXT NOT NULL DEFAULT 'listed',   -- 'listed' | 'watch' | 'delisted'
    prior_symbols   TEXT[] DEFAULT '{}',              -- tickers antigos (ex.: CPLE6 antes de CPLE3)
    listed_at       TIMESTAMPTZ,
    delisted_at     TIMESTAMPTZ,
    delist_reason   TEXT,
    notes           TEXT
);

-- =============================================================================
-- Tabela 2: resultado de cada teste de download (auditoria + base das regras)
-- =============================================================================
CREATE TABLE IF NOT EXISTS symbol_tests (
    id            BIGSERIAL PRIMARY KEY,
    symbol        TEXT NOT NULL REFERENCES symbols(symbol),
    tested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    interval      TEXT NOT NULL,                      -- '1d' | '1h' | '30m' | '15m'
    bars          INTEGER,                            -- qtd de candles retornados
    ok            BOOLEAN NOT NULL,                   -- True se veio dado usável
    error         TEXT,                               -- ex.: 'empty/truncated response'
    delist_signal BOOLEAN DEFAULT FALSE               -- sinal forte do probe HTTP do Yahoo
);
CREATE INDEX IF NOT EXISTS idx_tests_sym_time ON symbol_tests(symbol, tested_at DESC);

-- =============================================================================
-- Tabela 3: trilha de auditoria das transições de status
-- =============================================================================
CREATE TABLE IF NOT EXISTS symbol_status_log (
    id          BIGSERIAL PRIMARY KEY,
    symbol      TEXT NOT NULL REFERENCES symbols(symbol),
    from_status TEXT,
    to_status   TEXT NOT NULL,
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason      TEXT,                                 -- 'auto: 5 falhas consecutivas' | 'manual' | 'seed'
    source      TEXT                                  -- 'rule-engine' | 'ui' | 'seed'
);

-- =============================================================================
-- RLS — anon lê tudo (metadata pública); só service_role escreve (bypassa RLS)
-- =============================================================================
ALTER TABLE symbols           ENABLE ROW LEVEL SECURITY;
ALTER TABLE symbol_tests      ENABLE ROW LEVEL SECURITY;
ALTER TABLE symbol_status_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read_symbols" ON symbols           FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read_tests"   ON symbol_tests      FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read_log"     ON symbol_status_log FOR SELECT TO anon USING (true);
-- Nenhuma policy de INSERT/UPDATE para anon → painel e path de leitura são só leitura;
-- escritas (seed, job de teste, motor de regras) rodam com service_role.
