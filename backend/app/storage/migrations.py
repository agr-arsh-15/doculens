"""Run Alembic migrations programmatically at startup (works for SQLite and Postgres)."""
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine

_SCRIPTS = Path(__file__).resolve().parent / "alembic"
logging.getLogger("alembic").setLevel(logging.WARNING)


def _config(engine: Engine) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(_SCRIPTS))
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False).replace("%", "%%"))
    return cfg


def upgrade(engine: Engine) -> None:
    cfg = _config(engine)
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")
