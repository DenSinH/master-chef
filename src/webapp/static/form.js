
$(document).ready(function () {
    $('#addIngredient').click(function () {
        const row = $('<div class="ingredient-row">' +
            '<input type="text" class="amount" name="ingredient-amount" placeholder="Amount">' +
            '<input type="text" class="ingredient" name="ingredient-type" placeholder="Ingredient">' +
            '<span class="round-button remove-row"><i class="fas fa-minus"></i></span>' +
            '</div>');
        $('#ingredientRows').append(row);
    });

    $('#addStep').click(function () {
        const row = $('<div class="preparation-row">' +
            '<textarea class="step" name="preparation" placeholder="Step"></textarea>' +
            '<span class="round-button remove-row"><i class="fas fa-minus"></i></span>' +
            '</div>');
        $('#preparationRows').append(row);
    });

    $('#addGroup').click(function () {
        const row = $('<div class="ingredient-row">' +
            '<input type="text" class="amount" name="nutrition-amount" placeholder="Amount">' +
            '<input type="text" class="ingredient" name="nutrition-group" placeholder="Group">' +
            '<span class="round-button remove-row"><i class="fas fa-minus"></i></span>' +
            '</div>');
        $('#nutritionRows').append(row);
    });

    $(document).on('click', '.remove-row', function () {
        $(this).parent().remove();
    });

    $('#recipe-form').on('keydown', 'input', function (event) {
        if (event.which == 13) {
            event.preventDefault();
        }
    });

    $("#recipe-form").submit(function() {
        // set empty amounts to -1 (placeholder)
        $(this).find("input.amount").each(function() {
            if ($(this).val() == '') {
                $(this).val('-1');
            }
        });
        $(this).find("input.ingredient").each(function() {
            if ($(this).val() == '') {
                $(this).val('null');
            }
        });
        $(this).find("input.group").each(function() {
            if ($(this).val() == '') {
                $(this).val('null');
            }
        });
    });

    var thumbnailTimer;
    $("#thumbnailField").on('keyup', function () {
        clearTimeout(thumbnailTimer);
        thumbnailTimer = setTimeout(doneTyping, 1000);
        $("#thumbnailLoading").show();
        $("#thumbnailError").hide();
        $("#thumbnailPreview").hide();
    });

    $("#thumbnailField").on('keydown', function () {
        clearTimeout(thumbnailTimer);
    });

    function doneTyping () {
        $("#thumbnailLoading").hide();
        $("#thumbnailPreview").show();
        $("#thumbnailPreview").attr('src', $("#thumbnailField").val());
    }
});