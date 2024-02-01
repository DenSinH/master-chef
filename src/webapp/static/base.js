
function show_popup(message) {
    const popup = document.createElement('div');
    popup.textContent = message;
    popup.style.position = 'fixed';
    popup.style.top = '10px';
    popup.style.left = '50%';
    popup.style.transform = 'translateX(-50%)';
    popup.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
    popup.style.color = 'white';
    popup.style.padding = '10px 20px';
    popup.style.borderRadius = '5px';
    popup.style.zIndex = '9999';
    popup.style.textAlign = 'center';
    popup.style.maxWidth = '80vw';

    document.body.appendChild(popup);

    // Hide the message after 3 seconds (adjust as needed)
    setTimeout(() => {
        document.body.removeChild(popup);
    }, 2000);
}
