import {
  CONFIRMED_MARKER,
  UNCONFIRMED_MARKER,
  createResendClient,
  hasConfirmedMarker,
  isContactConfirmed,
} from "./resend.js";

export const TOKEN_TTL_MS = 48 * 60 * 60 * 1000;
const DEFAULT_SITE_ORIGIN = "https://snugs.ai";
const DEFAULT_FROM_EMAIL = "Snugs <hello@snugs.ai>";
const PRIVACY_PROMISE =
  "One short email a week, the roundup. Nothing else. Unsubscribe anytime.";
const EXPIRED_OR_INVALID_MESSAGE =
  "That confirmation link has expired or already been used. If you are already confirmed, you are all set. If not, sign up again on the hub and we will send a fresh link.";

const encoder = new TextEncoder();
const decoder = new TextDecoder();
const UNSUB_HKDF_SALT = encoder.encode("snugs-fbs-unsubscribe-salt-v1");
const UNSUB_HKDF_INFO = encoder.encode("snugs-fbs-unsubscribe-v1");

function toBase64Url(bytes) {
  let binary = "";
  const arr = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  for (let i = 0; i < arr.byteLength; i++) {
    binary += String.fromCharCode(arr[i]);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64Url(str) {
  if (typeof str !== "string" || !/^[A-Za-z0-9_-]+$/.test(str)) {
    return null;
  }
  const padLen = (4 - (str.length % 4)) % 4;
  if (padLen === 3) {
    return null;
  }
  const base64 = str.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat(padLen);
  try {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    if (toBase64Url(bytes) !== str) {
      return null;
    }
    return bytes;
  } catch {
    return null;
  }
}

export function constantTimeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string") {
    return false;
  }
  const bytesA = encoder.encode(a);
  const bytesB = encoder.encode(b);
  if (bytesA.byteLength !== bytesB.byteLength) {
    return false;
  }
  let diff = 0;
  for (let i = 0; i < bytesA.byteLength; i++) {
    diff |= bytesA[i] ^ bytesB[i];
  }
  return diff === 0;
}

async function hmacSignBase64Url(secret, message) {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(message));
  return toBase64Url(signature);
}

export async function createToken(
  email,
  secret,
  { now = Date.now(), ttlMs = TOKEN_TTL_MS } = {}
) {
  if (!secret) {
    throw new Error("Missing TOKEN_SECRET configuration");
  }
  const normalizedEmail = normalizeEmail(email);
  const exp = now + ttlMs;
  const payloadJson = JSON.stringify({ email: normalizedEmail, exp });
  const payloadB64 = toBase64Url(encoder.encode(payloadJson));
  const sigB64 = await hmacSignBase64Url(secret, payloadB64);
  return `${payloadB64}.${sigB64}`;
}

export async function createCsrfToken(token, secret) {
  if (!secret || !token) {
    throw new Error("Missing token or secret for CSRF generation");
  }
  return hmacSignBase64Url(secret, `csrf:${token}`);
}

export async function verifyToken(token, secret, { now = Date.now() } = {}) {
  if (!secret || typeof token !== "string" || !token.includes(".")) {
    return { valid: false, reason: "invalid" };
  }
  const parts = token.split(".");
  if (parts.length !== 2) {
    return { valid: false, reason: "invalid" };
  }
  const [payloadB64, sigB64] = parts;
  if (!payloadB64 || !sigB64) {
    return { valid: false, reason: "invalid" };
  }

  const expectedSigB64 = await hmacSignBase64Url(secret, payloadB64);
  if (!constantTimeEqual(sigB64, expectedSigB64)) {
    return { valid: false, reason: "invalid" };
  }

  const payloadBytes = fromBase64Url(payloadB64);
  if (!payloadBytes) {
    return { valid: false, reason: "invalid" };
  }

  let payload;
  try {
    payload = JSON.parse(decoder.decode(payloadBytes));
  } catch {
    return { valid: false, reason: "invalid" };
  }

  if (
    !payload ||
    payload.p !== undefined ||
    typeof payload.email !== "string" ||
    !isValidEmail(payload.email) ||
    typeof payload.exp !== "number" ||
    !Number.isFinite(payload.exp)
  ) {
    return { valid: false, reason: "invalid" };
  }

  if (now > payload.exp) {
    return { valid: false, reason: "expired", email: payload.email };
  }

  return { valid: true, email: normalizeEmail(payload.email), exp: payload.exp };
}

async function deriveUnsubscribeKey(secret) {
  const baseKey = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    "HKDF",
    false,
    ["deriveKey"]
  );
  return crypto.subtle.deriveKey(
    {
      name: "HKDF",
      hash: "SHA-256",
      salt: UNSUB_HKDF_SALT,
      info: UNSUB_HKDF_INFO,
    },
    baseKey,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
}

export async function createUnsubscribeToken(email, secret) {
  if (!secret) {
    throw new Error("Missing TOKEN_SECRET configuration");
  }
  const normalizedEmail = normalizeEmail(email);
  const key = await deriveUnsubscribeKey(secret);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const plaintext = encoder.encode(
    JSON.stringify({ p: "unsub", email: normalizedEmail })
  );
  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    plaintext
  );
  return `${toBase64Url(iv)}.${toBase64Url(ciphertext)}`;
}

export async function verifyUnsubscribeToken(token, secret) {
  if (!secret || typeof token !== "string" || !token.includes(".")) {
    return { ok: false };
  }
  const parts = token.split(".");
  if (parts.length !== 2) {
    return { ok: false };
  }
  const [ivB64, ctB64] = parts;
  if (!ivB64 || !ctB64) {
    return { ok: false };
  }
  const iv = fromBase64Url(ivB64);
  const ciphertext = fromBase64Url(ctB64);
  if (!iv || iv.byteLength !== 12 || !ciphertext || ciphertext.byteLength <= 16) {
    return { ok: false };
  }
  try {
    const key = await deriveUnsubscribeKey(secret);
    const decrypted = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv },
      key,
      ciphertext
    );
    const payload = JSON.parse(decoder.decode(decrypted));
    if (
      !payload ||
      typeof payload !== "object" ||
      payload.p !== "unsub" ||
      typeof payload.email !== "string" ||
      !isValidEmail(payload.email)
    ) {
      return { ok: false };
    }
    return { ok: true, email: normalizeEmail(payload.email) };
  } catch {
    return { ok: false };
  }
}

export function normalizeEmail(raw) {
  return typeof raw === "string" ? raw.trim().toLowerCase() : "";
}

export function isValidEmail(raw) {
  const email = normalizeEmail(raw);
  if (!email || email.length > 254) return false;
  if (email.includes("..")) return false;
  const parts = email.split("@");
  if (parts.length !== 2) return false;
  const [local, domain] = parts;
  if (!local || !domain || local.length > 64) return false;
  if (local.startsWith(".") || local.endsWith(".")) return false;
  if (domain.startsWith(".") || domain.endsWith(".") || domain.startsWith("-")) {
    return false;
  }
  return /^[^\s@]+@[^\s@]+\.[A-Za-z]{2,}$/.test(email);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function getSiteOrigin(env) {
  const raw = env?.SITE_ORIGIN || DEFAULT_SITE_ORIGIN;
  return raw.replace(/\/+$/, "");
}

function getHubUrl(siteOrigin) {
  return `${siteOrigin}/free-baby-stuff/`;
}

function buildCorsHeaders(request, siteOrigin) {
  const reqOrigin = request.headers.get("Origin");
  if (reqOrigin && reqOrigin === siteOrigin) {
    return {
      "Access-Control-Allow-Origin": siteOrigin,
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      Vary: "Origin",
    };
  }
  return { Vary: "Origin" };
}

function jsonResponse(body, status, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      ...extraHeaders,
    },
  });
}

function htmlResponse(html, status = 200) {
  return new Response(html, {
    status,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Frame-Options": "DENY",
    },
  });
}

function renderConfirmPage({
  title,
  heading,
  message,
  messageHtml,
  siteOrigin,
  formHtml = "",
}) {
  const hubUrl = escapeHtml(getHubUrl(siteOrigin));
  const bodyMessageHtml =
    messageHtml !== undefined ? messageHtml : escapeHtml(message);
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="robots" content="noindex, nofollow" />
  <title>${escapeHtml(title)} | Snugs</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@600;700&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet" />
  <style>
    * { box-sizing: border-box; -webkit-font-smoothing: antialiased; }
    body {
      margin: 0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      background: linear-gradient(180deg, #FFFBF7 0%, #FFF7ED 100%);
      color: #1C1917;
      font-family: 'DM Sans', system-ui, -apple-system, sans-serif;
    }
    .card {
      width: 100%;
      max-width: 480px;
      background: #FFFFFF;
      border: 1px solid #FED7AA;
      border-radius: 20px;
      padding: 36px 32px;
      box-shadow: 0 12px 32px rgba(234, 88, 12, 0.08);
      text-align: center;
    }
    .brand {
      font-family: 'Crimson Pro', Georgia, serif;
      font-size: 22px;
      font-weight: 700;
      color: #EA580C;
      text-decoration: none;
      display: inline-block;
      margin-bottom: 16px;
    }
    h1 {
      font-family: 'Crimson Pro', Georgia, serif;
      font-size: 30px;
      line-height: 1.2;
      margin: 0 0 12px;
      color: #1C1917;
    }
    p {
      font-size: 16px;
      line-height: 1.6;
      color: #57534E;
      margin: 0 0 24px;
    }
    .btn {
      display: inline-block;
      background: #EA580C;
      color: #FFFFFF;
      font-family: inherit;
      font-size: 16px;
      font-weight: 600;
      padding: 14px 28px;
      border: none;
      border-radius: 9999px;
      cursor: pointer;
      text-decoration: none;
    }
    .btn:hover { background: #C2410C; }
    .back-link {
      display: inline-block;
      margin-top: 20px;
      font-size: 14px;
      color: #EA580C;
      text-decoration: underline;
    }
    .promise {
      font-size: 13px;
      color: #78716C;
      margin-top: 16px;
      margin-bottom: 0;
    }
  </style>
</head>
<body>
  <main class="card">
    <a class="brand" href="${escapeHtml(siteOrigin)}">Snugs</a>
    <h1>${escapeHtml(heading)}</h1>
    <p>${bodyMessageHtml}</p>
    ${formHtml}
    <p class="promise">${escapeHtml(PRIVACY_PROMISE)}</p>
    <a class="back-link" href="${hubUrl}">Back to Free Baby Stuff</a>
  </main>
</body>
</html>`;
}

function buildConfirmationEmail({
  email,
  confirmUrl,
  unsubscribeUrl,
  fromEmail,
}) {
  const subject = "Confirm your signup for Free Baby Stuff Weekly";
  const text = [
    "Hi, and thanks for signing up.",
    "",
    "You asked to join Free Baby Stuff Weekly, the Snugs roundup of free baby stuff that we verify on the official sites before we list it. One click confirms it is really you:",
    "",
    `Confirm my email: ${confirmUrl}`,
    "",
    "After you confirm, you get one short email a week: new verified free offers for parents, the ones about to expire, and a note when a catch changes. Nothing else.",
    "",
    "If you did not sign up, ignore this email. The address will not be added and you will not hear from us again.",
    "",
    "The Snugs team",
    "",
    `Unsubscribe anytime: ${unsubscribeUrl}`,
  ].join("\n");

  const html = `<div style="font-family: system-ui, -apple-system, sans-serif; color: #1C1917; max-width: 520px; line-height: 1.6;">
  <p>Hi, and thanks for signing up.</p>
  <p>You asked to join Free Baby Stuff Weekly, the Snugs roundup of free baby stuff that we verify on the official sites before we list it. One click confirms it is really you:</p>
  <p><a href="${escapeHtml(confirmUrl)}" style="display: inline-block; background: #EA580C; color: #FFFFFF; padding: 12px 22px; border-radius: 9999px; text-decoration: none; font-weight: 600;">Confirm my email</a></p>
  <p>After you confirm, you get one short email a week: new verified free offers for parents, the ones about to expire, and a note when a catch changes. Nothing else.</p>
  <p>If you did not sign up, ignore this email. The address will not be added and you will not hear from us again.</p>
  <p>The Snugs team</p>
  <hr style="border: none; border-top: 1px solid #E7E5E4; margin: 24px 0;" />
  <p style="font-size: 12px; color: #78716C;">Unsubscribe anytime: <a href="${escapeHtml(unsubscribeUrl)}">unsubscribe</a></p>
</div>`;

  return {
    from: fromEmail,
    to: [email],
    subject,
    text,
    html,
    headers: {
      "List-Unsubscribe": `<${unsubscribeUrl}>, <mailto:hello@snugs.ai?subject=unsubscribe>`,
      "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    },
  };
}

function buildWelcomeEmail({ email, unsubscribeUrl, siteOrigin, fromEmail }) {
  const hubUrl = getHubUrl(siteOrigin);
  const subject = "You are on the list. Start with the free book.";
  const text = [
    "Welcome to Free Baby Stuff Weekly.",
    "",
    "Here is how this list works. Every week we check free offers for parents on the brands' and governments' own websites. If an offer needs a purchase or a card, we print that next to it, in the open. If an offer dies, we retire it. No affiliate links, so we never earn anything from what we list.",
    "",
    "Three good places to start:",
    "",
    "1. A free book every month until age 5. Dolly Parton's Imagination Library mails your child a book monthly, free. The catch is geography: check whether your ZIP is covered.",
    "2. The registry box truth. Amazon, Target, Walmart and Babylist all call their welcome boxes free. All four need registry spending first. The exact amounts are on the hub.",
    "3. Sample boxes that are actually free. PINCHme and SampleSource ship free sample boxes with no card required.",
    "",
    `The full list, with the catches printed: Free Baby Stuff, Verified (${hubUrl})`,
    "",
    'One last thing, since this list is from Snugs. Snugs is our baby sleep app: it tracks your baby\'s sleep and tells you when the next nap window opens. It comes with a 14-day free trial, and trying it is the only "offer" of ours you will ever see in this email series, right here, once.',
    "",
    "See you next week,",
    "The Snugs team",
    "",
    `Unsubscribe anytime: ${unsubscribeUrl}`,
  ].join("\n");

  const html = `<div style="font-family: system-ui, -apple-system, sans-serif; color: #1C1917; max-width: 520px; line-height: 1.6;">
  <p>Welcome to Free Baby Stuff Weekly.</p>
  <p>Here is how this list works. Every week we check free offers for parents on the brands' and governments' own websites. If an offer needs a purchase or a card, we print that next to it, in the open. If an offer dies, we retire it. No affiliate links, so we never earn anything from what we list.</p>
  <p>Three good places to start:</p>
  <ol>
    <li><strong>A free book every month until age 5.</strong> Dolly Parton's Imagination Library mails your child a book monthly, free. The catch is geography: check whether your ZIP is covered.</li>
    <li><strong>The registry box truth.</strong> Amazon, Target, Walmart and Babylist all call their welcome boxes free. All four need registry spending first. The exact amounts are on the hub.</li>
    <li><strong>Sample boxes that are actually free.</strong> PINCHme and SampleSource ship free sample boxes with no card required.</li>
  </ol>
  <p>The full list, with the catches printed: <a href="${escapeHtml(hubUrl)}" style="color: #EA580C; font-weight: 600;">Free Baby Stuff, Verified</a></p>
  <p>One last thing, since this list is from Snugs. Snugs is our baby sleep app: it tracks your baby's sleep and tells you when the next nap window opens. It comes with a 14-day free trial, and trying it is the only &quot;offer&quot; of ours you will ever see in this email series, right here, once.</p>
  <p>See you next week,<br />The Snugs team</p>
  <hr style="border: none; border-top: 1px solid #E7E5E4; margin: 24px 0;" />
  <p style="font-size: 12px; color: #78716C;">Unsubscribe anytime: <a href="${escapeHtml(unsubscribeUrl)}">unsubscribe</a></p>
</div>`;

  return {
    from: fromEmail,
    to: [email],
    subject,
    text,
    html,
    headers: {
      "List-Unsubscribe": `<${unsubscribeUrl}>, <mailto:hello@snugs.ai?subject=unsubscribe>`,
      "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    },
  };
}

function isSameOriginPost(request, siteOrigin) {
  let siteHost;
  let workerHost;
  try {
    siteHost = new URL(siteOrigin).host.toLowerCase();
    workerHost = new URL(request.url).host.toLowerCase();
  } catch {
    return false;
  }

  const allowedHosts = new Set([siteHost, workerHost]);
  const originHeader = request.headers.get("Origin");
  const refererHeader = request.headers.get("Referer");

  if (!originHeader && !refererHeader) {
    return false;
  }

  if (originHeader) {
    try {
      const originHost = new URL(originHeader).host.toLowerCase();
      if (!allowedHosts.has(originHost)) {
        return false;
      }
    } catch {
      return false;
    }
  }

  if (refererHeader) {
    try {
      const refererHost = new URL(refererHeader).host.toLowerCase();
      if (!allowedHosts.has(refererHost)) {
        return false;
      }
    } catch {
      return false;
    }
  }

  return true;
}

async function parseSubscribePayload(request) {
  const contentType = (request.headers.get("Content-Type") || "").toLowerCase();
  if (contentType.includes("application/x-www-form-urlencoded")) {
    const text = await request.text();
    const params = new URLSearchParams(text);
    return {
      email: params.get("email") ?? "",
      website: params.get("website") ?? "",
    };
  }
  const data = await request.json();
  if (!data || typeof data !== "object") {
    throw new Error("Invalid JSON payload");
  }
  return {
    email: data.email ?? "",
    website: data.website ?? "",
  };
}

async function parseConfirmPostPayload(request, url) {
  let token = url.searchParams.get("token") || "";
  let csrf = "";

  const contentType = (request.headers.get("Content-Type") || "").toLowerCase();
  if (contentType.includes("application/json")) {
    try {
      const body = await request.json();
      if (body && typeof body === "object") {
        if (typeof body.token === "string") token = body.token;
        if (typeof body.csrf === "string") csrf = body.csrf;
      }
    } catch {
      // Fall back to query token if body is empty
    }
  } else {
    try {
      const text = await request.text();
      if (text) {
        const params = new URLSearchParams(text);
        if (params.has("token")) token = params.get("token") || "";
        if (params.has("csrf")) csrf = params.get("csrf") || "";
      }
    } catch {
      // Fall back to query token
    }
  }

  return { token: token.trim(), csrf: csrf.trim() };
}

async function parseUnsubscribePostPayload(request, url) {
  let token = url.searchParams.get("token") || "";

  const contentType = (request.headers.get("Content-Type") || "").toLowerCase();
  if (contentType.includes("application/json")) {
    try {
      const body = await request.json();
      if (body && typeof body === "object" && typeof body.token === "string") {
        token = body.token;
      }
    } catch {
      // Fall back to query token if body is empty
    }
  } else {
    try {
      const text = await request.text();
      if (text) {
        const params = new URLSearchParams(text);
        if (params.has("token")) {
          token = params.get("token") || "";
        }
      }
    } catch {
      // Fall back to query token
    }
  }

  return { token: token.trim() };
}

function sanitizeErrorMessage(err, env = {}) {
  const name =
    err && typeof err.name === "string" && err.name ? err.name : "Error";
  const rawMessage =
    err && typeof err.message === "string" ? err.message : String(err ?? "");
  let text = `${name}: ${rawMessage}`;

  for (const secret of [env?.RESEND_API_KEY, env?.TOKEN_SECRET]) {
    if (typeof secret === "string" && secret.length > 0) {
      text = text.replaceAll(secret, "[redacted]");
    }
  }

  text = text
    .replace(/Bearer\s+\S+/gi, "[redacted]")
    .replace(/re_[A-Za-z0-9_]+/g, "[redacted]")
    .replace(/[A-Za-z0-9._%+-]+(?:@|%40)[A-Za-z0-9.-]+\.[A-Za-z]{2,}/gi, "[email]")
    .replace(/\s+/g, " ")
    .trim();

  if (text.length > 200) {
    text = text.slice(0, 200);
  }
  return text;
}

function logResendError(route, err, env = {}) {
  const op = err && typeof err.op === "string" ? err.op : "unknown";
  const hasStatus =
    err && (typeof err.status === "number" || typeof err.status === "string");
  const status = hasStatus ? err.status : "unknown";
  if (hasStatus) {
    console.error(`resend error route=${route} op=${op} status=${status}`);
    return;
  }
  const sanitized = sanitizeErrorMessage(err, env);
  console.error(
    `resend error route=${route} op=${op} status=${status} error=${sanitized}`
  );
}

export function createWorker(options = {}) {
  return {
    async fetch(request, env = {}, ctx) {
      const siteOrigin = getSiteOrigin(env);
      const fromEmail = env.FROM_EMAIL || DEFAULT_FROM_EMAIL;
      const fetchImpl = options.fetch || env.fetch || globalThis.fetch;
      const nowFn =
        options.now ||
        (typeof env.now === "function" ? env.now : () => Date.now());

      const url = new URL(request.url);
      const { pathname } = url;
      const method = request.method.toUpperCase();

      if (pathname === "/subscribe") {
        const corsHeaders = buildCorsHeaders(request, siteOrigin);

        if (method === "OPTIONS") {
          return new Response(null, { status: 204, headers: corsHeaders });
        }

        if (method !== "POST") {
          return jsonResponse({ error: "Not found" }, 404, corsHeaders);
        }

        let payload;
        try {
          payload = await parseSubscribePayload(request);
        } catch {
          return jsonResponse(
            { status: "error", error: "Invalid request body." },
            400,
            corsHeaders
          );
        }

        if (
          payload.website !== undefined &&
          payload.website !== null &&
          String(payload.website).trim() !== ""
        ) {
          return jsonResponse({ status: "pending" }, 200, corsHeaders);
        }

        if (!isValidEmail(payload.email)) {
          return jsonResponse(
            { status: "error", error: "Please enter a valid email address." },
            400,
            corsHeaders
          );
        }

        const email = normalizeEmail(payload.email);

        try {
          const segmentId = env.RESEND_AUDIENCE_ID;
          const resend = createResendClient({
            apiKey: env.RESEND_API_KEY,
            audienceId: segmentId,
            fetchImpl,
          });

          const existing = await resend.getContact(email);
          let inSegment = false;
          if (existing) {
            const segmentIds = segmentId
              ? await resend.listContactSegments(email)
              : [];
            inSegment = !segmentId || segmentIds.includes(segmentId);
          }

          if (existing && inSegment && isContactConfirmed(existing)) {
            return jsonResponse(
              { status: "already_subscribed" },
              200,
              corsHeaders
            );
          }

          const token = await createToken(email, env.TOKEN_SECRET, {
            now: nowFn(),
          });
          const unsubToken = await createUnsubscribeToken(
            email,
            env.TOKEN_SECRET
          );
          const confirmUrl = `${siteOrigin}/confirm?token=${encodeURIComponent(token)}`;
          const unsubscribeUrl = `${siteOrigin}/unsubscribe?token=${encodeURIComponent(unsubToken)}`;
          const emailMsg = buildConfirmationEmail({
            email,
            confirmUrl,
            unsubscribeUrl,
            siteOrigin,
            fromEmail,
          });

          if (existing) {
            if (!inSegment) {
              await resend.sendEmail(emailMsg);
              return jsonResponse({ status: "pending" }, 200, corsHeaders);
            }

            if (hasConfirmedMarker(existing)) {
              await resend.updateContact(email, {
                unsubscribed: true,
                first_name: UNCONFIRMED_MARKER,
              });
              await resend.sendEmail(emailMsg);
              return jsonResponse({ status: "pending" }, 200, corsHeaders);
            }

            await resend.sendEmail(emailMsg);
            return jsonResponse({ status: "pending_resent" }, 200, corsHeaders);
          }

          await resend.createContact({
            email,
            unsubscribed: true,
            first_name: UNCONFIRMED_MARKER,
            segmentId,
          });
          await resend.sendEmail(emailMsg);
          return jsonResponse({ status: "pending" }, 200, corsHeaders);
        } catch (err) {
          logResendError("/subscribe", err, env);
          return jsonResponse(
            {
              status: "error",
              error: "Unable to process subscription right now.",
            },
            502,
            corsHeaders
          );
        }
      }

      if (pathname === "/confirm") {
        if (method === "GET") {
          const token = (url.searchParams.get("token") || "").trim();
          const verification = await verifyToken(token, env.TOKEN_SECRET, {
            now: nowFn(),
          });

          if (!verification.valid) {
            if (verification.reason === "expired") {
              return htmlResponse(
                renderConfirmPage({
                  title: "Confirmation link expired",
                  heading: "This confirmation link has expired",
                  message: EXPIRED_OR_INVALID_MESSAGE,
                  siteOrigin,
                }),
                400
              );
            }

            return htmlResponse(
              renderConfirmPage({
                title: "Invalid confirmation link",
                heading: "Invalid confirmation link",
                message: EXPIRED_OR_INVALID_MESSAGE,
                siteOrigin,
              }),
              400
            );
          }

          try {
            const segmentId = env.RESEND_AUDIENCE_ID;
            const resend = createResendClient({
              apiKey: env.RESEND_API_KEY,
              audienceId: segmentId,
              fetchImpl,
            });
            const contact = await resend.getContact(verification.email);
            if (isContactConfirmed(contact)) {
              const segmentIds = segmentId
                ? await resend.listContactSegments(verification.email)
                : [];
              const inSegment = !segmentId || segmentIds.includes(segmentId);
              if (inSegment) {
                return htmlResponse(
                  renderConfirmPage({
                    title: "Already subscribed",
                    heading: "You're already on the list",
                    message:
                      "Your email is already confirmed for Free Baby Stuff Weekly.",
                    siteOrigin,
                  }),
                  200
                );
              }
            }
          } catch (err) {
            logResendError("/confirm", err, env);
            // If read lookup fails transiently on GET, still render the confirm button
          }

          const csrf = await createCsrfToken(token, env.TOKEN_SECRET);
          const formHtml = `<form method="POST" action="/confirm">
      <input type="hidden" name="token" value="${escapeHtml(token)}" />
      <input type="hidden" name="csrf" value="${escapeHtml(csrf)}" />
      <button type="submit" class="btn">Confirm my email</button>
    </form>`;

          return htmlResponse(
            renderConfirmPage({
              title: "Confirm your email",
              heading: "Confirm your email",
              message:
                "Click the button below to finish joining Free Baby Stuff Weekly.",
              siteOrigin,
              formHtml,
            }),
            200
          );
        }

        if (method === "POST") {
          if (!isSameOriginPost(request, siteOrigin)) {
            return htmlResponse(
              renderConfirmPage({
                title: "Forbidden",
                heading: "Confirmation request blocked",
                message:
                  "Please submit your confirmation directly from the Snugs confirmation page.",
                siteOrigin,
              }),
              403
            );
          }

          const { token, csrf } = await parseConfirmPostPayload(request, url);
          const verification = await verifyToken(token, env.TOKEN_SECRET, {
            now: nowFn(),
          });

          if (!verification.valid) {
            if (verification.reason === "expired") {
              return htmlResponse(
                renderConfirmPage({
                  title: "Confirmation link expired",
                  heading: "This confirmation link has expired",
                  message: EXPIRED_OR_INVALID_MESSAGE,
                  siteOrigin,
                }),
                400
              );
            }

            return htmlResponse(
              renderConfirmPage({
                title: "Invalid confirmation link",
                heading: "Invalid confirmation link",
                message: EXPIRED_OR_INVALID_MESSAGE,
                siteOrigin,
              }),
              400
            );
          }

          if (csrf) {
            const expectedCsrf = await createCsrfToken(token, env.TOKEN_SECRET);
            if (!constantTimeEqual(csrf, expectedCsrf)) {
              return htmlResponse(
                renderConfirmPage({
                  title: "Forbidden",
                  heading: "Confirmation request blocked",
                  message:
                    "Invalid confirmation form security token. Please open the link from your email again.",
                  siteOrigin,
                }),
                403
              );
            }
          }

          try {
            const segmentId = env.RESEND_AUDIENCE_ID;
            const resend = createResendClient({
              apiKey: env.RESEND_API_KEY,
              audienceId: segmentId,
              fetchImpl,
            });

            const existing = await resend.getContact(verification.email);
            if (existing) {
              const segmentIds = segmentId
                ? await resend.listContactSegments(verification.email)
                : [];
              const inSegment = !segmentId || segmentIds.includes(segmentId);
              if (inSegment && isContactConfirmed(existing)) {
                return htmlResponse(
                  renderConfirmPage({
                    title: "Already subscribed",
                    heading: "You're already on the list",
                    message:
                      "Your email is already confirmed for Free Baby Stuff Weekly.",
                    siteOrigin,
                  }),
                  200
                );
              }

              await resend.updateContact(verification.email, {
                unsubscribed: false,
                first_name: CONFIRMED_MARKER,
              });
              if (segmentId && !inSegment) {
                await resend.addContactToSegment(verification.email, segmentId);
              }
            } else {
              await resend.createContact({
                email: verification.email,
                unsubscribed: false,
                first_name: CONFIRMED_MARKER,
                segmentId,
              });
            }

            const unsubToken = await createUnsubscribeToken(
              verification.email,
              env.TOKEN_SECRET
            );
            const unsubscribeUrl = `${siteOrigin}/unsubscribe?token=${encodeURIComponent(unsubToken)}`;
            const welcomeMsg = buildWelcomeEmail({
              email: verification.email,
              unsubscribeUrl,
              siteOrigin,
              fromEmail,
            });
            await resend.sendEmail(welcomeMsg);

            const hubUrl = escapeHtml(getHubUrl(siteOrigin));
            return htmlResponse(
              renderConfirmPage({
                title: "You are on the list.",
                heading: "You are on the list.",
                messageHtml: `Your first roundup is on its way. Until then, the full verified list lives here: <a href="${hubUrl}" style="color: #EA580C; font-weight: 600;">Free Baby Stuff, Verified</a>`,
                siteOrigin,
              }),
              200
            );
          } catch (err) {
            logResendError("/confirm", err, env);
            return htmlResponse(
              renderConfirmPage({
                title: "Error confirming subscription",
                heading: "Something went wrong",
                message:
                  "We could not complete your confirmation right now. Please try clicking the link in your email again in a moment.",
                siteOrigin,
              }),
              502
            );
          }
        }
      }

      if (pathname === "/unsubscribe") {
        if (method === "GET") {
          const token = (url.searchParams.get("token") || "").trim();
          const verification = await verifyUnsubscribeToken(
            token,
            env.TOKEN_SECRET
          );

          if (!verification.ok) {
            return htmlResponse(
              renderConfirmPage({
                title: "Invalid unsubscribe link",
                heading: "Invalid unsubscribe link",
                message:
                  "This unsubscribe link is invalid or incomplete. Please email hello@snugs.ai and we will remove you right away.",
                siteOrigin,
              }),
              400
            );
          }

          const formHtml = `<form method="POST" action="/unsubscribe">
      <input type="hidden" name="token" value="${escapeHtml(token)}" />
      <button type="submit" class="btn">Unsubscribe</button>
    </form>`;

          return htmlResponse(
            renderConfirmPage({
              title: "Unsubscribe",
              heading: "Unsubscribe",
              message: "Unsubscribe from Free Baby Stuff Weekly?",
              siteOrigin,
              formHtml,
            }),
            200
          );
        }

        if (method === "POST") {
          const { token } = await parseUnsubscribePostPayload(request, url);
          const verification = await verifyUnsubscribeToken(
            token,
            env.TOKEN_SECRET
          );

          if (!verification.ok) {
            return htmlResponse(
              renderConfirmPage({
                title: "Invalid unsubscribe link",
                heading: "Invalid unsubscribe link",
                message:
                  "This unsubscribe link is invalid or incomplete. Please email hello@snugs.ai and we will remove you right away.",
                siteOrigin,
              }),
              400
            );
          }

          try {
            const segmentId = env.RESEND_AUDIENCE_ID;
            const resend = createResendClient({
              apiKey: env.RESEND_API_KEY,
              audienceId: segmentId,
              fetchImpl,
              retryOn429: true,
            });

            const existing = await resend.getContact(verification.email);
            if (existing) {
              if (segmentId) {
                await resend.removeContactFromSegment(
                  verification.email,
                  segmentId
                );
                const remainingSegments = await resend.listContactSegments(
                  verification.email
                );
                if (remainingSegments.length === 0) {
                  await resend.updateContact(verification.email, {
                    unsubscribed: true,
                  });
                }
              } else {
                await resend.updateContact(verification.email, {
                  unsubscribed: true,
                });
              }
            }

            return htmlResponse(
              renderConfirmPage({
                title: "You're unsubscribed",
                heading: "You're unsubscribed",
                message: `You will not get Free Baby Stuff Weekly anymore. You can rejoin anytime at ${getHubUrl(siteOrigin)}.`,
                siteOrigin,
              }),
              200
            );
          } catch (err) {
            logResendError("/unsubscribe", err, env);
            return htmlResponse(
              renderConfirmPage({
                title: "Error unsubscribing",
                heading: "Something went wrong",
                message:
                  "We could not complete your unsubscribe request right now. Please try again in a moment or email hello@snugs.ai.",
                siteOrigin,
              }),
              502
            );
          }
        }
      }

      return jsonResponse({ error: "Not found" }, 404);
    },
  };
}

const defaultWorker = createWorker();
export default defaultWorker;
