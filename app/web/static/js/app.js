// @ts-check

/**
 * static/js/app.js
 * Lógica Vanilla JS para MVP Tático SAA29.
 */

// ============================================================================
// DEFINIÇÕES DE TIPOS GLOBAIS (JSDoc Model Definitions)
// ============================================================================

/**
 * @typedef {Object} SAAUser
 * @property {number} id
 * @property {string} nome
 * @property {string} funcao
 * @property {string} [token]
 */

/**
 * @typedef {Object} Aeronave
 * @property {string} id
 * @property {string} matricula
 * @property {string} serial_number
 * @property {string} status
 * @property {boolean} [ativo]
 */

/**
 * @typedef {Object} TipoControle
 * @property {string} id
 * @property {string} nome
 * @property {string} [descricao]
 */

/**
 * @typedef {Object} Equipamento
 * @property {string} id
 * @property {string} part_number
 * @property {string} nome_generico
 * @property {string} [descricao]
 */

/**
 * @typedef {Object} RegraVencimento
 * @property {string} modelo_id
 * @property {string} tipo_controle_id
 * @property {number} periodicidade_meses
 * @property {string} [pn]
 * @property {string} [tipo_nome]
 */

/**
 * @typedef {Object} TipoInspecao
 * @property {string} id
 * @property {string} codigo
 * @property {string} nome
 * @property {string} [descricao]
 * @property {number} [duracao_dias]
 * @property {boolean} ativo
 */

// ============================================================================
// LOGICA DE TEMA E SESSÃO
// ============================================================================

const THEME_KEY = "saa29_theme";

/** @type {HTMLElement | null} */
const toggleThemeBtn = document.getElementById("theme-toggle");

/**
 * Inicializa o tema preferido do usuário ou carrega o padrão claro.
 * @returns {void}
 */
function initTheme() {
    let theme = localStorage.getItem(THEME_KEY);
    if (!theme) {
        // Default: Modo Claro (IGNORA preferência do SO se não houver escolha salva)
        theme = "light";
    }
    document.documentElement.setAttribute("data-theme", theme);
    updateThemeIcon(theme);
}

/**
 * Alterna entre tema claro e escuro.
 * @returns {void}
 */
function toggleTheme() {
    let currentTheme = document.documentElement.getAttribute("data-theme");
    let newTheme = currentTheme === "dark" ? "light" : "dark";
    
    document.documentElement.setAttribute("data-theme", newTheme);
    localStorage.setItem(THEME_KEY, newTheme);
    updateThemeIcon(newTheme);
}

/**
 * Atualiza o ícone do tema no botão correspondente.
 * @param {string} theme - "light" ou "dark"
 * @returns {void}
 */
function updateThemeIcon(theme) {
    if (!toggleThemeBtn) return;
    if (theme === "dark") {
        toggleThemeBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/></svg>`;
    } else {
        toggleThemeBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;
    }
}

// 2. JWT Cookies Interceptor logic
/**
 * Limpa a sessão local do usuário e redireciona para a tela de login.
 * @returns {Promise<void>}
 */
async function clearAuth() {
    // 1. Limpeza Local imediata para garantir que a UI deslogue
    localStorage.removeItem("saa29_user");
    
    // 2. Tenta notificar o servidor (opcional para o cliente, mas bom para segurança)
    try {
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        /** @type {Record<string, string>} */
        const headers = { "Content-Type": "application/json" };
        if (csrfMeta) {
            headers["X-CSRF-Token"] = csrfMeta.getAttribute("content") || "";
        }

        await fetch("/auth/logout", {
            method: "POST",
            headers: headers,
            credentials: 'same-origin'
        });
    } catch(e) {
        console.warn("Falha ao invalidar sessão no servidor:", e);
    }
    
    // 3. Redireciona sempre, independente do sucesso da chamada acima
    window.location.href = "/login";
}

/**
 * Função utilitária para chamadas à API com suporte a CSRF e tratamento de erros automático.
 * 
 * @param {string} endpoint - O endpoint da API (ex: "/aeronaves/")
 * @param {Omit<RequestInit, "body"> & { body?: any }} [options] - Opções extras da requisição HTTP
 * @returns {Promise<any>} O payload retornado em formato JSON
 */
async function apiFetch(endpoint, options = {}) {
    // Para endpoints na mesma origem, envia os Cookies de sessão (HttpOnly)
    options.credentials = 'same-origin';
    
    /** @type {Record<string, string>} */
    const headers = {
        ...(options.headers ? Object.fromEntries(new Headers(options.headers).entries()) : {})
    };

    // Auto-inject CSRF Token
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    if (csrfMeta) {
        headers["X-CSRF-Token"] = csrfMeta.getAttribute("content") || "";
    }

    // Auto-inject JSON se aplicável
    if (options.body && !(options.body instanceof FormData)) {
        if (typeof options.body === 'object') {
            options.body = JSON.stringify(options.body);
        }
        if (!headers["Content-Type"]) headers["Content-Type"] = "application/json";
    }

    try {
        const response = await fetch(endpoint, { ...options, headers });
        
        // Sincroniza o Token CSRF se o servidor enviar um novo no header
        const newToken = response.headers.get("X-CSRF-Token");
        if (newToken) {
            const meta = document.querySelector('meta[name="csrf-token"]');
            if (meta) meta.setAttribute("content", newToken);
        }

        if (response.status === 401) {
            // Apenas 401 (Unauthorized) limpa a sessão.
            clearAuth();
            throw new Error("Sessão expirada.");
        }

        let data;
        try {
            data = await response.json();
        } catch(e) {
            data = null;
        }

        if (response.status === 403) {
            // 403 (Forbidden) pode ser erro de permissão (RBAC) ou CSRF.
            let errMsg = data?.detail || "Falha na sincronia de segurança (CSRF). Por favor, recarregue a página (F5).";
            if (typeof errMsg !== 'string') errMsg = JSON.stringify(errMsg);
            throw new Error(errMsg);
        }
        
        if (!response.ok) {
            let errMsg = data?.detail || "Erro desconhecido na API";
            if (typeof errMsg !== 'string') errMsg = JSON.stringify(errMsg);
            throw new Error(errMsg);
        }

        return data;
    } catch (error) {
        // @ts-ignore
        showToast(error.message, "error");
        throw error;
    }
}

// 3. Utilitários Globais (SEC-04)
/**
 * Sanitiza texto contra ataques XSS de forma segura.
 * 
 * @param {string | null | undefined} text - O texto que necessita de sanitização
 * @returns {string} O texto sanitizado em formato seguro para inserção no HTML
 */
function escapeHtml(text) {
    if (text === null || text === undefined) return "";
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

// 4. Sistema de Toasts Visuais Premium
/**
 * Exibe um toast visual customizável no canto da tela.
 * 
 * @param {string} message - A mensagem a ser exibida no Toast
 * @param {"success" | "error" | "info" | "warning"} [type] - O tipo do Toast
 * @returns {void}
 */
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
    const logoutBtn = document.getElementById("logout-btn");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", clearAuth);
    }
});

