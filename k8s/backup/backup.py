"""Quiesce Odoo writers, produce a consistent DB/filestore backup, then resume."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import ssl
import subprocess
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

NS = os.environ.get("POD_NAMESPACE", "odoo-system")
TOKEN = Path("/var/run/secrets/kubernetes.io/serviceaccount/token").read_text().strip()
TLS = ssl.create_default_context(cafile="/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")
BASE = "https://kubernetes.default.svc"
SCALES = [f"/apis/argoproj.io/v1alpha1/namespaces/{NS}/rollouts/odoo-web-rollout/scale"] + [
    f"/apis/apps/v1/namespaces/{NS}/deployments/{name}/scale"
    for name in ("odoo-worker", "odoo-cron", "odoo-queue-runner")]
SCALERS = [f"/apis/keda.sh/v1alpha1/namespaces/{NS}/scaledobjects/{name}"
           for name in ("odoo-web-autoscaler", "odoo-worker-autoscaler")]
LOCKS = f"/api/v1/namespaces/{NS}/configmaps"
PAUSE_KEYS = ("autoscaling.keda.sh/paused", "autoscaling.keda.sh/paused-replicas")

def api(path, method="GET", value=None):
    data = None if value is None else json.dumps(value).encode()
    headers = {"Authorization": f"Bearer {TOKEN}"}
    if value is not None:
        headers["Content-Type"] = "application/merge-patch+json" if method == "PATCH" else "application/json"
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, context=TLS, timeout=30) as response:
        return json.load(response)

def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def stop_signal(signum, frame):
    raise InterruptedError(f"Backup interrupted by signal {signum}")

def resume(state):
    errors = []
    # Restore replicas before releasing KEDA so paused-replicas=0 cannot race the API.
    for path, count in state["scales"].items():
        try:
            api(path, "PATCH", {"spec": {"replicas": count}})
        except Exception as error:
            errors.append(str(error))
    for path, annotations in state["scalers"].items():
        try:
            api(path, "PATCH", {"metadata": {"annotations": annotations}})
        except Exception as error:
            errors.append(str(error))
    if errors:
        raise RuntimeError("Resume failed; recover from odoo-backup-lock: " + "; ".join(errors))

def main():
    database = os.environ["PGDATABASE"]
    if database != "odoo17_dev":
        raise ValueError("Backup database must be odoo17_dev")
    state = {"scales": {path: api(path)["spec"]["replicas"] for path in SCALES},
             "scalers": {path: {key: api(path).get("metadata", {}).get("annotations", {}).get(key)
                               for key in PAUSE_KEYS} for path in SCALERS}}
    # Atomic lock also prevents two manually-created Jobs from stopping the same writers.
    api(LOCKS, "POST", {"apiVersion": "v1", "kind": "ConfigMap",
        "metadata": {"name": "odoo-backup-lock", "namespace": NS},
        "data": {"resume.json": json.dumps(state)}})
    signal.signal(signal.SIGTERM, stop_signal)
    signal.signal(signal.SIGINT, stop_signal)
    try:
        for path in SCALERS:
            api(path, "PATCH", {"metadata": {"annotations": {
                "autoscaling.keda.sh/paused": None, "autoscaling.keda.sh/paused-replicas": "0"}}})
        deadline = time.monotonic() + 120
        while not all(any(c["type"] == "Paused" and c["status"] == "True"
                         for c in api(path).get("status", {}).get("conditions", [])) for path in SCALERS):
            if time.monotonic() > deadline:
                raise TimeoutError("KEDA did not pause")
            time.sleep(2)
        for path in SCALES:
            api(path, "PATCH", {"spec": {"replicas": 0}})
        query = urllib.parse.urlencode({"labelSelector": "app=odoo,component in (web,worker,cron,queue-runner)"})
        deadline = time.monotonic() + 900
        while api(f"/api/v1/namespaces/{NS}/pods?{query}")["items"]:
            if time.monotonic() > deadline:
                raise TimeoutError("Odoo writer pods did not terminate")
            time.sleep(2)
        print("All Odoo writers stopped; creating consistent backup.", flush=True)
        root = Path("/backup")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        staging = root / (stamp + ".partial")
        staging.mkdir(parents=True, exist_ok=False)
        dump = staging / "database.dump"
        subprocess.run(["pg_dump", "-Fc", "--no-owner", "--no-acl", "-f", str(dump)], check=True)
        source = Path("/var/lib/odoo/filestore") / database
        archive = staging / "filestore.tar.gz"
        with tarfile.open(archive, "w:gz") as output:
            if source.is_dir():
                output.add(source, arcname=database)
        metadata = staging / "metadata.json"
        metadata.write_text(json.dumps({"database": database, "created_utc": stamp,
                                        "consistent": True, "filestore_present": source.is_dir()}))
        (staging / "SHA256SUMS").write_text("".join(
            f"{checksum(path)}  {path.name}\n" for path in (dump, archive, metadata)))
        staging.rename(root / stamp)
        print(f"Backup complete: {stamp}", flush=True)
        # Delete only completed sets created by this script, after a successful new backup.
        for candidate in root.iterdir():
            if (candidate.is_dir() and candidate.name != stamp
                    and len(candidate.name) == 16 and candidate.name.endswith("Z")
                    and (candidate / "SHA256SUMS").is_file()
                    and time.time() - candidate.stat().st_mtime > 7 * 86400):
                shutil.rmtree(candidate)
    finally:
        # Ignore a second termination signal while restoring cluster state.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        resume(state)
        api(LOCKS + "/odoo-backup-lock", "DELETE")
        print("Odoo replica counts and autoscaling restored.", flush=True)

if __name__ == "__main__":
    main()
