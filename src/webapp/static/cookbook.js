const pageSize = 20;
var numPages = 1;
var searching = false;
var onlySaved = false;

function toggleOnlySaved() {
    onlySaved = !onlySaved;
    showPages(true);
}

function get_active_recipes(ignoreSearch) {
    let selector = ".recipe-item";
    if (searching && !ignoreSearch) {
        selector += ".search-result";
    }
    if (onlySaved) {
        selector += ".saved";
    }
    return $(selector);
}

function random_recipe() {
    let recipes = get_active_recipes();
    let randomIndex = Math.floor(Math.random() * recipes.length);
    recipes[randomIndex].click();
}

function showPages(doHide) {
    if (doHide) {
        $(".recipe-item").hide();
    }
    let recipes = get_active_recipes().slice(0, numPages * pageSize).show();
}

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

$(document).ready(function () {
    // recipe-items are hidden by default
    showPages(false);

    const searchBar = $('#searchBar');
    const recipeItems = get_active_recipes(true);

    searchBar.on('input', function () {
        const searchTerm = $(this).val().toLowerCase().trim();
        const searchWords = searchTerm.split(/\s+/);
        numPages = 1;

        if (searchTerm) {
            searching = true;
            recipeItems.each(function () {
                const item = $(this);
                const searchableWords = item.find('.searchable').text().toLowerCase().split(/\s+/);

                // Calculate similarity score based on Jaccard index
                const intersection = searchWords.filter(word =>
                    searchableWords.some(searchableWord =>
                        searchableWord.includes(word)
                    )
                );
                const similarityScore = intersection.length / searchWords.length;

                // Customize the threshold based on your needs
                const threshold = 0.5;

                // Consider it a match if the similarity score is above the threshold
                if (similarityScore > threshold) {
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