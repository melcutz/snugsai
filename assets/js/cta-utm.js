/**
 * Snugs.ai CTA UTM Passthrough & First-Touch Attribution (#45)
 * Passes incoming utm_* and ref parameters (from URL or first-touch sessionStorage)
 * through to every app.snugs.ai CTA while preserving placement and plan parameters.
 */
(function (root) {
  "use strict";

  var STORAGE_KEY = "snugs_utm_first_touch";
  var APP_HOST = "app.snugs.ai";

  function isUtmOrRef(key) {
    if (!key) return false;
    var k = String(key).trim().toLowerCase();
    return k.indexOf("utm_") === 0 || k === "ref";
  }

  function getInboundParams(customLocation, customStorage) {
    var loc = customLocation || (typeof window !== "undefined" ? window.location : null);
    var store = customStorage || (typeof sessionStorage !== "undefined" ? sessionStorage : null);

    var fromUrl = {};
    var hasUrlInbound = false;

    try {
      if (loc && loc.search && loc.search.length > 1) {
        var sp = new URLSearchParams(loc.search);
        sp.forEach(function (val, key) {
          if (isUtmOrRef(key) && val) {
            fromUrl[key] = val;
            hasUrlInbound = true;
          }
        });
      }
    } catch (_) {}

    if (hasUrlInbound) {
      try {
        if (store) {
          var existing = store.getItem(STORAGE_KEY);
          if (!existing) {
            store.setItem(STORAGE_KEY, JSON.stringify(fromUrl));
          }
        }
      } catch (_) {}
      return fromUrl;
    }

    try {
      if (store) {
        var stored = store.getItem(STORAGE_KEY);
        if (stored) {
          var parsed = JSON.parse(stored);
          if (parsed && typeof parsed === "object" && Object.keys(parsed).length > 0) {
            return parsed;
          }
        }
      }
    } catch (_) {}

    return null;
  }

  function updateCtaUrl(rawHref, placement, inbound) {
    if (!rawHref) return rawHref;

    var url;
    try {
      url = new URL(
        rawHref,
        typeof window !== "undefined" && window.location ? window.location.href : "https://snugs.ai"
      );
    } catch (_) {
      return rawHref;
    }

    // Badge / outbound links that are not app CTAs should not be rewritten.
    if (url.hostname !== APP_HOST) {
      return rawHref;
    }

    // If the visitor has no inbound utm_*/ref, existing marketing_site placement tracking may stay as the default.
    if (!inbound) {
      return rawHref;
    }

    // Derive placement identifier
    var effectivePlacement =
      placement ||
      url.searchParams.get("cta") ||
      url.searchParams.get("utm_campaign") ||
      url.searchParams.get("utm_content") ||
      "";

    // The plan param is kept.
    var existingPlan = url.searchParams.get("plan");

    // Existing utm_medium defaults to 'cta' if inbound does not provide one
    var defaultMedium = url.searchParams.get("utm_medium") || "cta";

    // Clear previous default marketing_site tracking params
    url.searchParams.delete("utm_source");
    url.searchParams.delete("utm_medium");
    url.searchParams.delete("utm_campaign");
    url.searchParams.delete("utm_content");

    // 1. Pass through incoming utm_* and ref params
    for (var k in inbound) {
      if (Object.prototype.hasOwnProperty.call(inbound, k) && inbound[k]) {
        url.searchParams.set(k, inbound[k]);
      }
    }

    // If ref was supplied but utm_source wasn't, mirror ref to utm_source
    if (!url.searchParams.has("utm_source") && inbound.ref) {
      url.searchParams.set("utm_source", inbound.ref);
    }

    // Ensure utm_medium exists
    if (!url.searchParams.has("utm_medium")) {
      url.searchParams.set("utm_medium", defaultMedium);
    }

    // 2. The CTA's own placement goes in a separate param such as utm_content or cta
    if (effectivePlacement) {
      url.searchParams.set("cta", effectivePlacement);
      if (!url.searchParams.has("utm_content")) {
        url.searchParams.set("utm_content", effectivePlacement);
      }
    }

    // 3. The plan param is kept
    if (existingPlan) {
      url.searchParams.set("plan", existingPlan);
    }

    return url.toString();
  }

  function syncAllCtas(rootDoc, inbound) {
    var doc = rootDoc || (typeof document !== "undefined" ? document : null);
    if (!doc || !doc.querySelectorAll) return;

    var inParams = inbound || getInboundParams();
    if (!inParams) return;

    var links = doc.querySelectorAll('a[href*="app.snugs.ai"], a[data-cta]');
    for (var i = 0; i < links.length; i++) {
      var a = links[i];
      var href = a.getAttribute("href");
      if (!href) continue;
      var placement = a.getAttribute("data-cta") || "";
      var updated = updateCtaUrl(href, placement, inParams);
      if (updated && updated !== href) {
        a.setAttribute("href", updated);
      }
    }
  }

  function setupClickInterceptor(rootDoc) {
    var doc = rootDoc || (typeof document !== "undefined" ? document : null);
    if (!doc || !doc.addEventListener) return;

    doc.addEventListener(
      "click",
      function (e) {
        var target = e.target;
        var a = target && target.closest ? target.closest("a") : null;
        if (!a) return;
        var href = a.getAttribute("href");
        if (!href || href.indexOf(APP_HOST) === -1) return;
        var inbound = getInboundParams();
        if (!inbound) return;
        var placement = a.getAttribute("data-cta") || "";
        var updated = updateCtaUrl(href, placement, inbound);
        if (updated && updated !== href) {
          a.setAttribute("href", updated);
        }
      },
      true
    );
  }

  function init(doc) {
    var d = doc || (typeof document !== "undefined" ? document : null);
    if (!d) return;

    if (d.readyState === "loading") {
      d.addEventListener("DOMContentLoaded", function () {
        syncAllCtas(d);
      });
    } else {
      syncAllCtas(d);
    }

    if (typeof window !== "undefined") {
      window.addEventListener("load", function () {
        syncAllCtas(d);
      });
    }

    setupClickInterceptor(d);
  }

  var api = {
    isUtmOrRef: isUtmOrRef,
    getInboundParams: getInboundParams,
    updateCtaUrl: updateCtaUrl,
    syncAllCtas: syncAllCtas,
    setupClickInterceptor: setupClickInterceptor,
    init: init,
    STORAGE_KEY: STORAGE_KEY,
    APP_HOST: APP_HOST
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
    module.exports.default = api;
    module.exports.updateCtaUrl = updateCtaUrl;
    module.exports.getInboundParams = getInboundParams;
    module.exports.syncAllCtas = syncAllCtas;
    module.exports.isUtmOrRef = isUtmOrRef;
  }
  if (root) {
    root.SnugsCtaUtm = api;
  }
  if (typeof document !== "undefined") {
    init(document);
  }
})(typeof globalThis !== "undefined" ? globalThis : (typeof window !== "undefined" ? window : this));
