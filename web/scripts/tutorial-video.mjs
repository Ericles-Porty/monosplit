// Records a tutorial video of the web interface, with captions in Portuguese.
//
//   node scripts/tutorial-video.mjs                       # http://127.0.0.1:8765/, writes ../work/video/
//   node scripts/tutorial-video.mjs <url> <out dir> --shots
//
// The server must be running (uv run python -m monosplit web serve) with the final experiment in
// the database. The video (WebM) is recorded by Playwright, which needs its ffmpeg build
// (`npx playwright-core install ffmpeg`); the browser is the installed Edge or Chrome.
// --shots also saves a screenshot at every caption, to check the video without playing it.
//
// The tour only reads: it opens editors without saving, shows the cost estimate without starting
// a paid job, and runs only the dry run (fake client, database monosplit_dry_run).
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { join, resolve } from "node:path";

import { chromium } from "playwright-core";

const args = process.argv.slice(2).filter((a) => !a.startsWith("--"));
const base = args[0] ?? "http://127.0.0.1:8765/";
const out = resolve(args[1] ?? "../work/video");
const shots = process.argv.includes("--shots");
mkdirSync(out, { recursive: true });
const shotDir = join(out, "shots");
if (shots) mkdirSync(shotDir, { recursive: true });

const executablePath = [
  process.env.MONOSPLIT_BROWSER,
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "/usr/bin/chromium",
  "/usr/bin/google-chrome",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
].find((path) => path && existsSync(path));
if (!executablePath) throw new Error("No Chromium-based browser found; set MONOSPLIT_BROWSER");

const W = 1600;
const H = 1000;
const STUDY = "final/jpetstore/gpt-6.1-sol-high";

// ------------------------------------------------------------------ overlay (runs in the page)

function installOverlay() {
  const css = `
  body { padding-bottom: 260px !important; }
  #tut-root, #tut-root * { box-sizing: border-box; pointer-events: none; }
  #tut-caption { position: fixed; left: 50%; bottom: 26px; transform: translateX(-50%); z-index: 2147483646;
    width: min(1220px, calc(100vw - 80px)); background: rgba(15, 23, 42, 0.93); color: #f8fafc;
    font: 500 24px/1.42 "Segoe UI", system-ui, sans-serif; padding: 16px 28px 18px; border-radius: 14px;
    box-shadow: 0 10px 30px rgba(0,0,0,.35); opacity: 0; transition: opacity .35s ease; }
  #tut-caption.on { opacity: 1; }
  #tut-caption .ch { display: block; font: 700 14px/1.2 "Segoe UI", system-ui, sans-serif; letter-spacing: .08em;
    text-transform: uppercase; color: #a5b4fc; margin-bottom: 6px; }
  #tut-caption code { font: 600 21px/1.3 Consolas, monospace; color: #fde68a; }
  #tut-cursor { position: fixed; left: 0; top: 0; z-index: 2147483647; width: 28px; height: 28px;
    transform: translate(-100px, -100px); transition: none; filter: drop-shadow(0 2px 3px rgba(0,0,0,.45)); }
  .tut-ripple { position: fixed; z-index: 2147483645; width: 46px; height: 46px; margin: -23px 0 0 -23px;
    border-radius: 50%; border: 3px solid #f59e0b; animation: tut-ripple .6s ease-out forwards; }
  @keyframes tut-ripple { from { transform: scale(.3); opacity: 1; } to { transform: scale(1.4); opacity: 0; } }
  #tut-mark { position: fixed; z-index: 2147483644; border: 3px solid #f59e0b; border-radius: 10px;
    box-shadow: 0 0 0 9999px rgba(15, 23, 42, 0.16); opacity: 0; transition: opacity .3s ease, left .3s, top .3s, width .3s, height .3s; }
  #tut-mark.on { opacity: 1; }
  #tut-card { position: fixed; inset: 0; z-index: 2147483643; display: flex; flex-direction: column; justify-content: center;
    padding: 0 140px; background: linear-gradient(135deg, #1e1b4b, #0f172a 60%); color: #f8fafc; opacity: 0; transition: opacity .5s ease;
    font-family: "Segoe UI", system-ui, sans-serif; }
  #tut-card.on { opacity: 1; }
  #tut-card h1 { font-size: 64px; margin: 0 0 12px; font-weight: 700; }
  #tut-card h2 { font-size: 30px; margin: 0 0 40px; font-weight: 400; color: #c7d2fe; }
  #tut-card ul { list-style: none; padding: 0; margin: 0; }
  #tut-card li { font-size: 25px; line-height: 1.5; margin: 6px 0; color: #e2e8f0; }
  #tut-card li code { font: 600 23px Consolas, monospace; color: #fde68a; }
  `;
  const make = () => {
    if (document.getElementById("tut-root") || !document.body) return;
    const root = document.createElement("div");
    root.id = "tut-root";
    root.innerHTML = `<style>${css}</style>
      <div id="tut-card"></div><div id="tut-mark"></div><div id="tut-caption"></div>
      <svg id="tut-cursor" viewBox="0 0 24 24"><path d="M4 2 L4 20 L9 15.5 L12.5 22 L15.5 20.6 L12.2 14.3 L19 14.3 Z"
        fill="#ffffff" stroke="#111827" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
    document.body.appendChild(root);
    const cursor = document.getElementById("tut-cursor");
    const at = window.__tutMouse || { x: -100, y: -100 };
    cursor.style.transform = `translate(${at.x - 4}px, ${at.y - 2}px)`;
    document.addEventListener("mousemove", (e) => {
      window.__tutMouse = { x: e.clientX, y: e.clientY };
      cursor.style.transform = `translate(${e.clientX - 4}px, ${e.clientY - 2}px)`;
    }, true);
  };
  window.__tut = {
    caption(chapter, html) {
      make();
      const box = document.getElementById("tut-caption");
      box.innerHTML = (chapter ? `<span class="ch">${chapter}</span>` : "") + html;
      box.classList.add("on");
    },
    hide() { make(); document.getElementById("tut-caption").classList.remove("on"); },
    ripple(x, y) {
      make();
      const r = document.createElement("div");
      r.className = "tut-ripple";
      r.style.left = `${x}px`;
      r.style.top = `${y}px`;
      document.getElementById("tut-root").appendChild(r);
      setTimeout(() => r.remove(), 700);
    },
    mark(box) {
      make();
      const m = document.getElementById("tut-mark");
      Object.assign(m.style, { left: `${box.x}px`, top: `${box.y}px`, width: `${box.width}px`, height: `${box.height}px` });
      m.classList.add("on");
    },
    unmark() { make(); document.getElementById("tut-mark").classList.remove("on"); },
    card(html) { make(); const c = document.getElementById("tut-card"); c.innerHTML = html; c.classList.add("on"); },
    uncard() { make(); document.getElementById("tut-card").classList.remove("on"); },
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", make);
  else make();
}

// ------------------------------------------------------------------ helpers (run in Node)

const browser = await chromium.launch({ executablePath, headless: true });
const tmpVideo = join(out, "raw");
rmSync(tmpVideo, { recursive: true, force: true });
const context = await browser.newContext({
  viewport: { width: W, height: H },
  deviceScaleFactor: 1,
  recordVideo: { dir: tmpVideo, size: { width: W, height: H } },
});
await context.addInitScript(() => {
  localStorage.setItem("monosplit.theme", "light");
  localStorage.setItem("monosplit.lang", "pt");
  localStorage.setItem("monosplit.debug", "1");
});
await context.addInitScript(installOverlay);
const page = await context.newPage();
const problems = [];
page.on("pageerror", (error) => problems.push(`page error: ${error.message}`));
page.on("response", (response) => {
  if (response.status() >= 400) problems.push(`HTTP ${response.status()} ${response.url()}`);
});

const wait = (ms) => page.waitForTimeout(ms);
let mouse = { x: W / 2, y: H / 2 };
let shotCount = 0;
const readMs = (html) => Math.max(3800, 1400 + html.replace(/<[^>]+>/g, "").length * 55);

/** Shows a caption, runs `action` while it is on screen, and keeps it for its reading time. */
async function say(chapter, html, action) {
  await page.evaluate(([c, t]) => window.__tut.caption(c, t), [chapter, html]);
  const start = Date.now();
  if (action) await action();
  const left = readMs(html) - (Date.now() - start);
  if (left > 0) await wait(left);
  if (shots) await page.screenshot({ path: join(shotDir, `${String(++shotCount).padStart(3, "0")}.png`) });
}

async function smoothScrollTo(y) {
  await page.evaluate((top) => window.scrollTo({ top: Math.max(0, top), behavior: "smooth" }), y);
  await wait(1100);
}

/** Scrolls smoothly until the element sits near the top of the viewport (or fits). */
async function reveal(locator, top = 120) {
  await unmark();
  const box = await locator.boundingBox();
  if (!box) return;
  if (box.y >= 70 && box.y + Math.min(box.height, 400) <= H - 190) return;
  const scrollY = await page.evaluate(() => window.scrollY);
  await smoothScrollTo(scrollY + box.y - top);
}

async function scrollToHeading(text, top = 90) {
  const heading = page.locator("h1, h2, h3", { hasText: text }).first();
  await unmark();
  const scrollY = await page.evaluate(() => window.scrollY);
  const box = await heading.boundingBox();
  await smoothScrollTo(scrollY + box.y - top);
}

async function moveTo(locator, fx = 0.5, fy = 0.5) {
  await reveal(locator);
  const box = await locator.boundingBox();
  const x = box.x + box.width * fx;
  const y = box.y + box.height * fy;
  const steps = Math.max(10, Math.round(Math.hypot(x - mouse.x, y - mouse.y) / 22));
  await page.mouse.move(x, y, { steps });
  mouse = { x, y };
  return { x, y };
}

async function click(locator, pause = 700) {
  const { x, y } = await moveTo(locator);
  await wait(250);
  await page.evaluate(([px, py]) => window.__tut.ripple(px, py), [x, y]);
  await locator.click();
  await wait(pause);
}

async function choose(locator, value, pause = 900) {
  const { x, y } = await moveTo(locator);
  await wait(250);
  await page.evaluate(([px, py]) => window.__tut.ripple(px, py), [x, y]);
  await locator.selectOption(value);
  await wait(pause);
}

async function mark(locator, pad = 6) {
  locator = locator.first();
  if (!(await locator.count())) {
    problems.push(`no element to highlight: ${locator}`);
    return;
  }
  await reveal(locator);
  const box = await locator.boundingBox();
  if (!box) return;
  await page.evaluate((b) => window.__tut.mark(b), {
    x: box.x - pad, y: box.y - pad, width: box.width + 2 * pad, height: Math.min(box.height + 2 * pad, H - box.y - 150),
  });
  await wait(300);
}
const unmark = () => page.evaluate(() => window.__tut?.unmark());

/** A button or tab by its exact text (a string) or by a pattern. */
const btn = (text) =>
  page
    .locator("button, [role=tab]")
    .filter({ hasText: typeof text === "string" ? new RegExp("^\\s*" + text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\s*$") : text })
    .first();

async function nav(name, ready) {
  await unmark();
  await click(page.locator("header").getByRole("link", { name, exact: true }), 300);
  await page.waitForSelector(ready, { timeout: 30000 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await wait(1200);
}

// ------------------------------------------------------------------ the tour

await page.goto(new URL("#/overview", base).toString());
await page.waitForSelector("table.data", { timeout: 30000 });
await page.mouse.move(mouse.x, mouse.y);

// Opening card
await page.evaluate(() => window.__tut.card(`
  <h1>MonoSplit</h1>
  <h2>Como usar a ferramenta do experimento: LLM × agrupamento hierárquico × partição aleatória</h2>
  <ul>
    <li>1. Visão geral · 2. Configuração · 3. Execução · 4. Decomposições</li>
    <li>5. Resultados · 6. Dados · 7. Wiki</li>
    <li>Dados mostrados: experimento <code>final</code>, perfil <code>gpt-6.1-sol-high</code></li>
  </ul>`));
await wait(7000);
await page.evaluate(() => window.__tut.uncard());
await wait(800);

// 1. Overview
const C1 = "1 · Visão geral";
await say(C1, "A interface roda no seu computador: <code>uv run python -m monosplit web serve --open</code> abre o endereço 127.0.0.1:8765. O menu do topo leva às sete páginas.",
  () => mark(page.locator("header nav").first()));
await say(C1, "A Visão geral lista os estudos guardados no banco: cada linha é uma aplicação rodada com um perfil de LLM, nas variantes com nomes originais e ofuscados.",
  () => mark(page.locator("table.data").first()));
await say(C1, "Termos com sublinhado pontilhado têm explicação: basta passar o mouse. Aqui, “Aceitas” é o número de respostas do modelo que passaram na regra de aceitação.",
  async () => { await unmark(); await moveTo(page.locator("table.data th", { hasText: "Aceitas" }).first().locator("*").first()); await wait(1200); });
await say(C1, "Cada estudo tem atalhos para as suas decomposições e para os resultados. Mais abaixo ficam as aplicações, com o commit fixado e o tamanho do grafo de chamadas.",
  async () => { await mark(page.getByRole("link", { name: "Ver decomposições" }).first()); await wait(1500); await scrollToHeading("Aplicações e grafos"); await mark(page.locator("table.data").nth(1)); });
await smoothScrollTo(0);
await say(C1, "No canto direito ficam o idioma (PT/EN) e o tema claro ou escuro.",
  () => mark(page.locator("header button", { hasText: /^PT$/ }).locator("xpath=..")));

// 2. Configuration
const C2 = "2 · Configuração";
await nav("Configuração", "table.data");
await say(C2, "A Configuração guarda no banco tudo o que define um estudo, em quatro abas: perfis de LLM, prompts, aplicações e experimentos.",
  () => mark(btn("Perfis de LLM").locator("xpath=..")));
await say(C2, "Um perfil fixa provedor, modelo, opções da requisição e preços. O perfil do experimento final é o <code>gpt-6.1-sol-high</code>; a chave de API vem de uma variável de ambiente e nunca vai para o navegador.",
  () => mark(page.locator("table.data tbody tr", { hasText: "gpt-6.1-sol-high" }).first()));
await say(C2, "Ao editar, a página valida tudo antes de salvar. Quando um perfil já tem execuções, provedor, modelo e parâmetros ficam travados: para testar outro modelo, crie outro perfil.",
  async () => { await unmark(); await click(page.locator("table.data tbody tr", { hasText: "gpt-6.1-sol-high" }).locator("button", { hasText: /^Editar$/ })); await wait(800); });
await say(C2, "Para um modelo novo, comece por um dos modelos de perfil: OpenAI, Anthropic, Gemini, Ollama (modelos locais) ou um servidor compatível com a API da OpenAI.",
  () => mark(page.locator("table.data").nth(1)));
await say(C2, "Na aba Prompts está o texto exato enviado ao modelo. Uma versão nunca é sobrescrita: editar cria a próxima versão.",
  async () => { await unmark(); await click(btn("Prompts")); await wait(800); });
await say(C2, "Na aba Aplicações, cada monólito Java fica preso a um repositório e a um commit, com o tipo de build e as pastas do código.",
  async () => { await click(btn("Aplicações")); await wait(800); });
await say(C2, "Na aba Experimentos há uma configuração por aplicação. As quatro <code>final-*</code> compartilham o nome <code>final</code>, e por isso os Resultados juntam as quatro aplicações.",
  async () => { await click(btn("Experimentos")); await wait(600); await mark(page.locator("table.data tbody tr", { hasText: "final-jpetstore" }).first()); });
await say(C2, "Uma configuração fixa aplicação, execuções aceitas por variante, limite de repetições, semente mestra, prompt, perfil padrão, variante do AH e se a análise inferencial roda.",
  async () => { await unmark(); await click(page.locator("table.data tbody tr", { hasText: "final-jpetstore" }).locator("button", { hasText: /^Editar$/ })); await wait(800); });

// 3. Execution
const C3 = "3 · Execução";
await nav("Execução", "text=Rodar um estudo");
await say(C3, "A Execução roda as tarefas no servidor local, uma de cada vez. Primeiro, cada aplicação é clonada no commit fixado, compilada e lida com javap para extrair o grafo de chamadas.",
  () => mark(page.locator("table.data").first()));
await scrollToHeading("Rodar um estudo");
const selects = page.locator("select");
await say(C3, "Para rodar um estudo, escolha a configuração do experimento e o perfil de LLM.",
  async () => { await choose(selects.nth(0), "final-jpetstore"); await choose(selects.nth(1), "gpt-6.1-sol-high"); });
await say(C3, "Antes de começar, a página mostra a estimativa de tokens, tentativas e custo. Aqui o estudo já está completo (10 de 10 aceitas por variante), então não falta nada.",
  () => mark(page.locator("table.data", { has: page.locator("th", { hasText: "Faltam" }) })));
await say(C3, "“Iniciar” pede confirmação do custo. Se a tarefa for interrompida, basta iniciá-la de novo: ela continua de onde parou. Na linha de comando: <code>uv run python -m monosplit all --experiment final-jpetstore</code>.",
  () => mark(btn("Iniciar")));
await scrollToHeading("Ensaio a seco");
await say(C3, "O ensaio a seco roda o pipeline inteiro com um cliente falso, sem custo, num banco separado. Serve para conferir a instalação antes de gastar com um modelo de verdade.",
  () => click(btn("Rodar ensaio a seco"), 1200));
await scrollToHeading("Tarefas");
await say(C3, "A lista de tarefas mostra o progresso, o custo até agora e o registro de cada tentativa, atualizados a cada segundo.", async () => {
  await page.waitForSelector(".job .chip.succeeded, .job .chip.failed", { timeout: 180000 });
  const log = page.locator(".job summary").first();
  if (await log.count()) await click(log, 800);
  await reveal(page.locator(".job").first(), 160);
  await mark(page.locator(".job").first());
});

// 4. Decompositions
const C4 = "4 · Decomposições";
await nav("Decomposições", ".pane canvas");
await choose(page.locator("select").first(), STUDY, 1800);
await say(C4, "As Decomposições mostram o grafo de chamadas dividido em serviços. Aqui: JPetStore, execução 1, com o LLM, o AH e a partição aleatória lado a lado, todos com o mesmo K.",
  () => mark(page.locator(".pane").first()));
await say(C4, "Cada classe fica na mesma posição em todos os painéis, e a cor é o serviço. Anéis escuros marcam classes de interface; arestas escuras são chamadas entre serviços.", async () => {
  await unmark();
  const point = await page.evaluate((id) => {
    const cy = window.__monosplitCy?.["pane-0"];
    const node = cy?.getElementById(id);
    if (!node || node.empty()) return null;
    const box = cy.container().getBoundingClientRect();
    const p = node.renderedPosition();
    return { x: box.left + p.x, y: box.top + p.y };
  }, "org.mybatis.jpetstore.domain.Cart");
  if (point) { await page.mouse.move(point.x, point.y, { steps: 25 }); mouse = point; await wait(1500); }
});
await say(C4, "Os botões escolhem a execução. Execuções com a mesma letra devolveram a mesma partição: aqui, só a execução 7 (letra B) difere das outras.",
  () => click(btn(/^7\s*K=4/)));
await say(C4, "“Agrupado por serviço” desenha cada serviço como uma caixa; um duplo clique recolhe o serviço num nó só.",
  () => click(btn("Agrupado por serviço"), 1500));
await click(btn("Posições fixas"), 800);
await say(C4, "Na variante com nomes ofuscados, o modelo recebe as classes como C01, C02… “Comparar com” marca com contorno tracejado as classes que mudaram de serviço entre duas execuções e mostra o ARI.", async () => {
  await click(btn("Nomes ofuscados"), 1200);
  await click(btn(/^2\s*K=/), 1000);
  await choose(page.locator("select").nth(1), "1", 1200);
});
await say(C4, "“Nome no prompt” mostra os nomes exatamente como o modelo os recebeu.",
  () => click(btn("Nome no prompt"), 1200));
await scrollToHeading("Métricas dos painéis", 120);
await say(C4, "Abaixo dos painéis ficam as métricas de cada método (SM, IFN, ICP e NED), uma tabela com todas as classes e a resposta do modelo.", async () => {
  await mark(page.locator("table.data", { has: page.locator("th", { hasText: "SM" }) }).first());
  await wait(2500);
  const answer = page.locator("summary", { hasText: "Resposta do modelo" }).first();
  if (await answer.count()) { await unmark(); await click(answer, 900); await reveal(answer, 120); }
});

// 5. Results
const C5 = "5 · Resultados";
await nav("Resultados", ".strip-figure svg");
await say(C5, "Os Resultados juntam todas as aplicações de um experimento e perfil. Dá para trocar a variante e ver uma aplicação de cada vez.",
  () => mark(page.locator("select").first()));
await scrollToHeading("Execuções do LLM");
await say(C5, "Primeiro, as execuções: tentativas, aceitas, inválidas e o motivo, K de cada execução, tokens, tempo e custo. No experimento final, as 80 execuções foram aceitas de primeira.",
  () => mark(page.locator("table.data").first()));
await scrollToHeading("Métricas por método · acmeair");
await say(C5, "Nas métricas por método, cada ponto é uma execução aceita; a faixa clara vai do primeiro ao terceiro quartil e o traço marca a mediana.",
  () => mark(page.locator(".strip-figure").first()));
await say(C5, "Toda figura exporta para SVG e PNG, e toda tabela para CSV e LaTeX, prontas para o artigo.",
  () => mark(btn("SVG").first().locator("xpath=..")));
await scrollToHeading("Diferenças pareadas (LLM");
await say(C5, "As diferenças pareadas comparam o LLM com cada controle na mesma execução e com o mesmo K: d = LLM − controle, com a contagem de sinais.");
await scrollToHeading("Testes de hipótese");
await say(C5, "Os testes de hipótese seguem o roteiro: Shapiro-Wilk, Wilcoxon ou t pareado, ajuste de Holm sobre as oito comparações e delta de Cliff como tamanho de efeito.",
  () => mark(page.locator("table.data").filter({ has: page.locator("th", { hasText: /Holm/ }) }).first()));
await scrollToHeading("Critério de comparação");
await say(C5, "O critério de comparação dá o veredito para cada controle, condição por condição: o critério adotado, com a condição de NED, e, logo abaixo, o do roteiro.",
  () => mark(page.locator("h3", { hasText: "Critério de comparação" }).locator("xpath=following-sibling::*[2]")));
await scrollToHeading("Seleção da variante do AH");
await say(C5, "As seis variantes do AH são sempre medidas; o controle usado no experimento final é fixo na configuração: vizinhos com ligação completa.");
await scrollToHeading("Estabilidade entre execuções");
await say(C5, "A estabilidade mostra quantas partições diferentes o LLM devolveu em 10 execuções e o ARI entre elas (1 = mesma partição).");

// 6. Data
const C6 = "6 · Dados";
await nav("Dados", "table.data");
await say(C6, "A página Dados mostra o que está guardado no banco, que é o registro principal do estudo. Execuções, respostas e métricas são só leitura: são a evidência do experimento.",
  () => mark(btn("Estudos").locator("xpath=..")));
await say(C6, "Em Tentativas, cada linha é uma chamada ao modelo. Ao clicar, aparecem a resposta completa, o modelo informado pela API, os tokens e o horário.", async () => {
  await click(btn("Tentativas"), 1200);
  await click(page.locator("table.data tbody tr").first(), 1200);
});
await say(C6, "Em Conferência de arestas, o pesquisador confere no código-fonte uma amostra de arestas do grafo, com sim ou não e uma nota.",
  () => click(btn("Conferência de arestas"), 1200));
await say(C6, "O Registro de alterações guarda toda mudança de configuração ou de dados, com os valores antes e depois. Apagar um estudo exige digitar o nome e faz antes uma cópia do banco.",
  () => click(btn("Registro de alterações"), 1200));

// 7. Wiki
const C7 = "7 · Wiki";
await nav("Wiki", ".wiki-content h1");
await say(C7, "A Wiki explica o estudo página por página, em português e inglês: objetivo, projeto, variáveis e hipóteses, métricas, grafo, tratamento, controles, análise e a ferramenta.",
  () => mark(page.locator("h2", { hasText: "Páginas" }).first().locator("xpath=..")));
await say(C7, "A página de métricas traz a fórmula de cada métrica, com o que ela mede e a direção preferida.", async () => {
  await click(page.locator("a[href*='page=metrics']").first(), 1200);
  await scrollToHeading("Modularidade estrutural (SM)", 90);
});
await say(C7, "No fim, um exemplo calculado à mão, que os testes do código conferem valor por valor.",
  () => scrollToHeading("Exemplo calculado à mão", 90));

// Closing card
await unmark();
await page.evaluate(() => window.__tut.hide());
await wait(500);
await page.evaluate(() => window.__tut.card(`
  <h1>Resumo dos comandos</h1>
  <h2>Na pasta <code>experimento/</code></h2>
  <ul>
    <li><code>docker compose up -d</code> · inicia o MongoDB</li>
    <li><code>uv run python -m monosplit db restore dump</code> · carrega o pacote de replicação (clone novo)</li>
    <li><code>uv run python -m monosplit web serve --open</code> · abre a interface</li>
    <li><code>uv run python -m monosplit all --experiment final-jpetstore</code> · roda um estudo</li>
    <li><code>uv run python -m monosplit db dump dump</code> · grava a cópia do banco para o git</li>
    <li>Mais detalhes: README.md, pasta docs/ e a Wiki da interface</li>
  </ul>`));
await wait(10000);

const video = page.video();
await context.close();
const file = join(out, "monosplit-tutorial.webm");
await video.saveAs(file);
await video.delete();
rmSync(tmpVideo, { recursive: true, force: true });
await browser.close();
console.log(file);
console.log(problems.length ? `${problems.length} problem(s):\n${problems.join("\n")}` : "No page errors or failed requests.");
