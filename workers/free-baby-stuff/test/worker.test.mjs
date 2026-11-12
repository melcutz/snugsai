import test from "node:test";
import assert from "node:assert/strict";
import {
  TOKEN_TTL_MS,
  createCsrfToken,
  createToken,
  createWorker,
} from "../src/index.js";
import { CONFIRMED_MARKER, UNCONFIRMED_MARKER } from "../src/resend.js";

const BASE_TIME = 1762900000000;

function createTestEnv(overrides = {}) {
  return {
    RESEND_API_KEY: "test-key-mock",
    RESEND_AUDIENCE_ID: "aud-free-baby-stuff",
    TOKEN_SECRET: "test-hmac-secret-value-for-unit-tests",
    SITE_ORIGIN: "https://snugs.ai",
    FROM_EMAIL: "Snugs <hello@snugs.ai>",
    ...overrides,
  };
}

function createMockResend(initialContacts = {}) {
  const contacts = new Map(Object.entries(initialContacts));
  const calls = [];
  const emails = [];

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
    const contactsPrefix = "/audiences/aud-free-baby-stuff/contacts";

    if (u.pathname === contactsPrefix && method === "POST") {
      const email = parsedBody.email.toLowerCase();
      const record = {
        object: "contact",
        id: `contact-${contacts.size + 1}`,
        email,
        unsubscribed: Boolean(parsedBody.unsubscribed),
        first_name: parsedBody.first_name ?? "",
      };
      contacts.set(email, record);
      return new Response(JSON.stringify(record), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (u.pathname.startsWith(`${contactsPrefix}/`)) {
      const email = decodeURIComponent(
        u.pathname.slice(`${contactsPrefix}/`.length)
      ).toLowerCase();

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
        const existing = contacts.get(email) || {
          object: "contact",
          id: `contact-${contacts.size + 1}`,
          email,
        };
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

  return { mockFetch, contacts, calls, emails };
}

test("1. new subscribe creates unconfirmed contact (unsubscribed=true) and sends confirmation email", async () => {
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

  assert.equal(mock.emails.length, 1);
  assert.deepEqual(mock.emails[0].to, ["parent@example.com"]);
  assert.match(mock.emails[0].subject, /Confirm/i);
  assert.match(mock.emails[0].text, /https:\/\/snugs\.ai\/confirm\?token=/);
  assert.match(
    mock.emails[0].text,
    /One short email a week, the roundup\. Nothing else\. Unsubscribe anytime\./
  );
  assert.match(mock.emails[0].text, /RESEND_UNSUBSCRIBE_URL/);
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
    (c) =>
      c.method === "POST" &&
      c.url.endsWith("/audiences/aud-free-baby-stuff/contacts")
  );
  assert.equal(createCalls.length, 0);
  assert.equal(mock.emails.length, 1);
  assert.match(mock.emails[0].subject, /Confirm/i);
});

test("3. already confirmed contact returns already_subscribed and sends no email", async () => {
  const mock = createMockResend({
    "active@example.com": {
      id: "c-2",
      email: "active@example.com",
      unsubscribed: false,
      first_name: CONFIRMED_MARKER,
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
  assert.equal(mock.calls.length, 1);
  assert.equal(mock.calls[0].method, "GET");
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

test("7. GET /confirm for already confirmed contact shows You're already on the list", async () => {
  const mock = createMockResend({
    "confirmed@example.com": {
      id: "c-4",
      email: "confirmed@example.com",
      unsubscribed: false,
      first_name: CONFIRMED_MARKER,
    },
  });
  const env = createTestEnv();
  const worker = createWorker({ fetch: mock.mockFetch, now: () => BASE_TIME });
  const token = await createToken("confirmed@example.com", env.TOKEN_SECRET, {
    now: BASE_TIME,
  });

  const req = new Request(
    `https://snugs.ai/confirm?token=${encodeURIComponent(token)}`,
    { method: "GET" }
  );
  const res = await worker.fetch(req, env);
  assert.equal(res.status, 200);
  const html = await res.text();
  assert.match(html, /You&#39;re already on the list|You're already on the list/);
  assert.doesNotMatch(html, /<button[^>]*>Confirm my email<\/button>/);
});

test("8. POST /confirm flips contact to unsubscribed=false once and sends one welcome email", async () => {
  const mock = createMockResend({
    "newparent@example.com": {
      id: "c-5",
      email: "newparent@example.com",
      unsubscribed: true,
      first_name: UNCONFIRMED_MARKER,
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

test("17. upstream Resend failure never leaks RESEND_API_KEY in response", async () => {
  const secretKey = "secret-api-key-value-never-leak";
  const env = createTestEnv({ RESEND_API_KEY: secretKey });
  const failingFetch = async () =>
    new Response(JSON.stringify({ message: "Internal error" }), { status: 500 });
  const worker = createWorker({ fetch: failingFetch, now: () => BASE_TIME });

  const res = await worker.fetch(
    new Request("https://snugs.ai/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "parent@example.com", website: "" }),
    }),
    env
  );
  assert.equal(res.status, 502);
  const text = await res.text();
  assert.equal(text.includes(secretKey), false);
});

