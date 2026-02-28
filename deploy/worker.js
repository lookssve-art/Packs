/**
 * Cloudflare Worker — Reverse proxy for Packs EV Tracker.
 *
 * Serves the static frontend from Workers Sites (KV),
 * proxies /api/* and /ws/* to the FastAPI backend.
 */

import { getAssetFromKV } from "@cloudflare/kv-asset-handler";
import manifestJSON from "__STATIC_CONTENT_MANIFEST";

const assetManifest = JSON.parse(manifestJSON);

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // Proxy API requests to backend
    if (path.startsWith("/api/")) {
      return proxyToBackend(request, env, path);
    }

    // Proxy WebSocket requests to backend
    if (path.startsWith("/ws/")) {
      return proxyWebSocket(request, env, path);
    }

    // Serve static files
    try {
      // Try exact path first
      const response = await getAssetFromKV(
        { request, waitUntil: ctx.waitUntil.bind(ctx) },
        { ASSET_MANIFEST: assetManifest, ASSET_NAMESPACE: env.__STATIC_CONTENT }
      );
      return new Response(response.body, {
        ...response,
        headers: {
          ...Object.fromEntries(response.headers),
          "Cache-Control": "public, max-age=300",
        },
      });
    } catch (e) {
      // Fall back to index.html for SPA routing
      try {
        const indexRequest = new Request(
          new URL("/index.html", request.url).toString(),
          request
        );
        return await getAssetFromKV(
          { request: indexRequest, waitUntil: ctx.waitUntil.bind(ctx) },
          { ASSET_MANIFEST: assetManifest, ASSET_NAMESPACE: env.__STATIC_CONTENT }
        );
      } catch (e2) {
        return new Response("Not Found", { status: 404 });
      }
    }
  },
};

/**
 * Proxy an HTTP request to the FastAPI backend.
 */
async function proxyToBackend(request, env, path) {
  const backendUrl = env.BACKEND_URL || "http://localhost:8000";
  const url = new URL(request.url);
  const targetUrl = `${backendUrl}${path}${url.search}`;

  const headers = new Headers(request.headers);
  headers.set("X-Forwarded-For", request.headers.get("CF-Connecting-IP") || "");
  headers.set("X-Forwarded-Proto", "https");

  try {
    const response = await fetch(targetUrl, {
      method: request.method,
      headers: headers,
      body: request.method !== "GET" && request.method !== "HEAD"
        ? request.body
        : undefined,
    });

    const responseHeaders = new Headers(response.headers);
    responseHeaders.set("Access-Control-Allow-Origin", "*");
    responseHeaders.set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
    responseHeaders.set("Access-Control-Allow-Headers", "*");

    return new Response(response.body, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch (e) {
    return new Response(
      JSON.stringify({ error: "Backend unavailable", detail: e.message }),
      { status: 502, headers: { "Content-Type": "application/json" } }
    );
  }
}

/**
 * Proxy WebSocket connection to the backend.
 */
async function proxyWebSocket(request, env, path) {
  const upgradeHeader = request.headers.get("Upgrade");
  if (!upgradeHeader || upgradeHeader.toLowerCase() !== "websocket") {
    return new Response("Expected WebSocket", { status: 426 });
  }

  const backendUrl = (env.BACKEND_URL || "http://localhost:8000")
    .replace("http://", "ws://")
    .replace("https://", "wss://");
  const targetUrl = `${backendUrl}${path}`;

  // Cloudflare Workers WebSocket proxy
  const [client, server] = Object.values(new WebSocketPair());

  server.accept();

  // Connect to backend WebSocket
  const backendWs = new WebSocket(targetUrl);

  backendWs.addEventListener("message", (event) => {
    try {
      server.send(event.data);
    } catch (e) {
      // Client disconnected
    }
  });

  backendWs.addEventListener("close", () => {
    try { server.close(); } catch (e) { /* ignore */ }
  });

  server.addEventListener("message", (event) => {
    try {
      backendWs.send(event.data);
    } catch (e) {
      // Backend disconnected
    }
  });

  server.addEventListener("close", () => {
    try { backendWs.close(); } catch (e) { /* ignore */ }
  });

  return new Response(null, { status: 101, webSocket: client });
}
