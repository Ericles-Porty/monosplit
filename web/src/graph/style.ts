import type { StylesheetJson } from "cytoscape";

import type { Palette } from "../theme/Theme";

/**
 * Cytoscape stylesheet for the current theme. Marks follow the dataviz specs: filled
 * nodes with a 2px surface ring, labels in text colours (never the service colour),
 * recessive edges inside services, darker edges between services.
 */
export function buildStyle(p: Palette): StylesheetJson {
  const style = [
    {
      selector: "core",
      style: { "active-bg-opacity": 0, "selection-box-opacity": 0 },
    },
    {
      selector: "node.cls",
      style: {
        width: 22,
        height: 22,
        "background-color": "data(color)",
        "border-width": 2,
        "border-color": p.surface,
        label: "data(label)",
        "font-family": p.font,
        "font-size": 11,
        color: p.text,
        "text-valign": "bottom",
        "text-halign": "center",
        "text-margin-y": 3,
        "text-background-color": p.surface,
        "text-background-opacity": 0.8,
        "text-background-padding": "1px",
        "text-background-shape": "round-rectangle",
        "min-zoomed-font-size": 5,
        "overlay-opacity": 0,
      },
    },
    {
      selector: "node.cls.iface",
      style: { "border-width": 3, "border-color": p.ring },
    },
    {
      selector: "node.svc",
      style: {
        shape: "round-rectangle",
        "corner-radius": 8,
        "background-color": "data(color)",
        "background-opacity": 0.1,
        "border-width": 1.5,
        "border-color": "data(color)",
        label: "data(label)",
        "font-family": p.font,
        "font-size": 13,
        "font-weight": 600,
        color: p.text,
        "text-valign": "top",
        "text-halign": "center",
        "text-margin-y": -4,
        padding: "14px",
        "overlay-opacity": 0,
      },
    },
    {
      selector: "node.svc-collapsed",
      style: {
        shape: "round-rectangle",
        "corner-radius": 10,
        width: "mapData(size, 1, 30, 48, 120)",
        height: 34,
        "background-color": "data(color)",
        "border-width": 2,
        "border-color": p.surface,
        label: "data(label)",
        "font-family": p.font,
        "font-size": 11,
        "font-weight": 600,
        color: p.text,
        "text-valign": "bottom",
        "text-margin-y": 4,
        "text-background-color": p.surface,
        "text-background-opacity": 0.8,
        "text-background-padding": "2px",
        "overlay-opacity": 0,
      },
    },
    {
      selector: "edge",
      style: {
        width: "data(width)",
        "curve-style": "bezier",
        "line-color": p.edgeIntra,
        "target-arrow-color": p.edgeIntra,
        "target-arrow-shape": "triangle",
        "arrow-scale": 0.6,
        opacity: 0.85,
        "overlay-opacity": 0,
      },
    },
    {
      selector: "edge.cross",
      style: { "line-color": p.edgeCross, "target-arrow-color": p.edgeCross, opacity: 0.75, "arrow-scale": 0.7 },
    },
    {
      selector: "edge[label != '']",
      style: {
        label: "data(label)",
        "font-family": p.font,
        "font-size": 10,
        color: p.text2,
        "text-background-color": p.surface,
        "text-background-opacity": 0.85,
        "text-background-padding": "1px",
      },
    },
    { selector: ".faded", style: { opacity: 0.14 } },
    { selector: "edge.lit", style: { opacity: 1 } },
    {
      selector: "node.lit",
      style: {
        "underlay-color": p.accent,
        "underlay-opacity": 0.28,
        "underlay-padding": 6,
        "underlay-shape": "ellipse",
      },
    },
    {
      selector: "node.picked",
      style: {
        "underlay-color": p.accent,
        "underlay-opacity": 0.45,
        "underlay-padding": 7,
        "underlay-shape": "ellipse",
      },
    },
    {
      selector: "node.changed",
      style: {
        "outline-width": 2,
        "outline-color": p.accent,
        "outline-style": "dashed",
        "outline-offset": 3,
      },
    },
  ];
  return style as unknown as StylesheetJson;
}
