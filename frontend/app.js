(function() {
    // Keep exact DOM bindings but expand for new elements safely
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
        dbFile: document.getElementById("dbFile"),

        // New elements
        sidebar: document.getElementById("main-sidebar"),
        btnToggleView: document.getElementById("btn-toggle-view"),
        toggleViewText: document.getElementById("toggle-view-text"),
        dataGridContainer: document.getElementById("data-grid-container"),
        dataGridBody: document.getElementById("data-grid-body"),

        // Filters
        filterDate: document.getElementById("filter-date"),
        filterSegment: document.getElementById("filter-segment"),

        // Chart panels
        chartRetention: document.getElementById("chart-container-retention"),
        chartRevenue: document.getElementById("chart-container-revenue"),
        chartTraffic: document.getElementById("chart-container-traffic"),
    };

    let idToken = null;
    let ws = null;
    let isSignedIn = false;
    let trendChart = null;
    let revenueChart = null;
    let trafficChart = null;

    // ----- VIEW TOGGLE -----
    if(DOM.btnToggleView) {
        DOM.btnToggleView.onclick = () => {
            const isHidden = DOM.sidebar.classList.contains("w-0");
            if (isHidden) {
                DOM.sidebar.classList.remove("w-0", "opacity-0", "px-0");
                DOM.sidebar.classList.add("w-72");
                DOM.toggleViewText.textContent = "View as Webpage";
            } else {
                DOM.sidebar.classList.remove("w-72");
                DOM.sidebar.classList.add("w-0", "opacity-0", "px-0");
                DOM.toggleViewText.textContent = "Show Controls";
            }
        };
    }

    // ----- CHART INITIALIZATION -----
    function initCharts() {
        if(!window.Chart) return;

        Chart.defaults.color = 'rgba(255, 255, 255, 0.7)';
        Chart.defaults.font.family = "'Inter', sans-serif";

        // 1. Retention Trend Chart (Line)
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
                        y: { beginAtZero: true, max: 100, grid: { color: 'rgba(255,255,255,0.05)', drawBorder: false } },
                        x: { grid: { display: false, drawBorder: false } }
                    }
                }
            });
        }

        // 2. Revenue Breakdown (Horizontal Bar)
        const revCtx = document.getElementById('revenueChart')?.getContext('2d');
        if(revCtx) {
            revenueChart = new Chart(revCtx, {
                type: 'bar',
                data: {
                    labels: ['Gaming', 'Tech', 'Vlogs', 'Music', 'Edu'],
                    datasets: [{
                        label: 'Revenue ($K)',
                        data: [120, 95, 80, 60, 45],
                        backgroundColor: 'rgba(16, 185, 129, 0.6)', // emerald-500
                        borderColor: '#10b981',
                        borderWidth: 1,
                        borderRadius: 4
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                        y: { grid: { display: false } }
                    }
                }
            });
        }

        // 3. Traffic Distribution (Doughnut)
        const trafficCtx = document.getElementById('trafficChart')?.getContext('2d');
        if(trafficCtx) {
            trafficChart = new Chart(trafficCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Organic', 'Direct', 'Referral', 'Social'],
                    datasets: [{
                        data: [40, 25, 20, 15],
                        backgroundColor: ['#8b5cf6', '#0ea5e9', '#10b981', '#f59e0b'],
                        borderWidth: 0,
                        hoverOffset: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '65%',
                    plugins: {
                        legend: { position: 'right', labels: { boxWidth: 12, font: { size: 10 } } }
                    }
                }
            });
        }
    }

    function animateChartUpdates() {
        // Coordinated animation frame for updating datasets
        if(trendChart) {
            trendChart.data.datasets[0].data = trendChart.data.datasets[0].data.map(v => Math.max(10, Math.min(100, v + (Math.random()*20 - 10))));
            trendChart.update();
        }
        if(revenueChart) {
            revenueChart.data.datasets[0].data = revenueChart.data.datasets[0].data.map(v => Math.max(20, v + (Math.random()*30 - 15)));
            revenueChart.update();
        }
        if(trafficChart) {
            const r1 = Math.random()*20; const r2 = Math.random()*20; const r3 = Math.random()*20; const r4 = 100 - (r1+r2+r3);
            trafficChart.data.datasets[0].data = [r1, r2, r3, r4];
            trafficChart.update();
        }
    }

    // ----- DYNAMIC CONTENT SWITCHING -----
    if(DOM.filterDate && DOM.filterSegment) {
        DOM.filterDate.onchange = animateChartUpdates;
        DOM.filterSegment.onchange = animateChartUpdates;
    }

    function highlightChartIntent(text) {
        const lower = text.toLowerCase();

        // Reset all
        if(DOM.chartRetention) DOM.chartRetention.classList.remove("ring-2", "ring-cyan-400", "shadow-[0_0_15px_rgba(34,211,238,0.5)]", "scale-[1.02]");
        if(DOM.chartRevenue) DOM.chartRevenue.classList.remove("ring-2", "ring-emerald-400", "shadow-[0_0_15px_rgba(16,185,129,0.5)]", "scale-[1.02]");
        if(DOM.chartTraffic) DOM.chartTraffic.classList.remove("ring-2", "ring-purple-400", "shadow-[0_0_15px_rgba(168,85,247,0.5)]", "scale-[1.02]");

        // Highlight based on intent
        if(lower.includes("revenue") || lower.includes("money") || lower.includes("earnings")) {
            if(DOM.chartRevenue) DOM.chartRevenue.classList.add("ring-2", "ring-emerald-400", "shadow-[0_0_15px_rgba(16,185,129,0.5)]", "scale-[1.02]");
        } else if (lower.includes("traffic") || lower.includes("source") || lower.includes("audience")) {
            if(DOM.chartTraffic) DOM.chartTraffic.classList.add("ring-2", "ring-purple-400", "shadow-[0_0_15px_rgba(168,85,247,0.5)]", "scale-[1.02]");
        } else if (lower.includes("retention") || lower.includes("trend")) {
            if(DOM.chartRetention) DOM.chartRetention.classList.add("ring-2", "ring-cyan-400", "shadow-[0_0_15px_rgba(34,211,238,0.5)]", "scale-[1.02]");
        }
    }


    // ----- FIREBASE AUTH (MOCK OR REAL) -----
    function initMockAuth() {
        if(DOM.formEmailAuth) {
            DOM.formEmailAuth.onsubmit = (e) => {
                e.preventDefault();
                idToken = "mock_token_" + Date.now();
                isSignedIn = true;
                enterApp({ email: DOM.inputEmail.value, displayName: "Data Analyst" });
            };
        }
        if(DOM.btnEmailRegister) {
            DOM.btnEmailRegister.onclick = DOM.formEmailAuth.onsubmit;
        }
        if(DOM.btnLogout) {
            DOM.btnLogout.onclick = () => exitApp();
        }
    }

    function enterApp(user) {
        DOM.authGate.classList.add("hidden");
        DOM.appShell.classList.remove("hidden");
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
    if(DOM.chatInput) {
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
    }

    if(DOM.btnSendChat) {
        DOM.btnSendChat.onclick = async () => {
            const text = DOM.chatInput.value.trim();
            if (!text) return;
            appendChat("user", text);
            DOM.chatInput.value = "";
            DOM.chatInput.style.height = "24px";

            highlightChartIntent(text);

            try {
                const res = await fetch("/api/sandbox/run", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${idToken}` },
                    body: JSON.stringify({ command: text })
                });
                const data = await res.json();
                if(data.output) {
                    appendChat("system", data.output);
                    animateChartUpdates(); // animate charts on success
                }
            } catch(e) {
                appendChat("system", `Error: ${e.message}`);
            }
        };
    }

    // ----- UPLOAD DB FILE & PREVIEW GRID -----
    function renderPreviewGrid(rows) {
        if(!DOM.dataGridContainer || !DOM.dataGridBody) return;
        DOM.dataGridBody.innerHTML = "";
        rows.forEach(row => {
            const tr = document.createElement("tr");
            tr.className = "hover:bg-white/5 transition-colors";
            tr.innerHTML = `
                <td class="px-4 py-3 border-r border-white/5 font-mono text-xs text-slate-400">${row.User_ID || "-"}</td>
                <td class="px-4 py-3 border-r border-white/5 text-cyan-300">${row.Platform || "-"}</td>
                <td class="px-4 py-3 border-r border-white/5">
                    <div class="flex items-center gap-2">
                        <div class="w-16 h-1.5 bg-white/10 rounded-full overflow-hidden">
                            <div class="h-full ${parseFloat(row.Retention_Rate) > 50 ? 'bg-emerald-500' : 'bg-red-500'}" style="width: ${row.Retention_Rate}%"></div>
                        </div>
                        <span class="text-xs text-slate-300">${row.Retention_Rate}%</span>
                    </div>
                </td>
                <td class="px-4 py-3 text-right font-medium text-emerald-400">$${parseFloat(row.Revenue).toFixed(2) || "0.00"}</td>
            `;
            DOM.dataGridBody.appendChild(tr);
        });

        // Show the grid container with a smooth fade in
        DOM.dataGridContainer.classList.remove("hidden");
        DOM.dataGridContainer.classList.add("fade-in");
    }

    if(DOM.btnUploadDb) {
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
                    const data = await res.json();
                    DOM.btnUploadDb.textContent = "Uploaded!";
                    DOM.headerStatus.textContent = "Database Connected";

                    // Render preview grid if backend sent data
                    if(data.preview_data && Array.isArray(data.preview_data)) {
                        renderPreviewGrid(data.preview_data);
                    }

                    appendChat("system", `**Dataset Uploaded:** \`${file.name}\` successfully ingested into the secure analytics sandbox. Sample isolated data grid populated below charts.`);
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
    }

    // ----- CHAT RENDERER -----
    function appendChat(role, text) {
        if(!DOM.chatHistory) return;
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
