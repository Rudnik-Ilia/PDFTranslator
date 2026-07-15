from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base


def sqlite_url(output_dir: Path) -> str:
    return f"sqlite:///{output_dir / 'project_state.sqlite'}"


def create_session_factory(output_dir: Path) -> sessionmaker[Session]:
    output_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(sqlite_url(output_dir), future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
