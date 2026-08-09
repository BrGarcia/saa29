// app/web/static/js/mobile/app_mobile.js
// Lógica global do SAA29 Mobile e registro do Service Worker

document.addEventListener('DOMContentLoaded', () => {
    // Registro do Service Worker para PWA
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js')
            .then(reg => console.log('SW SAA29 Registrado com sucesso:', reg.scope))
            .catch(err => console.log('Falha no registro do SW:', err));
    }

    // Lógica do Menu Sanduíche (Drawer Off-Canvas) - Conformidade CSP
    const btnOpen = document.getElementById('btn-mobile-menu');
    const btnClose = document.getElementById('btn-close-mobile-menu');
    const drawer = document.getElementById('mobile-menu-drawer');
    const overlay = document.getElementById('mobile-menu-overlay');

    function openDrawer() {
        drawer?.classList.add('active');
        overlay?.classList.add('active');
        drawer?.setAttribute('aria-hidden', 'false');
    }

    function closeDrawer() {
        drawer?.classList.remove('active');
        overlay?.classList.remove('active');
        drawer?.setAttribute('aria-hidden', 'true');
    }

    btnOpen?.addEventListener('click', openDrawer);
    btnClose?.addEventListener('click', closeDrawer);
    overlay?.addEventListener('click', closeDrawer);
});
