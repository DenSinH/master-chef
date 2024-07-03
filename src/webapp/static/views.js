const views_url = document.currentScript.getAttribute("data-url");

function getViews() {
    $.ajax({
        type: 'GET',
        url: views_url,
        contentType: 'application/json',
        success: function(response) {
            for (const [recipe, views] of Object.entries(response)) {
                $(`#recipe${recipe} .viewcount-value`).html(views);
            }
        },
        error: function(xhr, status, error) {
            console.error(`failed to retrieve viewcount: ${error}`)
        }
    });
}

// load views on document load
$(document).ready(getViews);