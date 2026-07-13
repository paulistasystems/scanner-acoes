<?php
/**
 * php/yahoo_bulk.php — Devolve TODOS os símbolos × timeframes como um único JSON
 * para consumo por sistema externo. Egress direto ao Yahoo Chart API v8 (browser
 * UA, sem cookie/crumb) — mesmo caminho comprovado pelo yahoo_probe.php (214/214).
 *
 * Por que NÃO buscar tudo numa única request sequencial: 214 símbolos × 4 TFs =
 * 864 séries; sequencial demora ~10 min e estoura o max_execution_time do PHP
 * (~30–120s) no DirectAdmin. Este endpoint usa:
 *   1. curl_multi — até $CONC chamadas ao Yahoo em paralelo;
 *   2. paginação por lote de símbolos (?offset=&limit=) — cada request completa
 *      em poucos segundos; o consumidor percorre as páginas via next_offset.
 *
 * Ranges por intervalo respeitam o limite intradiário do Yahoo (30m/15m ≤ 60d):
 *   1d=1y  1h=6mo  30m=1mo  15m=5d
 *
 * Shape do JSON:
 *   {
 *     "generated_at": "...", "server_ip": "...", "intervals": ["1d","1h",...],
 *     "total_symbols": 214, "offset": 0, "limit": 20, "more": true, "next_offset": 20,
 *     "data": {
 *       "PETR4.SA": {
 *         "1d": {"ok":true,"count":250,"candles":[{"t":..,"o":..,"h":..,"l":..,"c":..,"v":..}, ...]},
 *         "1h": {...}, "30m": {...}, "15m": {...}
 *       },
 *       "ITUB4.SA": { ... }
 *     }
 *   }
 *
 * Uso:
 *   yahoo_bulk.php                              # página 0 (20 símbolos × 4 TFs)
 *   yahoo_bulk.php?offset=20&limit=20           # próxima página
 *   yahoo_bulk.php?symbol=PETR4.SA              # um símbolo, todos os TFs
 *   yahoo_bulk.php?intervals=1d,1h&limit=50     # só alguns TFs, lote maior
 */

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

$UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    . '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

// Range seguro por intervalo (limite intradiário do Yahoo: 30m/15m <= 60 dias).
$RANGE_BY_INTERVAL = ['1d' => '1y', '1h' => '6mo', '30m' => '1mo', '15m' => '5d'];

$intervals = array_filter(array_map('trim', explode(',', $_GET['intervals'] ?? '1d,1h,30m,15m')));
if (!$intervals) $intervals = ['1d', '1h', '30m', '15m'];

// Universo: símbolo único (override) ou fatia de symbols.json.
$override = isset($_GET['symbol']) ? trim((string)$_GET['symbol']) : '';
if ($override !== '') {
    $symbols = [$override];
    $total = 1; $offset = 0; $limit = 1;
} else {
    $all = json_decode(@file_get_contents(__DIR__ . '/symbols.json'), true);
    if (!is_array($all)) {
        http_response_code(500);
        echo json_encode(['error' => 'symbols.json nao encontrado/invalido']);
        exit;
    }
    $total  = count($all);
    $offset = max(0, (int)($_GET['offset'] ?? 0));
    $limit  = min(50, max(1, (int)($_GET['limit'] ?? 20)));
    $symbols = array_slice($all, $offset, $limit);
}

/**
 * Converte o corpo cru do Yahoo Chart em candles compactos [{t,o,h,l,c,v}, ...].
 * Retorna ['ok'=>bool, 'code'=>int, 'count'=>n, 'candles'=>[...]] ou erro.
 */
function parse_chart($body, $code) {
    $j = json_decode($body, true);
    $chart = is_array($j) ? ($j['chart'] ?? null) : null;
    if (!is_array($chart)) return ['ok' => false, 'code' => $code, 'error' => 'non-json'];
    $res = $chart['result'][0] ?? null;
    $err = $chart['error'] ?? null;
    if (!is_array($res)) {
        return ['ok' => false, 'code' => $code, 'error' => $err['description'] ?? 'no result'];
    }
    $ts = $res['timestamp'] ?? [];
    $q  = $res['indicators']['quote'][0] ?? [];
    $candles = [];
    for ($i = 0, $n = count($ts); $i < $n; $i++) {
        $candles[] = [
            't' => $ts[$i],
            'o' => $q['open'][$i]  ?? null,
            'h' => $q['high'][$i]  ?? null,
            'l' => $q['low'][$i]   ?? null,
            'c' => $q['close'][$i] ?? null,
            'v' => $q['volume'][$i] ?? null,
        ];
    }
    return ['ok' => true, 'code' => $code, 'count' => count($candles), 'candles' => $candles];
}

// ---- monta a fila de jobs (symbol × interval) --------------------------------
$jobs = [];
foreach ($symbols as $sym) {
    foreach ($intervals as $iv) {
        $rng = $RANGE_BY_INTERVAL[$iv] ?? '1mo';
        $url = 'https://query1.finance.yahoo.com/v8/finance/chart/' . rawurlencode($sym)
             . '?range=' . urlencode($rng) . '&interval=' . urlencode($iv);
        $jobs[] = [$sym, $iv, $url];
    }
}

// ---- curl_multi: drena a fila com até $CONC chamadas em paralelo -------------
$CONC = 16;
$mh = curl_multi_init();
$active = [];   // id(handle) => [sym, iv]
$data = [];     // sym => iv => parsed
$queue = $jobs;

$replenish = function () use (&$queue, &$active, $mh, $UA, $CONC) {
    while (count($active) < $CONC && $queue) {
        list($sym, $iv, $url) = array_shift($queue);
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
        curl_multi_add_handle($mh, $ch);
        $active[(int)$ch] = [$sym, $iv, $ch];
    }
};

$replenish();
$running = 0;
do {
    curl_multi_exec($mh, $running);
    while ($info = curl_multi_info_read($mh)) {
        $ch = $info['handle'];
        $id = (int)$ch;
        if (isset($active[$id])) {
            list($sym, $iv) = $active[$id];
            $body = curl_multi_getcontent($ch);
            $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            $data[$sym][$iv] = parse_chart($body, $code);
            unset($active[$id]);
        }
        curl_multi_remove_handle($mh, $ch);
        curl_close($ch);
        $replenish();
    }
    if ($running > 0) curl_multi_select($mh, 1.0);
} while ($running > 0);

curl_multi_close($mh);

$next = ($offset + count($symbols)) < $total ? $offset + count($symbols) : null;
echo json_encode([
    'generated_at'   => gmdate('c'),
    'server_ip'      => $_SERVER['SERVER_ADDR'] ?? null,
    'intervals'      => array_values($intervals),
    'total_symbols'  => $total,
    'offset'         => $offset,
    'limit'          => $limit,
    'more'           => $next !== null,
    'next_offset'    => $next,
    'symbols_in_page'=> count($symbols),
    'data'           => $data,
], JSON_UNESCAPED_SLASHES);
