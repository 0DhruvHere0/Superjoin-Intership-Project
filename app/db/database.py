from pathlib import Path
import sqlite3
from app.config import settings
def get_database_path() -> Path:
    database_path = Path(settings.database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return database_path
def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(get_database_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
def initialize_database() -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    schema_sql = schema_path.read_text(encoding="utf-8")
    connection = get_connection()
    try:
        connection.executescript(schema_sql)
        connection.commit()
    finally:
        connection.close()