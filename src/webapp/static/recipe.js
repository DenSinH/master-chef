

function share_recipe() {
    if (navigator.share) {
        try {
            const title = document.title;
            let url;
            if (window.location.pathname.split('/').filter((section) => section).length >= 3) {
                // url has name of recipe (/recipe/id/name)
                url = window.location.href;
            }
            else {
                // append name to url
                url = window.location.href.replace(/\/+$/g, '') + '/' +
                      document.title.replace(/ /g, '-').replace(/[^\w-_]/g, '').toLowerCase();
            }
            navigator.share({
                title: title,
                text: 'Check out this delicious recipe!',
                url: url
            });
        } catch (error) {
            copy_url();
        }
    } else {
        // Fallback for browsers that do not support the Web Share API
        copy_url();
    }
}

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

    document.body.appendChild(popup);

    // Hide the message after 3 seconds (adjust as needed)
    setTimeout(() => {
        document.body.removeChild(popup);
    }, 2000);
}

function copy_url() {
    const textArea = document.createElement('textarea');
    textArea.value = window.location.href;
    document.body.appendChild(textArea);
    textArea.select();
    document.execCommand('copy');
    document.body.removeChild(textArea);

    show_popup('URL Copied!');
}

$(document).ready(function() {
    $(".ingredients tr").click(function() {
        $(this).toggleClass("active");
    });
    $(".instructions li").click(function() {
        $(this).toggleClass("active");
    });
});