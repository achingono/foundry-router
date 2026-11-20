"""Explicit local Docker integration for real native intake children."""

import json
import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.docker
def test_native_intake_real_linux_children():
    fixture = Path(__file__).parent / "fixtures" / "azure_intake_linux.py"
    image = os.environ.get("FOUNDRY_AZURE_INTAKE_TEST_IMAGE", "foundry-router-runtime-intake:local")
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--memory",
            "1g",
            "--cpus",
            "2",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=256m,mode=1777",
            "--mount",
            f"type=bind,src={fixture},dst=/verify.py,readonly",
            "--entrypoint",
            "python",
            image,
            "/verify.py",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    assert result.returncode == 0, result.stderr[-4096:]
    receipt = json.loads(result.stdout.splitlines()[-1])
    assert receipt["passed"] and receipt["native_children"] == 7 and receipt["all_leases_clean"]
    assert receipt["no_provider_network"] and not receipt["capacity_acceptance"]
    assert receipt["translated_children"] == 10
    assert {item["provider"] for item in receipt["translated_receipts"]} == {
        "azure_anthropic",
        "azure_mai",
    }
    assert all(
        item["passed"] and item["all_leases_clean"] for item in receipt["translated_receipts"]
    )
    assert any(
        request["literal_unicode"] and request["input_bytes"] > 8 * 1024 * 1024
        for request in receipt["requests"]
    )
