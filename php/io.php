<?php
// php/io.php — utilitário de IO no servidor (DirectAdmin/Passenger, paulista.dev)
//
// Versão versionada (git) do scanner-acoes. O token de segurança é lido da
// env IO_PHP_TOKEN (configurada no domínio via DirectAdmin ou .user.ini).
//
// Operações:
//   extract_sitepackages  — extrai scanner_sitepackages.tgz no venv
//   extract_tgz           — extrai .tar.gz genérico (tgz=, dest=)
//   extract_app           — extrai scanner_app.tgz em /scanner/ (rmrf prévio)
//   rmrf                  — remove diretório recursivamente (path=)
//   mkdir                 — cria diretório (path=)
//   ls                    — lista diretório (path=)
//   shell                 — executa comando (cmd=) — WAF pode 403
//   ping                  — sanity check
//   dir                   — scandir nativo (path=)
//   cat                   — lê ficheiro (path=)

$token = getenv('IO_PHP_TOKEN');
if (!isset($_GET['token']) || $_GET['token'] !== $token) {
    http_response_code(403);
    header('Content-Type: text/plain');
    echo "forbidden\n";
    exit(1);
}

ini_set('memory_limit', '-1');
set_time_limit(0);
header('Content-Type: text/plain');

$home = '/home/paulista/';

function p($s) { echo $s . "\n"; }

function rmrf_php($dir) {
    if (!is_dir($dir)) { return; }
    $it = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($dir, FilesystemIterator::SKIP_DOTS),
        RecursiveIteratorIterator::CHILD_FIRST
    );
    foreach ($it as $f) {
        if ($f->isDir()) { @rmdir($f->getPathname()); }
        else { @unlink($f->getPathname()); }
    }
    @rmdir($dir);
}

function _tar_extract($tgz, $dest) {
    if (!file_exists($tgz)) { p("ERRO: $tgz ausente"); exit(1); }
    if (!is_dir($dest)) { mkdir($dest, 0755, true); }
    p(">> phar extract $tgz -> $dest");
    try {
        $phar = new PharData($tgz);
        $phar->extractTo($dest, null, true);
        p("EXTRAIDO OK");
    } catch (Exception $e) {
        p("ERRO PharData: " . $e->getMessage());
        // fallback: tenta tar via exec (caso PharData falhe por symlinks etc)
        p(">> fallback: tar -xzf " . basename($tgz) . " -C " . basename($dest));
        $cmd = "tar -xzf " . escapeshellarg($tgz) . " -C " . escapeshellarg($dest) . " 2>&1";
        exec($cmd, $out, $rc);
        foreach ($out as $l) p($l);
        if ($rc === 0) {
            p("EXTRAIDO OK (fallback)");
        } else {
            p("ERRO extract (tar rc=$rc)");
            exit(1);
        }
    }
}

$op = $_GET['op'] ?? '';
$path = $_GET['path'] ?? '';
if ($path !== '' && $path[0] !== '/') {
    $path = $home . $path;
}

switch ($op) {
    case 'extract_sitepackages':
        // Extrai scanner_sitepackages.tgz no virtualenv Python 3.9 do scanner.
        $tgz = $home . 'scanner/scanner_sitepackages.tgz';
        $dest = $home . 'virtualenv/scanner/3.9/lib/python3.9/site-packages/';
        if (!file_exists($tgz)) { p("ERRO: $tgz ausente"); exit(1); }
        if (!is_dir($dest)) { mkdir($dest, 0755, true); }
        _tar_extract($tgz, $dest);
        // Remove .so aarch64 que porventura tenham ficado
        $removed = 0;
        $rii = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($dest, FilesystemIterator::SKIP_DOTS));
        foreach ($rii as $f) {
            if ($f->isFile() && strpos($f->getFilename(), 'aarch64') !== false) {
                @unlink($f->getPathname());
                $removed++;
            }
        }
        p("limpeza aarch64: $removed ficheiro(s) removido(s)");
        break;

    case 'extract_tgz':
        // Extrai um .tar.gz generico para um destino.
        $tgz_rel = $_GET['tgz'] ?? '';
        $dest_rel = $_GET['dest'] ?? '';
        if ($tgz_rel === '' || $dest_rel === '') {
            p("uso: op=extract_tgz&tgz=rel/to/file.tgz&dest=rel/to/dir"); exit(1);
        }
        $tgz = ($tgz_rel[0] === '/' ? '' : $home) . $tgz_rel;
        $dest = ($dest_rel[0] === '/' ? '' : $home) . $dest_rel;
        _tar_extract($tgz, $dest);
        break;

    case 'extract_app':
        // Extrai scanner_app.tgz em /scanner/, após limpar diretórios de
        // runtime que não devem persistir entre deploys (__pycache__, static
        // — mas preserva scanner.db, tmp/, etc.).
        $tgz = $home . 'scanner/scanner_app.tgz';
        $dest = $home . 'scanner/';
        if (!file_exists($tgz)) { p("ERRO: $tgz ausente"); exit(1); }
        if (!is_dir($dest)) { mkdir($dest, 0755, true); }
        // Remove dirs que o novo deploy deve substituir completamente
        foreach (['static', '__pycache__'] as $sub) {
            $d = $dest . $sub;
            if (is_dir($d)) {
                p(">> rmrf_php $d");
                rmrf_php($d);
            }
        }
        // Garante que static/ existe (tar pode falhar se houve ._static residual)
        $static_dir = $dest . 'static';
        if (!is_dir($static_dir)) {
            @unlink($static_dir); // remove Apple Double se existir
            mkdir($static_dir, 0755, true);
            p(">> mkdir $static_dir");
        }
        _tar_extract($tgz, $dest);
        // Copia restart.txt do extract para tmp/ (se veio solto na raiz)
        if (is_file($dest . 'restart.txt') && is_dir($dest . 'tmp')) {
            rename($dest . 'restart.txt', $dest . 'tmp/restart.txt');
        }
        break;

    case 'mkdir':
        if (!is_dir($path)) {
            mkdir($path, 0755, true);
            p("CRIADO OK");
        } else {
            p("JA EXISTE");
        }
        break;

    case 'ls':
        if (!is_dir($path)) { p("NAO E DIR: $path"); exit(1); }
        $cmd = "ls -la " . escapeshellarg($path) . " 2>&1";
        exec($cmd, $out, $rc);
        foreach ($out as $l) p($l);
        p("rc=$rc");
        break;

    case 'rmrf':
        if ($path === '' || $path === $home) { p("recusa: caminho vazio/raiz"); exit(1); }
        p(">> rmrf_php $path");
        rmrf_php($path);
        p("REMOVIDO OK");
        break;

    case 'shell':
        $cmd = $_GET['cmd'] ?? '';
        if ($cmd === '') { p("cmd vazio"); exit(1); }
        p(">> $cmd");
        exec($cmd . " 2>&1", $out, $rc);
        foreach ($out as $l) p($l);
        p("rc=$rc");
        break;

    case 'ping':
        p("ok home=" . $home);
        break;

    case 'dir':
        $p = $path !== '' ? $path : $home;
        if ($p[0] !== '/') $p = $home . $p;
        p(">> dir $p");
        if (!is_dir($p)) { p("NAO E DIR"); break; }
        $items = scandir($p);
        if ($items === false) { p("scandir falhou"); break; }
        foreach ($items as $it) {
            if ($it === '.' || $it === '..') continue;
            $tag = is_dir($p . '/' . $it) ? 'D' : 'F';
            p("$tag $it");
        }
        break;

    case 'cat':
        $p = $path !== '' ? $path : $home;
        if ($p[0] !== '/') $p = $home . $p;
        p(">> cat $p");
        if (!is_file($p)) { p("NAO E FICHEIRO"); break; }
        echo file_get_contents($p);
        break;

    default:
        p("op desconhecido: $op");
        p("ops: ping, ls, rmrf, mkdir, shell, extract_sitepackages, extract_tgz, extract_app, dir, cat");
        exit(1);
}
