"""Command line interface.

    python -m iris_mosaics status                 # all mosaics, one line each
    python -m iris_mosaics status 20240811        # one mosaic, step by step
    python -m iris_mosaics idl render prep1 20240811
    python -m iris_mosaics idl launch prep1 20240811
    python -m iris_mosaics idl watch  prep1 20240811
    python -m iris_mosaics idl log    prep1 20240811
    python -m iris_mosaics record despiked 20240811 --n-files 11767

Local steps stay in the notebooks; this drives the filament steps and keeps
the manifest up to date.
"""

from __future__ import annotations

import argparse
import sys
import time


def _status(args) -> int:
    from . import pipeline

    if args.date:
        print(pipeline.summary(args.date))
    else:
        print(pipeline.overview())
    return 0


def _idl(args) -> int:
    from . import remote
    from .config import MosaicConfig
    from .manifest import Manifest

    cfg = MosaicConfig.load(args.date)

    if args.action == "render":
        print(remote.render(args.step, cfg))
        return 0

    if args.action == "launch":
        from . import pipeline

        reason = pipeline.blocked_reason(args.date, args.step)
        if reason and not args.force:
            print(f"refusing to launch: {reason}", file=sys.stderr)
            print("pass --force to launch anyway", file=sys.stderr)
            return 1
        name = remote.launch(args.step, cfg)
        print(f"launched {name} on filament (detached)")
        print(f"poll with: python -m iris_mosaics idl watch {args.step} {args.date}")
        return 0

    if args.action == "status":
        print(remote.status(args.step, cfg))
        return 0

    if args.action == "log":
        print(remote.log(args.step, cfg, lines=args.lines))
        return 0

    if args.action == "stop":
        remote.stop(args.step, cfg)
        print(f"stopped {remote.job_name(args.step, cfg)}")
        return 0

    if args.action == "watch":
        while True:
            state = remote.status(args.step, cfg)
            try:
                n = remote.output_count(args.step, cfg)
                progress = f"  {n} files written"
            except Exception:
                progress = ""
            stamp = time.strftime("%H:%M:%S")
            print(f"[{stamp}] {state}{progress}", flush=True)
            if state in ("done", "failed", "not started"):
                if state == "failed":
                    print("\n--- tail of log ---", file=sys.stderr)
                    print(remote.log(args.step, cfg, lines=30), file=sys.stderr)
                    return 1
                if state == "done":
                    step = remote.STEPS[args.step]
                    m = Manifest.load(args.date)
                    m.record(step.manifest_step, n_files=remote.output_count(args.step, cfg))
                    m.save()
                    print(f"recorded {step.manifest_step} in the manifest")
                return 0
            time.sleep(args.interval)

    raise AssertionError(f"unhandled action {args.action}")


def _record(args) -> int:
    from .manifest import Manifest

    m = Manifest.load(args.date)
    details = {}
    if args.n_files is not None:
        details["n_files"] = args.n_files
    m.record(args.step, date=args.on, **details)
    path = m.save()
    print(f"recorded {args.step} for {args.date} in {path}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="iris_mosaics", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="show pipeline progress")
    p_status.add_argument("date", nargs="?", help="mosaic date, e.g. 20240811")
    p_status.set_defaults(func=_status)

    p_idl = sub.add_parser("idl", help="run the IDL steps on filament")
    p_idl.add_argument("action",
                       choices=["render", "launch", "status", "watch", "log", "stop"])
    p_idl.add_argument("step", choices=["prep1", "prep2"])
    p_idl.add_argument("date")
    p_idl.add_argument("--interval", type=int, default=300,
                       help="seconds between polls when watching (default 300)")
    p_idl.add_argument("--lines", type=int, default=40, help="log lines to show")
    p_idl.add_argument("--force", action="store_true",
                       help="launch even if the prerequisite step is not recorded")
    p_idl.set_defaults(func=_idl)

    p_rec = sub.add_parser("record", help="mark a step complete in the manifest")
    p_rec.add_argument("step")
    p_rec.add_argument("date")
    p_rec.add_argument("--on", help="completion date (default today)")
    p_rec.add_argument("--n-files", type=int)
    p_rec.set_defaults(func=_record)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
