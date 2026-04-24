document.addEventListener("DOMContentLoaded", () => {
    const userJson = localStorage.getItem("saa29_user");
    if (!userJson && window.location.pathname !== "/login") {
        window.location.href = "/login";
    } else if (userJson) {
        try {
            const user = JSON.parse(userJson);
            const funcao = user.funcao ? user.funcao.toUpperCase() : '';
            if (funcao === 'ADMINISTRADOR' || funcao === 'ENCARREGADO') {
                const adminNav = document.getElementById('admin-nav');
                if (adminNav) adminNav.style.display = 'flex';
                
                const settingsNav = document.getElementById('settings-nav');
                if (settingsNav) settingsNav.style.display = 'flex';
            }
        } catch (e) { }
    }
});
