/**
 * Cloudflare Worker — Pure reverse proxy for Packs EV Tracker.
 *
 * Forwards ALL requests to the FastAPI backend server.
 * No KV, no npm, no wrangler needed — paste directly into CF dashboard.
 *
 * Setup:
 *   1. Go to Cloudflare Dashboard → Workers & Pages → your worker
 *   2. Edit Code → paste this file
 *   3. Settings → Variables → add BACKEND_URL = "http://YOUR_SERVER_IP:8000"
 *   4. Deploy
 */

export default {
  async fetch(request, env) {
    const BACKEND = env.BACKEND_URL || "http://localhost:8000";
    const url = new URL(request.url);

    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: corsHeaders(),
      });
    }

    // WebSocket upgrade
    if (request.headers.get("Upgrade") === "websocket") {
      return proxyWebSocket(request, BACKEND, url.pathname);
    }

    // Proxy everything to backend
    const targetUrl = BACKEND + url.pathname + url.search;

    const headers = new Headers(request.headers);
    headers.set("Host", new URL(BACKEND).host);
    headers.set("X-Forwarded-For", request.headers.get("CF-Connecting-IP") || "");
    headers.set("X-Forwarded-Proto", "https");
    headers.set("X-Real-IP", request.headers.get("CF-Connecting-IP") || "");

    try {
      const resp = await fetch(targetUrl, {
        method: request.method,
        headers: headers,
        body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
        redirect: "follow",
      });

      const responseHeaders = new Headers(resp.headers);
      // Add CORS headers
      responseHeaders.set("Access-Control-Allow-Origin", "*");
      responseHeaders.set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
      responseHeaders.set("Access-Control-Allow-Headers", "*");

      return new Response(resp.body, {
        status: resp.status,
        statusText: resp.statusText,
        headers: responseHeaders,
      });
    } catch (e) {
      return new Response(
        JSON.stringify({
          error: "Backend unavailable",
          detail: e.message,
          hint: "Make sure BACKEND_URL is set and your server is running",
        }),
        {
          status: 502,
          headers: { "Content-Type": "application/json", ...corsHeaders() },
        }
      );
    }
  },
};

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Max-Age": "86400",
  };
}

async function proxyWebSocket(request, backend, path) {
  const wsUrl = backend.replace("http://", "ws://").replace("https://", "wss://") + path;

  const [client, server] = Object.values(new WebSocketPair());
  server.accept();

  const backendWs = new WebSocket(wsUrl);

  backendWs.addEventListener("message", (e) => {
    try { server.send(e.data); } catch (_) {}
  });
  backendWs.addEventListener("close", () => {
    try { server.close(); } catch (_) {}
  });
  server.addEventListener("message", (e) => {
    try { backendWs.send(e.data); } catch (_) {}
  });
  server.addEventListener("close", () => {
    try { backendWs.close(); } catch (_) {}
  });

  return new Response(null, { status: 101, webSocket: client });
}
