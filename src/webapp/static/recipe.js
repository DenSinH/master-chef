
function delete_recipe() {
    if (confirm("Are you sure you want to delete this recipe?")) {
        $.post("{{ url_for('delete_recipe', id=recipe_id) }}", function() {
          window.location.href = "{{ url_for('index') }}";
        })
        .fail(function(resp) {
            if (resp.status === 401) {
                // unauthorized, redirect to login page
                window.location.href = "{{ url_for('login_form') }}";
            }
            else {
                alert("Failed to delete recipe");
            }
        });
    }
}

$(document).ready(function() {
    $(".ingredients li").click(function() {
        $(this).toggleClass("active");
    });
    $(".instructions li").click(function() {
        $(this).toggleClass("active");
    });
});