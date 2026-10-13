"""Restore into a new drill database and separate filestore; verify attachments."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile

BACKUP_FILES = ("database.dump", "filestore.tar.gz", "metadata.json", "SHA256SUMS")

def run(*args):
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()

def sql(database, query):
    return run("psql", "-X", "-v", "ON_ERROR_STOP=1", "-At", "-d", database, "-c", query)

def download_from_s3(folder, name):
    bucket = os.environ.get("S3_BUCKET", "").strip()
    if not bucket:
        raise FileNotFoundError(f"Backup set {name} is not on the mounted volume and S3_BUCKET is unset")
    import boto3
    from botocore.config import Config
    client = boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT_URL", "").strip() or None,
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    prefix = os.environ.get("S3_PREFIX", "odoo/backups").strip("/")
    key_prefix = "/".join(part for part in (prefix, name) if part)
    client.head_object(Bucket=bucket, Key=f"{key_prefix}/_SUCCESS")
    staging = folder.with_name(folder.name + ".partial")
    staging.mkdir(parents=True, exist_ok=False)
    try:
        for filename in BACKUP_FILES:
            client.download_file(bucket, f"{key_prefix}/{filename}", str(staging / filename))
        staging.rename(folder)
    except Exception:
        import shutil
        shutil.rmtree(staging, ignore_errors=True)
        raise

def main():
    name = os.environ["BACKUP_SET"]
    if not re.fullmatch(r"\d{8}T\d{6}Z", name):
        raise ValueError("BACKUP_SET must be a completed UTC timestamp directory")
    target = os.environ.get("RESTORE_DATABASE", "odoo17_restore_drill")
    if not re.fullmatch(r"odoo17_restore_drill(?:_[a-z0-9_]+)?", target):
        raise ValueError("Only new odoo17_restore_drill databases are allowed")
    folder = Path("/backup") / name
    if not folder.is_dir():
        download_from_s3(folder, name)
    allowed = {"database.dump", "filestore.tar.gz", "metadata.json"}
    found = set()
    for line in (folder / "SHA256SUMS").read_text().splitlines():
        digest, filename = line.split("  ", 1)
        if filename not in allowed or filename in found:
            raise ValueError("Unexpected checksum entry")
        found.add(filename)
        hasher = hashlib.sha256()
        with (folder / filename).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
        if hasher.hexdigest() != digest:
            raise ValueError(f"Checksum mismatch: {filename}")
    if found != allowed:
        raise ValueError("Incomplete backup set")
    metadata = json.loads((folder / "metadata.json").read_text())
    if metadata.get("database") != "odoo17_dev" or metadata.get("consistent") is not True:
        raise ValueError("Backup does not contain a consistent odoo17_dev snapshot")
    if sql("postgres", f"SELECT 1 FROM pg_database WHERE datname='{target}'"):
        raise ValueError("Drill database already exists; choose a new suffix")
    destination = Path("/restore/filestore") / target
    if destination.exists():
        raise ValueError("Drill filestore already exists; choose a new suffix")
    run("createdb", target)
    run("pg_restore", "--exit-on-error", "--no-owner", "--no-acl", "-d", target,
        str(folder / "database.dump"))
    staging = Path("/restore") / ("extract_" + target)
    staging.mkdir(exist_ok=False)
    with tarfile.open(folder / "filestore.tar.gz") as archive:
        archive.extractall(staging, filter="data")
    destination.parent.mkdir(exist_ok=True)
    source = staging / "odoo17_dev"
    if source.exists():
        source.rename(destination)
    else:
        destination.mkdir()
    staging.rmdir()
    if sql(target, "SELECT count(*) FROM ir_module_module WHERE name='queue_job' AND state='installed'") != "1":
        raise ValueError("queue_job missing from restored database")
    records = sql(target, "SELECT store_fname || '|' || COALESCE(checksum, '') FROM ir_attachment WHERE store_fname IS NOT NULL")
    for record in records.splitlines():
        filename, expected = record.split("|", 1)
        path = (destination / filename).resolve()
        if not path.is_relative_to(destination.resolve()) or not path.is_file():
            raise ValueError(f"Missing/unsafe attachment: {filename}")
        if expected:
            digest = hashlib.sha1()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != expected:
                raise ValueError(f"Attachment checksum mismatch: {filename}")
    print(f"Restore drill passed: {target}; {len(records.splitlines())} file attachments verified.")

if __name__ == "__main__":
    main()
