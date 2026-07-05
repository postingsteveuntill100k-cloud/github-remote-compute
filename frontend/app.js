import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAnalytics } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-analytics.js";
import { getAuth, signInWithEmailAndPassword, createUserWithEmailAndPassword, GoogleAuthProvider, signInWithPopup, onAuthStateChanged, signOut, sendPasswordResetEmail, getRedirectResult, signInWithRedirect } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

const DOM = {
    authGate: document.getElementById("auth-gate"),
    appShell: document.getElementById("app-shell"),
    formEmailAuth: document.getElementById("form-email-auth"),
    inputEmail: document.getElementById("input-email"),
    btnEmailRegister: document.getElementById("btn-email-register"),
    btnGoogleLogin: document.getElementById("btn-google-login"),
    btnForgotPassword: document.getElementById("btn-forgot-password"),
    authSuccess: document.getElementById("auth-success"),
    authError: document.getElementById("auth-error"),
    userAvatar: document.getElementById("user-avatar"),
    userName: document.getElementById("user-name"),
    btnLogout: document.getElementById("btn-logout"),
    chatHistory: document.getElementById("chat-history"),
    chatInput: document.getElementById("chat-input"),
    btnSendChat: document.getElementById("btn-send-chat"),
    headerCpu: document.getElementById("header-cpu"),
    headerRam: document.getElementById("header-ram"),
    headerStatus: document.getElementById("header-status"),
    headerStatusContainer: document.getElementById("header-status-container"),
    btnUploadDb: document.getElementById("btn-upload-db"),
    dbFile: document.getElementById("dbFile"),

    sidebar: document.getElementById("main-sidebar"),
    btnToggleView: document.getElementById("btn-toggle-view"),
    toggleViewText: document.getElementById("toggle-view-text"),
    dataGridContainer: document.getElementById("data-grid-container"),
    dataGridBody: document.getElementById("data-grid-body"),
    btnExportCsv: document.getElementById("btn-export-csv"),
    sortableHeaders: document.querySelectorAll(".sortable-header"),

    btnSettings: document.getElementById("btn-settings"),
    settingsModal: document.getElementById("settings-modal"),
    btnCloseSettings: document.getElementById("btn-close-settings"),
    usageCount: document.getElementById("usage-count"),
    usageRing: document.getElementById("usage-ring"),
    toggleTheme: document.getElementById("toggle-theme"),
    toggleTelemetry: document.getElementById("toggle-telemetry"),
    presetChips: document.querySelectorAll(".preset-chip"),

    filterDate: document.getElementById("filter-date"),
    filterSegment: document.getElementById("filter-segment"),

    chartRetention: document.getElementById("chart-container-retention"),
    chartRevenue: document.getElementById("chart-container-revenue"),
    chartTraffic: document.getElementById("chart-container-traffic")
};

let idToken = null;
let ws = null;
let isSignedIn = false;
let trendChart = null;
let revenueChart = null;
let trafficChart = null;
let gridData = [];
let currentSort = { column: null, direction: 'asc' };

let tokensUsed = 0;
const MAX_TOKENS = 50;

// ----- SETTINGS & TELEMETRY -----
function updateUsageRing(newTokens) {
    tokensUsed += newTokens;
    if(tokensUsed > MAX_TOKENS) tokensUsed = MAX_TOKENS;
    if(DOM.usageCount) DOM.usageCount.textContent = tokensUsed;
    if(DOM.usageRing) {
        const percentage = (tokensUsed / MAX_TOKENS) * 100;
        const offset = 100 - percentage;
        DOM.usageRing.style.strokeDashoffset = offset;
        if (percentage >= 100) DOM.usageRing.classList.replace("text-cyan-400", "text-red-500");
    }
}

if(DOM.btnSettings) {
    DOM.btnSettings.onclick = () => {
        DOM.settingsModal.classList.remove("hidden");
        setTimeout(() => DOM.settingsModal.classList.remove("opacity-0"), 10);
    };
}

if(DOM.btnCloseSettings) {
    DOM.btnCloseSettings.onclick = () => {
        DOM.settingsModal.classList.add("opacity-0");
        setTimeout(() => DOM.settingsModal.classList.add("hidden"), 300);
    };
}

if(DOM.toggleTheme) {
    DOM.toggleTheme.onchange = (e) => {
        let s = JSON.parse(localStorage.getItem("app_settings") || "{}");
        s.darkOverride = e.target.checked;
        localStorage.setItem("app_settings", JSON.stringify(s));
    };
    const saved = localStorage.getItem("app_settings");
    if(saved) {
        try {
            const s = JSON.parse(saved);
            DOM.toggleTheme.checked = s.darkOverride;
        } catch(e){}
    }
}

if(DOM.presetChips) {
    DOM.presetChips.forEach(chip => {
        chip.onclick = () => {
            if(DOM.chatInput) DOM.chatInput.value = chip.textContent;
        };
    });
}

// ----- VIEW TOGGLE -----
if(DOM.btnToggleView) {
    DOM.btnToggleView.onclick = () => {
        const isHidden = DOM.sidebar.classList.contains("w-0");
        if (isHidden) {
            DOM.sidebar.classList.remove("w-0", "opacity-0", "px-0", "border-0");
            DOM.sidebar.classList.add("w-80");
            DOM.toggleViewText.textContent = "Full Canvas";
        } else {
            DOM.sidebar.classList.remove("w-80");
            DOM.sidebar.classList.add("w-0", "opacity-0", "px-0", "border-0");
            DOM.toggleViewText.textContent = "Show Controls";
        }
    };
}

// ----- DYNAMIC TELEMETRY SPIKES -----
let spikeInterval = null;
function startTelemetrySpike() {
    if(DOM.headerCpu) {
        DOM.headerCpu.classList.add("text-red-400", "drop-shadow-[0_0_8px_rgba(248,113,113,0.8)]");
        DOM.headerCpu.classList.remove("text-cyan-200");
        DOM.headerCpu.previousElementSibling.classList.replace("bg-cyan-500", "bg-red-500");
        DOM.headerCpu.previousElementSibling.classList.replace("shadow-[0_0_8px_rgba(6,182,212,0.8)]", "shadow-[0_0_8px_rgba(248,113,113,0.8)]");
    }
    if(DOM.headerRam) {
        DOM.headerRam.classList.add("text-orange-400", "drop-shadow-[0_0_8px_rgba(251,146,60,0.8)]");
        DOM.headerRam.classList.remove("text-purple-200");
        DOM.headerRam.previousElementSibling.classList.replace("bg-purple-500", "bg-orange-500");
        DOM.headerRam.previousElementSibling.classList.replace("shadow-[0_0_8px_rgba(168,85,247,0.8)]", "shadow-[0_0_8px_rgba(251,146,60,0.8)]");
    }

    spikeInterval = setInterval(() => {
        if(DOM.headerCpu) DOM.headerCpu.textContent = `Compute: ${Math.floor(Math.random() * 15 + 85)}%`;
        if(DOM.headerRam) DOM.headerRam.textContent = `Mem: ${Math.floor(Math.random() * 150 + 800)}MB`;
    }, 300);
}

function stopTelemetrySpike() {
    if(spikeInterval) { clearInterval(spikeInterval); spikeInterval = null; }
    if(DOM.headerCpu) {
        DOM.headerCpu.classList.remove("text-red-400", "drop-shadow-[0_0_8px_rgba(248,113,113,0.8)]");
        DOM.headerCpu.classList.add("text-cyan-200");
        DOM.headerCpu.previousElementSibling.classList.replace("bg-red-500", "bg-cyan-500");
        DOM.headerCpu.previousElementSibling.classList.replace("shadow-[0_0_8px_rgba(248,113,113,0.8)]", "shadow-[0_0_8px_rgba(6,182,212,0.8)]");
    }
    if(DOM.headerRam) {
        DOM.headerRam.classList.remove("text-orange-400", "drop-shadow-[0_0_8px_rgba(251,146,60,0.8)]");
        DOM.headerRam.classList.add("text-purple-200");
        DOM.headerRam.previousElementSibling.classList.replace("bg-orange-500", "bg-purple-500");
        DOM.headerRam.previousElementSibling.classList.replace("shadow-[0_0_8px_rgba(251,146,60,0.8)]", "shadow-[0_0_8px_rgba(168,85,247,0.8)]");
    }
    pollTelemetry();
}

function showSkeletonLoader() {
    startTelemetrySpike();
    if(!DOM.chatHistory) return null;
    const msgDiv = document.createElement("div");
    msgDiv.className = "chat-message agent-message relative z-10 fade-in";
    msgDiv.id = "chat-skeleton-loader";
    msgDiv.innerHTML = `
        <div class="flex gap-4">
            <div class="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500/50 to-purple-600/50 flex items-center justify-center flex-shrink-0 border border-white/10 animate-pulse">
                <svg class="w-4 h-4 text-white/50" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            </div>
            <div class="flex-1 glass-panel p-4 rounded-2xl rounded-tl-sm border border-white/5 shadow-md">
                <div class="h-2 w-32 skeleton-wave rounded-full mb-3"></div>
                <div class="space-y-2">
                    <div class="h-1.5 w-full skeleton-wave rounded-full"></div>
                    <div class="h-1.5 w-[85%] skeleton-wave rounded-full"></div>
                    <div class="h-1.5 w-[60%] skeleton-wave rounded-full"></div>
                </div>
            </div>
        </div>`;
    DOM.chatHistory.appendChild(msgDiv);
    DOM.chatHistory.scrollTop = DOM.chatHistory.scrollHeight;
    return msgDiv;
}

function removeSkeletonLoader() {
    stopTelemetrySpike();
    const loader = document.getElementById("chat-skeleton-loader");
    if(loader) loader.remove();
}

// ----- CHART INITIALIZATION -----
function initCharts() {
    if(!window.Chart) return;

    if (trendChart) { trendChart.destroy(); }
    if (revenueChart) { revenueChart.destroy(); }
    if (trafficChart) { trafficChart.destroy(); }

    Chart.defaults.color = 'rgba(255, 255, 255, 0.6)';
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(15, 23, 42, 0.9)';
    Chart.defaults.plugins.tooltip.titleColor = '#38bdf8';
    Chart.defaults.plugins.tooltip.bodyColor = '#f8fafc';
    Chart.defaults.plugins.tooltip.borderColor = 'rgba(56, 189, 248, 0.3)';
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
    Chart.defaults.plugins.tooltip.displayColors = false;

    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 1200, easing: 'easeOutQuart' },
        hover: { mode: 'nearest', intersect: true },
        plugins: { legend: { display: false } }
    };

    const trendCtx = document.getElementById('trendChart')?.getContext('2d');
    if(trendCtx) {
        trendChart = new Chart(trendCtx, {
            type: 'line',
            data: {
                labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                datasets: [{
                    label: 'Retention %',
                    data: [45, 52, 48, 61, 59, 72],
                    borderColor: '#06b6d4', // cyan-500
                    backgroundColor: 'rgba(6, 182, 212, 0.15)',
                    borderWidth: 2.5,
                    tension: 0.4,
                    fill: true,
                    pointBackgroundColor: '#06b6d4',
                    pointBorderColor: '#fff',
                    pointRadius: 3,
                    pointHoverRadius: 6,
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: '#06b6d4',
                    pointHoverBorderWidth: 2
                }]
            },
            options: {
                ...commonOptions,
                scales: {
                    y: { beginAtZero: true, max: 100, grid: { color: 'rgba(255,255,255,0.05)', drawBorder: false } },
                    x: { grid: { display: false, drawBorder: false } }
                }
            }
        });
    }

    const revCtx = document.getElementById('revenueChart')?.getContext('2d');
    if(revCtx) {
        revenueChart = new Chart(revCtx, {
            type: 'bar',
            data: {
                labels: ['Gaming', 'Tech', 'Vlogs', 'Music', 'Edu'],
                datasets: [{
                    label: 'Revenue ($K)',
                    data: [120, 95, 80, 60, 45],
                    backgroundColor: 'rgba(16, 185, 129, 0.7)', // emerald-500
                    hoverBackgroundColor: '#10b981',
                    borderColor: 'transparent',
                    borderWidth: 0,
                    borderRadius: 6
                }]
            },
            options: {
                ...commonOptions,
                indexAxis: 'y',
                scales: {
                    x: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)', drawBorder: false } },
                    y: { grid: { display: false, drawBorder: false } }
                }
            }
        });
    }

    const trafficCtx = document.getElementById('trafficChart')?.getContext('2d');
    if(trafficCtx) {
        trafficChart = new Chart(trafficCtx, {
            type: 'doughnut',
            data: {
                labels: ['Organic', 'Direct', 'Referral', 'Social'],
                datasets: [{
                    data: [40, 25, 20, 15],
                    backgroundColor: ['#8b5cf6', '#06b6d4', '#10b981', '#f59e0b'],
                    borderWidth: 2,
                    borderColor: '#1e1b2e',
                    hoverOffset: 8
                }]
            },
            options: {
                ...commonOptions,
                cutout: '65%',
                plugins: {
                    legend: { display: true, position: 'right', labels: { boxWidth: 10, font: { size: 10, family: "'Inter', sans-serif" }, color: 'rgba(255,255,255,0.7)' } }
                }
            }
        });
    }
}

function animateChartUpdates(dataObj = null) {
    if (dataObj && dataObj.charts) {
        if(trendChart && dataObj.charts.trend) {
            trendChart.data.datasets[0].data = dataObj.charts.trend;
            trendChart.update();
        }
        if(revenueChart && dataObj.charts.revenue) {
            revenueChart.data.datasets[0].data = dataObj.charts.revenue;
            revenueChart.update();
        }
        if(trafficChart && dataObj.charts.traffic) {
            trafficChart.data.datasets[0].data = dataObj.charts.traffic;
            trafficChart.update();
        }
    } else {
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
}

if(DOM.filterDate && DOM.filterSegment) {
    DOM.filterDate.onchange = () => animateChartUpdates();
    DOM.filterSegment.onchange = () => animateChartUpdates();
}

function highlightChartIntent(text) {
    const lower = text.toLowerCase();
    if(DOM.chartRetention) DOM.chartRetention.classList.remove("chart-highlight-retention");
    if(DOM.chartRevenue) DOM.chartRevenue.classList.remove("chart-highlight-revenue");
    if(DOM.chartTraffic) DOM.chartTraffic.classList.remove("chart-highlight-traffic");

    if(lower.includes("revenue") || lower.includes("money") || lower.includes("earnings") || lower.includes("breakdown")) {
        if(DOM.chartRevenue) DOM.chartRevenue.classList.add("chart-highlight-revenue");
    } else if (lower.includes("traffic") || lower.includes("source") || lower.includes("audience") || lower.includes("distribution")) {
        if(DOM.chartTraffic) DOM.chartTraffic.classList.add("chart-highlight-traffic");
    } else if (lower.includes("retention") || lower.includes("trend") || lower.includes("risk")) {
        if(DOM.chartRetention) DOM.chartRetention.classList.add("chart-highlight-retention");
    }
}

// ----- UPLOAD DB FILE & PREVIEW GRID -----
function sortGridData(column) {
    if (currentSort.column === column) {
        currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
    } else {
        currentSort.column = column;
        currentSort.direction = 'asc';
    }

    gridData.sort((a, b) => {
        let valA = a[column];
        let valB = b[column];

        if (!isNaN(parseFloat(valA))) valA = parseFloat(valA);
        if (!isNaN(parseFloat(valB))) valB = parseFloat(valB);

        if (valA < valB) return currentSort.direction === 'asc' ? -1 : 1;
        if (valA > valB) return currentSort.direction === 'asc' ? 1 : -1;
        return 0;
    });

    if(DOM.sortableHeaders) {
        DOM.sortableHeaders.forEach(th => {
            th.classList.remove('asc', 'desc');
            if (th.dataset.sort === column) {
                th.classList.add(currentSort.direction);
            }
        });
    }

    renderPreviewGrid(gridData);
}

if(DOM.sortableHeaders) {
    DOM.sortableHeaders.forEach(th => {
        th.onclick = () => sortGridData(th.dataset.sort);
    });
}

if(DOM.btnExportCsv) {
    DOM.btnExportCsv.onclick = () => {
        if(!gridData.length) return;
        const headers = Object.keys(gridData[0]).join(",");
        const rows = gridData.map(obj => Object.values(obj).join(",")).join("\n");
        const csvContent = headers + "\n" + rows;
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.setAttribute("href", url);
        link.setAttribute("download", "data_export.csv");
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };
}

function renderPreviewGrid(rows) {
    if(!DOM.dataGridContainer || !DOM.dataGridBody) return;
    DOM.dataGridBody.innerHTML = "";
    rows.forEach(row => {
        const tr = document.createElement("tr");
        tr.className = "hover:bg-white/5 transition-colors";
        tr.innerHTML = `
            <td class="px-6 py-4 border-r border-white/5 font-mono text-xs text-slate-400">${row.User_ID || "-"}</td>
            <td class="px-6 py-4 border-r border-white/5 text-cyan-300 text-sm font-medium">${row.Platform || "-"}</td>
            <td class="px-6 py-4 border-r border-white/5">
                <div class="flex items-center gap-3">
                    <div class="w-24 h-1.5 bg-black/60 rounded-full overflow-hidden shadow-inner">
                        <div class="h-full rounded-full transition-all duration-1000 ${parseFloat(row.Retention_Rate) > 50 ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]' : 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]'}" style="width: ${row.Retention_Rate}%"></div>
                    </div>
                    <span class="text-xs text-slate-300 font-mono">${row.Retention_Rate}%</span>
                </div>
            </td>
            <td class="px-6 py-4 text-right font-mono text-emerald-400 text-sm">$${parseFloat(row.Revenue).toFixed(2) || "0.00"}</td>
        `;
        DOM.dataGridBody.appendChild(tr);
    });

    DOM.dataGridContainer.classList.remove("hidden");
    DOM.dataGridContainer.classList.add("fade-in");
}

if(DOM.btnUploadDb) {
    DOM.btnUploadDb.onclick = async () => {
        if(DOM.dbFile && !DOM.dbFile.files[0]) {
            alert("Please select a file first.");
            return;
        }

        DOM.btnUploadDb.textContent = "Uploading...";
        const formData = new FormData();
        formData.append("file", DOM.dbFile.files[0]);

        try {
            const res = await fetch("/api/sandbox/upload", {
                method: "POST",
                headers: { "Authorization": `Bearer ${idToken}` },
                body: formData
            });

            if(res.ok) {
                const data = await res.json();
                DOM.btnUploadDb.textContent = "Uploaded!";

                if(DOM.headerStatus) DOM.headerStatus.textContent = "Database Connected";
                if(DOM.headerStatusContainer) {
                    DOM.headerStatusContainer.classList.remove("bg-emerald-500/10", "border-emerald-500/30", "text-emerald-400");
                    DOM.headerStatusContainer.classList.add("bg-cyan-500/10", "border-cyan-500/40", "text-cyan-400", "shadow-[0_0_15px_rgba(6,182,212,0.3)]");
                }

                if(data.preview_data && Array.isArray(data.preview_data)) {
                    gridData = data.preview_data;
                    renderPreviewGrid(gridData);
                }

                if(data.chart_metrics) {
                    animateChartUpdates({ charts: data.chart_metrics });
                }

                appendChat("system", `**Dataset Uploaded:** \`${DOM.dbFile.files[0].name}\` successfully ingested into the secure analytics sandbox. Sample isolated data grid populated below charts.`);
                setTimeout(() => DOM.btnUploadDb.textContent = "Upload to Sandbox", 3000);
            } else {
                throw new Error("Upload failed");
            }
        } catch(e) {
            DOM.btnUploadDb.textContent = "Error";
            setTimeout(() => DOM.btnUploadDb.textContent = "Upload to Sandbox", 2000);
            appendChat("system", `**Error:** Failed to upload. ${e.message}`);
        }
    };
}


// ----- CHAT SESSION PERSISTENCE -----
let chatHistoryArray = [];

function saveChatHistory() {
    localStorage.setItem("chat_session_history", JSON.stringify(chatHistoryArray));
}

function loadChatHistory() {
    const saved = localStorage.getItem("chat_session_history");
    if(saved) {
        try {
            chatHistoryArray = JSON.parse(saved);
            // Clear existing DOM except the first welcome message
            const children = Array.from(DOM.chatHistory.children);
            if(children.length > 1) {
                for(let i=1; i<children.length; i++) children[i].remove();
            }

            chatHistoryArray.forEach(msg => {
                renderChatMessage(msg.role, msg.text, false);
            });
        } catch(e) {
            console.error("Failed to load chat history", e);
        }
    }
}

// ----- CHAT RENDERER -----
function renderChatMessage(role, text, stream = false) {
    if(!DOM.chatHistory) return;
    const msgDiv = document.createElement("div");
    msgDiv.className = `chat-message fade-in relative z-10 ${role === "user" ? "" : "agent-message"}`;

    let avatarHTML = role === "user"
        ? `<div class="w-8 h-8 rounded-xl bg-white/10 border border-white/20 flex items-center justify-center flex-shrink-0 text-white shadow-sm"><svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg></div>`
        : `<div class="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center flex-shrink-0 shadow-[0_0_10px_rgba(99,102,241,0.4)] border border-white/10"><svg class="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg></div>`;

    let innerContainer = document.createElement("div");
    if(role === "user") {
        innerContainer.className = "flex-1 text-slate-200 text-xs leading-relaxed pt-1.5";
        innerContainer.innerHTML = window.marked ? marked.parse(text) : text;
    } else {
        innerContainer.className = "flex-1 text-slate-300 text-xs leading-relaxed glass-panel p-3 rounded-2xl rounded-tl-sm border border-white/5 shadow-md";
    }

    const flexWrapper = document.createElement("div");
    flexWrapper.className = "flex gap-3 max-w-full";
    flexWrapper.innerHTML = avatarHTML;
    flexWrapper.appendChild(innerContainer);
    msgDiv.appendChild(flexWrapper);
    DOM.chatHistory.appendChild(msgDiv);

    if (role !== "user" && stream) {
        let i = 0;
        const speed = 2; // ms per char
        function typeWriter() {
            if (i < text.length) {
                i += Math.floor(Math.random() * 4) + 1;
                const chunk = text.substring(0, i);
                innerContainer.innerHTML = window.marked ? marked.parse(chunk) : chunk;
                DOM.chatHistory.scrollTop = DOM.chatHistory.scrollHeight;
                setTimeout(typeWriter, speed);
            } else {
                innerContainer.innerHTML = window.marked ? marked.parse(text) : text;
                if(window.hljs) {
                    msgDiv.querySelectorAll('pre code').forEach((block) => hljs.highlightElement(block));
                }
                DOM.chatHistory.scrollTop = DOM.chatHistory.scrollHeight;
            }
        }
        typeWriter();
    } else {
        if(role !== "user") {
            innerContainer.innerHTML = window.marked ? marked.parse(text) : text;
        }
        DOM.chatHistory.scrollTop = DOM.chatHistory.scrollHeight;
        if(window.hljs) {
            msgDiv.querySelectorAll('pre code').forEach((block) => hljs.highlightElement(block));
        }
    }
}

function appendChat(role, text) {
    chatHistoryArray.push({ role, text });
    saveChatHistory();
    renderChatMessage(role, text, true);
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
        if(tokensUsed >= MAX_TOKENS) return;

        const text = DOM.chatInput.value.trim();
        if (!text) return;
        appendChat("user", text);
        DOM.chatInput.value = "";
        DOM.chatInput.style.height = "auto";

        highlightChartIntent(text);
        showSkeletonLoader();

        try {
            const res = await fetch("/api/sandbox/run", {
                method: "POST",
                headers: { "Content-Type": "application/json", "Authorization": `Bearer ${idToken}` },
                body: JSON.stringify({ command: text })
            });
            const data = await res.json();
            removeSkeletonLoader();

            if(data.output) {
                if(data.tokens_used) updateUsageRing(data.tokens_used);
                if(tokensUsed >= MAX_TOKENS && DOM.btnSendChat) {
                    DOM.btnSendChat.disabled = true;
                    DOM.chatInput.disabled = true;
                    DOM.chatInput.placeholder = "Rate limit exceeded (50/50). Please upgrade plan.";
                }

                appendChat("system", data.output);
                if(data.chart_metrics) {
                    animateChartUpdates({ charts: data.chart_metrics });
                } else {
                    animateChartUpdates();
                }
            }
        } catch(e) {
            removeSkeletonLoader();
            appendChat("system", `Error: ${e.message}`);
        }
    };
}

// ----- TELEMETRY -----
async function pollTelemetry() {
    if(!isSignedIn) return;
    try {
        const res = await fetch("/api/v1/system/telemetry", { headers: { "Authorization": `Bearer ${idToken}` } });
        if(res.ok) {
            const tel = await res.json();
            if(DOM.headerCpu) DOM.headerCpu.textContent = `Compute: ${tel.system_cpu_load || 0}%`;
            const mem = (tel.system_memory_total || 0) - (tel.system_memory_available || 0);
            if(DOM.headerRam) DOM.headerRam.textContent = `Mem: ${Math.round(mem / 1024 / 1024)}MB`;
        }
    } catch(e) {}
    setTimeout(pollTelemetry, 5000);
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

// ----- LIVE FIREBASE AUTHENTICATION -----
let auth = null;

async function initFirebaseAuth() {
    try {
        const configRes = await fetch("/api/v1/config");
        const firebaseConfig = await configRes.json();
        const app = initializeApp(firebaseConfig);
        auth = getAuth(app);
    } catch (e) {
        console.error("Failed to load Firebase config", e);
        return;
    }

    onAuthStateChanged(auth, async (user) => {
        if (user) {
            idToken = await user.getIdToken();
            isSignedIn = true;
            enterApp({ email: user.email || user.providerData[0]?.email || "Unknown", displayName: user.displayName || "Data Analyst" });
        } else {
            exitApp();
        }
    });

    if(DOM.formEmailAuth) {
        DOM.formEmailAuth.onsubmit = async (e) => {
            e.preventDefault();
            const email = DOM.inputEmail.value;
            const password = document.getElementById("input-password").value;
            try {
                await signInWithEmailAndPassword(auth, email, password);
            } catch (error) {
                if (DOM.authError) {
                    DOM.authError.textContent = error.message;
                    DOM.authError.classList.remove("hidden");
                }
            }
        };
    }

    if(DOM.btnEmailRegister) {
        DOM.btnEmailRegister.onclick = async () => {
            const email = DOM.inputEmail.value;
            const password = document.getElementById("input-password").value;
            try {
                await createUserWithEmailAndPassword(auth, email, password);
            } catch (error) {
                if (DOM.authError) {
                    DOM.authError.textContent = error.message;
                    DOM.authError.classList.remove("hidden");
                }
            }
        };
    }

    if(DOM.btnGoogleLogin) {
        DOM.btnGoogleLogin.onclick = async () => {
            try {
                if (DOM.authError) DOM.authError.classList.add("hidden");
                if (DOM.authSuccess) DOM.authSuccess.classList.add("hidden");

                const provider = new GoogleAuthProvider();
                provider.setCustomParameters({ prompt: 'select_account' });

                signInWithPopup(auth, provider).then((result) => {
                    console.log("Google Auth Success");
                }).catch((error) => {
                    console.error("Google Auth Error:", error);
                    if(error.code === 'auth/popup-blocked') {
                       signInWithRedirect(auth, provider);
                    } else {
                       if (DOM.authError) {
                           DOM.authError.textContent = error.message + " (Check if domain is authorized in Firebase)";
                           DOM.authError.classList.remove("hidden");
                       }
                    }
                });
            } catch (error) {
                if (DOM.authError) {
                    DOM.authError.textContent = error.message;
                    DOM.authError.classList.remove("hidden");
                }
            }
        };
    }

    getRedirectResult(auth).then((result) => {
         if(result) console.log("Redirect Auth Success");
    }).catch((error) => {
         if (DOM.authError) {
             DOM.authError.textContent = error.message;
             DOM.authError.classList.remove("hidden");
         }
    });

    if(DOM.btnForgotPassword) {
        DOM.btnForgotPassword.onclick = async () => {
            if (DOM.authError) DOM.authError.classList.add("hidden");
            if (DOM.authSuccess) DOM.authSuccess.classList.add("hidden");

            const email = DOM.inputEmail.value;
            if (!email) {
                if (DOM.authError) {
                    DOM.authError.textContent = "Please enter your email address first.";
                    DOM.authError.classList.remove("hidden");
                }
                return;
            }

            try {
                await sendPasswordResetEmail(auth, email);
                if (DOM.authSuccess) {
                    DOM.authSuccess.textContent = "Password reset email sent! Check your inbox.";
                    DOM.authSuccess.classList.remove("hidden");
                }
            } catch (error) {
                if (DOM.authError) {
                    DOM.authError.textContent = error.message;
                    DOM.authError.classList.remove("hidden");
                }
            }
        };
    }

    if(DOM.btnLogout) {
        DOM.btnLogout.onclick = () => {
            signOut(auth);
        };
    }
}

function enterApp(user) {
    if(DOM.authGate) DOM.authGate.classList.add("hidden");
    if(DOM.appShell) {
        DOM.appShell.classList.remove("hidden");
        setTimeout(() => DOM.appShell.classList.remove("opacity-0"), 50);
    }

    if(DOM.userName) DOM.userName.textContent = user.displayName || user.email.split("@")[0];
    if(DOM.userAvatar) DOM.userAvatar.src = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='36' height='36'><rect width='36' height='36' rx='18' fill='%236366f1'/></svg>";

    initCharts();
    connectWebSocket();
    pollTelemetry();
    loadChatHistory();
}

function exitApp() {
    isSignedIn = false;
    idToken = null;
    if(DOM.appShell) DOM.appShell.classList.add("opacity-0");
    setTimeout(() => {
        if(DOM.appShell) DOM.appShell.classList.add("hidden");
        if(DOM.authGate) DOM.authGate.classList.remove("hidden");
    }, 700);
    if(ws) { ws.close(); ws = null; }
}

initFirebaseAuth();
