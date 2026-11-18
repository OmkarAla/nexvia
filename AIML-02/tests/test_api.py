import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from nexvia_imaging.api.main import create_app
from nexvia_imaging.db.models import Base
from nexvia_imaging.db.repo import upsert_study

STUDY = {
    "study_uid": "1.2.3",
    "modality": "CR",
    "description": "SYNTHETIC CHEST",
    "n_instances": 1,
    "status": "analyzed",
    "findings": [
        {"label": "Effusion", "probability": 0.8},
        {"label": "Mass", "probability": 0.2},
    ],
    "overlays": ["1.2.3/effusion.png"],
    "model_version": "colab-nih-sample-001",
}


@pytest.fixture
def client(tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        upsert_study(session, STUDY)

    app = create_app(factory, tmp_path / "overlays", "colab-nih-sample-001")
    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    assert client.get("/health").json() == {
        "status": "ok",
        "model_version": "colab-nih-sample-001",
    }


def test_list_and_detail(client):
    studies = client.get("/studies").json()["studies"]
    assert len(studies) == 1
    assert studies[0]["findings"][0]["label"] == "Effusion"

    detail = client.get("/studies/1.2.3").json()["study"]
    assert detail["description"] == "SYNTHETIC CHEST"
    assert detail["status"] == "analyzed"


def test_missing_study_is_404(client):
    assert client.get("/studies/nope").status_code == 404


def test_decision_and_audit(client):
    response = client.post(
        "/studies/1.2.3/decision",
        json={"decision": "approve", "comment": "no acute finding", "reviewer": "ana"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["study"]["status"] == "reviewed"
    assert body["decision"]["decision"] == "approve"
    assert len(body["audit_hash"]) == 64

    second = client.post(
        "/studies/1.2.3/decision",
        json={"decision": "reject", "comment": "changed", "reviewer": "bob"},
    )
    assert second.status_code == 409

    audit = client.get("/audit").json()
    assert audit["valid"] is True
    assert len(audit["entries"]) == 1


def test_decision_requires_comment(client):
    response = client.post(
        "/studies/1.2.3/decision",
        json={"decision": "approve", "comment": "", "reviewer": "ana"},
    )
    assert response.status_code == 422


def test_demo_index_and_rendered_preview(tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app(factory, tmp_path / "overlays", "demo", demo_dir="data/demo")

    with TestClient(app) as test_client:
        studies = test_client.get("/demo/studies").json()["studies"]
        assert len(studies) == 7
        study_uid = studies[0]["study_uid"]
        preview = test_client.get(f"/studies/{study_uid}/preview")
        assert preview.status_code == 200
        assert preview.headers["content-type"] == "image/png"
