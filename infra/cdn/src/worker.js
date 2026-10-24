// Serves LLM trace logs from R2 at https://terminalvalue.net/raw-traces/<session-id>/<sha256>.jsonl.gz
//
// The URL path is the R2 object key. Logs are content-addressed (named by the sha256 of
// their uncompressed bytes) and never change, so they are cached forever. Read-only.

const KEY = /^raw-traces\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\/([0-9a-f]{64})\.jsonl\.gz$/;

export default {
  async fetch(request, env, ctx) {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method Not Allowed\n", { status: 405, headers: { allow: "GET, HEAD" } });
    }
    const url = new URL(request.url);
    const key = url.pathname.slice(1);
    const match = KEY.exec(key);
    if (!match) {
      return new Response("Not Found\n", { status: 404 });
    }
    // Serve repeats from the edge cache so they cost no R2 operation. Query strings are
    // dropped from the cache key so they cannot be used to bypass it. 404s are not cached.
    const cacheKey = new Request(url.origin + url.pathname);
    if (request.method === "GET") {
      const cached = await caches.default.match(cacheKey);
      if (cached) return cached;
    }
    const object = request.method === "HEAD" ? await env.TRACES.head(key) : await env.TRACES.get(key);
    if (!object) {
      return new Response("Not Found\n", { status: 404 });
    }
    const headers = new Headers({
      "content-type": "application/gzip",
      "cache-control": "public, max-age=31536000, immutable",
      "access-control-allow-origin": "*",
      "x-log-sha256": match[1], // of the uncompressed JSONL, as in the commit trailer
      etag: object.httpEtag,
    });
    if (request.method === "HEAD") {
      return new Response(null, { headers });
    }
    const response = new Response(object.body, { headers });
    ctx.waitUntil(caches.default.put(cacheKey, response.clone()));
    return response;
  },
};
