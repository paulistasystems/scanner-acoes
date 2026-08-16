---
name: yahoo-edge-poisoning-br-pins
description: Yahoo pode servir candles null por região/IP; o proxy tem fallback pinned em PoPs BR — diagnóstico e renovação dos pins
metadata:
  type: project
---

Incidente 2026-08-15: o cluster do Yahoo que atende o IP do servidor paulista.dev
(PoPs EUA via DNS) servia candles 1d com OHLCV **null** para datas inteiras
(07-31: 188 símbolos; 08-10: 100) por 15/5 dias, enquanto as PoPs brasileiras
serviam a barra populada. Sintoma no app: `bar_failures` congelado (288 pend,
attempts ~80 sem resolver), `✅ pronto` no status (fill_state completo não
depende disso).

**Why:** as duas rotas do `_fetch_one_daily_bar` saem do mesmo IP → mesmo
cluster envenenado. E o fallback precisa viver no proxy
(`php/yahoo_chart.php`), não no retry: `_trim_bars_to_window` deletaria como
órfã qualquer barra backfillada se a fetch principal continuar recebendo null
(parse descarta a linha all-NaN).

**How to apply:**
- Diagnosticar: `curl -sI 'https://paulista.dev/scanner/yahoo_chart.php?symbol=X&interval=1d&period1=..&period2=..'`
  — o header `X-Scanner-Edge` mostra `default` (edge do IP) ou `br:<ip>` (fallback usado).
  Se `bar_failures` congela em datas específicas com attempts subindo, suspeite disto.
- Renovar pins: os IPs estão em `EDGE_BR_PINS` no proxy (edge.gycpi.b.yahoodns.net).
  Se expirarem, resolver de um IP BR (`dig +short query1.finance.yahoo.com`) e
  atualizar a lista. Em 2026-08-15, `200.152.162.189` servia TODAS as datas
  envenenadas; `.143`/`.137` falhavam para alguns símbolos (testar antes de ordenar).
- Fila grande drena a 20/ciclo de warm (`_retry_bar_failures`); em fim de semana
  com fill completo, o prewarm pula as fetches principais — só o retry drena
  (POST /api/warm encadeados, um a cada ~90s, até zerar).
