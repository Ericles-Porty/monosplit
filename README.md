# monosplit

Instruments of a controlled *in vitro* experiment that compares decompositions of Java
monoliths into microservices produced by a general-purpose large language model (LLM)
with those of agglomerative hierarchical clustering (AH) and of a random partition with
the same number of services K. Dependent variables: structural modularity (SM), interface
number (IFN), inter-partition communication (ICP) and non-extreme distribution (NED).

Status: the final experiment was run on 2026-11-06 with OpenAI `gpt-6.1-sol` (profile
`gpt-6.1-sol-high`) on the four applications, with original and obfuscated class names:
80 accepted runs. A replication with a local open-weight model was piloted and dropped.
A second run of the same protocol, experiment `full` (2026-11-24, another master seed), is
also in the database; see `docs/decisions.md`.

- Decisions and their rationale, in the order they were taken: [docs/decisions.md](docs/decisions.md).
- Results of the final experiment, for the article (Portuguese): [docs/resultados.md](docs/resultados.md).
- Challenges met while building and running the study, for the article (Portuguese):
  [docs/desafios.md](docs/desafios.md).
- Hand calculation of the metrics: [docs/metrics_worked_example.md](docs/metrics_worked_example.md).

## Layout

```
src/monosplit/
  extraction/          JDK install, javap parser, call-graph extraction
  llm/                 LLM interface and one adapter per provider
  metrics.py           SM, IFN, ICP, NED
  controls.py          AH, random partition, HDBSCAN
  validation.py        acceptance rule for LLM outputs
  runner.py            LLM runs, retries and logs
  evaluate.py          controls and metrics per accepted run
  report.py            descriptive pilot report
  store.py             MongoDB storage of the configuration, graphs, runs and results
  configstore.py       validation and locks of the configuration edited by the interface
  dataedit.py          the changes allowed on the Data page (edge check, notes, study deletion)
  dbtools.py           import of the earlier config/, prompts/ and data/ files, dump and restore
  analysis.py          tests and comparison criterion of the full experiment
  estimate.py          cost and time estimate of a job, shown before it starts
  api/                 JSON API, node layout, jobs and static export of the web interface
web/                   web interface (React, TypeScript, Cytoscape.js); wiki pages in web/src/wiki/content
compose.yaml           the MongoDB server (Docker)
docs/                  decisions, results, challenges and the worked example of the metrics
dump/monosplit/        readable copy of the study database, one JSON Lines file per collection
tests/fixtures/        Java fixture, saved javap output and a copy of the prompt decomposition_base
work/                  cloned applications, builds, report copies, backups and the static site (not versioned)
```

## Experimental objects

| Application | Repository | Registered (collection `apps`) |
|---|---|---|
| JPetStore | https://github.com/Ericles-Porty/jpetstore-6 (fork of mybatis/jpetstore-6, unchanged) | tag `monosplit-pin` = release `jpetstore-6.3.0` (`ce8015b`), graph extracted |
| AcmeAir | https://github.com/Ericles-Porty/acmeair (fork of acmeair/acmeair at `f161227`, build updated) | commit `95586ab`, graph extracted; the WebSphere eXtreme Scale service is left out |
| DayTrader | https://github.com/Ericles-Porty/sample.daytrader7 (fork of WASdev/sample.daytrader7, unchanged) | id `daytrader`, commit `6df9bab` (MonoEmbed), graph extracted |
| Plants | https://github.com/Ericles-Porty/sample.mono-to-ms.pbw-monolith (fork of SteeleDesmond/sample.mono-to-ms.pbw-monolith) | id `plants`, commit `fdacf3b` (= `e6f2a6a` compiled for Java 8), graph extracted |

The four applications and repositories are those of Weerasinghe et al. (2026). The commits
seen on 2026-11-05 are in `docs/decisions.md`. AcmeAir comes from a fork that updates only its
Gradle build, so that it runs on JDK 21; its Java sources are unchanged (see `docs/decisions.md`,
section AcmeAir). An application builds with its own Maven wrapper, with the Maven the tool
installs or with its own Gradle wrapper (Gradle 8.5 or later).

## Setup

Requires [uv](https://docs.astral.sh/uv/), git and a MongoDB server (8.0 was used),
started here with [Docker](https://docs.docker.com/get-docker/).

```
docker compose up -d
uv sync --all-extras
uv run python -m monosplit jdk install
uv run python -m monosplit db restore dump      # only on a fresh clone: loads dump/monosplit
```

The dump holds the configuration too (applications, LLM profiles, prompt versions,
experiments), so a fresh clone needs no other file.

The second command downloads Eclipse Temurin 21 into a per-user folder
(`%LOCALAPPDATA%\monosplit\jdk` on Windows) and checks its checksum. It does not change
JAVA_HOME. Set `MONOSPLIT_JAVA_HOME` to use another JDK.

On Windows, application control can block the `monosplit.exe` launcher that uv creates;
`uv run python -m monosplit ...` works in every case and is used below.

## Data storage

The configuration, graphs, runs and results are stored in MongoDB, the primary record of
the study. `compose.yaml` runs the server in Docker on 127.0.0.1:27017 with the data in the
volume `monosplit-mongo`; `docker compose stop` keeps the data, `docker compose down -v`
deletes it. Set `MONOSPLIT_MONGO_URI` to use another server (default
`mongodb://127.0.0.1:27017`). The configuration and the graphs always live in `monosplit`.
Each experiment names the database of its runs (`database`, default `monosplit`); the dry
run uses `monosplit_dry_run`, so fake numbers never mix with the study.

| Collection | One document per |
|---|---|
| `apps` | application: repository, pinned commit, build and source paths |
| `profiles` | LLM profile: provider, model, request parameters, prices, note; names starting with `_` are templates |
| `prompts` | prompt version: the exact text, never overwritten |
| `experiments` | experiment configuration: application, runs, variants, seed, prompt, controls, analysis, note |
| `graphs` | application: class rows, edges with call counts, call sites, extraction metadata, edge check |
| `variants` | variant of a study: run configuration, prompt exactly as sent, prompt-name map |
| `attempts` | LLM attempt: log record, full API response and, when accepted, the partition |
| `evaluations` | study: AH selection, paired differences, measured partitions, summaries, report.md |
| `metrics` | metric row (variant, run, method) of the current evaluation |
| `notes` | study with a note written by the researcher |
| `audit` | change made by the interface or the command line: time, action, source, values before and after |

Each database keeps the audit of its own changes. No transaction is needed: an attempt is one insert, and a unique index refuses the same
attempt twice when a run resumes; a new evaluation writes its metric rows first and then
switches the pointer in `evaluations` with one document replacement.

```
uv run python -m monosplit db status            # connection and documents per collection
uv run python -m monosplit db dump dump         # writes dump/monosplit/*.jsonl
uv run python -m monosplit db restore dump      # into an empty database
```

The dump has documents in a fixed order and sorted keys, so two dumps of the same data are
byte for byte equal and `git diff` shows what changed. Run `db dump` before committing
data; the dump in git is the replication package.

Earlier versions kept the configuration in `config/` and `prompts/` (up to commit 5b3a115)
and the runs and results in `data/` (up to 7a9f75c). `db import-config [folder]` loads the configuration files of a folder holding
`config/` and `prompts/` (paths become names, comment lines become notes) and
`db import [data folder]` loads `data/runs`, `data/results` and the graph files. Both can
run again: documents already stored are skipped, and a configuration that differs from its
file is reported and kept.

## Procedure

The final experiment has one configuration per application: `final-jpetstore`,
`final-acmeair`, `final-plants` and `final-daytrader`. They share the experiment name `final`,
so the Results page pools the four applications, and use the profile `gpt-6.1-sol-high`
(settings in `docs/decisions.md`, section *Clean database and the final experiment*).

1. Clone, compile and extract the call graph of each application (`jpetstore`, `acmeair`,
   `plants`, `daytrader`):
   ```
   uv run python -m monosplit app fetch jpetstore
   uv run python -m monosplit extract jpetstore
   ```
2. Check a sample of edges against the source code on the Data page of the interface
   (tab *Edge check*): yes or no for each edge, and a note when needed. Paths are relative
   to `work/apps/<app>/`. The sample is drawn when the graph is extracted from the
   Execution page, or with `uv run python -m monosplit edge-sample jpetstore`.
3. Check the hand calculation in `docs/metrics_worked_example.md` and run the tests:
   `uv run pytest`.
4. Run the whole pipeline offline: `uv run python -m monosplit all --experiment dry_run`.
5. Create the LLM profile on the Configuration page, from the template of the provider:
   set the model, the reasoning effort (if any) and the prices, and put the API key in the
   environment variable named in the profile. The profile name identifies its runs in the database.
   For a local model, see *Local models (Ollama)* below.
6. Read the prompt exactly as it will be sent:
   `uv run python -m monosplit prompt --experiment final-jpetstore --variant obfuscated`.
7. Run each configuration (or use the Execution page, which shows the cost estimate first):
   ```
   uv run python -m monosplit all --experiment final-jpetstore
   ```
   `--llm <profile>` runs another profile instead of the one in the configuration. An
   interrupted run resumes when the command is repeated. A variant started under one
   configuration (model, parameters, prompt, graph) refuses to resume under another.
8. Read the results on the Results page (experiment `final`, profile `gpt-6.1-sol-high`): the
   hypothesis tests and the comparison criterion on the four applications pooled and on each
   one alone. Each study also has a report, copied to
   `work/reports/final/<app>/gpt-6.1-sol-high/report.md` (the database keeps the record).
9. Write the readable copy for git: `uv run python -m monosplit db dump dump`.

## LLM providers

`src/monosplit/llm/base.py` defines the interface (`LLMClient.generate`) and a registry.
Each provider has one adapter:

| Provider name | Adapter | Credentials |
|---|---|---|
| `openai` | Chat Completions, `openai` SDK | `OPENAI_API_KEY` |
| `anthropic` | Messages API, `anthropic` SDK | `ANTHROPIC_API_KEY` or an `ant auth login` profile |
| `gemini` | `google-genai` SDK | `GEMINI_API_KEY` |
| `ollama` | local models in [Ollama](https://ollama.com), native REST API (httpx) | none |
| `openai_compatible` | Chat Completions on another server (vLLM, LM Studio, OpenRouter) | optional |
| `fake` | offline stand-in for tests and dry runs | none |

Testing another model needs only a new profile. Adding a provider needs one class that
subclasses `LLMClient`, is decorated with `@register("<name>")` and is imported in
`src/monosplit/llm/__init__.py`; the runner, the prompt and the logs stay as they are.

### Local models (Ollama)

Install [Ollama](https://ollama.com/download), download a model and create its profile from
the template `_ollama` on the Configuration page:

```
ollama pull qwen3.5:4b
ollama show qwen3.5:4b           # parameters, quantization, thinking levels
```

The provider `ollama` talks to the server of this machine (`http://127.0.0.1:11434`) through
its native API, not through its OpenAI-compatible endpoint, which cannot set the context
window per request: the server default (4096 tokens with less than 24 GB of VRAM) would cut
the DayTrader prompt (about 10,100 tokens) without warning. The profile must set the context
window in its request options (`{"options": {"num_ctx": 49152}}`); the server refuses a prompt
that does not fit, and the tool refuses a configuration whose prompt and output limit do not
fit together, before any attempt is stored. The seed stays empty: each attempt gets a seed
derived from the master seed (`runner.attempt_seed`). Each variant records the model digest,
quantization, Modelfile parameters and server version; each attempt, the server version, the
context allocated and the share of the model in GPU memory. Nothing is billed, so jobs start
without the cost confirmation, and the Execution page shows the expected time instead.
Decisions and measurements: `docs/decisions.md`, section *Local models through Ollama*.
The study piloted a local replication with gpt-oss:20b and qwen3.5:4b and dropped it: on
this machine an attempt took 6 to 57 minutes, and on AcmeAir and DayTrader most answers
failed the acceptance rule (`docs/decisions.md`, section *Final experiment run, local
replication dropped*; `docs/desafios.md`, items 9 to 15).

## Web interface

The interface shows the call graph of each application and every decomposition of each
accepted run: the LLM, the AH variants, the random partition and HDBSCAN, side by side.
It requires Node.js 20 or later to build.

```
cd web
npm install
npm run build
cd ..
uv run python -m monosplit web serve --open      # http://127.0.0.1:8765/
```

`--database monosplit_dry_run` shows the dry run instead of the study. The server only binds
to 127.0.0.1 and only serves the studies found in that database. When MongoDB is not
running, the API answers 503 with the command that starts it.

Views:

- **Fixed positions.** Every panel draws the classes at the same positions (seeded layout,
  `src/monosplit/api/layout.py`), so the same class sits in the same place in every
  decomposition; zoom and pan are shared. Node colour is the service. Past three services,
  the service number follows the class name, because the categorical palette only keeps
  every pair of colours distinguishable up to three services.
- **Grouped by service.** Each service is a box; double-click a box, or use the buttons,
  to collapse services into single nodes with their calls summed.
- Panels 2 and 3 reuse the colour of the panel 1 service with the largest class overlap
  (Hungarian matching), so equal colours mean overlapping services.
- Dark rings mark interface classes (called from another service); dark edges are calls
  between services, with width by call count.
- *Compare with* marks, with a dashed outline, the classes that moved to another service
  between two runs, and gives the adjusted Rand index (ARI) of the two partitions. The
  letters under the run numbers group runs that returned the same partition.
- Below the panels: the metrics of each panel, a table of every class and its service
  (the accessible equivalent of the graphs), the class details and the model's answer.

**Results page.** One experiment and LLM profile at a time, across its applications:
LLM runs and rejection reasons; the four metrics by method (one dot per run, interquartile
band and median, HDBSCAN as a reference with its own K); the paired differences
LLM − control; the AH variant selection; and run-to-run stability. Summaries use the
code of `report.md`, so both show the same numbers. The hypothesis tests of the full
experiment (Shapiro-Wilk, paired Wilcoxon or paired t, Holm, Cliff's delta and the
comparison criterion, with the NED condition added after the pilot and the roteiro's criterion beside it) appear only when the experiment configuration sets
`inferential = true`, as the final experiment does; the pilot configurations set `false`. Every figure exports to
SVG and PNG (light theme, 900 px wide, about 8 pt at the text width of an article) and
every table to CSV (full precision) and LaTeX (booktabs, in the interface language).

**Wiki.** The study explained page by page, in Portuguese and English: goal (GQM),
design, variables and hypotheses, the four metrics with the hand-calculated example, the
call graph, the LLM treatment, the controls, the data analysis, the tool and a glossary.
The pages are Markdown files in `web/src/wiki/content/<pt|en>/`, rendered with marked and
KaTeX (formulas between `$...$` and `$$...$$`); they load only when the wiki opens.
`npm test` checks that every page exists in both languages with the same sections, that
every link points to an existing page and that every formula renders. The wiki describes
the design and the instruments; the results are on the Results page and in `docs/resultados.md`.

**Explanations.** Every term of the interface (metrics, methods, run counters, statistics,
configuration fields) has a dotted underline: hovering over it or reaching it with the Tab
key shows a short explanation and, where the wiki covers it, a link to that section. The
charts explain their panel titles, row labels and legend items the same way. The texts are
in `web/src/i18n/messages-help.ts`, in Portuguese and English; `npm test` checks that both
languages have every entry and that every link points to an existing wiki section.

**Configuration page** (local version only). Edits the configuration stored in the
database: LLM profiles (with the list of models available to the account and the prices),
experiment configurations, prompt versions (with a preview of the rendered prompt) and
applications (with the commit of a tag looked up by `git ls-remote`). Profiles and
experiments have a free-text note. Every save is validated, checked with the runner's code
and written to the change log. Rules that keep runs reproducible:

- a profile that already has runs keeps provider, model and request parameters (prices,
  timeouts and the key variable can change); to test another model, create another profile;
- an experiment with runs keeps its name, application, seed, retries, prompt and database;
- a prompt version is never overwritten; editing creates the next version (`_v2`, `_v3`…),
  and a version used by a run cannot be deleted;
- an application with an extracted graph or runs keeps its repository, commit and paths.

**Execution page** (local version only). Starts jobs on the server, one at a time:
graph extraction (clone, build, javap), LLM runs, controls and report, and the dry run.
Before a run with a paid model, the page shows the estimate (tokens per attempt, observed or
approximated; expected and maximum cost from the profile's prices) and asks for
confirmation; the server refuses a paid job whose estimate changed after it was shown.
A local model starts without confirmation; its estimate shows the time per attempt and the
expected time, from the earlier attempts, and warns when Ollama is not running or the model
was not downloaded.
Progress, cost so far and the log update every second; *Cancel* stops before the next
attempt, and starting the job again resumes it.

**Data page** (local version only). Shows what each database holds: the studies with their
attempts per variant, every attempt with the model's answer, the accepted partition and the
full API response, and the change log. The runs, answers, partitions and metrics are
read-only. What can change: the edge check of each application (yes or no and a note per
edge), a free-text note on a study, the recomputation of a study's controls and report (a
job that calls no model), and the deletion of a whole study, which needs the study typed as
confirmation and first writes a full dump of its database to `work/backups/<time>/`. Every
change, including those of the Configuration page, goes to the `audit` collection.

API keys are read from the environment, and on Windows also from the user's saved
variables (`HKEY_CURRENT_USER\Environment`), so a key created after the terminal was opened
is found. Key values are never sent to the browser. Every request that changes something
needs the `X-MonoSplit-Request` header and a local origin and host, so another site open in
the browser cannot trigger a paid run.

Development: run the API (`uv run python -m monosplit web serve`) and, in `web/`,
`npm run dev` (http://127.0.0.1:5173/, proxies `/api`). Checks: `npm run typecheck`,
`npm test`, and `npm run screenshot`, which captures the main views in both themes with
the installed Edge or Chrome and lists console errors.

**Static site.** `uv run python -m monosplit web export` writes `work/site/`: the built
interface plus one JSON file per API response. It needs no server-side code and uses
relative paths and hash routes, so the folder can be published as is (for example on
GitHub Pages) or opened from any static web server. It is read-only.

## Reproducibility

- Applications are pinned to a commit; the extraction refuses a checkout with local changes.
- The graph metadata records the JDK and javap versions and the counting rules.
- Every random step has a seed derived from the master seed in the experiment file, and
  the seed is written next to its result.
- Every attempt is logged with the model reported by the API, tokens, latency, cost and
  the full raw response; the prompt is stored exactly as sent.
- Dependency versions are locked in `uv.lock`.
- The dump in `dump/monosplit/` holds the configuration, every graph, attempt, raw response
  and evaluation, and the change log; `db restore` rebuilds the database from it, and
  dumping again gives the same files.

## Tests

```
uv run pytest
```

The tests use an in-memory MongoDB (mongomock) and a copy of the prompt `decomposition_base`
in `tests/fixtures/prompts/`. The tests marked `mongo` (`tests/test_store_mongo.py`) run
against the server of `compose.yaml` in a throwaway database, which also stands in for the
main database, and are skipped when it does not answer. The extraction tests parse saved javap
output of the Java fixture in `tests/fixtures/java`, and compile it again with javac when a
JDK is installed.
