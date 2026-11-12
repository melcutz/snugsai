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

export function createResendClient({
  apiKey,
  audienceId,
  fetchImpl = globalThis.fetch,
  baseUrl = RESEND_BASE_URL,
} = {}) {
  if (!apiKey) {
    throw new Error("Missing RESEND_API_KEY configuration");
  }

  const normalizedBase = baseUrl.replace(/\/+$/, "");
  const contactsPath = audienceId
    ? `${normalizedBase}/audiences/${encodeURIComponent(audienceId)}/contacts`
    : `${normalizedBase}/contacts`;

  async function request(url, options = {}) {
    const res = await fetchImpl(url, {
      ...options,
      headers: {
        Authorization: `Bearer ${apiKey}`,
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {}),
      },
    });
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
        throw new Error(`Resend getContact failed with status ${res.status}`);
      }
      const data = await res.json();
      return data && typeof data.data === "object" ? data.data : data;
    },

    async createContact({
      email,
      unsubscribed = true,
      first_name = UNCONFIRMED_MARKER,
      last_name,
    }) {
      const payload = {
        email,
        unsubscribed: Boolean(unsubscribed),
        first_name,
      };
      if (last_name !== undefined) {
        payload.last_name = last_name;
      }
      const res = await request(contactsPath, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        throw new Error(`Resend createContact failed with status ${res.status}`);
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
        throw new Error(`Resend updateContact failed with status ${res.status}`);
      }
      const data = await res.json();
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
        throw new Error(`Resend sendEmail failed with status ${res.status}`);
      }
      return res.json();
    },
  };
}
