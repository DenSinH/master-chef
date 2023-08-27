const pageSize = 20;
var numPages = 1;
var searching = false;

function showPages(doHide) {
    if (doHide) {
        $(".recipe-item").hide();
    }
    if (searching) {
        $(".recipe-item.search-result").slice(0, numPages * pageSize).show();
    }
    else {
        $(".recipe-item").slice(0, numPages * pageSize).show();
    }
}

$(document).ready(function () {
    // recipe-items are hidden by default
    showPages(false);

    const searchBar = $('#searchBar');
    const recipeItems = $('.recipe-item');

    searchBar.on('input', function () {
        let searchTerm = $(this).val().toLowerCase().trim();
        const advanced = searchTerm.startsWith("advanced:");
        if (advanced) {
            searchTerm = searchTerm.replace("advanced:", "").trim();
        }
        numPages = 1;

        if (searchTerm) {
            searching = true;
            recipeItems.each(function () {
                const item = $(this);
                let searchable = item.find('.searchable').text().toLowerCase();
                const advancedSearchable = item.find('.advanced-searchable').text().toLowerCase();
                if (advanced) {
                    searchable += " " + advancedSearchable;
                }

                if (searchable.includes(searchTerm)) {
                    item.addClass("search-result");
                } else {
                    item.removeClass("search-result");
                }
            });
            showPages(true);
        }
        else {
            searching = false;
            recipeItems.removeClass('search-result');
            showPages(true);
        }
    });
});

$(window).scroll(function() {
    if ($(window).scrollTop() + $(window).height() > $(document).height() - 100) {
        let recipeItems;
        if (searching) {
            recipeItems = $(".recipe-item.search-result");
        }
        else {
            recipeItems = $(".recipe-item");
        }
        if (numPages * pageSize < recipeItems.length) {
            numPages++;
            showPages(false);
        }
    }
});

function sortBy(attribute, direction) {
    let list = $(".recipe-list");
    list.find(".recipe-item").sort(function(a, b) {
        let aattr = $(a).data(attribute);
        let battr = $(b).data(attribute);

        if (aattr < battr) {
            return -direction;
        }
        if (battr < aattr) {
            return direction;
        }
        return 0;
    })
    .appendTo(list);
    numPages = 1;
    showPages(true);
}