import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import ctaUtm from "../assets/js/cta-utm.js";
const { updateCtaUrl, getInboundParams, syncAllCtas } = ctaUtm;

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");

const scriptPath = path.join(repoRoot, "assets/js/cta-utm.js");
const indexPath = path.join(repoRoot, "index.html");

test("assets/js/cta-utm.js exists and exports expected functions", () => {
  assert.ok(fs.existsSync(scriptPath), "assets/js/cta-utm.js must exist");
  assert.equal(typeof updateCtaUrl, "function");
  assert.equal(typeof getInboundParams, "function");
  assert.equal(typeof syncAllCtas, "function");
});

test("producthunt inbound passes through on Yearly pricing CTA, home-hero, and home-footer", () => {

  const inbound = { utm_source: "producthunt" };

  // 1. Home hero CTA
  const heroHref = "https://app.snugs.ai/?utm_source=marketing_site&utm_medium=cta&utm_campaign=home-hero";
  const heroUpdated = updateCtaUrl(heroHref, "home-hero", inbound);
  const heroUrl = new URL(heroUpdated);
  assert.equal(heroUrl.hostname, "app.snugs.ai");
  assert.equal(heroUrl.searchParams.get("utm_source"), "producthunt");
  assert.equal(heroUrl.searchParams.get("utm_medium"), "cta");
  // Placement must be recorded in separate param such as utm_content or cta
  const heroPlacement = heroUrl.searchParams.get("cta") || heroUrl.searchParams.get("utm_content");
  assert.equal(heroPlacement, "home-hero");
  assert.notEqual(heroUrl.searchParams.get("utm_campaign"), "home-hero");

  // 2. Yearly pricing CTA
  const yearlyHref = "https://app.snugs.ai/?utm_source=marketing_site&utm_medium=cta&utm_campaign=home-pricing-yearly&plan=yearly";
  const yearlyUpdated = updateCtaUrl(yearlyHref, "home-pricing-yearly", inbound);
  const yearlyUrl = new URL(yearlyUpdated);
  assert.equal(yearlyUrl.hostname, "app.snugs.ai");
  assert.equal(yearlyUrl.searchParams.get("utm_source"), "producthunt");
  assert.equal(yearlyUrl.searchParams.get("plan"), "yearly", "plan param must be kept");
  const yearlyPlacement = yearlyUrl.searchParams.get("cta") || yearlyUrl.searchParams.get("utm_content");
  assert.equal(yearlyPlacement, "home-pricing-yearly");
  assert.notEqual(yearlyUrl.searchParams.get("utm_campaign"), "home-pricing-yearly");

  // 3. Home footer CTA
  const footerHref = "https://app.snugs.ai/?utm_source=marketing_site&utm_medium=cta&utm_campaign=home-footer";
  const footerUpdated = updateCtaUrl(footerHref, "home-footer", inbound);
  const footerUrl = new URL(footerUpdated);
  assert.equal(footerUrl.hostname, "app.snugs.ai");
  assert.equal(footerUrl.searchParams.get("utm_source"), "producthunt");
  const footerPlacement = footerUrl.searchParams.get("cta") || footerUrl.searchParams.get("utm_content");
  assert.equal(footerPlacement, "home-footer");
  assert.notEqual(footerUrl.searchParams.get("utm_campaign"), "home-footer");
});

test("no-inbound default preserves existing marketing_site placement tracking", () => {
  const yearlyHref = "https://app.snugs.ai/?utm_source=marketing_site&utm_medium=cta&utm_campaign=home-pricing-yearly&plan=yearly";
  const result = updateCtaUrl(yearlyHref, "home-pricing-yearly", null);
  const url = new URL(result);
  assert.equal(url.searchParams.get("utm_source"), "marketing_site");
  assert.equal(url.searchParams.get("utm_medium"), "cta");
  assert.equal(url.searchParams.get("utm_campaign"), "home-pricing-yearly");
  assert.equal(url.searchParams.get("plan"), "yearly");
});

test("prod QA scenario: pete-qa and ph-precheck attribution is preserved on Yearly CTA", () => {
  const inbound = {
    utm_source: "pete-qa",
    utm_campaign: "ph-precheck"
  };

  const yearlyHref = "https://app.snugs.ai/?utm_source=marketing_site&utm_medium=cta&utm_campaign=home-pricing-yearly&plan=yearly";
  const result = updateCtaUrl(yearlyHref, "home-pricing-yearly", inbound);
  const url = new URL(result);
  assert.equal(url.searchParams.get("utm_source"), "pete-qa");
  assert.equal(url.searchParams.get("utm_campaign"), "ph-precheck", "campaign must not be overwritten by placement");
  assert.equal(url.searchParams.get("plan"), "yearly", "plan param must be kept");
  const placement = url.searchParams.get("cta") || url.searchParams.get("utm_content");
  assert.equal(placement, "home-pricing-yearly");
});

test("inbound ref param passes through to app CTA", () => {
  const inbound = { ref: "producthunt" };
  const yearlyHref = "https://app.snugs.ai/?utm_source=marketing_site&utm_medium=cta&utm_campaign=home-pricing-yearly&plan=yearly";
  const result = updateCtaUrl(yearlyHref, "home-pricing-yearly", inbound);
  const url = new URL(result);
  assert.equal(url.searchParams.get("ref"), "producthunt");
  assert.equal(url.searchParams.get("plan"), "yearly");
});

test("badge and non-app outbound links are not rewritten", () => {
  const inbound = { utm_source: "producthunt" };
  const badgeHref = "https://aiagentsdirectory.com/agent/snugsai?utm_source=badge&utm_medium=referral&utm_campaign=free_listing&utm_content=snugsai";
  const result = updateCtaUrl(badgeHref, "badge", inbound);
  assert.equal(result, badgeHref, "Badge link must not be changed");

  const publishHref = "https://publishyoursaas.com";
  assert.equal(updateCtaUrl(publishHref, "", inbound), publishHref);
});

test("index.html includes assets/js/cta-utm.js", () => {
  const html = fs.readFileSync(indexPath, "utf8");
  assert.match(html, /<script[^>]+src=["'][^"']*assets\/js\/cta-utm\.js["'][^>]*>/i, "index.html must include cta-utm.js");
});

test("sessionStorage stores first-touch and passes through when URL has no UTMs", () => {
  const mockStorage = {
    _data: {},
    getItem(k) { return Object.prototype.hasOwnProperty.call(this._data, k) ? this._data[k] : null; },
    setItem(k, v) { this._data[k] = String(v); }
  };

  // 1. First touch: visitor arrives with producthunt campaign
  const firstLocation = {
    search: "?utm_source=producthunt&utm_campaign=launch_day",
    hostname: "snugs.ai"
  };
  const firstTouch = getInboundParams(firstLocation, mockStorage);
  assert.deepEqual(firstTouch, {
    utm_source: "producthunt",
    utm_campaign: "launch_day"
  });
  assert.ok(
    mockStorage.getItem("snugs_utm_first_touch") || mockStorage.getItem("snugs_first_touch_utm"),
    "First touch must be stored in sessionStorage"
  );

  // 2. Subsequent page visit with clean URL (no search params)
  const cleanLocation = {
    search: "",
    hostname: "snugs.ai"
  };
  const cachedTouch = getInboundParams(cleanLocation, mockStorage);
  assert.deepEqual(cachedTouch, {
    utm_source: "producthunt",
    utm_campaign: "launch_day"
  }, "First touch must be retrieved from sessionStorage when URL is clean");

  // 3. CTA updated with cached first touch
  const yearlyHref = "https://app.snugs.ai/?utm_source=marketing_site&utm_medium=cta&utm_campaign=home-pricing-yearly&plan=yearly";
  const updated = updateCtaUrl(yearlyHref, "home-pricing-yearly", cachedTouch);
  const url = new URL(updated);
  assert.equal(url.searchParams.get("utm_source"), "producthunt");
  assert.equal(url.searchParams.get("utm_campaign"), "launch_day");
  assert.equal(url.searchParams.get("plan"), "yearly");
  const placement = url.searchParams.get("cta") || url.searchParams.get("utm_content");
  assert.equal(placement, "home-pricing-yearly");
});
