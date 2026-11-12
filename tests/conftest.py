import pytest

from nexvia_fraud.data.generate_demo import generate_demo_transactions


@pytest.fixture(scope="session")
def demo_df():
    return generate_demo_transactions(1600, seed=7)
