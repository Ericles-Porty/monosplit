# Decisions

Log of the decisions of the study, in the order they were taken: first while building the
pilot instruments (2026-11-04), before any LLM run, then after the pilot runs, for the final
experiment and for the local replication (2026-11-05 and 2026-11-06). A later section can
replace an earlier decision; the earlier text stays, with a note that points to the change.
The study design is in the roteiro, the experimental plan written for the course (31/10/2026),
which is not part of this package; the paper describes the final design. Items marked
**Deviation** change or refine a sentence of the roteiro and must be carried into the next
planning document. Commit hashes cited here belong to the development repository, which is
private; this package starts from a snapshot of it.

## Experimental object

**JPetStore pinned to tag `jpetstore-6.3.0`** (commit `ce8015be2c2658d0b657be20328e53045f3a9641`,
2026-07-09). Tags 6.0.2 to 6.3.0 have the 24 classes decomposed in the literature (the
number reported by Su et al., 2026), with the Stripes web layer. Tag 6.4.0 (2026-08-15)
migrated the web layer to Spring MVC and has 25 classes. Between 6.1.0 and 6.3.0 only two
source files changed (`CatalogService`, `CartActionBean`).

The build skips the parent POM's plugins that rewrite sources (formatter, import sort,
license headers, whitespace, OpenRewrite), and `monosplit` fails if the build modifies a
tracked file, so the bytecode matches the pinned commit.

## Call-graph extraction

**Tool: compiled bytecode read with `javap -v -p`** (Eclipse Temurin 21.0.13). The
compiler resolves the static type of every call, which a source parser would have to
approximate. Rules:

- Nodes: top-level classes of `src/main/java`, interfaces, enums and abstract classes
  included; tests excluded. Nested, inner and anonymous classes are merged into their
  top-level class.
- One call = one invocation instruction (`invokevirtual`, `invokespecial`, `invokestatic`,
  `invokeinterface`), or one invoking method handle of an `invokedynamic` instruction
  (method references such as `Item::getListPrice`), whose target is another top-level
  class of the application. Constructor calls count.
- The target is the class that declares the invoked member. javac records the receiver's
  static type, so `setMessage(...)` inside `CartActionBean` is recorded against
  `CartActionBean`; the extractor walks the application's superclasses and interfaces and
  attributes it to `AbstractActionBean`, which declares it. Members declared only in
  library types are library calls.
- Not counted: calls inside a class, calls to libraries, field accesses, type references
  without a call. Framework calls made at run time (Stripes, MyBatis XML mappers, JSP
  expressions) are not static calls between classes.
- Isolated classes stay in the graph and must be assigned by every method. In JPetStore,
  `Category` is isolated: no Java code calls its methods; only JSPs use it.

JPetStore 6.3.0: 24 classes, 40 edges, 159 calls, 1 isolated class (collection `graphs`, document `jpetstore`).

## Metrics

**Deviation: SM counts distinct edges, not calls.** The roteiro says that the call count
is the input of μ_i and γ_ij. The SM denominators, m_i² and 2·m_i·m_j, are the largest
possible numbers of directed edges inside a service and between two services, so each term
is an edge density and SM lies in [−1, 1]. With call counts, SM exceeds 1 and is not
comparable with the values in the literature. ICP keeps call counts ("proportion of the
calls"). IFN and NED do not depend on counts.

The sum over i ≠ j in SM runs over ordered pairs with directed γ_ij, which equals summing
(γ_ij + γ_ji) / (2 m_i m_j) over unordered pairs. SM is undefined for one service; the
acceptance rule requires K ≥ 2.

## LLM treatment

- **Provider-neutral client.** `LLMClient` is the interface; each provider has one adapter
  (OpenAI Chat Completions, Anthropic Messages, Google Gen AI, OpenAI-compatible servers
  such as Ollama). A model is described by a profile (collection `profiles`), and runs of
  each profile are stored apart.
- **Prompt `decomposition_v1`** (collection `prompts`), in English, written
  before any run. It sends the full class names (package and class) and the edge list
  with call counts, asks for every class in exactly one service, lets the model choose K
  (at least 2) and asks for JSON only. It names no metric and no size range, so the
  treatment is not tuned to the dependent variables.
- **Acceptance rule.** The JSON object may be bare, in a code fence or surrounded by text;
  class names must match the prompt exactly (after trimming spaces); services with no
  classes are dropped and counted. Rejection reasons, in order: invalid_json,
  invalid_schema, unknown_class, duplicate_class, missing_class, too_few_services, and
  refusal when the provider declines.
- **Retries.** An invalid output is re-sent with the same prompt and no feedback, up to 3
  times (4 attempts per run), so every accepted output is a zero-shot sample. A run with 4
  invalid attempts is a failed run; all attempts are counted. API errors (network, rate
  limit after the SDK's retries) are logged, are not outputs, and stop the command; the
  next call resumes.
- **Obfuscated variant.** Classes renamed to C01 … C24 in a seeded random order, so the
  aliases do not follow the packages; same edges, same template.
- **Temperature.** The roteiro fixes a temperature above zero, closed in the pilot. The
  value is the provider's default unless the model accepts another one. The Anthropic SDK
  in use (anthropic 2.5.0) sends API version 2026-10-21, which rejects `temperature`,
  `top_p` and `top_k` on every model; Claude samples at the default temperature 1.0, and
  the adapter refuses a configured temperature. Reasoning models of other providers may
  also accept only their default. The value sent, or "not sent", is recorded with each run.
- **Reasoning effort** is part of the model configuration and must be set explicitly in
  the profile when the model has it (for example `output_config.effort` for Claude).
- **No automatic fallback to another model.** Anthropic offers a server-side fallback that
  answers a refused request with another model. It is not enabled: the model is a
  controlled variable. A refusal is an invalid attempt with reason `refusal`.

## Controls

- **AH.** scikit-learn agglomerative clustering on a precomputed distance, cut into exactly
  K clusters. Distances: `calls`, 1 / (1 + calls a→b + calls b→a); `neighbors`, Jaccard
  distance between the closed neighbourhoods of the two classes. Linkages: average,
  complete, single (Ward needs Euclidean features). **Selection rule, fixed before the
  runs:** the variant with the highest median SM over the pilot's accepted runs becomes
  the AH control of the full experiment, ties to the first listed. This picks the
  strongest AH on the primary metric. JPetStore is also in the full experiment, so this
  tuning favours AH there; it goes to the threats to validity. **Replaced on 2026-11-06:**
  the full experiment fixes the AH control to `neighbors:complete` (section *Decisions for
  the full experiment*, item 2).
- **Random partition.** Uniform over all partitions of the classes into exactly K
  non-empty services, sampled exactly with the Stirling-number recurrence.
  **Deviation:** Python's `random` instead of NumPy, because the counts need
  arbitrary-precision integers. One partition per accepted run; its seed is derived from
  the master seed, the application, the profile, the variant and the run (SHA-256) and is
  written next to the result.
- **HDBSCAN.** Descriptive reference outside the pairing by K, computed once per distance,
  `min_cluster_size = 2`; each noise point becomes a service of its own. Its inclusion in
  the full experiment is decided after the pilot. Kept: the final experiment computes it
  as a descriptive reference.

## Analysis

- Pilot: descriptive only (median and interquartile range by method; paired differences
  LLM − control with sign counts). No hypothesis test.
- Full experiment (`src/monosplit/analysis.py`, tested on synthetic data): Shapiro-Wilk on
  the paired differences (α = 0.05); Wilcoxon signed-rank (two-sided, zero differences
  dropped) when normality is rejected, paired t test otherwise; Holm over the eight
  comparisons; Cliff's delta between the LLM and control values with the thresholds of
  Romano et al. (2006). When every difference is equal, normality is undefined: all zero
  means no test (p = 1), a constant non-zero shift goes to Wilcoxon.
- The experiment configuration chooses the analysis: `inferential = false` (pilot)
  or `true` (the full experiment; dry_run too, to rehearse the code on the fake
  client's numbers). With `true`, the Results page of the interface runs the plan above
  on the pairs of every application of the experiment pooled (40 pairs per comparison
  with 4 applications and 10 runs) and, for reference, on each application alone.
- Comparison criterion (roteiro): the "favours" side of a test is the sign of its
  location (median of d for Wilcoxon, mean of d for t) read with the metric's preferred
  direction. Condition (ii), "Cliff's delta at least small in SM", is implemented as
  written, on the magnitude |δ| ≥ 0.147; the interface shows the sign of δ beside it.
  Requiring the effect to favour the LLM would be a one-line change in `criterion`.

## Environment

Python 3.14 with versions locked in `uv.lock`; Eclipse Temurin 21.0.13 installed by
`monosplit jdk install`, outside JAVA_HOME. The SDK version, Python version and platform are
written to the meta of every variant (collection `variants`).

## Storage (2026-11-05)

- Graphs, runs and results moved from files under `data/` to a local MongoDB (8.0, in
  Docker through `compose.yaml`), at the researcher's request: queries across runs
  without walking folders, room for the four applications and more models, and safe
  writes when the interface and the command line work at the same time. The database is
  the primary record; the roteiro does not prescribe a storage format, so this is not a
  deviation from it.
- Integrity without transactions (a single server needs no replica set): an attempt is
  one insert holding the log record, the raw response and the accepted partition, and a
  unique index on (experiment, app, profile, variant, attempt) refuses a duplicate on
  resume; an evaluation writes its metric rows under a new id and then replaces the
  `evaluations` document that points to it.
- Maps keyed by class name (partitions, alias maps) are stored as [key, value] pairs,
  because class names contain dots.
- Git keeps `dump/monosplit/`, written by `monosplit db dump`: JSON Lines with documents in
  a fixed order and sorted keys, so the copy is diffable and the same data always gives
  the same bytes (`.gitattributes` pins LF). It is the replication package;
  `monosplit db restore` rebuilds the database from it.
- The pilot data were imported with `monosplit db import data`, then checked: every API
  payload built from the database equals the one built from the files (21 payloads), and
  recomputing the controls, metrics and report from the restored dump gives the stored
  values and the same report.md. The files left git in the same change and remain in
  its history (commits up to 7a9f75c).
- The dry run writes to the database `monosplit_dry_run`, never dumped; graphs always live
  in `monosplit`.

## Configuration in the database and the Data page (2026-11-05)

- At the researcher's request, the configuration left the files `config/apps.toml`,
  `config/llm/*.toml`, `config/*.toml` and `prompts/*.txt` for the collections `apps`,
  `profiles`, `experiments` and `prompts` of the main database. The interface already wrote
  every configuration change through one module (`configstore.py`), so its validation and
  the locks that keep runs reproducible did not change. Git keeps the configuration through
  the dump, so `git diff` still shows each change. Not a deviation from the roteiro, which
  prescribes no storage format.
- Import (`monosplit db import-config`): paths became names (an experiment names its prompt
  `decomposition_v1` and its default profile `gpt-5.6-luna-medium`), and the comment lines
  of each file became the new `note` field of profiles and experiments, without the header
  the earlier interface wrote and without command examples. Every configuration loaded
  back with the runner's code, and the stored prompt text is byte for byte the file
  (same SHA-256), so the variants already run keep matching their configuration. The files
  left git in the same change and remain in its history (commits up to 5b3a115). The four
  profile templates got their first sentence rewritten, since there is no file to copy.
- The command line names experiments and profiles (`--experiment pilot --llm gpt-5.6-luna`);
  a path of the earlier layout is reduced to its name. `all` is the new name of the
  command that runs, evaluates and reports; `pilot` remains as a synonym.
- **Audit.** Every change made by the interface or the command line to the configuration,
  the graphs (a new extraction, a new edge sample, an edited edge check), the study notes
  or the existence of a study adds a document to the collection `audit` of the database
  changed: time, action, collection, target, source and the values before and after.
  Saving a configuration equal to the stored one is not recorded. Runs and evaluations are
  not audited this way: their own documents are the record.
- **Data page.** The attempts, API responses, accepted partitions, evaluations and metrics
  are the evidence of the experiment and are read-only in the interface; only the runs
  and the evaluation write them. The researcher may change the edge check (verdict and note
  per edge; it replaces the CSV file and `db import data`), a free-text note per study
  (collection `notes`), and may delete a whole study, for example runs made with a wrong
  configuration. A deletion needs the study typed as confirmation, is refused while a job
  is running, and first writes a full dump of the database to `work/backups/<time>/`.

## AcmeAir (2026-11-05)

- **Version.** acmeair/acmeair at commit `f16122729873ef0449ea276dfb2d2a1d45bebb40`
  (2015-08-17), the commit pinned by MonoEmbed (Sellami and Saied, 2025), whose replication
  package Weerasinghe et al. (2026) ran; MonoEmbed counts 86 classes for it, without giving the
  counting rule. Su et al. (2026) use another code base, blueperf/acmeair-monolithic-java
  (32 classes, redesigned and now on Jakarta EE 9); it is not used here.
- **Build.** The original build is Gradle 2.6, which runs only on JDK 8 or older; current Gradle
  rejects its script (the `compile` configuration was removed in Gradle 7). At the researcher's
  request, the fork [Ericles-Porty/acmeair](https://github.com/Ericles-Porty/acmeair), commit
  `95586ab4536409765ba7baf812714c2887033e6d`, updates only the build: Gradle 9.8.2 wrapper (with
  the checksum of the distribution), java-library configurations, Java EE 7 API as compileOnly
  and `--release 8`. `git diff f161227 -- '*.java'` is empty; the fork's FORK.md lists every
  change. The tool got the build type `gradle-wrapper`: the project's gradlew with the pinned
  JDK, Gradle files in `work/gradle/`.
- The new build does not change the call graph: javac resolves each call from the same sources
  and the same dependency versions (javaee-web-api 7.0, json-simple 1.1.1, mongo-java-driver
  2.13.0, morphia 0.110), and the class files are Java 8 class files (major version 52), as
  with the original build on JDK 8.
- **Deviation: the WebSphere eXtreme Scale service is left out.** `acmeair-services-wxs`
  (17 classes) depends on IBM's objectgrid client 8.6.0.2, which is not in a public repository,
  so it cannot be compiled from public sources. The monolith is the MongoDB deployment of the
  original build (`-Pservice=morphia`): modules common, services, services-morphia, loader and
  webapp. `acmeair-reporter`, a separate Maven project for performance reports, is not part of
  the application, as in the original build.
- Graph (collection `graphs`, document `acmeair`): 52 classes, 72 edges, 220 calls, 6 isolated
  classes: `AcmeAirConstants` and `MorphiaConstants` (interfaces of constants, which javac
  inlines), `BigIntegerConverter` (a Morphia converter registered by annotation), and
  `DatastoreFactory`, `AcmeAirApp` and `AppConfig`, which the container finds through
  annotations. A sample of 20 edges is stored for the manual check (seed 20261104).
- The call sites of an edge sample used to name every file under the first source folder of
  the application, which is wrong for applications with one source folder per module
  (AcmeAir, DayTrader). Each file is now placed under the source folder of the checkout that
  holds it. The samples of AcmeAir and DayTrader, not checked yet, were drawn again with the
  same seed: the same edges, with the paths corrected.

## Decided by the pilot runs (resolved on 2026-11-06)

- Temperature value, for a model that accepts one. Resolved: the model chosen, gpt-6.1-sol,
  is called without a temperature, at the API default (`docs/desafios.md`, item 7).
- AH variant (rule above). Resolved: fixed to `neighbors:complete`.
- Prompt changes, if the failure rate is high; a new template gets a new name (`decomposition_v2`).
  Resolved: no change; the final experiment uses `decomposition_base`.
- Whether 10 accepted runs per application suffice, from the variation among the 5 pilot runs.
  Resolved: 10 accepted runs per variant and application.
- Inclusion of HDBSCAN. Resolved: kept as a descriptive reference, outside the tests.

Details in the sections *Decisions for the full experiment* and *Clean database and the final
experiment*, below.

## For the full experiment (not needed by the pilot)

Repositories, as cited by Weerasinghe et al. (2026); HEAD checked with `git ls-remote` on
2026-11-05. DayTrader and Plants were registered at these commits (collection `apps`, Maven
builds not run yet); AcmeAir is registered from a fork (section AcmeAir):

| Application | Repository | HEAD on 2026-11-05 |
|---|---|---|
| JPetStore | https://github.com/mybatis/jpetstore-6 | pinned: `jpetstore-6.3.0` (`ce8015be`) |
| AcmeAir | https://github.com/acmeair/acmeair | `f16122729873ef0449ea276dfb2d2a1d45bebb40` |
| DayTrader | https://github.com/WASdev/sample.daytrader7 | `643d04c100f75898003b5c98cde6b5f5015c613a` |
| Plants | https://github.com/WASdev/sample.plantsbywebsphere | `bf5f18b0ba120dfe68a91d7e181c06e32ed6f3c4` |

- Plants: the variant used by MonoEmbed, and so in the runs of Weerasinghe et al., is the
  simplified one without Java EE components: SteeleDesmond/sample.mono-to-ms.pbw-monolith at
  `e6f2a6a437221c2652b907a709cf0343780013f2` (Maven, 38 classes in the main sources).
- DayTrader: MonoEmbed pins `6df9bab50f1325a8101680dc488aa1dc5254c5b0` (2022-04-04); the
  registered HEAD differs from it in one Java file (`MarketSummaryWebSocket`) and in
  deployment files.

### Literature versions and forks (2026-11-06)

The user chose the literature versions of DayTrader and Plants, for comparison with MonoEmbed
and Weerasinghe et al. The earlier registrations `daytrader` and `plants` are locked by their
graphs (and by the user's study `dt`) and stay in the database; the study uses two new ids.
All four applications now have a copy under Ericles-Porty, so a removed or rewritten upstream
repository does not break the replication; each fork has the tag `monosplit-pin` on the
pinned commit of the original.

| Id | Repository (fork of) | Commit | Graph |
|---|---|---|---|
| jpetstore | mybatis/jpetstore-6 (fork Ericles-Porty/jpetstore-6, registration unchanged: locked by runs, same commit) | `ce8015be` | 24 classes |
| acmeair | Ericles-Porty/acmeair (acmeair/acmeair `f161227`) | `95586ab` | 52 classes, 72 edges |
| daytrader-mono | Ericles-Porty/sample.daytrader7 (WASdev/sample.daytrader7), unchanged | `6df9bab` | 108 classes, 231 edges, 1228 calls, 17 isolated |
| plants-mono | Ericles-Porty/sample.mono-to-ms.pbw-monolith (SteeleDesmond), branch `monosplit` | `fdacf3b` | 36 classes, 62 edges, 312 calls, 3 isolated |

- Plants: the root pom compiles for Java 6, which JDK 21 refuses. The fork branch `monosplit`
  changes only `source`/`target` to 1.8 and adds FORK.md; the Java sources equal `e6f2a6a`.
  Build: `-pl PlantsByWebSphere -am` from the root pom (pbw-lib is a module of the same
  repository); the graph covers the `PlantsByWebSphere` module only. The 38 source files
  give 36 top-level classes.
- DayTrader at `6df9bab` builds with the same arguments as the earlier registration.
- **Deviation:** Plants is compiled for Java 8 instead of Java 6 (no effect on the call graph).

### Defaults of the tool (2026-11-06)

The user deleted the configuration of the dry run by mistake through the Configuration page,
together with entries they meant to delete (the experiments pilot, pilot-2 and dt and their
studies, the prompt decomposition_v1 and the profile gpt-5.6-luna; the studies have backups
in `work/backups/` and are in the dump of commit de05a95). At the user's request:

- The defaults of the tool cannot be deleted (`configstore.PROTECTED`): the experiment
  `dry_run`, the profile `fake`, the prompt `decomposition_base` and the profile templates
  (names starting with `_`). They can still be edited; a prompt is never edited. The other
  entries can be deleted when no run or configuration uses them, as before. The Configuration
  page marks the defaults and disables their Delete button.
- `decomposition_base` replaces `decomposition_v1` as the default prompt. Its text is the text
  of `decomposition_v1`, except the comment header, which is not sent: the system and user
  messages are identical. The user's `decomposition_v2` has the same text as well.
- `dry_run` was restored from the audit record of its deletion, with `prompt_template =
  decomposition_base`, and the dry run was run again (database `monosplit_dry_run`).

### Defaults in the package and clean database (2026-11-06)

The defaults (`dry_run`, `fake`, the profile templates and `decomposition_base`) are kept in
`src/monosplit/defaults/` and created by every command that uses the database (all but `db`,
`jdk` and `providers`) when they are missing; an existing default is never overwritten. They
no longer depend on the database, the dump or the audit log. At the user's request the
database was then reset for a clean test: only the defaults, the profile `gpt-5.6-luna-medium`
and the application `jpetstore` with its graph remain; the other applications and graphs, the
prompt `decomposition_v2`, the database `monosplit_dry_run`, `work/backups/` and the audit
collection were deleted. The pilot data stay in the git history (dump of commit de05a95).

### JPetStore from the fork (2026-11-06)

At the user's request, `jpetstore` now clones Ericles-Porty/jpetstore-6 at the tag
`monosplit-pin`, which marks the same commit as the release tag `jpetstore-6.3.0`
(`ce8015be`). The graph was extracted again from the fork: same graph hash
(`f140ef22...`), 24 classes, 40 edges, 159 calls; the edge sample was drawn again with the
same seed (no row had been checked). `jpetstore` became a default of the tool, because the
dry run reads it: it is created from `src/monosplit/defaults/apps.json` when missing and
cannot be deleted. Its graph is not a default and must be extracted.

### Obfuscated variant in the full experiment (2026-11-06)

The user decided to keep both variants (original and obfuscated names) in the full
experiment, as in the roteiro. Pilot runs with gpt-5.6-sol (reasoning_effort high, 3 runs per
application, original variant only) cost about US$ 0.03 (JPetStore), 0.05 (AcmeAir),
0.06 (Plants) and 0.11 (DayTrader) per run at the profile prices; 10 runs per variant and
application (80 runs) are estimated at about US$ 5 at those prices. Still open before the full
experiment: the model, the AH variant (fixed instead of `auto`) and NED in the criterion.

### Decisions for the full experiment (2026-11-06)

Taken by the user after the pilot runs, before any run of the full experiment. Pilot numbers
are descriptive (1 to 10 runs per application) and are not results.

1. **Model: `gpt-6.1-sol`, `reasoning_effort = "high"`** (profile `gpt-6.1-sol-high`, US$ 2 /
   10 per million input / output tokens, price page accessed 2026-11-06). Pilot comparison,
   original variant:
   - gpt-5.6-sol (3 runs per application) and gpt-6.1-sol (3 runs, Plants and DayTrader):
     same median SM in Plants (0.107), lower ICP and NED with 6.1 in both (DayTrader ICP 0.42
     -> 0.31, NED 0.75 -> 0.50), at a third (Plants) to a half (DayTrader) of the cost.
   - gpt-6-astra (1 run per application): same metric values as gpt-6.1-sol in Plants and
     DayTrader at five times the cost per run; the full experiment would cost about US$ 10.6
     with astra and about US$ 2 with gpt-6.1-sol.
   The model has no dated snapshot name: the run dates and the model reported by the API in
   each attempt identify the version used.
2. **AH control fixed to `neighbors:complete`** (`ah_primary`), instead of `auto`. With `auto`,
   the variant is chosen per study by the highest median SM on the same runs, which selects
   on the dependent variable and favours the control in SM; in one pilot study (Plants,
   gpt-5.6-sol) it picked `calls:complete`. `neighbors:complete` is the variant chosen in the
   JPetStore pilot and in most pilot studies. All six variants are still measured and reported.
3. **NED joins the comparison criterion (Deviation).** The LLM is superior to a control when,
   besides the three conditions of the roteiro, there is no significant difference
   unfavourable to the LLM in NED. Reason, a property of the metric and not of the observed
   direction: the cohesion term of SM is the edge density mu_i / m_i^2, averaged over services
   with equal weight, so in sparse call graphs SM rewards partitions with one large service
   and several services of two or three classes. A local search on the pilot graphs, at the
   LLM's usual K, found SM of about 0.21 to 0.25 with such partitions (NED 0.75 to 1.00) and
   about 0.12 to 0.17 when every service has 5 to 20 classes; the AH control produced
   partitions of the first kind (AcmeAir: 38 to 45 of 52 classes in one service, NED 1.00).
   NED is the metric that flags these partitions (Weerasinghe et al., 2026). The results will
   report the criterion of the roteiro and the criterion with NED side by side.

Also kept: both variants (original and obfuscated), 10 accepted runs per variant and
application, prompt `decomposition_base`. Not run yet. To do before running: create the
experiments of the full experiment with these settings, and change `analysis.criterion`,
the Results page and the wiki (Variables and hypotheses) for decision 3.

Decision 3 implemented on 2026-11-06: `analysis.criterion` returns `no_unfavourable_ned`,
`llm_superior` (conditions i to iv) and `llm_superior_roteiro` (i to iii); the Results page
shows both verdicts; wiki pages Variables and hypotheses and Metrics updated. Open: with the
random control, condition (iv) can fail because a random partition with the same K spreads
classes evenly and so has a low NED (pilot, Plants with gpt-5.6-luna: NED unfavourable to the
LLM against the random partition). Whether condition (iv) applies to both controls or only to
the AH control is for the user to decide.
Resolved on 2026-11-06: the user keeps condition (iv) for both controls (AH and random
partition), as implemented. The effect of the size balance of the random partition on
condition (iv) is to be discussed in the article; the verdict of the roteiro's criterion,
reported beside the adopted one, shows the comparison without it.

## Local models through Ollama (2026-11-06)

The roteiro admits "a second model, with open weights, ... as a separate replication, outside
the main factor". At the user's request the tool runs local models served by Ollama 0.40.15 on
the study machine: RTX 4050 Laptop GPU with 6 GB, Ryzen 7 7735HS, 31 GB of RAM, Windows 11.
Not a deviation: the replication uses the same prompt, applications, variants, acceptance rule
and analysis as the main study, under its own profiles.

Decided by the user:

1. **Native adapter** `ollama` (POST /api/chat, `src/monosplit/llm/ollama_client.py`) instead
   of the provider `openai_compatible` pointed at Ollama's /v1 endpoint. That endpoint cannot
   set the context window per request, and the server default on this machine is 4096 tokens
   (Ollama picks 4k, 32k or 256k by GPU memory). Measured: the DayTrader prompt (35,898
   characters, 10,141 tokens for Qwen 3.5) sent with a 2048-token context was cut to 1,026
   tokens, and the model answered anyway (HTTP 200, the start of a JSON object). The endpoint
   also reports neither the model digest nor the server version.
2. **A seed derived for each attempt**: SHA-256 of master seed / experiment / application /
   profile / variant / attempt number, mod 2^31 (`runner.attempt_seed`), stored in each attempt
   record (`seed`); the rule is in the variant meta (`attempt_seeds`) and in the resume
   fingerprint. With the profile's seed sent to every attempt, as for the hosted models, a
   local model can answer every attempt alike (measured below); with no seed, the attempts
   differ but no seed is recorded. The experiment name is part of the seed, so a pilot and the
   full experiment with the same master seed draw different samples.
3. **No structured output** (Ollama's `format`, which restricts generation to a JSON schema):
   the treatment is the prompt `decomposition_base`, as sent to the hosted models. If the
   failure rate is high, a change is decided after the pilot, as for prompt changes.
4. **Two models, two separate replications**: profile `gpt-oss-20b-high` (gpt-oss:20b, MoE
   with 20.9B parameters, MXFP4, digest `f38aa0c53da5`) and profile `qwen3.5-4b-think`
   (qwen3.5:4b, 4.2B parameters, Q4_K_M, digest `d8b0f5e9760c`), both downloaded on 2026-11-06.
   Changed after the pilot: only qwen3.5:4b stays (section Pilot of the local models, below).

Decided in the implementation (the profiles can still change; nothing has run):

- **Context.** `options.num_ctx` is required in the request options and sent with every
  request, with `truncate = false` and `shift = false`: the server refuses a prompt that does
  not fit (HTTP 400, "request (10141 tokens) exceeds the available context size (2048
  tokens)") instead of cutting it. The adapter also refuses an answer whose prompt
  (`prompt_eval_count`) plus the output limit exceed the context the server allocated
  (`/api/ps`), and, before any call, a prompt that cannot fit even at 5 characters per token.
  Each is a configuration error: the job stops, no attempt is stored, and a new variant
  without attempts is removed, so the profile stays editable.
- **Both profiles**: num_ctx 49152 and output limit 32000 (the limit of the hosted profiles;
  the largest prompt plus the limit is about 42,200 tokens); temperature empty, so the
  Modelfile defaults apply and are recorded (gpt-oss: temperature 1; qwen3.5: temperature 1,
  top_k 20, top_p 0.95, presence_penalty 1.5); thinking "high" for gpt-oss, as
  `reasoning_effort = "high"` in the hosted profiles, and on for qwen3.5, whose only levels are
  on and off.
- **Identity.** Each variant records the digest, size, quantization, Modelfile parameters,
  capabilities and server version (`meta.model_identity`); the digest is in the resume
  fingerprint, so a variant never mixes weights, and a digest change during a job stops it.
  Each attempt records the server version, digest, context allocated and bytes in GPU memory
  (`raw.runtime`). The server version is recorded but does not stop a resume. The Ollama app
  updates itself on Windows: keep the version fixed during a replication.
- Ollama cloud models (served by ollama.com) are refused.
- Nothing is billed: `paid = False`, as for the fake client. Jobs start without the cost
  confirmation; the estimate shows the time per attempt and the expected time, from the
  observed latencies, and checks that the server answers and the model is downloaded. The
  profiles have a price of 0, so every attempt records a cost of 0 instead of none.
- A server failure (HTTP 5xx) is tried again after 10 s and 30 s; a server that is not
  running, or a timeout (`timeout_s`: 5400 s for gpt-oss, 3600 s for qwen3.5), is an API
  error, as with the hosted providers.

Measurements while building the instruments (single calls, not results):

- Prompt sizes. JPetStore: 1,346 tokens (qwen3.5), 1,387 (gpt-oss, Harmony format), 1,322
  (OpenAI's count in the pilot). DayTrader: 10,141 (qwen3.5), 9,526 (OpenAI).
- gpt-oss:20b, num_ctx 32768: 13.2 GiB loaded, 3.2 GiB (24 %) in GPU memory, the rest on the
  CPU; prompt evaluation about 400 tokens/s (43 tokens/s in the first call after the
  download), generation about 16 tokens/s. JPetStore, thinking high: 7,770 and 5,418 output
  tokens, 554 s (43 s of loading included) and 330 s; thinking low: 599 to 1,223 output
  tokens, 34 to 86 s.
- qwen3.5:4b, entirely in GPU memory at 2k and 4k context. JPetStore without thinking (8k
  context): 410 output tokens, 13 to 19 s. With the profile settings (thinking on, num_ctx
  49152) the server keeps 22 of its 33 layers (68 %) in GPU memory and generates about 18
  tokens/s; the first attempt of the end-to-end check through the runner (JPetStore) was
  accepted (K = 3) after 15,680 output tokens and 1,049 s, and so was the second (15,626
  tokens, 1,018 s). The small model thinks about twice as long as gpt-oss:20b, so the larger
  applications may reach the output limit (a truncated answer is an invalid attempt); to
  watch in the pilot. Without thinking it answers in about 20 s but failed 11 of 12 attempts
  (duplicate, missing or unknown classes), which supports thinking on for this profile.
- **Same seed, same answer?** qwen3.5:4b (JPetStore, without thinking) gave byte for byte the
  same answer to the same seed in 4 of 4 calls at 8k context, with an empty prompt cache and
  with the cache of the previous call, and in 3 of 3 calls at the 49k context of its profile,
  with a third of the model on the CPU. A second run of the
  end-to-end check, in a new process, repeated its 4 attempts seed by seed (status and output
  tokens). Another seed gave another answer. In every one of these calls the server took the
  same 1,342 of the 1,346 prompt tokens from its cache. gpt-oss:20b gave different answers to
  the same seed in each of the 3 pairs compared (empty cache against the cache of a previous
  call; two calls with the cache): for it, the server takes one cached token less at every
  call (1,386, 1,385, 1,384 of 1,387), so the last prompt tokens are computed differently
  each time, and the sampling changes. Unloading the model before every attempt would give
  every attempt the same start (whether two such calls then agree could not be checked), but
  loading gpt-oss:20b right after an unload crashed the model process in 2 of 2 tries (HTTP
  500, "CUDA error: shared object initialization failed"; the next request loaded it
  normally), and every attempt would pay the loading again (17 to 43 s). So the cache stays
  on: the seed per attempt makes the runs differ and is recorded; an attempt of qwen3.5:4b
  can be repeated from its seed, one of gpt-oss:20b is not expected to repeat byte for byte.
  Threat to validity for the article (reliability of the replication), together with the
  use of quantized builds: the results describe these builds, whose digests are recorded.
- Time of a replication (4 applications × 2 variants × 10 accepted runs, about 1.25 attempts
  per run, about 100 attempts), extrapolated from the JPetStore calls: in the order of 20 hours
  for gpt-oss:20b with thinking high and 30 to 40 hours for qwen3.5:4b with thinking on, more
  if the larger applications need longer answers. Measure it in the pilot; the Execution page
  shows the expected time once a variant has its first attempt.

### Pilot of the local models (2026-11-06)

Four pilot configurations, one per application and profile, with the settings of the hosted
references (seed 1793933766, variant original, prompt decomposition_base): `pilot-jpetstore-gptoss`
and `pilot-jpetstore-qwen` as `exp-jpetstore-3` (3 runs, at most 3 failed), `pilot-dt-gptoss` and
`pilot-dt-qwen` as `exp-dt` (3 runs, at most 1 failed). They ran one after another on the study
machine, so the two models never shared the GPU: 7.1 hours in all.

| Configuration | Attempts | Accepted | K of the accepted | Output tokens per attempt | Minutes per attempt |
|---|---|---|---|---|---|
| pilot-jpetstore-gptoss | 3 | 3 | 4, 4, 4 | 5,508 to 8,362 | 5.7 to 9.4 |
| pilot-dt-gptoss | 4 | 0 (1 failed run) | | 27,046 to 32,000 | 46.4 to 57.3 |
| pilot-jpetstore-qwen | 3 | 3 | 2, 2, 3 | 14,085 to 17,577 | 15.6 to 21.0 |
| pilot-dt-qwen | 5 | 1 (1 failed run) | 2 | 13,335 to 19,516 | 20.4 to 32.5 |

- The hosted profiles accepted 7 of 7 DayTrader attempts (`exp-dt`, `pilot-dt-61`,
  `pilot-dt-astra`), with 3,101 to 3,780 output tokens, K from 3 to 5 and less than a minute
  each.
- gpt-oss:20b on DayTrader (9,591 prompt tokens): two answers reached the output limit (32,000
  tokens, finish "length") before the JSON closed (`invalid_json`); the other two ended by
  themselves, at 30,666 and 27,046 tokens, and left out 11 and 5 classes (`missing_class`).
  Generation slowed from about 16 tokens/s on JPetStore to 8 to 10 tokens/s with the longer
  context.
- qwen3.5:4b on DayTrader (10,139 prompt tokens): one answer accepted, with K = 2. The rejected
  ones misspelled the package of every class (`daytrada`, `unknown_class`), invented three class
  names (`unknown_class`), or left out 1 and 16 classes (`missing_class`).
- DayTrader has 108 classes, 54 of them in `web.prims` (Ping servlets and beans with similar
  names). Apart from the misspelled package, every class the local models left out or invented
  is in `web.prims`, except `util.WebSocketJMSMessage`, left out by two qwen answers.
- Reading: on the largest application, the local models lose track of the class list during a
  long reasoning. The output limit cut only two of the four gpt-oss answers; a higher limit
  would not have saved the other two.
- **Decided by the user (2026-11-06):** the local replication keeps the profiles and the rules
  in every application, DayTrader included, and reports its failures as a result. Raising the
  output limit or lowering the reasoning level after seeing the answers would fit the treatment
  to the model and the application; a higher limit would also have saved at most two of the
  four gpt-oss answers. Options not taken: a higher output limit for the local profiles, the
  reasoning level medium for gpt-oss:20b, DayTrader left out of the local replication.
- In the replication configuration, DayTrader gets a low limit of failed runs (`exp-dt` has 1),
  set when the configuration is created: a failed run of qwen3.5:4b there took 1.9 hours (4
  attempts).
- **Decided by the user (2026-11-06), after the pilot:** the local replication uses only
  qwen3.5:4b (profile `qwen3.5-4b-think`); gpt-oss:20b is dropped. Its profile and pilot runs
  are in the dump of commit ff068b7 (the database was cleaned afterwards, below). Pilot facts bearing on it: no DayTrader
  attempt accepted (0 of 4, 46 to 57 minutes each), attempts not repeatable from their seed,
  a quarter of the model in GPU memory.
- Time of the qwen3.5:4b replication (4 applications × 2 variants × 10 accepted runs), from the
  pilot times. This replaces the estimate above. JPetStore: about 18 minutes per attempt, all
  accepted, so 6 to 7 hours for its 20 runs. AcmeAir (52 classes) and Plants (36) were not
  piloted; between JPetStore (24 classes, 18 minutes) and DayTrader (108 classes, 27 minutes)
  they should take 20 to 25 minutes per attempt, 7 to 10 hours each, more if they need retries.
  DayTrader, with 1 attempt accepted in 5 and a limit of one failed run per variant, would stop
  after about 7 attempts per variant (about 3 hours) with one or two accepted runs. In all
  about 30 hours, if the obfuscated variant, not piloted, behaves like the original.

### Configuration of the local replication (2026-11-06)

Created, not run. Four configurations, `rep-qwen-jpetstore`, `rep-qwen-acmeair`,
`rep-qwen-plants` and `rep-qwen-daytrader`, share the experiment name `rep-qwen`, so the Results
page pools the four applications as the planned analysis does. Settings of the full experiment:
profile `qwen3.5-4b-think`, prompt `decomposition_base`, both variants, 10 accepted runs per
variant, 3 retries, AH control `neighbors:complete` with the six variants measured, inferential
analysis, master seed 1793933766 (the seed of the pilot configurations; the experiment name
enters every derived seed, so the samples differ from the pilot's).

- Limit of failed runs per variant: 1 for DayTrader (decided by the user, above); 10 for the
  other three, as in the earlier configurations with 10 runs. The limit can
  still be changed on the Configuration page.
- The challenges met so far, written for the article, are in `docs/desafios.md`.

## Clean database and the final experiment (2026-11-06)

At the user's request, the database keeps only what the final experiment uses. Before the
cleaning, commit ff068b7 stored the code and the dump with every pilot run (hosted models:
gpt-5.6-luna, gpt-5.6-sol, gpt-5.6-terra, gpt-6.1-sol, gpt-6-astra; local: gpt-oss:20b,
qwen3.5:4b); the pilot numbers in this file and in `docs/desafios.md` come from that dump.

- Deleted: the 17 earlier experiment configurations and their studies (each deletion first
  wrote a full dump to `work/backups/`, outside git) and the profiles gpt-5.6-luna-medium,
  gpt-5.6-sol-high, gpt-5.6-terra, gpt-6-astra-high and gpt-oss-20b-high.
- Kept: the defaults of the tool, the four applications and their graphs, the prompt
  `decomposition_base`, the profiles `gpt-6.1-sol-high` and `qwen3.5-4b-think`, and the
  replication `rep-qwen`.
- **Final experiment**, created, not run: `final-jpetstore`, `final-acmeair`, `final-plants` and
  `final-daytrader`, experiment name `final`, profile `gpt-6.1-sol-high`, with the settings of
  the full experiment (both variants, 10 accepted runs per variant, prompt
  `decomposition_base`, AH control `neighbors:complete` with the six variants measured,
  inferential analysis, master seed 1793933766). Limit of failed runs per variant: 3 (decided
  by the user). The cost estimate of the Execution page, before any run: about US$ 3.4 for the
  80 runs (3,000 output tokens and 1.25 attempts per run assumed), at most about US$ 135 if
  every attempt allowed failed at the output limit.

## Final experiment run, local replication dropped (2026-11-06)

- The final experiment ran on the four applications with `gpt-6.1-sol-high` (jobs from 16:18 to
  17:44): 80 attempts, 80 accepted, no failed run. Before it, a study of `final-acmeair` with
  3 attempts that failed with HTTP 401 (wrong API key, no model answer) was deleted with a
  backup in `work/backups/`.
- The replication `rep-qwen` started with `rep-qwen-acmeair` (52 classes). Its four
  attempts, on the original variant: 1 accepted (K = 2) and 3 invalid. One left out
  `morphia.entities.CustomerImpl` and `morphia.services.util.MongoConnectionManager`; one
  invented `com.acmeair.config.AcmeAirConstants` (the class is `com.acmeair.AcmeAirConstants`)
  and left out `loader.FlightLoader` and `web.AcmeAirApp`; one left out five classes
  (`AcmeAirConstants`, `CustomerImpl`, `service.TransactionService`, `web.AcmeAirApp`,
  `web.AppConfig`). 17.0 to 20.5 minutes and 12,900 to 14,700 output tokens per attempt. A run fails
  after 4 invalid attempts (1 + 3 retries). With 1 accepted attempt in 3 or 4, about 20 % to
  30 % of the runs would fail, and AcmeAir would need about 60 to 80 attempts for its 20
  accepted runs (10 per variant), some 19 to 25 hours for this application alone; its limit of
  10 failed runs per variant would not be reached (about 2 to 5 expected). The sample is small, but it agrees with the
  DayTrader pilot (1 accepted in 5).
- **Decided by the user (2026-11-06):** the study drops the local replication; it uses only
  `gpt-6.1-sol-high`. The four `rep-qwen` jobs were cancelled (the AcmeAir one after its fourth
  attempt) and the qwen attempts were deleted, with a backup in `work/backups/` (outside git).
  The configurations `rep-qwen-*` and the profile `qwen3.5-4b-think` were deleted with them; they
  are in the dump of commit d01d05f, and the pilots of both local models in the dump of commit
  ff068b7. The Ollama adapter stays in the tool. The local models enter the article as a
  challenge and a limitation (`docs/desafios.md`, items 9 to 15), not as results. Options
  not taken: run the replication to its stopping rules (30 hours or more) and report the rate
  of invalid answers; keep only JPetStore as an exploratory replication.
- Correction (2026-11-06, after the decision): the first version of this entry, and the
  question put to the user, counted a failed run as 3 invalid attempts and the limit of failed
  runs over both variants. They gave about 30 % to 40 % of failed runs, the limit likely reached,
  and more than 15 hours. The corrected figures above give fewer failed runs and more time;
  the reason for the decision, the time and the rate of invalid answers on this machine, stands.

## Second run of the full experiment, `full` (2026-11-24)

This run was made in a working copy that did not have the commits ff068b7 to abf178a
(the local models, the clean database and the experiment `final` of 2026-11-06): its database
matched the dump of commit 2ea5292, so the full experiment looked not yet run. At the user's
request ("finalize the article") the protocol of 2026-11-06 was run again as the experiment
`full`, with its own master seed. When the two histories were merged, the user chose to keep
both experiments: `final` is the run described in `docs/resultados.md`; `full` is an
independent second run of the same protocol (same model, prompt, applications, variants,
controls and analysis; another master seed, so other obfuscation orders and random
partitions). Its limit of failed runs was 5 per variant instead of 3; neither run reached
it. The merged dump holds both. The database was then rebuilt from it: the old database was
dropped (backup in `work/backups/20261124-180751-antes-do-merge/`), `db restore dump` loaded
the merged dump, and a new dump came out byte for byte identical to it.

### Checks before the run

- `uv run python -m pytest`: 179 tests passed, the `mongo` ones included.
- Edge sample: the 20 sampled edges of each application (80) were checked at every recorded
  call site in the source code of the pinned checkouts, and all were confirmed (verdict `yes`).
  At the user's request the check was made by Claude (an AI assistant), not by the user; each
  row's note says so, and the edits were written through `dataedit.update_edge_check` (audit
  source `cli`). Cases that needed the context: implicit `super()` calls on the class
  declaration line (JPetStore `CartActionBean`, AcmeAir `CustomerServiceImpl`), a method
  inherited from `AbstractActionBean`, the method reference `Item::getListPrice`, the nested
  enum `Customer.PhoneType`, and calls split over lines, recorded by javac on the last line of
  their arguments (DayTrader `TradeDirect`, Plants `MailerBean` and `ShoppingBean`).
- `docs/metrics_worked_example.md` was recomputed by hand: SM, IFN, ICP and NED of P1 and P2
  match the stated values and `tests/test_metrics.py`.

### Configurations

Four experiment configurations, one per application, share the experiment name `full`, so the
Results page pools them: `full-jpetstore`, `full-acmeair`, `full-daytrader`, `full-plants`.
Settings: profile `gpt-6.1-sol-high`, prompt `decomposition_base`, variants original and
obfuscated, 10 accepted runs per variant, `max_retries = 3`, `max_failed_runs = 5` per
variant (a stop rule for an unexpected failure rate, not reached), the six AH variants with
`ah_primary = neighbors:complete`, HDBSCAN `min_cluster_size = 2`, `inferential = true`, master
seed 20261124 (fixed before the runs), database `monosplit`.

### Execution

- The first attempt (JPetStore, original names) ended with HTTP 401, "Incorrect API key". The
  VS Code process that started the run held an old `OPENAI_API_KEY`; the user's saved variable
  (HKEY_CURRENT_USER\Environment) held a newer key, and `llm/env.py` reads the process
  variable first. The attempt produced no model output and is stored as `api_error`. The run
  was resumed with the variable removed from the process (`env -u OPENAI_API_KEY`), so the
  saved key was used, with the same configuration. No code changed.
- Totals, timing and cost: see the paper and the Results page; they come from the database
  through `scripts/gerar_dados.py`.

### Article

The paper is generated from this database: `scripts/gerar_dados.py` reads `results_payload`
and writes the tables, the figure and every number quoted in the text (see the README,
section *Reproducing the paper*). The main run is `final`; `full` is reported as a second run of
the protocol (keys prefixed `rep-`, a table of both runs' pooled tests and the agreement between
them). Both gave the same outcome in the 16 pooled comparisons and the same 4 pooled verdicts;
per application, 3 of the 16 verdicts differ, each through one condition (NED against the
random partition, or SM against AH).
