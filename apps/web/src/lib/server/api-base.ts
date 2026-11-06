/**
 * Server-only API target resolution for checkout route handlers.
 *
 * Browser requests use the same-origin `/api` rewrite. Checkout callbacks run
 * on the Next.js server, so they need an explicit private API origin when the
 * web app is hosted. Never expose this value with a NEXT_PUBLIC_ prefix.
 */
const LOCAL_API = "http://127.0.0.1:8000";

function isLocalHttp(url: URL) {
  return url.protocol === "http:" && (url.hostname === "localhost" || url.hostname === "127.0.0.1");
}

export function internalApiBase(): string | null {
  const configured = process.env.INTENTRA_API_URL;
  // A local default is useful for the documented single-machine topology, but
  // must never accidentally become a Vercel Serverless target.
  const value = configured ?? (process.env.VERCEL ? undefined : LOCAL_API);
  if (!value) return null;

  try {
    const parsed = new URL(value);
    if (
      !parsed.hostname ||
      parsed.username ||
      parsed.password ||
      parsed.search ||
      parsed.hash ||
      (parsed.protocol !== "https:" && !isLocalHttp(parsed))
    ) return null;
    return parsed.toString().replace(/\/$/, "");
  } catch {
    return null;
  }
}
