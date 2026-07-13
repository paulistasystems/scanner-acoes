<?php
/**
 * php/yahoo_snapshot.php — Snapshot COMPLETO (todos os símbolos × TFs) direto do
 * Yahoo Chart API v8 — 100% PHP, ao vivo, sem Python/DB/cache. Grava em disco:
 *   - all_data.csv  (formato longo/tidy: symbol,interval,ts,o,h,l,c,v) — DB friendly
 *   - all_data.json (aninhado: data[symbol][interval] = {count, candles:[...]})
 * escrita atômica (temp + rename). Devolve:
 *   - página HTML de status (default) — tabela símbolo × timeframe (verde/vermelho),
 *     legível como log de checagem;
 *   - ?json=1  → sumário JSON (para o consume_snapshot.py).
 *
 * Fluxo: dispare uma vez (build ~30-60s p/ ~864 séries); depois consuma os arquivos
 * estáticos. Chame de novo para regerar (sobrescreve atomicamente). Lock evita dois
 * builds simultâneos batendo no Yahoo.
 *
 * Ranges por intervalo respeitam o limite intradiário do Yahoo (30m/15m <= 60d):
 *   1d=1y  1h=6mo  30m=1mo  15m=5d
 */

@set_time_limit(300);
@ini_set('memory_limit', '512M');
header('Cache-Control: no-store');

$UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    . '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

$RANGE_BY_INTERVAL = ['1d' => '1y', '1h' => '6mo', '30m' => '1mo', '15m' => '5d'];

$intervals = array_filter(array_map('trim', explode(',', $_GET['intervals'] ?? '1d,1h,30m,15m')));
if (!$intervals) $intervals = ['1d', '1h', '30m', '15m'];
$as_json = isset($_GET['json']) && $_GET['json'] === '1';

$all = json_decode(@file_get_contents(__DIR__ . '/symbols.json'), true);
if (!is_array($all)) {
    http_response_code(500);
    header('Content-Type: application/json');
    echo json_encode(['status' => 'error', 'error' => 'symbols.json nao encontrado/invalido']);
    exit;
}

// Lock (janela de 240s; depois presume-se build travado e permite outro).
$lock = __DIR__ . '/.snapshot.lock';
if (is_file($lock) && (time() - filemtime($lock) < 240)) {
    header('Content-Type: application/json');
    echo json_encode(['status' => 'already_building', 'lock_age_s' => time() - filemtime($lock)]);
    exit;
}
@file_put_contents($lock, (string)time());

/** Converte corpo cru do Yahoo Chart em {ok,count,candles} ou {ok:false,error}. */
function parse_chart($body, $code) {
    $j = json_decode($body, true);
    $chart = is_array($j) ? ($j['chart'] ?? null) : null;
    if (!is_array($chart)) return ['ok' => false, 'error' => 'non-json'];
    $res = $chart['result'][0] ?? null;
    $err = $chart['error'] ?? null;
    if (!is_array($res)) return ['ok' => false, 'error' => $err['description'] ?? 'no result'];
    $ts = $res['timestamp'] ?? [];
    $q  = $res['indicators']['quote'][0] ?? [];
    $candles = [];
    for ($i = 0, $n = count($ts); $i < $n; $i++) {
        $candles[] = [
            't' => $ts[$i],
            'o' => $q['open'][$i]   ?? null,
            'h' => $q['high'][$i]   ?? null,
            'l' => $q['low'][$i]    ?? null,
            'c' => $q['close'][$i]  ?? null,
            'v' => $q['volume'][$i] ?? null,
        ];
    }
    return ['ok' => true, 'count' => count($candles), 'candles' => $candles];
}

$t0 = microtime(true);

// Fila de jobs (symbol × interval).
$jobs = [];
foreach ($all as $sym) {
    foreach ($intervals as $iv) {
        $rng = $RANGE_BY_INTERVAL[$iv] ?? '1mo';
        $jobs[] = [$sym, $iv, 'https://query1.finance.yahoo.com/v8/finance/chart/'
                   . rawurlencode($sym) . '?range=' . urlencode($rng)
                   . '&interval=' . urlencode($iv)];
    }
}

// curl_multi: até $CONC chamadas em paralelo.
$CONC = 24;
$mh = curl_multi_init();
$active = [];
$data = [];
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
        $active[(int)$ch] = [$sym, $iv];
    }
};
$replenish();
$running = 0;
do {
    curl_multi_exec($mh, $running);
    while ($info = curl_multi_info_read($mh)) {
        $ch = $info['handle']; $id = (int)$ch;
        if (isset($active[$id])) {
            list($sym, $iv) = $active[$id];
            $data[$sym][$iv] = parse_chart(curl_multi_getcontent($ch), curl_getinfo($ch, CURLINFO_HTTP_CODE));
            unset($active[$id]);
        }
        curl_multi_remove_handle($mh, $ch); curl_close($ch);
        $replenish();
    }
    if ($running > 0) curl_multi_select($mh, 1.0);
} while ($running > 0);
curl_multi_close($mh);

// ---- gravação em disco (atômica) -------------------------------------------
$generated_at = gmdate('c');

// JSON aninhado.
$json_tmp = __DIR__ . '/all_data.json.tmp';
file_put_contents($json_tmp, json_encode([
    'generated_at'  => $generated_at,
    'server_ip'     => $_SERVER['SERVER_ADDR'] ?? null,
    'intervals'     => array_values($intervals),
    'symbols_count' => count($all),
    'data'          => $data,
], JSON_UNESCAPED_SLASHES));
rename($json_tmp, __DIR__ . '/all_data.json');

// CSV longo/tidy — uma linha por candle (DB friendly: pandas/SQLite/SQL LOAD).
$csv_tmp = __DIR__ . '/all_data.csv.tmp';
$fp = fopen($csv_tmp, 'w');
fputcsv($fp, ['symbol', 'interval', 'ts', 'open', 'high', 'low', 'close', 'volume']);
foreach ($data as $sym => $tfs) {
    foreach ($tfs as $iv => $r) {
        if (!($r['ok'] ?? false)) continue;
        foreach ($r['candles'] as $c) {
            fputcsv($fp, [
                $sym, $iv,
                gmdate('Y-m-d\TH:i:s\Z', $c['t']),
                $c['o'], $c['h'], $c['l'], $c['c'], $c['v'],
            ]);
        }
    }
}
fclose($fp);
rename($csv_tmp, __DIR__ . '/all_data.csv');
@unlink($lock);

$elapsed = round(microtime(true) - $t0, 1);
$server_ip = $_SERVER['SERVER_ADDR'] ?? '?';

// ---- cobertura (sumário) ----------------------------------------------------
$by_ok = []; $by_fail = []; $failures = [];
foreach ($all as $sym) {
    foreach ($intervals as $iv) {
        $r = $data[$sym][$iv] ?? null;
        if ($r && $r['ok']) $by_ok[$iv] = ($by_ok[$iv] ?? 0) + 1;
        else {
            $by_fail[$iv] = ($by_fail[$iv] ?? 0) + 1;
            $failures[] = ['symbol' => $sym, 'interval' => $iv, 'error' => $r['error'] ?? 'missing'];
        }
    }
}
$series_ok = array_sum($by_ok);
$series_fail = array_sum($by_fail);
$expected = count($all) * count($intervals);

$summary = [
    'status'       => 'ok',
    'generated_at' => $generated_at,
    'elapsed_s'    => $elapsed,
    'symbols'      => count($all),
    'intervals'    => array_values($intervals),
    'series_ok'    => $series_ok,
    'series_fail'  => $series_fail,
    'expected'     => $expected,
    'by_interval'  => ['ok' => $by_ok, 'fail' => $by_fail],
    'failures'     => $failures,
    'files' => [
        'csv' => ['name' => 'all_data.csv', 'url' => 'https://paulista.dev/all_data.csv',
                  'bytes' => filesize(__DIR__ . '/all_data.csv')],
        'json' => ['name' => 'all_data.json', 'url' => 'https://paulista.dev/all_data.json',
                   'bytes' => filesize(__DIR__ . '/all_data.json')],
    ],
];

// ---- saída: HTML (default, legível) ou JSON (?json=1) -----------------------
if ($as_json) {
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($summary, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
    exit;
}

header('Content-Type: text/html; charset=utf-8');
$pct = $expected ? round(100 * $series_ok / $expected, 1) : 0;
$h_fail = '';
if ($failures) {
    $h_fail .= '<section><h2>Falhas (' . count($failures) . ')</h2><table class="log">'
             . '<tr><th>símbolo</th><th>intervalo</th><th>erro</th></tr>';
    foreach ($failures as $f) {
        $h_fail .= '<tr><td>' . htmlspecialchars($f['symbol']) . '</td><td>' . $f['interval']
                 . '</td><td>' . htmlspecialchars($f['error']) . '</td></tr>';
    }
    $h_fail .= '</table></section>';
}
$rows = '';
foreach ($all as $sym) {
    $cells = '';
    foreach ($intervals as $iv) {
        $r = $data[$sym][$iv] ?? null;
        if ($r && $r['ok']) {
            $cells .= '<td class="ok" title="' . $sym . ' ' . $iv . '">' . $r['count'] . '</td>';
        } else {
            $cells .= '<td class="fail" title="' . htmlspecialchars($r['error'] ?? 'missing') . '">✕</td>';
        }
    }
    $rows .= '<tr><td class="sym">' . $sym . '</td>' . $cells . '</tr>' . "\n";
}
$headcells = '';
foreach ($intervals as $iv) $headcells .= '<th>' . $iv . '</th>';

echo <<<HTML
<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Scanner — Snapshot Yahoo</title>
<style>
  body{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:24px;color:#222}
  h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;margin:24px 0 8px;border-bottom:1px solid #ddd;padding-bottom:4px}
  .meta{color:#555;margin-bottom:16px}
  .box{background:#f6f8fa;border:1px solid #e1e4e8;border-radius:6px;padding:12px 16px;margin-bottom:16px}
  .pills span{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;margin-right:6px}
  .ok-pill{background:#dcfbe6;color:#1a6b3a} .fail-pill{background:#ffd6d6;color:#8a1f1f}
  a{color:#0969da}
  table{border-collapse:collapse;width:100%;font-size:12px}
  th,td{border:1px solid #e1e4e8;padding:3px 6px;text-align:right}
  th{background:#f0f3f6} td.sym{text-align:left;font-family:ui-monospace,Menlo,monospace}
  td.ok{background:#dcfbe6;color:#1a6b3a} td.fail{background:#ffd6d6;color:#8a1f1f;text-align:center}
  .log td{text-align:left}
  code{background:#f0f3f6;padding:1px 4px;border-radius:3px}
</style></head><body>
<h1>Scanner — Snapshot Yahoo (PHP ao vivo)</h1>
<div class="meta">gerado em {$generated_at} · servidor {$server_ip} · build {$elapsed}s</div>
<div class="box">
  <strong>{$series_ok}/{$expected}</strong> séries OK ({$pct}%) ·
  <span class="pills"><span class="ok-pill">OK {$series_ok}</span><span class="fail-pill">FAIL {$series_fail}</span></span>
  <br><br>
  Arquivos: <a href="all_data.csv">all_data.csv</a> ({$summary['files']['csv']['bytes']} bytes, longo/tidy · DB friendly) ·
  <a href="all_data.json">all_data.json</a> ({$summary['files']['json']['bytes']} bytes, aninhado) ·
  <a href="yahoo_snapshot.php">🔄 regerar</a> · <a href="yahoo_snapshot.php?json=1">sumário JSON</a>
</div>
<table><tr><th>símbolo</th>{$headcells}</tr>
{$rows}</table>
{$h_fail}
</body></html>
HTML;
