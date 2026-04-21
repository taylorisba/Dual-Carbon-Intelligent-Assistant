from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.core.config import get_settings


settings = get_settings()
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=False,
)



def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
