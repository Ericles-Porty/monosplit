// Screenshots of the web interface for visual checks, plus the browser's console errors.
//
//   npm run screenshot                                   # http://127.0.0.1:8765/, writes screenshots/
//   node scripts/screenshot.mjs http://127.0.0.1:8000/ out
//
// The server must be running (uv run python -m monosplit web serve), or point the URL at a
// static export served by any web server. playwright-core downloads no browser: it uses
// MONOSPLIT_BROWSER, or the installed Microsoft Edge or Google Chrome.
import { existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

import { chromium } from "playwright-core";

const base = process.argv[2] ?? "http://127.0.0.1:8765/";
const out = process.argv[3] ?? "screenshots";
mkdirSync(out, { recursive: true });

const executablePath = [
  process.env.MONOSPLIT_BROWSER,
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "/usr/bin/chromium",
  "/usr/bin/google-chrome",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
].find((path) => path && existsSync(path));
if (!executablePath) throw new Error("No Chromium-based browser found; set MONOSPLIT_BROWSER");

// Study shown in the views (experiment/app/profile); MONOSPLIT_STUDY picks another one.
const STUDY = process.env.MONOSPLIT_STUDY ?? "dry-run/jpetstore/fake";
const [EXPERIMENT, , PROFILE] = STUDY.split("/");
const views = [
  { name: "overview", hash: "#/overview", wait: "table.data" },
  { name: "fixed", study: true, hash: `#/decompositions?study=${STUDY}`, wait: ".pane canvas", hover: "org.mybatis.jpetstore.domain.Cart" },
  { name: "grouped", study: true, hash: `#/decompositions?study=${STUDY}&layout=grouped`, wait: ".pane canvas" },
  {
    name: "obfuscated-compare",
    study: true,
    hash: `#/decompositions?study=${STUDY}&variant=obfuscated&run=2&compare=1&labels=prompt`,
    wait: ".pane canvas",
  },
  { name: "results", study: true, hash: `#/results?set=${EXPERIMENT}/${PROFILE}`, wait: ".strip-figure svg" },
  { name: "results-obfuscated", study: true, hash: `#/results?set=${EXPERIMENT}/${PROFILE}&variant=obfuscated&ah=all`, wait: ".strip-figure svg" },
  { name: "wiki-overview", hash: "#/wiki", wait: ".wiki-content h1" },
  { name: "wiki-metrics", hash: "#/wiki?page=metrics", wait: ".wiki-content .katex" },
  // Local version only (the static site has no configuration or execution pages).
  { name: "config-profiles", hash: "#/config?tab=profiles", wait: "table.data", local: true, click: "table.data tbody tr:nth-child(2) .actions-cell button" },
  { name: "config-experiments", hash: "#/config?tab=experiments", wait: "table.data", local: true, click: "table.data tbody tr:last-child .actions-cell button" },
  { name: "config-prompts", hash: "#/config?tab=prompts", wait: "table.data", local: true },
  { name: "config-apps", hash: "#/config?tab=apps", wait: "table.data", local: true },
  { name: "execution", hash: "#/execution", wait: ".form", local: true, dryRun: true },
  // The Data page is only read here; no view saves or deletes anything.
  { name: "data-studies", study: true, hash: `#/data?tab=studies&study=${STUDY}`, wait: "table.data", local: true },
  { name: "data-attempts", study: true, hash: `#/data?tab=attempts&experiment=${EXPERIMENT}&attempt=${STUDY}/obfuscated/1`, wait: "pre.output", local: true },
  { name: "data-edges", hash: "#/data?tab=edges&app=jpetstore", wait: "table.edge-check", local: true },
  { name: "data-audit", hash: "#/data?tab=audit", wait: "table.data, p.empty", local: true },
];

// Views of a study are skipped when the API lists no stored study (an empty main database).
const index = await fetch(new URL("api/index", base)).then((r) => (r.ok ? r.json() : null)).catch(() => null);
const skipStudies = Array.isArray(index?.studies) && index.studies.length === 0;
if (skipStudies) console.log(`No stored study: skipping the views of ${STUDY}`);

const browser = await chromium.launch({ executablePath, headless: true });
const problems = [];
for (const [theme, lang] of [
  ["light", "pt"],
  ["dark", "en"],
]) {
  const context = await browser.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });
  await context.addInitScript(
    ([t, l]) => {
      localStorage.setItem("monosplit.theme", t);
      localStorage.setItem("monosplit.lang", l);
      localStorage.setItem("monosplit.debug", "1");
    },
    [theme, lang],
  );
  const page = await context.newPage();
  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") problems.push(`[${theme}] console.${message.type()}: ${message.text()}`);
  });
  page.on("pageerror", (error) => problems.push(`[${theme}] page error: ${error.message}`));
  page.on("response", (response) => {
    if (response.status() >= 400) problems.push(`[${theme}] HTTP ${response.status()} ${response.url()}`);
  });

  for (const view of views) {
    await page.goto(new URL(view.hash, base).toString());
    if (view.study && skipStudies) continue;
    if (view.local && (await page.evaluate(() => window.MONOSPLIT_STATIC === true))) continue;
    await page.waitForSelector(view.wait, { timeout: 20000 });
    await page.waitForTimeout(1500);
    if (view.click) {
      await page.click(view.click);
      await page.waitForTimeout(500);
    }
    if (view.dryRun && theme === "light") {
      // Start the dry run (fake client, no cost) and wait until the job is done.
      await page.getByRole("button", { name: /ensaio a seco|dry run/i }).last().click();
      await page.waitForSelector(".job .chip.succeeded, .job .chip.failed", { timeout: 120000 });
      await page.waitForTimeout(800);
    }
    const file = join(out, `${view.name}-${theme}.png`);
    await page.screenshot({ path: file, fullPage: true });
    console.log(file);

    if (view.hover) {
      const point = await page.evaluate((id) => {
        const cy = window.__monosplitCy?.["pane-0"];
        const node = cy?.getElementById(id);
        if (!node || node.empty()) return null;
        const box = cy.container().getBoundingClientRect();
        const p = node.renderedPosition();
        return { x: box.left + p.x, y: box.top + p.y };
      }, view.hover);
      if (point) {
        await page.mouse.move(point.x, point.y);
        await page.waitForTimeout(400);
        const hoverFile = join(out, `${view.name}-hover-${theme}.png`);
        await page.screenshot({ path: hoverFile, clip: { x: 0, y: 0, width: 1600, height: 1000 } });
        console.log(hoverFile);
      } else {
        problems.push(`[${theme}] could not find node ${view.hover} to hover`);
      }
    }
  }
  await context.close();
}
await browser.close();
console.log(problems.length ? `\n${problems.length} problem(s):\n${problems.join("\n")}` : "\nNo console errors, page errors or failed requests.");
