const post_url = document.currentScript.getAttribute("post-url");
const delete_url = document.currentScript.getAttribute("delete-url");

function editReview() {
    let userReview = $("#userReview");
    let userRating = $('#userRating');
    userReview.prop('contenteditable', true);
    userReview.addClass('editing');
    userRating.addClass('editing');
    $('#reviewSubmitButton').removeClass('hidden');
    $('#reviewEditButton').addClass('hidden');
}

function stopEditReview() {
    let userReview = $("#userReview");
    let userRating = $('#userRating');
    userReview.prop('contenteditable', false);
    userReview.removeClass('editing');
    userRating.removeClass('editing');
    $('#reviewSubmitButton').addClass('hidden');
    $('#reviewEditButton').removeClass('hidden');
}

function updateRating(stars) {
    $('#userRating span').removeClass('selected');
    $('#userRating span:lt(' + stars + ')').addClass('selected');
    $('#userRating').attr('data-rating', stars);
}

// Handle star clicks for user rating
$(document).ready(function() {
    $('#userRating span').on('click', function() {
        if ($('#userRating').hasClass('editing')) {
            let stars = $(this).index() + 1;
            updateRating(stars);
        }
    });
})

function submitReview() {
    let userReview = $("#userReview");
    let userReviewContent = userReview.text();
    let userRating = $('#userRating');
    let selectedRating = parseInt(userRating.attr('data-rating'));
    if (selectedRating === 0) {
        showPopup("You must give at least 1 star");
        return;
    }

    if (selectedRating == userRating.attr('data-last-rating') && userReviewContent == userReview.attr('data-last-review')) {
        showPopup('Comment posted!');
        return;
    }

    $.ajax({
        type: 'POST',
        url: post_url,
        contentType: 'application/json',
        data: JSON.stringify({
            rating: selectedRating,
            text: userReviewContent
        }),
        success: function(response) {
            userRating.attr('data-last-rating', selectedRating);
            userReview.attr('data-last-review', userReviewContent);
            showPopup('Comment posted!');
            stopEditReview();
        },
        error: function(xhr, status, error) {
            if (xhr.status == 429) {
                showPopup('You are doing that too fast! Try again later...');
            }
            else {
                try {
                    var errorResponse = JSON.parse(xhr.responseText);
                    $("#errors").html(`<p>${errorResponse.error}</p>`);
                } catch (e) {
                    console.error("Error parsing JSON response:", e);
                    showPopup('There was a problem posting your review...');
                }
            }
        }
    });
}

function deleteReview() {
    $.ajax({
        type: 'DELETE',
        url: delete_url,
        contentType: 'application/json',
        success: function(response) {
            updateRating(0);
            $('#userRating').attr('data-last-rating', 0);
            $('#userReview').text('');
            $('#userReview').attr('data-last-review', '');
            showPopup('Comment deleted!');
            editReview();
        },
        error: function(error) {
            if (xhr.status == 429) {
                showPopup('You are doing that too fast! Try again later...');
            }
            else {
                try {
                    var errorResponse = JSON.parse(xhr.responseText);
                    $("#errors").html(`<p>${errorResponse.error}</p>`);
                } catch (e) {
                    console.error("Error parsing JSON response:", e);
                    showPopup('There was a problem deleting your review...');
                }
            }
        }
    });
}
