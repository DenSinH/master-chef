$(document).ready(function() {
    var carouselInner = $('.carousel-inner');

    function slide() {
        if (document.hidden) return;

        var firstMessage = carouselInner.children('.message').first();
        var messageWidth = firstMessage.outerWidth(true);

        carouselInner.stop(true).animate(
            { left: -messageWidth },
            500,
            'linear',
            function() {
                $(this).append(firstMessage).css('left', 0);
            }
        );
    }

    setInterval(slide, 5000);

    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            carouselInner.stop(true, true).css('left', 0);
        }
    });
});