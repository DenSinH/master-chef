
function getSaved(collection) {
    $.ajax({
        type: 'GET',
        url: `/saved/${collection}`,
        contentType: 'application/json',
        success: function(response) {
            for (let saved of response.saves) {
                $(`#recipe${saved}`).addClass('saved');
            }
            $(".save-icon").removeClass('hidden');
        },
        error: function(xhr, status, error) {
            show_popup('Failed to retrieve saved recipes, are you still logged in?')
        }
    });
}

function getSavedSingle(collection, recipeId) {
    $.ajax({
        type: 'GET',
        url: `/saved/${collection}/${recipeId}`,
        contentType: 'application/json',
        success: function(response) {
            if (response.saved) {
                $(`#recipe${recipeId}`).addClass('saved');
            }
            $(".save-icon").removeClass('hidden');
        },
        error: function(xhr, status, error) {
            show_popup('Failed to retrieve saved status, are you still logged in?')
        }
    });
}

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
                    show_popup('You are doing that too fast!');
                }
                else {
                    show_popup('Failed to unsave recipe, are you still logged in?');
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
                    show_popup('You are doing that too fast!');
                }
                else {
                    show_popup('Failed to save recipe, are you still logged in?');
                }
            }
        });
    }
    element.addClass
}
