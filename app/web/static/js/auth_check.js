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
            
            // Controle de visibilidade global por data-role
            document.querySelectorAll('[data-role]').forEach(el => {
                const requiredRoles = el.getAttribute('data-role').toUpperCase().split(',').map(r=>r.trim());
                
                let hasAccess = false;
                if (funcao === 'ADMINISTRADOR') {
                    hasAccess = true; // Admin acessa tudo
                } else if (funcao === 'ENCARREGADO') {
                    hasAccess = requiredRoles.includes('ENCARREGADO') || requiredRoles.includes('MANTENEDOR');
                } else if (funcao === 'INSPETOR') {
                    hasAccess = requiredRoles.includes('INSPETOR');
                } else if (funcao === 'MANTENEDOR') {
                    hasAccess = requiredRoles.includes('MANTENEDOR');
                }

                if (!hasAccess) {
                    const currentDisplay = window.getComputedStyle(el).display;
                    if (currentDisplay !== 'none') {
                        el.setAttribute('data-original-display', currentDisplay);
                    }
                    el.style.display = 'none';
                } else {
                    // Se o elemento foi ocultado por nós, restauramos o display original
                    if (el.style.display === 'none') {
                        const original = el.getAttribute('data-original-display');
                        el.style.display = original || ''; // Deixa o CSS original agir se não houver atributo
                    }
                }
            });

            // Ajustes específicos na barra de navegação
            if (['ADMINISTRADOR', 'ENCARREGADO', 'MANTENEDOR', 'INSPETOR'].includes(funcao)) {
                const adminNav = document.getElementById('admin-nav');
                if (adminNav) adminNav.style.display = 'flex';
            }
            
            // Mostrar configurações para Admin ou Encarregado (conforme RBAC)
            if (['ADMINISTRADOR'].includes(funcao)) {
                const settingsNav = document.getElementById('settings-nav');
                if (settingsNav) settingsNav.style.display = 'flex';
            }

        } catch (e) { }
    }
});

/**
 * Verifica se o usuário logado possui o papel necessário.
 * @param {string} requiredRole - Papel mínimo exigido (ADMINISTRADOR, ENCARREGADO, INSPETOR, MANTENEDOR)
 * @returns {boolean}
 */
window.hasPermission = function(requiredRole) {
    const userJson = localStorage.getItem("saa29_user");
    if (!userJson) return false;
    
    try {
        const user = JSON.parse(userJson);
        const funcao = user.funcao ? user.funcao.toUpperCase() : '';
        
        if (funcao === 'ADMINISTRADOR') return true;
        if (funcao === 'ENCARREGADO') return requiredRole === 'ENCARREGADO' || requiredRole === 'MANTENEDOR';
        if (funcao === 'INSPETOR') return requiredRole === 'INSPETOR';
        if (funcao === 'MANTENEDOR') return requiredRole === 'MANTENEDOR';
        
        return false;
    } catch (e) {
        return false;
    }
};
