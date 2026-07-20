const http = require("http");
const url = require("url");
const fs = require("fs");
const path = require("path");

const DIST_DIR = path.join(__dirname, "dist");
const BACKEND_URL = "http://backend:8000";

const CONTENT_TYPES = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "application/javascript",
  ".json": "application/json",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
};

function proxyToBackend(req, res) {
  const parsedUrl = url.parse(req.url);
  const options = {
    hostname: "backend",
    port: 8000,
    path: parsedUrl.path,
    method: req.method,
    headers: req.headers,
  };

  // Remove hop-by-hop headers
  delete options.headers.host;
  delete options.headers.connection;
  delete options.headers["transfer-encoding"];

  const proxyReq = http.request(options, (proxyRes) => {
    res.writeHead(proxyRes.statusCode, proxyRes.headers);
    proxyRes.pipe(res, { end: true });
  });

  proxyReq.on("error", () => {
    res.writeHead(502, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "Backend unavailable" }));
  });

  // Pipe request body for POST/PUT/PATCH
  req.pipe(proxyReq, { end: true });
}

function serveStatic(req, res) {
  const pathname = url.parse(req.url).pathname || "/";
  const file = pathname === "/" ? "index.html" : pathname;
  const filePath = path.join(DIST_DIR, file);

  try {
    const content = fs.readFileSync(filePath);
    const ext = path.extname(filePath);
    const contentType = CONTENT_TYPES[ext] || "application/octet-stream";
    res.writeHead(200, { "Content-Type": contentType });
    res.end(content);
  } catch {
    // SPA fallback: serve index.html for any route
    const index = fs.readFileSync(path.join(DIST_DIR, "index.html"));
    res.writeHead(200, { "Content-Type": "text/html" });
    res.end(index);
  }
}

http
  .createServer((req, res) => {
    const pathname = url.parse(req.url).pathname || "/";

    // Proxy /api/* requests to backend
    if (pathname.startsWith("/api")) {
      // Block direct browser navigation (Sec-Fetch-Dest: document)
      // Allow programmatic fetch/axios calls (Sec-Fetch-Dest: empty)
      const secFetchDest = req.headers['sec-fetch-dest'];
      if (secFetchDest === 'document') {
        res.writeHead(403, { "Content-Type": "application/json" });
        return res.end(JSON.stringify({ error: "Forbidden" }));
      }
      return proxyToBackend(req, res);
    }

    // Serve static files for all other routes
    serveStatic(req, res);
  })
  .listen(80, () => console.log("Serving on port 80"));