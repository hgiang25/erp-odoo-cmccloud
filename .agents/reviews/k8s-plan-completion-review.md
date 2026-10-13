# Rà soát và triển khai plan Kubernetes — 2026-10-13

## Kết luận triển khai

Plan được đối chiếu với toàn bộ manifest và mã nguồn Odoo. A1–A9 đều có xử lý trong source; cluster Docker Desktop chưa có context nên kiểm thử trên Kubernetes còn chờ. Không chạy apply vào EKS/cluster khác.

| Mục | Thay đổi |
|---|---|
| A1 | deploy.ps1 cố định context docker-desktop trên mọi lệnh mutate; dừng nếu thiếu context; không đổi current-context. |
| A2 | ApisixRoute + Helm APISIX; websocket/HTTP, timeout 600s, upload 100 MiB; loại NGINX cũ khỏi build. |
| A3 | Rollout là chủ sở hữu duy nhất web pods; stable/canary Services, trafficRouting.apisix cho hai rules; KEDA trỏ Rollout. |
| A4 | Odoo soft/hard 768 MiB/1 GiB; web 2.5 GiB, queue worker 2.5 GiB, runner 1.5 GiB, cron 2.5 GiB. |
| A5 | Giữ entrypoint chính thức; DB args qua Secret; initContainer render admin Secret vào emptyDir pod riêng. |
| A6 | Backup đúng odoo17_dev; PVC riêng; quiesce writers; SHA256; restore drill vào DB/PVC riêng và verify attachment. |
| A7 | Init Job trước app/KEDA; list_db=False, dbfilter cố định; password login admin DB mới sinh ngẫu nhiên. |
| A8 | UID/GID/fsGroup 101; PVC cloud RWX, local RWO single-node; non-root các container Odoo. |
| A9 | Pool 4/process cả gevent; max_connections=300; 252 pool slots + 32 reserve = 284 ở max replica/surge. |
| Queue | Image OCA commit ghim, cài module thực sự; dispatcher singleton + worker Service nội bộ; cron tách riêng. |
| HTTP scaling | Overlay Prometheus APISIX + scrape mẫu; kích hoạt sau khi có monitoring/query hợp lệ. |

## Điều chỉnh plan để phù hợp runtime

- OCA runner gọi HTTP /queue_job/runjob, không trực tiếp thực thi job. Giữ --no-http cho cron và dispatcher; queue worker mở HTTP nội bộ. Runner root:8 chung; web/cron/queue worker root:0.
- db_maxconn=16 không an toàn khi scale web + queue + canary/gevent cùng lúc. Chọn 4 và tính cả canary surge, reserve cho bootstrap/monitoring.
- Hai cron processes cần 2.5 GiB theo công thức memory, không thể giữ limit 1.5 GiB.
- Query scaler bao gồm started để job đang chạy được tính khi scale down; Odoo xử lý SIGTERM với grace 660s, timeout job 600s. Thiết kế vẫn cần job idempotent/retry khi pod bị kill cứng.
- Snapshot nhất quán cần dừng writers. CronJob gây khoảng bảo trì hàng ngày lúc 02:00 Việt Nam. Không mô tả backup live là nhất quán.
- Backup PVC riêng trong cùng cluster chưa phải DR off-site; cần sao chép backup ra failure domain khác ở môi trường cloud.
- Bộ Helm ghim phiên bản tương thích để tái lập lab; kiểm tra bản vá, TLS, storage và upgrade compatibility trước khi dùng cloud.

## Bằng chứng

- Local: odoo/service/server.py (prefork HTTP/cron spawning, đóng pool trước fork); odoo/tools/config.py (db_maxconn/gevent); addons/web/controllers/home.py (/web/health); odoo/http.py (FilesystemSessionStore); ir_cron.py (SKIP LOCKED); bus.py (pg_notify).
- Image odoo:17.0: id odoo trả UID/GID 101; /entrypoint.sh dùng wait-for-psql.py và DB env nếu config không có credentials.
- [OCA runner 17.0](https://github.com/OCA/queue/blob/983b6adc1aa780c3d69247cd2d5cadc91bcffe82/queue_job/jobrunner/runner.py), [runner hooks](https://github.com/OCA/queue/blob/983b6adc1aa780c3d69247cd2d5cadc91bcffe82/queue_job/jobrunner/__init__.py).
- [Argo/APISIX](https://argoproj.github.io/argo-rollouts/features/traffic-management/apisix/), [KEDA PostgreSQL](https://keda.sh/docs/2.18/scalers/postgresql/), [APISIX metrics](https://apisix.apache.org/docs/apisix/3.11/plugins/prometheus/).
- helm show chart/values/crds kiểm chứng tên trường của chart APISIX 2.10.0/controller 0.14.0 và versions Argo 2.43.6/KEDA 2.18.0/metrics-server 3.12.2.

## Xác minh

- Kustomize base/local/http-scaling: mỗi bộ 24 resources, liên kết/selector/storage/probe/memory và budget 284/300 hợp lệ.
- Kubeconform strict: 19 core resources hợp lệ, 5 CRD được kiểm riêng bằng jsonschema từ Helm CRDs chính thức.
- Argo Rollout, ApisixRoute, ScaledObject, TriggerAuthentication: schema chính thức hợp lệ cho cả ba bộ.
- Job init và Job restore: kubeconform strict hợp lệ.
- Helm APISIX values render 13 resources; Python syntax, PowerShell Parser, deploy -ValidateOnly và docker compose config hợp lệ.
- Docker build thành công image Odoo+OCA và backup Python/PostgreSQL.
- Smoke test Docker cô lập: DB init và chạy lại không đổi password; admin authentication; dispatcher no-http gửi job tới HTTP worker; queue job cập nhật partner thành công.
- Restore script chạy trên PostgreSQL thật: DB mới khôi phục, kiểm chứng **20 file attachments**; từ chối restore đè DB và backup bị sửa checksum. Container/network/volumes của test đã được dọn.
- Bằng chứng runtime bổ sung: Odoo ir_actions_report yêu cầu ít nhất 2 workers cho PDF; queue dùng 2 HTTP workers, cron --workers=2 dù no-http; memory và maxQueue=8 được tính lại.
- Helpers PowerShell đã kiểm tra truyền đủ arguments bằng kubectl giả lập; deploy thực tế từ chối thiếu docker-desktop trước thay đổi cluster và giữ nguyên current-context.

Pending: runtime cluster, canary traffic weights thực tế, KEDA HPA và restore drill Kubernetes; thiếu docker-desktop context.

## Điều chỉnh CD cho CMC Cloud

Repo tham chiếu `hcm3-k8s-lab` build image bằng GitHub Actions rồi dùng runner
self-hosted chạy `kubectl apply`/`kubectl set image`. Project Odoo giữ cách tag image
theo commit và runner bastion, nhưng thay deploy trực tiếp bằng GitOps: workflow
commit image tag vào overlay, Argo CD app-of-apps tự đồng bộ APISIX, Argo Rollouts,
KEDA, etcd và Odoo. Runner có quyền cluster chỉ dùng cho bootstrap Argo CD thủ công.

## Chuyển môi trường sau kiểm tra local

Cluster local đã được dọn theo yêu cầu người dùng. Phần CMC được refactor riêng,
kết quả và giới hạn hiện tại xem [CMC readiness review](cmc-cloud-readiness.md).
Các kiểm chứng Docker/local phía trên không được xem là nghiệm thu runtime CMC.
