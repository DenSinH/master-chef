const recipe_id = document.currentScript.getAttribute("recipe-id");

function shareRecipe() {
    if (navigator.share) {
        try {
            const title = document.title;
            let url;
            if (window.location.pathname.split('/').filter((section) => section).length >= 4) {
                // url has name of recipe (/recipe/collection/id/name)
                url = window.location.href;
            }
            else {
                // append name to url
                url = window.location.href.replace(/\/+$/g, '') + '/' +
                      document.title.replace(/ /g, '-').replace(/[^\w-_]/g, '').toLowerCase();
            }
            navigator.share({
                title: title,
                text: 'Check out this delicious recipe!',
                url: url
            });
        } catch (error) {
            copyUrl();
        }
    } else {
        // Fallback for browsers that do not support the Web Share API
        copyUrl();
    }
}

function copyUrl() {
  navigator.clipboard.writeText(window.location.href);
  showPopup('URL Copied!');
}

function reduce(numerator, denominator) {
  let gcd = function gcd(a,b){
    return b ? gcd(b, a % b) : a;
  };
  gcd = gcd(numerator, denominator);
  return [numerator / gcd, denominator / gcd];
}

function formatFrac(numerator, denominator) {
  if (denominator === 1) {
  	return String(numerator);
  }
  else if (numerator === denominator) {
  	return "1";
  }
  else if (numerator < denominator) {
    return numerator + "/" + denominator;
  }
  else {
    return +(numerator / denominator).toFixed(2);
  }
}

function convert(amount, base, people) {
  const specre = /[½⅓⅕⅙⅛⅔⅖⅚⅜¾⅗⅝⅞⅘¼⅐⅑⅒↉]/i;
  const specchar = {
  	'½' : [1, 2],
    '⅓' : [1, 3],
    '⅕' : [1, 5],
    '⅙' : [1, 6],
    '⅛' : [1, 8],
    '⅔' : [2, 3],
    '⅖' : [2, 5],
    '⅚' : [5, 6],
    '⅜' : [3, 8],
    '¾' : [3, 4],
    '⅗' : [3, 5],
    '⅝' : [5, 8],
    '⅞' : [7, 8],
    '⅘' : [4, 5],
    '¼' : [1, 4],
    '⅐' : [1, 7],
    '⅑' : [1, 9],
    '⅒' : [1, 10],
  }
  const amtre = /(\d+)(?:\s*([\/\.,])\s*(\d+))?/i;
  const amttext = /^\D*$/;
  const amtret = /^\D*(\d+)(?:\s*([\/\.,])\s*(\d+))?\D*$/i;
  // converted int
  if (Number.isInteger(amount)) {
    let reduced = reduce(people * amount, base);
    return formatFrac(reduced[0], reduced[1]);
  }
  // converted float
  else if (typeof amount === "number" && !Number.isInteger(amount)) {
    return (people * amount) / base;
  }
  // special character fractions
  else if (specre.test(amount)) {
    // digits leftover in amount, do simple conversion
  	if (/\d/.test(amount)) {
      let reduced = reduce(people, base);
      let formatted = formatFrac(reduced[0], reduced[1]);
      if (formatted == 1) {
        return amount;
      }
      return formatted  + " * " + amount;
    }
    // compute transformed fraction
  	let transformed = amount.replace(specre, function(f) {
      let reduced = reduce(people * specchar[f][0], base * specchar[f][1]);
      return formatFrac(reduced[0], reduced[1]);
    });
    return transformed;
  }
  // only text unit (snuf, a bit, some)
  else if (amttext.test(amount)) {
  	return amount;
  }
  // properly formatted fractional / floating point amount (1.2, 3, 4,5, 2/3)
  else if (amtret.test(amount)) {
    let transformed = amount.replace(amtre, function(s, n, sep, d) {
      if (sep === "/") {
        if (d === undefined) {
          d = "1";
        }
        let reduced = reduce(people * parseInt(n), base * parseInt(d));
      	return formatFrac(reduced[0], reduced[1]);
      }
      else {
        return +(people * parseFloat(n + "." + d) / base).toFixed(2);
      }
    });

    return transformed;
  }
  // improperly formatted amount, simple conversion
  else {
  	let formatted = formatFrac(people, base);
    if (formatted == 1) {
    	return amount;
    }
    return formatted  + " * " + amount;
  }
}

function setAmounts(base, people) {
    let people_amount = $("#people-amount");
    people_amount.text(people);

    people = parseInt(people);
    base = parseInt(base);

    if (typeof base === 'number' && !isNaN(base) && typeof people === 'number' && !isNaN(people)) {
        if (people == base) {
            $(".people-based-on").addClass("hidden");
            $(".ingredients .ingredient-amount").each(function() {
                let el = $(this);
                el.text(el.data("base"));
            });
        }
        else {
            $(".people-based-on").removeClass("hidden");
            $(".ingredients .ingredient-amount").each(function() {
                let el = $(this);
                el.text(convert(el.data("base"), base, people));
            });
        }
    }
}

function setValue(key, value) {
  localStorage.setItem(`${recipe_id}:${key}`, value);
}

function getValue(key) {
  return localStorage.getItem(`${recipe_id}:${key}`);
}


function incrPeople() {
    let people_amount = $("#people-amount");
    let people = parseInt(people_amount.text()) + 1;
    setValue('people', people);
    let base = parseInt(people_amount.data("base"));
    setAmounts(base, people);
}

function decrPeople() {
    let people_amount = $("#people-amount");
    let people = parseInt(people_amount.text()) - 1;
    if (people >= 1) {
        setValue('people', people);
        let base = parseInt(people_amount.data("base"));
        setAmounts(base, people);
    }
    else {
        // cannot go below 1 person
    }
}

function resetIngredients() {
  let people_amount = $("#people-amount");
  let base = parseInt(people_amount.data("base"));
  setAmounts(base, base);
  setValue('people', base);
  $(".ingredients tr").each(function(index) {
    $(this).removeClass("active");
    setValue("ingredients-" + index, false);
  });
}

function resetInstructions() {
  $(".instructions li").each(function(index) {
    $(this).removeClass("active");
    setValue("instructions-" + index, false);
  });
}

$(document).ready(function() {
    // Load the toggled state from localStorage
    $(".ingredients tr").each(function(index) {
      if (getValue("ingredients-" + index) === "true") {
        $(this).addClass("active");
      }
    });

    $(".instructions li").each(function(index) {
      if (getValue("instructions-" + index) === "true") {
        $(this).addClass("active");
      }
    });

    // Toggle the class and save the state to localStorage
    $(".ingredients tr").click(function() {
      $(this).toggleClass("active");
      var index = $(".ingredients tr").index(this);
      setValue("ingredients-" + index, $(this).hasClass("active"));
    });

    $(".instructions li").click(function() {
      $(this).toggleClass("active");
      var index = $(".instructions li").index(this);
      setValue("instructions-" + index, $(this).hasClass("active"));
    });


    let people = getValue('people');
    if (people) {
      let people_amount = $("#people-amount");
      let base = parseInt(people_amount.data("base"));
      setAmounts(base, people);
    }
    $("#incr-people").click(incrPeople);
    $("#decr-people").click(decrPeople);
    $("ref").click(function(e) {
      e.stopPropagation();
      let ingredient = $("#ingredient-" + $(this).attr('data-ingredient'));
      showPopup(`${ingredient.find('.ingredient-amount').text()} ${ingredient.find(':not(.ingredient-amount)').text()}`.trim());
    });
});