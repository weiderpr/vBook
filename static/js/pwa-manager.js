const VAPID_PUBLIC_KEY = 'BE1CtcFZWRjO42kjA68rtGut2LAC5n93-65WrI7rBLi-CkO_rTxqQXPJ0XYE4BwVXpbouaHZAVMKJ7qpKaDj8_g';

function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
        .replace(/\-/g, '+')
        .replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

async function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        try {
            const registration = await navigator.serviceWorker.register('/book/sw.js', {
                scope: '/book/'
            });
            console.log('Service Worker registrado com sucesso:', registration.scope);
            return registration;
        } catch (error) {
            console.error('Falha ao registrar o Service Worker:', error);
        }
    }
}

async function subscribeUserToPush() {
    const registration = await navigator.serviceWorker.ready;
    
    try {
        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY)
        });

        console.log('Usuário assinado com sucesso!');
        await sendSubscriptionToBackend(subscription);
    } catch (error) {
        if (Notification.permission === 'denied') {
            console.warn('Permissão para notificações foi negada');
        } else {
            console.error('Falha ao assinar o usuário:', error);
        }
    }
}

async function sendSubscriptionToBackend(subscription) {
    const response = await fetch('/book/mobile/subscribe-push/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: json_stringify_subscription(subscription)
    });

    if (response.ok) {
        console.log('Assinatura salva no servidor');
    }
}

// Helper para converter subscription em JSON simples para o Django
function json_stringify_subscription(subscription) {
    const subJson = subscription.toJSON();
    return JSON.stringify({
        endpoint: subJson.endpoint,
        p256dh: subJson.keys.p256dh,
        auth: subJson.keys.auth
    });
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Iniciar quando o usuário interagir ou carregar
window.addEventListener('load', async () => {
    await registerServiceWorker();
    
    // Opcional: Pedir permissão automaticamente ou via botão
    if (Notification.permission === 'default') {
        // Podemos esperar uma interação do usuário para não ser invasivo
        console.log('Notificações prontas para serem solicitadas');
    }
});

// Função pública para ser chamada via botão na UI
async function enableNotifications() {
    if (!('Notification' in window)) {
        alert("Notificações não suportadas. Se estiver no iPhone, você deve primeiro 'Adicionar à Tela de Início'.");
        return false;
    }
    
    try {
        const permission = await Notification.requestPermission();
        if (permission === 'granted') {
            await subscribeUserToPush();
            alert("Notificações ativadas com sucesso!");
            return true;
        } else {
            alert("Permissão negada para notificações.");
        }
    } catch (err) {
        console.error("Erro ao solicitar permissão:", err);
        alert("Erro ao ativar notificações: " + err.message);
    }
    return false;
}

// Global helper for the button
async function handleEnablePush() {
    const success = await enableNotifications();
    if (success) {
        const prompt = document.getElementById('pushPrompt');
        if (prompt) prompt.style.display = 'none';
    }
}
