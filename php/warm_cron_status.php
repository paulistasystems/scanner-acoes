<?php
/**
 * php/warm_cron_status.php — O warm_cron está rodando em dia?
 *
 * Deploy (subpath /scanner/ do domínio, junto de yahoo_chart.php):
 *   https://paulista.dev/scanner/warm_cron_status.php
 *   https://paulista.dev/scanner/warm_cron_status.php?format=html
 *
 * Sinais (em ordem de utilidade)
 * ------------------------------
 * 1) Heartbeat JSON  tmp/warm_cron_status.json  (gravado pelo warm_cron.py)
 * 2) SQLite scanner.db — tabela fill_state.last_filled_at
 *    Cada (symbol, interval) aquecido faz INSERT OR REPLACE com timestamp.
 *    Isso é a prova *no banco* de que o job (ou outro prewarm) escreveu dados.
 *    Padrao cron a cada 10 min → fills espalhados em varios slots de 10 min.
 *    Um bulk unico → 90%+ dos fills no mesmo slot de 10 min.
 * 3) mtimes de warm_cron.log / .lock (auxiliar)
 * 4) crontab -l se shell_exec existir (só agenda, não prova execução)
 */

header('Cache-Control: no-store');
date_default_timezone_set('America/Sao_Paulo');

$tz = new DateTimeZone('America/Sao_Paulo');
$now = new DateTimeImmutable('now', $tz);

// ---------- paths ----------
$tmpCandidates = [
    '/home/paulista/scanner/tmp',
    dirname(__DIR__) . '/tmp',
    __DIR__ . '/../tmp',
];
$tmpDir = null;
foreach ($tmpCandidates as $d) {
    if (@is_dir($d)) { $tmpDir = $d; break; }
}
$statusPath = $tmpDir ? $tmpDir . '/warm_cron_status.json' : null;
$logPath    = $tmpDir ? $tmpDir . '/warm_cron.log' : null;
$lockPath   = $tmpDir ? $tmpDir . '/warm_cron.lock' : null;

function _db_path(): ?string {
    $env = getenv('SCANNER_DB');
    if ($env && @is_file($env)) return $env;
    $prod = '/home/paulista/scanner/scanner.db';
    if (@is_file($prod)) return $prod;
    $local = dirname(__DIR__) . '/scanner.db';
    if (@is_file($local)) return $local;
    $local2 = __DIR__ . '/../scanner.db';
    if (@is_file($local2)) return $local2;
    return null;
}

function _file_meta(?string $path): ?array {
    if (!$path || !@is_file($path)) return null;
    $mtime = @filemtime($path);
    return [
        'path'   => $path,
        'exists' => true,
        'bytes'  => @filesize($path),
        'mtime'  => $mtime ? date('c', $mtime) : null,
        'age_s'  => $mtime ? (time() - $mtime) : null,
    ];
}

function _parse_iso(?string $s, DateTimeZone $tz): ?DateTimeImmutable {
    if (!$s) return null;
    try {
        if (preg_match('/[zZ]$|[+-]\d{2}:?\d{2}$/', $s)) {
            return (new DateTimeImmutable($s))->setTimezone($tz);
        }
        return new DateTimeImmutable($s, $tz);
    } catch (Exception $e) {
        return null;
    }
}

/** Pregão B3: seg–sex 10:00–17:59 America/Sao_Paulo. */
function _in_market_window(DateTimeImmutable $dt): bool {
    if ((int)$dt->format('N') > 5) return false;
    $hm = (int)$dt->format('Hi');
    return $hm >= 1000 && $hm <= 1759;
}

// ---------- 1) heartbeat JSON ----------
$heartbeat = null;
if ($statusPath && @is_file($statusPath)) {
    $raw = @file_get_contents($statusPath);
    $heartbeat = json_decode((string)$raw, true);
    if (!is_array($heartbeat)) $heartbeat = null;
}

$lastRef = null;
$lastRefKind = null;
if (is_array($heartbeat)) {
    if (!empty($heartbeat['last_end'])) {
        $lastRef = _parse_iso((string)$heartbeat['last_end'], $tz);
        $lastRefKind = 'end';
    } elseif (!empty($heartbeat['last_start']) && ($heartbeat['last_status'] ?? '') === 'running') {
        $lastRef = _parse_iso((string)$heartbeat['last_start'], $tz);
        $lastRefKind = 'start';
    } elseif (!empty($heartbeat['last_skip'])) {
        $lastRef = _parse_iso((string)$heartbeat['last_skip'], $tz);
        $lastRefKind = 'skip';
    } elseif (!empty($heartbeat['last_start'])) {
        $lastRef = _parse_iso((string)$heartbeat['last_start'], $tz);
        $lastRefKind = 'start';
    }
}

$ageS = $lastRef ? ($now->getTimestamp() - $lastRef->getTimestamp()) : null;
$inMarket = _in_market_window($now);
$maxAgeS = $inMarket ? 20 * 60 : 75 * 60;

$verdict = 'never';
$verdictDetail = 'Nenhum heartbeat (tmp/warm_cron_status.json). Deploye warm_cron.py novo e rode o cron ao menos 1x.';

if (is_array($heartbeat)) {
    $st = (string)($heartbeat['last_status'] ?? '');
    if ($st === 'running' && $ageS !== null && $ageS < 2 * 3600) {
        $verdict = 'running';
        $verdictDetail = "warm_cron em execução (idade {$ageS}s).";
    } elseif ($st === 'error') {
        $verdict = 'error';
        $verdictDetail = 'Última execução em erro: ' . (string)($heartbeat['last_error'] ?? '?');
    } elseif ($ageS === null) {
        $verdict = 'unknown';
        $verdictDetail = 'Heartbeat sem timestamp utilizável.';
    } elseif ($ageS <= $maxAgeS) {
        $verdict = 'ok';
        $verdictDetail = sprintf(
            'Última atividade há %ds (limite %ds; janela %s).',
            $ageS, $maxAgeS, $inMarket ? 'pregão */10' : 'fora do pregão (horário)'
        );
    } else {
        $verdict = 'late';
        $verdictDetail = sprintf(
            'ATRASADO: última atividade há %ds (limite %ds).',
            $ageS, $maxAgeS
        );
    }
}

// ---------- 2) SQLite fill_state timestamps ----------
// warm_cron → data_layer.prewarm → _set_fill_state:
//   INSERT OR REPLACE INTO fill_state(symbol, interval, last_filled_at) VALUES (?,?,?)
// last_filled_at = datetime.now().isoformat() no momento do fill.
// NÃO é o ts da candle (isso fica em bars.ts). É o relógio de wall-clock do job.
$dbEvidence = [
    'available' => false,
    'db_path'   => _db_path(),
    'error'     => null,
];

if ($dbEvidence['db_path'] && extension_loaded('pdo_sqlite')) {
    try {
        $pdo = new PDO('sqlite:' . $dbEvidence['db_path']);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $pdo->exec('PRAGMA busy_timeout=3000');

        $count = (int)$pdo->query('SELECT COUNT(*) FROM fill_state')->fetchColumn();
        $minmax = $pdo->query(
            'SELECT MIN(last_filled_at) AS mn, MAX(last_filled_at) AS mx FROM fill_state'
        )->fetch(PDO::FETCH_ASSOC);

        $byInterval = $pdo->query(
            "SELECT interval, COUNT(*) AS n,
                    MIN(last_filled_at) AS mn, MAX(last_filled_at) AS mx
             FROM fill_state GROUP BY interval ORDER BY interval"
        )->fetchAll(PDO::FETCH_ASSOC);

        // Densidade por slot de 10 min (substr do ISO local: YYYY-MM-DDTHH:M + floor)
        // last_filled_at típico: 2026-07-13T21:22:13.823232-03:00
        $rows = $pdo->query('SELECT last_filled_at, interval FROM fill_state')->fetchAll(PDO::FETCH_ASSOC);

        $slots = [];          // 'Y-m-d H:i' floor 10min → count
        $hourBuckets = [];    // 'Y-m-d H' → count
        $maxDt = null;
        $minDt = null;
        $parsed = 0;

        foreach ($rows as $r) {
            $dt = _parse_iso((string)$r['last_filled_at'], $tz);
            if (!$dt) continue;
            $parsed++;
            if ($maxDt === null || $dt > $maxDt) $maxDt = $dt;
            if ($minDt === null || $dt < $minDt) $minDt = $dt;
            $floorMin = (int)floor(((int)$dt->format('i')) / 10) * 10;
            $slot = $dt->format('Y-m-d H:') . str_pad((string)$floorMin, 2, '0', STR_PAD_LEFT);
            $slots[$slot] = ($slots[$slot] ?? 0) + 1;
            $hour = $dt->format('Y-m-d H:00');
            $hourBuckets[$hour] = ($hourBuckets[$hour] ?? 0) + 1;
        }
        arsort($slots);
        arsort($hourBuckets);

        $topSlot = null;
        $topSlotCount = 0;
        if ($slots) {
            $topSlot = array_key_first($slots);
            $topSlotCount = $slots[$topSlot];
        }
        $topHour = $hourBuckets ? array_key_first($hourBuckets) : null;
        $topHourCount = $topHour ? $hourBuckets[$topHour] : 0;

        $fillAgeS = $maxDt ? ($now->getTimestamp() - $maxDt->getTimestamp()) : null;
        $burstRatio = ($count > 0 && $topSlotCount > 0) ? round($topSlotCount / $count, 3) : null;

        // Interpretação do padrão temporal
        // - burst (1 slot 10min com >=50% fills): um prewarm contínuo / bulk, NÃO vários ticks de cron
        // - cron-like: vários slots de 10min com fills, ao longo de horas de pregão
        $slotCount = count($slots);
        $pattern = 'empty';
        $patternDetail = 'fill_state vazio.';
        if ($count > 0) {
            if ($burstRatio !== null && $burstRatio >= 0.5) {
                $pattern = 'bulk_burst';
                $patternDetail = sprintf(
                    '%.0f%% dos fills no mesmo slot de 10 min (%s, n=%d). Parece UMA corrida longa de prewarm, não ticks */10 espalhados.',
                    $burstRatio * 100, $topSlot, $topSlotCount
                );
            } elseif ($slotCount >= 4) {
                $pattern = 'spread_multi_slot';
                $patternDetail = sprintf(
                    '%d slots de 10 min com fills — consistente com várias execuções (cron ou manuais).',
                    $slotCount
                );
            } else {
                $pattern = 'few_slots';
                $patternDetail = sprintf(
                    'Só %d slot(s) de 10 min com atividade — poucas corridas, não um dia inteiro de */10.',
                    $slotCount
                );
            }
        }

        // "db_fresh": max last_filled_at dentro da mesma janela de graça do heartbeat
        $dbFresh = ($fillAgeS !== null && $fillAgeS <= $maxAgeS);
        $dbVerdict = 'never';
        if ($count === 0) {
            $dbVerdict = 'empty';
        } elseif ($dbFresh) {
            $dbVerdict = 'fresh';
        } else {
            $dbVerdict = 'stale';
        }

        // top 8 slots + hours for payload
        $topSlots = [];
        $i = 0;
        foreach ($slots as $k => $v) {
            $topSlots[] = ['slot' => $k, 'fills' => $v];
            if (++$i >= 8) break;
        }
        $topHours = [];
        $i = 0;
        foreach ($hourBuckets as $k => $v) {
            $topHours[] = ['hour' => $k, 'fills' => $v];
            if (++$i >= 8) break;
        }

        $dbEvidence = [
            'available'       => true,
            'db_path'         => $dbEvidence['db_path'],
            'error'           => null,
            'fill_state_count'=> $count,
            'parsed_timestamps' => $parsed,
            'last_filled_min' => $minDt ? $minDt->format('c') : ($minmax['mn'] ?? null),
            'last_filled_max' => $maxDt ? $maxDt->format('c') : ($minmax['mx'] ?? null),
            'fill_age_s'      => $fillAgeS,
            'db_verdict'      => $dbVerdict,   // fresh | stale | empty
            'db_fresh'        => $dbFresh,
            'pattern'         => $pattern,     // bulk_burst | spread_multi_slot | few_slots | empty
            'pattern_detail'  => $patternDetail,
            'burst_ratio'     => $burstRatio,
            'distinct_10min_slots' => $slotCount,
            'top_10min_slot'  => $topSlot,
            'top_10min_fills' => $topSlotCount,
            'top_slots'       => $topSlots,
            'top_hours'       => $topHours,
            'by_interval'     => $byInterval,
            'note'            => 'last_filled_at = wall-clock do prewarm (_set_fill_state), NÃO o timestamp da candle (bars.ts).',
        ];
    } catch (Throwable $e) {
        $dbEvidence['error'] = $e->getMessage();
    }
} elseif (!$dbEvidence['db_path']) {
    $dbEvidence['error'] = 'scanner.db não encontrado';
} else {
    $dbEvidence['error'] = 'extensão pdo_sqlite indisponível';
}

// ---------- 3) crontab (informativo) ----------
$crontab = ['available' => false, 'lines' => [], 'error' => null, 'warm_cron_entries' => []];
$disabled = array_map('trim', explode(',', (string)ini_get('disable_functions')));
if (function_exists('shell_exec') && !in_array('shell_exec', $disabled, true)) {
    $out = @shell_exec('crontab -l 2>&1');
    if ($out === null || $out === '') {
        $crontab['error'] = 'shell_exec vazio (sem crontab ou bloqueado)';
    } else {
        $crontab['available'] = true;
        $lines = preg_split("/\r\n|\n|\r/", trim($out)) ?: [];
        $crontab['lines'] = $lines;
        $crontab['warm_cron_entries'] = array_values(array_filter(
            $lines,
            static fn($ln) => stripos($ln, 'warm_cron') !== false
        ));
        if (stripos($out, 'not allowed') !== false || stripos($out, 'denied') !== false) {
            $crontab['available'] = false;
            $crontab['error'] = trim($out);
        }
    }
} else {
    $crontab['error'] = 'shell_exec indisponível (disable_functions / CageFS)';
}

// ---------- combined reading ----------
// Heartbeat é a prova do *processo* warm_cron.py.
// SQLite é a prova de que *algum* prewarm escreveu fill_state (cron, manual, API, upload).
$combined = 'unknown';
$combinedDetail = '';
if ($verdict === 'ok' || $verdict === 'running') {
    $combined = $verdict;
    $combinedDetail = 'Heartbeat do warm_cron.py em dia.';
    if (($dbEvidence['db_verdict'] ?? null) === 'stale') {
        $combinedDetail .= ' (DB fill_state mais antigo que o heartbeat — possível run sem fills novos, normal se já filled.)';
    }
} elseif (($dbEvidence['db_verdict'] ?? null) === 'fresh') {
    $combined = 'db_active_no_heartbeat';
    $combinedDetail = 'fill_state fresco no SQLite, mas sem heartbeat JSON. '
        . 'Algo escreveu o banco (prewarm/manual/versão antiga do script), mas não o warm_cron.py com status.';
    if (($dbEvidence['pattern'] ?? '') === 'bulk_burst') {
        $combinedDetail .= ' Padrão = bulk_burst (uma corrida), não */10 contínuo.';
    }
} elseif ($verdict === 'never' && ($dbEvidence['db_verdict'] ?? null) === 'stale') {
    $combined = 'idle_or_dead';
    $combinedDetail = 'Sem heartbeat e fill_state velho — cron provavelmente não está rodando. '
        . ($dbEvidence['pattern_detail'] ?? '');
} elseif ($verdict === 'late') {
    $combined = 'late';
    $combinedDetail = $verdictDetail;
} elseif ($verdict === 'error') {
    $combined = 'error';
    $combinedDetail = $verdictDetail;
} else {
    $combined = $verdict;
    $combinedDetail = $verdictDetail;
}

$payload = [
    'ok'               => in_array($verdict, ['ok', 'running'], true),
    'verdict'          => $verdict,
    'detail'           => $verdictDetail,
    'combined'         => $combined,
    'combined_detail'  => $combinedDetail,
    'now'              => $now->format('c'),
    'timezone'         => 'America/Sao_Paulo',
    'in_market_window' => $inMarket,
    'max_age_s'        => $maxAgeS,
    'last_ref'         => $lastRef ? $lastRef->format('c') : null,
    'last_ref_kind'    => $lastRefKind,
    'age_s'            => $ageS,
    'expected_schedule'=> [
        'market' => '*/10 10-17 * * 1-5  .../python warm_cron.py >> .../tmp/warm_cron.log 2>&1',
        'hourly' => '3 * * * *  .../python warm_cron.py >> .../tmp/warm_cron.log 2>&1',
    ],
    'heartbeat'        => $heartbeat,
    'sqlite'           => $dbEvidence,
    'files'            => [
        'status' => _file_meta($statusPath),
        'log'    => _file_meta($logPath),
        'lock'   => _file_meta($lockPath),
        'tmp_dir'=> $tmpDir,
    ],
    'crontab'          => $crontab,
    'note'             => 'Prova de processo=heartbeat JSON. Prova de escrita=fill_state.last_filled_at no SQLite. bars.ts é o horário da candle, não do job.',
];

$http = 200;
if (in_array($verdict, ['late', 'never', 'error'], true)
    && !in_array($combined, ['db_active_no_heartbeat'], true)) {
    // Se o DB está fresco mesmo sem heartbeat, devolve 200 com aviso no combined
    // (ainda queremos alertar falta de heartbeat, mas HTTP 200 se dados fluem).
    $http = 503;
}
// Caso especial: DB fresco sem heartbeat → 200 + ok=false (monitora combined)
if ($combined === 'db_active_no_heartbeat') {
    $http = 200;
}
http_response_code($http);

$format = isset($_GET['format']) ? strtolower((string)$_GET['format']) : 'json';
if ($format === 'html') {
    header('Content-Type: text/html; charset=utf-8');
    $v = htmlspecialchars($verdict, ENT_QUOTES, 'UTF-8');
    $c = htmlspecialchars($combined, ENT_QUOTES, 'UTF-8');
    $d = htmlspecialchars($verdictDetail, ENT_QUOTES, 'UTF-8');
    $cd = htmlspecialchars($combinedDetail, ENT_QUOTES, 'UTF-8');
    $color = [
        'ok' => '#0a0', 'running' => '#06c', 'late' => '#c60',
        'never' => '#c00', 'error' => '#c00', 'unknown' => '#666',
        'db_active_no_heartbeat' => '#c60', 'idle_or_dead' => '#c00',
    ][$combined] ?? '#333';
    $jsonPretty = htmlspecialchars(
        json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES),
        ENT_QUOTES, 'UTF-8'
    );
    $dbLine = '';
    if (!empty($dbEvidence['available'])) {
        $dbLine = sprintf(
            '<p><b>SQLite fill_state:</b> %s · age=%ss · pattern=<code>%s</code><br>%s</p>',
            htmlspecialchars((string)$dbEvidence['db_verdict'], ENT_QUOTES, 'UTF-8'),
            htmlspecialchars((string)($dbEvidence['fill_age_s'] ?? '?'), ENT_QUOTES, 'UTF-8'),
            htmlspecialchars((string)$dbEvidence['pattern'], ENT_QUOTES, 'UTF-8'),
            htmlspecialchars((string)$dbEvidence['pattern_detail'], ENT_QUOTES, 'UTF-8')
        );
    }
    echo "<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\">"
       . "<title>warm_cron status</title>"
       . "<style>body{font-family:system-ui,sans-serif;max-width:54rem;margin:2rem auto;padding:0 1rem}"
       . "h1 span{color:{$color}} pre{background:#f4f4f4;padding:1rem;overflow:auto;font-size:12px}"
       . "code{background:#eee;padding:0 .25rem}</style></head><body>"
       . "<h1>warm_cron: <span>{$c}</span></h1>"
       . "<p><b>heartbeat verdict:</b> {$v} — {$d}</p>"
       . "<p><b>combined:</b> {$cd}</p>"
       . $dbLine
       . "<p><small>now {$now->format('c')} · market=" . ($inMarket ? 'yes' : 'no')
       . " · max_age={$maxAgeS}s</small></p>"
       . "<pre>{$jsonPretty}</pre></body></html>";
    exit;
}

header('Content-Type: application/json; charset=utf-8');
echo json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n";
