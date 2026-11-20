from pathlib import Path

import pandas as pd
import pytest
import yaml
from feast import FeatureStore

from feature_repo.features import ALL_FEATURES, TRANSACTION, build_transaction_view
from nexvia_fraud.features.feast_service import (
    FeastFeatureService,
    load_training_matrix,
    transaction_refs,
)
from nexvia_fraud.features.service import FeatureService
from scripts.build_feast_features import build_feast_features

DEMO_CSV = Path("data/demo/transactions.csv")


@pytest.fixture(scope="module")
def feast_repo(tmp_path_factory):
    root = tmp_path_factory.mktemp("feast-serving")
    table = build_feast_features(DEMO_CSV, root / "features.parquet")
    (root / "feature_store.yaml").write_text(
        yaml.safe_dump(
            {
                "project": "nexvia_serve_test",
                "registry": str(root / "registry.db"),
                "provider": "local",
                "offline_store": {"type": "file"},
                "online_store": {"type": "sqlite", "path": str(root / "online.db")},
                "entity_key_serialization_version": 3,
            }
        )
    )
    store = FeatureStore(repo_path=str(root))
    store.apply([TRANSACTION, build_transaction_view(root / "features.parquet")])
    start = table["event_timestamp"].min().to_pydatetime()
    end = (table["event_timestamp"].max() + pd.Timedelta(days=1)).to_pydatetime()
    store.materialize(start_date=start, end_date=end)
    return root, table


def test_online_lookup_matches_offline_table(feast_repo):
    root, table = feast_repo
    serving = FeastFeatureService(root)

    sample = table.sample(n=5, random_state=7)
    for row in sample.itertuples(index=False):
        actual = serving.get_features(
            row.card_id,
            pd.Timestamp(row.event_timestamp),
            0.0,
            "",
            "",
            "",
            transaction_id=row.transaction_id,
        )
        for feature in ALL_FEATURES:
            assert actual[feature] == pytest.approx(
                float(getattr(row, feature)), rel=1e-5
            )


def test_unknown_transaction_falls_back(feast_repo):
    root, table = feast_repo
    local = FeatureService.from_dataframe(pd.read_csv(DEMO_CSV))
    serving = FeastFeatureService(root, fallback=local)

    row = table.iloc[0]
    values = serving.get_features(
        row.card_id,
        pd.Timestamp(row.event_timestamp),
        10.0,
        "d",
        "e.com",
        "a",
        transaction_id="not-in-feast",
    )

    assert set(values) == set(local.feature_names())
    assert all(isinstance(value, float) for value in values.values())


def test_training_matrix_matches_local(feast_repo):
    root, table = feast_repo
    local = FeatureService.from_dataframe(pd.read_csv(DEMO_CSV))
    frame = pd.read_csv(DEMO_CSV).head(10)
    frame["event_time"] = pd.to_datetime(frame["event_time"], utc=True)
    frame = frame.sort_values("event_time").reset_index(drop=True)

    matrix = load_training_matrix(frame, root)

    assert list(matrix.columns) == local.feature_names()
    for index, row in frame.iterrows():
        expected = local.get_features(
            row.card_id,
            row.event_time,
            float(row.amount),
            row.device_id,
            row.email_domain,
            row.addr_id,
        )
        for feature in local.feature_names():
            assert matrix.iloc[index][feature] == pytest.approx(
                expected[feature], rel=1e-5
            )
    assert len(transaction_refs()) == 13
