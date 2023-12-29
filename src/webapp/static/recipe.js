function share_recipe() {
    if (navigator.share) {
        try {
            const title = document.title;
            let url;
            if (window.location.pathname.split('/').filter((section) => section).length >= 3) {
                // url has name of recipe (/recipe/id/name)
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
            copy_url();
        }
    } else {
        // Fallback for browsers that do not support the Web Share API
        copy_url();
    }
}

function show_popup(message) {
    const popup = document.createElement('div');
    popup.textContent = message;
    popup.style.position = 'fixed';
    popup.style.top = '10px';
    popup.style.left = '50%';
    popup.style.transform = 'translateX(-50%)';
    popup.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
    popup.style.color = 'white';
    popup.style.padding = '10px 20px';
    popup.style.borderRadius = '5px';
    popup.style.zIndex = '9999';

    document.body.appendChild(popup);

    // Hide the message after 3 seconds (adjust as needed)
    setTimeout(() => {
        document.body.removeChild(popup);
    }, 2000);
}

function copy_url() {
    const textArea = document.createElement('textarea');
    textArea.value = window.location.href;
    document.body.appendChild(textArea);
    textArea.select();
    document.execCommand('copy');
    document.body.removeChild(textArea);

    show_popup('URL Copied!');
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
    return formatFrac(people * amount, base);
  }
  // converted float
  else if (typeof amount === "number" && !Number.isInteger(amount)) {
    return (people * amount) / base;
  }
  // special character fractions
  else if (specre.test(amount)) {
    // digits leftover in amount, do simple conversion
  	if (/\d/.test(amount)) {
      let formatted = formatFrac(people, base);
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

function set_amounts(base, people) {
    if (people === base) {
        $(".ingredients .ingredient-amount").each(function() {
            let el = $(this);
            el.text(el.data("base"));
        });
    }
    else {
        $(".ingredients .ingredient-amount").each(function() {
            let el = $(this);
            el.text(convert(el.data("base"), base, people));
        });
    }
}

function incr_people() {
    let people_amount = $("#people-amount");
    let people = parseInt(people_amount.text()) + 1;
    people_amount.text(people);
    let base = parseInt(people_amount.data("base"));
    set_amounts(base, people);
}

function decr_people() {
    let people_amount = $("#people-amount");
    let people = parseInt(people_amount.text()) - 1;
    if (people >= 1) {
        people_amount.text(people);
        let base = parseInt(people_amount.data("base"));
        set_amounts(base, people);
    }
    else {
        // cannot go below 1 person
    }
}

$(document).ready(function() {
    $(".ingredients tr").click(function() {
        $(this).toggleClass("active");
    });
    $(".instructions li").click(function() {
        $(this).toggleClass("active");
    });
    $("#incr-people").click(incr_people);
    $("#decr-people").click(decr_people);
});