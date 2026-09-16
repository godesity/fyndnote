"""Console entry point: ``fyndnote serve`` runs the API/SPA/docs; ``fyndnote migrate`` imports a Label Studio export."""

import argparse
import os
import sys
from pathlib import Path


def _serve(args: argparse.Namespace) -> None:
    if args.data_dir:
        os.environ["FYNDNOTE_HOME"] = str(Path(args.data_dir).resolve())
    import uvicorn

    uvicorn.run("fyndnote.main:app", host=args.host, port=args.port, reload=args.reload)


def _add_serve_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--host", default=os.getenv("FYNDNOTE_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.getenv("FYNDNOTE_PORT", "8000")))
    p.add_argument(
        "--data-dir",
        default=None,
        help="Data dir for the SQLite DB, datasets and templates "
        "(default: ~/.fyndnote, or ./data in a source checkout)",
    )
    p.add_argument(
        "--reload", action="store_true", help="Restart on code changes (dev only)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fyndnote",
        description="fyndnote annotation server and import tools",
    )
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser(
        "serve", help="Run the API, the built SPA and the docs (default command)"
    )
    _add_serve_args(serve)

    migrate = sub.add_parser(
        "migrate",
        help="Import a Label Studio export over the HTTP API",
        description="Import a Label Studio export into a running fyndnote server.",
    )
    _add_serve_args(migrate)
    migrate.add_argument(
        "--input",
        required=True,
        help="Label Studio export (.json array or .jsonl/.jsonls)",
    )
    migrate.add_argument(
        "--user",
        required=True,
        help="fyndnote user_id all annotations are attributed to",
    )
    migrate.add_argument(
        "--project-name",
        default=None,
        help="project name (default: input filename stem)",
    )
    migrate.add_argument(
        "--dataset-name", default=None, help="dataset upload filename stem"
    )
    migrate.add_argument(
        "--config",
        default=None,
        help="Label Studio project JSON (with labeling XML) or raw XML",
    )
    migrate.add_argument("--color", default="#1976d2")
    migrate.add_argument("--instructions", default="")
    migrate.add_argument(
        "--allow-partial",
        action="store_true",
        help="drop unmappable controls instead of hard-failing",
    )
    migrate.add_argument(
        "--report-predictions",
        action="store_true",
        help="validate and count predictions[] in the summary",
    )
    migrate.add_argument(
        "--dry-run",
        action="store_true",
        help="print the plan, template and first annotation without POSTing",
    )
    migrate.add_argument(
        "--media-column",
        default=None,
        help="data column holding image/audio URLs",
    )
    migrate.add_argument(
        "--media-url-base",
        default=None,
        help="prefix for relative /data/ media paths",
    )
    migrate.add_argument("--timeout", type=float, default=30.0)

    # `fyndnote --port 8000` predates subcommands: keep it working as `serve`.
    argv = sys.argv[1:]
    if argv and argv[0] not in ("serve", "migrate") and argv[0] not in ("-h", "--help"):
        argv = ["serve", *argv]
    args = parser.parse_args(argv)

    if args.command == "migrate":
        from fyndnote.tools import migrate_labelstudio as mig

        raise SystemExit(mig.main(_migrate_argv(sys.argv[1:])))

    _serve(args)


def _migrate_argv(argv: list[str]) -> list[str]:
    """Translate `fyndnote migrate ...` args for the migration parser.

    Drops serve-only flags (the migration talks to --base-url, or to a server
    started from this same data dir) and defaults --base-url to the serve host
    and port resolved from flags/env so `fyndnote migrate` needs no extra flag.
    """
    out: list[str] = []
    if argv and argv[0] == "migrate":
        argv = argv[1:]
    i = 0
    host = os.getenv("FYNDNOTE_HOST", "127.0.0.1")
    port = os.getenv("FYNDNOTE_PORT", "8000")
    while i < len(argv):
        a = argv[i]
        if a in ("--host", "--port", "--data-dir"):
            val = argv[i + 1]
            if a == "--host":
                host = val
            elif a == "--port":
                port = val
            elif a == "--data-dir":
                os.environ["FYNDNOTE_HOME"] = str(Path(val).resolve())
            i += 2
            continue
        if a == "--reload":
            i += 1
            continue
        out.append(a)
        i += 1
    if not any(a == "--base-url" or a.startswith("--base-url=") for a in out):
        out += ["--base-url", f"http://{host}:{port}"]
    return out


if __name__ == "__main__":
    main()
