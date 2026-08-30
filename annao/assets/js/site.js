/* Anna O — liten progressiv forbedring. Siden fungerer uten JS. */
(function () {
  "use strict";

  /* --- Mobilmeny -------------------------------------------------------- */
  var toggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("hovedmeny");

  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!open));
      nav.setAttribute("data-open", String(!open));
    });

    nav.addEventListener("click", function (e) {
      if (e.target.closest("a")) {
        toggle.setAttribute("aria-expanded", "false");
        nav.setAttribute("data-open", "false");
      }
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
        toggle.setAttribute("aria-expanded", "false");
        nav.setAttribute("data-open", "false");
        toggle.focus();
      }
    });
  }

  /* --- Skygge/linje på header ved scroll --------------------------------- */
  var header = document.querySelector(".site-header");
  if (header) {
    var onScroll = function () {
      header.setAttribute("data-scrolled", String(window.scrollY > 8));
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  /* --- Innfading ved scroll ---------------------------------------------- */
  var reveals = document.querySelectorAll("[data-reveal]");
  if (reveals.length && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    reveals.forEach(function (el) { io.observe(el); });
  } else {
    reveals.forEach(function (el) { el.classList.add("is-visible"); });
  }

  /* --- "Åpent nå" --------------------------------------------------------
     Åpningstider som [åpne, stenge] i lokal tid, 0 = søndag.
     Endres ett sted: her og i HTML-tabellen på kontaktsiden.
     Merk: dette er en enkel visning som ikke tar høyde for helligdager. */
  var HOURS = {
    1: ["10:00", "17:00"],
    2: ["10:00", "17:00"],
    3: ["10:00", "17:00"],
    4: ["10:00", "18:00"],
    5: ["10:00", "17:00"],
    6: ["10:00", "15:00"],
    0: null
  };

  var toMinutes = function (hhmm) {
    var p = hhmm.split(":");
    return parseInt(p[0], 10) * 60 + parseInt(p[1], 10);
  };

  var badges = document.querySelectorAll("[data-status]");
  if (badges.length) {
    var now = new Date();
    var today = HOURS[now.getDay()];
    var mins = now.getHours() * 60 + now.getMinutes();
    var isOpen = !!today && mins >= toMinutes(today[0]) && mins < toMinutes(today[1]);

    var label;
    if (isOpen) {
      label = "Åpent nå · til " + today[1];
    } else {
      // Finn neste dag med åpningstid
      var next = null;
      for (var i = today && mins < toMinutes(today[0]) ? 0 : 1; i <= 7; i++) {
        var d = (now.getDay() + i) % 7;
        if (HOURS[d]) {
          next = { offset: i, open: HOURS[d][0] };
          break;
        }
      }
      if (!next) {
        label = "Stengt nå";
      } else if (next.offset === 0) {
        label = "Åpner i dag " + next.open;
      } else if (next.offset === 1) {
        label = "Åpner i morgen " + next.open;
      } else {
        var names = ["søndag", "mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag"];
        label = "Åpner " + names[(now.getDay() + next.offset) % 7] + " " + next.open;
      }
    }

    badges.forEach(function (el) {
      el.textContent = label;
      el.setAttribute("data-open", String(isOpen));
      el.hidden = false;
    });
  }

  /* --- Årstall i footer --------------------------------------------------- */
  document.querySelectorAll("[data-year]").forEach(function (el) {
    el.textContent = String(new Date().getFullYear());
  });
})();
