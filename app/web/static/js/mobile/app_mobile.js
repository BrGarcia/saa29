// app/web/static/js/mobile/app_mobile.js
// Lógica global do SAA29 Mobile e registro do Service Worker

document.addEventListener('DOMContentLoaded', () => {
    // Registro do Service Worker para PWA
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js')
            .then(reg => console.log('SW SAA29 Registrado com sucesso:', reg.scope))
            .catch(err => console.log('Falha no registro do SW:', err));
    }
});
