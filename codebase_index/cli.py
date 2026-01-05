#!/usr/bin/env python3
"""
Command-line interface for the LLM-efficient codebase indexing system.

Usage:
    python -m codebase_index.cli /path/to/codebase [command] [args]

Commands:
    overview        Show codebase overview
    query "..."     Process a natural language query
    grep <pattern>  Search for a pattern
    find <name>     Find an entity by name
    calls <name>    What calls this entity?
    callees <name>  What does this entity call?
    impact <name>   Impact analysis for an entity
    stats           Show index statistics
    central         Show most connected entities
    repl            Start interactive REPL
"""

import argparse
import sys
from pathlib import Path

from .index import CodebaseIndex


def main():
    parser = argparse.ArgumentParser(
        description="LLM-efficient codebase indexing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to codebase (default: current directory)",
    )

    parser.add_argument(
        "command",
        nargs="?",
        default="repl",
        choices=["overview", "query", "grep", "find", "calls", "callees", "impact", "stats", "central", "repl", "files"],
        help="Command to run (default: repl)",
    )

    parser.add_argument(
        "args",
        nargs="*",
        help="Command arguments",
    )

    parser.add_argument(
        "--budget",
        type=int,
        default=4000,
        help="Token budget for responses (default: 4000)",
    )

    args = parser.parse_args()

    # Initialize and build index
    path = Path(args.path).resolve()
    if not path.exists():
        print(f"Error: Path does not exist: {path}", file=sys.stderr)
        sys.exit(1)

    print(f"Initializing index for: {path}")
    index = CodebaseIndex(str(path))
    index.build()
    print()

    # Execute command
    if args.command == "overview":
        print(index.get_overview())

    elif args.command == "query":
        if not args.args:
            print("Error: query command requires a query string", file=sys.stderr)
            sys.exit(1)
        query = " ".join(args.args)
        print(index.query(query, budget=args.budget))

    elif args.command == "grep":
        if not args.args:
            print("Error: grep command requires a pattern", file=sys.stderr)
            sys.exit(1)
        print(index.grep(args.args[0]))

    elif args.command == "find":
        if not args.args:
            print("Error: find command requires an entity name", file=sys.stderr)
            sys.exit(1)
        print(index.find(args.args[0]))

    elif args.command == "calls":
        if not args.args:
            print("Error: calls command requires an entity name", file=sys.stderr)
            sys.exit(1)
        print(index.what_calls(args.args[0]))

    elif args.command == "callees":
        if not args.args:
            print("Error: callees command requires an entity name", file=sys.stderr)
            sys.exit(1)
        print(index.what_does_call(args.args[0]))

    elif args.command == "impact":
        if not args.args:
            print("Error: impact command requires an entity name", file=sys.stderr)
            sys.exit(1)
        print(index.impact(args.args[0]))

    elif args.command == "stats":
        stats = index.stats()
        print("## Index Statistics\n")
        for key, value in sorted(stats.items()):
            print(f"  {key}: {value}")

    elif args.command == "central":
        print(index.central_entities(top_k=15))

    elif args.command == "files":
        files = index.list_files()
        print(f"## Indexed Files ({len(files)})\n")
        for f in sorted(files):
            print(f"  {f}")

    elif args.command == "repl":
        run_repl(index)


def run_repl(index: CodebaseIndex):
    """Run interactive REPL."""
    print("=" * 60)
    print("LLM-Efficient Codebase Index - Interactive Mode")
    print("=" * 60)
    print()
    print("Commands:")
    print("  .overview          - Show codebase overview")
    print("  .grep <pattern>    - Search for pattern")
    print("  .find <name>       - Find entity by name")
    print("  .calls <name>      - What calls this?")
    print("  .callees <name>    - What does this call?")
    print("  .impact <name>     - Impact analysis")
    print("  .stats             - Show statistics")
    print("  .central           - Most connected entities")
    print("  .files             - List files")
    print("  .session           - Show session state")
    print("  .task <desc>       - Set current task")
    print("  .reset             - Reset session")
    print("  .quit              - Exit")
    print()
    print("Or just type a natural language query!")
    print()

    while True:
        try:
            user_input = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.startswith("."):
            # Command mode
            parts = user_input[1:].split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd == "quit" or cmd == "exit":
                print("Goodbye!")
                break
            elif cmd == "overview":
                print(index.get_overview())
            elif cmd == "grep":
                if not arg:
                    print("Usage: .grep <pattern>")
                else:
                    print(index.grep(arg))
            elif cmd == "find":
                if not arg:
                    print("Usage: .find <name>")
                else:
                    print(index.find(arg))
            elif cmd == "calls":
                if not arg:
                    print("Usage: .calls <name>")
                else:
                    print(index.what_calls(arg))
            elif cmd == "callees":
                if not arg:
                    print("Usage: .callees <name>")
                else:
                    print(index.what_does_call(arg))
            elif cmd == "impact":
                if not arg:
                    print("Usage: .impact <name>")
                else:
                    print(index.impact(arg))
            elif cmd == "stats":
                stats = index.stats()
                print("\n## Index Statistics\n")
                for key, value in sorted(stats.items()):
                    print(f"  {key}: {value}")
            elif cmd == "central":
                print(index.central_entities())
            elif cmd == "files":
                files = index.list_files()
                print(f"\n## Indexed Files ({len(files)})\n")
                for f in sorted(files):
                    print(f"  {f}")
            elif cmd == "session":
                print(index.session_summary())
            elif cmd == "task":
                if not arg:
                    print("Usage: .task <description>")
                else:
                    index.set_task(arg)
                    print(f"Task set: {arg}")
            elif cmd == "reset":
                index.reset_session()
                print("Session reset.")
            else:
                print(f"Unknown command: .{cmd}")
        else:
            # Query mode
            print()
            print(index.query(user_input))

        print()


if __name__ == "__main__":
    main()
