const saves_url = document.currentScript.getAttribute("data-url");

function getSaved() {
    $.ajax({
        type: 'GET',
        url: saves_url,
        contentType: 'application/json',
        success: function(response) {
            for (let saved of response.saves) {
                $(`#recipe${saved}`).addClass('saved');
            }
            $(".save-icon").removeClass('hidden');
        },
        error: function(xhr, status, error) {
            showPopup('Failed to retrieve saved recipes, are you still logged in?')
        }
    });
}

$(document).ready(getSaved);

function toggleSave(event, collection, recipeId) {
    event.preventDefault();
    event.stopPropagation();
    let element = $(`#recipe${recipeId}`);
    if (element.hasClass('saved')) {
        $.ajax({
            type: 'DELETE',
            url: `/saved/${collection}/${recipeId}`,
            contentType: 'application/json',
            success: function(response) {
                element.removeClass('saved');
            },
            error: function(xhr, status, error) {
                if (xhr.status == 429) {
                    showPopup('You are doing that too fast!');
                }
                else {
                    showPopup('Failed to unsave recipe, are you still logged in?');
                }
            }
        });
    }
    else {
        $.ajax({
            type: 'POST',
            url: `/saved/${collection}/${recipeId}`,
            contentType: 'application/json',
            success: function(response) {
                element.addClass('saved');
            },
            error: function(xhr, status, error) {
                if (xhr.status == 429) {
                    showPopup('You are doing that too fast!');
                }
                else {
                    showPopup('Failed to save recipe, are you still logged in?');
                }
            }
        });
    }
}
