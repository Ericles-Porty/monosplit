// Files written by the Results page: CSV tables, SVG and PNG figures. Everything runs in the
// browser, so the static site exports the same files as the local version.

export function downloadBlob(name: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function downloadText(name: string, text: string, type: string): void {
  downloadBlob(name, new Blob([text], { type: `${type};charset=utf-8` }));
}

export type CsvValue = string | number | boolean | null | undefined;

/** RFC 4180 CSV. Numbers keep full precision with a decimal point, whatever the interface language. */
export function toCsv(columns: string[], rows: Record<string, CsvValue>[]): string {
  const cell = (value: CsvValue): string => {
    if (value === null || value === undefined) return "";
    const text = typeof value === "number" ? (Number.isFinite(value) ? String(value) : "") : String(value);
    return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  return [columns.join(","), ...rows.map((row) => columns.map((c) => cell(row[c])).join(","))].join("\r\n") + "\r\n";
}

/** File name safe on every system: letters, digits, dots, dashes and underscores. */
export function fileName(...parts: string[]): string {
  return parts
    .filter(Boolean)
    .join("_")
    .replace(/[^A-Za-z0-9._-]+/g, "-")
    .replace(/-+/g, "-");
}

export function svgDocument(markup: string): string {
  return `<?xml version="1.0" encoding="UTF-8"?>\n${markup}\n`;
}

/** Rasterises an SVG document at `scale` times its size, on its own background. */
export async function svgToPng(svg: string, width: number, height: number, scale = 2): Promise<Blob> {
  const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }));
  try {
    const image = new Image();
    image.decoding = "sync";
    image.src = url;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Canvas 2D is not available");
    context.scale(scale, scale);
    context.drawImage(image, 0, 0, width, height);
    return await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("PNG encoding failed"))), "image/png"),
    );
  } finally {
    URL.revokeObjectURL(url);
  }
}
