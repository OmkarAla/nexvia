"""Build a heterogeneous card/device/email/address graph from transactions."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler
from torch_geometric.data import HeteroData

CARD_FEATURES = ["n_txn", "amount_mean", "amount_std", "n_devices", "n_emails", "n_addrs"]
ENTITY_FEATURES = ["n_txn", "n_cards", "amount_mean"]


@dataclass
class TransactionGraph:
    data: HeteroData
    cards: pd.DataFrame
    card_index: dict[str, int]
    device_index: dict[str, int]
    email_index: dict[str, int]
    addr_index: dict[str, int]


def _entity_features(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    grouped = (
        frame.groupby(column)
        .agg(
            n_txn=("transaction_id", "count"),
            n_cards=("card_id", "nunique"),
            amount_mean=("amount", "mean"),
        )
        .reset_index()
    )
    return grouped


def _index(values) -> dict[str, int]:
    return {value: index for index, value in enumerate(sorted(values))}


def _scaled(frame: pd.DataFrame, columns: list[str]) -> torch.Tensor:
    values = frame[columns].to_numpy(dtype=float)
    values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
    return torch.tensor(StandardScaler().fit_transform(values), dtype=torch.float)


def _edge_index(
    frame: pd.DataFrame,
    left_column: str,
    left_index: dict[str, int],
    right_column: str,
    right_index: dict[str, int],
) -> torch.Tensor:
    pairs = frame[[left_column, right_column]].drop_duplicates()
    left = torch.tensor([left_index[value] for value in pairs[left_column]], dtype=torch.long)
    right = torch.tensor([right_index[value] for value in pairs[right_column]], dtype=torch.long)
    return torch.stack([left, right])


def build_graph(df: pd.DataFrame) -> TransactionGraph:
    frame = df.copy()

    card_ids = sorted(frame["card_id"].unique())
    cards = (
        frame.groupby("card_id")
        .agg(
            is_fraud=("is_fraud", "max"),
            n_txn=("transaction_id", "count"),
            amount_mean=("amount", "mean"),
            amount_std=("amount", "std"),
            n_devices=("device_id", "nunique"),
            n_emails=("email_domain", "nunique"),
            n_addrs=("addr_id", "nunique"),
        )
        .reindex(card_ids)
        .reset_index()
    )
    cards["amount_std"] = cards["amount_std"].fillna(0.0)
    cards["is_fraud"] = cards["is_fraud"].astype(int)

    devices = _entity_features(frame, "device_id")
    emails = _entity_features(frame, "email_domain")
    addrs = _entity_features(frame, "addr_id")

    card_index = _index(cards["card_id"])
    device_index = _index(devices["device_id"])
    email_index = _index(emails["email_domain"])
    addr_index = _index(addrs["addr_id"])

    data = HeteroData()
    data["card"].x = _scaled(cards, CARD_FEATURES)
    data["card"].y = torch.tensor(cards["is_fraud"].to_numpy(), dtype=torch.float)

    for name, table in (
        ("device", devices),
        ("email", emails),
        ("addr", addrs),
    ):
        data[name].x = _scaled(table, ENTITY_FEATURES)

    for name, column, mapping in (
        ("device", "device_id", device_index),
        ("email", "email_domain", email_index),
        ("addr", "addr_id", addr_index),
    ):
        forward = _edge_index(frame, "card_id", card_index, column, mapping)
        data["card", "uses", name].edge_index = forward
        data[name, "used_by", "card"].edge_index = forward.flip(0)

    return TransactionGraph(
        data=data,
        cards=cards,
        card_index=card_index,
        device_index=device_index,
        email_index=email_index,
        addr_index=addr_index,
    )
