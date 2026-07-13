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
// Write-through: grava o JSON cru no scanner.db (tabela chart_cache) se o fetch deu
// OK. Best-effort — falha silenciosa se SQLite/DB indisponível (o relay segue intacto).
if ((int)$info['http_code'] === 200 && $symbol !== '' && isset($_GET['interval'])) {
    _scanner_cache_put($symbol, $_GET['interval'], $body);
}
echo $body;


// ----------------- chart_cache write-through (scanner.db) -----------------
// O proxy é o único EGRESS para o Yahoo em produção; cada fetch também persiste o
// JSON cru no SQLite (tabela chart_cache). O data_layer (Python) só LÊ este cache e
// faz a normalização (auto-adjust/tz/índice) — assim o PHP "atualiza o banco direto"
// sem duplicar a lógica de indicadores (sem risco de divergência). Como o aquecimento
// roda via cron (assíncrono, sequencial), não há lock entre escritores concorrentes;
// WAL + busy_timeout do SQLite tolera o resto.
function _scanner_db_path(): ?string {
    $env = getenv('SCANNER_DB');
    if ($env && @is_file($env)) return $env;
    $prod = '/home/paulista/scanner/scanner.db';     // proxy na raiz do domínio
    if (@is_file($prod)) return $prod;
    $local = __DIR__ . '/../scanner.db';             // dev: php/ sob o repo
    if (@is_file($local)) return $local;
    return null;
}

function _scanner_cache_put(string $symbol, string $interval, string $body): void {
    $db = _scanner_db_path();
    if ($db === null || $body === '') return;
    if (!extension_loaded('pdo_sqlite')) return;     // hospedagem sem SQLite -> só relay
    try {
        $pdo = new PDO('sqlite:' . $db);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_SILENT);
        $pdo->exec('PRAGMA busy_timeout=5000');
        $pdo->exec('PRAGMA journal_mode=WAL');
        $pdo->exec("CREATE TABLE IF NOT EXISTS chart_cache (
            symbol TEXT NOT NULL, interval TEXT NOT NULL,
            fetched_at TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(symbol, interval))");
        // INSERT OR REPLACE: compatível com qualquer SQLite (sem depender de UPSERT).
        $stmt = $pdo->prepare(
            "INSERT OR REPLACE INTO chart_cache(symbol, interval, fetched_at, payload)
             VALUES(:s, :i, :t, :p)");
        $stmt->execute([':s' => $symbol, ':i' => $interval,
                        ':t' => date('c'), ':p' => $body]);
    } catch (Throwable $e) {
        // best-effort: cache é otimização, nunca pode quebrar o relay.
    }
}
