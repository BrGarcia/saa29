// Se o usuário já tiver sessão ativa no servidor, redireciona.
// Caso contrário, limpa dados locais stale e permanece no login.
document.addEventListener("DOMContentLoaded", async () => {
    if (localStorage.getItem("saa29_user")) {
        try {
            const res = await fetch("/auth/me", { credentials: "same-origin" });
            if (res.ok) {
                // Sessão válida no servidor — redireciona para a landing page (Dashboard)
                window.location.href = "/dashboard";
                return;
            }
        } catch (e) { /* rede falhou, fica no login */ }
        // Sessão inválida — limpa dados locais stale
        localStorage.removeItem("saa29_user");
    }

    const form = document.getElementById('loginForm');
    if (form) {
        form.addEventListener('submit', handleLogin);
    }
});

async function handleLogin(e) {
    e.preventDefault();

    const form = document.getElementById('loginForm');
    const loginBtn = document.getElementById('loginBtn');
    const formData = new FormData(form);

    loginBtn.disabled = true;
    loginBtn.innerHTML = 'Conectando...';

    try {
        // Busca o token CSRF da meta tag renderizada pelo backend.
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        const csrfToken = csrfMeta ? (csrfMeta.getAttribute('content') || '') : '';
        if (!csrfToken) {
            const msg = "Erro de segurança (CSRF). Recarregue a página.";
            if (typeof showToast === "function") showToast(msg, "error");
            else alert(msg);
            throw new Error(msg);
        }

        // O endpoint do FastAPI com OAuth2PasswordRequestForm aceita FormData urlencoded
        const response = await fetch('/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
                'X-CSRF-Token': csrfToken
            },
            credentials: 'same-origin',
            body: new URLSearchParams(formData)
        });

        // Sincroniza o token CSRF rotacionado pelo middleware nesta resposta
        // (200, 401 ou 429) — sem isso, a 2a tentativa reenvia o token velho
        // da meta tag contra o cookie ja rotacionado e leva 403 de CSRF.
        const novoCsrfToken = response.headers.get('X-CSRF-Token');
        if (novoCsrfToken && csrfMeta) {
            csrfMeta.setAttribute('content', novoCsrfToken);
        }

        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            let msg = 'Credenciais inválidas ou erro no servidor.';
            if (response.status === 401) msg = "Login ou senha incorretos.";
            else if (data.detail) {
                msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
            }
            if (response.status === 429) {
                msg = data.detail || "Muitas tentativas. Tente novamente mais tarde.";
            }
            if (typeof showToast === "function") showToast(msg, "error");
            else alert(msg);
            throw new Error(msg);
        }

        const data = await response.json();

        // Grava APENAS metadados mínimos necessários para renderização UI condicional
        if (data.usuario) {
            const minUser = {
                id: data.usuario.id,
                nome: data.usuario.nome,
                funcao: data.usuario.funcao,
                username: data.usuario.username,
                posto: data.usuario.posto
            };
            localStorage.setItem("saa29_user", JSON.stringify(minUser));
        }
        if (typeof showToast === "function") showToast("Acesso autorizado. Carregando Painel...", "success");
        else alert("Acesso autorizado");

        // Redireciona para o Dashboard (Landing Page)
        setTimeout(() => {
            window.location.href = "/dashboard";
        }, 800);

    } catch (err) {
        console.error(err);
    } finally {
        loginBtn.disabled = false;
        loginBtn.innerHTML = 'Autenticar';
    }
}
