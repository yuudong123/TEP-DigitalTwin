import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runtime_audit", ROOT / "deploy/runtime_status.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def kafka():
    return {"State": {"Status": "running", "Running": True, "Health": {"Status": "healthy"}},
            "Mounts": [{"Type": "volume", "Name": "tep-kafka-data", "Destination": "/tmp/kraft-combined-logs"}]}


def app():
    return {"State": {"Status": "running", "Running": True},
            "Config": {"Env": ["RETRAIN_ENABLED=false", "SECRET=never-print-this"]}}


def entries(root, names):
    for name in names:
        path = root / audit.ENTRYPOINTS[name]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()


def test_missing_api_is_partial_not_full_success(tmp_path):
    entries(tmp_path, ["inference", "monitor"])
    result = audit.evaluate(tmp_path, {"kafka": kafka(), "inference": app(), "monitor": app()})
    assert result["implemented_runtime_ready"]
    assert not result["full_runtime_ready"]
    assert result["pending_entrypoints"] == ["api"]
    assert "never-print-this" not in str(result)


def test_stopped_or_missing_implemented_service_fails(tmp_path):
    entries(tmp_path, ["monitor"])
    result = audit.evaluate(tmp_path, {"kafka": kafka()})
    assert "monitor: container missing" in result["issues"]
    stopped = app()
    stopped["State"]["Status"] = "exited"
    result = audit.evaluate(tmp_path, {"kafka": kafka(), "monitor": stopped})
    assert "monitor: not ready" in result["issues"]


def test_wrong_volume_or_unhealthy_kafka_fails(tmp_path):
    state = kafka()
    state["Mounts"][0]["Name"] = "temporary-volume"
    state["State"]["Health"]["Status"] = "starting"
    result = audit.evaluate(tmp_path, {"kafka": state})
    assert "kafka: expected persistent volume missing" in result["issues"]
    assert "kafka: healthy check required" in result["issues"]


def test_automatic_retraining_requires_explicit_disable(tmp_path):
    entries(tmp_path, ["monitor"])
    state = app()
    state["Config"]["Env"] = ["RETRAIN_ENABLED=true"]
    result = audit.evaluate(tmp_path, {"kafka": kafka(), "monitor": state})
    assert "monitor: explicit RETRAIN_ENABLED=false required" in result["issues"]


def test_complete_readiness_is_not_an_e2e_claim(tmp_path):
    entries(tmp_path, audit.ENTRYPOINTS)
    result = audit.evaluate(tmp_path, {"kafka": kafka(), "api": app(), "monitor": app(), "inference": app()})
    assert result["full_runtime_ready"]
    assert "not application E2E" in result["scope"]


def test_jenkins_uses_checked_out_script_and_archives_reports():
    source = (ROOT / "Jenkinsfile").read_text()
    assert '%WORKSPACE%\\\\deploy\\\\09-manual-deploy.ps1' in source
    assert 'archiveArtifacts' in source
