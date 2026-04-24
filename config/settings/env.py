import os
from pathlib import Path
from urllib.parse import urlparse


def get_env(name: str, default=None):
    return os.getenv(name, default)


def get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int(name: str, default: int = 0) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def get_list(name: str, default=None, separator: str = ",") -> list[str]:
    if default is None:
        default = []
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(separator) if item.strip()]


def _parse_database_url(database_url: str):
    parsed = urlparse(database_url)
    engine_map = {
        "postgres": "django.db.backends.postgresql",
        "postgresql": "django.db.backends.postgresql",
        "sqlite": "django.db.backends.sqlite3",
    }
    engine = engine_map.get(parsed.scheme)
    if engine is None:
        raise ValueError(f"Unsupported database scheme: {parsed.scheme}")

    if engine == "django.db.backends.sqlite3":
        db_path = parsed.path.lstrip("/") or "db.sqlite3"
        return {"ENGINE": engine, "NAME": db_path}

    return {
        "ENGINE": engine,
        "NAME": parsed.path.lstrip("/"),
        "USER": parsed.username or "",
        "PASSWORD": parsed.password or "",
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
    }


def get_database_config(base_dir: Path, sqlite_name: str = "db.sqlite3"):
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        database_config = _parse_database_url(database_url)
        if database_config["ENGINE"] == "django.db.backends.sqlite3":
            database_config["NAME"] = str(base_dir / database_config["NAME"])
        return database_config

    postgres_db = os.getenv("POSTGRES_DB")
    if postgres_db:
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": postgres_db,
            "USER": os.getenv("POSTGRES_USER", "postgres"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }

    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(base_dir / sqlite_name),
    }
