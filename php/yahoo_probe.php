<?php
/**
 * php/yahoo_probe.php — Diagnóstico de cobertura do Yahoo Chart API v8 a partir
 * do servidor (paulista.dev).
 *
 * Lê `php/symbols.json` (universo autoritativo do scanner, gerado por
 * `php/gen_symbols.py` a partir de `symbols_fallback.ATIVOS_B3_AMPLIADO`) e testa
 * um slice de cada vez, classificando cada símbolo:
 *
 *   DATA    — Yahoo devolveu candles            (símbolo ativo, econômico)
 *   NO_DATA — Yahoo devolveu erro explícito      (Not Found / "may be delisted")
 *   EMPTY   — HTTP 200 mas sem `result`          (sinal de throttle/block, NÃO delisting)
 *   ERROR   — falha de rede/curl/corpo não-JSON
 *
 * Por que isto existe: o yfinance faz um bootstrap cookie/crumb (fc.yahoo.com →
 * getcrumb) que neste IP do servidor recebe 401 "Invalid Crumb" → json.loads("")
 * → "No price data found, symbol may be delisted" para TODOS os tickers, até os
 * líquidos. O endpoint público /v8/finance/chart NÃO exige crumb — responde
 * 200+dados só com User-Agent de browser. Este probe usa esse caminho direto,
 * igual ao `_fetch_chart_direct` do `data_layer.py` (e ao futuro
 * `php/yahoo_chart.php`), para separar delisting real do throttle.
 *
 * Paginado (?offset=&limit=) para respeitar o max_execution_time do PHP. Rode
 * todas as páginas até `more=false`.
 *
 * Uso:
 *   yahoo_probe.php?offset=0&limit=30&interval=1d&range=1y
 *   yahoo_probe.php?symbols=MTRE3.SA,PLPL3.SA,BTLG11.SA   (override ad-hoc)
 */

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

$UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    . '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

// ---- universo ---------------------------------------------------------------
$override = isset($_GET['symbols']) ? trim((string)$_GET['symbols']) : '';
if ($override !== '') {
    $all = array_values(array_filter(array_map('trim', explode(',', $override))));
    $total = count($all);
    $offset = 0;
    $limit  = $total;
} else {
    $symbolsFile = __DIR__ . '/symbols.json';
    if (!is_file($symbolsFile)) {
        http_response_code(500);
        echo json_encode(['error' => 'symbols.json nao encontrado', 'path' => $symbolsFile]);
        exit;
    }
    $all = json_decode(file_get_contents($symbolsFile), true);
    if (!is_array($all)) {
        http_response_code(500);
        echo json_encode(['error' => 'symbols.json invalido']);
        exit;
    }
    $total  = count($all);
    $offset = max(0, (int)($_GET['offset'] ?? 0));
    $limit  = min(60, max(1, (int)($_GET['limit'] ?? 30)));
}

$interval = $_GET['interval'] ?? '1d';
$range    = $_GET['range']    ?? '1y';
$slice    = array_slice($all, $offset, $limit);

$out = [];
$counts = ['DATA' => 0, 'NO_DATA' => 0, 'EMPTY' => 0, 'ERROR' => 0];
$start = microtime(true);

foreach ($slice as $sym) {
    $url = 'https://query1.finance.yahoo.com/v8/finance/chart/' . rawurlencode($sym)
         . '?range=' . urlencode($range) . '&interval=' . urlencode($interval);

    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_TIMEOUT        => 15,
        CURLOPT_CONNECTTIMEOUT => 8,
        CURLOPT_SSL_VERIFYPEER => true,
        CURLOPT_USERAGENT      => $UA,
        CURLOPT_HTTPHEADER     => ['Accept: application/json,text/plain,*/*',
                                   'Accept-Language: en-US,en;q=0.9'],
    ]);
    $body = curl_exec($ch);
    $info = curl_getinfo($ch);
    $err  = curl_error($ch);
    curl_close($ch);

    $rec = ['symbol' => $sym, 'http' => (int)$info['http_code']];

    if ($body === false && $err !== '') {
        $rec['status'] = 'ERROR';
        $rec['curl_error'] = $err;
    } else {
        $json = json_decode($body, true);
        $chart = is_array($json) ? ($json['chart'] ?? null) : null;
        if (!is_array($chart)) {
            $rec['status'] = 'ERROR';
            $rec['body_head'] = substr((string)$body, 0, 160);
        } else {
            $result = $chart['result'][0] ?? null;
            $error  = $chart['error'] ?? null;
            if (is_array($result)) {
                $meta = $result['meta'] ?? [];
                $ts   = $result['timestamp'] ?? [];
                $rec['status']   = 'DATA';
                $rec['bars']     = count($ts);
                $rec['exchange'] = $meta['exchangeName'] ?? null;
                $rec['currency'] = $meta['currency'] ?? null;
                $rec['price']    = $meta['regularMarketPrice'] ?? null;
                if ($ts) {
                    $rec['first'] = gmdate('Y-m-d', $ts[0]);
                    $rec['last']  = gmdate('Y-m-d', $ts[count($ts) - 1]);
                }
            } elseif (is_array($error)) {
                $rec['status']   = 'NO_DATA';
                $rec['err_code'] = $error['code'] ?? null;
                $rec['err_desc'] = $error['description'] ?? null;
            } else {
                $rec['status'] = 'EMPTY';
            }
        }
    }

    $counts[$rec['status']] = ($counts[$rec['status']] ?? 0) + 1;
    $out[] = $rec;
    usleep(120000); // 0.12s entre chamadas — cortesia ao Yahoo, evita throttle
}

$next = ($offset + count($slice)) < $total ? $offset + count($slice) : null;
echo json_encode([
    'server_ip'     => $_SERVER['SERVER_ADDR'] ?? null,
    'interval'      => $interval,
    'range'         => $range,
    'total_symbols' => $total,
    'offset'        => $offset,
    'limit'         => $limit,
    'probed'        => count($slice),
    'more'          => $next !== null,
    'next_offset'   => $next,
    'elapsed_s'     => round(microtime(true) - $start, 2),
    'summary'       => $counts,
    'results'       => $out,
], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
