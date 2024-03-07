$(document).ready(function() {
    var carouselInner = $('.carousel-inner');

    function slide() {
        var firstMessage = carouselInner.children('.message').first();
        var messageWidth = firstMessage.outerWidth(true);
        carouselInner.animate({ left: -messageWidth }, 500, 'linear', function() {
            $(this).append(firstMessage);
            $(this).css('left', 0);
        });
    }

    setInterval(slide, 5000);
});