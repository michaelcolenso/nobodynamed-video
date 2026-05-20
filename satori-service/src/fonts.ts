import fs from "fs";
import path from "path";

export interface FontData {
  name: string;
  data: ArrayBuffer;
  weight: 400 | 900;
  style: "normal";
}

const FONT_DIR = path.resolve(process.env["FONT_DIR"] ?? path.join(__dirname, "../../fonts"));

function loadFont(filename: string, name: string, weight: 400 | 900): FontData {
  const p = path.join(FONT_DIR, filename);
  if (!fs.existsSync(p)) {
    throw new Error(
      `Font file not found: ${p}\n` +
        `Place SourceSerif4-Black.ttf and SourceSerif4-Regular.ttf in ${FONT_DIR}`
    );
  }
  const buf = fs.readFileSync(p);
  return {
    name,
    // Convert Node Buffer → ArrayBuffer
    data: buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer,
    weight,
    style: "normal",
  };
}

let _fonts: FontData[] | null = null;

export function getFonts(): FontData[] {
  if (_fonts) return _fonts;
  _fonts = [
    loadFont("SourceSerif4-Black.ttf", "Source Serif 4 Black", 900),
    loadFont("SourceSerif4-Regular.ttf", "Source Serif 4", 400),
  ];
  return _fonts;
}

export function getFontNames(): string[] {
  return getFonts().map((f) => f.name);
}
