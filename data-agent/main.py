#!/usr/bin/env python3
"""
DataSanitizer — main entry point.

Standard usage:
    python main.py <filepath>

v4 Live Data Connectors:
    python main.py --connect sheets --id <sheet_id>
    python main.py --connect db [--config db_config.json]
    python main.py --connect api --url <endpoint> [--key <auth>]
    python main.py --connect gmail --query "<search>"

v4 Watchdog:
    python main.py --watch <file_or_connection> [--interval daily|hourly]
"""

import sys
import os


def _load_dotenv():
    """Silently load .env file if present."""
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
        except Exception:
            pass


def main():
    _load_dotenv()
    args = sys.argv[1:]

    # ── v4 Watchdog mode ──────────────────────────────────────────────────────
    if "--watch" in args:
        idx = args.index("--watch")
        source = args[idx + 1] if idx + 1 < len(args) else ""
        interval = "daily"
        if "--interval" in args:
            int_idx = args.index("--interval")
            interval = args[int_idx + 1] if int_idx + 1 < len(args) else "daily"
        if not source:
            print("Usage: python main.py --watch <file_or_connection> [--interval daily|hourly]")
            sys.exit(1)
        try:
            from v4.watchdog import run_watchdog
            run_watchdog(source, interval)
        except Exception as e:
            print("⚠ Failed to start the file watcher. This feature requires additional dependencies or permissions.")
        return

    # ── v4 Live connector mode ────────────────────────────────────────────────
    if "--connect" in args:
        idx = args.index("--connect")
        source_type = args[idx + 1].lower() if idx + 1 < len(args) else ""

        df = None
        filename = "connected_data.csv"

        if source_type == "sheets":
            sheet_id = _get_arg(args, "--id", "")
            if not sheet_id:
                print("Usage: python main.py --connect sheets --id <sheet_id>")
                sys.exit(1)
            from v4.data_connectors.sheets_connector import load_sheet
            df = load_sheet(sheet_id)
            filename = f"sheet_{sheet_id[:8]}.csv"

        elif source_type == "db":
            config_path = _get_arg(args, "--config", "db_config.json")
            from v4.data_connectors.db_connector import connect_db
            df = connect_db(config_path)
            filename = "db_query_result.csv"

        elif source_type == "api":
            url = _get_arg(args, "--url", "")
            key = _get_arg(args, "--key", "")
            if not url:
                print("Usage: python main.py --connect api --url <endpoint> [--key <auth>]")
                sys.exit(1)
            from v4.data_connectors.api_connector import fetch_api
            df = fetch_api(url, key)
            filename = "api_data.csv"

        elif source_type == "gmail":
            query = _get_arg(args, "--query", "")
            if not query:
                print("Usage: python main.py --connect gmail --query \"<search>\"")
                sys.exit(1)
            from v4.data_connectors.gmail_connector import fetch_gmail_attachment
            df = fetch_gmail_attachment(query)
            filename = "gmail_attachment.csv"

        else:
            print(f"Unknown connector: '{source_type}'. Supported: sheets, db, api, gmail")
            sys.exit(1)

        if df is None:
            print("Could not load data from connector. Exiting.")
            sys.exit(1)

        # Save to a temp CSV and run through v1 normally
        import tempfile
        tmp_path = os.path.join("output", f"_connector_{filename}")
        os.makedirs("output", exist_ok=True)
        df.to_csv(tmp_path, index=False)
        print(f"  Data saved to: {tmp_path}")
        print(f"  Proceeding through v1 cleaning pipeline...")
        sys.argv = [sys.argv[0], tmp_path]  # rewrite args for v1 CLI
        from v1.cli import main as v1_main
        v1_main()
        return

    # ── Standard file-based or web-based entry ────────────────────────────────
    if len(args) == 0:
        import socket
        import webbrowser
        import threading
        from v1.web.server import app, go_event
        from v1 import session_manager
        from v1.cli import run_agent_loop

        def get_free_port():
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
            s.close()
            return port

        port = get_free_port()

        # Start Flask in a background daemon thread
        server_thread = threading.Thread(
            target=app.run,
            kwargs={"host": "127.0.0.1", "port": port, "debug": False, "use_reloader": False, "threaded": True},
            daemon=True
        )
        server_thread.start()

        # Open the browser
        url = f"http://127.0.0.1:{port}"
        print(f"\n🚀 Ingestion server running at {url}")
        print("Opening browser for ingestion...")
        webbrowser.open(url)

        # Loop to handle transitions between browser and terminal agent
        try:
            while True:
                go_event.clear()
                print("\nWaiting for terminal launch command from browser... (Ctrl+C to quit)")
                while not go_event.wait(timeout=0.5):
                    pass

                try:
                    session_dict = session_manager.load_session()
                except Exception as e:
                    print("Failed to load your previous session. You can continue with a new session.")
                    break

                try:
                    ret = run_agent_loop(session_dict)
                    if not ret:
                        # User exited REPL cleanly via /exit or /quit
                        print("\nExiting DataSanitizer. Goodbye!")
                        sys.exit(0)
                except Exception as e:
                    print("The agent encountered an unexpected error. Please try again or restart the application.")
                    break
        except KeyboardInterrupt:
            print("\nExiting DataSanitizer. Goodbye!")
            sys.exit(0)
        return

    from v1.cli import main as v1_main
    v1_main()


def _get_arg(args: list, flag: str, default: str) -> str:
    if flag in args:
        idx = args.index(flag)
        if idx + 1 < len(args):
            return args[idx + 1]
    return default


if __name__ == "__main__":
    main()