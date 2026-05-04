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
        // Busca o token CSRF da meta tag
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

        // O endpoint do FastAPI com OAuth2PasswordRequestForm aceita FormData urlencoded
        const response = await fetch('/auth/login', {
            method: 'POST',
            headers: {
                'X-CSRF-Token': csrfToken
            },
            body: new URLSearchParams(formData)
        });

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

        // Grava APENAS metadados do usuário para renderização UI condicional
        if (data.usuario) {
            localStorage.setItem("saa29_user", JSON.stringify(data.usuario));
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
