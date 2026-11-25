# Using the tool

## Interface pages

| Page | Use |
|---|---|
| Wiki | These pages |
| Overview | Studies found in the database, cost of the runs and the applications' graphs |
| Configuration | Model profiles, prompt versions, applications and experiments; local version only |
| Execution | Graph extraction, model runs, controls and report, with a cost estimate; local version only |
| Decompositions | Graph of each decomposition, with up to three methods side by side, comparison between runs and the model's answer |
| Results | Metrics by method, paired differences, hypothesis tests (in the full experiment), AH selection and stability, with export of figures and tables |
| Data | Studies, attempts and the model's answers read-only, the edge check, notes, deletion of studies and the change log; local version only |

On the Decompositions page, each class keeps the same position in every panel, and the colour is the service. Panels 2 and 3 reuse the colour of the panel 1 service with the largest class overlap. The palette keeps every pair of colours distinguishable only up to 3 services; from 4 on, the service number follows the class name.

## Command line

The commands run in the `experimento/` folder:

```
docker compose up -d                           # starts MongoDB (compose.yaml)
uv run python -m monosplit db status            # connection and documents per collection
uv run python -m monosplit jdk install          # installs the pinned JDK (Temurin 21)
uv run python -m monosplit app fetch jpetstore  # clones the application at its pinned commit
uv run python -m monosplit extract jpetstore    # builds and extracts the call graph
uv run python -m monosplit edge-sample jpetstore
uv run python -m monosplit prompt --experiment <configuration> --variant obfuscated
uv run python -m monosplit all --experiment <configuration> --llm <profile>
uv run python -m monosplit web serve --open     # interface at http://127.0.0.1:8765/
uv run python -m monosplit web export           # static site in work/site/
uv run python -m monosplit db dump dump         # readable copy of the database in dump/monosplit/
uv run python -m monosplit db restore dump      # rebuilds the database on an empty server
```

Experiments and profiles are named as on the Configuration page.

## Data storage

The configuration, graphs, runs and results are stored in a local MongoDB database, the primary record of the study. The `compose.yaml` file starts the server in Docker; the environment variable `MONOSPLIT_MONGO_URI` points to another server when needed. The configuration and the graphs live in the `monosplit` database. Each experiment writes its runs to the database named in its `database` field: the study uses `monosplit`, and the dry run uses `monosplit_dry_run`.

| Collection | One document per |
|---|---|
| `apps` | application: repository, pinned commit and build |
| `profiles` | model profile; names starting with `_` are profile templates |
| `prompts` | prompt version, never overwritten |
| `experiments` | experiment configuration |
| `graphs` | application: classes, edges, call sites and the manual edge check |
| `variants` | variant of a study: run configuration, prompt as sent and name map |
| `attempts` | attempt: record, full answer and, when accepted, the partition |
| `evaluations` | evaluated study: AH selection, paired differences, measured partitions and report |
| `metrics` | metric row of the current evaluation |
| `notes` | study with a note by the researcher |
| `audit` | change made by the interface or the command line |

The items that come with the tool cannot be deleted, but they can be edited: the `dry_run` experiment, the `jpetstore` application it uses, the `fake` profile, the `decomposition_base` prompt and the profile templates. The others can be deleted when no run or configuration uses them. The defaults are also kept in the code of the tool, which recreates any missing one when a command opens the database.

Every configuration has a notes field of free text. The comments of the configuration files of earlier versions became these notes when they were imported (`db import-config`).

Each attempt is written at once, and a unique index prevents storing the same attempt twice when a run is resumed. A new evaluation writes its rows before replacing the previous one, so the interface never shows two evaluations mixed.

The `db dump` command writes the database to JSON Lines files (one JSON document per line, JavaScript Object Notation), in a fixed order, in the `dump/` folder, which is kept in git and forms the replication package. The `db restore` command rebuilds the database from that copy on an empty server.

## Data page

The Data page shows what each database holds. The attempts, the model's answers, the accepted partitions and the metrics are read-only: they are the evidence of the experiment, and only the runs and the evaluation write them. The page allows three kinds of change:

- the manual check of the edges of each application, with the verdict (yes or no) and a note per edge;
- the note on a study, as free text;
- the deletion of a whole study, for example a run made with a wrong configuration. Before the deletion, a full copy of the database goes to `work/backups/`, outside git.

Recomputing the controls, metrics and report can also be asked for on that page; it calls no model.

Every change, including those made on the Configuration page, adds a document to the `audit` collection of the database changed, with the date, the action, the source and the values before and after. The Change log tab lists these documents, which also go into the dump.

## Reproducibility

- Each application is pinned to a commit; the extraction refuses a checkout with local changes.
- The graph metadata record the versions of the JDK (Java Development Kit) and of `javap` and the counting rules.
- Every random step has a seed derived from the experiment's master seed, recorded next to the result.
- Every attempt records the model reported by the API (Application Programming Interface), the tokens, the time, the cost and the full answer; the prompt is stored exactly as sent.
- Dependency versions are locked in `uv.lock`, for Python, and in `web/package-lock.json`, for the interface.

## Keys and costs

API keys are read from environment variables and are never sent to the browser. Before a paid run, the Execution page shows the estimate of tokens and cost and asks for confirmation; the server refuses the run if the estimate changed after it was shown. A local model, in Ollama, needs neither a key nor a confirmation: the estimate shows the expected time, measured on the earlier attempts, and warns when Ollama is not running or the model was not downloaded (`ollama pull <model>`). Routes that write to the database accept requests only from the interface itself, from a local origin.

## Static site

The `web export` command writes a read-only copy of the interface with the data embedded, which works from any static file server or subfolder. That copy has no Configuration, Execution or Data pages. The exports of the Results page work in it, because the browser produces them.
