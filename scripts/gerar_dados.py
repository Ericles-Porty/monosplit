"""Generate the data of the paper from the study database: tables, figure and the numbers of the text.

No result number of the paper is typed by hand. This script reads the database through the same
functions as the Results page of the web interface (monosplit.api.payloads.results_payload) and
writes LaTeX fragments that the paper includes with \\input.

Usage, from the root of this package, with MongoDB running (`docker compose up -d`) and the
database restored from the dump (`uv run python -m monosplit db restore dump`):

    uv run python scripts/gerar_dados.py                    # English, in work/paper-data/en/
    uv run python scripts/gerar_dados.py --idioma pt        # Portuguese, in work/paper-data/pt/
    uv run python scripts/gerar_dados.py --saida <folder>   # another output folder

By default the main run is the experiment `final` and the second run of the protocol is the
experiment `full` (keys prefixed rep-); see --experiment, --replicacao and --profile. The
Portuguese output translates the labels and uses a decimal comma, written as {,} so that it
works both in text and in math mode.

Files written:

    numeros.tex            \\dado{key}: every number quoted in the text (attempts, cost, p, delta...)
    tab_execucoes.tex      LLM runs per application and name variant
    tab_descritiva.tex     median and interquartile range of the metrics per method
    tab_testes.tex         paired tests, Holm adjustment and Cliff's delta (four applications pooled)
    tab_criterio.tex       conditions of the comparison criterion, per variant and control
    tab_ah.tex             median SM of the six AH variants, of the LLM and of the random partition
    tab_por_aplicacao.tex  tests of each application alone (10 pairs)
    tab_replicacao.tex     pooled tests of the main run and of the second run
    fig_diferencas.tex     figure of the paired differences (pgfplots)
    resultados.json        the complete payload used, for checking

Run the script again whenever the database changes. In the course repository, the paper reads
the output of `--saida ../entregas/03-artigo/dados` (and `dados_pt` for --idioma pt).
"""
from __future__ import annotations

import argparse
import json
import statistics
import zlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from monosplit.api.payloads import results_payload, study_key
from monosplit.paths import WORK_DIR
from monosplit.store import open_store

APPS = ("jpetstore", "acmeair", "daytrader", "plants")
APP_NAMES = {"jpetstore": "JPetStore", "acmeair": "AcmeAir", "daytrader": "DayTrader", "plants": "Plants"}
VARIANTS = ("original", "obfuscated")
CONTROLS = ("ah", "random")
METRICS = ("sm", "ifn", "icp", "ned")
METRIC_NAMES = {"sm": "SM", "ifn": "IFN", "icp": "ICP", "ned": "NED"}
AH_ORDER = ("calls:average", "calls:complete", "calls:single",
            "neighbors:average", "neighbors:complete", "neighbors:single")
LOCAL = timezone(timedelta(hours=-3))  # Brasilia time (UTC-3), where the runs were made

# Language of the output, set in main() by --idioma.
IDIOMA = "en"

MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro")

TEXTOS = {
    "en": {
        "variant_title": {"original": "Original names", "obfuscated": "Obfuscated names"},
        "variant_cell": {"original": "original", "obfuscated": "obfuscated"},
        "variant_short": {"original": "Original", "obfuscated": "Obfuscated"},
        "control_label": {"ah": "AH", "random": "Random"},
        "control_vs": {"ah": "AH", "random": "Random"},
        "magnitude_letter": {"negligible": "N", "small": "S", "medium": "M", "large": "L", None: "--"},
        "magnitude_word": {"negligible": "negligible", "small": "small", "medium": "medium", "large": "large"},
        "test_word": {"wilcoxon": "Wilcoxon", "t": "paired $t$", "none": "none"},
        "neither": "neither",
        "yes": "yes",
        "no": "no",
        "no_reasons": "none",
        "runs_header": ("Application & Names & Attempts & Invalid & Median & Range & Distinct & Mean ARI & "
                        "Cost (US\\$)"),
        "desc_header": ("Application & Method & SM $\\uparrow$ & IFN $\\downarrow$ & ICP $\\downarrow$ & "
                        "NED $\\downarrow$"),
        "tests_header": ("Metric & SW $p$ & Test & Location of $d$ & $p$ & $p_{\\mathrm{Holm}}$ & "
                         "Cliff's $\\delta$ & Favours"),
        "crit_condition": "Condition",
        "crit_columns": "Names & Control",
        "perapp_columns": "Application",
        "ah_header": "Method",
        "distance": {"calls": "calls", "neighbors": "neighbors"},
        "linkage": {"average": "average", "complete": "complete", "single": "single"},
        "control_mark": " (control)",
        "fig_rows": "{Obf.\\ vs.\\ Random, Obf.\\ vs.\\ AH, Orig.\\ vs.\\ Random, Orig.\\ vs.\\ AH}",
        "fig_higher": "higher is better",
        "fig_lower": "lower is better",
        "fig_xlabel": "$d$ = LLM $-$ control; {side} favours the LLM",
        "fig_number_format": "/pgf/number format/fixed",
        "rep_columns": "Names & Control & Run",
        "rep_favours": "Fav.",
        "rep_case": "{app} with {variant} names against {control} (held only in {run})",
        "rep_control": {"ah": "AH", "random": "the random partition"},
        "rep_join": lambda xs: xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1],
    },
    "pt": {
        "variant_title": {"original": "Nomes originais", "obfuscated": "Nomes ofuscados"},
        "variant_cell": {"original": "originais", "obfuscated": "ofuscados"},
        "variant_short": {"original": "Originais", "obfuscated": "Ofuscados"},
        "control_label": {"ah": "AH", "random": "Aleatória"},
        "control_vs": {"ah": "AH", "random": "aleatória"},
        "magnitude_letter": {"negligible": "D", "small": "P", "medium": "M", "large": "G", None: "--"},
        "magnitude_word": {"negligible": "desprezível", "small": "pequeno", "medium": "médio", "large": "grande"},
        "test_word": {"wilcoxon": "Wilcoxon", "t": "$t$ pareado", "none": "nenhum"},
        "neither": "nenhum",
        "yes": "sim",
        "no": "não",
        "no_reasons": "nenhuma",
        "runs_header": ("Aplicação & Nomes & Tentativas & Inválidas & Mediana & Faixa & Distintas & ARI médio & "
                        "Custo (US\\$)"),
        "desc_header": ("Aplicação & Método & SM $\\uparrow$ & IFN $\\downarrow$ & ICP $\\downarrow$ & "
                        "NED $\\downarrow$"),
        "tests_header": ("Métrica & $p$ (SW) & Teste & Localização de $d$ & $p$ & $p_{\\mathrm{Holm}}$ & "
                         "$\\delta$ de Cliff & Favorece"),
        "crit_condition": "Condição",
        "crit_columns": "Nomes & Controle",
        "perapp_columns": "Aplicação",
        "ah_header": "Método",
        "distance": {"calls": "chamadas", "neighbors": "vizinhança"},
        "linkage": {"average": "média", "complete": "completa", "single": "simples"},
        "control_mark": " (controle)",
        "fig_rows": "{Ofusc.\\ vs.\\ aleatória, Ofusc.\\ vs.\\ AH, Orig.\\ vs.\\ aleatória, Orig.\\ vs.\\ AH}",
        "fig_higher": "maior é melhor",
        "fig_lower": "menor é melhor",
        "fig_xlabel": "{side} favorece o LLM",
        "fig_number_format": "/pgf/number format/fixed, /pgf/number format/use comma",
        "rep_columns": "Nomes & Controle & Execução",
        "rep_favours": "Fav.",
        "rep_case": "{app} com nomes {variant} contra {control} (valeu só no {run})",
        "rep_control": {"ah": "o AH", "random": "a partição aleatória"},
        "rep_join": lambda xs: xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " e " + xs[-1],
    },
}


def tx(chave: str):
    """Text in the output language."""
    return TEXTOS[IDIOMA][chave]


# ------------------------------------------------------------------ formatacao

def loc(numero: str) -> str:
    """Separators of the output language. In Portuguese, a thousands point and a decimal comma, written as {,}."""
    if IDIOMA != "pt":
        return numero
    return numero.replace(",", "\0").replace(".", "{,}").replace("\0", ".")


def signed(text: str) -> str:
    """Use the LaTeX minus sign and drop the sign of a rounded zero (-0.000)."""
    if text.startswith("-") and float(text) == 0:
        text = text[1:]
    return loc(text).replace("-", "\\textminus ")


def f3(x: float | None) -> str:
    return "--" if x is None else signed(f"{x:.3f}")


def f2(x: float | None) -> str:
    return "--" if x is None else signed(f"{x:.2f}")


def fp(p: float | None) -> str:
    """p-value: three decimals, or < 0.001."""
    if p is None:
        return "--"
    return loc("$<$0.001" if p < 0.001 else f"{p:.3f}")


def fstat(test: str, s: float | None) -> str:
    if s is None:
        return "--"
    return loc(f"{s:.0f}") if test == "wilcoxon" else signed(f"{s:.2f}")


def tex_escape(text: str) -> str:
    return text.replace("_", "\\_").replace("%", "\\%").replace("&", "\\&")


def run_date(dt: datetime) -> str:
    if IDIOMA == "pt":
        return f"{dt.day} de {MESES[dt.month - 1]} de {dt.year}"
    return f"{dt:%B} {dt.day}, {dt.year}"


class Numbers:
    """Collection of \\dado{key}{value}."""

    def __init__(self) -> None:
        self.items: dict[str, str] = {}

    def __setitem__(self, key: str, value) -> None:
        self.items[key] = str(value)

    def merge(self, other: "Numbers", prefix: str) -> None:
        """Add the keys of another collection with a prefix (second run: rep-)."""
        for key, value in other.items.items():
            self.items[f"{prefix}{key}"] = value

    def write(self, path: Path) -> None:
        lines = ["% Gerado por gerar_dados.py. Nao edite: rode o script de novo.",
                 "\\providecommand{\\dado}[1]{\\csname dado@#1\\endcsname}"]
        for key, value in sorted(self.items.items()):
            lines.append(f"\\expandafter\\def\\csname dado@{key}\\endcsname{{{value}}}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ leitura

def load(experiment: str, profile: str) -> tuple[dict, dict]:
    store = open_store()
    payload = results_payload(store, experiment, profile)
    extra: dict = {"metas": {}, "attempts": {}, "partitions": {}, "runs": {}}
    for app in APPS:
        for variant in VARIANTS:
            key = study_key(experiment, app, profile, variant)
            doc = store.variant(key)
            extra["metas"][(app, variant)] = doc["meta"] if doc else None
            extra["attempts"][(app, variant)] = store.attempts(key)
            extra["runs"][(app, variant)] = store.accepted_runs(key)
        evaluation = store.evaluation(study_key(experiment, app, profile)) or {}
        extra["partitions"][app] = evaluation.get("partitions") or []
    return payload, extra


def service_sizes(row: dict) -> list[int]:
    """Service sizes of a measured partition (list of [class, service] pairs)."""
    counts: dict = defaultdict(int)
    for _cls, service in row.get("partition") or []:
        counts[service] += 1
    return sorted(counts.values(), reverse=True)


# ------------------------------------------------------------------ numeros

def numbers_from(payload: dict, extra: dict) -> Numbers:
    n = Numbers()
    n["model"] = payload["model"]
    n["effort"] = payload["request_options"].get("reasoning_effort", "")
    all_attempts = [r for rows in extra["attempts"].values() for r in rows]
    answered = [r for r in all_attempts if r["status"] in ("accepted", "invalid")]
    returned = sorted({r.get("model_returned") for r in answered if r.get("model_returned")})
    n["model-returned"] = ", ".join(f"\\texttt{{{tex_escape(m)}}}" for m in returned)
    n["n-model-returned"] = len(returned)
    stamps = sorted(datetime.fromisoformat(r["timestamp_utc"]) for r in all_attempts)
    first, last = stamps[0].astimezone(LOCAL), stamps[-1].astimezone(LOCAL)
    n["first-local"] = first.strftime("%Y-%m-%d %H:%M")
    n["last-local"] = last.strftime("%Y-%m-%d %H:%M")
    n["first-time"] = first.strftime("%H:%M")
    n["last-time"] = last.strftime("%H:%M")
    n["run-date"] = run_date(first)
    n["duration-min"] = f"{(last - first).total_seconds() / 60:.0f}"
    n["attempts-total"] = len(all_attempts)
    n["answered-total"] = len(answered)
    n["accepted-total"] = sum(r["status"] == "accepted" for r in all_attempts)
    n["invalid-total"] = sum(r["status"] == "invalid" for r in all_attempts)
    n["apierror-total"] = sum(r["status"] == "api_error" for r in all_attempts)
    cost = sum(r.get("cost_usd") or 0 for r in all_attempts)
    accepted = sum(r["status"] == "accepted" for r in all_attempts)
    n["cost-total"] = loc(f"{cost:.2f}")
    n["cost-per-run"] = loc(f"{cost / max(accepted, 1):.2f}")
    n["input-tokens-total"] = loc(f"{sum(r.get('input_tokens') or 0 for r in answered):,}")
    n["output-tokens-total"] = loc(f"{sum(r.get('output_tokens') or 0 for r in answered):,}")
    lat = [r["latency_s"] for r in answered if r.get("latency_s") is not None]
    n["latency-median"] = f"{statistics.median(lat):.0f}"
    n["latency-max"] = f"{max(lat):.0f}"
    metas = [m for m in extra["metas"].values() if m]
    n["sdk"] = tex_escape(metas[0]["sdk"])
    n["python"] = metas[0]["python"]
    n["platform"] = tex_escape(metas[0]["platform"])
    reasons = defaultdict(int)
    for r in all_attempts:
        if r["status"] == "invalid":
            reasons[r.get("reason") or "unknown"] += 1
    n["invalid-reasons"] = (", ".join(f"{tex_escape(k)} ({v})" for k, v in sorted(reasons.items()))
                            or tx("no_reasons"))

    edge_yes = edge_total = 0
    for app_row in payload["apps"]:
        es = (app_row.get("checks") or {}).get("edge_sample") or {}
        edge_yes += es.get("yes") or 0
        edge_total += es.get("total") or 0
    n["edgecheck-yes-total"] = edge_yes
    n["edgecheck-total"] = edge_total

    for app_row in payload["apps"]:
        app = app_row["app"]
        g = app_row["graph"] or {}
        n[f"{app}-classes"] = g.get("classes")
        n[f"{app}-edges"] = g.get("edges")
        n[f"{app}-calls"] = g.get("calls_in_graph")
        n[f"{app}-isolated"] = g.get("isolated_classes")
        checks = app_row.get("checks") or {}
        es = checks.get("edge_sample") or {}
        n[f"{app}-edgecheck-yes"] = es.get("yes")
        n[f"{app}-edgecheck-total"] = es.get("total")
        cov = checks.get("coverage") or {}
        n[f"{app}-coverage"] = f"{cov.get('covering')}/{cov.get('accepted')}"
        hc = checks.get("hand_check") or {}
        n[f"{app}-handcheck"] = f"{hc.get('matched')}/{hc.get('total')}"
        for v in app_row["variants"]:
            prefix = f"{app}-{v['variant']}"
            ks = [int(k) for k in str(v["k_accepted"]).split()]
            if not ks:
                continue
            n[f"{prefix}-attempts"] = v["attempts"]
            n[f"{prefix}-accepted"] = v["accepted"]
            n[f"{prefix}-invalid"] = v["invalid"]
            n[f"{prefix}-k-median"] = loc(f"{statistics.median(ks):g}")
            n[f"{prefix}-k-min"] = min(ks)
            n[f"{prefix}-k-max"] = max(ks)
            st = v.get("stability") or {}
            n[f"{prefix}-distinct"] = st.get("distinct_partitions")
            n[f"{prefix}-ari-mean"] = f2(st.get("mean_ari"))
            n[f"{prefix}-ari-min"] = f2(st.get("min_ari"))
            n[f"{prefix}-cost"] = loc(f"{v['cost_usd']:.2f}")

    for s in payload["metric_summaries"]:
        value = loc(f"{s['median']:g}") if s["metric"] == "k" else fmt(s["metric"], s["median"])
        n[f"{s['app']}-{s['variant']}-{s['method'].replace(':', '-')}-{s['metric']}-median"] = value

    # Size of the largest service (classes), per method, in the measured partitions of each run.
    for app in APPS:
        classes = next((a["graph"] or {}).get("classes") for a in payload["apps"] if a["app"] == app)
        for variant in VARIANTS:
            for method, label in (("llm", "llm"), ("ah:neighbors:complete", "ah"), ("random", "random")):
                largest = [service_sizes(r)[0] for r in extra["partitions"][app]
                           if r.get("method") == method and r.get("variant") == variant and r.get("partition")]
                if largest:
                    key = f"{app}-{variant}-{label}-largest"
                    n[f"{key}-median"] = loc(f"{statistics.median(largest):g}")
                    n[f"{key}-min"] = min(largest)
                    n[f"{key}-max"] = max(largest)
                    n[f"{key}-share"] = f"{100 * statistics.median(largest) / classes:.0f}"
            runs = extra["runs"][(app, variant)]
            if runs:
                # Runs that returned the most frequent partition (service names do not count).
                shapes = defaultdict(int)
                for r in runs:
                    shapes[frozenset(frozenset(s["classes"]) for s in r["services"])] += 1
                n[f"{app}-{variant}-modal-runs"] = max(shapes.values())
                first_run = min(runs, key=lambda r: r["run"])
                n[f"{app}-{variant}-run1-services"] = ", ".join(
                    f"\\texttt{{{tex_escape(s['name'])}}} ({len(s['classes'])})" for s in first_run["services"])

    # HDBSCAN: one partition per application and distance, with its own K (descriptive reference).
    for r in payload["metrics"]:
        if r["method"].startswith("hdbscan"):
            key = f"{r['app']}-{r['method'].replace(':', '-')}"
            n[f"{key}-k"] = r["k"]
            n[f"{key}-noise"] = r.get("noise_points")
            for m in METRICS:
                n[f"{key}-{m}"] = fmt(m, r[m])

    pooled = defaultdict(list)
    for r in payload["metrics"]:
        if r["variant"] in VARIANTS:
            for m in ("k", *METRICS):
                if r.get(m) is not None:
                    pooled[(r["variant"], r["method"], m)].append(r[m])
    for (variant, method, m), values in pooled.items():
        n[f"all-{variant}-{method.replace(':', '-')}-{m}-median"] = fmt(m, statistics.median(values)) if m != "k" \
            else loc(f"{statistics.median(values):g}")

    used = [c["test"] for b in payload["tests"] or [] if b["scope"] == "all" for c in b["comparisons"]]
    n["tests-total"] = len(used)
    n["tests-wilcoxon"] = used.count("wilcoxon")
    n["tests-t"] = used.count("t")

    for s in payload["difference_summaries"]:
        key = f"d-{s['scope']}-{s['variant']}-{s['control']}-{s['metric']}"
        n[f"{key}-median"] = f3(s["median"])
        n[f"{key}-pos"] = s["positive"]
        n[f"{key}-neg"] = s["negative"]
        n[f"{key}-zero"] = s["zero"]
        n[f"{key}-n"] = s["n"]

    for block in payload["tests"] or []:
        for c in block["comparisons"]:
            key = f"t-{block['scope']}-{block['variant']}-{c['control']}-{c['metric']}"
            n[f"{key}-test"] = tx("test_word").get(c["test"], c["test"])
            n[f"{key}-p"] = fp(c["p_value"])
            n[f"{key}-pholm"] = fp(c["p_holm"])
            n[f"{key}-sw"] = fp(c["normality_p"])
            n[f"{key}-delta"] = f2(c["cliffs_delta"])
            n[f"{key}-mag"] = tx("magnitude_word").get(c["magnitude"], "--")
            n[f"{key}-mediand"] = f3(c["median_diff"])
            n[f"{key}-meand"] = f3(c["mean_diff"])
            n[f"{key}-favours"] = {"llm": "LLM", "control": tx("control_label")[c["control"]],
                                   "none": tx("neither")}[c["favours"]]
            n[f"{key}-sig"] = tx("yes") if c["significant"] else tx("no")
        for control, crit in (block["criterion"] or {}).items():
            if crit is None:
                continue
            key = f"c-{block['scope']}-{block['variant']}-{control}"
            for field, value in crit.items():
                n[f"{key}-{field}"] = tx("yes") if value else tx("no")
    return n


# ------------------------------------------------------------------ tabelas

def tick(value: bool) -> str:
    return "\\ding{51}" if value else "\\ding{55}"


def table_runs(payload: dict) -> str:
    rows = []
    for app in APPS:
        app_row = next((a for a in payload["apps"] if a["app"] == app), None)
        if app_row is None:
            continue
        for i, v in enumerate(app_row["variants"]):
            ks = [int(k) for k in str(v["k_accepted"]).split()]
            if not ks:
                continue
            st = v.get("stability") or {}
            first = APP_NAMES[app] if i == 0 else ""
            names = tx("variant_cell")[v["variant"]]
            k_median = loc(format(statistics.median(ks), "g"))
            cost = loc(format(v["cost_usd"], ".2f"))
            rows.append(
                f"{first} & {names} & {v['attempts']} & {v['invalid']} & {k_median} & {min(ks)}--{max(ks)} & "
                f"{st.get('distinct_partitions')} & {f2(st.get('mean_ari'))} & {cost} \\\\")
        rows.append("\\addlinespace")
    body = "\n".join(rows[:-1])
    return ("% Gerado por gerar_dados.py.\n"
            "\\setlength{\\tabcolsep}{3.8pt}\n"
            "\\begin{tabular}{@{}llrrrrrrr@{}}\n\\toprule\n"
            " & & & & \\multicolumn{2}{c}{$K$} & & & \\\\\n"
            "\\cmidrule(lr){5-6}\n"
            f"{tx('runs_header')} \\\\\n"
            "\\midrule\n" + body + "\n\\bottomrule\n\\end{tabular}\n")


DECIMALS = {"sm": 3, "ifn": 2, "icp": 3, "ned": 2}


def fmt(metric: str, x: float | None) -> str:
    if x is None:
        return "--"
    return signed(f"{x:.{DECIMALS[metric]}f}")


def table_descriptive(payload: dict) -> str:
    summ = {(s["app"], s["variant"], s["method"], s["metric"]): s for s in payload["metric_summaries"]}
    ah = "ah:neighbors:complete"
    methods = (("llm", "LLM"), (ah, "AH"), ("random", tx("control_label")["random"]))
    lines = []
    for variant in VARIANTS:
        lines.append(f"\\multicolumn{{6}}{{@{{}}l}}{{\\textit{{{tx('variant_title')[variant]}}}}} \\\\")
        for app in APPS:
            for i, (method, label) in enumerate(methods):
                cells = []
                for m in METRICS:
                    s = summ.get((app, variant, method, m))
                    cells.append("--" if s is None else f"{fmt(m, s['median'])} ({fmt(m, s['iqr'])})")
                first = APP_NAMES[app] if i == 0 else ""
                lines.append(f"{first} & {label} & " + " & ".join(cells) + " \\\\")
            lines.append("\\addlinespace")
        lines.append("\\midrule")
    body = "\n".join(lines[:-2])
    return ("% Gerado por gerar_dados.py.\n"
            "\\begin{tabular}{@{}llrrrr@{}}\n\\toprule\n"
            f"{tx('desc_header')} \\\\\n"
            "\\midrule\n" + body + "\n\\bottomrule\n\\end{tabular}\n")


def table_tests(payload: dict) -> str:
    blocks = {(b["scope"], b["variant"]): b for b in payload["tests"] or []}
    lines = []
    for variant in VARIANTS:
        block = blocks.get(("all", variant))
        if block is None:
            continue
        for control in CONTROLS:
            lines.append(f"\\multicolumn{{8}}{{@{{}}l}}{{\\textit{{{tx('variant_title')[variant]}: LLM vs.\\ "
                         f"{tx('control_vs')[control]}}}}} \\\\")
            for metric in METRICS:
                c = next(r for r in block["comparisons"] if r["control"] == control and r["metric"] == metric)
                test = {"wilcoxon": "W", "t": "$t$", "none": "--"}.get(c["test"], c["test"])
                location = c["mean_diff"] if c["test"] == "t" else c["median_diff"]
                favours = {"llm": "LLM", "control": tx("control_label")[control], "none": "--"}[c["favours"]]
                if not c["significant"]:
                    favours = "--"
                p_holm = fp(c["p_holm"])
                if c["significant"]:
                    p_holm = f"\\textbf{{{p_holm}}}"
                lines.append(
                    f"\\quad {METRIC_NAMES[metric]} & {fp(c['normality_p'])} & {test} & {f3(location)} & "
                    f"{fp(c['p_value'])} & {p_holm} & {f2(c['cliffs_delta'])} "
                    f"{tx('magnitude_letter')[c['magnitude']]} & {favours} \\\\")
            lines.append("\\addlinespace")
        lines.append("\\midrule")
    body = "\n".join(lines[:-2])
    return ("% Gerado por gerar_dados.py.\n"
            "\\begin{tabular}{@{}lrcrrrlc@{}}\n\\toprule\n"
            f"{tx('tests_header')} \\\\\n\\midrule\n" + body + "\n\\bottomrule\n\\end{tabular}\n")


def table_criterion(payload: dict) -> str:
    blocks = {(b["scope"], b["variant"]): b for b in payload["tests"] or []}
    lines = []
    for variant in VARIANTS:
        block = blocks.get(("all", variant))
        if block is None:
            continue
        for control in CONTROLS:
            c = (block["criterion"] or {}).get(control)
            if c is None:
                continue
            lines.append(
                f"{tx('variant_short')[variant]} & {tx('control_label')[control]} & {tick(c['sm_favours_llm'])} & "
                f"{tick(c['sm_effect_at_least_small'])} & {tick(c['no_unfavourable_ifn_icp'])} & "
                f"{tick(c['no_unfavourable_ned'])} & {tx('yes') if c['llm_superior'] else tx('no')} & "
                f"{tx('yes') if c['llm_superior_roteiro'] else tx('no')} \\\\")
    return ("% Gerado por gerar_dados.py.\n"
            "\\begin{tabular}{@{}llcccccc@{}}\n\\toprule\n"
            f" & & \\multicolumn{{4}}{{c}}{{{tx('crit_condition')}}} & \\multicolumn{{2}}{{c}}{{LLM superior}} \\\\\n"
            "\\cmidrule(lr){3-6}\\cmidrule(l){7-8}\n"
            f"{tx('crit_columns')} & (i) & (ii) & (iii) & (iv) & (i)--(iv) & (i)--(iii) \\\\\n"
            "\\midrule\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n")


def table_per_app(payload: dict) -> str:
    """Tests of each application alone (10 pairs per row, Holm over the eight rows).

    Each cell has one symbol per metric, in the order SM, IFN, ICP, NED: + significant
    difference in favour of the LLM, \\textminus{} in favour of the control, 0 not significant.
    The dagger marks the cells where the adopted criterion, (i) to (iv), holds.
    """
    blocks = {(b["scope"], b["variant"]): b for b in payload["tests"] or []}
    symbol = {"llm": "+", "control": "$-$"}
    lines = []
    for app in APPS:
        cells = []
        for variant in VARIANTS:
            block = blocks.get((app, variant))
            for control in CONTROLS:
                if block is None:
                    cells.append("--")
                    continue
                marks = []
                for metric in METRICS:
                    c = next(r for r in block["comparisons"] if r["control"] == control and r["metric"] == metric)
                    marks.append(symbol[c["favours"]] if c["significant"] else "0")
                crit = (block["criterion"] or {}).get(control) or {}
                dagger = "$^\\dagger$" if crit.get("llm_superior") else "\\phantom{$^\\dagger$}"
                cells.append("\\,".join(marks) + dagger)
        lines.append(f"{APP_NAMES[app]} & " + " & ".join(cells) + " \\\\")
    vs_ah = "LLM vs.\\ AH"
    vs_random = f"LLM vs.\\ {tx('control_vs')['random']}"
    return ("% Gerado por gerar_dados.py.\n"
            "\\begin{tabular}{@{}lcccc@{}}\n\\toprule\n"
            f" & \\multicolumn{{2}}{{c}}{{{tx('variant_title')['original']}}} & "
            f"\\multicolumn{{2}}{{c}}{{{tx('variant_title')['obfuscated']}}} \\\\\n"
            "\\cmidrule(lr){2-3}\\cmidrule(l){4-5}\n"
            f"{tx('perapp_columns')} & {vs_ah} & {vs_random} & {vs_ah} & {vs_random} \\\\\n\\midrule\n"
            + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n")


def table_ah(payload: dict) -> str:
    summ = {(s["app"], s["variant"], s["method"], s["metric"]): s for s in payload["metric_summaries"]}

    def ah_label(variant: str) -> str:
        distance, linkage = variant.split(":")
        return f"AH, {tx('distance')[distance]}, {tx('linkage')[linkage]}"

    rows = ([("llm", "LLM")] + [(f"ah:{v}", ah_label(v)) for v in AH_ORDER]
            + [("random", tx("control_label")["random"])])
    lines = []
    for method, label in rows:
        cells = []
        for app in APPS:
            s = summ.get((app, "original", method, "sm"))
            cells.append("--" if s is None else f3(s["median"]))
        if method == "ah:neighbors:complete":
            label += tx("control_mark")
        lines.append(f"{label} & " + " & ".join(cells) + " \\\\")
    header = " & ".join(APP_NAMES[a] for a in APPS)
    return ("% Gerado por gerar_dados.py.\n"
            "\\begin{tabular}{@{}lrrrr@{}}\n\\toprule\n"
            f"{tx('ah_header')} & {header} \\\\\n\\midrule\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n")


def outcomes(payload: dict) -> tuple[dict, dict, dict]:
    """Outcome of each comparison (LLM, control or none), magnitude of delta and verdict of the
    adopted criterion, by (scope, variant, control[, metric])."""
    result, magnitude, verdict = {}, {}, {}
    for block in payload["tests"] or []:
        for c in block["comparisons"]:
            key = (block["scope"], block["variant"], c["control"], c["metric"])
            result[key] = c["favours"] if c["significant"] else "none"
            magnitude[key] = c["magnitude"]
        for control, crit in (block["criterion"] or {}).items():
            if crit is not None:
                verdict[(block["scope"], block["variant"], control)] = crit["llm_superior"]
    return result, magnitude, verdict


def replication_numbers(main: dict, rep: dict) -> Numbers:
    """Agreement between the main run and the second run of the protocol."""
    n = Numbers()
    res_m, mag_m, ver_m = outcomes(main)
    res_r, mag_r, ver_r = outcomes(rep)
    for scope, label in (("all", "all"), ("app", "app")):
        def pick(keys):
            return [k for k in keys if (k[0] == "all") == (scope == "all")]
        comps = pick(res_m)
        verdicts = pick(ver_m)
        n[f"rep-agree-sig-{label}"] = sum(res_m[k] == res_r.get(k) for k in comps)
        n[f"rep-n-sig-{label}"] = len(comps)
        n[f"rep-agree-mag-{label}"] = sum(mag_m[k] == mag_r.get(k) for k in comps)
        n[f"rep-agree-crit-{label}"] = sum(ver_m[k] == ver_r.get(k) for k in verdicts)
        n[f"rep-n-crit-{label}"] = len(verdicts)
    cases = []
    for app in APPS:
        for variant in VARIANTS:
            for control in CONTROLS:
                key = (app, variant, control)
                if key in ver_m and ver_m[key] != ver_r.get(key):
                    cases.append(tx("rep_case").format(app=APP_NAMES[app], variant=tx("variant_cell")[variant],
                                                       control=tx("rep_control")[control],
                                                       run="\\texttt{final}" if ver_m[key] else "\\texttt{full}"))
    n["rep-crit-app-diff"] = tx("rep_join")(cases) if cases else tx("no_reasons")
    return n


def table_replication(main: dict, rep: dict) -> str:
    """Pooled test of each comparison in the two runs of the protocol: Cliff's delta and the
    method favoured by a significant difference (-- when not significant)."""
    def cell(payload: dict, variant: str, control: str, metric: str) -> str:
        block = next(b for b in payload["tests"] if b["scope"] == "all" and b["variant"] == variant)
        c = next(r for r in block["comparisons"] if r["control"] == control and r["metric"] == metric)
        favours = {"llm": "LLM", "control": tx("control_label")[control], "none": "--"}[c["favours"]]
        return f"{f2(c['cliffs_delta'])} & {favours if c['significant'] else '--'}"

    lines = []
    for variant in VARIANTS:
        for control in CONTROLS:
            label = f"{tx('variant_short')[variant]} & {tx('control_label')[control]}"
            for run, payload in (("\\texttt{final}", main), ("\\texttt{full}", rep)):
                cells = " & ".join(cell(payload, variant, control, m) for m in METRICS)
                lines.append(f"{label} & {run} & {cells} \\\\")
                label = " & "
            lines.append("\\addlinespace")
    metrics = " & ".join(f"\\multicolumn{{2}}{{c}}{{{METRIC_NAMES[m]}}}" for m in METRICS)
    rules = "".join(f"\\cmidrule(lr){{{4 + 2 * i}-{5 + 2 * i}}}" for i in range(len(METRICS)))
    sub = " & ".join(["$\\delta$ & " + tx("rep_favours")] * len(METRICS))
    return ("% Gerado por gerar_dados.py.\n"
            "\\setlength{\\tabcolsep}{4pt}\n"
            "\\begin{tabular}{@{}lll" + "rl" * len(METRICS) + "@{}}\n\\toprule\n"
            f" & & & {metrics} \\\\\n{rules}\n"
            f"{tx('rep_columns')} & {sub} \\\\\n\\midrule\n"
            + "\n".join(lines[:-1]) + "\n\\bottomrule\n\\end{tabular}\n")


# ------------------------------------------------------------------ figura

MARKS = {"jpetstore": "*", "acmeair": "square*", "daytrader": "triangle*", "plants": "diamond*"}
ROWS = [("original", "ah"), ("original", "random"), ("obfuscated", "ah"), ("obfuscated", "random")]


def jitter(*parts) -> float:
    """Deterministic vertical offset in [-0.28, 0.28], so that the markers do not overlap."""
    h = zlib.crc32("/".join(map(str, parts)).encode()) / 0xFFFFFFFF
    return (h - 0.5) * 0.56


def figure_differences(payload: dict) -> str:
    diffs = payload["differences"]
    summaries = {(s["scope"], s["variant"], s["control"], s["metric"]): s for s in payload["difference_summaries"]}
    y_of = {row: len(ROWS) - i for i, row in enumerate(ROWS)}
    out = ["% Gerado por gerar_dados.py.",
           "\\begin{tikzpicture}",
           "\\begin{groupplot}[group style={group size=2 by 2, horizontal sep=5mm, vertical sep=20mm, "
           "yticklabels at=edge left},",
           "  scale only axis, width=52mm, height=34mm, ymin=0.45, ymax=4.55, ytick={1,2,3,4},",
           f"  yticklabels={tx('fig_rows')},",
           "  tick label style={font=\\scriptsize}, label style={font=\\scriptsize}, title style={font=\\small},",
           "  axis line style={draw=axisgray}, tick style={draw=axisgray}, ytick style={draw=none},",
           "  xmajorgrids, grid style={draw=gridgray, line width=0.3pt}, scaled x ticks=false,",
           f"  x tick label style={{{tx('fig_number_format')}}}]"]
    for metric in METRICS:
        direction = tx("fig_higher") if metric == "sm" else tx("fig_lower")
        side = "$d>0$" if metric == "sm" else "$d<0$"
        out.append(f"\\nextgroupplot[title={{{METRIC_NAMES[metric]} ({direction})}}, "
                   f"xlabel={{{tx('fig_xlabel').format(side=side)}}}]")
        out.append("\\addplot[draw=zerogray, dashed, line width=0.6pt] coordinates {(0,0.45) (0,4.55)};")
        for (variant, control) in ROWS:
            y = y_of[(variant, control)]
            color = "ahcolor" if control == "ah" else "randomcolor"
            for app in APPS:
                pts = [(d[f"d_{metric}"], y + jitter(app, d["run"], variant, control, metric))
                       for d in diffs if d["variant"] == variant and d["control"] == control and d["app"] == app
                       and d[f"d_{metric}"] is not None]
                if not pts:
                    continue
                coords = " ".join(f"({x:.5f},{yy:.3f})" for x, yy in pts)
                out.append(f"\\addplot[only marks, mark={MARKS[app]}, color={color}, mark size=2.1pt, "
                           f"mark options={{draw=white, line width=0.3pt}}] coordinates {{{coords}}};")
            s = summaries.get(("all", variant, control, metric))
            if s is not None:
                out.append(f"\\addplot[draw=inkcolor, line width=1.4pt] coordinates "
                           f"{{({s['median']:.5f},{y - 0.38:.2f}) ({s['median']:.5f},{y + 0.38:.2f})}};")
    out.append("\\end{groupplot}")
    out.append("\\end{tikzpicture}")
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ main

def main() -> None:
    global IDIOMA
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment", default="final", help="main run of the paper (default: final)")
    parser.add_argument("--replicacao", default="full",
                        help="second run of the same protocol, keys prefixed rep- (default: full); empty for none")
    parser.add_argument("--profile", default="gpt-6.1-sol-high", help="LLM profile (default: gpt-6.1-sol-high)")
    parser.add_argument("--idioma", choices=sorted(TEXTOS), default="en",
                        help="output language: en (the paper) or pt (Portuguese study version, decimal comma)")
    parser.add_argument("--saida", default=None,
                        help="output folder, relative to the current folder (default: work/paper-data/<idioma>)")
    args = parser.parse_args()
    IDIOMA = args.idioma
    out = Path(args.saida).resolve() if args.saida else WORK_DIR / "paper-data" / IDIOMA
    out.mkdir(parents=True, exist_ok=True)

    payload, extra = load(args.experiment, args.profile)
    if not payload["analysis"]["inferential"]:
        raise SystemExit("The experiment does not have the tests turned on (inferential = false).")
    numbers = numbers_from(payload, extra)
    if args.replicacao:
        rep_payload, rep_extra = load(args.replicacao, args.profile)
        numbers.merge(numbers_from(rep_payload, rep_extra), "rep-")
        numbers.merge(replication_numbers(payload, rep_payload), "")
        (out / "tab_replicacao.tex").write_text(table_replication(payload, rep_payload), encoding="utf-8")
    numbers.write(out / "numeros.tex")
    (out / "tab_execucoes.tex").write_text(table_runs(payload), encoding="utf-8")
    (out / "tab_descritiva.tex").write_text(table_descriptive(payload), encoding="utf-8")
    (out / "tab_testes.tex").write_text(table_tests(payload), encoding="utf-8")
    (out / "tab_criterio.tex").write_text(table_criterion(payload), encoding="utf-8")
    (out / "tab_ah.tex").write_text(table_ah(payload), encoding="utf-8")
    (out / "tab_por_aplicacao.tex").write_text(table_per_app(payload), encoding="utf-8")
    (out / "fig_diferencas.tex").write_text(figure_differences(payload), encoding="utf-8")
    (out / "resultados.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                                         encoding="utf-8")
    print(f"data written to {out}")


if __name__ == "__main__":
    main()
