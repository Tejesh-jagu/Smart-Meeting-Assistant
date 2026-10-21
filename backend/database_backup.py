"""Create and safely restore local PostgreSQL custom-format backups."""

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import psycopg
from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_BACKUP_DIR = BACKEND_DIR / "backups"


def find_postgres_tool(name):
    executable = shutil.which(name) or shutil.which(f"{name}.exe")
    if executable:
        return executable

    program_files = Path(os.getenv("ProgramFiles", r"C:\Program Files"))
    matches = list((program_files / "PostgreSQL").glob(f"*/bin/{name}.exe"))
    if matches:
        return str(sorted(matches, reverse=True)[0])

    raise RuntimeError(
        f"Could not find {name}. Add PostgreSQL's bin directory to PATH or install PostgreSQL command-line tools."
    )


def run_postgres_tool(arguments):
    result = subprocess.run(
        arguments,
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        details = result.stderr.strip() or f"Process exited with code {result.returncode}."
        raise RuntimeError(details)
    return result.stdout


def required_database_settings(database=None):
    values = {
        "host": os.getenv("PGHOST"),
        "port": os.getenv("PGPORT"),
        "user": os.getenv("PGUSER"),
        "password": os.getenv("PGPASSWORD", ""),
        "database": database or os.getenv("PGDATABASE"),
    }
    missing = [key for key, value in values.items() if key != "password" and not value]
    if missing:
        raise RuntimeError(
            "Missing PostgreSQL settings in backend/.env: " + ", ".join(missing)
        )
    return values


def connection_parameters(settings, database=None):
    return {
        "host": settings["host"],
        "port": settings["port"],
        "user": settings["user"],
        "password": settings["password"],
        "dbname": database or settings["database"],
    }


def validate_archive(archive_path):
    pg_restore = find_postgres_tool("pg_restore")
    listing = run_postgres_tool([pg_restore, "--list", str(archive_path)])
    if not listing.strip():
        raise RuntimeError("The backup archive has no readable PostgreSQL directory.")


def create_backup(arguments):
    settings = required_database_settings(arguments.database)
    database_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", settings["database"])
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    output_dir = arguments.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"smart_meeting_assistant_{database_label}_{timestamp}.dump"
    if archive_path.exists():
        raise RuntimeError(f"Refusing to overwrite existing backup: {archive_path}")

    pg_dump = find_postgres_tool("pg_dump")
    try:
        run_postgres_tool(
            [
                pg_dump,
                "--format=custom",
                "--no-owner",
                "--no-acl",
                "--file",
                str(archive_path),
                "--host",
                settings["host"],
                "--port",
                str(settings["port"]),
                "--username",
                settings["user"],
                "--dbname",
                settings["database"],
            ]
        )
        validate_archive(archive_path)
    except Exception:
        archive_path.unlink(missing_ok=True)
        raise

    print(f"Backup created and verified: {archive_path}")


def restore_backup(arguments):
    archive_path = arguments.archive.resolve()
    if not archive_path.is_file():
        raise RuntimeError(f"Backup file does not exist: {archive_path}")

    settings = required_database_settings()
    if arguments.target_database == settings["database"]:
        raise RuntimeError(
            "Refusing to restore into the configured source database. Choose a separate empty database."
        )
    if arguments.confirm_target != arguments.target_database:
        raise RuntimeError(
            "Confirmation did not match. Pass --confirm-target with the exact target database name."
        )

    validate_archive(archive_path)
    target_parameters = connection_parameters(settings, arguments.target_database)
    with psycopg.connect(**target_parameters) as connection:
        existing_objects = connection.execute(
            """
            SELECT COUNT(*)
            FROM pg_class AS class
            JOIN pg_namespace AS namespace ON namespace.oid = class.relnamespace
            WHERE namespace.nspname NOT IN ('pg_catalog', 'information_schema')
              AND namespace.nspname NOT LIKE 'pg_toast%'
              AND class.relkind IN ('r', 'v', 'm', 'S', 'f', 'p')
            """
        ).fetchone()[0]

    if existing_objects:
        raise RuntimeError(
            f"Target database {arguments.target_database!r} contains user data; restore only into an empty database."
        )

    pg_restore = find_postgres_tool("pg_restore")
    run_postgres_tool(
        [
            pg_restore,
            "--exit-on-error",
            "--single-transaction",
            "--no-owner",
            "--no-acl",
            "--dbname",
            arguments.target_database,
            str(archive_path),
        ]
    )
    print(f"Backup restored into empty database: {arguments.target_database}")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Back up or restore the local Smart Meeting Assistant PostgreSQL database."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup", help="Create and verify a custom-format backup.")
    backup_parser.add_argument(
        "--database",
        help="Database to back up (defaults to PGDATABASE in backend/.env).",
    )
    backup_parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_BACKUP_DIR,
        help="Backup directory (defaults to backend/backups).",
    )
    backup_parser.set_defaults(handler=create_backup)

    restore_parser = subparsers.add_parser(
        "restore", help="Restore an archive into a separate, empty database."
    )
    restore_parser.add_argument("archive", type=Path, help="Path to a verified .dump backup.")
    restore_parser.add_argument("--target-database", required=True)
    restore_parser.add_argument(
        "--confirm-target",
        required=True,
        help="Must exactly match --target-database to confirm the restore target.",
    )
    restore_parser.set_defaults(handler=restore_backup)
    return parser


def main():
    load_dotenv(BACKEND_DIR / ".env")
    arguments = build_parser().parse_args()
    try:
        arguments.handler(arguments)
    except (OSError, psycopg.Error, RuntimeError) as error:
        print(f"Backup operation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
