# Fraud demo recording runbook

Target: one 5–8 minute narrated screen recording of AIML-01. Do not commit the video; upload it and link it from the README.

## 1. Reset and start the API (Terminal 1)

```powershell
cd D:\nexvia\AIML-01
python -m pip install -e ".[dev]"
Remove-Item data\dev.db -ErrorAction SilentlyContinue
$env:DATABASE_URL = "sqlite:///./data/dev.db"
python scripts/seed.py --limit 600
$env:DRIFT_SHARE_THRESHOLD = "0.3"
python scripts/drift_job.py --once
python -m uvicorn nexvia_fraud.api.app:app --host 127.0.0.1 --port 8000
```

Wait for `Application startup complete`. Then verify in another terminal:

```powershell
curl http://127.0.0.1:8000/health
curl "http://127.0.0.1:8000/alerts?status=open&min_score=0.5&limit=5"
curl http://127.0.0.1:8000/drift/latest
```

You should see `model_version: demo-001`, roughly 30 open alerts, and a drift report around 46%.

## 2. Start the dashboard (Terminal 2)

```powershell
cd D:\nexvia\AIML-01\dashboard
npm install
npm run dev
```

Open <http://localhost:5173>. The queue should populate within ~3 seconds. If port 5173 is busy, use the port Vite prints.

## 3. Recording setup

- OBS Studio (recommended): Display Capture + microphone, 1920×1080, 30 fps, MP4.
- Or Windows Game Bar: `Win+Alt+R` (records the active window).
- Close Slack/Discord, enable Focus Assist, hide browser bookmarks (`Ctrl+Shift+B`), 100% zoom.
- Never show `.env`, the Kaggle token, or the terminal history.
- Test 10 seconds, confirm audio, then start the real take.

## 4. Shot list (~6–7 minutes)

| Time | On screen | Say / do |
|---|---|---|
| 0:00 | Dashboard header | What it is: real-time fraud scoring + analyst review. Synthetic demo data, not production. |
| 0:30 | Case queue | 30+ alerts from a replayed Kafka stream; scores above threshold create cases. |
| 1:00 | **Live feed** tab | Scored transactions arriving; point out `B` markers from the blended model. |
| 1:40 | **Case queue** | Filter min score; open the top alert (e.g. `txn-002994`). |
| 2:10 | Case detail | Score, amount, card, prior cases, **mode: blended**, GNN score. |
| 2:40 | SHAP bars | Explain positive contributions (address/device sharing) and that SHAP is XGBoost-only. |
| 3:40 | Decision | Type a reason: "matches a known fraud ring"; click **Reject**. |
| 4:10 | Status + audit | Status changes; audit hash appears. |
| 4:30 | **Model health** | 46% drifted features, per-feature scores, one open retraining request. |
| 5:20 | Request | Approve it; explain nothing retrains automatically — human gate. |
| 5:50 | `/audit` tab | `valid: true`, chained entry with the decision payload. |
| 6:20 | Close | Metrics: PR-AUC 0.740 / blended 0.839; p99 ~26 ms; limitations next. |

## 5. Clean take

If you make a mistake, stop, `Ctrl+C` both terminals, delete `data\dev.db`, and repeat from step 1.

## 6. Publish

- Upload to Google Drive or YouTube **unlisted**; do not commit the MP4.
- Add the link to `AIML-01/README.md` and `SUBMISSION.md`.
- Suggested filename: `AIML-01-fraud-demo.mp4`.
