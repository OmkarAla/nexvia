"""Load IEEE-CIS Fraud Detection into the project's transaction schema.

Column mapping (documented for the EDA/report):
    TransactionID -> transaction_id
    card1         -> card_id            ("card-<n>")
    TransactionDT -> event_time         (seconds from 2017-11-30 UTC)
    TransactionAmt-> amount
    DeviceInfo    -> device_id
    P/R_emaildomain -> email_domain
    addr1         -> addr_id            ("addr-<n>")
    isFraud       -> is_fraud

The raw competition files are never committed; `data/raw/` is gitignored.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

START = pd.Timestamp("2017-11-30T00:00:00Z")

TRANSACTION_COLUMNS = [
    "TransactionID",
    "TransactionDT",
    "TransactionAmt",
    "card1",
    "P_emaildomain",
    "R_emaildomain",
    "addr1",
    "isFraud",
]


def load_ieee(data_dir: str | Path, limit: int | None = None, seed: int = 7) -> pd.DataFrame:
    data_dir = Path(data_dir)
    transactions = pd.read_csv(
        data_dir / "train_transaction.csv", usecols=TRANSACTION_COLUMNS
    )
    identity = pd.read_csv(
        data_dir / "train_identity.csv", usecols=["TransactionID", "DeviceInfo"]
    )
    merged = transactions.merge(identity, on="TransactionID", how="left")

    if limit is not None and limit < len(merged):
        merged = merged.sample(n=limit, random_state=seed)

    frame = pd.DataFrame(
        {
            "transaction_id": merged["TransactionID"].astype(str),
            "card_id": "card-" + merged["card1"].fillna(0).astype("Int64").astype(str),
            "event_time": START + pd.to_timedelta(merged["TransactionDT"], unit="s"),
            "amount": merged["TransactionAmt"].astype(float),
            "device_id": merged["DeviceInfo"].fillna("unknown-device").astype(str),
            "email_domain": merged["P_emaildomain"]
            .fillna(merged["R_emaildomain"])
            .fillna("unknown.example")
            .astype(str),
            "addr_id": "addr-" + merged["addr1"].fillna(0).astype("Int64").astype(str),
            "is_fraud": merged["isFraud"].astype(int),
        }
    )
    return frame.sort_values("event_time").reset_index(drop=True)


def summarize_ieee(raw_dir: str | Path, frame: pd.DataFrame) -> dict:
    raw_dir = Path(raw_dir)
    transactions = pd.read_csv(
        raw_dir / "train_transaction.csv",
        usecols=["TransactionAmt", "card1", "P_emaildomain", "addr1", "isFraud"],
    )
    identity = pd.read_csv(raw_dir / "train_identity.csv", usecols=["TransactionID"])

    per_day = (
        frame.assign(day=frame["event_time"].dt.date)
        .groupby("day")["is_fraud"]
        .agg(["mean", "count"])
    )
    return {
        "rows_used": int(len(frame)),
        "rows_raw": int(len(transactions)),
        "fraud_rate_used": float(frame["is_fraud"].mean()),
        "fraud_rate_raw": float(transactions["isFraud"].mean()),
        "cards": int(frame["card_id"].nunique()),
        "start": str(frame["event_time"].min()),
        "end": str(frame["event_time"].max()),
        "amount_mean": float(frame["amount"].mean()),
        "amount_median": float(frame["amount"].median()),
        "amount_p99": float(frame["amount"].quantile(0.99)),
        "identity_coverage": float(len(identity) / len(transactions)),
        "missing": {
            "device": float(transactions["card1"].isna().mean()),
            "email": float(transactions["P_emaildomain"].isna().mean()),
            "addr": float(transactions["addr1"].isna().mean()),
        },
        "top_email_domains": frame["email_domain"].value_counts().head(10).to_dict(),
        "per_day_fraud_rate": {
            str(day): {"rate": float(row["mean"]), "count": int(row["count"])}
            for day, row in per_day.iterrows()
        },
    }


def write_eda_report(summary: dict, path: str | Path) -> None:
    per_day = summary["per_day_fraud_rate"]
    days = list(per_day.items())[:5]
    lines = [
        "# IEEE-CIS Fraud Detection — EDA",
        "",
        "Generated from `train_transaction.csv` + `train_identity.csv`.",
        "",
        "## Class imbalance",
        "",
        f"- Raw rows: **{summary['rows_raw']:,}**",
        f"- Fraud rate (raw): **{summary['fraud_rate_raw']:.4%}**",
        f"- Rows used for the demo training set: {summary['rows_used']:,}",
        f"- Fraud rate (used): {summary['fraud_rate_used']:.4%}",
        "",
        "This is the heavy imbalance the brief calls out. Accuracy is meaningless; "
        "the project evaluates with PR-AUC and precision/recall at a fixed FPR.",
        "",
        "## Time range and cards",
        "",
        f"- {summary['start']} → {summary['end']}",
        f"- Distinct cards: {summary['cards']:,}",
        "",
        "## Amounts",
        "",
        f"- Mean: {summary['amount_mean']:.2f}",
        f"- Median: {summary['amount_median']:.2f}",
        f"- p99: {summary['amount_p99']:.2f}",
        "",
        "## Missingness",
        "",
        f"- Identity row coverage: {summary['identity_coverage']:.2%} of transactions",
        f"- Missing email domain: {summary['missing']['email']:.2%}",
        f"- Missing address: {summary['missing']['addr']:.2%}",
        "",
        "## Top email domains",
        "",
    ]
    for domain, count in summary["top_email_domains"].items():
        lines.append(f"- `{domain}`: {count:,}")
    lines += ["", "## Fraud rate by day (first five)", ""]
    for day, values in days:
        lines.append(f"- {day}: {values['rate']:.3%} of {values['count']:,} transactions")
    lines += [
        "",
        "## Notes",
        "",
        "- The loader maps card1/DeviceInfo/email/addr1 into the project schema; "
        "the mapping is documented in `src/nexvia_fraud/data/load_ieee.py`.",
        "- The demo artifacts in `artifacts/demo/` remain synthetic; real-data "
        "artifacts are written to `artifacts/ieee/`.",
        "",
    ]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load and summarize IEEE-CIS")
    parser.add_argument("--data-dir", default="data/raw/ieee")
    parser.add_argument("--out", default="data/ieee/transactions.parquet")
    parser.add_argument("--limit", type=int, default=150000)
    parser.add_argument("--eda", default="reports/ieee_eda.md")
    parser.add_argument("--json", default="reports/ieee_eda.json")
    args = parser.parse_args()

    frame = load_ieee(args.data_dir, limit=args.limit)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out, index=False)

    summary = summarize_ieee(args.data_dir, frame)
    write_eda_report(summary, args.eda)
    Path(args.json).write_text(json.dumps(summary, indent=2, default=str))
    print(
        f"wrote {len(frame):,} transactions to {out}; "
        f"fraud rate {summary['fraud_rate_used']:.3%}"
    )


if __name__ == "__main__":
    main()
