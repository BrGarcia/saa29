/**
 * static/js/app.js
 * Lógica Vanilla JS para MVP Tático SAA29.
 */

// 1. Gerenciamento de Tema (Dark/Light Mode)
const THEME_KEY = "saa29_theme";
const toggleThemeBtn = document.getElementById("theme-toggle");

function initTheme() {
    let theme = localStorage.getItem(THEME_KEY);
    if (!theme) {
        // Default: Modo Claro (IGNORA preferência do SO se não houver escolha salva)
        theme = "light";
    }
    document.documentElement.setAttribute("data-theme", theme);
    updateThemeIcon(theme);
}

function toggleTheme() {
    let currentTheme = document.documentElement.getAttribute("data-theme");
    let newTheme = currentTheme === "dark" ? "light" : "dark";
    
    document.documentElement.setAttribute("data-theme", newTheme);
    localStorage.setItem(THEME_KEY, newTheme);
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    if (!toggleThemeBtn) return;
    if (theme === "dark") {
        toggleThemeBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/></svg>`;
    } else {
        toggleThemeBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;
    }
}

// 2. JWT Cookies Interceptor logic
function clearAuth() {
    try {
        fetch("/auth/logout", {
            method: "POST",
            headers: { "Content-Type": "application/json" } // Fetch via cookies auth automatically
        }).catch(e => {});
    } catch(e) {}
    
    localStorage.removeItem("saa29_user");
    window.location.href = "/login";
}

async function apiFetch(endpoint, options = {}) {
    // Para endpoints na mesma origem, envia os Cookies de sessão (HttpOnly)
    options.credentials = 'same-origin';
    
    const headers = {
        ...(options.headers || {})
    };

    // Auto-inject JSON se aplicável
    if (options.body && !(options.body instanceof FormData) && typeof options.body === 'object') {
        options.body = JSON.stringify(options.body);
        if (!headers["Content-Type"]) headers["Content-Type"] = "application/json";
    }

    try {
        const response = await fetch(endpoint, { ...options, headers });
        if (response.status === 401) {
            clearAuth();
            throw new Error("Sessão expirada.");
        }
        
        let data;
        try {
            data = await response.json();
        } catch(e) {
            data = null;
        }

        if (!response.ok) {
            let errMsg = data?.detail || "Erro desconhecido na API";
            if (typeof errMsg !== 'string') errMsg = JSON.stringify(errMsg);
            throw new Error(errMsg);
        }

        return data;
    } catch (error) {
        showToast(error.message, "error");
        throw error;
    }
}

// 3. Utilitários Globais (SEC-04)
function escapeHtml(text) {
    if (text === null || text === undefined) return "";
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

// 4. Sistema de Toasts Visuais Premium
function showToast(message, type = "info") {
    let container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    
    let icon = "";
    if(type === 'success') icon = `<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>`;
    else if(type === 'error') icon = `<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>`;

    const span = document.createElement("span");
    span.textContent = message;
    toast.innerHTML = icon;
    toast.appendChild(span);

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Inicializações Automáticas
document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    if (toggleThemeBtn) {
        toggleThemeBtn.addEventListener("click", toggleTheme);
    }
});
