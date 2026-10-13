"""Initialize a fresh database or install missing modules; do not upgrade ERP data."""
import os
import subprocess
import time
import psycopg2

options = dict(host=os.environ["HOST"], port=os.environ.get("PORT", "5432"),
               user=os.environ["USER"], password=os.environ["PASSWORD"])
deadline = time.monotonic() + 120
while True:
    try:
        connection = psycopg2.connect(dbname="postgres", **options)
        break
    except psycopg2.OperationalError:
        if time.monotonic() >= deadline:
            raise
        time.sleep(2)
with connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_database WHERE datname=%s", ("odoo17_dev",))
        exists = bool(cursor.fetchone())
connection.close()
fresh = not exists
missing = ["base", "web", "queue_job"]
if exists:
    with psycopg2.connect(dbname="odoo17_dev", **options) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.ir_module_module')")
            if cursor.fetchone()[0]:
                cursor.execute("SELECT name FROM ir_module_module WHERE state='installed'")
                installed = {row[0] for row in cursor.fetchall()}
                missing = [module for module in missing if module not in installed]
            else:
                fresh = True
if missing:
    subprocess.run(["/entrypoint.sh", "odoo", "-c", "/etc/odoo/odoo.conf",
                    "-d", "odoo17_dev", "-i", ",".join(missing),
                    "--without-demo=all", "--stop-after-init", "--no-http",
                    "--workers=0", "--max-cron-threads=0",
                    "--load=base,web,queue_job"], check=True)
else:
    print("Database already initialized; required modules installed.")

if fresh:
    # Set the login password through the ORM only for a newly initialized database.
    subprocess.run(["/entrypoint.sh", "odoo", "shell", "-c", "/etc/odoo/odoo.conf",
                    "-d", "odoo17_dev", "--no-http", "--workers=0", "--max-cron-threads=0"],
                   input='import os\nenv.ref("base.user_admin").write({"password": os.environ["ADMIN_LOGIN_PASSWORD"]})\nenv.cr.commit()\n',
                   text=True, check=True)
