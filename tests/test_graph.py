import pandas as pd

from nexvia_fraud.models.graph import build_graph


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            dict(transaction_id="t1", card_id="c1", event_time="2026-01-01T00:00:00Z",
                 amount=10.0, device_id="d1", email_domain="e1.com", addr_id="a1", is_fraud=1),
            dict(transaction_id="t2", card_id="c1", event_time="2026-01-01T00:10:00Z",
                 amount=20.0, device_id="d2", email_domain="e1.com", addr_id="a1", is_fraud=1),
            dict(transaction_id="t3", card_id="c2", event_time="2026-01-01T00:20:00Z",
                 amount=30.0, device_id="d1", email_domain="e2.com", addr_id="a1", is_fraud=0),
            dict(transaction_id="t4", card_id="c3", event_time="2026-01-01T00:30:00Z",
                 amount=40.0, device_id="d3", email_domain="e3.com", addr_id="a2", is_fraud=0),
        ]
    )


def test_card_nodes_and_features():
    graph = build_graph(_frame())

    assert graph.data["card"].num_nodes == 3
    assert graph.data["card"].x.shape == (3, 6)
    assert set(graph.cards.columns) == {
        "card_id",
        "is_fraud",
        "n_txn",
        "amount_mean",
        "amount_std",
        "n_devices",
        "n_emails",
        "n_addrs",
    }
    labels = graph.cards.set_index("card_id")["is_fraud"].to_dict()
    assert labels == {"c1": 1, "c2": 0, "c3": 0}


def test_entity_nodes_and_bidirectional_edges():
    graph = build_graph(_frame())

    assert graph.data["device"].num_nodes == 3
    assert graph.data["email"].num_nodes == 3
    assert graph.data["addr"].num_nodes == 2

    # c1-d1, c1-d2, c2-d1, c3-d3
    assert graph.data["card", "uses", "device"].edge_index.shape == (2, 4)
    assert graph.data["device", "used_by", "card"].edge_index.shape == (2, 4)
    assert graph.data["card", "uses", "email"].edge_index.shape == (2, 3)
    assert graph.data["addr", "used_by", "card"].edge_index.shape == (2, 3)


def test_shared_device_is_visible_in_node_features():
    graph = build_graph(_frame())

    card_features = graph.data["card"].x
    device_features = graph.data["device"].x
    assert card_features.shape[0] == 3
    # device d1 is used by two cards; its second feature is the distinct-card count
    d1_index = graph.device_index["d1"]
    assert device_features[d1_index, 1] > 1
