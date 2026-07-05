(function() {
    const DOM = {
        authGate: document.getElementById("auth-gate"),
        appShell: document.getElementById("app-shell"),
        formEmailAuth: document.getElementById("form-email-auth"),
        inputEmail: document.getElementById("input-email"),
        inputPassword: document.getElementById("input-password"),
        btnEmailLogin: document.getElementById("btn-email-login"),
        btnEmailRegister: document.getElementById("btn-email-register"),
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
        sidebarPort: document.getElementById("sidebar-port"),
        btnSaveKeys: document.getElementById("btn-save-keys"),
        keyClaude: document.getElementById("key-claude"),
        btnUploadDb: document.getElementById("btn-upload-db"),
        dbFile: document.getElementById("dbFile")
    };

    let idToken = null;
    let ws = null;
    let isSignedIn = false;

    // ----- FIREBASE AUTH (MOCK OR REAL) -----
    function initMockAuth() {
        // Skip actual Firebase in localstack, auto-login for hackathon speed
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
        DOM.userName.textContent = user.displayName || user.email.split("@")[0];
        DOM.userAvatar.src = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32'><rect width='32' height='32' rx='16' fill='%2310a37f'/></svg>";
        connectWebSocket();
        pollTelemetry();
    }

    function exitApp() {
        isSignedIn = false;
        idToken = null;
        DOM.appShell.classList.add("hidden");
        DOM.authGate.classList.remove("hidden");
        if(ws) { ws.close(); ws = null; }
    }

    // ----- TELEMETRY -----
    async function pollTelemetry() {
        if(!isSignedIn) return;
        try {
            const res = await fetch("/api/v1/system/telemetry", { headers: { "Authorization": `Bearer ${idToken}` } });
            if(res.ok) {
                const tel = await res.json();
                DOM.headerCpu.textContent = `CPU: ${tel.system_cpu_load || 0}%`;
                const mem = (tel.system_memory_total || 0) - (tel.system_memory_available || 0);
                DOM.headerRam.textContent = `RAM: ${Math.round(mem / 1024 / 1024)} MB`;
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
            }
        } catch(e) {
            appendChat("system", `Error: ${e.message}`);
        }
    };

    // ----- SAVE API KEYS -----
    DOM.btnSaveKeys.onclick = async () => {
        const tokens = {
            claude: DOM.keyClaude.value,
        };
        DOM.btnSaveKeys.textContent = "Saving...";
        try {
            const res = await fetch("/api/auth/save", {
                method: "POST",
                headers: { "Content-Type": "application/json", "Authorization": `Bearer ${idToken}` },
                body: JSON.stringify({ tokens })
            });
            if(res.ok) {
                DOM.btnSaveKeys.textContent = "Saved!";
                setTimeout(() => DOM.btnSaveKeys.textContent = "Save Tokens", 2000);
            } else {
                throw new Error("Failed to save");
            }
        } catch(e) {
            DOM.btnSaveKeys.textContent = "Error";
            setTimeout(() => DOM.btnSaveKeys.textContent = "Save Tokens", 2000);
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
                DOM.headerStatus.textContent = "Database Connected // Sandbox Isolated";
                DOM.headerStatus.classList.add("status-badge", "online");
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
        msgDiv.className = role === "user" ? "chat-message" : "chat-message agent-message";

        let avatarHTML = role === "user"
            ? `<div class="message-avatar" style="background:var(--accent); color:white;">U</div>`
            : `<div class="message-avatar">AI</div>`;

        // Render Markdown using marked.js
        let htmlContent = text;
        if(window.marked) {
            htmlContent = marked.parse(text);
        }

        msgDiv.innerHTML = `${avatarHTML}<div class="message-content">${htmlContent}</div>`;
        DOM.chatHistory.appendChild(msgDiv);
        DOM.chatHistory.scrollTop = DOM.chatHistory.scrollHeight;

        // Apply syntax highlighting
        if(window.hljs) {
            msgDiv.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
                // Add copy button
                const pre = block.parentElement;
                if(pre.tagName === 'PRE' && !pre.querySelector('.copy-btn')) {
                    const btn = document.createElement('button');
                    btn.className = 'copy-btn';
                    btn.textContent = 'Copy';
                    btn.onclick = () => {
                        navigator.clipboard.writeText(block.innerText);
                        btn.textContent = 'Copied!';
                        setTimeout(() => btn.textContent = 'Copy', 2000);
                    };
                    pre.appendChild(btn);
                }
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
                appendChat("system", entry.msg);
            } catch(e) {}
        };
        ws.onclose = () => {
            if(isSignedIn) setTimeout(connectWebSocket, 3000);
        };
    }

    initMockAuth();
})();
