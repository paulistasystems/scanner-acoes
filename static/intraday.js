const BASE = location.pathname.replace(/\/intraday$/, '').replace(/\/$/, '');

// Apenas os intervalos usados nos scanners intraday (1d, 30m, 15m)
const WARM_INTERVALS = "1d,30m,15m";

let intradayScanners = [];

async function init() {
    setupEventListeners();
    await fetchScanners();
    buildGrid();
    updateStatus();
    setInterval(updateStatus, 5000);
    startup();
}

async function fetchScanners() {
    try {
        const res = await fetch(`${BASE}/api/scanners`);
        const data = await res.json();
        // Filtra apenas os scanners que têm o group "intraday" marcado no backend
        intradayScanners = (data.scanners || []).filter(s => s.group === 'intraday');
    } catch (e) {
        console.error("Failed to load scanners", e);
        intradayScanners = [];
    }
}

function buildGrid() {
    const grid = document.getElementById('grid-intraday');
    if (!grid) return;

    grid.innerHTML = '';

    intradayScanners.forEach(s => {
        const panel = document.createElement('div');
        panel.className = 'scanner-panel';
        panel.dataset.id = s.id;
        panel.innerHTML = `
            <header>
                <span class="panel-name">${escapeHtml(s.name)}</span>
                <div class="panel-actions">
                    <span class="panel-badge loading">⏳ aguardando</span>
                </div>
            </header>
            <div class="table-container"></div>
        `;
        grid.appendChild(panel);
    });
}

function panelFor(id) {
    return document.querySelector(`.scanner-panel[data-id="${CSS.escape(id)}"]`);
}

function setBadge(panel, state, text) {
    if (!panel) return;
    const badge = panel.querySelector('.panel-badge');
    if (!badge) return;
    badge.className = `panel-badge ${state}`;
    badge.innerText = text;
}

async function startup() {
    setRunAllButton(false);
    try {
        const ok = await ensureDataReady();
        if (!ok) {
            markAllPanelsBlocked('⛔ dados incompletos');
            return;
        }
        await runAll();
    } catch (e) {
        console.error("startup failed", e);
        markAllPanelsBlocked('⛔ erro ao preparar dados');
    } finally {
        setRunAllButton(true);
    }
}

function isDataReady(data) {
    return !!(data && data.data_ready && data.data_ready.ready);
}

async function ensureDataReady() {
    let kickedWarm = false;
    for (let i = 0; i < 7200; i++) {
        let data;
        try {
            const res = await fetch(`${BASE}/api/status`);
            data = await res.json();
        } catch (e) {
            console.error("ensureDataReady status failed", e);
            await sleep(3000);
            continue;
        }
        updateStatusFrom(data);

        if (isDataReady(data)) {
            return true;
        }

        if (data.warming) {
            // aguardando progresso...
        } else if (!kickedWarm) {
            try {
                await fetch(`${BASE}/api/warm`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ intervals: WARM_INTERVALS })
                });
                kickedWarm = true;
            } catch (e) {
                console.error("ensureDataReady warm failed", e);
            }
        } else {
            if (i > 0 && i % 40 === 0) {
                kickedWarm = false;
            }
        }
        await sleep(3000);
    }
    return false;
}

function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
}

function waitForWarm() {
    return ensureDataReady();
}

function markAllPanelsBlocked(text) {
    intradayScanners.forEach((s) => {
        const panel = panelFor(s.id);
        if (!panel) return;
        setBadge(panel, 'error', text);
        const body = panel.querySelector('.table-container');
        if (body) {
            body.innerHTML = '<p class="placeholder">Scanners bloqueados até o warm completar (Intervalos: 1d, 30m, 15m).</p>';
        }
    });
}

async function runAll() {
    setRunAllButton(false);
    try {
        const res = await fetch(`${BASE}/api/status`);
        const data = await res.json();
        updateStatusFrom(data);
        if (!isDataReady(data)) {
            markAllPanelsBlocked('⛔ aguardando dados');
            const ok = await ensureDataReady();
            if (!ok) {
                markAllPanelsBlocked('⛔ dados incompletos');
                return;
            }
        }
        const promises = intradayScanners.map((s) => runSingle(s));
        await Promise.allSettled(promises);
    } finally {
        setRunAllButton(true);
    }
}

async function runSingle(scanner) {
    const panel = panelFor(scanner.id);
    if (!panel) return;
    const body = panel.querySelector('.table-container');

    setBadge(panel, 'loading', '⏳ executando…');
    body.innerHTML = '';

    let url = `${BASE}/api/scan?scanner=${encodeURIComponent(scanner.id)}`;

    // Pega o parametro de symbolos da pagina exclusiva
    const customSymbols = document.getElementById('custom-symbols-input')?.value.trim();
    if (customSymbols && scanner.uses_symbols) {
        url += `&symbols=${encodeURIComponent(customSymbols)}`;
    }

    try {
        const res = await fetch(url);
        const data = await res.json();

        if (data.warming) {
            setBadge(panel, 'loading', '⏳ aquecendo…');
            await waitForWarm();
            return runSingle(scanner);
        }
        if (data.not_ready || res.status === 503) {
            setBadge(panel, 'error', '⛔ dados incompletos');
            const msg = (data.data_ready && data.data_ready.message) || data.error || 'Warm incompleto';
            body.innerHTML = `<p class="placeholder">${escapeHtml(msg)}</p>`;
            return;
        }
        if (data.error) {
            setBadge(panel, 'error', '❌ erro');
            body.innerHTML = `<p style="color:red">Erro: ${escapeHtml(data.error)}</p>`;
            return;
        }
        if (!data.rows || data.rows.length === 0) {
            setBadge(panel, 'empty', '— vazio');
            body.innerHTML = '<p class="placeholder">Nenhum ativo encontrado.</p>';
            return;
        }

        setBadge(panel, 'done', `✅ ${data.rows.length} ativos`);
        renderTable(body, data.columns, data.rows);
    } catch (e) {
        setBadge(panel, 'error', '❌ rede');
        body.innerHTML = `<p style="color:red">Erro de rede: ${escapeHtml(e.message)}</p>`;
    }
}

function setupEventListeners() {
    document.getElementById('btn-refresh').addEventListener('click', refreshDB);
    document.getElementById('btn-warm').addEventListener('click', () => triggerWarm());
    document.getElementById('btn-run-all').addEventListener('click', startup);
}

function setRunAllButton(enabled) {
    const btn = document.getElementById('btn-run-all');
    if (!btn) return;
    btn.disabled = !enabled;
    btn.textContent = enabled ? '🔄 Atualizar Todos os Scanners' : '⏳ Executando…';
}

async function updateStatus() {
    try {
        const res = await fetch(`${BASE}/api/status`);
        const data = await res.json();
        updateStatusFrom(data);
    } catch (e) {
        console.error("Failed to update status", e);
    }
}

function updateStatusFrom(data) {
    const dbSummary = document.getElementById('db-summary');
    if (dbSummary) {
        const s = data.summary;
        const dr = data.data_ready;
        let base = '';
        if (s && typeof s === 'object') {
            base = `${s.bars ?? 0} barras · ${s.distinct_symbols ?? 0} ativos · ${s.fill_state ?? 0} preenchidos · ${s.fetch_failures ?? 0} falhas`;
        } else {
            base = s || '';
        }
        if (dr && typeof dr === 'object') {
            const gate = dr.ready ? '✅ pronto' : `⛔ ${dr.coverage_pct ?? 0}% (${dr.filled_pairs ?? 0}/${dr.expected_pairs ?? 0})`;
            base = base ? `${base} · ${gate}` : gate;
        }
        dbSummary.innerText = base;
    }

    const wdiv = document.getElementById('warming-status');
    const dr = data.data_ready;

    let isMissingFiles = false;
    let isFullyDone = false;
    if (data.today_requirements) {
        if (data.today_requirements.amount_still_missing > 0) {
            isMissingFiles = true;
        } else {
            isFullyDone = true;
        }
    }

    const showWarmUi = data.warming || (dr && !dr.ready) || isMissingFiles || isFullyDone;

    if (showWarmUi) {
        wdiv.style.display = 'block';
        let pct = 0;
        let detail = '';

        if (data.today_requirements && data.today_requirements.total_assets_to_scan_today > 0) {
            const tr = data.today_requirements;
            const wp = data.warm_progress;

            pct = Math.round((tr.amount_fresh / tr.total_assets_to_scan_today) * 100);

            if (tr.amount_still_missing > 0) {
                if (data.warming && wp && wp.total > 0) {
                    detail = `Baixando dados do dia... [ ${wp.done}/${wp.total} ] — Faltam: ${tr.amount_still_missing}`;
                } else {
                    detail = `Faltam atualizar ${tr.amount_still_missing} itens hoje`;
                }
            } else {
                detail = `Concluído: 100% atualizado para hoje`;
            }
        } else if (data.warming && data.warm_progress && data.warm_progress.total > 0) {
            const wp = data.warm_progress;
            pct = Math.round((wp.done / wp.total) * 100);
            detail = `Aquecendo: ${wp.done}/${wp.total}`;
        } else {
            detail = 'Aguarde...';
        }
        document.getElementById('warm-pct').innerText = pct;
        document.getElementById('warm-progress').value = pct;
        document.getElementById('warm-detail').innerText = detail;
    } else {
        wdiv.style.display = 'none';
    }
}

async function triggerWarm() {
    await fetch(`${BASE}/api/warm`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ intervals: WARM_INTERVALS }) });
    updateStatus();
}

async function refreshDB() {
    await fetch(`${BASE}/api/refresh`, { method: 'POST' });
    updateStatus();
    loadFill();
}

async function loadFill() {
    const res = await fetch(`${BASE}/api/fill_state`);
    const data = await res.json();
    if(data.length > 0) {
        const cols = Object.keys(data[0]).map(k => ({key: k, label: k}));
        renderTable(document.getElementById('table-fill'), cols, data);
    } else {
        document.getElementById('table-fill').innerHTML = '<p>Banco de dados vazio ou sem estado.</p>';
    }
}

function renderTable(container, columns, rows) {
    if (!rows.length) {
        container.innerHTML = "<p>Sem dados.</p>";
        return;
    }

    let html = '<table><thead><tr>';
    columns.forEach(c => {
        html += `<th>${c.label}</th>`;
    });
    html += '</tr></thead><tbody>';

    rows.forEach(row => {
        html += '<tr>';
        columns.forEach(c => {
            let val = row[c.key];
            if (val === null || val === undefined) val = "";
            else if (typeof val === 'number') val = (val % 1 !== 0) ? val.toFixed(2) : val;

            if (val === '✅') html += `<td style="color: #00c853;">${val}</td>`;
            else if (val === '❌') html += `<td style="color: #ff5252;">${val}</td>`;
            else if (typeof val === 'string' && val.includes('✅')) html += `<td style="color: #00c853;">${val}</td>`;
            else if (typeof val === 'string' && val.includes('⚠️')) html += `<td style="color: #ffd600;">${val}</td>`;
            else if (typeof val === 'string' && val.includes('❌')) html += `<td style="color: #ff5252;">${val}</td>`;
            else html += `<td>${val}</td>`;
        });
        html += '</tr>';
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
}

window.addEventListener("DOMContentLoaded", init);