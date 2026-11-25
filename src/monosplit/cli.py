"""Command line of the experiment. Run from the experimento/ folder.

`uv run python -m monosplit ...` works everywhere; `uv run monosplit ...` uses the
generated launcher, which Windows application control may block.

The configuration, runs and results are stored in MongoDB: start it with
`docker compose up -d` in experimento/ (see compose.yaml and the README). Experiments and
LLM profiles are named as on the Configuration page.

Examples:
    uv run python -m monosplit db status
    uv run python -m monosplit jdk install
    uv run python -m monosplit app fetch jpetstore
    uv run python -m monosplit extract jpetstore
    uv run python -m monosplit edge-sample jpetstore
    uv run python -m monosplit prompt --experiment pilot --variant obfuscated
    uv run python -m monosplit all --experiment dry_run
    uv run python -m monosplit all --experiment pilot --llm gpt-5.6-luna
    uv run python -m monosplit db dump dump
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__


def _profile(config, override: str | None):
    from .config import load_profile

    name = override or config.llm_profile
    if name is None:
        raise SystemExit("No LLM profile: pass --llm <profile> or set the default profile of the experiment")
    return load_profile(name)


def cmd_jdk(args) -> None:
    from .extraction.jdk import find_jdk, install_jdk, jdk_version

    home = install_jdk(force=args.force) if args.action == "install" else find_jdk()
    if home is None:
        raise SystemExit("No JDK installed. Run `uv run monosplit jdk install`.")
    print(home)
    print(jdk_version(home))


def cmd_app(args) -> None:
    from .apps import build, fetch, get_app

    app = get_app(args.app)
    if args.action == "fetch":
        print(fetch(app))
    else:
        print(f"Build log: {build(app)}")


def cmd_extract(args) -> None:
    from .operations import extract_app

    stats = extract_app(args.app, print, build_first=not args.skip_build, with_edge_sample=False)
    print(json.dumps(stats))


def cmd_edge_sample(args) -> None:
    from .operations import sample_edges

    size = sample_edges(args.app, args.n, args.seed)
    print(f"{size} edges stored for {args.app}; check them on the Data page of the web interface.")


def cmd_providers(_args) -> None:
    from .llm import providers

    print("\n".join(providers()))


def cmd_prompt(args) -> None:
    from .config import load_config
    from .prompting import load_prompt, variant_graph
    from .runner import obfuscation_seed

    config = load_config(args.experiment)
    graph = config.graph()
    prompt_graph, _ = variant_graph(graph, args.variant, obfuscation_seed(config))
    system, user = load_prompt(config.prompt_template).render(prompt_graph)
    print(f"=== system\n{system}\n=== user\n{user}")


def _run(config, profile, variants) -> None:
    from .operations import run_llm

    run_llm(config, profile, list(variants), print)


def cmd_run(args) -> None:
    from .config import load_config

    config = load_config(args.experiment)
    _run(config, _profile(config, args.llm), args.variant or config.variants)


def cmd_evaluate(args) -> None:
    from .config import load_config
    from .evaluate import evaluate

    config = load_config(args.experiment)
    evaluation = evaluate(config, _profile(config, args.llm).name)
    print(f"evaluation {evaluation} stored in database {config.database}")


def cmd_report(args) -> None:
    from .config import load_config
    from .report import write_report

    config = load_config(args.experiment)
    print(write_report(config, _profile(config, args.llm).name))


def cmd_web(args) -> None:
    from .paths import WORK_DIR, resolve
    from .store import open_store

    store = open_store(args.database)  # fails early, with instructions, when MongoDB is down
    if args.action == "serve":
        from .api.server import serve

        print(f"monosplit web interface: http://{args.host}:{args.port}/  (database: {store.database}; Ctrl+C stops)")
        serve(args.database, host=args.host, port=args.port, open_browser=args.open)
    else:
        from .api.export import export_site

        out = resolve(args.out) if args.out else WORK_DIR / "site"
        counts = export_site(out, store)
        print(f"{out}: {counts['graphs']} graph(s), {counts['studies']} study(ies), {counts['runs']} run(s), {counts['results']} result set(s)")


def cmd_db(args) -> None:
    from . import dbtools
    from .paths import resolve
    from .store import open_store, uri

    store = open_store(args.database)
    if args.action == "status":
        print(f"{uri()} database {store.database} (configuration and graphs in {store.graph_database})")
        print(json.dumps(store.counts(), indent=2))
    elif args.action == "import-config":
        root = resolve(args.folder or ".")
        print(json.dumps(dbtools.import_config(open_store(), root), indent=2))
    elif args.action == "import":
        print(json.dumps(dbtools.import_folder(store, resolve(args.folder or "data")), indent=2))
    elif args.action == "dump":
        out = resolve(args.folder or "dump")
        counts = dbtools.dump(store, out)
        print(f"{out / store.database}: {json.dumps(counts)}")
    else:
        source = resolve(args.folder or "dump") / store.database
        print(json.dumps(dbtools.restore(store, source), indent=2))


def cmd_pilot(args) -> None:
    from .config import load_config
    from .evaluate import evaluate
    from .report import write_report

    config = load_config(args.experiment)
    profile = _profile(config, args.llm)
    _run(config, profile, config.variants)
    evaluate(config, profile.name)
    print(write_report(config, profile.name))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="monosplit", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"monosplit {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("jdk", help="install or show the pinned JDK (Temurin 21)")
    p.add_argument("action", choices=["install", "show"])
    p.add_argument("--force", action="store_true", help="download again even if installed")
    p.set_defaults(func=cmd_jdk)

    p = sub.add_parser("app", help="clone an application at its pinned commit, or compile it")
    p.add_argument("action", choices=["fetch", "build"])
    p.add_argument("app")
    p.set_defaults(func=cmd_app)

    p = sub.add_parser("extract", help="compile an application and store its call graph in the database")
    p.add_argument("app")
    p.add_argument("--skip-build", action="store_true", help="use the existing class files")
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("edge-sample", help="sample edges for manual checking in the source code")
    p.add_argument("app")
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--seed", type=int, default=20261104)
    p.set_defaults(func=cmd_edge_sample)

    p = sub.add_parser("providers", help="list the registered LLM providers")
    p.set_defaults(func=cmd_providers)

    for name, func, text in (
        ("run", cmd_run, "run the LLM until the target number of accepted runs (resumable)"),
        ("evaluate", cmd_evaluate, "build the controls and compute the metrics"),
        ("report", cmd_report, "write the descriptive report"),
        ("all", cmd_pilot, "run, evaluate and report"),
        ("pilot", cmd_pilot, "same as all"),
    ):
        p = sub.add_parser(name, help=text)
        p.add_argument("--experiment", "--config", dest="experiment", required=True,
                       help="experiment configuration (its id on the Configuration page)")
        p.add_argument("--llm", help="LLM profile name; overrides the default profile of the experiment")
        if name == "run":
            p.add_argument("--variant", action="append", choices=["original", "obfuscated"])
        p.set_defaults(func=func)

    p = sub.add_parser("web", help="serve the web interface, or export it as a static site")
    p.add_argument("action", choices=["serve", "export"])
    p.add_argument("--database", default="monosplit", help="MongoDB database to show (default: monosplit)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--open", action="store_true", help="open the browser")
    p.add_argument("--out", help="export folder (default: work/site)")
    p.set_defaults(func=cmd_web)

    p = sub.add_parser("db", help="database status, import of the earlier files, dump and restore")
    p.add_argument("action", choices=["status", "import-config", "import", "dump", "restore"])
    p.add_argument("folder", nargs="?", help="import-config: folder holding config/ and prompts/ (default .); "
                   "import: data folder (default data); dump/restore: dump folder (default dump)")
    p.add_argument("--database", default="monosplit", help="MongoDB database (default: monosplit)")
    p.set_defaults(func=cmd_db)

    p = sub.add_parser("prompt", help="print the prompt of a variant without calling any model")
    p.add_argument("--experiment", "--config", dest="experiment", required=True)
    p.add_argument("--variant", default="original", choices=["original", "obfuscated"])
    p.set_defaults(func=cmd_prompt)

    args = parser.parse_args(argv)
    try:
        # The defaults of the tool are created when missing. Not for `db` (restore needs an
        # empty database) nor for commands that do not use the database.
        if args.command not in ("db", "jdk", "providers"):
            from .defaults import ensure_defaults
            from .store import open_store

            for created in ensure_defaults(open_store()):
                print(f"created the default {created}")
        args.func(args)
    except Exception as error:
        from .llm import LLMConfigurationError
        from .runner import RunStopped

        from .store import StoreUnavailable

        if isinstance(error, (RunStopped, LLMConfigurationError, ValueError, RuntimeError, StoreUnavailable)):
            print(f"error: {error}", file=sys.stderr)
            raise SystemExit(1) from None
        raise


if __name__ == "__main__":
    main()
