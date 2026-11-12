import test from "node:test";
import assert from "node:assert/strict";
import {
  TOKEN_TTL_MS,
  createCsrfToken,
  createToken,
  createUnsubscribeToken,
  createWorker,
  verifyToken,
  verifyUnsubscribeToken,
} from "../src/index.js";
import { CONFIRMED_MARKER, UNCONFIRMED_MARKER } from "../src/resend.js";

const BASE_TIME = 1762900000000;
const DEFAULT_SEGMENT_ID = "seg-free-baby-stuff";

function createTestEnv(overrides = {}) {
  return {
    RESEND_API_KEY: "test-key-mock",
    RESEND_AUDIENCE_ID: DEFAULT_SEGMENT_ID,
    TOKEN_SECRET: "test-hmac-secret-value-for-unit-tests",
    SITE_ORIGIN: "https://snugs.ai",
    FROM_EMAIL: "Snugs <hello@snugs.ai>",
    ...overrides,
  };
}

function createMockResend(initialContacts = {}) {
  const contacts = new Map();
  const segmentsByEmail = new Map();
  const calls = [];
  const emails = [];

  function ensureSegmentSet(email) {
    const norm = email.toLowerCase();
    if (!segmentsByEmail.has(norm)) {
      segmentsByEmail.set(norm, new Set());
    }
    return segmentsByEmail.get(norm);
  }

  for (const [rawEmail, info] of Object.entries(initialContacts)) {
    const email = rawEmail.toLowerCase();
    const { segments, ...contactFields } = info;
    contacts.set(email, {
      object: "contact",
      ...contactFields,
      email,
    });
    const segSet = ensureSegmentSet(email);
    const initialSegments =
      segments !== undefined ? segments : [DEFAULT_SEGMENT_ID];
    for (const seg of initialSegments) {
      segSet.add(seg);
    }
  }

  async function mockFetch(url, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const parsedBody = options.body ? JSON.parse(options.body) : null;
    calls.push({
      method,
      url: String(url),
      body: parsedBody,
      headers: options.headers || {},
    });

    const u = new URL(url);

    if (u.pathname === "/contacts" && method === "POST") {
      const email = parsedBody.email.toLowerCase();
      const record = {
        object: "contact",
        id: `contact-${contacts.size + 1}`,
        email,
        unsubscribed: Boolean(parsedBody.unsubscribed),
        first_name: parsedBody.first_name ?? "",
      };
      contacts.set(email, record);
      const segSet = ensureSegmentSet(email);
      if (Array.isArray(parsedBody.segments)) {
        for (const item of parsedBody.segments) {
          const segId = typeof item === "string" ? item : item?.id;
          if (segId) {
            segSet.add(segId);
          }
        }
      }
      return new Response(JSON.stringify(record), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    const contactMatch = u.pathname.match(/^\/contacts\/([^/]+)$/);
    if (contactMatch) {
      const email = decodeURIComponent(contactMatch[1]).toLowerCase();

      if (method === "GET") {
        const existing = contacts.get(email);
        if (!existing) {
          return new Response(
            JSON.stringify({ message: "Contact not found" }),
            { status: 404, headers: { "Content-Type": "application/json" } }
          );
        }
        return new Response(JSON.stringify(existing), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      if (method === "PATCH") {
        const existing = contacts.get(email);
        if (!existing) {
          return new Response(
            JSON.stringify({ message: "Contact not found" }),
            { status: 404, headers: { "Content-Type": "application/json" } }
          );
        }
        const updated = {
          ...existing,
          ...parsedBody,
        };
        contacts.set(email, updated);
        return new Response(JSON.stringify(updated), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
    }

    const listSegmentsMatch = u.pathname.match(
      /^\/contacts\/([^/]+)\/segments$/
    );
    if (listSegmentsMatch && method === "GET") {
      const email = decodeURIComponent(listSegmentsMatch[1]).toLowerCase();
      const existing = contacts.get(email);
      if (!existing) {
        return new Response(
          JSON.stringify({ message: "Contact not found" }),
          { status: 404, headers: { "Content-Type": "application/json" } }
        );
      }
      const segSet = ensureSegmentSet(email);
      return new Response(
        JSON.stringify({
          object: "list",
          data: Array.from(segSet).map((id) => ({ id })),
          has_more: false,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    const segmentMatch = u.pathname.match(
      /^\/contacts\/([^/]+)\/segments\/([^/]+)$/
    );
    if (segmentMatch && (method === "POST" || method === "DELETE")) {
      const email = decodeURIComponent(segmentMatch[1]).toLowerCase();
      const segId = decodeURIComponent(segmentMatch[2]);
      const existing = contacts.get(email);
      if (!existing) {
        return new Response(
          JSON.stringify({ message: "Contact not found" }),
          { status: 404, headers: { "Content-Type": "application/json" } }
        );
      }
      const segSet = ensureSegmentSet(email);
      if (method === "POST") {
        segSet.add(segId);
        return new Response(
          JSON.stringify({ object: "contact_segment", id: segId }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }
        );
      }
      segSet.delete(segId);
      return new Response(
        JSON.stringify({ object: "contact_segment", id: segId, deleted: true }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (u.pathname === "/emails" && method === "POST") {
      const emailRecord = {
        id: `email-${emails.length + 1}`,
        ...parsedBody,
      };
      emails.push(emailRecord);
      return new Response(JSON.stringify({ id: emailRecord.id }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    return new Response(JSON.stringify({ message: "Unexpected endpoint" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  return {
    mockFetch,
    contacts,
    segmentsByEmail,
    calls,
    emails,
    getSegments(email) {
      return ensureSegmentSet(email);
    },
  };
}

test("1. new subscribe creates unconfirmed contact (unsubscribed=true) in this segment and sends confirmation email", async () => {
  const mock = createMockResend();
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });

  const req = new Request("https://snugs.ai/subscribe", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Origin: "https://snugs.ai",
    },
    body: JSON.stringify({ email: "Parent@Example.com", website: "" }),
  });

  const res = await worker.fetch(req, env);
  assert.equal(res.status, 200);
  const data = await res.json();
  assert.deepEqual(data, { status: "pending" });

  const stored = mock.contacts.get("parent@example.com");
  assert.ok(stored);
  assert.equal(stored.unsubscribed, true);
  assert.equal(stored.first_name, UNCONFIRMED_MARKER);
  assert.equal(
    mock.getSegments("parent@example.com").has(DEFAULT_SEGMENT_ID),
    true
  );

  const createCall = mock.calls.find(
    (c) => c.method === "POST" && c.url.endsWith("/contacts")
  );
  assert.ok(createCall);
  assert.deepEqual(createCall.body.segments, [{ id: DEFAULT_SEGMENT_ID }]);

  assert.equal(mock.emails.length, 1);
  assert.deepEqual(mock.emails[0].to, ["parent@example.com"]);
  assert.match(mock.emails[0].subject, /Confirm/i);
  assert.match(mock.emails[0].text, /https:\/\/snugs\.ai\/confirm\?token=/);
  assert.match(
    mock.emails[0].text,
    /One short email a week, the roundup\. Nothing else\. Unsubscribe anytime\./
  );
  assert.match(mock.emails[0].text, /https:\/\/snugs\.ai\/unsubscribe\?token=/);
  assert.match(mock.emails[0].html, /https:\/\/snugs\.ai\/unsubscribe\?token=/);
  assert.equal(mock.emails[0].text.includes("RESEND_UNSUBSCRIBE_URL"), false);
  assert.equal(mock.emails[0].html.includes("RESEND_UNSUBSCRIBE_URL"), false);
  assert.equal(mock.emails[0].text.includes("{{{"), false);
  assert.equal(mock.emails[0].html.includes("{{{"), false);
  assert.match(
    mock.emails[0].headers["List-Unsubscribe"],
    /<https:\/\/snugs\.ai\/unsubscribe\?token=[^>]+>, <mailto:hello@snugs\.ai\?subject=unsubscribe>/
  );
  assert.equal(
    mock.emails[0].headers["List-Unsubscribe-Post"],
    "List-Unsubscribe=One-Click"
  );
});

test("2. duplicate subscribe for pending unconfirmed contact resends confirmation without creating duplicate contact", async () => {
  const mock = createMockResend({
    "pending@example.com": {
      id: "c-1",
      email: "pending@example.com",
      unsubscribed: true,
      first_name: UNCONFIRMED_MARKER,
    },
  });
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });

  const req = new Request("https://snugs.ai/subscribe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "pending@example.com", website: "" }),
  });

  const res = await worker.fetch(req, env);
  assert.equal(res.status, 200);
  const data = await res.json();
  assert.deepEqual(data, { status: "pending_resent" });

  const createCalls = mock.calls.filter(
    (c) => c.method === "POST" && c.url.endsWith("/contacts")
  );
  assert.equal(createCalls.length, 0);
  assert.equal(mock.emails.length, 1);
  assert.match(mock.emails[0].subject, /Confirm/i);
});

test("3. already confirmed contact in this segment returns already_subscribed and sends no email", async () => {
  const mock = createMockResend({
    "active@example.com": {
      id: "c-2",
      email: "active@example.com",
      unsubscribed: false,
      first_name: CONFIRMED_MARKER,
      segments: [DEFAULT_SEGMENT_ID],
    },
  });
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });

  const req = new Request("https://snugs.ai/subscribe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "active@example.com", website: "" }),
  });

  const res = await worker.fetch(req, env);
  assert.equal(res.status, 200);
  const data = await res.json();
  assert.deepEqual(data, { status: "already_subscribed" });
  assert.equal(mock.emails.length, 0);
  assert.equal(mock.calls.length, 2);
  assert.equal(mock.calls[0].method, "GET");
  assert.equal(mock.calls[1].method, "GET");
  assert.match(mock.calls[1].url, /\/contacts\/active%40example\.com\/segments$/);
});

test("4. honeypot website field filled returns 200 pending and makes no Resend calls", async () => {
  const mock = createMockResend();
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });

  const req = new Request("https://snugs.ai/subscribe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: "bot@example.com",
      website: "https://spam-bot.example",
    }),
  });

  const res = await worker.fetch(req, env);
  assert.equal(res.status, 200);
  const data = await res.json();
  assert.deepEqual(data, { status: "pending" });
  assert.equal(mock.calls.length, 0);
  assert.equal(mock.emails.length, 0);
});

test("5. invalid email returns 400 error and makes no Resend calls", async () => {
  const mock = createMockResend();
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });

  for (const badEmail of ["", "not-an-email", "missing@tld", "a..b@snugs.ai"]) {
    const req = new Request("https://snugs.ai/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: badEmail, website: "" }),
    });
    const res = await worker.fetch(req, env);
    assert.equal(res.status, 400);
    const data = await res.json();
    assert.equal(data.status, "error");
  }

  assert.equal(mock.calls.length, 0);
});

test("6. GET /confirm with valid token shows Confirm my email button and makes no mutating calls", async () => {
  const mock = createMockResend({
    "reader@example.com": {
      id: "c-3",
      email: "reader@example.com",
      unsubscribed: true,
      first_name: UNCONFIRMED_MARKER,
    },
  });
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });
  const token = await createToken("reader@example.com", env.TOKEN_SECRET, {
    now: BASE_TIME,
  });

  const req = new Request(
    `https://snugs.ai/confirm?token=${encodeURIComponent(token)}`,
    { method: "GET" }
  );
  const res = await worker.fetch(req, env);
  assert.equal(res.status, 200);
  assert.match(res.headers.get("Content-Type") || "", /text\/html/);

  const html = await res.text();
  assert.match(html, /Confirm my email/);
  assert.match(html, /<form method="POST" action="\/confirm">/);
  assert.match(html, /name="token"/);
  assert.match(html, /name="csrf"/);

  const mutatingCalls = mock.calls.filter((c) => c.method !== "GET");
  assert.equal(mutatingCalls.length, 0);
  assert.equal(mock.contacts.get("reader@example.com").unsubscribed, true);
});

test("7. GET /confirm shows You're already on the list only when confirmed and in this segment", async () => {
  const mock = createMockResend({
    "confirmed@example.com": {
      id: "c-4",
      email: "confirmed@example.com",
      unsubscribed: false,
      first_name: CONFIRMED_MARKER,
      segments: [DEFAULT_SEGMENT_ID],
    },
    "otherseg@example.com": {
      id: "c-4b",
      email: "otherseg@example.com",
      unsubscribed: false,
      first_name: CONFIRMED_MARKER,
      segments: ["seg-other-list"],
    },
  });
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });

  const tokenConfirmed = await createToken(
    "confirmed@example.com",
    env.TOKEN_SECRET,
    { now: BASE_TIME }
  );
  const resConfirmed = await worker.fetch(
    new Request(
      `https://snugs.ai/confirm?token=${encodeURIComponent(tokenConfirmed)}`,
      { method: "GET" }
    ),
    env
  );
  assert.equal(resConfirmed.status, 200);
  const htmlConfirmed = await resConfirmed.text();
  assert.match(
    htmlConfirmed,
    /You&#39;re already on the list|You're already on the list/
  );
  assert.doesNotMatch(
    htmlConfirmed,
    /<button[^>]*>Confirm my email<\/button>/
  );

  const tokenOther = await createToken(
    "otherseg@example.com",
    env.TOKEN_SECRET,
    { now: BASE_TIME }
  );
  const resOther = await worker.fetch(
    new Request(
      `https://snugs.ai/confirm?token=${encodeURIComponent(tokenOther)}`,
      { method: "GET" }
    ),
    env
  );
  assert.equal(resOther.status, 200);
  const htmlOther = await resOther.text();
  assert.match(htmlOther, /<button[^>]*>Confirm my email<\/button>/);
});

test("8. POST /confirm flips contact to unsubscribed=false once, ensures segment membership, and sends one welcome email", async () => {
  const mock = createMockResend({
    "newparent@example.com": {
      id: "c-5",
      email: "newparent@example.com",
      unsubscribed: true,
      first_name: UNCONFIRMED_MARKER,
      segments: [],
    },
  });
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });
  const token = await createToken("newparent@example.com", env.TOKEN_SECRET, {
    now: BASE_TIME,
  });
  const csrf = await createCsrfToken(token, env.TOKEN_SECRET);

  const req = new Request("https://snugs.ai/confirm", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Origin: "https://snugs.ai",
    },
    body: new URLSearchParams({ token, csrf }).toString(),
  });

  const res = await worker.fetch(req, env);
  assert.equal(res.status, 200);
  const html = await res.text();
  assert.match(html, /You&#39;re on the list|You're on the list/);

  const updated = mock.contacts.get("newparent@example.com");
  assert.equal(updated.unsubscribed, false);
  assert.equal(updated.first_name, CONFIRMED_MARKER);
  assert.equal(
    mock.getSegments("newparent@example.com").has(DEFAULT_SEGMENT_ID),
    true
  );

  assert.equal(mock.emails.length, 1);
  assert.deepEqual(mock.emails[0].to, ["newparent@example.com"]);
  assert.match(
    mock.emails[0].text,
    /One short email a week, the roundup\. Nothing else\. Unsubscribe anytime\./
  );
});

test("9. second POST /confirm sends no second welcome email and renders already-on-list", async () => {
  const mock = createMockResend({
    "once@example.com": {
      id: "c-6",
      email: "once@example.com",
      unsubscribed: true,
      first_name: UNCONFIRMED_MARKER,
    },
  });
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });
  const token = await createToken("once@example.com", env.TOKEN_SECRET, {
    now: BASE_TIME,
  });
  const csrf = await createCsrfToken(token, env.TOKEN_SECRET);

  const makePost = () =>
    new Request("https://snugs.ai/confirm", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Origin: "https://snugs.ai",
      },
      body: new URLSearchParams({ token, csrf }).toString(),
    });

  const firstRes = await worker.fetch(makePost(), env);
  assert.equal(firstRes.status, 200);
  assert.equal(mock.emails.length, 1);

  const secondRes = await worker.fetch(makePost(), env);
  assert.equal(secondRes.status, 200);
  const secondHtml = await secondRes.text();
  assert.match(
    secondHtml,
    /You&#39;re already on the list|You're already on the list/
  );
  assert.equal(mock.emails.length, 1);
});

test("10. expired token (past 48h) is rejected on both GET and POST /confirm and links back to hub", async () => {
  const mock = createMockResend();
  const env = createTestEnv();
  const token = await createToken("late@example.com", env.TOKEN_SECRET, {
    now: BASE_TIME,
  });
  const expiredTime = BASE_TIME + TOKEN_TTL_MS + 1000;
  const worker = createWorker({
    fetch: mock.mockFetch,
    now: () => expiredTime,
  });

  const getRes = await worker.fetch(
    new Request(
      `https://snugs.ai/confirm?token=${encodeURIComponent(token)}`,
      { method: "GET" }
    ),
    env
  );
  assert.equal(getRes.status, 400);
  const getHtml = await getRes.text();
  assert.match(getHtml, /expired/i);
  assert.match(getHtml, /https:\/\/snugs\.ai\/free-baby-stuff\//);

  const postRes = await worker.fetch(
    new Request("https://snugs.ai/confirm", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Origin: "https://snugs.ai",
      },
      body: new URLSearchParams({ token }).toString(),
    }),
    env
  );
  assert.equal(postRes.status, 400);
  const postHtml = await postRes.text();
  assert.match(postHtml, /expired/i);
  assert.match(postHtml, /https:\/\/snugs\.ai\/free-baby-stuff\//);
  assert.equal(mock.calls.length, 0);
});

test("11. tampered or invalid token is rejected on GET and POST /confirm", async () => {
  const mock = createMockResend();
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });
  const validToken = await createToken("user@example.com", env.TOKEN_SECRET, {
    now: BASE_TIME,
  });
  const tamperedToken = `${validToken.slice(0, -2)}ab`;

  const getRes = await worker.fetch(
    new Request(
      `https://snugs.ai/confirm?token=${encodeURIComponent(tamperedToken)}`,
      { method: "GET" }
    ),
    env
  );
  assert.equal(getRes.status, 400);
  const getHtml = await getRes.text();
  assert.match(getHtml, /invalid/i);
  assert.match(getHtml, /https:\/\/snugs\.ai\/free-baby-stuff\//);

  const postRes = await worker.fetch(
    new Request("https://snugs.ai/confirm", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Origin: "https://snugs.ai",
      },
      body: new URLSearchParams({ token: tamperedToken }).toString(),
    }),
    env
  );
  assert.equal(postRes.status, 400);
  assert.equal(mock.calls.length, 0);
});

test("12. cross-origin POST /confirm is rejected with 403 and makes no Resend calls", async () => {
  const mock = createMockResend({
    "victim@example.com": {
      id: "c-7",
      email: "victim@example.com",
      unsubscribed: true,
      first_name: UNCONFIRMED_MARKER,
    },
  });
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });
  const token = await createToken("victim@example.com", env.TOKEN_SECRET, {
    now: BASE_TIME,
  });

  const crossOriginReq = new Request("https://snugs.ai/confirm", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Origin: "https://evil.example.org",
    },
    body: new URLSearchParams({ token }).toString(),
  });
  const crossRes = await worker.fetch(crossOriginReq, env);
  assert.equal(crossRes.status, 403);

  const missingOriginReq = new Request("https://snugs.ai/confirm", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({ token }).toString(),
  });
  const missingRes = await worker.fetch(missingOriginReq, env);
  assert.equal(missingRes.status, 403);

  assert.equal(mock.calls.length, 0);
});

test("13. unsubscribe-then-resubscribe goes through double opt-in again", async () => {
  const mock = createMockResend({
    "returning@example.com": {
      id: "c-8",
      email: "returning@example.com",
      unsubscribed: true,
      first_name: CONFIRMED_MARKER,
    },
  });
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });

  // Step 1: Parent resubscribes after having previously confirmed and then unsubscribed
  const subReq = new Request("https://snugs.ai/subscribe", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Origin: "https://snugs.ai",
    },
    body: JSON.stringify({ email: "returning@example.com", website: "" }),
  });
  const subRes = await worker.fetch(subReq, env);
  assert.equal(subRes.status, 200);
  const subData = await subRes.json();
  assert.deepEqual(subData, { status: "pending" });

  // Contact remains unsubscribed=true and marker is reset to unconfirmed until confirmed
  assert.equal(mock.contacts.get("returning@example.com").unsubscribed, true);
  assert.equal(
    mock.contacts.get("returning@example.com").first_name,
    UNCONFIRMED_MARKER
  );
  assert.equal(mock.emails.length, 1);
  assert.match(mock.emails[0].subject, /Confirm/i);

  // Step 2: Parent confirms via POST /confirm and receives welcome email
  const token = await createToken("returning@example.com", env.TOKEN_SECRET, {
    now: BASE_TIME,
  });
  const confirmReq = new Request("https://snugs.ai/confirm", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Origin: "https://snugs.ai",
    },
    body: new URLSearchParams({ token }).toString(),
  });
  const confirmRes = await worker.fetch(confirmReq, env);
  assert.equal(confirmRes.status, 200);
  assert.equal(mock.contacts.get("returning@example.com").unsubscribed, false);
  assert.equal(
    mock.contacts.get("returning@example.com").first_name,
    CONFIRMED_MARKER
  );
  assert.equal(mock.emails.length, 2);
  assert.match(mock.emails[1].subject, /Free Baby Stuff Weekly list/i);
});

test("14. unknown routes and disallowed methods return 404", async () => {
  const mock = createMockResend();
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });

  const unknownPathRes = await worker.fetch(
    new Request("https://snugs.ai/unknown-path", { method: "GET" }),
    env
  );
  assert.equal(unknownPathRes.status, 404);

  const getSubscribeRes = await worker.fetch(
    new Request("https://snugs.ai/subscribe", { method: "GET" }),
    env
  );
  assert.equal(getSubscribeRes.status, 404);

  const putConfirmRes = await worker.fetch(
    new Request("https://snugs.ai/confirm", { method: "PUT" }),
    env
  );
  assert.equal(putConfirmRes.status, 404);
});

test("15. CORS Access-Control-Allow-Origin header is returned only for SITE_ORIGIN", async () => {
  const mock = createMockResend();
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });

  const allowedPreflight = await worker.fetch(
    new Request("https://snugs.ai/subscribe", {
      method: "OPTIONS",
      headers: { Origin: "https://snugs.ai" },
    }),
    env
  );
  assert.equal(allowedPreflight.status, 204);
  assert.equal(
    allowedPreflight.headers.get("Access-Control-Allow-Origin"),
    "https://snugs.ai"
  );

  const disallowedPreflight = await worker.fetch(
    new Request("https://snugs.ai/subscribe", {
      method: "OPTIONS",
      headers: { Origin: "https://other-site.example" },
    }),
    env
  );
  assert.equal(
    disallowedPreflight.headers.get("Access-Control-Allow-Origin"),
    null
  );

  const disallowedPost = await worker.fetch(
    new Request("https://snugs.ai/subscribe", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: "https://other-site.example",
      },
      body: JSON.stringify({ email: "valid@example.com", website: "bot" }),
    }),
    env
  );
  assert.equal(disallowedPost.headers.get("Access-Control-Allow-Origin"), null);
});

test("16. POST /confirm accepts worker's own preview host and rejects tampered CSRF token", async () => {
  const mock = createMockResend({
    "preview@example.com": {
      id: "c-9",
      email: "preview@example.com",
      unsubscribed: true,
      first_name: UNCONFIRMED_MARKER,
    },
  });
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });
  const token = await createToken("preview@example.com", env.TOKEN_SECRET, {
    now: BASE_TIME,
  });

  const badCsrfRes = await worker.fetch(
    new Request("https://snugs-free-baby-stuff.preview.workers.dev/confirm", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Origin: "https://snugs-free-baby-stuff.preview.workers.dev",
      },
      body: new URLSearchParams({ token, csrf: "bad-csrf-token" }).toString(),
    }),
    env
  );
  assert.equal(badCsrfRes.status, 403);
  assert.equal(mock.contacts.get("preview@example.com").unsubscribed, true);

  const validCsrf = await createCsrfToken(token, env.TOKEN_SECRET);
  const okRes = await worker.fetch(
    new Request("https://snugs-free-baby-stuff.preview.workers.dev/confirm", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Referer:
          "https://snugs-free-baby-stuff.preview.workers.dev/confirm?token=abc",
      },
      body: new URLSearchParams({ token, csrf: validCsrf }).toString(),
    }),
    env
  );
  assert.equal(okRes.status, 200);
  assert.equal(mock.contacts.get("preview@example.com").unsubscribed, false);
});

test("17. upstream Resend failure logs HTTP status without email or key and never leaks RESEND_API_KEY in response", async () => {
  const secretKey = "secret-api-key-value-never-leak";
  const targetEmail = "private-parent@example.com";
  const env = createTestEnv({ RESEND_API_KEY: secretKey });
  const failingFetch = async () =>
    new Response(JSON.stringify({ message: "Service unavailable" }), {
      status: 503,
    });
  const worker = createWorker({ fetch: failingFetch, now: () => BASE_TIME });

  const errorLogs = [];
  const origError = console.error;
  console.error = (...args) => {
    errorLogs.push(args.join(" "));
  };

  try {
    const res = await worker.fetch(
      new Request("https://snugs.ai/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: targetEmail, website: "" }),
      }),
      env
    );
    assert.equal(res.status, 502);
    const text = await res.text();
    assert.equal(text.includes(secretKey), false);
    assert.equal(text.includes(targetEmail), false);

    assert.equal(errorLogs.length, 1);
    assert.match(errorLogs[0], /resend/i);
    assert.match(errorLogs[0], /503/);
    assert.equal(errorLogs[0].includes(secretKey), false);
    assert.equal(errorLogs[0].toLowerCase().includes(targetEmail), false);
    assert.equal(errorLogs[0].toLowerCase().includes("private-parent"), false);
  } finally {
    console.error = origError;
  }
});

test("18. global contact from another segment is not already_subscribed, stays globally subscribed, and is added to this segment only on POST /confirm", async () => {
  const mock = createMockResend({
    "otherlist@example.com": {
      id: "c-10",
      email: "otherlist@example.com",
      unsubscribed: false,
      first_name: CONFIRMED_MARKER,
      segments: ["seg-other-newsletter"],
    },
  });
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });

  const subRes = await worker.fetch(
    new Request("https://snugs.ai/subscribe", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: "https://snugs.ai",
      },
      body: JSON.stringify({ email: "otherlist@example.com", website: "" }),
    }),
    env
  );
  assert.equal(subRes.status, 200);
  const subBody = await subRes.json();
  assert.deepEqual(subBody, { status: "pending" });

  // Global contact stays subscribed to its existing list and is not added to this segment before confirmation
  assert.equal(mock.contacts.get("otherlist@example.com").unsubscribed, false);
  assert.equal(
    mock.getSegments("otherlist@example.com").has("seg-other-newsletter"),
    true
  );
  assert.equal(
    mock.getSegments("otherlist@example.com").has(DEFAULT_SEGMENT_ID),
    false
  );
  assert.equal(mock.emails.length, 1);

  const token = await createToken("otherlist@example.com", env.TOKEN_SECRET, {
    now: BASE_TIME,
  });
  const csrf = await createCsrfToken(token, env.TOKEN_SECRET);

  const confirmRes = await worker.fetch(
    new Request("https://snugs.ai/confirm", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Origin: "https://snugs.ai",
      },
      body: new URLSearchParams({ token, csrf }).toString(),
    }),
    env
  );
  assert.equal(confirmRes.status, 200);
  assert.equal(mock.contacts.get("otherlist@example.com").unsubscribed, false);
  assert.equal(
    mock.getSegments("otherlist@example.com").has("seg-other-newsletter"),
    true
  );
  assert.equal(
    mock.getSegments("otherlist@example.com").has(DEFAULT_SEGMENT_ID),
    true
  );
  assert.equal(mock.emails.length, 2);

  for (const call of mock.calls) {
    const pathname = new URL(call.url).pathname;
    assert.match(pathname, /^\/(contacts|emails)(\/|$)/);
  }
});

test("19. POST /confirm creates contact in this segment if missing at confirm time", async () => {
  const mock = createMockResend();
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });

  const token = await createToken("freshconfirm@example.com", env.TOKEN_SECRET, {
    now: BASE_TIME,
  });
  const csrf = await createCsrfToken(token, env.TOKEN_SECRET);

  const res = await worker.fetch(
    new Request("https://snugs.ai/confirm", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Origin: "https://snugs.ai",
      },
      body: new URLSearchParams({ token, csrf }).toString(),
    }),
    env
  );
  assert.equal(res.status, 200);
  const created = mock.contacts.get("freshconfirm@example.com");
  assert.ok(created);
  assert.equal(created.unsubscribed, false);
  assert.equal(created.first_name, CONFIRMED_MARKER);
  assert.equal(
    mock.getSegments("freshconfirm@example.com").has(DEFAULT_SEGMENT_ID),
    true
  );
  assert.equal(mock.emails.length, 1);
});

test("20. welcome email contains real unsubscribe link and List-Unsubscribe-Post header without RESEND_UNSUBSCRIBE_URL or {{{", async () => {
  const mock = createMockResend({
    "welcomecheck@example.com": {
      id: "c-20",
      email: "welcomecheck@example.com",
      unsubscribed: true,
      first_name: UNCONFIRMED_MARKER,
    },
  });
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });
  const token = await createToken(
    "welcomecheck@example.com",
    env.TOKEN_SECRET,
    { now: BASE_TIME }
  );
  const csrf = await createCsrfToken(token, env.TOKEN_SECRET);

  const res = await worker.fetch(
    new Request("https://snugs.ai/confirm", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Origin: "https://snugs.ai",
      },
      body: new URLSearchParams({ token, csrf }).toString(),
    }),
    env
  );
  assert.equal(res.status, 200);
  assert.equal(mock.emails.length, 1);
  const msg = mock.emails[0];
  assert.match(msg.text, /https:\/\/snugs\.ai\/unsubscribe\?token=/);
  assert.match(msg.html, /https:\/\/snugs\.ai\/unsubscribe\?token=/);
  assert.equal(msg.text.includes("RESEND_UNSUBSCRIBE_URL"), false);
  assert.equal(msg.html.includes("RESEND_UNSUBSCRIBE_URL"), false);
  assert.equal(msg.text.includes("{{{"), false);
  assert.equal(msg.html.includes("{{{"), false);
  assert.match(
    msg.headers["List-Unsubscribe"],
    /<https:\/\/snugs\.ai\/unsubscribe\?token=[^>]+>, <mailto:hello@snugs\.ai\?subject=unsubscribe>/
  );
  assert.equal(
    msg.headers["List-Unsubscribe-Post"],
    "List-Unsubscribe=One-Click"
  );
});

test("21. unsubscribe token is AES-GCM encrypted, does not reveal email, and enforces purpose separation", async () => {
  const secret = "test-hmac-secret-value-for-unit-tests";
  const email = "secret-parent+tag@example.com";
  const unsubToken = await createUnsubscribeToken(email, secret);

  assert.equal(unsubToken.toLowerCase().includes("secret-parent"), false);
  assert.equal(unsubToken.toLowerCase().includes("example.com"), false);
  for (const part of unsubToken.split(".")) {
    const padded =
      part.replace(/-/g, "+").replace(/_/g, "/") +
      "=".repeat((4 - (part.length % 4)) % 4);
    const decoded = Buffer.from(padded, "base64").toString("utf8");
    assert.equal(decoded.toLowerCase().includes("secret-parent"), false);
    assert.equal(decoded.toLowerCase().includes("example.com"), false);
  }

  const verified = await verifyUnsubscribeToken(unsubToken, secret);
  assert.deepEqual(verified, { ok: true, email });

  // Confirm token fails verifyUnsubscribeToken, and unsub token fails verifyToken
  const confirmToken = await createToken(email, secret, { now: BASE_TIME });
  assert.deepEqual(await verifyUnsubscribeToken(confirmToken, secret), {
    ok: false,
  });
  const confirmCheck = await verifyToken(unsubToken, secret, {
    now: BASE_TIME,
  });
  assert.equal(confirmCheck.valid, false);

  // Garbage inputs never throw
  for (const garbage of ["", null, undefined, "not-a-token", "a.b.c", "..", "!!!.???"]) {
    assert.deepEqual(await verifyUnsubscribeToken(garbage, secret), {
      ok: false,
    });
  }
});

test("22. GET /unsubscribe is read-only (zero Resend calls) and renders confirmation form", async () => {
  const mock = createMockResend({
    "reader-unsub@example.com": {
      id: "c-22",
      email: "reader-unsub@example.com",
      unsubscribed: false,
      first_name: CONFIRMED_MARKER,
      segments: [DEFAULT_SEGMENT_ID],
    },
  });
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });
  const unsubToken = await createUnsubscribeToken(
    "reader-unsub@example.com",
    env.TOKEN_SECRET
  );

  const res = await worker.fetch(
    new Request(
      `https://snugs.ai/unsubscribe?token=${encodeURIComponent(unsubToken)}`,
      { method: "GET" }
    ),
    env
  );
  assert.equal(res.status, 200);
  const html = await res.text();
  assert.match(html, /Unsubscribe from Free Baby Stuff Weekly\?/);
  assert.match(html, /<form method="POST" action="\/unsubscribe">/);
  assert.match(html, /name="token"/);
  assert.equal(mock.calls.length, 0);
  assert.equal(mock.contacts.get("reader-unsub@example.com").unsubscribed, false);
});

test("23. POST /unsubscribe one-click (no Origin) and form submit remove segment, set unsubscribed=true when no segments remain, and allow resubscribe", async () => {
  const email = "oneclick@example.com";
  const mock = createMockResend({
    [email]: {
      id: "c-23",
      email,
      unsubscribed: false,
      first_name: CONFIRMED_MARKER,
      segments: [DEFAULT_SEGMENT_ID],
    },
  });
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });
  const unsubToken = await createUnsubscribeToken(email, env.TOKEN_SECRET);

  // One-click POST without Origin or Referer
  const res1 = await worker.fetch(
    new Request(
      `https://snugs.ai/unsubscribe?token=${encodeURIComponent(unsubToken)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: "List-Unsubscribe=One-Click",
      }
    ),
    env
  );
  assert.equal(res1.status, 200);
  const html1 = await res1.text();
  assert.match(html1, /You&#39;re unsubscribed|You're unsubscribed/);
  assert.equal(mock.getSegments(email).has(DEFAULT_SEGMENT_ID), false);
  assert.equal(mock.contacts.get(email).unsubscribed, true);
  assert.equal(mock.emails.length, 0);

  // Repeat POST via form field is idempotent
  const res2 = await worker.fetch(
    new Request("https://snugs.ai/unsubscribe", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ token: unsubToken }).toString(),
    }),
    env
  );
  assert.equal(res2.status, 200);
  assert.equal(mock.emails.length, 0);

  // Resubscribe after unsubscribe goes through pending -> confirm -> back in segment
  const subRes = await worker.fetch(
    new Request("https://snugs.ai/subscribe", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: "https://snugs.ai",
      },
      body: JSON.stringify({ email, website: "" }),
    }),
    env
  );
  assert.equal(subRes.status, 200);
  assert.deepEqual(await subRes.json(), { status: "pending" });
  assert.equal(mock.emails.length, 1);

  const confirmToken = await createToken(email, env.TOKEN_SECRET, {
    now: BASE_TIME,
  });
  const csrf = await createCsrfToken(confirmToken, env.TOKEN_SECRET);
  const confirmRes = await worker.fetch(
    new Request("https://snugs.ai/confirm", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Origin: "https://snugs.ai",
      },
      body: new URLSearchParams({ token: confirmToken, csrf }).toString(),
    }),
    env
  );
  assert.equal(confirmRes.status, 200);
  assert.equal(mock.getSegments(email).has(DEFAULT_SEGMENT_ID), true);
  assert.equal(mock.contacts.get(email).unsubscribed, false);
});

test("24. POST /unsubscribe for multi-segment contact keeps other segment and leaves unsubscribed=false", async () => {
  const email = "multilist@example.com";
  const mock = createMockResend({
    [email]: {
      id: "c-24",
      email,
      unsubscribed: false,
      first_name: CONFIRMED_MARKER,
      segments: [DEFAULT_SEGMENT_ID, "seg-other-list"],
    },
  });
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });
  const unsubToken = await createUnsubscribeToken(email, env.TOKEN_SECRET);

  const res = await worker.fetch(
    new Request(
      `https://snugs.ai/unsubscribe?token=${encodeURIComponent(unsubToken)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: "List-Unsubscribe=One-Click",
      }
    ),
    env
  );
  assert.equal(res.status, 200);
  assert.equal(mock.getSegments(email).has(DEFAULT_SEGMENT_ID), false);
  assert.equal(mock.getSegments(email).has("seg-other-list"), true);
  assert.equal(mock.contacts.get(email).unsubscribed, false);
  assert.equal(mock.contacts.get(email).first_name, CONFIRMED_MARKER);
});

test("25. POST /unsubscribe handles pending contact and missing contact", async () => {
  const pendingEmail = "pending-unsub@example.com";
  const missingEmail = "missing-unsub@example.com";
  const mock = createMockResend({
    [pendingEmail]: {
      id: "c-25",
      email: pendingEmail,
      unsubscribed: true,
      first_name: UNCONFIRMED_MARKER,
      segments: [DEFAULT_SEGMENT_ID],
    },
  });
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });

  const pendingToken = await createUnsubscribeToken(
    pendingEmail,
    env.TOKEN_SECRET
  );
  const resPending = await worker.fetch(
    new Request(
      `https://snugs.ai/unsubscribe?token=${encodeURIComponent(pendingToken)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: "List-Unsubscribe=One-Click",
      }
    ),
    env
  );
  assert.equal(resPending.status, 200);
  assert.equal(mock.getSegments(pendingEmail).has(DEFAULT_SEGMENT_ID), false);
  assert.equal(mock.contacts.get(pendingEmail).unsubscribed, true);

  const missingToken = await createUnsubscribeToken(
    missingEmail,
    env.TOKEN_SECRET
  );
  const resMissing = await worker.fetch(
    new Request(
      `https://snugs.ai/unsubscribe?token=${encodeURIComponent(missingToken)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: "List-Unsubscribe=One-Click",
      }
    ),
    env
  );
  assert.equal(resMissing.status, 200);
  const htmlMissing = await resMissing.text();
  assert.match(htmlMissing, /You&#39;re unsubscribed|You're unsubscribed/);
});

test("26. /unsubscribe rejects bad, tampered, missing, and confirm tokens with 400 and /confirm rejects unsub token", async () => {
  const email = "token-checks@example.com";
  const mock = createMockResend({
    [email]: {
      id: "c-26",
      email,
      unsubscribed: false,
      first_name: CONFIRMED_MARKER,
      segments: [DEFAULT_SEGMENT_ID],
    },
  });
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });

  const validUnsub = await createUnsubscribeToken(email, env.TOKEN_SECRET);
  const tamperedUnsub =
    validUnsub.slice(0, -1) + (validUnsub.endsWith("A") ? "B" : "A");
  const confirmToken = await createToken(email, env.TOKEN_SECRET, {
    now: BASE_TIME,
  });

  for (const bad of ["", "bad", tamperedUnsub, confirmToken]) {
    const query = bad ? `?token=${encodeURIComponent(bad)}` : "";
    const getRes = await worker.fetch(
      new Request(`https://snugs.ai/unsubscribe${query}`, { method: "GET" }),
      env
    );
    assert.equal(getRes.status, 400);
    const getHtml = await getRes.text();
    assert.match(getHtml, /Invalid unsubscribe link/);

    const postRes = await worker.fetch(
      new Request(`https://snugs.ai/unsubscribe${query}`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: "List-Unsubscribe=One-Click",
      }),
      env
    );
    assert.equal(postRes.status, 400);
  }

  // Unsub token rejected on GET and POST /confirm
  const getConfirmRes = await worker.fetch(
    new Request(
      `https://snugs.ai/confirm?token=${encodeURIComponent(validUnsub)}`,
      { method: "GET" }
    ),
    env
  );
  assert.equal(getConfirmRes.status, 400);

  const csrf = await createCsrfToken(validUnsub, env.TOKEN_SECRET);
  const postConfirmRes = await worker.fetch(
    new Request("https://snugs.ai/confirm", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Origin: "https://snugs.ai",
      },
      body: new URLSearchParams({ token: validUnsub, csrf }).toString(),
    }),
    env
  );
  assert.equal(postConfirmRes.status, 400);

  // Disallowed method on /unsubscribe returns 404
  const putRes = await worker.fetch(
    new Request("https://snugs.ai/unsubscribe", { method: "PUT" }),
    env
  );
  assert.equal(putRes.status, 404);

  assert.equal(mock.calls.length, 0);
});

test("27. non-HTTP error logs sanitized message without email, key, or secret, and 503 on /unsubscribe logs status", async () => {
  const apiKey = "custom-api-key-val";
  const tokenSecret = "custom-token-secret-val";
  const resendStyleKey = "re_" + "abc123xyz";
  const email = "leak-test+qa@example.com";
  const env = createTestEnv({
    RESEND_API_KEY: apiKey,
    TOKEN_SECRET: tokenSecret,
  });

  const errorLogs = [];
  const origError = console.error;
  console.error = (...args) => {
    errorLogs.push(args.join(" "));
  };

  try {
    const throwingWorker = createWorker({
      fetch: async () => {
        throw new TypeError(
          `fetch failed for ${email} with ${apiKey} and ${tokenSecret} and ${resendStyleKey} and Bearer tok123`
        );
      },
      now: () => BASE_TIME,
    });

    const res1 = await throwingWorker.fetch(
      new Request("https://snugs.ai/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, website: "" }),
      }),
      env
    );
    assert.equal(res1.status, 502);
    assert.equal(errorLogs.length, 1);
    assert.match(
      errorLogs[0],
      /resend error route=\/subscribe op=unknown status=unknown error=TypeError: fetch failed/
    );
    assert.equal(errorLogs[0].includes("leak-test"), false);
    assert.equal(errorLogs[0].includes("@example.com"), false);
    assert.equal(errorLogs[0].includes(apiKey), false);
    assert.equal(errorLogs[0].includes(tokenSecret), false);
    assert.equal(errorLogs[0].includes(resendStyleKey), false);
    assert.equal(errorLogs[0].includes("tok123"), false);
    assert.match(errorLogs[0], /\[email\]/);
    assert.match(errorLogs[0], /\[redacted\]/);

    errorLogs.length = 0;
    const unsubToken = await createUnsubscribeToken(email, tokenSecret);
    const worker503 = createWorker({
      fetch: async () =>
        new Response(JSON.stringify({ message: "unavailable" }), {
          status: 503,
        }),
      now: () => BASE_TIME,
    });
    const res2 = await worker503.fetch(
      new Request(
        `https://snugs.ai/unsubscribe?token=${encodeURIComponent(unsubToken)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: "List-Unsubscribe=One-Click",
        }
      ),
      env
    );
    assert.equal(res2.status, 502);
    assert.equal(errorLogs.length, 1);
    assert.match(
      errorLogs[0],
      /resend error route=\/unsubscribe op=getContact status=503/
    );
    assert.equal(errorLogs[0].includes("leak-test"), false);
    assert.equal(errorLogs[0].includes(apiKey), false);
  } finally {
    console.error = origError;
  }
});
