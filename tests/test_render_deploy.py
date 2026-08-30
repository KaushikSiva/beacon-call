import subprocess
from pathlib import Path

import yaml

PROJECT_DIR = Path(__file__).resolve().parents[1]


def test_render_blueprint_is_single_disk_backed_supervised_service() -> None:
    blueprint = yaml.safe_load((PROJECT_DIR / "render.yaml").read_text())
    assert list(blueprint) == ["services"]
    assert len(blueprint["services"]) == 1
    service = blueprint["services"][0]

    assert service["type"] == "web"
    assert service["runtime"] == "docker"
    assert service["plan"] != "free"
    assert service["numInstances"] == 1
    assert service["healthCheckPath"] == "/api/health"
    assert service["maxShutdownDelaySeconds"] >= 135
    assert service["disk"] == {
        "name": "beacon-call-data",
        "mountPath": "/app/runtime",
        "sizeGB": 1,
    }


def test_render_blueprint_never_contains_secret_values() -> None:
    blueprint = yaml.safe_load((PROJECT_DIR / "render.yaml").read_text())
    env_vars = {item["key"]: item for item in blueprint["services"][0]["envVars"]}
    required_secrets = {
        "LIVEKIT_URL",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
        "LIVEKIT_SIP_TRUNK_ID",
        "BEACON_DESTINATION_NUMBER",
        "OPENAI_API_KEY",
    }
    assert all(env_vars[name] == {"key": name, "sync": False} for name in required_secrets)
    assert env_vars["BEACON_API_TOKEN"] == {
        "key": "BEACON_API_TOKEN",
        "generateValue": True,
    }
    assert env_vars["BEACON_RUNTIME_DIR"]["value"] == "/app/runtime"


def test_render_supervisor_has_valid_bash_and_docker_runs_it() -> None:
    script = PROJECT_DIR / "scripts" / "render_start.sh"
    subprocess.run(["bash", "-n", str(script)], check=True)
    dockerfile = (PROJECT_DIR / "Dockerfile").read_text()
    assert 'CMD ["./scripts/render_start.sh"]' in dockerfile
    assert "python main.py start --log-level=info" in script.read_text()
