# -*- coding: utf-8 -*-
"""
Feature 3D — Gmail attachment connector.

Usage:
    python main.py --connect gmail --query "<gmail search>"

Searches Gmail for matching emails with CSV/Excel attachments,
lets user pick one, downloads it, and returns a DataFrame.

READ-ONLY — never sends emails or modifies Gmail.
"""

from __future__ import annotations

import os
import io
import base64
import tempfile
from typing import Optional

import pandas as pd

_SUPPORTED_MIME = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",  # fallback
}

_SUPPORTED_EXT = {".csv", ".tsv", ".xlsx", ".xls"}


def fetch_gmail_attachment(query: str) -> Optional[pd.DataFrame]:
    """
    Search Gmail for matching emails with CSV/Excel attachments,
    present a selection list, download selected attachment, return DataFrame.
    Falls back gracefully if Gmail API / credentials are unavailable.
    """
    service = _build_gmail_service()
    if service is None:
        _print_setup_instructions()
        return None

    try:
        results = service.users().messages().list(
            userId="me",
            q=query + " has:attachment",
            maxResults=10,
        ).execute()
    except Exception as e:
        print("  ⚠ Gmail search failed. Please check your search query and try again.")
        return None

    messages = results.get("messages", [])
    if not messages:
        print(f"  No emails with attachments found matching: '{query}'")
        return None

    # Collect attachment metadata
    candidates: list[dict] = []
    for msg_meta in messages:
        msg_id = msg_meta["id"]
        try:
            msg = service.users().messages().get(
                userId="me", id=msg_id, format="metadata",
                metadataHeaders=["Subject", "From", "Date"]
            ).execute()
        except Exception:
            continue

        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        subject = headers.get("Subject", "(no subject)")
        sender = headers.get("From", "?")
        date = headers.get("Date", "?")

        # Check parts for attachments
        parts = _flatten_parts(msg.get("payload", {}))
        for part in parts:
            filename = part.get("filename", "")
            _, ext = os.path.splitext(filename.lower())
            if ext in _SUPPORTED_EXT:
                candidates.append({
                    "msg_id": msg_id,
                    "part_id": part.get("partId", ""),
                    "attachment_id": part.get("body", {}).get("attachmentId", ""),
                    "filename": filename,
                    "subject": subject,
                    "sender": sender,
                    "date": date,
                })
                break  # one attachment per email

    if not candidates:
        print(f"  No CSV/Excel attachments found in emails matching: '{query}'")
        return None

    print(f"\n  Found {len(candidates)} email(s) with CSV/Excel attachments matching '{query}':")
    for i, c in enumerate(candidates, 1):
        print(f"    [{i}] '{c['subject']}' from {c['sender']} ({c['date']})")
    print()

    try:
        choice = input("  Which would you like to analyze? (number): ").strip()
        if not choice.isdigit() or not (1 <= int(choice) <= len(candidates)):
            print("  Invalid choice — cancelling Gmail load.")
            return None
        selected = candidates[int(choice) - 1]
    except (KeyboardInterrupt, EOFError):
        return None

    # Download attachment
    try:
        att = service.users().messages().attachments().get(
            userId="me",
            messageId=selected["msg_id"],
            id=selected["attachment_id"],
        ).execute()
        raw = base64.urlsafe_b64decode(att["data"])
    except Exception as e:
        print("  ⚠ Failed to download the attachment. Please check your internet connection and try again.")
        return None

    # Parse to DataFrame
    filename = selected["filename"]
    _, ext = os.path.splitext(filename.lower())
    try:
        if ext in (".csv", ".tsv"):
            sep = "\t" if ext == ".tsv" else ","
            df = pd.read_csv(io.BytesIO(raw), sep=sep)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(io.BytesIO(raw))
        else:
            print(f"  ⚠ Unsupported attachment format: {ext}")
            return None

        print(f"  [Gmail] Loaded '{filename}' — {len(df):,} rows × {len(df.columns)} cols.")
        return df
    except Exception as e:
        print("  ⚠ Failed to parse the attachment. Please check that the file is not corrupted and try again.")
        return None


def _flatten_parts(payload: dict) -> list[dict]:
    """Recursively collect all message parts."""
    parts = payload.get("parts", [])
    if not parts:
        return [payload]
    result = []
    for part in parts:
        result.extend(_flatten_parts(part))
    return result


def _build_gmail_service():
    """Build and return a Gmail API service, or None if unavailable."""
    try:
        from google.oauth2.credentials import Credentials  # type: ignore
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
        from googleapiclient.discovery import build  # type: ignore
    except ImportError:
        return None

    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
    cred_path = os.path.join(os.getcwd(), "gmail_credentials.json")
    token_path = os.path.join(os.getcwd(), "gmail_token.json")

    if not os.path.exists(cred_path):
        return None

    creds = None
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception:
            pass

    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request  # type: ignore
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, "w") as token:
                token.write(creds.to_json())
        except Exception:
            return None

    try:
        return build("gmail", "v1", credentials=creds)
    except Exception:
        return None


def _print_setup_instructions() -> None:
    print()
    print("  ⚠ Gmail connection requires OAuth setup.")
    print("  Steps:")
    print("  1. Go to https://console.cloud.google.com/")
    print("  2. Create OAuth 2.0 credentials (Desktop App type)")
    print("  3. Download as 'gmail_credentials.json' in your project folder")
    print("  4. Install: pip install google-auth-oauthlib google-api-python-client")
    print()
    print("  For now, you can download the file from Gmail manually and upload it directly.")
    print()
