export function showNotification(message, type = 'success') {
    const existing = document.querySelector('.notification');
    if (existing)
        existing.remove();
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);
    setTimeout(() => notification.classList.add('show'), 100);
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}
//# sourceMappingURL=notifications.js.map