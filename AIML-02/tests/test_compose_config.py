import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def test_compose_defines_orthanc_and_postgres():
    if shutil.which("docker") is None:
        pytest.skip("docker CLI not available")

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["docker", "compose", "config", "--services"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    services = set(result.stdout.split())
    assert {"postgres", "orthanc", "seed", "api", "worker"} <= services
