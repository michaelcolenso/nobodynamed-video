import express, { Request, Response } from "express";
import { renderFrame, TemplateName } from "./render";
import { getFontNames } from "./fonts";
import satori from "satori";

const app = express();
app.use(express.json({ limit: "4mb" }));

const PORT = parseInt(process.env["PORT"] ?? "3001", 10);

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

  const validTemplates: TemplateName[] = ["hook", "reveal", "narrative", "cta"];
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

app.listen(PORT, () => {
  // Eagerly load fonts to fail fast if they're missing.
  try {
    getFontNames();
    console.log(`[satori-service] listening on :${PORT}`);
  } catch (err) {
    console.error(`[satori-service] FATAL: ${err}`);
    process.exit(1);
  }
});
