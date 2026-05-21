import express, { Request, Response } from "express";
import type { Server } from "node:http";
import { renderFrame, TemplateName } from "./render";
import { getFontNames } from "./fonts";

const app = express();
app.use(express.json({ limit: "4mb" }));

const PORT = parseInt(process.env["PORT"] ?? "3001", 10);

async function reportListenError(err: NodeJS.ErrnoException): Promise<never> {
  if (err.code === "EADDRINUSE") {
    let reuseHint = `Another process is already listening on :${PORT}.`;

    try {
      const resp = await fetch(`http://127.0.0.1:${PORT}/health`);
      if (resp.ok) {
        const body = (await resp.json()) as { status?: string };
        if (body.status === "ok") {
          reuseHint = [
            `A healthy Satori service is already running on :${PORT}.`,
            "Reuse that process, stop it before restarting, or pick another port.",
            `If you pick another port, start with PORT=<port> and set SATORI_URL=http://localhost:<port>.`,
          ].join(" ");
        }
      }
    } catch {
      // Keep the generic message when the existing listener is not this service.
    }

    console.error(`[satori-service] FATAL: ${reuseHint}`);
    process.exit(1);
  }

  console.error("[satori-service] FATAL:", err);
  process.exit(1);
}

// GET /health
app.get("/health", (_req: Request, res: Response) => {
  let satoriVersion = "unknown";
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    satoriVersion = require("satori/package.json").version as string;
  } catch {}

  let fontNames: string[] = [];
  try {
    fontNames = getFontNames();
  } catch (err) {
    res.status(503).json({
      status: "error",
      message: String(err),
      satori: satoriVersion,
      fonts: [],
    });
    return;
  }

  res.json({
    status: "ok",
    satori: satoriVersion,
    fonts: fontNames,
  });
});

// POST /render
app.post("/render", async (req: Request, res: Response) => {
  const { template, props } = req.body as {
    template: TemplateName;
    props: Record<string, unknown>;
  };

  if (!template || !props) {
    res.status(400).json({ error: "Missing 'template' or 'props' in request body." });
    return;
  }

  const validTemplates: TemplateName[] = ["hook", "reveal", "narrative", "cta", "canvas"];
  if (!validTemplates.includes(template)) {
    res.status(400).json({
      error: `Unknown template '${template}'. Must be one of: ${validTemplates.join(", ")}.`,
    });
    return;
  }

  try {
    const png = await renderFrame(template, props);
    res.set("Content-Type", "image/png");
    res.set("Content-Length", String(png.length));
    res.send(png);
  } catch (err) {
    console.error(`[satori-service] render error for template=${template}:`, err);
    res.status(500).json({ error: String(err) });
  }
});

// Eagerly load fonts to fail fast if they're missing.
try {
  getFontNames();
} catch (err) {
  console.error(`[satori-service] FATAL: ${err}`);
  process.exit(1);
}

const server: Server = app.listen(PORT);

server.on("listening", () => {
  console.log(`[satori-service] listening on :${PORT}`);
});

server.on("error", (err: NodeJS.ErrnoException) => {
  void reportListenError(err);
});
