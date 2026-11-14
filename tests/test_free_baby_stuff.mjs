import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fbs from "../assets/js/free-baby-stuff.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");

const EXPECTED_55_TITLES = [
  "A free book for your child, every month until age 5",
  "Free formula samples and coupons by mail",
  "Free sample boxes you build yourself",
  "Free seasonal sample boxes",
  "Amazon Baby Registry Welcome Box",
  "Target Baby Box (Registry Welcome Kit)",
  "Walmart Baby Registry Welcome Box",
  "Babylist Hello Baby Box",
  "Khan Academy Kids",
  "Duolingo ABC",
  "Storyline Online",
  "StoryWeaver",
  "Oxford Owl free eBook library",
  "Sesame Street in Communities",
  "PBS KIDS",
  "Libby: your library card becomes an app",
  "Free books by post: the national schemes",
  "PJ Library",
  "OpenLearn (The Open University)",
  "UNICEF Parenting",
  "Raising Children Network",
  "Zero to Three",
  "Vroom",
  "BBC Tiny Happy People",
  "FutureLearn parenting courses",
  "Triple P Online (positive parenting courses)",
  "Bright by Text",
  "La Leche League: free breastfeeding help",
  "WIC: food support for mothers and young children",
  "Free diapers: the National Diaper Bank Network",
  "Scotland's Baby Box",
  "Finland's Maternity Package",
  "New South Wales Baby Bundle",
  "Victorian Baby Bundle",
  "England: funded childcare hours",
  "Scotland: 1,140 hours of funded early learning",
  "Head Start and Early Head Start (United States)",
  "Not free, but worth knowing: Canada's $10-a-day childcare",
  "Museums for All: museums from free to $5 with an EBT card",
  "Every Kid Outdoors: a free national parks pass for 4th graders",
  "Your library card may include free museum and zoo passes",
  "Kids Bowl Free: two free games a day, all summer",
  "CDC Milestone Tracker app",
  "Vaccines for Children (VFC): free vaccines for eligible kids",
  "Reach Out and Read: a free book at every checkup",
  "Free smoke alarms, installed",
  "Postpartum Support International: free help after birth",
  "parkrun: a free 5k in a park near you, every week",
  "Scratch: free coding for kids",
  "Smithsonian Learning Lab",
  "BBC Bitesize",
  "USAGov Benefit Finder (United States)",
  "Turn2us (United Kingdom)",
  "Canada Benefits Finder (Canada)",
  "VITA and TCE: free tax preparation (United States)"
];

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

test("filter option US shows US and Worldwide cards and hides UK-only cards", () => {
  const cards = makeSampleCards();
  const res = fbs.filterCardsByCountry(cards, "United States");
  assert.equal(res.selectedCountry, "US");
  assert.deepEqual(res.visibleCards.map((c) => c.id), ["c-worldwide", "c-us"]);
  assert.equal(cards.find((c) => c.id === "c-worldwide").hidden, false);
  assert.equal(cards.find((c) => c.id === "c-us").hidden, false);
  assert.equal(cards.find((c) => c.id === "c-uk").hidden, true);
  assert.equal(res.isEmpty, false);
});

test("filter option UK matches Worldwide, single and multi-country UK cards and hides US-only cards", () => {
  const cards = makeSampleCards();
  const res = fbs.filterCardsByCountry(cards, "United Kingdom");
  assert.equal(res.selectedCountry, "UK");
  assert.deepEqual(res.visibleCards.map((c) => c.id), ["c-worldwide", "c-uk", "c-multi"]);
  assert.equal(cards.find((c) => c.id === "c-us").hidden, true);
});

test("filter option Canada shows Canada and Worldwide cards", () => {
  const cards = makeSampleCards();
  const res = fbs.filterCardsByCountry(cards, "Canada");
  assert.equal(res.selectedCountry, "Canada");
  assert.deepEqual(res.visibleCards.map((c) => c.id), ["c-worldwide", "c-ca"]);
});

test("filter option Australia matches Worldwide, single and multi-country Australia cards", () => {
  const cards = makeSampleCards();
  const res = fbs.filterCardsByCountry(cards, "Australia");
  assert.equal(res.selectedCountry, "Australia");
  assert.deepEqual(res.visibleCards.map((c) => c.id), ["c-worldwide", "c-au", "c-multi"]);
});

test("filterCardsByCountry hides sections that become empty and shows non-empty sections", () => {
  const usSection = { id: "sec-us", dataset: { offerSection: "sec-us" }, hidden: false, style: { display: "" } };
  const ukSection = { id: "sec-uk", dataset: { offerSection: "sec-uk" }, hidden: false, style: { display: "" } };
  const cards = [
    { id: "c-us-1", country: "US", hidden: false, parentElement: usSection },
    { id: "c-uk-1", country: "UK", hidden: false, parentElement: ukSection }
  ];

  const usRes = fbs.filterCardsByCountry(cards, "US", [usSection, ukSection]);
  assert.equal(usSection.hidden, false);
  assert.equal(ukSection.hidden, true);
  assert.equal(ukSection.style.display, "none");
  assert.equal(usRes.hiddenSections.includes(ukSection), true);

  const ukRes = fbs.filterCardsByCountry(cards, "UK", [usSection, ukSection]);
  assert.equal(usSection.hidden, true);
  assert.equal(ukSection.hidden, false);
  assert.equal(ukSection.style.display, "");
  assert.equal(ukRes.hiddenSections.includes(usSection), true);

  fbs.resetCountryFilter(cards, [usSection, ukSection]);
  assert.equal(usSection.hidden, false);
  assert.equal(ukSection.hidden, false);
});

test("resetCountryFilter restores All selection and un-hides all cards", () => {
  const cards = makeSampleCards();
  fbs.filterCardsByCountry(cards, "US");
  assert.equal(cards.filter((c) => !c.hidden).length, 2);

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
  assert.equal(fbs.parseCountryFromHash("#country=United%20Kingdom"), "UK");
  assert.equal(fbs.parseCountryFromHash("#country=United%20States"), "US");
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
  assert.match(s405.message, /Signup isn't open yet, please try again later/i);

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

test("hub and roundup HTML files have no data-copy-pending and meet SEO requirements", () => {
  const hubHtml = fs.readFileSync(path.join(repoRoot, "free-baby-stuff/index.html"), "utf8");
  const roundupHtml = fs.readFileSync(path.join(repoRoot, "free-baby-stuff/roundup-1/index.html"), "utf8");

  assert.equal(hubHtml.includes("data-copy-pending"), false, "hub has no data-copy-pending");
  assert.equal(roundupHtml.includes("data-copy-pending"), false, "roundup has no data-copy-pending");
  assert.equal(hubHtml.includes("Listings are being verified"), false);
  assert.equal(roundupHtml.includes("Listings are being verified"), false);
  assert.equal(hubHtml.includes("\u2014"), false, "hub has no em dash");
  assert.equal(roundupHtml.includes("\u2014"), false, "roundup has no em dash");

  assert.ok(hubHtml.includes(fbs.PRIVACY_LINE), "hub includes exact privacy line");
  assert.ok(hubHtml.includes('id="subscribe-form"'), "hub includes primary subscribe-form");
  assert.ok(hubHtml.includes('id="subscribe-form-footer"'), "hub includes footer subscribe form without duplicate id");
  assert.ok(hubHtml.includes('name="website"'), "hub includes honeypot field");
  assert.ok(hubHtml.includes('data-trial-block="true"'), "hub includes trial block");
  assert.ok(!hubHtml.toLowerCase().includes("noindex"), "hub has no noindex");
  assert.ok(!roundupHtml.toLowerCase().includes("noindex"), "roundup has no noindex");
  assert.ok(
    roundupHtml.includes("Free Baby Stuff Weekly #1: a free book every month, sample boxes, and the registry box truth"),
    "roundup includes JJ's Roundup #1 title"
  );
});

test("hub renders all 55 listing titles, Where lines, Verified dates, and clean external links", () => {
  const hubHtml = fs.readFileSync(path.join(repoRoot, "free-baby-stuff/index.html"), "utf8");
  const withoutTemplate = hubHtml.replace(/<template[\s\S]*?<\/template>/gi, "");

  const cardRegex = /<article\s+class="offer-card[^"]*"\s+data-country="([^"]+)"[\s\S]*?<\/article>/gi;
  const cards = [];
  let match;
  while ((match = cardRegex.exec(withoutTemplate)) !== null) {
    cards.push({
      country: match[1],
      html: match[0],
      text: match[0]
        .replace(/<[^>]+>/g, " ")
        .replace(/&#39;/g, "'")
        .replace(/&quot;/g, '"')
        .replace(/&amp;/g, "&")
        .replace(/\s+/g, " ")
        .trim()
    });
  }

  assert.equal(cards.length, 55, "exactly 55 offer cards rendered in hub HTML");

  for (const title of EXPECTED_55_TITLES) {
    const found = cards.some((c) => c.text.includes(title));
    assert.equal(found, true, `missing listing title: ${title}`);
  }

  for (let i = 0; i < cards.length; i++) {
    const c = cards[i];
    assert.ok(c.country.length > 0, `card #${i + 1} has non-empty data-country`);
    assert.ok(c.text.includes("Where:"), `card #${i + 1} includes Where: line`);
    assert.ok(c.text.includes("Verified November 11, 2026"), `card #${i + 1} includes Verified November 11, 2026`);
  }

  const extAnchorRegex = /<a\s+([^>]*href="https?:\/\/[^"]+"[^>]*)>/gi;
  let aMatch;
  let extCount = 0;
  while ((aMatch = extAnchorRegex.exec(withoutTemplate)) !== null) {
    const attrs = aMatch[1];
    const hrefMatch = attrs.match(/href="([^"]+)"/i);
    if (!hrefMatch) continue;
    const href = hrefMatch[1];
    const urlObj = new URL(href);
    if (urlObj.hostname === "snugs.ai" || urlObj.hostname.endsWith(".snugs.ai")) continue;

    extCount++;
    assert.match(attrs, /target="_blank"/i, `external link ${href} has target="_blank"`);
    assert.match(attrs, /rel="[^"]*noopener[^"]*"/i, `external link ${href} has noopener`);
    assert.match(attrs, /rel="[^"]*noreferrer[^"]*"/i, `external link ${href} has noreferrer`);
    for (const bad of ["utm_", "?ref=", "&ref=", "tag=", "aff", "clickid"]) {
      assert.equal(href.toLowerCase().includes(bad), false, `external link ${href} has no ${bad}`);
    }
  }
  assert.ok(extCount >= 55, `checked ${extCount} external offer links`);
});

test("hub and roundup clip horizontal overflow from decorative blobs (#27)", () => {
  for (const relPath of ["free-baby-stuff/index.html", "free-baby-stuff/roundup-1/index.html"]) {
    const html = fs.readFileSync(path.join(repoRoot, relPath), "utf8");
    const styleMatch = html.match(/<style>([\s\S]*?)<\/style>/i);
    assert.ok(styleMatch, `${relPath} has inline <style>`);
    const css = styleMatch[1];
    assert.match(css, /html\s*\{[^}]*overflow-x\s*:\s*(?:hidden|clip)/i, `${relPath} clips html overflow-x`);
    assert.match(css, /body\s*\{[^}]*overflow-x\s*:\s*(?:hidden|clip)/i, `${relPath} clips body overflow-x`);
  }
});
