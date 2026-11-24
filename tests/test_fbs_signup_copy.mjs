import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, "..");

const fbs = (await import("../assets/js/free-baby-stuff.js")).default;

test("free-baby-stuff/index.html helper copy does not promise weekly roundup before confirmation", () => {
  const htmlPath = path.join(rootDir, "free-baby-stuff", "index.html");
  const html = fs.readFileSync(htmlPath, "utf8");

  assert.equal(html.includes("Your first roundup arrives this week"), false);
  assert.equal(html.includes("arrives this week"), false);

  const expectedHelper = "Confirm your email first, then the roundup follows.";
  assert.equal(html.includes(expectedHelper), true);

  const matches = html.split(expectedHelper).length - 1;
  assert.equal(matches >= 2, true, "Expected helper copy in both hero and footer");
});

test("free-baby-stuff/index.html has dismiss controls for subscribe status", () => {
  const htmlPath = path.join(rootDir, "free-baby-stuff", "index.html");
  const html = fs.readFileSync(htmlPath, "utf8");

  assert.match(html, /id="subscribe-dismiss"/);
  assert.match(html, /id="subscribe-dismiss-footer"/);
});

test("parseConfirmationQuery parses confirmed query parameters and hashes", () => {
  const queryCases = [
    "?confirmed=1",
    "?confirmed=true",
    "?confirmed=yes",
    "?confirmed",
    "?status=confirmed",
    "?status=subscribed",
    "?subscription=confirmed",
    "?subscribed=1",
    "?foo=bar&confirmed=1&baz=qux"
  ];

  for (const q of queryCases) {
    const res = fbs.parseConfirmationQuery(q, "");
    assert.ok(res, `Failed to parse query: ${q}`);
    assert.equal(res.state, "confirmed");
    assert.equal(res.status, "confirmed");
    assert.equal(res.dismissible, true);
    assert.equal(res.canResend, false);
    assert.match(res.message, /You are subscribed/i);
    assert.match(res.message, /roundup will follow/i);
  }

  const hashCases = [
    "#confirmed",
    "#subscription-confirmed"
  ];

  for (const h of hashCases) {
    const res = fbs.parseConfirmationQuery("", h);
    assert.ok(res, `Failed to parse hash: ${h}`);
    assert.equal(res.state, "confirmed");
    assert.equal(res.dismissible, true);
  }
});

test("parseConfirmationQuery parses already_subscribed query parameters and hashes", () => {
  const queryCases = [
    "?status=already_subscribed",
    "?status=already-subscribed"
  ];

  for (const q of queryCases) {
    const res = fbs.parseConfirmationQuery(q, "");
    assert.ok(res, `Failed to parse query: ${q}`);
    assert.equal(res.state, "already_subscribed");
    assert.equal(res.dismissible, true);
    assert.equal(res.canResend, false);
    assert.match(res.message, /already subscribed/i);
  }

  const resHash = fbs.parseConfirmationQuery("", "#already-subscribed");
  assert.ok(resHash);
  assert.equal(resHash.state, "already_subscribed");
});

test("parseConfirmationQuery returns null for unconfirmed or irrelevant queries", () => {
  assert.equal(fbs.parseConfirmationQuery("", ""), null);
  assert.equal(fbs.parseConfirmationQuery("?country=US", ""), null);
  assert.equal(fbs.parseConfirmationQuery("?foo=bar", "#top"), null);
});

test("mapSubscribeResponse states are dismissible and double opt-in aligned", () => {
  const pending = fbs.mapSubscribeResponse({
    ok: true,
    status: 200,
    body: JSON.stringify({ status: "pending" })
  });
  assert.equal(pending.state, "success");
  assert.equal(pending.dismissible, true);
  assert.equal(pending.canResend, true);
  assert.match(pending.message, /confirm your subscription first, then the roundup follows/i);

  const resent = fbs.mapSubscribeResponse({
    ok: true,
    status: 200,
    body: JSON.stringify({ status: "pending_resent" })
  });
  assert.equal(resent.state, "pending");
  assert.equal(resent.dismissible, true);
  assert.equal(resent.canResend, true);
  assert.match(resent.message, /confirm first, then the roundup follows/i);

  const already = fbs.mapSubscribeResponse({
    ok: true,
    status: 200,
    body: JSON.stringify({ status: "already_subscribed" })
  });
  assert.equal(already.state, "already_subscribed");
  assert.equal(already.dismissible, true);
  assert.equal(already.canResend, false);
  assert.match(already.message, /already subscribed/i);

  const confirmed = fbs.mapSubscribeResponse({
    ok: true,
    status: 200,
    body: JSON.stringify({ status: "confirmed" })
  });
  assert.equal(confirmed.state, "confirmed");
  assert.equal(confirmed.dismissible, true);
  assert.equal(confirmed.canResend, false);
  assert.match(confirmed.message, /subscribed.*roundup will follow/i);
});

test("No em dashes or en dashes exist in changed files or copy", () => {
  const filesToCheck = [
    path.join(rootDir, "free-baby-stuff", "index.html"),
    path.join(rootDir, "assets", "js", "free-baby-stuff.js"),
    path.join(rootDir, "workers", "free-baby-stuff", "src", "index.js")
  ];

  for (const f of filesToCheck) {
    const content = fs.readFileSync(f, "utf8");
    assert.equal(content.includes("\u2014"), false, `Found em dash in ${f}`);
    assert.equal(content.includes("\u2013"), false, `Found en dash in ${f}`);
  }
});
