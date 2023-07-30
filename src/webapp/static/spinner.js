
$(document).ready(function () {
  $('form').submit(function (event) {
    // Show the spinner and hide the submit button
    $('#spinner').show();
    $('#submit').hide();
  });
});