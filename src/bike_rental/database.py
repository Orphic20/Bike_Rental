import os
from collections.abc import Generator
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends
from sqlmodel import Session, create_engine

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Add the Supabase connection string to .env."
    )

engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "").lower() in {"1", "true", "yes"},
    # Supabase closes idle connections and Render's free tier suspends the
    # service, so a pooled connection is often dead by the time we reuse it.
    pool_pre_ping=True,
    pool_recycle=300,
    # Supabase's free tier has a low connection ceiling; stay well under it.
    pool_size=5,
    max_overflow=5,
)


def get_session() -> Generator[Session, None, None]:
    """Per-request database session.

    Endpoints commit explicitly. Anything left uncommitted is rolled back when
    the session closes, including when an endpoint raises.
    """
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
