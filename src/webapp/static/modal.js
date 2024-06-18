$(document).ready(function() {
    // Get all modal elements
    let modals = $("[data-modal]");
  
    // Add event listener for modal open
    $("[data-modal-target]").click(function() {
      var modalTarget = $(this).data("modal-target");
      $(modalTarget).css("display", "block");
    });
  
    // Add event listener for modal close
    $("[data-modal-close]").click(function() {
      var modal = $(this).closest("[data-modal]");
      modal.css("display", "none");
    });
  
    // Add event listener for modal close on outside click
    $(window).click(function(event) {
      modals.each(function() {
        var modal = $(this);
        if (event.target == modal[0]) {
          modal.css("display", "none");
        }
      });
    });
  });