import { formatMoney, formatScore, formatTime, scoreTone } from "../format";
import type { Transaction } from "../types";

export function LiveFeed({ transactions }: { transactions: Transaction[] }) {
  if (transactions.length === 0) {
    return <p className="muted">No transactions yet. Start the producer to replay the demo stream.</p>;
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Live feed</h2>
        <span className="muted">{transactions.length} most recent</span>
      </div>
      <table className="feed">
        <thead>
          <tr>
            <th>Time</th>
            <th>Transaction</th>
            <th>Card</th>
            <th className="right">Amount</th>
            <th className="right">Score</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((transaction) => (
            <tr key={transaction.transaction_id}>
              <td className="muted">{formatTime(transaction.event_time)}</td>
              <td className="mono">{transaction.transaction_id}</td>
              <td className="mono">{transaction.card_id}</td>
              <td className="right">{formatMoney(transaction.amount)}</td>
              <td className={`right score-${scoreTone(transaction.score)}`}>
                {formatScore(transaction.score)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
