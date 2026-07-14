const BASE = location.pathname.replace(/\/$/, '');

const PROFILES = {
    "Conservador": { adx_min: 20, rsi_min: 45, rsi_max: 65, vol_ratio: 1.5, vol_medio_min: 1000000, desc: "Menos setups, maior qualidade. Volume forte (1.5x) + liquidez mínima 1M + tendência clara." },
    "Moderado": { adx_min: 15, rsi_min: 40, rsi_max: 70, vol_ratio: 1.2, vol_medio_min: 500000, desc: "Equilíbrio entre quantidade e qualidade. Volume moderado (1.2x) + liquidez mínima 500K." },
    "Agressivo": { adx_min: 15, rsi_min: 40, rsi_max: 80, vol_ratio: 0.8, vol_medio_min: 300000, desc: "Máximo de oportunidades. Volume permissivo (0.8x) + liquidez mínima 300K." },
};

// Todos os 4 intervalos — cobre também os scanners de Abertura (15m).
const WARM_INTERVALS = "1d,1h,30m,15m";

let currentScanners = [];

async function init() {
    setupEventListeners();
    await fetchScanners();
    buildGrid();
    updateStatus();
    setInterval(updateStatus, 5000); // Poll status every 5s
    startup(); // Auto-run todos os scanners no carregamento da página
}

async function fetchScanners() {
    try {
        const res = await fetch(`${BASE}/api/scanners`);
        const data = await res.json();
        currentScanners = data.scanners || [];
    } catch (e) {
        console.error("Failed to load scanners", e);
        currentScanners = [];
    }
}

// Constrói um painel por scanner, separando os que usam perfil (Swing) dos fixos.
function buildGrid() {
    const profileGrid = document.getElementById('grid-profile');
    const fixedGrid = document.getElementById('grid-fixed');
    if (!profileGrid || !fixedGrid) return;

    profileGrid.innerHTML = '';
    fixedGrid.innerHTML = '';

    currentScanners.forEach(s => {
        const panel = document.createElement('div');
        panel.className = 'scanner-panel';
        panel.dataset.id = s.id;
        panel.innerHTML = `
            <header>
                <span class="panel-name">${escapeHtml(s.name)}</span>
                <div class="panel-actions">
                    <button class="btn-copy-analysis" style="display: none;">📋 Copiar Análise</button>
                    <span class="panel-badge loading">⏳ aguardando</span>
                </div>
            </header>
            <div class="table-container"></div>
        `;
        (s.uses_profile ? profileGrid : fixedGrid).appendChild(panel);

        const copyBtn = panel.querySelector('.btn-copy-analysis');
        if (copyBtn) {
            copyBtn.addEventListener('click', () => handleCopyClick(panel, s));
        }
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

// Fluxo de carregamento: warm (idempotente) até data_ready, senão scanners bloqueados.
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

/** Garante universo × intervalos preenchidos. Dispara warm se preciso (idempotente). */
async function ensureDataReady() {
    let kickedWarm = false;
    // até ~6h de warm longo (poll 3s)
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
            // aguarda progresso
        } else if (!kickedWarm) {
            // incompleto e parado → dispara warm (prewarm só preenche o que falta)
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
            // warm já terminou mas ainda incompleto (falhas Yahoo etc.)
            // tenta mais um kick a cada ~2 min de poll parado
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

// Compat: botão "Forçar Warm" e painéis que esperam fim do worker
function waitForWarm() {
    return ensureDataReady();
}

function markAllPanelsBlocked(text) {
    currentScanners.forEach((s) => {
        const panel = panelFor(s.id);
        if (!panel) return;
        setBadge(panel, 'error', text);
        const body = panel.querySelector('.table-container');
        if (body) {
            body.innerHTML = '<p class="placeholder">Scanners bloqueados até o warm completar todos os intervalos (1d, 1h, 30m, 15m) para o universo.</p>';
        }
    });
}

// Dispara todos os scanners em paralelo — só se data_ready.
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
        const promises = currentScanners.map((s) => runSingle(s));
        await Promise.allSettled(promises);
    } finally {
        setRunAllButton(true);
    }
}

async function runSingle(scanner) {
    const panel = panelFor(scanner.id);
    if (!panel) return;
    const body = panel.querySelector('.table-container');
    const copyBtn = panel.querySelector('.btn-copy-analysis');
    if (copyBtn) copyBtn.style.display = 'none';

    setBadge(panel, 'loading', '⏳ executando…');
    body.innerHTML = '';

    let url = `${BASE}/api/scan?scanner=${encodeURIComponent(scanner.id)}`;
    if (scanner.uses_profile) {
        const adx = document.getElementById('adx_min').value;
        const rsi_min = document.getElementById('rsi_min').value;
        const rsi_max = document.getElementById('rsi_max').value;
        const vol_ratio = document.getElementById('vol_ratio_min').value;
        const vol_medio = document.getElementById('vol_medio_min').value;
        url += `&adx_min=${adx}&rsi_min=${rsi_min}&rsi_max=${rsi_max}&vol_ratio_min=${vol_ratio}&vol_medio_min=${vol_medio}`;
    }

    try {
        const res = await fetch(url);
        const data = await res.json();

        if (data.warming) {
            // Corrida rara: aquecimento iniciou durante o scan. Aguarda e reexecuta este painel.
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

        panel.lastResults = { columns: data.columns, rows: data.rows };
        if (copyBtn) copyBtn.style.display = 'inline-block';

        setBadge(panel, 'done', `✅ ${data.rows.length} ativos`);
        renderTable(body, data.columns, data.rows);
    } catch (e) {
        setBadge(panel, 'error', '❌ rede');
        body.innerHTML = `<p style="color:red">Erro de rede: ${escapeHtml(e.message)}</p>`;
    }
}

function setupEventListeners() {
    const customSliders = document.getElementById('custom-sliders');
    const radios = document.querySelectorAll('input[name="profile"]');

    radios.forEach(r => {
        r.addEventListener('change', (e) => {
            const profile = e.target.value;
            if (profile === "Personalizado") {
                customSliders.style.display = 'grid';
                document.getElementById('profile-desc').innerText = "Ajuste os valores manualmente.";
            } else {
                customSliders.style.display = 'none';
                applyProfile(profile);
            }
        });
    });

    // Initialize default profile (sliders só aparecem no modo Personalizado)
    document.getElementById('custom-sliders').style.display = 'none';
    applyProfile("Conservador");

    // Sliders update labels
    const sliders = ['vol_ratio_min', 'vol_medio_min', 'adx_min', 'rsi_min', 'rsi_max'];
    sliders.forEach(id => {
        const el = document.getElementById(id);
        const label = document.getElementById(`val-${id.split('_')[0]}`);
        if(label) {
            el.addEventListener('input', (e) => {
                label.innerText = e.target.value;
            });
        }
    });

    // DB Panel tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            e.target.classList.add('active');
            document.getElementById(e.target.dataset.target).classList.add('active');

            if (e.target.dataset.target === 'tab-fill') loadFill();
            if (e.target.dataset.target === 'tab-failures') loadFailures();
        });
    });

    document.getElementById('btn-load-bars').addEventListener('click', loadBars);
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

function applyProfile(profileName) {
    const p = PROFILES[profileName];
    if(!p) return;

    document.getElementById('profile-desc').innerText = p.desc;
    document.getElementById('vol_ratio_min').value = p.vol_ratio;
    document.getElementById('val-vol').innerText = p.vol_ratio;
    document.getElementById('vol_medio_min').value = p.vol_medio_min;
    document.getElementById('val-liq').innerText = p.vol_medio_min;
    document.getElementById('adx_min').value = p.adx_min;
    document.getElementById('val-adx').innerText = p.adx_min;
    document.getElementById('rsi_min').value = p.rsi_min;
    document.getElementById('val-rsi-min').innerText = p.rsi_min;
    document.getElementById('rsi_max').value = p.rsi_max;
    document.getElementById('val-rsi-max').innerText = p.rsi_max;
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
    const showWarmUi = data.warming || (dr && !dr.ready);
    if (showWarmUi) {
        wdiv.style.display = 'block';
        const wp = data.warm_progress;
        let pct = 0;
        let detail = '';
        if (data.warming && wp && wp.total > 0) {
            pct = Math.round((wp.done / wp.total) * 100);
            detail = `${wp.done}/${wp.total} - ${wp.last_symbol || ''}`;
        } else if (dr && dr.expected_pairs > 0) {
            pct = Math.round(dr.coverage_pct || 0);
            const parts = (dr.by_interval || []).map(
                (x) => `${x.interval}:${x.have}/${x.expected}`
            );
            detail = parts.length ? parts.join(' · ') : (dr.message || 'Aguardando dados…');
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

            // Format checkmarks
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

// DB Panel load functions
async function loadBars() {
    const sym = document.getElementById('bars-symbol').value;
    const int = document.getElementById('bars-interval').value;
    const res = await fetch(`${BASE}/api/bars?symbol=${encodeURIComponent(sym)}&interval=${encodeURIComponent(int)}`);
    const data = await res.json();
    if(data.length > 0) {
        const cols = Object.keys(data[0]).map(k => ({key: k, label: k}));
        renderTable(document.getElementById('table-bars'), cols, data);
    } else {
        document.getElementById('table-bars').innerHTML = '<p>Nenhum dado encontrado para este ativo/intervalo.</p>';
    }
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

async function loadFailures() {
    const res = await fetch(`${BASE}/api/failures`);
    const data = await res.json();
    if(data.length > 0) {
        const cols = Object.keys(data[0]).map(k => ({key: k, label: k}));
        renderTable(document.getElementById('table-failures'), cols, data);
    } else {
        document.getElementById('table-failures').innerHTML = '<p>Nenhuma falha registrada.</p>';
    }
}

function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
}

function formatarResultadosParaTexto(columns, rows) {
    if (!rows || rows.length === 0) {
        return "Não há setups de compra válidos no momento.";
    }
    return rows.map(row => {
        const pares = [];
        columns.forEach(col => {
            let val = row[col.key];
            let valStr = "";
            if (val === null || val === undefined || (typeof val === 'number' && isNaN(val))) {
                valStr = "N/A";
            } else if (typeof val === 'number') {
                valStr = (val % 1 !== 0) ? val.toFixed(2) : val.toString();
            } else {
                valStr = String(val);
            }
            pares.push(`${col.label}: ${valStr}`);
        });
        return pares.join(" | ");
    }).join("\n");
}

function handleCopyClick(panel, scanner) {
    if (!panel.lastResults) return;
    const { columns, rows } = panel.lastResults;
    const copyBtn = panel.querySelector('.btn-copy-analysis');

    const promptTrader = `### Você é um trader profissional de Intraday e Swing curto prazo no mercado brasileiro.

**Regras de Análise (obedeça rigorosamente):**
- Timeframe principal: 1 hora
- Timeframe auxiliar: 30 minutos
- Estilo: Intraday ou Swing de 1 a 3 dias (posso carregar overnight)
- Risco máximo por trade: 1% do capital
- Risk:Reward mínimo obrigatório: **1:2**
- **Só liste setups de COMPRA válidos** (nada de venda ou short)
- Só recomende entrada se Score ≥ 65 e haja boa confluência entre 1h e 30m

**Responda EXATAMENTE neste formato:**

### ANÁLISE FINAL

**Setups de Compra Válidos (em ordem de prioridade):**

**XXXX** → **Score: XX/100**
**Entrada Sugerida:** R$ XXXX
**Stop Loss:** R$ XXXX (-X.X%)
**Target 1:** R$ XXXX (+X.X% | R:R 1:2)
**Target 2:** R$ XXXX (+X.X% | R:R 1:3)
**Confluência 1h + 30m:**
**Forças principais:**
**Fraquezas / Riscos:**
**Estratégia sugerida:**

**Setups para Monitorar (sem confluência suficiente):**
XXXX → Motivo breve

**Resumo Geral:**
**Viés do mercado hoje:**
**Nível de risco do dia (Baixo / Médio / Alto):**
**Melhor horário para entrada:**

Seja objetivo, direto e conservador. Se não houver setups bons, diga claramente "Não há setups de compra válidos no momento."

---

**Dados do Scanner (cole aqui todo o output do scanner):**

`;

    const dadosTextuais = formatarResultadosParaTexto(columns, rows);
    let configSliders = "";

    if (scanner.uses_profile) {
        const profile = document.querySelector('input[name="profile"]:checked').value;
        const vol = document.getElementById('vol_ratio_min').value;
        const adx = document.getElementById('adx_min').value;
        const rsiMin = document.getElementById('rsi_min').value;
        const rsiMax = document.getElementById('rsi_max').value;

        configSliders = `\n\n---\n**Scanner:** ${scanner.name}\n**Perfil:** ${profile}\n\n**Configuração dos Filtros Utilizados:**\n• Volume Ratio Mínimo: ${vol}\n• ADX Mínimo: ${adx}\n• RSI Mínimo: ${rsiMin}\n• RSI Máximo: ${rsiMax}`;
    } else {
        configSliders = `\n\n---\n**Scanner:** ${scanner.name}\n\n**Filtros:** Este scanner utiliza filtros internos próprios (configurações fixas incorporadas no scanner)`;
    }

    const textToCopy = promptTrader + dadosTextuais + configSliders;

    navigator.clipboard.writeText(textToCopy).then(() => {
        const originalText = copyBtn.textContent;
        copyBtn.textContent = '✅ Copiado!';
        copyBtn.style.background = 'linear-gradient(135deg, #059669, #047857)';
        copyBtn.style.color = '#fff';
        setTimeout(() => {
            copyBtn.textContent = originalText;
            copyBtn.style.background = '';
            copyBtn.style.color = '';
        }, 2000);
    }).catch(err => {
        console.error('Erro ao copiar para clipboard:', err);
        alert('Erro ao copiar automaticamente.');
    });
}

// Start
document.addEventListener("DOMContentLoaded", init);
