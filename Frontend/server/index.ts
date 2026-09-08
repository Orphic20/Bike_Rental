import express from "express";
import fs from "node:fs";
import { createServer } from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// After `pnpm build` this file lives at dist/index.js and the client build at
// dist/public. Running the un-bundled source from server/ needs the sibling path.
const candidates = [
  path.resolve(__dirname, "public"),
  path.resolve(__dirname, "..", "dist", "public"),
];
const staticPath = candidates.find((candidate) => fs.existsSync(candidate));

if (!staticPath) {
  console.error("No client build found. Run `pnpm build` first.");
  process.exit(1);
}

const app = express();
app.use(express.static(staticPath));

// Single-page app: every unmatched path falls through to the client router.
app.get("*", (_req, res) => {
  res.sendFile(path.join(staticPath, "index.html"));
});

const port = Number(process.env.PORT) || 3000;
createServer(app).listen(port, () => {
  console.log(`Serving ${staticPath} on http://localhost:${port}/`);
});
