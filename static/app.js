/**
 * Event Planning Assistant Frontend Logic
 * Security Directive: textContent property only. Zero raw HTML injection.
 * Accessible, Responsive, and WCAG AA Compliant.
 */

document.addEventListener("DOMContentLoaded", function () {
  "use strict";

  // Form & Input elements
  var planForm = document.getElementById("plan-form");
  var eventTypeSelect = document.getElementById("event_type");
  var guestsInput = document.getElementById("guests");
  var budgetInput = document.getElementById("budget");
  var eventDateInput = document.getElementById("event_date");
  var preferencesInput = document.getElementById("preferences");
  var charCounter = document.getElementById("char-counter");
  var submitBtn = document.getElementById("submit-btn");
  var btnText = document.getElementById("btn-text");
  var btnSpinner = document.getElementById("btn-spinner");
  var resetBtn = document.getElementById("reset-btn");
  var statusBanner = document.getElementById("status-banner");
  var printBtn = document.getElementById("print-btn");

  // Results containers
  var resultsSection = document.getElementById("results-section");
  var summaryCardsContainer = document.getElementById("summary-cards-container");
  var budgetSummaryText = document.getElementById("budget-summary-text");
  var budgetVisualBar = document.getElementById("budget-visual-bar");
  var budgetTableBody = document.getElementById("budget-table-body");
  var budgetTableFoot = document.getElementById("budget-table-foot");
  var ideasGrid = document.getElementById("ideas-grid");
  var ideasSourceBadge = document.getElementById("ideas-source-badge");
  var ideasDescriptionText = document.getElementById("ideas-description-text");
  var timelineList = document.getElementById("timeline-list");
  var vendorAlertBox = document.getElementById("vendor-alert-box");
  var vendorTableBody = document.getElementById("vendor-table-body");

  // Color palette for visual budget bar
  var BAR_COLORS = ["#2563eb", "#059669", "#d97706", "#7c3aed", "#db2777", "#475569"];

  // Set minimum event date to tomorrow
  var tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  var tomorrowISO = tomorrow.toISOString().split("T")[0];
  eventDateInput.setAttribute("min", tomorrowISO);

  // Preference character counter
  preferencesInput.addEventListener("input", function () {
    var length = preferencesInput.value.length;
    charCounter.textContent = length + " / 300";
    if (length >= 300) {
      charCounter.style.color = "var(--color-danger)";
    } else {
      charCounter.style.color = "var(--color-text-muted)";
    }
  });

  // Reset form handler
  resetBtn.addEventListener("click", function () {
    planForm.reset();
    charCounter.textContent = "0 / 300";
    charCounter.style.color = "var(--color-text-muted)";
    hideStatus();
    resultsSection.classList.add("hidden");
    eventTypeSelect.focus();
  });

  // Print handler
  printBtn.addEventListener("click", function () {
    window.print();
  });

  // Form submit handler
  planForm.addEventListener("submit", function (e) {
    e.preventDefault();
    hideStatus();

    var eventType = eventTypeSelect.value.trim();
    var guests = parseInt(guestsInput.value, 10);
    var budget = parseFloat(budgetInput.value);
    var eventDate = eventDateInput.value.trim();
    var preferences = preferencesInput.value.trim();

    // Client-side quick validation
    if (!eventType) {
      showStatus("Please select an event type.", "error");
      eventTypeSelect.focus();
      return;
    }
    if (isNaN(guests) || guests < 1 || guests > 5000) {
      showStatus("Guests must be a valid number between 1 and 5,000.", "error");
      guestsInput.focus();
      return;
    }
    if (isNaN(budget) || budget <= 0) {
      showStatus("Please enter a valid positive budget in INR (₹).", "error");
      budgetInput.focus();
      return;
    }
    if (!eventDate) {
      showStatus("Please choose an event date.", "error");
      eventDateInput.focus();
      return;
    }
    if (eventDate <= tomorrowISO.slice(0, 10) && eventDate < tomorrowISO) {
      showStatus("Event date must be strictly in the future.", "error");
      eventDateInput.focus();
      return;
    }

    setLoading(true);

    var payload = {
      event_type: eventType,
      guests: guests,
      budget: budget,
      event_date: eventDate,
      preferences: preferences
    };

    fetch("/api/plan", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    })
      .then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok) {
            var msg = (data && data.error) ? data.error : ("Server responded with status " + response.status);
            throw new Error(msg);
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

  function setLoading(isLoading) {
    if (isLoading) {
      submitBtn.setAttribute("disabled", "true");
      btnText.textContent = "Analyzing & Calculating...";
      btnSpinner.classList.remove("hidden");
    } else {
      submitBtn.removeAttribute("disabled");
      btnText.textContent = "Generate Comprehensive Plan";
      btnSpinner.classList.add("hidden");
    }
  }

  function showStatus(message, type) {
    statusBanner.textContent = message;
    statusBanner.className = "status-banner " + (type === "error" ? "error" : "success");
    statusBanner.classList.remove("hidden");
  }

  function hideStatus() {
    statusBanner.textContent = "";
    statusBanner.className = "status-banner hidden";
  }

  function clearElement(element) {
    while (element.firstChild) {
      element.removeChild(element.firstChild);
    }
  }

  /**
   * Safe DOM Helper: creates element with attributes and textContent
   */
  function createElement(tag, className, textContent, attributes) {
    var el = document.createElement(tag);
    if (className) {
      el.className = className;
    }
    if (textContent !== undefined && textContent !== null) {
      el.textContent = textContent;
    }
    if (attributes) {
      for (var key in attributes) {
        if (attributes.hasOwnProperty(key)) {
          el.setAttribute(key, attributes[key]);
        }
      }
    }
    return el;
  }

  function formatCurrency(amount) {
    return "₹" + Number(amount).toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  /**
   * Render the entire plan result
   */
  function renderPlanResults(plan, ideas, ideasMeta) {
    resultsSection.classList.remove("hidden");

    var inputs = plan.inputs;
    var budgetPlan = plan.budget_plan;
    var timeline = plan.timeline;
    var vendorChecklist = plan.vendor_checklist;

    // 1. Render Summary Cards
    clearElement(summaryCardsContainer);

    var cardsData = [
      {
        label: "Event Type",
        value: inputs.event_type.toUpperCase()
      },
      {
        label: "Guest Count",
        value: inputs.guests.toLocaleString("en-IN") + " Guests"
      },
      {
        label: "Total Budget",
        value: formatCurrency(budgetPlan.total_budget_inr)
      },
      {
        label: "Budget Tier",
        value: budgetPlan.tier.toUpperCase(),
        badge: "badge-" + budgetPlan.tier.toLowerCase(),
        sub: formatCurrency(budgetPlan.budget_per_guest_inr) + " / guest"
      }
    ];

    cardsData.forEach(function (card) {
      var cardDiv = createElement("div", "summary-card");
      cardDiv.appendChild(createElement("div", "summary-card-label", card.label));

      var valDiv = createElement("div", "summary-card-value", card.value);
      if (card.badge) {
        var badgeSpan = createElement("span", "badge " + card.badge, card.value);
        valDiv.textContent = "";
        valDiv.appendChild(badgeSpan);
      }
      cardDiv.appendChild(valDiv);

      if (card.sub) {
        cardDiv.appendChild(createElement("div", "field-hint", card.sub));
      }
      summaryCardsContainer.appendChild(cardDiv);
    });

    // 2. Render Budget Breakdown & Visual Bar
    budgetSummaryText.textContent =
      "Tier: " + budgetPlan.tier.toUpperCase() + " (" + formatCurrency(budgetPlan.budget_per_guest_inr) + " per guest). " +
      (budgetPlan.tier === "tight"
        ? "Note: Tight tier intentionally trims decor allocation and enlarges contingency buffer."
        : "Balanced across all vital vendors with contingency buffer.");

    clearElement(budgetVisualBar);
    clearElement(budgetTableBody);
    clearElement(budgetTableFoot);

    var allocations = budgetPlan.allocations || [];
    var totalPct = 0;
    var totalAmt = 0;

    allocations.forEach(function (alloc, idx) {
      totalPct += alloc.percentage;
      totalAmt += alloc.amount_inr;

      // Add segment to visual bar
      var color = BAR_COLORS[idx % BAR_COLORS.length];
      var barSegment = createElement("div", "budget-bar-segment", alloc.category + " (" + alloc.percentage + "%)", {
        "style": "width: " + alloc.percentage + "%; background-color: " + color + ";",
        "title": alloc.category + ": " + alloc.percentage + "% (" + formatCurrency(alloc.amount_inr) + ")"
      });
      budgetVisualBar.appendChild(barSegment);

      // Add row to table
      var tr = createElement("tr");
      var tdCat = createElement("td", null, alloc.category);
      var tdPct = createElement("td", null, alloc.percentage + "%");
      var tdAmt = createElement("td", null, formatCurrency(alloc.amount_inr));

      tr.appendChild(tdCat);
      tr.appendChild(tdPct);
      tr.appendChild(tdAmt);
      budgetTableBody.appendChild(tr);
    });

    // Foot row
    var footTr = createElement("tr");
    footTr.appendChild(createElement("th", null, "Total"));
    footTr.appendChild(createElement("td", null, Math.round(totalPct) + "%"));
    footTr.appendChild(createElement("td", null, formatCurrency(totalAmt)));
    budgetTableFoot.appendChild(footTr);

    // 3. Render 5 Personalized Ideas
    clearElement(ideasGrid);
    var isGemini = ideasMeta.source === "gemini";
    ideasSourceBadge.className = "badge " + (isGemini ? "badge-upcoming" : "badge-tight");
    ideasSourceBadge.textContent = isGemini ? "AI Powered (Gemini REST)" : "Curated Expert Recommendations";

    if (ideasMeta.cached) {
      ideasSourceBadge.textContent += " [Cached]";
    }

    ideasDescriptionText.textContent =
      "5 actionable recommendations specifically tailored for your " + inputs.event_type +
      " with a " + budgetPlan.tier + " budget profile.";

    ideas.forEach(function (idea) {
      var card = createElement("div", "idea-card");
      card.appendChild(createElement("div", "idea-category-tag", idea.category || "Idea"));
      card.appendChild(createElement("h4", "idea-title", idea.title));
      card.appendChild(createElement("p", "idea-description", idea.description));
      ideasGrid.appendChild(card);
    });

    // 4. Render Countdown Timeline
    clearElement(timelineList);
    timeline.forEach(function (task) {
      var itemClass = "timeline-item " + (task.is_past_due ? "past-due" : "upcoming");
      var item = createElement("div", itemClass);

      // Date column
      var dateCol = createElement("div", "timeline-item-date");
      dateCol.appendChild(createElement("div", null, task.target_date));
      var statusBadge = createElement(
        "span",
        "badge " + (task.is_past_due ? "badge-past-due" : "badge-upcoming"),
        task.is_past_due ? "Past Due" : "T-" + task.days_before_event + " Days"
      );
      dateCol.appendChild(statusBadge);

      // Info column
      var infoCol = createElement("div", null);
      infoCol.appendChild(createElement("div", "timeline-item-title", task.title));
      infoCol.appendChild(createElement("div", "timeline-item-desc", task.description));

      // Action column with Add to Google Calendar link
      var actionCol = createElement("div", null);
      var calLink = createElement(
        "a",
        "btn btn-outline btn-sm",
        "Add to Calendar",
        {
          "href": task.google_calendar_url,
          "target": "_blank",
          "rel": "noopener noreferrer",
          "aria-label": "Add task " + task.title + " to Google Calendar"
        }
      );
      actionCol.appendChild(calLink);

      item.appendChild(dateCol);
      item.appendChild(infoCol);
      item.appendChild(actionCol);
      timelineList.appendChild(item);
    });

    // 5. Render Vendor Checklist
    clearElement(vendorTableBody);
    if (inputs.guests >= 200) {
      vendorAlertBox.classList.remove("hidden");
      vendorAlertBox.textContent =
        "Notice for Large Gathering (" + inputs.guests + " Guests): Dedicated security bouncers and valet parking marshals have been added to your checklist as mandatory requirements.";
    } else {
      vendorAlertBox.classList.add("hidden");
    }

    vendorChecklist.forEach(function (vendor) {
      var tr = createElement("tr");

      var tdCat = createElement("td", null, vendor.category);
      var tdTask = createElement("td", null, vendor.task);

      var tdPriority = createElement("td");
      if (vendor.mandatory) {
        tdPriority.appendChild(createElement("span", "badge badge-mandatory", "Mandatory"));
      } else {
        tdPriority.appendChild(createElement("span", "badge badge-comfortable", "Standard"));
      }

      var tdAction = createElement("td");
      var mapsLink = createElement(
        "a",
        "btn btn-outline btn-sm",
        "Search Maps",
        {
          "href": vendor.google_maps_url,
          "target": "_blank",
          "rel": "noopener noreferrer",
          "aria-label": "Search " + vendor.category + " on Google Maps"
        }
      );
      tdAction.appendChild(mapsLink);

      tr.appendChild(tdCat);
      tr.appendChild(tdTask);
      tr.appendChild(tdPriority);
      tr.appendChild(tdAction);
      vendorTableBody.appendChild(tr);
    });
  }
});
