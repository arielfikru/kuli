"""kuli — top-level admin CLI. Inspect/reset the intern health state.

  kuli health                 show each intern's health (rate-limit / auth / down)
  kuli health reset           clear all health state
  kuli health reset <intern>  clear one intern (use after `gemini login` etc.)
"""
import argparse
import json
import sys

from . import health


def parse_args():
    p = argparse.ArgumentParser(prog="kuli", description="KULI intern-pool admin.")
    sub = p.add_subparsers(dest="cmd")
    h = sub.add_parser("health", help="show intern health, or reset it")
    h.add_argument("action", nargs="?", choices=["reset"], help="reset health state")
    h.add_argument("intern", nargs="?", help="intern to reset (default: all)")
    return p, p.parse_args()


def main():
    parser, args = parse_args()
    if args.cmd != "health":
        parser.print_help()
        sys.exit(1)
    if args.action == "reset":
        health.health_reset(args.intern)
        print(f"reset health: {args.intern or 'all interns'}")
        return
    status = health.health_status()
    if not status:
        print("all interns healthy (no failure state recorded)")
        return
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
