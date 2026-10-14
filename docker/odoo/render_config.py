"""Render the admin Secret into a pod-private config; never print credentials."""
import configparser
import os
from pathlib import Path
import re

config = configparser.ConfigParser(interpolation=None)
config.read("/config/odoo.conf")
config["options"]["admin_passwd"] = os.environ["ODOO_ADMIN_PASSWORD"]
config["options"]["db_sslmode"] = os.environ.get("ODOO_DB_SSLMODE", "prefer")
database = os.environ.get("ODOO_DB_NAME", "odoo17_dev")
if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", database):
    raise ValueError("ODOO_DB_NAME must be a safe PostgreSQL identifier")
config["options"]["db_name"] = database
config["options"]["dbfilter"] = "^" + re.escape(database) + "$"
target = Path("/etc/odoo/odoo.conf")
with target.open("w", encoding="utf-8") as stream:
    config.write(stream)
target.chmod(0o600)
