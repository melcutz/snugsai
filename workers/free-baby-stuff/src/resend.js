const RESEND_BASE_URL = "https://api.resend.com";

export const CONFIRMED_MARKER = "confirmed";
export const UNCONFIRMED_MARKER = "unconfirmed";

export function hasConfirmedMarker(contact) {
  if (!contact || typeof contact !== "object") return false;
  return (
    contact.first_name === CONFIRMED_MARKER ||
    contact.last_name === CONFIRMED_MARKER ||
    contact.confirmed === true
  );
}

export function isContactConfirmed(contact) {
  if (!contact || typeof contact !== "object") return false;
  return contact.unsubscribed === false && hasConfirmedMarker(contact);
}

function createResendError(op, status) {
  const err = new Error(`Resend ${op} failed with status ${status}`);
  err.op = op;
  err.status = status;
  return err;
}

function parseRetryAfterMs(headerValue, defaultMs = 1000, maxMs = 2000) {
  if (headerValue !== null && headerValue !== undefined && String(headerValue).trim() !== "") {
    const seconds = Number(String(headerValue).trim());
    if (Number.isFinite(seconds) && seconds >= 0) {
      return Math.min(Math.round(seconds * 1000), maxMs);
    }
  }
  return defaultMs;
}

export function createResendClient({
  apiKey,
  audienceId,
  fetchImpl = globalThis.fetch,
  baseUrl = RESEND_BASE_URL,
  retryOn429 = false,
} = {}) {
  if (!apiKey) {
    throw new Error("Missing RESEND_API_KEY configuration");
  }

  const normalizedBase = baseUrl.replace(/\/+$/, "");
  const contactsPath = `${normalizedBase}/contacts`;

  async function request(url, options = {}) {
    const fetchOptions = {
      ...options,
      headers: {
        Authorization: `Bearer ${apiKey}`,
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {}),
      },
    };
    const res = await fetchImpl(url, fetchOptions);
    if (res.status === 429 && retryOn429) {
      const retryAfter = res.headers?.get?.("Retry-After");
      const delayMs = parseRetryAfterMs(retryAfter);
      if (delayMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }
      return fetchImpl(url, fetchOptions);
    }
    return res;
  }

  return {
    async getContact(email) {
      const url = `${contactsPath}/${encodeURIComponent(email)}`;
      const res = await request(url, { method: "GET" });
      if (res.status === 404) {
        return null;
      }
      if (!res.ok) {
        throw createResendError("getContact", res.status);
      }
      const data = await res.json();
      return data && typeof data.data === "object" ? data.data : data;
    },

    async createContact({
      email,
      unsubscribed = true,
      first_name = UNCONFIRMED_MARKER,
      last_name,
      segmentId,
      segments,
    }) {
      const payload = {
        email,
        unsubscribed: Boolean(unsubscribed),
        first_name,
      };
      if (last_name !== undefined) {
        payload.last_name = last_name;
      }
      const resolvedSegmentId =
        segmentId !== undefined ? segmentId : audienceId;
      if (Array.isArray(segments) && segments.length > 0) {
        payload.segments = segments.map((s) =>
          typeof s === "string" ? { id: s } : { id: s.id }
        );
      } else if (resolvedSegmentId) {
        payload.segments = [{ id: resolvedSegmentId }];
      }
      const res = await request(contactsPath, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        throw createResendError("createContact", res.status);
      }
      const data = await res.json();
      return data && typeof data.data === "object" ? data.data : data;
    },

    async updateContact(emailOrId, updates) {
      const url = `${contactsPath}/${encodeURIComponent(emailOrId)}`;
      const res = await request(url, {
        method: "PATCH",
        body: JSON.stringify(updates),
      });
      if (!res.ok) {
        throw createResendError("updateContact", res.status);
      }
      const data = await res.json();
      return data && typeof data.data === "object" ? data.data : data;
    },

    async listContactSegments(emailOrId) {
      const url = `${contactsPath}/${encodeURIComponent(emailOrId)}/segments`;
      const res = await request(url, { method: "GET" });
      if (res.status === 404) {
        return [];
      }
      if (!res.ok) {
        throw createResendError("listContactSegments", res.status);
      }
      const body = await res.json();
      const items = Array.isArray(body?.data)
        ? body.data
        : Array.isArray(body)
          ? body
          : [];
      return items
        .map((item) => (typeof item === "string" ? item : item?.id))
        .filter(Boolean);
    },

    async addContactToSegment(emailOrId, segmentId = audienceId) {
      const url = `${contactsPath}/${encodeURIComponent(emailOrId)}/segments/${encodeURIComponent(segmentId)}`;
      const res = await request(url, { method: "POST" });
      if (!res.ok) {
        throw createResendError("addContactToSegment", res.status);
      }
      const data = await res.json();
      return data && typeof data.data === "object" ? data.data : data;
    },

    async removeContactFromSegment(emailOrId, segmentId = audienceId) {
      const url = `${contactsPath}/${encodeURIComponent(emailOrId)}/segments/${encodeURIComponent(segmentId)}`;
      const res = await request(url, { method: "DELETE" });
      if (res.status === 404) {
        return null;
      }
      if (!res.ok) {
        throw createResendError("removeContactFromSegment", res.status);
      }
      const text = await res.text();
      if (!text) {
        return null;
      }
      const data = JSON.parse(text);
      return data && typeof data.data === "object" ? data.data : data;
    },

    async sendEmail({ from, to, subject, text, html, headers }) {
      const payload = {
        from,
        to: Array.isArray(to) ? to : [to],
        subject,
        text,
        html,
      };
      if (headers) {
        payload.headers = headers;
      }
      const res = await request(`${normalizedBase}/emails`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        throw createResendError("sendEmail", res.status);
      }
      return res.json();
    },
  };
}
