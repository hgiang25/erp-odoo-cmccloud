# Login UI demo — 2026-10-22

- Added a navy/gold banner above the login card in `addons/web/views/webclient_templates.xml`, template `web.login_layout`.
- Visible text: `CMC CLOUD LAB`, `Giao diện Odoo đã được cập nhật`, and a dated demo marker.
- Login form, authentication and database settings are unchanged.
- Verification: XML parsing and Git whitespace checks; browser/runtime verification is pending.
- Delivery: build/deploy the updated source image and upgrade the `web` module in the target database through the maintenance workflow to reload the stored QWeb view. Restarting Pods alone may leave the old database view intact. Inspect `/web/login` while logged out.
