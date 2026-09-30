"""Read-only container readiness audit. Does not start, stop or change services."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

ENTRYPOINTS = {"api": "src/api/main.py", "inference": "src/inference/main.py",
               "monitor": "src/monitoring/main.py"}


def evaluate(root: Path, states: dict) -> dict:
    pending = [name for name, path in ENTRYPOINTS.items() if not (root / path).is_file()]
    required = ["kafka"] + [name for name in ENTRYPOINTS if name not in pending]
    issues = []
    services = {}
    for name in required:
        state = states.get(name)
        if state is None:
            issues.append(f"{name}: container missing")
            services[name] = {"running": False}
            continue
        runtime = state.get("State", {})
        running = runtime.get("Status") == "running" and runtime.get("Running") is True
        health = runtime.get("Health", {}).get("Status")
        services[name] = {"running": running, "health": health,
                          "restart_count": state.get("RestartCount", 0)}
        if not running or (health and health != "healthy"):
            issues.append(f"{name}: not ready")
        if name == "kafka":
            if health != "healthy":
                issues.append("kafka: healthy check required")
            mounts = state.get("Mounts", [])
            if not any(m.get("Type") == "volume" and m.get("Name") == "tep-kafka-data"
                       and m.get("Destination") == "/tmp/kraft-combined-logs" for m in mounts):
                issues.append("kafka: expected persistent volume missing")
        if name == "monitor":
            # No environment values other than this public safety flag are exposed.
            env = dict(item.split("=", 1) for item in state.get("Config", {}).get("Env", []) if "=" in item)
            disabled = env.get("RETRAIN_ENABLED", "").strip().lower() in {"false", "0", "no", "off"}
            services[name]["retraining_disabled"] = disabled
            if not disabled:
                issues.append("monitor: explicit RETRAIN_ENABLED=false required")
    return {"time": datetime.now(timezone.utc).isoformat(), "services": services,
            "pending_entrypoints": pending, "issues": issues,
            "full_runtime_ready": not pending and not issues,
            "implemented_runtime_ready": not issues,
            "scope": "container readiness only; not application E2E or reboot proof"}


def audit(root: Path, docker: str) -> dict:
    states = {}
    for name in ("kafka", *ENTRYPOINTS):
        command = subprocess.run([docker, "inspect", f"tep-{name}"], capture_output=True, text=True)
        if command.returncode == 0:
            states[name] = json.loads(command.stdout)[0]
        elif "No such" not in command.stderr and "no such" not in command.stderr:
            raise RuntimeError("Docker audit failed; check daemon connectivity")
    result = evaluate(root, states)
    revision = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True)
    result["revision"] = revision.stdout.strip()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root, args.docker)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result["issues"] else 2 if result["pending_entrypoints"] else 0)
