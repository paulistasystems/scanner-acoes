const BASE = location.pathname.replace(/\/$/, '');

const PROFILES = {
    "Conservador": { adx_min: 20, rsi_min: 45, rsi_max: 65, vol_ratio: 1.5, vol_medio_min: 1000000, desc: "Menos setups, maior qualidade. Volume forte (1.5x) + liquidez mínima 1M + tendência clara." },
    "Moderado": { adx_min: 15, rsi_min: 40, rsi_max: 70, vol_ratio: 1.2, vol_medio_min: 500000, desc: "Equilíbrio entre quantidade e qualidade. Volume moderado (1.2x) + liquidez mínima 500K." },
    "Agressivo": { adx_min: 15, rsi_min: 40, rsi_max: 80, vol_ratio: 0.8, vol_medio_min: 300000, desc: "Máximo de oportunidades. Volume permissivo (0.8x) + liquidez mínima 300K." },
};

let currentScanners = [];
let pollInterval = null;

async function init() {
    await fetchScanners();
    setupEventListeners();
    updateStatus();
    setInterval(updateStatus, 5000); // Poll status every 5s
}

async function fetchScanners() {
    try {
        const res = await fetch(`${BASE}/api/scanners`);
        const data = await res.json();
        currentScanners = data.scanners;
        
        const select = document.getElementById('scanner-select');
        select.innerHTML = '<option value="">-- Escolha um Scanner --</option>';
        data.scanners.forEach(s => {
            select.innerHTML += `<option value="${s.id}">${s.name}</option>`;
        });
    } catch (e) {
        console.error("Failed to load scanners", e);
    }
}

function setupEventListeners() {
    const scannerSelect = document.getElementById('scanner-select');
    const profileControls = document.getElementById('profile-controls');
    const customSliders = document.getElementById('custom-sliders');
    const radios = document.querySelectorAll('input[name="profile"]');
    
    scannerSelect.addEventListener('change', (e) => {
        const scannerId = e.target.value;
        const scanner = currentScanners.find(s => s.id === scannerId);
        if (scanner && scanner.uses_profile) {
            profileControls.style.display = 'block';
        } else {
            profileControls.style.display = 'none';
        }
    });

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

    // Initialize default profile
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
    
    document.getElementById('btn-run').addEventListener('click', runScanner);
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
        
        document.getElementById('db-summary').innerText = data.summary;
        
        const wdiv = document.getElementById('warming-status');
        if (data.warming) {
            wdiv.style.display = 'block';
            const wp = data.warm_progress;
            const pct = wp.total > 0 ? Math.round((wp.done / wp.total) * 100) : 0;
            document.getElementById('warm-pct').innerText = pct;
            document.getElementById('warm-progress').value = pct;
            document.getElementById('warm-detail').innerText = `${wp.done}/${wp.total} - ${wp.last_symbol}`;
        } else {
            wdiv.style.display = 'none';
        }
    } catch (e) {
        console.error("Failed to update status", e);
    }
}

async function triggerWarm() {
    await fetch(`${BASE}/api/warm`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
    updateStatus();
}

async function refreshDB() {
    await fetch(`${BASE}/api/refresh`, { method: 'POST' });
    updateStatus();
    loadFill();
}

async function runScanner() {
    const scannerId = document.getElementById('scanner-select').value;
    if (!scannerId) {
        alert("Selecione um scanner!");
        return;
    }
    
    const container = document.getElementById('table-results');
    const countDiv = document.getElementById('results-count');
    container.innerHTML = '<p>Executando scanner, aguarde...</p>';
    countDiv.innerText = '';
    document.getElementById('btn-run').disabled = true;

    try {
        let url = `${BASE}/api/scan?scanner=${scannerId}`;
        
        const scanner = currentScanners.find(s => s.id === scannerId);
        if (scanner && scanner.uses_profile) {
            const adx = document.getElementById('adx_min').value;
            const rsi_min = document.getElementById('rsi_min').value;
            const rsi_max = document.getElementById('rsi_max').value;
            const vol_ratio = document.getElementById('vol_ratio_min').value;
            const vol_medio = document.getElementById('vol_medio_min').value;
            url += `&adx_min=${adx}&rsi_min=${rsi_min}&rsi_max=${rsi_max}&vol_ratio_min=${vol_ratio}&vol_medio_min=${vol_medio}`;
        }

        const res = await fetch(url);
        const data = await res.json();

        if (data.warming) {
            container.innerHTML = '<p>⏳ O banco de dados está aquecendo (baixando cotações). O scanner será concluído quando o aquecimento terminar.</p>';
            if (pollInterval) clearInterval(pollInterval);
            pollInterval = setInterval(async () => {
                const sRes = await fetch(`${BASE}/api/status`);
                const sData = await sRes.json();
                if (!sData.warming) {
                    clearInterval(pollInterval);
                    runScanner(); // Re-run when warm is done
                }
            }, 3000);
            return;
        }
        
        if (data.error) {
            container.innerHTML = `<p style="color:red">Erro: ${data.error}</p>`;
            return;
        }

        if (!data.rows || data.rows.length === 0) {
            container.innerHTML = '<p>Nenhum ativo encontrado com os critérios selecionados.</p>';
            return;
        }

        countDiv.innerHTML = `<strong>Encontrados: ${data.rows.length} ativos</strong>`;
        renderTable(container, data.columns, data.rows);
        
    } catch (e) {
        container.innerHTML = `<p style="color:red">Erro de rede: ${e.message}</p>`;
    } finally {
        document.getElementById('btn-run').disabled = false;
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
    const res = await fetch(`${BASE}/api/bars?symbol=${sym}&interval=${int}`);
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

// Start
document.addEventListener("DOMContentLoaded", init);
