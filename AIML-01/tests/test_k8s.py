import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def test_kustomize_builds_the_fraud_stack():
    if shutil.which("kubectl") is None:
        pytest.skip("kubectl not available")

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["kubectl", "kustomize", "k8s/overlays/kind"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr

    manifest = result.stdout
    assert manifest.count("kind: Deployment") >= 6
    assert "kind: Job" in manifest
    assert "name: api" in manifest
    assert "name: consumer" in manifest
    assert "name: dashboard" in manifest
    assert "name: drift-monitor" in manifest
    assert "name: feast-materialize" in manifest
    assert "name: postgres" in manifest
    assert "name: kafka" in manifest
    assert "nexvia-fraud:dev" in manifest
