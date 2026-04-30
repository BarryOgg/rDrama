#!/usr/bin/env python3
"""
Resolve which PostgreSQL URL pytest should use.

By default, tests use a separate database: the same connection as DATABASE_URL
but with the database name suffixed by _test (when the URL has no database
path, libpq defaults to a database named like the user — we treat that as
postgres and use postgres_test).

Override with TEST_DATABASE_URL. Set USE_DEV_DATABASE_FOR_TESTS=1 to keep the
previous behavior (tests hit DATABASE_URL as-is).

Run inside the site container (see util/test.py): this module is not meant to
be run on the host against a Docker-only Postgres hostname.
"""

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def _admin_connection(parsed):
	for admin_path in ("/postgres", "/template1"):
		admin_url = urlunparse(parsed._replace(path=admin_path))
		try:
			return psycopg2.connect(admin_url)
		except psycopg2.OperationalError:
			continue
	raise RuntimeError(
		"Could not connect to Postgres using /postgres or /template1 "
		"(check DATABASE_URL / network)."
	) from None


def reset_test_postgres_database() -> str:
	if os.environ.get("USE_DEV_DATABASE_FOR_TESTS"):
		print(
			"reset_test_postgres_database: skipped (USE_DEV_DATABASE_FOR_TESTS)",
			file=sys.stderr,
		)
		return resolve_test_database_url()
	url = resolve_test_database_url()
	parsed = urlparse(url.strip())
	if parsed.scheme not in ("postgresql", "postgres"):
		return url
	dbname = (parsed.path or "").strip().lstrip("/")
	if not dbname:
		raise ValueError(f"Cannot reset: no database name in URL {url!r}")
	admin_conn = _admin_connection(parsed)
	admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
	try:
		with admin_conn.cursor() as cur:
			cur.execute(
				"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
				"WHERE datname = %s AND pid <> pg_backend_pid()",
				(dbname,),
			)
			cur.execute(
				sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
					sql.Identifier(dbname)
				)
			)
			cur.execute(
				sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname))
			)
	finally:
		admin_conn.close()
	return url


def _repo_root() -> Path:
	return Path(__file__).resolve().parents[1]


def load_dotenv_if_needed() -> None:
	if os.environ.get("SITE_ID") is None:
		from dotenv import load_dotenv

		root = _repo_root()
		load_dotenv(dotenv_path=root / "bootstrap/site_env")
		load_dotenv(dotenv_path=root / "env", override=True)


def derived_test_database_url(base: str) -> str:
	parsed = urlparse(base.strip())
	path = (parsed.path or "").strip()
	if path in ("", "/"):
		dbname = "postgres"
	else:
		dbname = path.lstrip("/")
	if dbname.endswith("_test"):
		return base.rstrip()
	new_path = f"/{dbname}_test"
	return urlunparse(parsed._replace(path=new_path))


def resolve_test_database_url() -> str:
	load_dotenv_if_needed()
	if os.environ.get("USE_DEV_DATABASE_FOR_TESTS"):
		raw = os.environ.get("DATABASE_URL")
		if raw is None or not str(raw).strip():
			raise RuntimeError(
				"USE_DEV_DATABASE_FOR_TESTS is set but DATABASE_URL is missing or empty"
			)
		return str(raw).strip()
	if "TEST_DATABASE_URL" in os.environ:
		ex = os.environ.get("TEST_DATABASE_URL", "").strip()
		if not ex:
			raise RuntimeError("TEST_DATABASE_URL is set but empty")
		return ex
	raw = os.environ.get("DATABASE_URL")
	if raw is None or not str(raw).strip():
		raise RuntimeError(
			"DATABASE_URL must be set (or set TEST_DATABASE_URL to the test DB URL)"
		)
	return derived_test_database_url(str(raw).strip())


def configure_process_for_tests() -> str:
	url = resolve_test_database_url()
	os.environ["DATABASE_URL"] = url
	return url


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"--reset",
		action="store_true",
		help="drop and recreate the test database (empty), then print its URL",
	)
	args = parser.parse_args()
	if args.reset:
		url = reset_test_postgres_database()
	else:
		url = resolve_test_database_url()
	print(url)


if __name__ == "__main__":
	main()
