import os
import uuid
import datetime
import threading
import pandas as pd
from functools import wraps
from flask import Flask, request, jsonify, render_template

from v1 import session_manager
from v1 import lock_manager
from v1.inspector import DataInspector
from v1.cleaner import DataCleaner

# Configure Flask app with explicit template folder
TEMPLATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "templates"))
app = Flask(__name__, template_folder=TEMPLATE_DIR)

import logging
# Silence default Flask (Werkzeug) access logs to prevent terminal clutter
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# Threading event to signal main.py to resume terminal loop
go_event = threading.Event()
# Lock for thread-safe access to pending_files
pending_lock = threading.Lock()
# Lock for thread-safe access to session data
session_lock = threading.Lock()

# In-memory staging registry
# structure: { id: { id, name, path, size, has_issues, total_issues, report } }
pending_files = {}

def load_df(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".tsv":
        return pd.read_csv(path, sep="\t")
    elif ext in (".xlsx", ".xls"):
        return pd.read_excel(path, engine="openpyxl")
    return pd.read_csv(path)

def check_lock(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if lock_manager.is_locked():
            return jsonify({
                "message": "The agent is currently running in your terminal. Please finish there before making changes here."
            }), 423
        return func(*args, **kwargs)
    return wrapper

@app.route("/", methods=["GET"])
def index():
    locked = lock_manager.is_locked()
    datasets = {}
    session_id = None
    with session_lock:
        try:
            session = session_manager.load_session()
            session_id = session.get("session_id")
            datasets = session.get("datasets", {})
        except Exception:
            pass
    return render_template("index.html", locked=locked, datasets=datasets, session_id=session_id)

@app.route("/api/upload", methods=["POST"])
@check_lock
def upload():
    uploaded_files = request.files.getlist("files")
    if not uploaded_files or not uploaded_files[0].filename:
        return jsonify({"error": "No files uploaded."}), 400

    # Pre-check file sizes
    for f in uploaded_files:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(0)
        if size > 10 * 1024 * 1024:
            return jsonify({"error": f"File '{f.filename}' exceeds 10MB limit."}), 400

    staging_dir = "staging"
    os.makedirs(staging_dir, exist_ok=True)

    results = []
    with pending_lock:
        if len(pending_files) + len(uploaded_files) > 5:
            return jsonify({"error": "Total staged files cannot exceed 5."}), 400

        for f in uploaded_files:
            file_id = str(uuid.uuid4())[:8]
            filename = f.filename
            staged_name = f"{file_id}_{filename}"
            staged_path = os.path.abspath(os.path.join(staging_dir, staged_name))

            f.save(staged_path)
            size = os.path.getsize(staged_path)

            try:
                inspector = DataInspector(staged_path)
                report = inspector.inspect()

                pending_files[file_id] = {
                    "id": file_id,
                    "name": filename,
                    "path": staged_path,
                    "size": size,
                    "has_issues": report.has_issues,
                    "total_issues": report.total_issues,
                    "report": report
                }

                results.append({
                    "id": file_id,
                    "name": filename,
                    "size": size,
                    "has_issues": report.has_issues,
                    "total_issues": report.total_issues
                })
            except Exception as e:
                if os.path.exists(staged_path):
                    try:
                        os.remove(staged_path)
                    except Exception:
                        pass
                # User-friendly error message
                error_msg = "File inspection failed. Please check that the file is not corrupted and is in a supported format (CSV, TSV, XLS, XLSX)."
                return jsonify({"error": error_msg}), 500

    return jsonify(results)

@app.route("/api/pending", methods=["GET"])
def get_pending():
    session_datasets = []
    current_session_id = None
    with session_lock:
        try:
            session = session_manager.load_session()
            current_session_id = session.get("session_id")
            for ds_id, ds in session.get("datasets", {}).items():
                v1_sum = ds.get("v1_summary", {})
                was_cleaned = len(v1_sum.get("actions_log", [])) > 0
                session_datasets.append({
                    "id": ds_id,
                    "name": ds.get("name"),
                    "was_cleaned": was_cleaned,
                    "issues_resolved": v1_sum.get("issues_resolved", 0)
                })
        except Exception:
            pass

    pending_list = []
    with pending_lock:
        for fid, f in pending_files.items():
            pending_list.append({
                "id": f["id"],
                "name": f["name"],
                "size": f["size"],
                "has_issues": f["has_issues"],
                "total_issues": f["total_issues"]
            })

    return jsonify({
        "pending": pending_list,
        "committed": session_datasets,
        "session_id": current_session_id
    })

@app.route("/api/decide", methods=["POST"])
@check_lock
def decide():
    body = request.json or {}
    action = body.get("action", "clean_none")
    selected_ids = body.get("selected_ids", [])

    with session_lock:
        session = None
        current_pointer_path = os.path.join("sessions", "current_session.json")
        if os.path.exists(current_pointer_path):
            try:
                session = session_manager.load_session()
            except Exception:
                pass

        if not session:
            sid = session_manager.new_session_id()
            session = {
                "session_id": sid,
                "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "active_dataset_id": "",
                "datasets": {},
                "v3_summary": {
                    "conversation_history": [],
                    "queries_run": []
                },
                "active_version": "v1"
            }

        with pending_lock:
            for fid in list(pending_files.keys()):
                f = pending_files[fid]
                staged_path = f["path"]
                filename = f["name"]
                report = f["report"]

                should_clean = False
                if action == "clean_all":
                    should_clean = True
                elif action == "clean_selected" and fid in selected_ids:
                    should_clean = True

                try:
                    original_df = load_df(staged_path)

                    if should_clean:
                        cleaner = DataCleaner(original_df, report)
                        cleaned_df = cleaner.clean()
                        output_path = cleaner.save()
                        applied_actions = [act.description for act in report.cleaning_actions]
                        issues_resolved = cleaner.steps_done
                    else:
                        cleaned_df = original_df
                        ext = os.path.splitext(filename)[1].lower()
                        cleaned_filename = f"{os.path.splitext(filename)[0]}_cleaned{ext}"
                        output_path = os.path.abspath(os.path.join("output", cleaned_filename))
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        if ext in (".xlsx", ".xls"):
                            cleaned_df.to_excel(output_path, index=False, engine="openpyxl")
                        elif ext == ".tsv":
                            cleaned_df.to_csv(output_path, sep="\t", index=False)
                        else:
                            cleaned_df.to_csv(output_path, index=False)
                        applied_actions = []
                        issues_resolved = 0

                    ds_id = session_manager.add_dataset(
                        session=session,
                        name=filename,
                        original_df=original_df,
                        cleaned_df=cleaned_df,
                        applied_actions=applied_actions,
                        issues_resolved=issues_resolved,
                        was_cleaned=should_clean
                    )

                    session["datasets"][ds_id]["file"]["original"] = os.path.abspath(staged_path)
                    session["datasets"][ds_id]["file"]["cleaned"] = os.path.abspath(output_path)

                    if not session.get("active_dataset_id"):
                        session["active_dataset_id"] = ds_id

                    del pending_files[fid]
                    if os.path.exists(staged_path):
                        os.remove(staged_path)
                except Exception as e:
                    # User-friendly error message
                    error_msg = "Failed to process file. Please try again or contact support if the problem persists."
                    return jsonify({"error": error_msg}), 500

        session_manager.save_session(session)
        session_manager.write_current_session(session["session_id"])
        return jsonify({"success": True})

@app.route("/api/dataset/<ds_id>", methods=["DELETE"])
@check_lock
def delete_dataset(ds_id):
    with session_lock:
        try:
            session = session_manager.load_session()
        except Exception:
            return jsonify({"error": "No active session to delete from."}), 404

        if ds_id not in session.get("datasets", {}):
            return jsonify({"error": "Dataset not found in session."}), 404

        session_manager.remove_dataset(session, ds_id)
        # Always save the session after modification to ensure changes are persisted
        try:
            session_manager.save_session(session)
        except Exception as e:
            return jsonify({"error": "Failed to save session after dataset removal."}), 500

        return jsonify({"success": True})


@app.route("/api/connect/sheets", methods=["POST"])
@check_lock
def connect_sheets():
    """Connect to a Google Sheet and add it to the session."""
    with session_lock:
        try:
            session = session_manager.load_session()
        except Exception:
            return jsonify({"error": "No active session to add data to."}), 404

        data = request.get_json()
        if not data or 'sheet_id' not in data:
            return jsonify({"error": "Missing sheet_id parameter"}), 400

        sheet_id = data['sheet_id'].strip()
        if not sheet_id:
            return jsonify({"error": "Sheet ID cannot be empty"}), 400

        try:
            # Import the Google Sheets connector
            import sys
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'v4', 'data_connectors'))
            from sheets_connector import load_sheet

            # Fetch the Google Sheet
            df = load_sheet(sheet_id, force_refresh=False)
            if df is None:
                return jsonify({"error": "Failed to fetch data from Google Sheet. Please check the Sheet ID and ensure the sheet is accessible."}), 400

            # Generate a dataset ID
            ds_id = session_manager.new_session_id()

            # Initialize session if needed
            if not session.get("datasets"):
                session["datasets"] = {}
                if not session.get("session_id"):
                    session["session_id"] = session_manager.new_session_id()
                if not session.get("active_dataset_id"):
                    session["active_dataset_id"] = ds_id

            # Add the dataset to session
            # We need to create a cleaned version (same as original for now)
            cleaned_df = df.copy()

            # Save both dataframes as pickles
            output_dir = os.path.join("output", "sheets")
            os.makedirs(output_dir, exist_ok=True)

            original_pickle = os.path.join(output_dir, f"{ds_id}_original.pkl")
            cleaned_pickle = os.path.join(output_dir, f"{ds_id}_cleaned.pkl")

            df.to_pickle(original_pickle)
            cleaned_df.to_pickle(cleaned_pickle)

            # Add to session
            session["datasets"][ds_id] = {
                "name": f"Google Sheet: {sheet_id}",
                "file": {
                    "original": original_pickle,
                    "cleaned": cleaned_pickle,
                    "dataframe_pickle": cleaned_pickle
                },
                "v1_summary": {
                    "issues_resolved": 0,
                    "actions_log": []
                }
            }

            # Set as active if no active dataset
            if not session.get("active_dataset_id"):
                session["active_dataset_id"] = ds_id

            # Save session
            session_manager.save_session(session)
            session_manager.write_current_session(session["session_id"])

            return jsonify({
                "success": True,
                "dataset_id": ds_id,
                "name": session["datasets"][ds_id]["name"],
                "rows": len(df),
                "columns": len(df.columns)
            })

        except ImportError as e:
            return jsonify({"error": "Google Sheets connector not available. Please install required packages: pip install gspread google-auth"}), 500
        except Exception as e:
            return jsonify({"error": f"Failed to connect to Google Sheet: {str(e)}"}), 500


@app.route("/api/connect/db", methods=["POST"])
@check_lock
def connect_db():
    """Connect to a database using a config file and add results to the session."""
    with session_lock:
        try:
            session = session_manager.load_session()
        except Exception:
            return jsonify({"error": "No active session to add data to."}), 404

        # Check if file was uploaded
        if 'config' not in request.files:
            return jsonify({"error": "No config file provided"}), 400

        config_file = request.files['config']
        if config_file.filename == '':
            return jsonify({"error": "No config file selected"}), 400

        if not config_file.filename.endswith('.json'):
            return jsonify({"error": "Config file must be a JSON file"}), 400

        # Save the config file temporarily
        config_path = os.path.join("temp_db_config.json")
        try:
            config_file.save(config_path)

            # Import the database connector
            import sys
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'v4', 'data_connectors'))
            from db_connector import load_db_config, connect_db

            # Load the DB config
            cfg = load_db_config(config_path)
            if cfg is None:
                return jsonify({"error": "Failed to load database configuration. Please check your db_config.json file."}), 400

            # Connect to database and get data
            df = connect_db(config_path)
            if df is None:
                return jsonify({"error": "Failed to connect to database or retrieve data. Please check your configuration and connection."}), 400

            # Generate a dataset ID
            ds_id = session_manager.new_session_id()

            # Initialize session if needed
            if not session.get("datasets"):
                session["datasets"] = {}
                if not session.get("session_id"):
                    session["session_id"] = session_manager.new_session_id()
                if not session.get("active_dataset_id"):
                    session["active_dataset_id"] = ds_id

            # Save both dataframes as pickles (original and cleaned are the same for DB)
            output_dir = os.path.join("output", "db")
            os.makedirs(output_dir, exist_ok=True)

            original_pickle = os.path.join(output_dir, f"{ds_id}_original.pkl")
            cleaned_pickle = os.path.join(output_dir, f"{ds_id}_cleaned.pkl")

            df.to_pickle(original_pickle)
            df.to_pickle(cleaned_pickle)  # Same as original for DB data

            # Add to session
            session["datasets"][ds_id] = {
                "name": f"Database: {cfg.get('database', 'unknown')}@{cfg.get('host', 'unknown')}",
                "file": {
                    "original": original_pickle,
                    "cleaned": cleaned_pickle,
                    "dataframe_pickle": cleaned_pickle
                },
                "v1_summary": {
                    "issues_resolved": 0,
                    "actions_log": []
                }
            }

            # Set as active if no active dataset
            if not session.get("active_dataset_id"):
                session["active_dataset_id"] = ds_id

            # Save session
            session_manager.save_session(session)
            session_manager.write_current_session(session["session_id"])

            return jsonify({
                "success": True,
                "dataset_id": ds_id,
                "name": session["datasets"][ds_id]["name"],
                "rows": len(df),
                "columns": len(df.columns)
            })

        except ImportError as e:
            return jsonify({"error": "Database connector not available. Please install required packages: pip install psycopg2-binary (Postgres) or pymysql (MySQL)"}), 500
        except Exception as e:
            return jsonify({"error": f"Failed to connect to database: {str(e)}"}), 500
        finally:
            # Clean up temp config file
            if os.path.exists(config_path):
                try:
                    os.remove(config_path)
                except Exception:
                    pass

@app.route("/api/go_to_agent", methods=["POST"])
def go_to_agent():
    lock_manager.acquire_lock()
    go_event.set()
    return jsonify({"success": True})

@app.route("/api/lock_status", methods=["GET"])
def lock_status():
    return jsonify({"locked": lock_manager.is_locked()})