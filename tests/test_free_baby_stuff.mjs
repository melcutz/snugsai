import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fbs from "../assets/js/free-baby-stuff.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");

function makeSampleCards() {
  return [
    { id: "c-worldwide", country: "Worldwide", hidden: false },
    { id: "c-us", country: "US", hidden: false },
    { id: "c-uk", country: "UK", hidden: false },
    { id: "c-ca", country: "Canada", hidden: false },
    { id: "c-au", country: "Australia", hidden: false },
    { id: "c-fi", country: "Finland", hidden: false },
    { id: "c-ie", country: "Ireland", hidden: false },
    { id: "c-multi", country: "UK, Ireland, Australia", hidden: false }
  ];
}

test("filter option All shows every card including Finland and Ireland", () => {
  const cards = makeSampleCards();
  const res = fbs.filterCardsByCountry(cards, "All");
  assert.equal(res.selectedCountry, "All");
  assert.equal(res.visibleCount, 8);
  assert.equal(res.isEmpty, false);
  assert.equal(cards.every((c) => c.hidden === false), true);
});

test("filter option Worldwide filters cards in place", () => {
  const cards = makeSampleCards();
  const res = fbs.filterCardsByCountry(cards, "Worldwide");
  assert.equal(res.selectedCountry, "Worldwide");
  assert.deepEqual(res.visibleCards.map((c) => c.id), ["c-worldwide"]);
  assert.equal(cards.find((c) => c.id === "c-worldwide").hidden, false);
  assert.equal(cards.find((c) => c.id === "c-us").hidden, true);
});

test("filter option US filters cards in place", () => {
  const cards = makeSampleCards();
  const res = fbs.filterCardsByCountry(cards, "US");
  assert.equal(res.selectedCountry, "US");
  assert.deepEqual(res.visibleCards.map((c) => c.id), ["c-us"]);
  assert.equal(res.isEmpty, false);
});

test("filter option UK matches single and multi-country UK cards", () => {
  const cards = makeSampleCards();
  const res = fbs.filterCardsByCountry(cards, "UK");
  assert.equal(res.selectedCountry, "UK");
  assert.deepEqual(res.visibleCards.map((c) => c.id), ["c-uk", "c-multi"]);
});

test("filter option Canada filters cards in place", () => {
  const cards = makeSampleCards();
  const res = fbs.filterCardsByCountry(cards, "Canada");
  assert.equal(res.selectedCountry, "Canada");
  assert.deepEqual(res.visibleCards.map((c) => c.id), ["c-ca"]);
});

test("filter option Australia matches single and multi-country Australia cards", () => {
  const cards = makeSampleCards();
  const res = fbs.filterCardsByCountry(cards, "Australia");
  assert.equal(res.selectedCountry, "Australia");
  assert.deepEqual(res.visibleCards.map((c) => c.id), ["c-au", "c-multi"]);
});

test("resetCountryFilter restores All selection and un-hides all cards", () => {
  const cards = makeSampleCards();
  fbs.filterCardsByCountry(cards, "US");
  assert.equal(cards.filter((c) => !c.hidden).length, 1);

  const resetRes = fbs.resetCountryFilter(cards);
  assert.equal(resetRes.selectedCountry, "All");
  assert.equal(resetRes.visibleCount, cards.length);
  assert.equal(cards.every((c) => c.hidden === false), true);
});

test("empty state triggers when no cards match selected country", () => {
  const onlyUs = [{ id: "c-us", country: "US", hidden: false }];
  const res = fbs.filterCardsByCountry(onlyUs, "Canada");
  assert.equal(res.selectedCountry, "Canada");
  assert.equal(res.visibleCount, 0);
  assert.equal(res.isEmpty, true);
  assert.match(res.emptyMessage, /Canada/);
});

test("URL hash helpers parse and format country filters safely", () => {
  assert.equal(fbs.parseCountryFromHash("#country=UK"), "UK");
  assert.equal(fbs.parseCountryFromHash("#canada"), "Canada");
  assert.equal(fbs.parseCountryFromHash("#country=Finland"), "All");
  assert.equal(fbs.parseCountryFromHash(""), "All");
  assert.equal(fbs.formatCountryHash("All"), "");
  assert.equal(fbs.formatCountryHash("Australia"), "#country=Australia");
});

test("mapSubscribeResponse maps pending status to success check-email state with resend", () => {
  const state = fbs.mapSubscribeResponse({
    ok: true,
    status: 200,
    body: JSON.stringify({ status: "pending" })
  });
  assert.equal(state.state, "success");
  assert.match(state.message, /Check your email to confirm/i);
  assert.equal(state.canResend, true);
  assert.equal(state.dismissible, false);
});

test("mapSubscribeResponse maps already_subscribed status clearly", () => {
  const state = fbs.mapSubscribeResponse({
    ok: true,
    status: 200,
    body: JSON.stringify({ status: "already_subscribed" })
  });
  assert.equal(state.state, "already_subscribed");
  assert.match(state.message, /already subscribed/i);
  assert.equal(state.canResend, false);
});

test("mapSubscribeResponse maps pending_resent and pending_confirmation with resend enabled", () => {
  const resent = fbs.mapSubscribeResponse({
    ok: true,
    status: 200,
    body: JSON.stringify({ status: "pending_resent" })
  });
  assert.equal(resent.state, "pending");
  assert.equal(resent.canResend, true);
  assert.match(resent.message, /Check your email to confirm/i);
});

test("mapSubscribeResponse maps worker error status to dismissible error", () => {
  const errState = fbs.mapSubscribeResponse({
    ok: false,
    status: 400,
    body: JSON.stringify({ status: "error", message: "Invalid email domain." })
  });
  assert.equal(errState.state, "error");
  assert.equal(errState.message, "Invalid email domain.");
  assert.equal(errState.dismissible, true);
});

test("mapSubscribeResponse maps 404, 405, non-JSON, and network errors to honest unavailable message", () => {
  const s404 = fbs.mapSubscribeResponse({ ok: false, status: 404, body: "Not Found" });
  assert.equal(s404.state, "error");
  assert.match(s404.message, /Signup isn't open yet, please try again later/i);
  assert.equal(s404.dismissible, true);

  const s405 = fbs.mapSubscribeResponse({ ok: false, status: 405, body: "Method Not Allowed" });
  assert.equal(s405.state, "error");
  assert.match(s405.message, /Signup isn't open yet, please try again later/i);

  const sHtml = fbs.mapSubscribeResponse({ ok: true, status: 200, body: "<html></html>" });
  assert.equal(sHtml.state, "error");
  assert.match(sHtml.message, /Signup isn't open yet, please try again later/i);

  const sNet = fbs.mapSubscribeResponse({ networkError: true });
  assert.equal(sNet.state, "error");
  assert.match(sNet.message, /Signup isn't open yet, please try again later/i);
});

test("submitSubscribe POSTs JSON with email and honeypot website field to /subscribe", async () => {
  let capturedUrl = null;
  let capturedOptions = null;

  const mockFetch = async (url, options) => {
    capturedUrl = url;
    capturedOptions = options;
    return {
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ status: "pending" })
    };
  };

  const result = await fbs.submitSubscribe({
    email: "parent@example.com",
    website: "bot-trap",
    fetchImpl: mockFetch
  });

  assert.equal(capturedUrl, "/subscribe");
  assert.equal(capturedOptions.method, "POST");
  const parsedBody = JSON.parse(capturedOptions.body);
  assert.deepEqual(parsedBody, {
    email: "parent@example.com",
    website: "bot-trap"
  });
  assert.equal(result.state, "success");
});

test("hub and roundup HTML files meet scaffold and SEO requirements", () => {
  const hubHtml = fs.readFileSync(path.join(repoRoot, "free-baby-stuff/index.html"), "utf8");
  const roundupHtml = fs.readFileSync(path.join(repoRoot, "free-baby-stuff/roundup-1/index.html"), "utf8");

  assert.ok(hubHtml.includes(fbs.PRIVACY_LINE), "hub includes exact privacy line");
  assert.ok(hubHtml.includes('name="website"'), "hub includes honeypot field");
  assert.ok(hubHtml.includes('data-trial-block="true"'), "hub includes trial block");
  assert.ok(hubHtml.includes('data-copy-pending="true"'), "hub includes copy-pending placeholders");
  assert.ok(roundupHtml.includes('data-copy-pending="true"'), "roundup includes copy-pending placeholder");
  assert.ok(!hubHtml.toLowerCase().includes("noindex"), "hub has no noindex");
  assert.ok(!roundupHtml.toLowerCase().includes("noindex"), "roundup has no noindex");
});
