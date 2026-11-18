# AIML-02 — API

Base URL `http://localhost:8000`. Interactive docs at `/docs`.

## GET /health

```json
{ "status": "ok", "model_version": "colab-nih-sample-001" }
```

## GET /studies?status=analyzed&limit=100

```json
{
  "studies": [
    {
      "id": "1.2.826...",
      "modality": "CR",
      "description": "SYNTHETIC CHEST - EDUCATION ONLY - 00",
      "n_instances": 1,
      "status": "analyzed",
      "findings": [
        { "label": "Effusion", "probability": 0.42 },
        { "label": "Atelectasis", "probability": 0.31 }
      ],
      "overlays": ["1.2.826.../effusion.png", "1.2.826.../atelectasis.png"],
      "model_version": "colab-nih-sample-001",
      "created_at": "2026-11-18T10:00:00Z",
      "updated_at": "2026-11-18T10:00:05Z"
    }
  ]
}
```

`status` is one of `pending`, `analyzed`, `reviewed`.

## GET /studies/{id}

Returns `{ "study": { ... } }`. `404` when unknown.

## POST /studies/{id}/decision

```json
{ "decision": "approve", "comment": "no acute cardiopulmonary finding", "reviewer": "ana" }
```

- `200` — `{ "study", "decision", "audit_hash" }`
- `404` — study not found
- `409` — already reviewed
- `422` — empty comment/reviewer

## GET /audit

```json
{
  "entries": [
    {
      "id": 1,
      "prev_hash": "000...",
      "hash": "b4c1...",
      "payload": { "event": "review", "study_id": "1.2...", "decision": "approve" },
      "created_at": "2026-11-18T10:01:00"
    }
  ],
  "valid": true
}
```

## Static overlays

`GET /overlays/{study_id}/{finding}.png` serves the Grad-CAM PNGs written by the worker. The viewer overlays them on the Cornerstone3D canvas.
