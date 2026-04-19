// Detecta automáticamente la IP o el dominio desde el que estás accediendo
const host = window.location.hostname || 'localhost';
const API_BASE = `http://${host}:5000/api`;

let COMERCIO_ID = null;
let saldoVisible = true;
let saldoActual = 0;
let nombreComercio = '';

let selectedAccountTemp = 'COM001';
let comerciosDisponibles = [];
const accountBalances = {};

// Historial de chat separado por comercio (clave: comercio_id, valor: array de mensajes)
const chatHistoriesByComercio = {};
let currentChatHistory = [];

function getInitials(nombre) {
    return nombre
        .split(' ')
        .map(word => word[0])
        .join('')
        .substring(0, 2)
        .toUpperCase();
}

document.addEventListener("DOMContentLoaded", async () => {
    // Cargar comercios disponibles desde el servidor
    await loadAccountOptions();
    if (comerciosDisponibles.length > 0) {
        cambiarCuenta(comerciosDisponibles[0].comercio.id);
    }
});

async function loadAccountOptions() {
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
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeAccountModal(event) {
    if (event && event.target !== event.currentTarget) return;
    const modal = document.getElementById('accountModal');
    modal.classList.remove('active');
    document.body.style.overflow = '';
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
    if (!selectedAccountTemp && comerciosDisponibles.length > 0) {
        selectedAccountTemp = comerciosDisponibles[0].comercio.id;
    }
    await cambiarCuenta(selectedAccountTemp);
    const badge = document.getElementById('current-account-badge');
    if (badge) badge.textContent = selectedAccountTemp;
    closeAccountModal();
    showMockMessage(`Cuenta cambiada a ${selectedAccountTemp}`);
}

async function cambiarCuenta(idComercio) {
    // Si ya hay un comercio activo, guardar su historial de chat
    if (COMERCIO_ID && COMERCIO_ID !== idComercio) {
        chatHistoriesByComercio[COMERCIO_ID] = [...currentChatHistory];
    }

    COMERCIO_ID = idComercio;

    // Limpiar las áreas de chat y cargar historial del nuevo comercio
    clearChatAreas();
    currentChatHistory = chatHistoriesByComercio[COMERCIO_ID] || [];
    renderChatHistory();

    try {
        const res = await fetch(`${API_BASE}/comercio/${COMERCIO_ID}`);
        if (!res.ok) throw new Error("Comercio no encontrado");
        const data = await res.json();

        saldoActual = data.metricas.saldo_actual;
        nombreComercio = data.comercio.nombre;

        document.getElementById('balance-label-cuenta').textContent = `Cuenta: ${nombreComercio}`;
        document.getElementById('balance-cuenta-info').textContent = `${data.comercio.categoria} • ${data.comercio.ciudad}`;
        const currentBadge = document.getElementById('current-account-badge');
        if (currentBadge) currentBadge.textContent = COMERCIO_ID;
        actualizarSaldoUI();

        await fetchAlertaProactiva();
        if (window.innerWidth >= 768) await fetchDashboardMetrics();

    } catch (error) {
        console.error("Error al cargar cuenta:", error);
        document.getElementById('balance-label-cuenta').textContent = "Error al cargar cuenta";
    }
}

// Limpiar ambas áreas de chat (PC y móvil)
function clearChatAreas() {
    const modalChatArea = document.getElementById('modal-chat-messages');
    const mobileChatArea = document.getElementById('mobile-chat-messages');

    // Guardar los mensajes del sistema (bienvenida) pero limpiar el resto
    if (modalChatArea) {
        const systemMessages = modalChatArea.querySelectorAll('.message.bot');
        modalChatArea.innerHTML = '';
        // Re-agregar mensaje de bienvenida
        addWelcomeMessage(modalChatArea);
    }

    if (mobileChatArea) {
        const systemMessages = mobileChatArea.querySelectorAll('.message.bot');
        mobileChatArea.innerHTML = '';
        // Re-agregar mensaje de bienvenida
        addWelcomeMessage(mobileChatArea);
    }
}

// Agregar mensaje de bienvenida específico del comercio
function addWelcomeMessage(chatArea) {
    const welcomeDiv = document.createElement('div');
    welcomeDiv.className = 'message bot';
    const nombre = nombreComercio || 'tu negocio';
    welcomeDiv.innerHTML = `¡Hola! Soy tu Contador de Bolsillo 🤖. Estoy aquí para ayudarte con <strong>${nombre}</strong>. ¿Qué te gustaría saber hoy?`;
    chatArea.appendChild(welcomeDiv);
}

// Renderizar el historial de chat actual
function renderChatHistory() {
    const modalChatArea = document.getElementById('modal-chat-messages');
    const mobileChatArea = document.getElementById('mobile-chat-messages');

    currentChatHistory.forEach(msg => {
        if (modalChatArea) {
            appendMessageToArea(msg.text, msg.sender, modalChatArea);
        }
        if (mobileChatArea) {
            appendMessageToArea(msg.text, msg.sender, mobileChatArea);
        }
    });
}

// Función auxiliar para agregar mensaje a un área específica sin agregar al historial
function appendMessageToArea(text, sender, chatArea) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}`;

    if (sender === 'bot' && !text.includes('fa-circle-notch')) {
        marked.setOptions({ breaks: true });
        msgDiv.innerHTML = marked.parse(text);
    } else {
        msgDiv.textContent = text;
        if(text.includes('fa-circle-notch')) msgDiv.innerHTML = text;
    }

    chatArea.appendChild(msgDiv);
    chatArea.scrollTo({
        top: chatArea.scrollHeight,
        behavior: 'smooth'
    });
}

function toggleSaldoVisibility() {
    saldoVisible = !saldoVisible;
    const eyeIcon = document.getElementById('eye-icon');
    eyeIcon.className = saldoVisible ? 'fa-regular fa-eye-slash' : 'fa-regular fa-eye';
    actualizarSaldoUI();
}

function actualizarSaldoUI() {
    const balanceElement = document.getElementById('balance-amount-value');
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
        
        let bg = 'rgba(0, 210, 185, 0.1)';
        let color = 'var(--text-primary)';
        let border = 'rgba(0, 210, 185, 0.3)';
        let iconColor = 'var(--deuna-turquoise)';
        let icon;

        if (data.tipo === 'positiva') { icon = 'fa-arrow-trend-up'; }
        else if (data.tipo === 'negativa') { icon = 'fa-arrow-trend-down'; iconColor = '#EF4444'; bg = 'rgba(239, 68, 68, 0.05)'; border = 'rgba(239, 68, 68, 0.2)'; }
        else { icon = 'fa-lightbulb'; iconColor = 'var(--deuna-purple)'; bg = 'rgba(76, 29, 128, 0.05)'; border = 'rgba(76, 29, 128, 0.15)'; }

        const badgeHTML = `
            <div class="proactive-badge" style="background:${bg}; color:${color}; border-color:${border};" onclick="askAboutAlert('${data.titulo}')">
                <i class="fa-solid ${icon}" style="color: ${iconColor};"></i>
                <span><strong style="color: ${iconColor};">${data.titulo}</strong> ${data.descripcion}</span>
            </div>`;
        
        document.getElementById('proactive-badge-pc').innerHTML = badgeHTML;
        document.getElementById('proactive-badge-mobile').innerHTML = badgeHTML;
    } catch (error) {
        console.error("Fallo carga alerta proactiva:", error);
    }
}

function askAboutAlert(titulo) {
    const input = window.innerWidth >= 768 ? document.getElementById('modal-user-input') : document.getElementById('mobile-user-input');
    input.value = `Dime más sobre esto: ${titulo}`;
    window.innerWidth >= 768 ? sendMessageModal() : sendMessageMobile();
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

        document.getElementById('kpi-ventas').textContent = `$${ventas.toLocaleString()}`;
        document.getElementById('kpi-ticket').textContent = `$${ticket}`;
        document.getElementById('kpi-tx').textContent = tx.toLocaleString();

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
    const ctx = document.getElementById('dashboardPieChart').getContext('2d');
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

const modalInput = document.getElementById('modal-user-input');
const mobileInput = document.getElementById('mobile-user-input');
const modalChatArea = document.getElementById('modal-chat-messages');
const mobileChatArea = document.getElementById('mobile-chat-messages');

modalInput.addEventListener('keypress', e => { if(e.key === 'Enter') sendMessageModal(); });
mobileInput.addEventListener('keypress', e => { if(e.key === 'Enter') sendMessageMobile(); });

function sendMessageModal() { sendChatToAPI(modalInput, modalChatArea); }
function sendMessageMobile() { sendChatToAPI(mobileInput, mobileChatArea); }

async function sendChatToAPI(inputField, chatArea) {
    const text = inputField.value.trim();
    if (!text) return;

    // Guardar mensaje del usuario en historial
    appendMessage(text, 'user', chatArea);
    currentChatHistory.push({ text: text, sender: 'user', timestamp: Date.now() });
    inputField.value = '';

    const loaderId = 'loader-' + Date.now();
    appendMessage('<i class="fa-solid fa-circle-notch fa-spin"></i> Analizando datos...', 'bot', chatArea, loaderId);

    try {
        // Preparar historial para enviar al backend
        const historialParaBackend = currentChatHistory.slice(-20).map(msg => ({
            role: msg.sender === 'user' ? 'user' : 'assistant',
            content: msg.text
        }));

        const res = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mensaje: text,
                id_comercio: COMERCIO_ID,
                historial: historialParaBackend
            })
        });
        const data = await res.json();

        document.getElementById(loaderId).remove();

        if(res.ok) {
            appendMessage(data.respuesta, 'bot', chatArea);
            currentChatHistory.push({ text: data.respuesta, sender: 'bot', timestamp: Date.now() });
        } else {
            const errorMsg = data.detail || "Hubo un error al procesar tu solicitud.";
            appendMessage(errorMsg, 'bot', chatArea);
            currentChatHistory.push({ text: errorMsg, sender: 'bot', timestamp: Date.now(), isError: true });
        }

        // Guardar historial actualizado
        chatHistoriesByComercio[COMERCIO_ID] = [...currentChatHistory];

    } catch (error) {
        document.getElementById(loaderId).remove();
        const errorMsg = `No se pudo conectar a la API en ${API_BASE}. Asegúrate de que el servidor esté corriendo.`;
        appendMessage(errorMsg, 'bot', chatArea);
        currentChatHistory.push({ text: errorMsg, sender: 'bot', timestamp: Date.now(), isError: true });
    }
}

function appendMessage(text, sender, chatArea, id = null) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}`;
    if (id) msgDiv.id = id;

    // Si el mensaje es del bot y NO es el ícono de carga, convertimos de Markdown a HTML
    if (sender === 'bot' && !text.includes('fa-circle-notch')) {
        // Configuramos marked para que rompa líneas de forma natural
        marked.setOptions({ breaks: true });
        msgDiv.innerHTML = marked.parse(text);
    } else {
        // Si es el usuario o el loader, va como texto plano
        msgDiv.textContent = text;
        // Excepción para el HTML del loader
        if(text.includes('fa-circle-notch')) msgDiv.innerHTML = text;
    }

    chatArea.appendChild(msgDiv);

    // Usar scroll behavior smooth para que baje fluidamente
    chatArea.scrollTo({
        top: chatArea.scrollHeight,
        behavior: 'smooth'
    });
}

let toastTimeout;
function showMockMessage(featureName) {
    const toast = document.getElementById('toastMessage');
    toast.textContent = `Demo: Clic en "${featureName}"`;
    toast.classList.add('show');
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => toast.classList.remove('show'), 2000);
}

const homeScreen = document.getElementById('screen-home');
const chatMobileScreen = document.getElementById('screen-chat-mobile');
const mobileNav = document.getElementById('mobile-nav');
const chatModal = document.getElementById('chatModal');

function openChat() {
    // Asegurar que el historial del comercio actual esté cargado
    currentChatHistory = chatHistoriesByComercio[COMERCIO_ID] || [];

    if (window.innerWidth >= 768) {
        chatModal.classList.add('active');
    } else {
        homeScreen.classList.add('hidden');
        mobileNav.style.display = 'none';
        setTimeout(() => chatMobileScreen.classList.remove('hidden'), 50);
    }
}

function closeChat() {
    if (window.innerWidth >= 768) {
        chatModal.classList.remove('active');
    } else {
        chatMobileScreen.classList.add('hidden');
        if(window.innerWidth < 768) mobileNav.style.display = 'flex';
        setTimeout(() => homeScreen.classList.remove('hidden'), 50);
    }
}

window.addEventListener('resize', () => {
    if (window.innerWidth >= 768) {
        mobileNav.style.display = 'none';
        chatMobileScreen.classList.add('hidden');
        homeScreen.classList.remove('hidden');
        if(!pieChartInstance) fetchDashboardMetrics();
    } else {
        if (chatModal.classList.contains('active')) closeChat();
        if (chatMobileScreen.classList.contains('hidden')) mobileNav.style.display = 'flex';
    }
});