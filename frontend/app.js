(function() {
    const DOM = {
        authGate: document.getElementById("auth-gate"),
        appShell: document.getElementById("app-shell"),
        formEmailAuth: document.getElementById("form-email-auth"),
        inputEmail: document.getElementById("input-email"),
        btnEmailRegister: document.getElementById("btn-email-register"),
        userAvatar: document.getElementById("user-avatar"),
        userName: document.getElementById("user-name"),
        btnLogout: document.getElementById("btn-logout"),
        chatHistory: document.getElementById("chat-history"),
        chatInput: document.getElementById("chat-input"),
        btnSendChat: document.getElementById("btn-send-chat"),
        headerCpu: document.getElementById("header-cpu"),
        headerRam: document.getElementById("header-ram"),
        headerStatus: document.getElementById("header-status"),
        btnUploadDb: document.getElementById("btn-upload-db"),
        dbFile: document.getElementById("dbFile")
    };

    let idToken = null;
    let ws = null;
    let isSignedIn = false;
    let trendChart = null;
    let riskChart = null;

    // ----- CHART INITIALIZATION -----
    function initCharts() {
        if(!window.Chart) return;

        Chart.defaults.color = 'rgba(255, 255, 255, 0.7)';
        Chart.defaults.font.family = "'Inter', sans-serif";

        const trendCtx = document.getElementById('trendChart')?.getContext('2d');
        if(trendCtx) {
            trendChart = new Chart(trendCtx, {
                type: 'line',
                data: {
                    labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                    datasets: [{
                        label: 'Retention %',
                        data: [45, 52, 48, 61, 59, 72],
                        borderColor: '#0ea5e9', // cyan-500
                        backgroundColor: 'rgba(14, 165, 233, 0.1)',
                        borderWidth: 2,
                        tension: 0.4,
                        fill: true,
                        pointBackgroundColor: '#0ea5e9',
                        pointBorderColor: '#fff',
                        pointRadius: 3
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: {
                            beginAtZero: true, max: 100,
                            grid: { color: 'rgba(255,255,255,0.05)', drawBorder: false }
                        },
                        x: {
                            grid: { display: false, drawBorder: false }
                        }
                    }
                }
            });
        }

        const riskCtx = document.getElementById('riskChart')?.getContext('2d');
        if(riskCtx) {
            riskChart = new Chart(riskCtx, {
                type: 'doughnut',
                data: {
                    labels: ['High Risk', 'Medium Risk', 'Low Risk'],
                    datasets: [{
                        data: [22, 36, 42],
                        backgroundColor: ['#f43f5e', '#f59e0b', '#10b981'],
                        borderWidth: 0,
                        hoverOffset: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '75%',
                    plugins: { legend: { display: false }, tooltip: { enabled: true } }
                }
            });
        }
    }

    function updateCharts(data) {
        // Just simulate a change for the visual effect
        if(trendChart) {
            trendChart.data.datasets[0].data = trendChart.data.datasets[0].data.map(v => v + (Math.random()*10 - 5));
            trendChart.update();
        }
    }

    // ----- FIREBASE AUTH (MOCK OR REAL) -----
    function initMockAuth() {
        DOM.formEmailAuth.onsubmit = (e) => {
            e.preventDefault();
            idToken = "mock_token_" + Date.now();
            isSignedIn = true;
            enterApp({ email: DOM.inputEmail.value, displayName: "Data Analyst" });
        };
        DOM.btnEmailRegister.onclick = DOM.formEmailAuth.onsubmit;

        if(DOM.btnLogout) {
            DOM.btnLogout.onclick = () => exitApp();
        }
    }

    function enterApp(user) {
        DOM.authGate.classList.add("hidden");
        DOM.appShell.classList.remove("hidden");
        // Fade in effect
        setTimeout(() => DOM.appShell.classList.remove("opacity-0"), 50);

        DOM.userName.textContent = user.displayName || user.email.split("@")[0];
        DOM.userAvatar.src = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='36' height='36'><rect width='36' height='36' rx='18' fill='%236366f1'/></svg>";

        initCharts();
        connectWebSocket();
        pollTelemetry();
    }

    function exitApp() {
        isSignedIn = false;
        idToken = null;
        DOM.appShell.classList.add("opacity-0");
        setTimeout(() => {
            DOM.appShell.classList.add("hidden");
            DOM.authGate.classList.remove("hidden");
        }, 700);
        if(ws) { ws.close(); ws = null; }
    }

    // ----- TELEMETRY -----
    async function pollTelemetry() {
        if(!isSignedIn) return;
        try {
            const res = await fetch("/api/v1/system/telemetry", { headers: { "Authorization": `Bearer ${idToken}` } });
            if(res.ok) {
                const tel = await res.json();
                DOM.headerCpu.textContent = `Compute: ${tel.system_cpu_load || 0}%`;
                const mem = (tel.system_memory_total || 0) - (tel.system_memory_available || 0);
                DOM.headerRam.textContent = `Memory: ${Math.round(mem / 1024 / 1024)} MB`;
            }
        } catch(e) {}
        setTimeout(pollTelemetry, 5000);
    }

    // ----- CHAT INPUT & SEND -----
    DOM.chatInput.addEventListener('input', function() {
        this.style.height = "24px";
        this.style.height = `${Math.min(this.scrollHeight, 200)}px`;
    });

    DOM.chatInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            DOM.btnSendChat.click();
        }
    });

    DOM.btnSendChat.onclick = async () => {
        const text = DOM.chatInput.value.trim();
        if (!text) return;
        appendChat("user", text);
        DOM.chatInput.value = "";
        DOM.chatInput.style.height = "24px";

        try {
            const res = await fetch("/api/sandbox/run", {
                method: "POST",
                headers: { "Content-Type": "application/json", "Authorization": `Bearer ${idToken}` },
                body: JSON.stringify({ command: text })
            });
            const data = await res.json();
            if(data.output) {
                appendChat("system", data.output);
                updateCharts(data); // animate charts on success
            }
        } catch(e) {
            appendChat("system", `Error: ${e.message}`);
        }
    };

    // ----- UPLOAD DB FILE -----
    DOM.btnUploadDb.onclick = async () => {
        const file = DOM.dbFile.files[0];
        if (!file) {
            alert("Please select a file first.");
            return;
        }

        DOM.btnUploadDb.textContent = "Uploading...";
        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await fetch("/api/sandbox/upload", {
                method: "POST",
                headers: { "Authorization": `Bearer ${idToken}` },
                body: formData
            });

            if(res.ok) {
                DOM.btnUploadDb.textContent = "Uploaded!";
                DOM.headerStatus.textContent = "Database Connected";
                appendChat("system", `**Dataset Uploaded:** \`${file.name}\` successfully ingested into the secure analytics sandbox.`);
                setTimeout(() => DOM.btnUploadDb.textContent = "Upload to Sandbox", 3000);
            } else {
                throw new Error("Upload failed");
            }
        } catch(e) {
            DOM.btnUploadDb.textContent = "Error";
            setTimeout(() => DOM.btnUploadDb.textContent = "Upload to Sandbox", 2000);
            appendChat("system", `**Error:** Failed to upload \`${file.name}\`. ${e.message}`);
        }
    };

    // ----- CHAT RENDERER -----
    function appendChat(role, text) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `chat-message fade-in relative z-10 ${role === "user" ? "" : "agent-message"}`;

        let avatarHTML = role === "user"
            ? `<div class="w-8 h-8 rounded-lg bg-white/10 border border-white/20 flex items-center justify-center flex-shrink-0 text-white shadow-lg"><svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg></div>`
            : `<div class="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center flex-shrink-0 shadow-lg shadow-indigo-500/20"><svg class="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg></div>`;

        let htmlContent = text;
        if(window.marked) {
            htmlContent = marked.parse(text);
        }

        msgDiv.innerHTML = `<div class="flex gap-4 max-w-4xl mx-auto">${avatarHTML}<div class="message-content flex-1 text-slate-300 text-sm leading-relaxed">${htmlContent}</div></div>`;
        DOM.chatHistory.appendChild(msgDiv);
        DOM.chatHistory.scrollTop = DOM.chatHistory.scrollHeight;

        if(window.hljs) {
            msgDiv.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });
        }
    }

    // ----- WEBSOCKET -----
    function connectWebSocket() {
        const wsUrl = `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/api/v1/tunnels/logs/ws?token=${idToken}`;
        ws = new WebSocket(wsUrl);
        ws.onmessage = (event) => {
            if(event.data === "pong") return;
            try {
                const entry = JSON.parse(event.data);
                if(entry.msg && !entry.msg.includes("Telemetry") && !entry.msg.includes("Heartbeat")) {
                     // small toast or silent console log for glassmorphism
                     console.log("System Log: ", entry.msg);
                }
            } catch(e) {}
        };
        ws.onclose = () => {
            if(isSignedIn) setTimeout(connectWebSocket, 3000);
        };
    }

    initMockAuth();
})();
