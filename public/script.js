    const API_BASE = 'http://localhost:8000/api';
    const COMERCIO_ID = 'COM001'; 

    document.addEventListener("DOMContentLoaded", () => {
        fetchAlertaProactiva();
        if (window.innerWidth >= 768) fetchDashboardMetrics();
    });

    async function fetchAlertaProactiva() {
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
        try {
            const res = await fetch(`${API_BASE}/comercio/${COMERCIO_ID}`);
            if (!res.ok) throw new Error("Comercio no encontrado");
            const data = await res.json();
            
            document.getElementById('kpi-ventas').textContent = `$${data.metricas.total_ventas.toLocaleString()}`;
            document.getElementById('kpi-ticket').textContent = `$${data.metricas.ticket_promedio}`;
            document.getElementById('kpi-tx').textContent = data.metricas.total_transacciones.toLocaleString();

            const metodos = Object.keys(data.metodos_pago.porcentajes);
            const valores = Object.values(data.metodos_pago.porcentajes);
            renderPieChart(metodos, valores);
        } catch (error) {
            console.error("Error cargando dashboard:", error);
        }
    }

    function renderPieChart(labels, data) {
        const ctx = document.getElementById('dashboardPieChart').getContext('2d');
        if (pieChartInstance) pieChartInstance.destroy(); 
        
        Chart.defaults.color = '#94a3b8';
        
        pieChartInstance = new Chart(ctx, {
            type: 'doughnut', 
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: ['#14b8a6', '#8b5cf6', '#f59e0b', '#ef4444'], 
                    borderWidth: 2, 
                    borderColor: '#1c1c1c'
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                cutout: '65%',
                plugins: { 
                    legend: { 
                        position: 'bottom', 
                        labels: { color: '#f8fafc', padding: 20, boxWidth: 12, usePointStyle: true, font: { size: 13, family: 'Inter' } } 
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

        appendMessage(text, 'user', chatArea);
        inputField.value = '';

        const loaderId = 'loader-' + Date.now();
        appendMessage('<i class="fa-solid fa-circle-notch fa-spin"></i> Analizando datos...', 'bot', chatArea, loaderId);

        try {
            const res = await fetch(`${API_BASE}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mensaje: text, id_comercio: COMERCIO_ID })
            });
            const data = await res.json();
            
            document.getElementById(loaderId).remove();
            
            if(res.ok) {
                appendMessage(data.respuesta, 'bot', chatArea);
            } else {
                appendMessage(data.detail || "Hubo un error al procesar tu solicitud.", 'bot', chatArea);
            }
        } catch (error) {
            document.getElementById(loaderId).remove();
            appendMessage("No se pudo conectar a la API en localhost:8000.", 'bot', chatArea);
        }
    }

    function appendMessage(text, sender, chatArea, id = null) {
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
        if (window.innerWidth >= 768) {
            chatModal.style.display = 'flex';
        } else {
            homeScreen.classList.add('hidden');
            mobileNav.style.display = 'none';
            setTimeout(() => chatMobileScreen.classList.remove('hidden'), 50);
        }
    }

    function closeChat() {
        if (window.innerWidth >= 768) {
            chatModal.style.display = 'none';
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
            if (chatModal.style.display === 'flex') closeChat();
            if (chatMobileScreen.classList.contains('hidden')) mobileNav.style.display = 'flex';
        }
    });