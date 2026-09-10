"""Console entry point: `fyndnote` serves the API, the built SPA and the docs."""
import argparse
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="fyndnote", description="Run the fyndnote annotation server")
    parser.add_argument("--host", default=os.getenv("FYNDNOTE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("FYNDNOTE_PORT", "8000")))
    parser.add_argument("--data-dir", default=None,
                        help="Data dir for the SQLite DB, datasets and templates "
                             "(default: ~/.fyndnote, or ./data in a source checkout)")
    parser.add_argument("--reload", action="store_true", help="Restart on code changes (dev only)")
    args = parser.parse_args()
    if args.data_dir:
        os.environ["FYNDNOTE_HOME"] = str(Path(args.data_dir).resolve())
    import uvicorn
    uvicorn.run("fyndnote.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
