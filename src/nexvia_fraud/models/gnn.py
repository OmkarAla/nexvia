"""Train a heterogeneous GraphSAGE model and export card-level fraud scores."""

from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.metrics import average_precision_score, roc_auc_score
from torch_geometric.data import HeteroData
from torch_geometric.nn import HeteroConv, SAGEConv

from nexvia_fraud.models.graph import TransactionGraph, build_graph

RELATIONS = [
    ("card", "uses", "device"),
    ("device", "used_by", "card"),
    ("card", "uses", "email"),
    ("email", "used_by", "card"),
    ("card", "uses", "addr"),
    ("addr", "used_by", "card"),
]
HIDDEN = 32


class FraudSAGE(torch.nn.Module):
    def __init__(self, in_dims: dict[str, int], hidden: int = HIDDEN) -> None:
        super().__init__()
        self.conv1 = HeteroConv(
            {
                relation: SAGEConv((in_dims[relation[0]], in_dims[relation[2]]), hidden)
                for relation in RELATIONS
            },
            aggr="sum",
        )
        self.conv2 = HeteroConv(
            {relation: SAGEConv((hidden, hidden), hidden) for relation in RELATIONS},
            aggr="sum",
        )
        self.head = torch.nn.Linear(hidden, 1)

    def forward(self, x_dict, edge_index_dict):
        x = self.conv1(x_dict, edge_index_dict)
        x = {key: F.relu(value) for key, value in x.items()}
        x = self.conv2(x, edge_index_dict)
        x = {key: F.relu(value) for key, value in x.items()}
        embeddings = x["card"]
        return self.head(embeddings).squeeze(-1), embeddings


def _in_dims(graph: TransactionGraph) -> dict[str, int]:
    return {
        node_type: int(graph.data[node_type].x.shape[1])
        for node_type in ("card", "device", "email", "addr")
    }


def _forward(model: FraudSAGE, data: HeteroData):
    return model(data.x_dict, data.edge_index_dict)


def _safe_auc(y: np.ndarray, scores: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return 0.0
    return float(average_precision_score(y, scores))


def train_gnn(
    df: pd.DataFrame,
    out_dir: str | Path,
    run_id: str,
    epochs: int = 60,
    seed: int = 7,
) -> dict:
    torch.manual_seed(seed)
    np.random.seed(seed)

    frame = df.copy()
    frame["event_time"] = pd.to_datetime(frame["event_time"], utc=True)
    validation_start = frame["event_time"].quantile(0.7)
    window = frame[frame["event_time"] < validation_start].reset_index(drop=True)

    graph = build_graph(window)
    labels = graph.data["card"].y
    n_cards = len(graph.cards)

    rng = np.random.default_rng(seed)
    order = rng.permutation(n_cards)
    n_train = max(1, int(n_cards * 0.7))
    n_val = max(1, int(n_cards * 0.15))
    split = np.full(n_cards, "test", dtype=object)
    split[order[:n_train]] = "train"
    split[order[n_train : n_train + n_val]] = "val"

    train_mask = torch.tensor(split == "train")
    val_mask = torch.tensor(split == "val")

    model = FraudSAGE(_in_dims(graph))
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=1e-4)

    positives = float(labels[train_mask].sum())
    negatives = float(train_mask.sum() - positives)
    pos_weight = torch.tensor([negatives / positives if positives > 0 else 1.0])
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    best_state = copy.deepcopy(model.state_dict())
    best_val = -1.0
    epochs_run = 0
    patience = 10
    stale = 0

    for epoch in range(epochs):
        epochs_run = epoch + 1
        model.train()
        optimizer.zero_grad()
        logits, _ = _forward(model, graph.data)
        loss = loss_fn(logits[train_mask], labels[train_mask])
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            logits, _ = _forward(model, graph.data)
            probabilities = torch.sigmoid(logits[val_mask]).numpy()
        val_score = _safe_auc(labels[val_mask].numpy(), probabilities)

        if val_score > best_val:
            best_val = val_score
            best_state = copy.deepcopy(model.state_dict())
            stale = 0
        else:
            stale += 1
            if stale >= patience:
                break

    model.load_state_dict(best_state)
    model.eval()

    full_graph = build_graph(frame)
    with torch.no_grad():
        logits, _ = _forward(model, full_graph.data)
        full_scores = torch.sigmoid(logits).numpy()

    split_lookup = dict(zip(graph.cards["card_id"], split, strict=False))
    score_frame = pd.DataFrame(
        {
            "card_id": full_graph.cards["card_id"],
            "gnn_score": full_scores,
        }
    )
    score_frame["split"] = score_frame["card_id"].map(split_lookup).fillna("unseen")

    test_cards = score_frame[score_frame["split"] == "test"]
    test_labels = full_graph.cards.set_index("card_id")["is_fraud"]
    y_test = test_labels.reindex(test_cards["card_id"]).to_numpy()
    pr_auc = _safe_auc(y_test, test_cards["gnn_score"].to_numpy())
    roc_auc = (
        float(roc_auc_score(y_test, test_cards["gnn_score"]))
        if len(np.unique(y_test)) > 1
        else 0.0
    )

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    torch.save(
        {"state_dict": model.state_dict(), "in_dims": _in_dims(graph), "hidden": HIDDEN},
        out / "gnn_model.pt",
    )
    score_frame.to_parquet(out / "gnn_card_scores.parquet", index=False)

    metrics = {
        "run_id": run_id,
        "pr_auc": pr_auc,
        "roc_auc": roc_auc,
        "val_pr_auc": float(best_val),
        "n_train_cards": int((split == "train").sum()),
        "n_val_cards": int((split == "val").sum()),
        "n_test_cards": int((split == "test").sum()),
        "n_cards_total": int(len(full_graph.cards)),
        "epochs_run": epochs_run,
        "seed": seed,
        "validation_start": str(validation_start.isoformat()),
    }
    for key, value in metrics.items():
        if isinstance(value, float) and not math.isfinite(value):
            metrics[key] = 0.0
    (out / "gnn_metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics


def load_gnn_scores(out_dir: str | Path) -> dict[str, float]:
    path = Path(out_dir) / "gnn_card_scores.parquet"
    if not path.exists():
        return {}
    frame = pd.read_parquet(path)
    return dict(zip(frame["card_id"], frame["gnn_score"], strict=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the GraphSAGE fraud model")
    parser.add_argument("--data", default="data/demo/transactions.csv")
    parser.add_argument("--out", default="artifacts/demo")
    parser.add_argument("--run-id", default="demo-gnn-001")
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    frame = pd.read_csv(args.data)
    metrics = train_gnn(frame, args.out, args.run_id, args.epochs, args.seed)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
