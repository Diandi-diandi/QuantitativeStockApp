"""
Central configuration: paths and secrets.

Loading secrets from InfoSet (a git-ignored file) is intentional so this file
can be committed without leaking credentials. If InfoSet is missing, a clear
error is raised so setup failures do not surface as attribute errors later.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "db"
DB_PATH = DB_DIR / "quantstock.db"
BACKUP_DIR = BASE_DIR / "db_backup"

DB_DIR.mkdir(exist_ok=True)


def _load_secrets():
    try:
        import InfoSet
    except ImportError as e:
        raise RuntimeError(
            "InfoSet.py not found. Copy InfoSet.example.py to InfoSet.py "
            "and fill in api_key and sys_pwd."
        ) from e
    return InfoSet.api_key, InfoSet.sys_pwd


API_KEY, SYS_PWD = _load_secrets()
