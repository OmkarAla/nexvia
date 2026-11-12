# Next Session Handoff — 2026-11-13 (updated)

## Submission constraint change

- The evaluation allows **one GitHub URL** with subfolders per project.
- Both projects now live under `D:
exvia`: `nexvia-fraud/` (built) and `nexvia-imaging/` (scaffold).
- The standalone `D:
exvia-fraud` folder is a leftover copy; make changes in `D:
exvia
exvia-fraud` from now on.
- CI moved to the repository root: `.github/workflows/fraud-ci.yml`.

---

# Next Session Handoff — 2026-11-12

## Where we are

- Design doc written: `docs/superpowers/specs/2026-11-11-two-ml-platforms-design.md`
- Builder review done; most questions resolved in the doc.
- No product code written yet. Design is **not approved**.
- Two repos planned: `nexvia-fraud` and `nexvia-imaging`.

## Decisions locked in

- Two standalone repos, not a monorepo.
- Training on free-tier Google Colab (T4); serving/demos CPU-only.
- Kaggle token will be supplied by the human partner.
- Deploy on Render (Python services) + Vercel (React frontends).
- Repos public from day one.
- Fraud first, then imaging; vertical slice + recording, then depth.

## Questions to open the next session with

1. **Design approval** — approve `docs/superpowers/specs/2026-11-11-two-ml-platforms-design.md`, or what needs to change?
2. **Hosting accounts** — who owns Render/Vercel/Upstash/R2: the human partner creates them, or should I prepare configs for them to connect?
3. **People** — how many interns, and whose names/roles go into the reflections and deck?
4. **Branding** — confirm `nexvia-fraud` / `nexvia-imaging`, or different names?

## Next action after approval

Invoke `writing-plans` and produce the implementation plan, starting with the fraud vertical slice:
producer → Kafka → FastAPI scorer (XGBoost) → Postgres → React review dashboard.
