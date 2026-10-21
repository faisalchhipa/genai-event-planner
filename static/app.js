/**
 * Event Planning Assistant — Spatial UI
 * Security: textContent property only. No raw HTML injection via inner/outerHTML or insertAdjacentHTML.
 * Accessibility: WCAG AA, aria-live, keyboard, prefers-reduced-motion.
 * Performance: transform+opacity only; animations paused on hidden tab.
 */

document.addEventListener("DOMContentLoaded", function () {
  "use strict";

  /* ──────────────────────────────────────────────────────────────────────
     FEATURE DETECTION
  ────────────────────────────────────────────────────────────────────── */
  var REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var IS_TOUCH       = window.matchMedia("(pointer: coarse)").matches;
  var NO_PARALLAX    = REDUCED_MOTION || IS_TOUCH;

  /* ──────────────────────────────────────────────────────────────────────
     DOM ELEMENT CACHE (all existing IDs preserved)
  ────────────────────────────────────────────────────────────────────── */
  var planForm           = document.getElementById("plan-form");
  var eventTypeSelect    = document.getElementById("event_type");
  var guestsInput        = document.getElementById("guests");
  var budgetInput        = document.getElementById("budget");
  var eventDateInput     = document.getElementById("event_date");
  var preferencesInput   = document.getElementById("preferences");
  var charCounter        = document.getElementById("char-counter");
  var submitBtn          = document.getElementById("submit-btn");
  var btnText            = document.getElementById("btn-text");
  var btnSpinner         = document.getElementById("btn-spinner");
  var resetBtn           = document.getElementById("reset-btn");
  var statusBanner       = document.getElementById("status-banner");
  var printBtn           = document.getElementById("print-btn");
  var resultsSection     = document.getElementById("results-section");
  var summaryCardsContainer = document.getElementById("summary-cards-container");
  var budgetSummaryText  = document.getElementById("budget-summary-text");
  var budgetVisualBar    = document.getElementById("budget-visual-bar");
  var budgetTableBody    = document.getElementById("budget-table-body");
  var budgetTableFoot    = document.getElementById("budget-table-foot");
  var ideasGrid          = document.getElementById("ideas-grid");
  var ideasSourceBadge   = document.getElementById("ideas-source-badge");
  var ideasDescriptionText = document.getElementById("ideas-description-text");
  var timelineList       = document.getElementById("timeline-list");
  var vendorAlertBox     = document.getElementById("vendor-alert-box");
  var vendorTableBody    = document.getElementById("vendor-table-body");
  var countdownDays      = document.getElementById("countdown-days");
  var countdownHours     = document.getElementById("countdown-hours");
  var countdownMins      = document.getElementById("countdown-mins");
  var countdownSrText    = document.getElementById("countdown-sr-text");

  /* Bar colours for 3D chart (also used as CSS custom properties) */
  var BAR_COLORS = ["#7c6cf0","#22d3ee","#f59e0b","#8b5cf6","#ec4899","#64748b"];

  /* ──────────────────────────────────────────────────────────────────────
     AURORA PARALLAX LAYERS & CURSOR GLOW (inject into body)
  ────────────────────────────────────────────────────────────────────── */
  (function setupAurora() {
    var depths = [
      { cls: "aurora-layer aurora-l1", depth: 0.022 },
      { cls: "aurora-layer aurora-l2", depth: 0.038 },
      { cls: "aurora-layer aurora-l3", depth: 0.015 }
    ];

    var layers = depths.map(function (d) {
      var el = document.createElement("div");
      el.className = d.cls;
      el.setAttribute("aria-hidden", "true");
      el.dataset.depth = String(d.depth);
      document.body.insertBefore(el, document.body.firstChild);
      return el;
    });

    var glow = document.createElement("div");
    glow.className = "cursor-glow";
    glow.setAttribute("aria-hidden", "true");
    document.body.appendChild(glow);

    if (NO_PARALLAX) return;

    var rafId = null;
    var tx = window.innerWidth / 2;
    var ty = window.innerHeight / 2;

    document.addEventListener("mousemove", function (e) {
      tx = e.clientX;
      ty = e.clientY;
      if (!rafId) {
        rafId = requestAnimationFrame(function () {
          rafId = null;
          var cx = tx - window.innerWidth  / 2;
          var cy = ty - window.innerHeight / 2;
          layers.forEach(function (layer) {
            var d = parseFloat(layer.dataset.depth);
            layer.style.setProperty(
              "transform",
              "translate(" + (cx * d) + "px," + (cy * d) + "px)"
            );
          });
          glow.style.setProperty(
            "transform",
            "translate(" + (tx - 200) + "px," + (ty - 200) + "px)"
          );
        });
      }
    });
  }());

  /* ──────────────────────────────────────────────────────────────────────
     CARD LIGHTING & SPECULAR HIGHLIGHT (Zero 3D blur on text/details)
  ────────────────────────────────────────────────────────────────────── */
  (function setupTilt() {
    if (NO_PARALLAX) return;

    var allCards = document.querySelectorAll(".card");

    function applyTilt(card, e) {
      var rect = card.getBoundingClientRect();
      /* Specular highlight: tracks pointer across card surface without 3D text blur */
      var mx = ((e.clientX - rect.left) / rect.width  * 100).toFixed(1);
      var my = ((e.clientY - rect.top)  / rect.height * 100).toFixed(1);
      card.style.setProperty("--mx", mx + "%");
      card.style.setProperty("--my", my + "%");
    }

    function resetTilt(card) {
      card.style.setProperty("--mx", "50%");
      card.style.setProperty("--my", "50%");
    }

    function bindCard(card) {
      var raf = null;
      card.addEventListener("mousemove", function (e) {
        if (!raf) raf = requestAnimationFrame(function () { raf = null; applyTilt(card, e); });
      });
      card.addEventListener("mouseleave", function () {
        if (raf) { cancelAnimationFrame(raf); raf = null; }
        resetTilt(card);
      });
    }

    allCards.forEach(bindCard);

    /* Also bind dynamically added result-cards via MutationObserver */
    var mo = new MutationObserver(function (mutations) {
      mutations.forEach(function (m) {
        m.addedNodes.forEach(function (n) {
          if (n.nodeType === 1 && n.classList && n.classList.contains("card")) bindCard(n);
        });
      });
    });
    mo.observe(document.getElementById("main-content"), { childList: true, subtree: true });
  }());

  /* ──────────────────────────────────────────────────────────────────────
     PAUSE ANIMATIONS WHEN TAB IS HIDDEN
  ────────────────────────────────────────────────────────────────────── */
  document.addEventListener("visibilitychange", function () {
    var state = document.hidden ? "paused" : "running";
    document.documentElement.style.setProperty("--anim-state", state);
    /* Apply to all animated elements (ring, aurora, spinner) */
    var animated = document.querySelectorAll(
      ".countdown-orbit-ring, body::before, .spinner, .aurora-layer"
    );
    animated.forEach(function (el) {
      el.style.setProperty("animation-play-state", state);
    });
  });

  /* ──────────────────────────────────────────────────────────────────────
     FLOATING LABEL HELPERS
  ────────────────────────────────────────────────────────────────────── */
  function initFloatField(input) {
    var wrapper = input.closest(".float-field");
    if (!wrapper) return;

    function update() {
      var hasVal = input.value !== "" && input.value !== null;
      if (hasVal) wrapper.classList.add("has-value");
      else         wrapper.classList.remove("has-value");
    }

    input.addEventListener("input",  update);
    input.addEventListener("change", update);
    update(); /* initial state */
  }

  [guestsInput, budgetInput, eventDateInput, preferencesInput].forEach(initFloatField);
  /* Select always has a value, handled via CSS .float-select rule */

  /* ──────────────────────────────────────────────────────────────────────
     SET MINIMUM DATE
  ────────────────────────────────────────────────────────────────────── */
  var tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  var tomorrowISO = tomorrow.toISOString().split("T")[0];
  eventDateInput.setAttribute("min", tomorrowISO);

  /* ──────────────────────────────────────────────────────────────────────
     CHARACTER COUNTER
  ────────────────────────────────────────────────────────────────────── */
  preferencesInput.addEventListener("input", function () {
    var len = preferencesInput.value.length;
    charCounter.textContent = len + " / 300";
    if (len >= 300) charCounter.classList.add("char-over");
    else            charCounter.classList.remove("char-over");
  });

  /* ──────────────────────────────────────────────────────────────────────
     RESET
  ────────────────────────────────────────────────────────────────────── */
  resetBtn.addEventListener("click", function () {
    planForm.reset();
    charCounter.textContent = "0 / 300";
    charCounter.classList.remove("char-over");
    hideStatus();
    resultsSection.classList.add("hidden");
    stopCountdown();
    eventTypeSelect.focus();
  });

  /* ──────────────────────────────────────────────────────────────────────
     PRINT
  ────────────────────────────────────────────────────────────────────── */
  printBtn.addEventListener("click", function () { window.print(); });

  /* ──────────────────────────────────────────────────────────────────────
     FORM SUBMIT — API CALL (unchanged logic)
  ────────────────────────────────────────────────────────────────────── */
  planForm.addEventListener("submit", function (e) {
    e.preventDefault();
    hideStatus();

    var eventType   = eventTypeSelect.value.trim();
    var guests      = parseInt(guestsInput.value, 10);
    var budget      = parseFloat(budgetInput.value);
    var eventDate   = eventDateInput.value.trim();
    var preferences = preferencesInput.value.trim();

    if (!eventType) {
      showStatus("Please select an event type.", "error");
      eventTypeSelect.focus(); return;
    }
    if (isNaN(guests) || guests < 1 || guests > 5000) {
      showStatus("Guests must be a valid number between 1 and 5,000.", "error");
      guestsInput.focus(); return;
    }
    if (isNaN(budget) || budget <= 0) {
      showStatus("Please enter a valid positive budget in INR (\u20B9).", "error");
      budgetInput.focus(); return;
    }
    if (!eventDate) {
      showStatus("Please choose an event date.", "error");
      eventDateInput.focus(); return;
    }
    if (eventDate < tomorrowISO) {
      showStatus("Event date must be strictly in the future.", "error");
      eventDateInput.focus(); return;
    }

    setLoading(true);

    var payload = {
      event_type:  eventType,
      guests:      guests,
      budget:      budget,
      event_date:  eventDate,
      preferences: preferences
    };

    fetch("/api/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
      .then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok) {
            throw new Error((data && data.error) ? data.error : "Server error " + response.status);
          }
          return data;
        });
      })
      .then(function (data) {
        setLoading(false);
        if (data.success && data.plan) {
          renderPlanResults(data.plan, data.ideas || [], data.ideas_meta || {});
          showStatus("Event plan generated successfully!", "success");
          resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
        } else {
          showStatus(data.error || "Unable to generate plan.", "error");
        }
      })
      .catch(function (err) {
        setLoading(false);
        showStatus(err.message || "Network error. Please try again.", "error");
      });
  });

  /* ──────────────────────────────────────────────────────────────────────
     LOADING STATE
  ────────────────────────────────────────────────────────────────────── */
  function setLoading(on) {
    if (on) {
      submitBtn.setAttribute("disabled", "true");
      btnText.textContent = "Calculating\u2026";
      btnSpinner.classList.remove("hidden");
    } else {
      submitBtn.removeAttribute("disabled");
      btnText.textContent = "Generate Spatial Plan";
      btnSpinner.classList.add("hidden");
    }
  }

  function showStatus(msg, type) {
    statusBanner.textContent = msg;
    statusBanner.className = "status-banner " + (type === "error" ? "error" : "success");
    statusBanner.classList.remove("hidden");
  }
  function hideStatus() {
    statusBanner.textContent = "";
    statusBanner.className = "status-banner hidden";
  }

  /* ──────────────────────────────────────────────────────────────────────
     DOM HELPERS (textContent only; no innerHTML / outerHTML)
  ────────────────────────────────────────────────────────────────────── */
  function clearEl(el) {
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  function mk(tag, cls, text, attrs) {
    var el = document.createElement(tag);
    if (cls)  el.className = cls;
    if (text !== undefined && text !== null) el.textContent = text;
    if (attrs) for (var k in attrs) { if (attrs.hasOwnProperty(k)) el.setAttribute(k, attrs[k]); }
    return el;
  }

  function formatINR(n) {
    return "\u20B9" + Number(n).toLocaleString("en-IN", {
      minimumFractionDigits: 2, maximumFractionDigits: 2
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     COUNTDOWN TIMER
  ────────────────────────────────────────────────────────────────────── */
  var _countdownInterval = null;
  var _countdownDate = null;

  function startCountdown(dateStr) {
    stopCountdown();
    _countdownDate = new Date(dateStr + "T00:00:00");
    tickCountdown();
    _countdownInterval = setInterval(tickCountdown, 30000); /* update every 30s */
  }

  function tickCountdown() {
    var now  = new Date();
    var diff = _countdownDate - now;
    if (diff <= 0) {
      countdownDays.textContent  = "00";
      countdownHours.textContent = "00";
      countdownMins.textContent  = "00";
      countdownSrText.textContent = "Event has passed or is today.";
      stopCountdown();
      return;
    }
    var d = Math.floor(diff / 86400000);
    var h = Math.floor((diff % 86400000) / 3600000);
    var m = Math.floor((diff % 3600000)  / 60000);
    countdownDays.textContent  = pad2(d);
    countdownHours.textContent = pad2(h);
    countdownMins.textContent  = pad2(m);
    countdownSrText.textContent =
      d + " days, " + h + " hours, " + m + " minutes until your event.";
  }

  function stopCountdown() {
    if (_countdownInterval) { clearInterval(_countdownInterval); _countdownInterval = null; }
  }

  function pad2(n) { return n < 10 ? "0" + n : String(n); }

  /* ──────────────────────────────────────────────────────────────────────
     COUNT-UP ANIMATION (for budget table amounts)
  ────────────────────────────────────────────────────────────────────── */
  function animateCountUp(el, target, duration) {
    if (REDUCED_MOTION) { el.textContent = formatINR(target); return; }
    var start     = performance.now();
    var startVal  = 0;
    function step(now) {
      var pct = Math.min((now - start) / duration, 1);
      var ease = 1 - Math.pow(1 - pct, 3); /* ease-out cubic */
      el.textContent = formatINR(startVal + (target - startVal) * ease);
      if (pct < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  /* ──────────────────────────────────────────────────────────────────────
     3D BUDGET BAR CHART
     budget-visual-bar is repurposed as a vertical bar chart.
     Bars rise via IntersectionObserver trigger; amounts count up.
  ────────────────────────────────────────────────────────────────────── */
  function buildBudgetBars(allocations, totalBudget) {
    clearEl(budgetVisualBar);
    var BAR_HEIGHT_MAX = 180; /* px for 100% allocation */
    var barEls = [];
    var amtEls = [];

    allocations.forEach(function (alloc, idx) {
      var color      = BAR_COLORS[idx % BAR_COLORS.length];
      var barH       = Math.max(4, (alloc.percentage / 100) * BAR_HEIGHT_MAX);
      var wrap       = mk("div", "bar-wrap");
      var amtLbl     = mk("div", "bar-amount", "\u20B90");
      var bar        = mk("div", "budget-bar-3d");
      var catLbl     = mk("div", "bar-cat-label",
                          alloc.category.split(" ").slice(0, 2).join(" "));

      bar.setAttribute("title", alloc.category + ": " + alloc.percentage + "%");
      bar.style.setProperty("--bar-color", color);
      bar.style.setProperty("height", "0px"); /* start at 0, animate on reveal */
      bar._targetH   = barH;
      bar._targetAmt = alloc.amount_inr;

      wrap.appendChild(amtLbl);
      wrap.appendChild(bar);
      wrap.appendChild(catLbl);
      budgetVisualBar.appendChild(wrap);
      barEls.push(bar);
      amtEls.push(amtLbl);
    });

    /* Trigger bar reveal via IntersectionObserver */
    var triggered = false;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting && !triggered) {
          triggered = true;
          io.disconnect();
          barEls.forEach(function (bar, i) {
            /* Stagger each bar slightly */
            setTimeout(function () {
              bar.style.setProperty("height", bar._targetH + "px");
              animateCountUp(amtEls[i], bar._targetAmt, 1200);
            }, i * 100);
          });
        }
      });
    }, { threshold: 0.25 });
    io.observe(budgetVisualBar);
  }

  /* ──────────────────────────────────────────────────────────────────────
     TIMELINE INTERSECTIONOBSERVER (fallback for non-scroll-driven browsers)
  ────────────────────────────────────────────────────────────────────── */
  var _timelineIO = null;

  function setupTimelineIO() {
    /* Skip if browser supports scroll-driven animations */
    if (CSS.supports && CSS.supports("animation-timeline", "scroll()")) return;
    if (_timelineIO) _timelineIO.disconnect();

    _timelineIO = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("in-view");
          _timelineIO.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15, rootMargin: "0px 0px -40px 0px" });

    document.querySelectorAll(".timeline-item").forEach(function (item) {
      _timelineIO.observe(item);
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     FLIP CARD LOGIC (keyboard accessible; real <button> toggles)
  ────────────────────────────────────────────────────────────────────── */
  function bindFlipCard(card) {
    var inner    = card.querySelector(".flip-card-inner");
    var showBtn  = card.querySelector(".flip-btn-show");
    var hideBtn  = card.querySelector(".flip-btn-hide");
    var frontDiv = card.querySelector(".flip-front");
    var backDiv  = card.querySelector(".flip-back");
    if (!inner || !showBtn || !hideBtn) return;

    showBtn.addEventListener("click", function () {
      if (REDUCED_MOTION) {
        /* Swap visibility without rotate */
        frontDiv.setAttribute("hidden", "");
        backDiv.removeAttribute("hidden");
        showBtn.setAttribute("aria-expanded", "true");
        hideBtn.focus();
      } else {
        inner.classList.add("flipped");
        showBtn.setAttribute("aria-expanded", "true");
        hideBtn.setAttribute("aria-expanded", "true");
        /* Move focus to back after transition */
        setTimeout(function () { hideBtn.focus(); }, 320);
      }
    });

    hideBtn.addEventListener("click", function () {
      if (REDUCED_MOTION) {
        backDiv.setAttribute("hidden", "");
        frontDiv.removeAttribute("hidden");
        showBtn.setAttribute("aria-expanded", "false");
        showBtn.focus();
      } else {
        inner.classList.remove("flipped");
        showBtn.setAttribute("aria-expanded", "false");
        hideBtn.setAttribute("aria-expanded", "false");
        setTimeout(function () { showBtn.focus(); }, 320);
      }
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     RENDER PLAN RESULTS
  ────────────────────────────────────────────────────────────────────── */
  function renderPlanResults(plan, ideas, ideasMeta) {
    resultsSection.classList.remove("hidden");

    var inputs        = plan.inputs;
    var budgetPlan    = plan.budget_plan;
    var timeline      = plan.timeline;
    var vendors       = plan.vendor_checklist;

    /* 1 — COUNTDOWN RING */
    startCountdown(inputs.event_date);

    /* 2 — SUMMARY CARDS */
    clearEl(summaryCardsContainer);
    var cardsData = [
      { label: "Event Type",   value: inputs.event_type.toUpperCase() },
      { label: "Guest Count",  value: inputs.guests.toLocaleString("en-IN") + " Guests" },
      { label: "Total Budget", value: formatINR(budgetPlan.total_budget_inr) },
      {
        label: "Budget Tier",
        value: budgetPlan.tier.toUpperCase(),
        badge: "badge badge-" + budgetPlan.tier.toLowerCase(),
        sub:   formatINR(budgetPlan.budget_per_guest_inr) + " \u2215 guest"
      }
    ];

    cardsData.forEach(function (c) {
      var cardDiv = mk("div", "summary-card");
      cardDiv.appendChild(mk("div", "summary-card-label", c.label));
      var valDiv = mk("div", "summary-card-value");
      if (c.badge) {
        valDiv.appendChild(mk("span", c.badge, c.value));
      } else {
        valDiv.textContent = c.value;
      }
      cardDiv.appendChild(valDiv);
      if (c.sub) cardDiv.appendChild(mk("div", "field-hint", c.sub));
      summaryCardsContainer.appendChild(cardDiv);
    });

    /* 3 — BUDGET */
    budgetSummaryText.textContent =
      "Tier: " + budgetPlan.tier.toUpperCase() +
      " (\u20B9" + budgetPlan.budget_per_guest_inr.toFixed(0) + " per guest). " +
      (budgetPlan.tier === "tight"
        ? "Tight tier trims Decor to 5 % and grows the contingency buffer to 12 %."
        : "Balanced allocation across all vendor categories with contingency buffer.");

    buildBudgetBars(budgetPlan.allocations || [], budgetPlan.total_budget_inr);

    clearEl(budgetTableBody);
    clearEl(budgetTableFoot);

    var totalPct = 0; var totalAmt = 0;
    (budgetPlan.allocations || []).forEach(function (a) {
      totalPct += a.percentage;
      totalAmt += a.amount_inr;
      var tr = mk("tr");
      tr.appendChild(mk("td", null, a.category));
      tr.appendChild(mk("td", null, a.percentage + "%"));
      tr.appendChild(mk("td", null, formatINR(a.amount_inr)));
      budgetTableBody.appendChild(tr);
    });
    var ftr = mk("tr");
    ftr.appendChild(mk("th", null, "Total"));
    ftr.appendChild(mk("td", null, Math.round(totalPct) + "%"));
    ftr.appendChild(mk("td", null, formatINR(totalAmt)));
    budgetTableFoot.appendChild(ftr);

    /* 4 — IDEAS FLIP CARDS */
    clearEl(ideasGrid);
    var isGemini = ideasMeta.source === "gemini";
    ideasSourceBadge.className = "badge " + (isGemini ? "badge-upcoming" : "badge-tight");
    ideasSourceBadge.textContent =
      (isGemini ? "AI Powered (Gemini)" : "Curated Recommendations") +
      (ideasMeta.cached ? " \u2014 Cached" : "");
    ideasDescriptionText.textContent =
      "5 recommendations for your " + inputs.event_type + " with a " + budgetPlan.tier + " budget.";

    ideas.forEach(function (idea, i) {
      var cardEl   = mk("article", "flip-card");
      var titleStr = idea.title || "";
      var catStr   = idea.category || "Idea";
      var descStr  = idea.description || "";
      var lbl      = "Idea " + (i + 1) + ": " + titleStr;
      cardEl.setAttribute("aria-label", lbl);

      /* flip-card-inner (rotated by JS) */
      var inner = mk("div", "flip-card-inner");
      inner.setAttribute("aria-live", "polite");

      /* Front face */
      var front = mk("div", "flip-face flip-front");
      front.appendChild(mk("span", "idea-category-tag", catStr));
      front.appendChild(mk("h4",  "idea-title", titleStr));
      var showBtn = mk("button", "flip-btn flip-btn-show", "See Details");
      showBtn.setAttribute("aria-expanded", "false");
      showBtn.setAttribute("aria-label", "See full description for: " + titleStr);
      showBtn.setAttribute("type", "button");
      front.appendChild(showBtn);

      /* Back face */
      var back = mk("div", "flip-face flip-back");
      back.appendChild(mk("p", "idea-description", descStr));
      var hideBtn = mk("button", "flip-btn flip-btn-hide", "Back");
      hideBtn.setAttribute("aria-expanded", "false");
      hideBtn.setAttribute("aria-label", "Return to idea summary: " + titleStr);
      hideBtn.setAttribute("type", "button");
      back.appendChild(hideBtn);

      inner.appendChild(front);
      inner.appendChild(back);
      cardEl.appendChild(inner);
      ideasGrid.appendChild(cardEl);

      /* Bind flip behaviour */
      bindFlipCard(cardEl);
    });

    /* 5 — TIMELINE */
    clearEl(timelineList);
    timeline.forEach(function (task) {
      var isPast   = task.is_past_due;
      var itemCls  = "timeline-item " + (isPast ? "past-due" : "upcoming");
      var item     = mk("div", itemCls);

      /* Date column */
      var dateCol  = mk("div", "timeline-item-date", task.target_date);
      var statusBadge = mk("span",
        "badge " + (isPast ? "badge-past-due" : "badge-upcoming"),
        isPast ? "Past Due" : "T\u2212" + task.days_before_event + " days");
      dateCol.appendChild(statusBadge);

      /* Info column */
      var infoCol  = mk("div");
      infoCol.appendChild(mk("div", "timeline-item-title", task.title));
      infoCol.appendChild(mk("div", "timeline-item-desc",  task.description));
      /* Past-due icon + label (accessible text via textContent) */
      if (isPast) {
        var pdLabel = mk("div", "past-due-label");
        pdLabel.appendChild(mk("span", null, "\u26A0\uFE0F")); /* ⚠️ */
        pdLabel.appendChild(mk("span", null, "Action overdue \u2014 reschedule immediately"));
        infoCol.appendChild(pdLabel);
      }

      /* Calendar link */
      var actionCol = mk("div");
      var calLink   = mk("a", "btn btn-outline btn-sm", "Add to Calendar", {
        href:       task.google_calendar_url,
        target:     "_blank",
        rel:        "noopener noreferrer",
        "aria-label": "Add \u201C" + task.title + "\u201D to Google Calendar"
      });
      actionCol.appendChild(calLink);

      item.appendChild(dateCol);
      item.appendChild(infoCol);
      item.appendChild(actionCol);
      timelineList.appendChild(item);
    });

    /* Boot timeline IntersectionObserver after DOM update */
    requestAnimationFrame(setupTimelineIO);

    /* 6 — VENDOR CHECKLIST */
    clearEl(vendorTableBody);
    if (inputs.guests >= 200) {
      vendorAlertBox.classList.remove("hidden");
      vendorAlertBox.textContent =
        "\u26A0\uFE0F Large gathering (" + inputs.guests +
        " guests): Dedicated security bouncers and valet parking marshals " +
        "have been added as mandatory checklist items.";
    } else {
      vendorAlertBox.classList.add("hidden");
    }

    vendors.forEach(function (v) {
      var tr = mk("tr");
      tr.appendChild(mk("td", null, v.category));
      tr.appendChild(mk("td", null, v.task));

      var tdPri = mk("td");
      tdPri.appendChild(mk("span",
        v.mandatory ? "badge badge-mandatory" : "badge badge-comfortable",
        v.mandatory ? "Mandatory" : "Standard"));
      tr.appendChild(tdPri);

      var tdAction = mk("td");
      tdAction.appendChild(mk("a", "btn btn-outline btn-sm", "Search Maps", {
        href:       v.google_maps_url,
        target:     "_blank",
        rel:        "noopener noreferrer",
        "aria-label": "Search " + v.category + " on Google Maps"
      }));
      tr.appendChild(tdAction);
      vendorTableBody.appendChild(tr);
    });
  }

}); /* end DOMContentLoaded */
