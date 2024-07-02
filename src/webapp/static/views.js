function getViews(url) {
    $.ajax({
        type: 'GET',
        url: url,
        contentType: 'application/json',
        success: function(response) {
            for (const [recipe, views] of Object.entries(response)) {
                console.log(recipe, views)
                $(`#recipe${recipe} .viewcount-value`).html(views);
            }
        },
        error: function(xhr, status, error) {
            console.error(`failed to retrieve viewcount: ${error}`)
        }
    });
}