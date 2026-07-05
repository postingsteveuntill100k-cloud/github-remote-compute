import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAnalytics } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-analytics.js";
import { getAuth, signInWithEmailAndPassword, createUserWithEmailAndPassword, GoogleAuthProvider, signInWithPopup, onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";


    const DOM = {
        authGate: document.getElementById("auth-gate"),
        appShell: document.getElementById("app-shell"),
        formEmailAuth: document.getElementById("form-email-auth"),
        inputEmail: document.getElementById("input-email"),
        btnEmailRegister: document.getElementById("btn-email-register"),
        btnGoogleLogin: document.getElementById("btn-google-login"),
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

        filterDate: document.getElementById("filter-date"),
        filterSegment: document.getElementById("filter-segment"),

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
    let gridData = [];
    let currentSort = { column: null, direction: 'asc' };

    // ----- VIEW TOGGLE -----
    if(DOM.btnToggleView) {
        DOM.btnToggleView.onclick = () => {
            const isHidden = DOM.sidebar.classList.contains("w-0");
            if (isHidden) {
                DOM.sidebar.classList.remove("w-0", "opacity-0", "px-0", "border-0");
                DOM.sidebar.classList.add("w-72");
                DOM.toggleViewText.textContent = "Full Canvas";
            } else {
                DOM.sidebar.classList.remove("w-72");
                DOM.sidebar.classList.add("w-0", "opacity-0", "px-0", "border-0");
                DOM.toggleViewText.textContent = "Show Controls";
            }
        };
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
            // Visual trigger without data mutation
            if(trendChart) trendChart.update();
            if(revenueChart) revenueChart.update();
            if(trafficChart) trafficChart.update();
        }
    }

    if(DOM.filterDate && DOM.filterSegment) {
        DOM.filterDate.onchange = animateChartUpdates;
        DOM.filterSegment.onchange = animateChartUpdates;
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

    // ----- TELEMETRY SPIKES -----
    let spikeInterval = null;
    function startTelemetrySpike() {
        if(DOM.headerCpu) {
            DOM.headerCpu.classList.add("text-red-400", "drop-shadow-[0_0_8px_rgba(248,113,113,0.8)]");
            DOM.headerCpu.classList.remove("text-cyan-200");
            DOM.headerCpu.previousElementSibling.classList.replace("bg-cyan-500", "bg-red-500");
            DOM.headerCpu.previousElementSibling.classList.replace("shadow-[0_0_6px_rgba(6,182,212,0.8)]", "shadow-[0_0_6px_rgba(248,113,113,0.8)]");
        }
        if(DOM.headerRam) {
            DOM.headerRam.classList.add("text-orange-400", "drop-shadow-[0_0_8px_rgba(251,146,60,0.8)]");
            DOM.headerRam.classList.remove("text-purple-200");
            DOM.headerRam.previousElementSibling.classList.replace("bg-purple-500", "bg-orange-500");
            DOM.headerRam.previousElementSibling.classList.replace("shadow-[0_0_6px_rgba(168,85,247,0.8)]", "shadow-[0_0_6px_rgba(251,146,60,0.8)]");
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
            DOM.headerCpu.previousElementSibling.classList.replace("shadow-[0_0_6px_rgba(248,113,113,0.8)]", "shadow-[0_0_6px_rgba(6,182,212,0.8)]");
        }
        if(DOM.headerRam) {
            DOM.headerRam.classList.remove("text-orange-400", "drop-shadow-[0_0_8px_rgba(251,146,60,0.8)]");
            DOM.headerRam.classList.add("text-purple-200");
            DOM.headerRam.previousElementSibling.classList.replace("bg-orange-500", "bg-purple-500");
            DOM.headerRam.previousElementSibling.classList.replace("shadow-[0_0_6px_rgba(251,146,60,0.8)]", "shadow-[0_0_6px_rgba(168,85,247,0.8)]");
        }
        pollTelemetry(); // force refresh normal status
    }

    // ----- SKELETON LOADER -----
    function showSkeletonLoader() {
        startTelemetrySpike();
        if(!DOM.chatHistory) return null;
        const msgDiv = document.createElement("div");
        msgDiv.className = "chat-message agent-message relative z-10 fade-in";
        msgDiv.id = "chat-skeleton-loader";
        msgDiv.innerHTML = `
            <div class="flex gap-5 max-w-5xl mx-auto">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500/50 to-purple-600/50 flex items-center justify-center flex-shrink-0 border border-white/10 animate-pulse">
                    <svg class="w-5 h-5 text-white/50" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                </div>
                <div class="flex-1 glass-panel p-5 rounded-2xl rounded-tl-sm border border-white/5 shadow-md">
                    <div class="h-3 w-48 skeleton-wave rounded-full mb-4"></div>
                    <div class="space-y-3">
                        <div class="h-2 w-full skeleton-wave rounded-full"></div>
                        <div class="h-2 w-[90%] skeleton-wave rounded-full"></div>
                        <div class="h-2 w-[60%] skeleton-wave rounded-full"></div>
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

    // ----- LIVE FIREBASE AUTHENTICATION -----
    const firebaseConfig = {
        apiKey: "AIzaSyDYG2wkluDX0pqRTBuufu6QmFXb4i4TBpk",
        authDomain: "mcpsuper-servers.firebaseapp.com",
        projectId: "mcpsuper-servers",
        storageBucket: "mcpsuper-servers.firebasestorage.app",
        messagingSenderId: "214677923673",
        appId: "1:214677923673:web:75e45d40a510abab6d8e48",
        measurementId: "G-P409QBP5QJ"
    };

    const app = initializeApp(firebaseConfig);
    const analytics = getAnalytics(app);
    const auth = getAuth(app);

    function initFirebaseAuth() {

        onAuthStateChanged(auth, async (user) => {
            if (user) {
                idToken = await user.getIdToken();
                isSignedIn = true;
                enterApp({ email: user.email, displayName: user.displayName || "Data Analyst" });
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
                    const authError = document.getElementById("auth-error");
                    authError.textContent = error.message;
                    authError.classList.remove("hidden");
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
                    const authError = document.getElementById("auth-error");
                    authError.textContent = error.message;
                    authError.classList.remove("hidden");
                }
            };
        }
        if(DOM.btnGoogleLogin) {
            DOM.btnGoogleLogin.onclick = async () => {
                try {
                    const provider = new GoogleAuthProvider();
                    await signInWithPopup(auth, provider);
                } catch (error) {
                    const authError = document.getElementById("auth-error");
                    authError.textContent = error.message;
                    authError.classList.remove("hidden");
                }
            };
        }
        if(DOM.btnLogout) {
            DOM.btnLogout.onclick = () => {
                signOut(auth);
            };
        }
    }

    initFirebaseAuth();
