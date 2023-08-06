
// Get all the dropdown from document
$(".dropdown-toggle").each(dropDownFunc);

// Dropdown Open and Close function
function dropDownFunc() {
    if($(this).hasClass("click-dropdown")) {
        $(this).on("click", function (e) {
            e.preventDefault();

            if (this.nextElementSibling.classList.contains("dropdown-active") === true) {
                // Close the clicked dropdown
                this.parentElement.classList.remove("dropdown-open");
                this.nextElementSibling.classList.remove("dropdown-active");

            } else {
                // Close the opend dropdown
                closeDropdown();

                // add the open and active class(Opening the DropDown)
                this.parentElement.classList.add("dropdown-open");
                this.nextElementSibling.classList.add("dropdown-active");
            }
        });
    }

    if($(this).hasClass("hover-dropdown")) {
        function dropdownHover(e) {
            if(e.type == "mouseover"){
                closeDropdown();

                // add the open and active class(Opening the DropDown)
                this.parentElement.classList.add("dropdown-open");
                this.nextElementSibling.classList.add("dropdown-active");
            }
        }

        $(this).on("mouseover", dropdownHover);
        $(this).on("mouseout", dropdownHover);
    }
};

window.addEventListener("click", function (e) {
    // Close the menu if click happen outside menu
    if (e.target.closest(".dropdown-container") === null) {
        closeDropdown();
    }
});

function closeDropdown() {
    $(".dropdown-container").each(function () {
        $(this).removeClass("dropdown-open")
    });

    $(".dropdown-menu").each(function () {
        $(this).removeClass("dropdown-active");
    });
}

$(".dropdown-menu").each(function() {
    $(this).on("mouseleave", closeDropdown);
});

$(".dropdown-item").on("click", function() {
    $(this).closest(".dropdown-container").find(".dropdown-toggle").html($(this).html());
    closeDropdown();
});