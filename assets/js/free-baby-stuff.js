/**
 * Snugs.ai Free Baby Stuff hub logic (#27)
 * Country filter, data-driven card renderer, and email signup form handler.
 */
(function (root) {
  "use strict";

  var FILTER_COUNTRIES = ["All", "Worldwide", "US", "UK", "Canada", "Australia"];
  var PRIVACY_LINE = "One short email a week, the roundup. Nothing else. Unsubscribe anytime.";
  var UNAVAILABLE_MESSAGE = "Signup isn't open yet, please try again later";
  var SUBSCRIBE_ENDPOINT = "/subscribe";

  // Copy is pending verification; populate with verified offer objects when copy files land.
  var OFFER_LISTINGS = [];

  function normalizeCountryFilter(value) {
    if (value == null) return "All";
    var clean = String(value).trim();
    if (clean.charAt(0) === "#") {
      clean = clean.slice(1).trim();
    }
    if (clean.toLowerCase().indexOf("country=") === 0) {
      clean = clean.slice("country=".length).trim();
    }
    try {
      clean = decodeURIComponent(clean).trim();
    } catch (_) {}
    if (!clean) return "All";

    var lower = clean.toLowerCase();
    for (var i = 0; i < FILTER_COUNTRIES.length; i++) {
      if (FILTER_COUNTRIES[i].toLowerCase() === lower) {
        return FILTER_COUNTRIES[i];
      }
    }
    return "All";
  }

  function parseCountryFromHash(hash) {
    return normalizeCountryFilter(hash);
  }

  function formatCountryHash(country) {
    var normalized = normalizeCountryFilter(country);
    if (normalized === "All") return "";
    return "#country=" + encodeURIComponent(normalized);
  }

  function extractCardCountry(card) {
    if (!card) return "";
    if (typeof card === "string") return card;
    if (typeof card.getAttribute === "function") {
      return card.getAttribute("data-country") || "";
    }
    if (card.dataset && typeof card.dataset.country === "string") {
      return card.dataset.country;
    }
    if (typeof card.country === "string") {
      return card.country;
    }
    return "";
  }

  function cardMatchesCountry(card, selectedCountry) {
    var selected = normalizeCountryFilter(selectedCountry);
    if (selected === "All") return true;

    var rawCountry = extractCardCountry(card);
    if (!rawCountry) return false;

    var target = selected.toLowerCase();
    var tokens = String(rawCountry).split(/[,|/]+/);
    for (var i = 0; i < tokens.length; i++) {
      if (tokens[i].trim().toLowerCase() === target) {
        return true;
      }
    }
    return false;
  }

  function filterCardsByCountry(cards, selectedCountry) {
    var selected = normalizeCountryFilter(selectedCountry);
    var list = Array.isArray(cards) ? cards : Array.from(cards || []);
    var visibleCards = [];

    for (var i = 0; i < list.length; i++) {
      var card = list[i];
      var matches = cardMatchesCountry(card, selected);
      if (matches) {
        visibleCards.push(card);
      }
      if (card && typeof card === "object" && "hidden" in card) {
        card.hidden = !matches;
      }
    }

    var isEmpty = visibleCards.length === 0;
    var emptyMessage = "";
    if (isEmpty) {
      emptyMessage = selected === "All"
        ? "Listings are being verified. Check back soon."
        : "No verified listings match " + selected + " right now. Reset to All to view every listing.";
    }

    return {
      selectedCountry: selected,
      visibleCards: visibleCards,
      visibleCount: visibleCards.length,
      totalCount: list.length,
      isEmpty: isEmpty,
      emptyMessage: emptyMessage
    };
  }

  function resetCountryFilter(cards) {
    return filterCardsByCountry(cards, "All");
  }

  function buildSubscribePayload(email, website) {
    return {
      email: String(email == null ? "" : email).trim(),
      website: String(website == null ? "" : website)
    };
  }

  function mapSubscribeResponse(response) {
    if (!response || response instanceof Error || response.networkError) {
      return {
        state: "error",
        status: "network_error",
        message: UNAVAILABLE_MESSAGE,
        dismissible: true,
        canResend: false
      };
    }

    var httpStatus = typeof response.status === "number" ? response.status : 200;
    if (httpStatus === 404 || httpStatus === 405) {
      return {
        state: "error",
        status: "endpoint_missing",
        message: UNAVAILABLE_MESSAGE,
        dismissible: true,
        canResend: false
      };
    }

    var rawBody = response.body !== undefined
      ? response.body
      : (response.data !== undefined ? response.data : response);

    var parsed = rawBody;
    if (typeof rawBody === "string") {
      var trimmed = rawBody.trim();
      if (!trimmed) {
        return {
          state: "error",
          status: "non_json",
          message: UNAVAILABLE_MESSAGE,
          dismissible: true,
          canResend: false
        };
      }
      try {
        parsed = JSON.parse(trimmed);
      } catch (_) {
        return {
          state: "error",
          status: "non_json",
          message: UNAVAILABLE_MESSAGE,
          dismissible: true,
          canResend: false
        };
      }
    }

    if (!parsed || typeof parsed !== "object" || typeof parsed.status !== "string") {
      return {
        state: "error",
        status: "non_json",
        message: UNAVAILABLE_MESSAGE,
        dismissible: true,
        canResend: false
      };
    }

    var workerStatus = parsed.status.trim().toLowerCase();
    var customMsg = typeof parsed.message === "string" && parsed.message.trim()
      ? parsed.message.trim()
      : "";

    if (workerStatus === "pending" || workerStatus === "success") {
      return {
        state: "success",
        status: workerStatus,
        message: customMsg || "Check your email to confirm your subscription.",
        dismissible: false,
        canResend: true
      };
    }

    if (workerStatus === "pending_resent" || workerStatus === "pending_confirmation") {
      return {
        state: "pending",
        status: workerStatus,
        message: customMsg || "Check your email to confirm. Confirmation email sent.",
        dismissible: false,
        canResend: true
      };
    }

    if (workerStatus === "already_subscribed") {
      return {
        state: "already_subscribed",
        status: "already_subscribed",
        message: customMsg || "You are already subscribed to the weekly roundup.",
        dismissible: false,
        canResend: false
      };
    }

    if (workerStatus === "error") {
      return {
        state: "error",
        status: "error",
        message: customMsg || "Could not complete signup. Please check your email and try again.",
        dismissible: true,
        canResend: false
      };
    }

    return {
      state: "error",
      status: "unavailable",
      message: UNAVAILABLE_MESSAGE,
      dismissible: true,
      canResend: false
    };
  }

  async function submitSubscribe(options) {
    var opts = options || {};
    var payload = buildSubscribePayload(opts.email, opts.website);
    var endpoint = opts.endpoint || SUBSCRIBE_ENDPOINT;
    var fetchFn = opts.fetchImpl || (typeof fetch === "function" ? fetch : null);

    if (!payload.email || payload.email.indexOf("@") === -1) {
      return {
        state: "error",
        status: "validation_error",
        message: "Please enter a valid email address.",
        dismissible: true,
        canResend: false,
        payload: payload
      };
    }

    if (typeof fetchFn !== "function") {
      var noFetchState = mapSubscribeResponse({ networkError: true });
      noFetchState.payload = payload;
      return noFetchState;
    }

    try {
      var res = await fetchFn(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify(payload)
      });

      var bodyText = "";
      if (res && typeof res.text === "function") {
        bodyText = await res.text();
      } else if (res && typeof res.json === "function") {
        bodyText = await res.json();
      } else if (res && res.body !== undefined) {
        bodyText = res.body;
      }

      var mapped = mapSubscribeResponse({
        ok: Boolean(res && res.ok),
        status: res && typeof res.status === "number" ? res.status : 200,
        body: bodyText
      });
      mapped.payload = payload;
      return mapped;
    } catch (_) {
      var errMapped = mapSubscribeResponse({ networkError: true });
      errMapped.payload = payload;
      return errMapped;
    }
  }

  function sanitizeDirectUrl(rawUrl) {
    if (!rawUrl || typeof rawUrl !== "string") return "#";
    try {
      var u = new URL(rawUrl);
      var keys = Array.from(u.searchParams.keys());
      for (var i = 0; i < keys.length; i++) {
        if (keys[i].toLowerCase().indexOf("utm_") === 0) {
          u.searchParams.delete(keys[i]);
        }
      }
      return u.toString();
    } catch (_) {
      return rawUrl;
    }
  }

  function renderOfferCards(listings, container, template, doc) {
    if (!container) return [];
    var d = doc || (typeof document !== "undefined" ? document : null);
    if (!d) return [];

    container.innerHTML = "";
    var items = Array.isArray(listings) ? listings : [];
    var rendered = [];

    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      if (!item) continue;
      var cardEl = null;

      if (template && template.content && template.content.firstElementChild) {
        cardEl = template.content.firstElementChild.cloneNode(true);
      } else {
        cardEl = d.createElement("article");
        cardEl.className = "offer-card rounded-3xl border border-orange-200 bg-white/90 p-6 soft-shadow";
      }

      var countryVal = item.country || "Worldwide";
      cardEl.setAttribute("data-country", countryVal);

      var badgeEl = cardEl.querySelector('[data-field="badge"]');
      if (badgeEl) badgeEl.textContent = item.badge || "Truly free";

      var titleEl = cardEl.querySelector('[data-field="title"]');
      if (titleEl) titleEl.textContent = item.title || "";

      var whatEl = cardEl.querySelector('[data-field="whatYouGet"]');
      if (whatEl) whatEl.textContent = item.whatYouGet || "";

      var catchEl = cardEl.querySelector('[data-field="catch"]');
      if (catchEl) catchEl.textContent = item.catchText || item.catch || "";

      var whereEl = cardEl.querySelector('[data-field="country"]');
      if (whereEl) whereEl.textContent = item.where || countryVal;

      var verifiedEl = cardEl.querySelector('[data-field="verifiedDate"]');
      if (verifiedEl) verifiedEl.textContent = item.verifiedDate || "";

      var linkEl = cardEl.querySelector('[data-field="url"]');
      if (linkEl) linkEl.setAttribute("href", sanitizeDirectUrl(item.url));

      container.appendChild(cardEl);
      rendered.push(cardEl);
    }

    return rendered;
  }

  function initHubPage(doc, win) {
    var d = doc || (typeof document !== "undefined" ? document : null);
    var w = win || (typeof window !== "undefined" ? window : null);
    if (!d) return;

    var filterButtons = Array.from(d.querySelectorAll("[data-country-filter]"));
    var resetButtons = Array.from(d.querySelectorAll("[data-reset-filter]"));
    var activeFilterBar = d.getElementById("active-filter-bar");
    var activeFilterLabel = d.getElementById("active-filter-label");
    var emptyStateBox = d.getElementById("filter-empty-state");
    var emptyStateText = d.getElementById("filter-empty-text");
    var offersContainer = d.getElementById("offers-container");
    var cardTemplate = d.getElementById("offer-card-template");

    if (offersContainer && OFFER_LISTINGS.length > 0) {
      renderOfferCards(OFFER_LISTINGS, offersContainer, cardTemplate, d);
    }

    function getCardElements() {
      if (!offersContainer) return [];
      return Array.from(offersContainer.querySelectorAll("[data-country]"));
    }

    function applyFilterToDom(requestedCountry, updateHash) {
      var cards = getCardElements();
      var result = filterCardsByCountry(cards, requestedCountry);
      var selected = result.selectedCountry;

      for (var i = 0; i < filterButtons.length; i++) {
        var btn = filterButtons[i];
        var btnCountry = normalizeCountryFilter(btn.getAttribute("data-country-filter") || btn.textContent);
        var isSelected = btnCountry === selected;
        btn.setAttribute("aria-pressed", isSelected ? "true" : "false");
        if (isSelected) {
          btn.classList.add("bg-orange-600", "text-white", "border-orange-600");
          btn.classList.remove("bg-white", "text-gray-700", "border-orange-200");
        } else {
          btn.classList.remove("bg-orange-600", "text-white", "border-orange-600");
          btn.classList.add("bg-white", "text-gray-700", "border-orange-200");
        }
      }

      if (activeFilterBar) {
        if (selected === "All") {
          activeFilterBar.classList.add("hidden");
          activeFilterBar.hidden = true;
        } else {
          activeFilterBar.classList.remove("hidden");
          activeFilterBar.hidden = false;
          if (activeFilterLabel) {
            activeFilterLabel.textContent = selected;
          }
        }
      }

      if (emptyStateBox) {
        var showEmpty = (cards.length > 0 && result.isEmpty) || (cards.length === 0 && selected !== "All");
        if (showEmpty) {
          emptyStateBox.classList.remove("hidden");
          emptyStateBox.hidden = false;
          if (emptyStateText) {
            emptyStateText.textContent = result.emptyMessage;
          }
        } else {
          emptyStateBox.classList.add("hidden");
          emptyStateBox.hidden = true;
        }
      }

      if (updateHash && w && w.history && typeof w.history.replaceState === "function") {
        var hashStr = formatCountryHash(selected);
        var baseUrl = w.location.pathname + w.location.search;
        w.history.replaceState(null, "", hashStr ? baseUrl + hashStr : baseUrl);
      }

      return result;
    }

    for (var i = 0; i < filterButtons.length; i++) {
      (function (btn) {
        btn.addEventListener("click", function () {
          var targetCountry = btn.getAttribute("data-country-filter") || btn.textContent;
          applyFilterToDom(targetCountry, true);
        });
      })(filterButtons[i]);
    }

    for (var j = 0; j < resetButtons.length; j++) {
      resetButtons[j].addEventListener("click", function () {
        applyFilterToDom("All", true);
      });
    }

    var initialCountry = w && w.location ? parseCountryFromHash(w.location.hash) : "All";
    applyFilterToDom(initialCountry, initialCountry !== "All");

    if (w) {
      w.addEventListener("hashchange", function () {
        var nextCountry = parseCountryFromHash(w.location.hash);
        applyFilterToDom(nextCountry, false);
      });
    }

    // Email capture form handling
    var form = d.getElementById("subscribe-form");
    var emailInput = d.getElementById("subscribe-email");
    var websiteInput = d.getElementById("subscribe-website");
    var submitBtn = d.getElementById("subscribe-submit");
    var statusBox = d.getElementById("subscribe-status");
    var statusMsg = d.getElementById("subscribe-status-message");
    var resendBtn = d.getElementById("subscribe-resend");
    var dismissBtn = d.getElementById("subscribe-dismiss");
    var lastSubmittedPayload = null;

    function hideStatus() {
      if (!statusBox) return;
      statusBox.classList.add("hidden");
      statusBox.hidden = true;
      statusBox.removeAttribute("data-state");
      if (statusMsg) statusMsg.textContent = "";
      if (resendBtn) {
        resendBtn.classList.add("hidden");
        resendBtn.hidden = true;
      }
      if (dismissBtn) {
        dismissBtn.classList.add("hidden");
        dismissBtn.hidden = true;
      }
    }

    function renderSubscribeState(mapped) {
      if (!statusBox || !statusMsg) return;
      statusBox.classList.remove(
        "hidden",
        "bg-green-50",
        "border-green-200",
        "text-green-900",
        "bg-amber-50",
        "border-amber-200",
        "text-amber-900",
        "bg-red-50",
        "border-red-200",
        "text-red-900"
      );
      statusBox.hidden = false;
      statusBox.setAttribute("data-state", mapped.state);
      statusMsg.textContent = mapped.message;

      if (mapped.state === "success" || mapped.state === "already_subscribed") {
        statusBox.classList.add("bg-green-50", "border-green-200", "text-green-900");
      } else if (mapped.state === "pending") {
        statusBox.classList.add("bg-amber-50", "border-amber-200", "text-amber-900");
      } else {
        statusBox.classList.add("bg-red-50", "border-red-200", "text-red-900");
      }

      if (resendBtn) {
        if (mapped.canResend) {
          resendBtn.classList.remove("hidden");
          resendBtn.hidden = false;
        } else {
          resendBtn.classList.add("hidden");
          resendBtn.hidden = true;
        }
      }

      if (dismissBtn) {
        if (mapped.dismissible) {
          dismissBtn.classList.remove("hidden");
          dismissBtn.hidden = false;
        } else {
          dismissBtn.classList.add("hidden");
          dismissBtn.hidden = true;
        }
      }
    }

    async function handleSend(emailVal, websiteVal) {
      if (submitBtn) submitBtn.disabled = true;
      if (resendBtn) resendBtn.disabled = true;
      lastSubmittedPayload = buildSubscribePayload(emailVal, websiteVal);
      var result = await submitSubscribe({
        email: lastSubmittedPayload.email,
        website: lastSubmittedPayload.website,
        endpoint: SUBSCRIBE_ENDPOINT
      });
      renderSubscribeState(result);
      if (submitBtn) submitBtn.disabled = false;
      if (resendBtn) resendBtn.disabled = false;
      return result;
    }

    if (form) {
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var emailVal = emailInput ? emailInput.value : "";
        var websiteVal = websiteInput ? websiteInput.value : "";
        handleSend(emailVal, websiteVal);
      });
    }

    if (resendBtn) {
      resendBtn.addEventListener("click", function () {
        var emailVal = (lastSubmittedPayload && lastSubmittedPayload.email) || (emailInput ? emailInput.value : "");
        var websiteVal = (lastSubmittedPayload && lastSubmittedPayload.website) || (websiteInput ? websiteInput.value : "");
        handleSend(emailVal, websiteVal);
      });
    }

    if (dismissBtn) {
      dismissBtn.addEventListener("click", function () {
        hideStatus();
      });
    }
  }

  var api = {
    FILTER_COUNTRIES: FILTER_COUNTRIES,
    PRIVACY_LINE: PRIVACY_LINE,
    UNAVAILABLE_MESSAGE: UNAVAILABLE_MESSAGE,
    SUBSCRIBE_ENDPOINT: SUBSCRIBE_ENDPOINT,
    OFFER_LISTINGS: OFFER_LISTINGS,
    normalizeCountryFilter: normalizeCountryFilter,
    parseCountryFromHash: parseCountryFromHash,
    formatCountryHash: formatCountryHash,
    cardMatchesCountry: cardMatchesCountry,
    filterCardsByCountry: filterCardsByCountry,
    resetCountryFilter: resetCountryFilter,
    buildSubscribePayload: buildSubscribePayload,
    mapSubscribeResponse: mapSubscribeResponse,
    submitSubscribe: submitSubscribe,
    sanitizeDirectUrl: sanitizeDirectUrl,
    renderOfferCards: renderOfferCards,
    initHubPage: initHubPage
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.SnugsFreeBabyStuff = api;
  }
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", function () {
        initHubPage(document, typeof window !== "undefined" ? window : null);
      });
    } else {
      initHubPage(document, typeof window !== "undefined" ? window : null);
    }
  }
})(typeof globalThis !== "undefined" ? globalThis : (typeof window !== "undefined" ? window : this));
