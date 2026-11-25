/// <reference types="vite/client" />

declare module "cytoscape-fcose";

interface Window {
  /** Set by `monosplit web export`: read data/<path>.json instead of calling /api. */
  MONOSPLIT_STATIC?: boolean;
}
