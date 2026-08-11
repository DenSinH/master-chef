
$(document).ready(function () {
  $('form').on('submit', function (event) {
    // Submitting this form normally would immediately navigate away,
    // blanking the page (and hiding the spinner) while the server is still
    // translating (potentially slow). Instead, submit via fetch to start the
    // translation in the background, then stream its progress with a native
    // EventSource (which reconnects automatically without restarting the
    // translation), showing the raw JSON as ChatGPT generates it, and
    // navigate to the result once a final "done" event arrives.
    event.preventDefault();

    const form = this;
    const jsonPreview = $('#json-preview');

    $('#spinner').show();
    $('#submit').hide();
    jsonPreview.text('').show();

    function fail(message) {
      showPopup(message);
      $('#spinner').hide();
      $('#submit').show();
    }

    fetch(form.action, {
      method: form.method || 'POST',
      body: new FormData(form),
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (data.redirect) {
          window.location.href = data.redirect;
          return;
        }

        const es = new EventSource(data.stream);

        es.addEventListener('progress', function (evt) {
          const data = JSON.parse(evt.data);
          jsonPreview.append(document.createTextNode(data.text));
          jsonPreview.scrollTop(jsonPreview[0].scrollHeight);
        });

        es.addEventListener('done', function (evt) {
          es.close();
          const data = JSON.parse(evt.data);
          window.location.href = data.redirect;
        });

        es.addEventListener('error', function (evt) {
          // A generic connection error (e.g. a transient network blip) has
          // no `data`, and EventSource will retry automatically, so it
          // shouldn't be treated as a failure here. Only a named "error"
          // event sent by the server carries data.
          if (!evt.data) {
            return;
          }

          es.close();
          const data = JSON.parse(evt.data);
          if (data.redirect) {
            window.location.href = data.redirect;
          } else {
            fail(data.message);
          }
        });
      })
      .catch(function (error) {
        console.error('Error submitting form:', error);
        fail('Something went wrong, please try again: ' + error);
      });
  });
});
