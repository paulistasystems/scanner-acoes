<?php
/**
 * php/yahoo_chart.php — Egress confiável para o Yahoo Chart API v8.
 *
 * Este é o ÚNICO caminho de aquisição de candles do scanner, usado tanto local
 * (servido por `php -S` via php/run_php_server.sh) quanto em produção
 * (https://paulista.dev/yahoo_chart.php). O `data_layer._fetch_chart_direct`
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
 * Uso:
 *   yahoo_chart.php?symbol=PETR4.SA&interval=1d&period1=...&period2=...
 *   yahoo_chart.php?symbol=PETR4.SA&interval=1h&range=6mo
 */

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

$ch = curl_init($url);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_FOLLOWLOCATION => true,
    CURLOPT_TIMEOUT        => 20,
    CURLOPT_CONNECTTIMEOUT => 10,
    CURLOPT_SSL_VERIFYPEER => true,
    CURLOPT_USERAGENT      => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                            . '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    CURLOPT_HTTPHEADER     => ['Accept: application/json,text/plain,*/*',
                               'Accept-Language: en-US,en;q=0.9'],
]);
$body = curl_exec($ch);
$info = curl_getinfo($ch);
$err  = curl_error($ch);
curl_close($ch);

header('Content-Type: application/json; charset=utf-8');
if ($body === false || $err !== '') {
    http_response_code(502);
    echo json_encode(['chart' => ['error' => ['code' => 'BadGateway',
                                              'description' => $err ?: 'empty upstream']]]);
    exit;
}

// Pass-through do corpo do Yahoo (raw). O Python faz parse + normalização.
http_response_code((int)$info['http_code'] ?: 502);
echo $body;
