import satori from "satori";
import { Resvg } from "@resvg/resvg-js";
import React from "react";
import { getFonts } from "./fonts";
import { CANVAS } from "./templates/shared";

import Hook, { HookProps } from "./templates/hook";
import Reveal, { RevealProps } from "./templates/reveal";
import Narrative, { NarrativeProps } from "./templates/narrative";
import Cta, { CtaProps } from "./templates/cta";
import Canvas, { CanvasProps } from "./templates/canvas";

type TemplateName = "hook" | "reveal" | "narrative" | "cta" | "canvas";

type PropsMap = {
  hook: HookProps;
  reveal: RevealProps;
  narrative: NarrativeProps;
  cta: CtaProps;
  canvas: CanvasProps;
};

function buildElement(template: TemplateName, props: Record<string, unknown>): React.ReactElement {
  switch (template) {
    case "hook":
      return React.createElement(Hook, props as unknown as HookProps);
    case "reveal":
      return React.createElement(Reveal, props as unknown as RevealProps);
    case "narrative":
      return React.createElement(Narrative, props as unknown as NarrativeProps);
    case "cta":
      return React.createElement(Cta, props as unknown as CtaProps);
    case "canvas":
      return React.createElement(Canvas, props as unknown as CanvasProps);
    default: {
      const _: never = template;
      throw new Error(`Unknown template: ${template}`);
    }
  }
}

export async function renderFrame(
  template: TemplateName,
  props: Record<string, unknown>
): Promise<Buffer> {
  const fonts = getFonts();
  const element = buildElement(template, props);

  const svg = await satori(element, {
    width: CANVAS.w,
    height: CANVAS.h,
    fonts: fonts.map((f) => ({
      name: f.name,
      data: f.data,
      weight: f.weight,
      style: f.style,
    })),
  });

  const resvg = new Resvg(svg, {
    fitTo: { mode: "width", value: CANVAS.w },
  });
  const pngData = resvg.render();
  return pngData.asPng();
}

export { TemplateName };
