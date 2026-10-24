from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from DB.models import Base


class Database:
    def __init__(self, database_url: str | None = None):
        if database_url:
            url = make_url(database_url)
        else:
            database_path = Path(__file__).resolve().parent / "github_agent.sqlite3"
            url = URL.create("sqlite", database=str(database_path))

        engine_options: dict = {}
        if url.get_backend_name() == "sqlite":
            engine_options["connect_args"] = {"check_same_thread": False}
            if url.database in (None, "", ":memory:"):
                engine_options["poolclass"] = StaticPool
            elif url.database != ":memory:" and not url.database.startswith("file:"):
                Path(url.database).expanduser().resolve().parent.mkdir(
                    parents=True, exist_ok=True
                )

        self.engine: Engine = create_engine(url, **engine_options)
        self._session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        Base.metadata.create_all(self.engine)

    def create_session(self) -> Session:
        return self._session_factory()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        session = self.create_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def close(self) -> None:
        self.engine.dispose()
