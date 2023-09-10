
function add_ingredient() {
    const row = $('<div class="ingredient-row">' +
        '<input type="text" class="amount" name="ingredient-amount" placeholder="Amount">' +
        '<input type="text" class="ingredient" name="ingredient-type" placeholder="Ingredient">' +
        '<span class="round-button remove-row"><i class="fas fa-minus"></i></span>' +
        '</div>');
    $('#ingredientRows').append(row);
    set_callbacks();
}

function add_step() {
    const row = $('<div class="preparation-row">' +
        '<textarea class="step" name="preparation" placeholder="Step"></textarea>' +
        '<span class="round-button remove-row"><i class="fas fa-minus"></i></span>' +
        '</div>');
    $('#preparationRows').append(row);
    set_callbacks();
}

function add_group() {
    const row = $('<div class="ingredient-row">' +
        '<input type="text" class="amount" name="nutrition-amount" placeholder="Amount">' +
        '<input type="text" class="ingredient" name="nutrition-group" placeholder="Group">' +
        '<span class="round-button remove-row"><i class="fas fa-minus"></i></span>' +
        '</div>');
    $('#nutritionRows').append(row);
    set_callbacks();
}

function set_callbacks() {
    const classes = [".ingredient", ".step", ".group"];
    const callbacks = [add_ingredient, add_step, add_group];
    for (i in classes) {
        const inputs = $(classes[i]);
        const callback = callbacks[i];

        inputs.on("keydown", function (e) {
            if (e.which == 13 || e.which == 9) {
                const index = inputs.index(this);
                if (index == inputs.length - 1 && $(this).val()) {
                    // don't prevent default, since
                    // it will go to the new field
                    // the enter callback has already
                    // been altered elsewhere
                    callback();
                }
            }
        });
    }
}

$(document).ready(function () {
    $('#addIngredient').click(add_ingredient);
    $('#addStep').click(add_step);
    $('#addGroup').click(add_group);
    set_callbacks();

    $(document).on('click', '.remove-row', function () {
        $(this).parent().parent().remove();
    });

    $('#recipe-form').on('keydown', 'input, textarea', function (event) {
        if (event.which == 13) {
            event.preventDefault();
            const form_fields = $("#recipe-form input, #recipe-form textarea");
            const index = form_fields.index(this);
            if (index + 1 < form_fields.length) {
                form_fields[index + 1].focus();
            }
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

    new Sortable(document.getElementById('ingredientRows'), {
        animation: 150,
        ghostClass: 'sortable-ghost',
        handle: ".handle",
    });

    new Sortable(document.getElementById('nutritionRows'), {
        animation: 150,
        ghostClass: 'sortable-ghost',
        handle: ".handle",
    });

    new Sortable(document.getElementById('preparationRows'), {
        animation: 150,
        ghostClass: 'sortable-ghost',
        handle: ".handle",
    });
});