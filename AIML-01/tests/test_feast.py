from pathlib import Path

import pandas as pd
import pytest
import yaml

from nexvia_fraud.features.service import FeatureService

feast = pytest.importorskip("feast")
from feast import FeatureStore  # noqa: E402

from feature_repo.features import CARD, FEATURE_GROUPS, build_views  # noqa: E402
from scripts.build_feast_features import build_feast_features  # noqa: E402

DEMO_CSV = Path("data/demo/transactions.csv")


@pytest.fixture(scope="module")
def feast_repo(tmp_path_factory):
    root = tmp_path_factory.mktemp("feast")
    table = build_feast_features(DEMO_CSV, root / "features.parquet")

    (root / "feature_store.yaml").write_text(
        yaml.safe_dump(
            {
                "project": "nexvia_test",
                "registry": str(root / "registry.db"),
                "provider": "local",
                "offline_store": {"type": "file"},
                "online_store": {"type": "sqlite", "path": str(root / "online.db")},
                "entity_key_serialization_version": 3,
            }
        )
    )

    store = FeatureStore(repo_path=str(root))
    store.apply([CARD, *build_views(root / "features.parquet")])
    return store, table


def test_views_cover_every_feature():
    covered = [feature for features in FEATURE_GROUPS.values() for feature in features]
    assert len(covered) == 13
    assert len(set(covered)) == 13


def test_historical_retrieval_matches_point_in_time_table(feast_repo):
    store, table = feast_repo
    sample = table.iloc[[10, 500, 1200]][["card_id", "event_timestamp"]].copy()

    features = [feature for features in FEATURE_GROUPS.values() for feature in features]
    refs = [f"{view}:{feature}" for view, group in FEATURE_GROUPS.items() for feature in group]
    retrieved = store.get_historical_features(entity_df=sample, features=refs).to_df()

    keyed = retrieved.set_index(["card_id", "event_timestamp"])
    for row in sample.itertuples(index=False):
        expected = table[
            (table["card_id"] == row.card_id) & (table["event_timestamp"] == row.event_timestamp)
        ].iloc[0]
        actual = keyed.loc[(row.card_id, row.event_timestamp)]
        for feature in features:
            assert actual[feature] == pytest.approx(float(expected[feature]), rel=1e-6)


def test_offline_table_matches_feature_service(tmp_path):
    frame = pd.read_csv(DEMO_CSV).head(50)
    frame["event_time"] = pd.to_datetime(frame["event_time"], utc=True)
    service = FeatureService.from_dataframe(pd.read_csv(DEMO_CSV))
    table = build_feast_features(DEMO_CSV, tmp_path / "parity.parquet")

    for row in frame.itertuples(index=False):
        expected = service.get_features(
            row.card_id,
            row.event_time,
            float(row.amount),
            row.device_id,
            row.email_domain,
            row.addr_id,
        )
        stored = table[table["transaction_id"] == row.transaction_id].iloc[0]
        for name, value in expected.items():
            assert stored[name] == pytest.approx(value, rel=1e-6)
