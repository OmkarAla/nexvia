import os

os.environ.setdefault("NEXVIA_DISABLE_MLFLOW", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from nexvia_fraud.data.generate_demo import generate_demo_transactions
from nexvia_fraud.db.models import Base


@pytest.fixture(scope="session")
def demo_df():
    return generate_demo_transactions(1600, seed=7)


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
