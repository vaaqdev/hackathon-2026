const API_BASE = 'http://localhost:5000/api';
let COMERCIO_ID = null;
let saldoVisible = true;
let saldoActual = 0;
let nombreComercio = '';
let selectedAccountTemp = 'COM001';
let comerciosDisponibles = []; // Almacena los comercios cargados del servidor
const accountBalances = {};

document.addEventListener("DOMContentLoaded", async () => {
    // Cargar comercios disponibles desde el servidor, luego seleccionar el primero
    await loadAccountOptions();
    if (comerciosDisponibles.length > 0) {
        cambiarCuenta(comerciosDisponibles[0].comercio.id);
    }
});

function getInitials(nombre) {
    // Genera iniciales a partir del nombre del comercio
    return nombre
        .split(' ')
        .map(word => word[0])
        .join('')
        .substring(0, 2)
        .toUpperCase();
}

async function loadAccountOptions() {
    // Cargar comercios disponibles desde el servidor
    try {
        const res = await fetch(`${API_BASE}/comercios`);
        if (!res.ok) throw new Error('Error cargando comercios');
        const data = await res.json();
        comerciosDisponibles = data.comercios || [];

        // Generar HTML del modal dinámicamente
        const modalBody = document.getElementById('account-modal-body');
        if (modalBody && comerciosDisponibles.length > 0) {
            modalBody.innerHTML = comerciosDisponibles.map((c, index) => {
                const comercio = c.comercio;
                const isSelected = index === 0 ? 'selected' : '';
                return `
                    <div class="account-option ${isSelected}" data-account="${comercio.id}" onclick="selectAccountOption('${comercio.id}')">
                        <div class="account-option-avatar">${getInitials(comercio.nombre)}</div>
                        <div class="account-option-info">
                            <div class="account-option-name">${comercio.nombre}</div>
                            <div class="account-option-id">${comercio.id} • ${comercio.categoria} • ${comercio.ciudad}</div>
                            <div class="account-balance-preview" id="preview-${comercio.id}">Cargando...</div>
                        </div>
                        <div class="account-option-check"><i class="fa-solid fa-check"></i></div>
                    </div>
                `;
            }).join('');
        }

        // Cargar saldos de todos los comercios
        await loadAccountBalances();

    } catch (e) {
        console.error('Error cargando comercios:', e);
    }
}

async function loadAccountBalances() {
    // Cargar saldos de todas las cuentas cargadas dinámicamente
    for (const c of comerciosDisponibles) {
        const comercioId = c.comercio.id;
        try {
            const res = await fetch(`${API_BASE}/comercio/${comercioId}`);
            if (res.ok) {
                const data = await res.json();
                accountBalances[comercioId] = data.metricas.saldo_actual;
                const previewEl = document.getElementById(`preview-${comercioId}`);
                if (previewEl) {
                    previewEl.textContent = `Saldo: $${accountBalances[comercioId].toLocaleString('en-US', {minimumFractionDigits: 2})}`;
                }
            }
        } catch (e) {
            console.error(`Error cargando saldo de ${comercioId}:`, e);
        }
    }
}

function openAccountModal() {
    const primerComercio = comerciosDisponibles.length > 0 ? comerciosDisponibles[0].comercio.id : 'COM001';
    selectedAccountTemp = COMERCIO_ID || primerComercio;
    updateAccountSelectionUI();
    const modal = document.getElementById('accountModal');
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeAccountModal(event) {
    if (event && event.target !== event.currentTarget) return;
    const modal = document.getElementById('accountModal');
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

function selectAccountOption(accountId) {
    selectedAccountTemp = accountId;
    updateAccountSelectionUI();
}

function updateAccountSelectionUI() {
    document.querySelectorAll('.account-option').forEach(opt => {
        if (opt.dataset.account === selectedAccountTemp) {
            opt.classList.add('selected');
        } else {
            opt.classList.remove('selected');
        }
    });
}

async function confirmAccountChange() {
    await cambiarCuenta(selectedAccountTemp);
    const badge = document.getElementById('current-account-badge');
    if (badge) badge.textContent = selectedAccountTemp;
    closeAccountModal();
    showMockMessage(`Cuenta cambiada a ${selectedAccountTemp}`);
}

async function cambiarCuenta(idComercio) {
    COMERCIO_ID = idComercio;

    try {
        // Obtener datos del comercio
        const res = await fetch(`${API_BASE}/comercio/${COMERCIO_ID}`);
        if (!res.ok) throw new Error("Comercio no encontrado");
        const data = await res.json();

        saldoActual = data.metricas.saldo_actual;
        nombreComercio = data.comercio.nombre;

        // Actualizar UI si los elementos existen
        const balanceLabel = document.getElementById('balance-label-cuenta');
        const balanceCuentaInfo = document.getElementById('balance-cuenta-info');
        const currentBadge = document.getElementById('current-account-badge');

        if (balanceLabel) balanceLabel.textContent = `Cuenta: ${nombreComercio}`;
        if (balanceCuentaInfo) balanceCuentaInfo.textContent = `${data.comercio.categoria} • ${data.comercio.ciudad}`;
        if (currentBadge) currentBadge.textContent = COMERCIO_ID;

        actualizarSaldoUI();

        // Recargar datos relacionados
        await fetchAlertaProactiva();
        if (window.innerWidth >= 768) await fetchDashboardMetrics();

    } catch (error) {
        console.error("Error al cargar cuenta:", error);
        const balanceLabel = document.getElementById('balance-label-cuenta');
        if (balanceLabel) balanceLabel.textContent = "Error al cargar cuenta";
    }
}

function toggleSaldoVisibility() {
    saldoVisible = !saldoVisible;
    const eyeIcon = document.getElementById('eye-icon');
    if (eyeIcon) {
        eyeIcon.className = saldoVisible ? 'fa-regular fa-eye-slash' : 'fa-regular fa-eye';
    }
    actualizarSaldoUI();
}

function actualizarSaldoUI() {
    const balanceElement = document.getElementById('balance-amount-value');
    if (!balanceElement) return;

    if (saldoVisible) {
        balanceElement.textContent = `$${saldoActual.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        balanceElement.style.color = '#FFFFFF';
    } else {
        balanceElement.textContent = '****';
        balanceElement.style.color = 'rgba(255,255,255,0.5)';
    }
}

async function fetchAlertaProactiva() {
    if (!COMERCIO_ID) return;
    try {
        const res = await fetch(`${API_BASE}/alerta-proactiva?id_comercio=${COMERCIO_ID}`);
        if (!res.ok) throw new Error("Error de red al consultar alerta");
        const data = await res.json();

        let bg, color, border, icon;
        if (data.tipo === 'positiva') { bg = 'rgba(16, 185, 129, 0.1)'; color = '#34d399'; border = 'rgba(16, 185, 129, 0.2)'; icon = 'fa-arrow-trend-up'; }
        else if (data.tipo === 'negativa') { bg = 'rgba(239, 68, 68, 0.1)'; color = '#f87171'; border = 'rgba(239, 68, 68, 0.2)'; icon = 'fa-arrow-trend-down'; }
        else { bg = 'rgba(139, 92, 246, 0.1)'; color = '#a78bfa'; border = 'rgba(139, 92, 246, 0.2)'; icon = 'fa-lightbulb'; }

        const badgeHTML = `
            <div class="proactive-badge" style="background:${bg}; color:${color}; border:1px solid ${border};" onclick="askAboutAlert('${data.titulo}')">
                <i class="fa-solid ${icon}"></i>
                <span><strong style="color: #fff">${data.titulo}</strong> ${data.descripcion}</span>
            </div>`;

        const badgePC = document.getElementById('proactive-badge-pc');
        const badgeMobile = document.getElementById('proactive-badge-mobile');

        if (badgePC) badgePC.innerHTML = badgeHTML;
        if (badgeMobile) badgeMobile.innerHTML = badgeHTML;
    } catch (error) {
        console.error("Fallo carga alerta proactiva:", error);
    }
}

function askAboutAlert(titulo) {
    const input = window.innerWidth >= 768 ? document.getElementById('modal-user-input') : document.getElementById('mobile-user-input');
    if (input) {
        input.value = `Dime más sobre esto: ${titulo}`;
        window.innerWidth >= 768 ? sendMessageModal() : sendMessageMobile();
    }
}

let pieChartInstance = null;
async function fetchDashboardMetrics() {
    if (!COMERCIO_ID) return;
    try {
        const res = await fetch(`${API_BASE}/comercio/${COMERCIO_ID}`);
        if (!res.ok) throw new Error("Comercio no encontrado");
        const data = await res.json();

        const metricas = data.metricas || {};
        const ventas = metricas.saldo_actual || 0;
        const ticket = metricas.ticket_promedio || 0;
        const tx = metricas.total_transacciones || 0;

        const kpiVentas = document.getElementById('kpi-ventas');
        const kpiTicket = document.getElementById('kpi-ticket');
        const kpiTx = document.getElementById('kpi-tx');

        if (kpiVentas) kpiVentas.textContent = `$${ventas.toLocaleString()}`;
        if (kpiTicket) kpiTicket.textContent = `$${ticket}`;
        if (kpiTx) kpiTx.textContent = tx.toLocaleString();

        const metodosPago = data.metodos_pago || {};
        const porcentajes = metodosPago.porcentajes || {};
        const metodos = Object.keys(porcentajes);
        const valores = Object.values(porcentajes);
        renderPieChart(metodos.length ? metodos : ['Sin datos'], valores.length ? valores : [100]);
    } catch (error) {
        console.error("Error cargando dashboard:", error);
    }
}

function renderPieChart(labels, data) {
    const canvas = document.getElementById('dashboardPieChart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (pieChartInstance) pieChartInstance.destroy();

    Chart.defaults.color = '#6C6C6C';

    pieChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: ['#4C1D80', '#00D2B9', '#8b5cf6', '#fbbf24'],
                borderWidth: 2,
                borderColor: '#FFFFFF'
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#1E1E1E', padding: 20, boxWidth: 12, usePointStyle: true, font: { size: 13, family: 'Inter' } }
                }
            }
        }
    });
}

// Configurar event listeners para inputs
const modalInput = document.getElementById('modal-user-input');
const mobileInput = document.getElementById('mobile-user-input');
const modalChatArea = document.getElementById('modal-chat-messages');
const mobileChatArea = document.getElementById('mobile-chat-messages');

if (modalInput) {
    modalInput.addEventListener('keypress', e => { if(e.key === 'Enter') sendMessageModal(); });
}
if (mobileInput) {
    mobileInput.addEventListener('keypress', e => { if(e.key === 'Enter') sendMessageMobile(); });
}

function sendMessageModal() { sendChatToAPI(modalInput, modalChatArea); }
function sendMessageMobile() { sendChatToAPI(mobileInput, mobileChatArea); }

async function sendChatToAPI(inputField, chatArea) {
    if (!inputField || !chatArea) return;

    const text = inputField.value.trim();
    if (!text) return;

    appendMessage(text, 'user', chatArea);
    inputField.value = '';

    const loaderId = 'loader-' + Date.now();
    appendMessage('<i class="fa-solid fa-circle-notch fa-spin"></i> Analizando datos...', 'bot', chatArea, loaderId);

    try {
        const res = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mensaje: text, id_comercio: COMERCIO_ID || 'COM001' })
        });
        const data = await res.json();

        const loader = document.getElementById(loaderId);
        if (loader) loader.remove();

        if(res.ok) {
            appendMessage(data.respuesta, 'bot', chatArea);
        } else {
            appendMessage(data.detail || "Hubo un error al procesar tu solicitud.", 'bot', chatArea);
        }
    } catch (error) {
        const loader = document.getElementById(loaderId);
        if (loader) loader.remove();
        appendMessage("No se pudo conectar a la API en localhost:5000.", 'bot', chatArea);
    }
}

function appendMessage(text, sender, chatArea, id = null) {
    if (!chatArea) return;
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}`;
    if (id) msgDiv.id = id;
    msgDiv.innerHTML = text;
    chatArea.appendChild(msgDiv);
    chatArea.scrollTop = chatArea.scrollHeight;
}

let toastTimeout;
function showMockMessage(featureName) {
    const toast = document.getElementById('toastMessage');
    if (toast) {
        toast.textContent = `Demo: Clic en "${featureName}"`;
        toast.classList.add('show');
        clearTimeout(toastTimeout);
        toastTimeout = setTimeout(() => toast.classList.remove('show'), 2000);
    }
}

const homeScreen = document.getElementById('screen-home');
const chatMobileScreen = document.getElementById('screen-chat-mobile');
const mobileNav = document.getElementById('mobile-nav');
const chatModal = document.getElementById('chatModal');

function openChat() {
    if (window.innerWidth >= 768) {
        if (chatModal) chatModal.style.display = 'flex';
    } else {
        if (homeScreen) homeScreen.classList.add('hidden');
        if (mobileNav) mobileNav.style.display = 'none';
        setTimeout(() => { if (chatMobileScreen) chatMobileScreen.classList.remove('hidden'); }, 50);
    }
}

function closeChat() {
    if (window.innerWidth >= 768) {
        if (chatModal) chatModal.style.display = 'none';
    } else {
        if (chatMobileScreen) chatMobileScreen.classList.add('hidden');
        if(window.innerWidth < 768 && mobileNav) mobileNav.style.display = 'flex';
        setTimeout(() => { if (homeScreen) homeScreen.classList.remove('hidden'); }, 50);
    }
}

window.addEventListener('resize', () => {
    if (window.innerWidth >= 768) {
        if (mobileNav) mobileNav.style.display = 'none';
        if (chatMobileScreen) chatMobileScreen.classList.add('hidden');
        if (homeScreen) homeScreen.classList.remove('hidden');
        if(!pieChartInstance) fetchDashboardMetrics();
    } else {
        if (chatModal && chatModal.style.display === 'flex') closeChat();
        if (chatMobileScreen && chatMobileScreen.classList.contains('hidden') && mobileNav) mobileNav.style.display = 'flex';
    }
});
