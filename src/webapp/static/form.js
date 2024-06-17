function add_element(parent, selector, index, element, after=true) {
    if (after) {
        if (!$(`${parent} ${selector}`).eq(index).after(element).length) {
            $(parent).append(element);
        }
    }
    else {
        if (!$(`${parent} ${selector}`).eq(index).before(element).length) {
            $(parent).prepend(element);
        }
    }
}


function add_ingredient(index=-1, text="", after=true) {
    const row = $('<div class="ingredient-row">' +
        '<span class="handle"><i class="fas fa-grip-lines"></i></span>' +
        '<input type="text" class="amount" name="ingredient-amount" placeholder="Amount">' +
        `<input type="text" class="ingredient" name="ingredient-type" placeholder="Ingredient" value=${text}>` +
        '<div class="remove-row-container">' +
            '<span class="round-button remove-row"><i class="fas fa-minus"></i></span>' +
        '</div>' +
        '</div>');
    add_element('#ingredientRows', '.ingredient-row', index, row, after);
    set_callbacks();
}

function add_step(index=-1, text="", after=true) {
    const row = $('<div class="preparation-row">' +
        '<span class="handle"><i class="fas fa-grip-lines"></i></span>' +
        `<textarea class="step" name="preparation" placeholder="Step">${text}</textarea>` +
        '<div class="remove-row-container">' +
            '<span class="round-button remove-row"><i class="fas fa-minus"></i></span>' +
        '</div>' +
        '</div>');
    add_element('#preparationRows', '.preparation-row', index, row, after);
    set_callbacks();
}

function add_group(index=-1, text="", after=true) {
    const row = $('<div class="nutrition-row">' +
        '<span class="handle"><i class="fas fa-grip-lines"></i></span>' +
        '<input type="text" class="amount" name="nutrition-amount" placeholder="Amount">' +
        `<input type="text" class="group" name="nutrition-group" placeholder="Group" value="${text}">` +
        '<div class="remove-row-container">' +
            '<span class="round-button remove-row"><i class="fas fa-minus"></i></span>' +
        '</div>' +
        '</div>');
    add_element('#nutritionRows', '.nutrition-row', index, row, after);
    set_callbacks();
}

function get_cursor_pos(element) {
    if (element.selectionStart !== undefined) {
        return element.selectionStart;
    } else {
        // For IE < 9 support
        var range = document.selection.createRange();
        range.moveStart('character', -element.value.length);
        return range.text.length;
    }
}

function set_callbacks() {
    const classes = [".ingredient", ".step", ".group"];
    const callbacks = [add_ingredient, add_step, add_group];
    for (i in classes) {
        const inputs = $(classes[i]);
        const callback = callbacks[i];
        
        inputs.off("keydown");
        inputs.on("keydown", function (e) {
            if (e.which == 13 || e.which == 9) {
                const index = inputs.index(this);

                if (e.shiftKey) {
                    let cursor_pos = get_cursor_pos(this);
                    let input_value = $(this).val();
                    let after_cursor = input_value.substring(cursor_pos);
                    $(this).val(input_value.substring(0, cursor_pos));
                    callback(index, after_cursor);
                }
                else if (index == inputs.length - 1 && $(this).val()) {
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

function resizeAndCompressImage(file, maxWidth, callback) {
    var reader = new FileReader();

    reader.onload = function(e) {
        var img = new Image();

        img.onload = function() {
            var canvas = document.createElement('canvas');
            var ctx = canvas.getContext('2d');

            // Calculate the new dimensions while maintaining the aspect ratio
            var newWidth, newHeight;
            if (img.width > img.height) {
                newWidth = maxWidth;
                newHeight = (img.height * maxWidth) / img.width;
            } else {
                newHeight = maxWidth;
                newWidth = (img.width * maxWidth) / img.height;
            }

            // Set the canvas dimensions
            canvas.width = newWidth;
            canvas.height = newHeight;

            // Draw the image on the canvas
            ctx.drawImage(img, 0, 0, newWidth, newHeight);

            // Convert the canvas content to a compressed JPEG blob
            canvas.toBlob(function(blob) {
                callback(blob);
            }, 'image/jpeg', 0.8);
        };

        img.src = e.target.result;
    };

    reader.readAsDataURL(file);
}

$(document).ready(function () {
    $('.add-ingredient').first().click(() => add_ingredient(0, "", false));
    $('.add-ingredient').last().click(add_ingredient);
    $('.add-step').first().click(() => add_step(0, "", false));
    $('.add-step').last().click(add_step);
    $('.add-group').first().click(() => add_group(0, "", false));
    $('.add-group').last().click(add_group);
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

    function loadThumbnail() {
        $("#thumbnailLoading").show();
        $("#thumbnailError").hide();
        $("#thumbnailPreview").hide();
    }

    function showThumbnail() {
        $("#thumbnailLoading").hide();
        $("#thumbnailPreview").show();
        $("#thumbnailPreview").attr('src', $("#thumbnailField").val());
    }

    var thumbnailTimer;
    $("#thumbnailField").on('keyup', function () {
        clearTimeout(thumbnailTimer);
        thumbnailTimer = setTimeout(showThumbnail, 1000);
        loadThumbnail();
    });

    $("#thumbnailField").on('keydown', function () {
        clearTimeout(thumbnailTimer);
    });

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

    $("#image-upload-input").on("change", function() {
        let file = this.files[0];

        if (file) {
            let old_val = $("#thumbnailField").val();
            $("#thumbnailField").val("");
            $("#thumbnailField").prop("disabled", true);
            $(this).prop("disabled", true);
            loadThumbnail();

            // Create a FormData object and append the file
            resizeAndCompressImage(file, 1024, function(compressedBlob) {
                let formData = new FormData();
                formData.append('image', compressedBlob, $("#recipe-name").val() || file.name);

                // Send the FormData to the server using fetch
                fetch('/add/upload-image', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.link) {
                        $("#thumbnailField").val(data.link);
                    }
                    else {
                        // allow retrying same image
                        this.value = "";
                        show_popup("Did not get URL for uploaded image");
                        $("#thumbnailField").val(old_val);
                    }
                })
                .catch(error => {
                    // allow retrying same image
                    this.value = "";
                    console.error('Error uploading file:', error);
                    show_popup('Error uploading file: ' + error);
                    $("#thumbnailField").val(old_val);
                })
                .finally(() => {
                    $(this).prop("disabled", false);
                    $("#thumbnailField").prop("disabled", false);
                    showThumbnail();
                });
            });
        }
    });

    $("#image-upload").click(function() {
        $("#image-upload-input").click();
    });

    $(".double-select select:first-child").change(function() {
        let sibling = $(this).parent().find("select:nth-child(2)");
        if (this.value === "other" || this.value === "none" ||
            this.value === sibling.val()) {
            sibling.val("");
        }
    });

    $(".double-select select:nth-child(2)").change(function() {
        let sibling = $(this).parent().find("select:first-child");
        if (this.value === sibling.val()) {
            $(this).val("");
        }
        else if ($(this).val() && (sibling.val() === "other" || sibling.val() === "none")) {
            sibling.val($(this).val());
            $(this).val("");
        }
    });
});