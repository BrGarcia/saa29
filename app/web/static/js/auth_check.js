document.addEventListener("DOMContentLoaded", async () => {
    // Validação com backend (M-06)
    const path = window.location.pathname.replace(/\/$/, "");
    if (path !== "/login" && path !== "") {
        try {
            const res = await fetch("/auth/me");
            if (!res.ok) {
                localStorage.removeItem("saa29_user");
                window.location.href = "/login";
                return;
            }
            const data = await res.json();
            localStorage.setItem("saa29_user", JSON.stringify(data));
        } catch (e) {
            localStorage.removeItem("saa29_user");
            window.location.href = "/login";
            return;
        }
    }

    const userJson = localStorage.getItem("saa29_user");
    if (userJson) {
        try {
            const user = JSON.parse(userJson);
            const funcao = user.funcao ? user.funcao.toUpperCase() : '';
            
            // Mostrar navegação dos módulos para todos os perfis operacionais
            if (['ADMINISTRADOR', 'ENCARREGADO', 'MANTENEDOR'].includes(funcao)) {
                const adminNav = document.getElementById('admin-nav');
                if (adminNav) adminNav.style.display = 'flex';
            }
            
            // Mostrar configurações apenas para Administradores
            if (funcao === 'ADMINISTRADOR') {
                const settingsNav = document.getElementById('settings-nav');
                if (settingsNav) settingsNav.style.display = 'flex';
            }
        } catch (e) { }
    }
});
