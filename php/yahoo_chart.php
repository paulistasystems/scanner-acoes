<?php
/**
 * php/yahoo_chart.php — Egress confiável para o Yahoo Chart API v8.
 *
 * Este é o ÚNICO caminho de aquisição de candles do scanner, usado tanto local
 * (servido por `php -S` via php/run_php_server.sh) quanto em produção
 * (https://paulista.dev/scanner/yahoo_chart.php). O `data_layer._fetch_chart_direct`
 * aponta para esta URL via `SCANNER_CHART_URL`.
 *
 * Por que um proxy PHP e não yfinance direto: o yfinance faz um bootstrap
 * cookie/crumb (fc.yahoo.com → getcrumb) que, no IP do servidor paulista.dev,
 * recebe 401 "Invalid Crumb" e devolve vazio para todos os tickers —inclusive os
 * líquidos. O endpoint público /v8/finance/chart NÃO exige crumb: responde
 * 200+dados só com User-Agent de browser. Este proxy usa esse caminho direto.
 * Cobertura verificada: 214/214 símbolos do universo retornam DATA (probe).
 *
 * Repassa `symbol` + `interval` + (`period1`/`period2` | `range`) ao Yahoo e
 * devolve o corpo JSON cru, espelhando o HTTP code. A normalização
 * (auto-adjust, tz, índice) continua no `data_layer._fetch_chart_direct`, que
 * apenas troca a URL de origem (Yahoo direto → este proxy) — assim não há
 * duplicação da lógica de paridade com yfinance.
 *
 * Fallback de edge (PoP BR): o cluster do Yahoo que atende o IP deste servidor
 * (resolvido via DNS = PoPs dos EUA) pode servir candles com OHLCV null para
 * datas específicas — em 2026-08-15, 07-31 (188 símbolos) e 08-10 (100) estavam
 * null nesse cluster há 15/5 dias, enquanto as PoPs brasileiras
 * (edge.gycpi.b.yahoodns.net, 200.152.162.x) serviam a barra populada. Quando o
 * corpo primário contém closes null, refazemos a request com CURLOPT_RESOLVE
 * fixando uma PoP BR e servimos o corpo com menos nulls. Sem nulls (caso
 * normal) o fallback não roda — zero custo. IP sem resposta = pula para o
 * próximo; todos falharem = serve o primário (comportamento anterior).
 *
 * Uso:
 *   yahoo_chart.php?symbol=PETR4.SA&interval=1d&period1=...&period2=...
 *   yahoo_chart.php?symbol=PETR4.SA&interval=1h&range=6mo
 */

// PoPs BR do Yahoo (edge.gycpi.b.yahoodns.net, resolvidas de um IP residencial
// BR em 2026-08-15). Ordem: a .189 serviu TODAS as datas envenenadas no probe;
// as demais são redundância (algumas datas vieram null em .143/.137).
const EDGE_BR_PINS = ['200.152.162.189', '200.152.162.143', '200.152.162.137', '200.152.162.136'];

// GET no Yahoo; $pin fixa a PoP via CURLOPT_RESOLVE (mesmo SNI/Host, outro IP).
function curl_chart($url, $pin = null) {
    $ch = curl_init($url);
    $opts = [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_TIMEOUT        => 20,
        CURLOPT_CONNECTTIMEOUT => 10,
        CURLOPT_SSL_VERIFYPEER => true,
        CURLOPT_USERAGENT      => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                                . '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        CURLOPT_HTTPHEADER     => ['Accept: application/json,text/plain,*/*',
                                   'Accept-Language: en-US,en;q=0.9'],
    ];
    if ($pin) {
        $opts[CURLOPT_RESOLVE] = ['query1.finance.yahoo.com:443:' . $pin];
    }
    curl_setopt_array($ch, $opts);
    $body = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err  = curl_error($ch);
    curl_close($ch);
    return [$body, $code, $err];
}

// Nº de closes null no corpo (candle servido vazio pelo edge). -1 = não-JSON ou
// sem quote (fallback não sabe avaliar → não roda).
function null_close_count($body) {
    $j = json_decode((string)$body, true);
    $q = $j['chart']['result'][0]['indicators']['quote'][0]['close'] ?? null;
    if (!is_array($q)) {
        return -1;
    }
    $n = 0;
    foreach ($q as $c) {
        if ($c === null) {
            $n++;
        }
    }
    return $n;
}

header('Cache-Control: no-store');

$symbol = isset($_GET['symbol']) ? trim((string)$_GET['symbol']) : '';
if ($symbol === '') {
    http_response_code(400);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['chart' => ['error' => ['code' => 'Bad Request',
                                              'description' => 'missing symbol']]]);
    exit;
}

// Repassa apenas parâmetros que o Yahoo entende.
$fwd = [];
foreach (['interval', 'range', 'period1', 'period2', 'includePrePost', 'events'] as $k) {
    if (isset($_GET[$k]) && $_GET[$k] !== '') {
        $fwd[$k] = $_GET[$k];
    }
}

$url = 'https://query1.finance.yahoo.com/v8/finance/chart/' . rawurlencode($symbol);
if ($fwd) {
    $url .= '?' . http_build_query($fwd);
}

[$body, $http_code, $err] = curl_chart($url);

header('Content-Type: application/json; charset=utf-8');
if ($body === false || $err !== '') {
    http_response_code(502);
    echo json_encode(['chart' => ['error' => ['code' => 'BadGateway',
                                              'description' => $err ?: 'empty upstream']]]);
    exit;
}

$http_code = $http_code ?: 502;
$edge_used = 'default';

// Edge envenenado? Closes null no corpo 200 → re-busca pinned numa PoP BR e
// serve o primeiro corpo que reduza os nulls (ver header docblock).
if ($http_code === 200) {
    $nulls = null_close_count($body);
    if ($nulls > 0) {
        foreach (EDGE_BR_PINS as $pin) {
            [$pbody, $pcode, $perr] = curl_chart($url, $pin);
            if ($pbody === false || $perr !== '' || $pcode !== 200) {
                continue;
            }
            $pnulls = null_close_count($pbody);
            if ($pnulls >= 0 && $pnulls < $nulls) {
                $body      = $pbody;
                $nulls     = $pnulls;
                $edge_used = 'br:' . $pin;
                break; // primeiro que melhora serve — 200.152.162.189 cura quase tudo
            }
        }
    }
}

header('X-Scanner-Edge: ' . $edge_used);

// Pass-through do corpo do Yahoo (raw). O Python faz parse + normalização.
http_response_code($http_code);
echo $body;

