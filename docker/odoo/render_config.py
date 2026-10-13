"""Render the admin Secret into a pod-private config; never print credentials."""
import configparser
import os
from pathlib import Path

config = configparser.ConfigParser(interpolation=None)
config.read("/config/odoo.conf")
config["options"]["admin_passwd"] = os.environ["ODOO_ADMIN_PASSWORD"]
config["options"]["db_sslmode"] = os.environ.get("ODOO_DB_SSLMODE", "prefer")
target = Path("/etc/odoo/odoo.conf")
with target.open("w", encoding="utf-8") as stream:
    config.write(stream)
target.chmod(0o600)
