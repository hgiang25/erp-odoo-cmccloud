# KẾ HOẠCH TRIỂN KHAI HOÀN CHỈNH: ODOO DECOMPOSED MONOLITH TRÊN KUBERNETES
> **Dự án**: Final Lab - Đưa Odoo ERP lên Kubernetes (CMC Cloud Standard)  
> **Thư mục quản lý**: `.agents/plans/`  
> **Trạng thái**: Đã triển khai source; đã kiểm tra offline/container; kiểm chứng Kubernetes chờ context docker-desktop

---

## 1. TỔNG QUAN KIẾN TRÚC MỤC TIÊU (DECOMPOSED MONOLITH)

```
                            [ INTERNET / CLIENTS ]
                                       │
                                       ▼
                       [ Apache APISIX Gateway ]
                         - Modern API Gateway & Ingress
                         - Websocket Forwarding (/websocket -> 8072)
                         - Buffer 100MB cho import/file upload
                         - Argo Rollouts Canary Traffic Routing
                                       │
                      ┌────────────────┴────────────────┐
                      ▼ (HTTP Traffic)                  │
           [ Odoo Web Tier (Stateless) ]                │ (Internal Traffic Only)
           - Replicas: 2 -> 10 Pods                     ▼
           - Args: --max-cron-threads=0        [ Odoo Worker Tier (Async Queue) ]
           - KEDA ScaledObject (HTTP/CPU)      - OCA queue_job Job Runner
           - Liveness/Readiness: /web/health   - KEDA ScaledObject (Queue Depth)
                      │                        - Cron Runner (SKIP LOCKED Safe)
                      │                                 │
                      ├────────────────┬────────────────┤
                      ▼                ▼                ▼
            [ Shared Storage (PVC) ]   │     [ PostgreSQL 15 (DBaaS) ]
            - /var/lib/odoo/filestore  │     - max_connections: 300
            - /var/lib/odoo/sessions   │     - pg_notify (Bus Realtime)
            - fsGroup: 101             │     - Bảng queue_job & ir_cron
```

---

## 2. NỘI DUNG CÁC BƯỚC THỰC HIỆN CHI TIẾT

### Giai đoạn 1: Sửa các lỗi vận hành & Chuẩn hóa Hạ tầng Cơ sở (A4 - A9)

1. **Khắc phục quyền ghi Storage (Permission Denied A8)**:
   - Bổ sung `securityContext: { fsGroup: 101, runAsUser: 101 }` vào cả Web và Worker Pods để user `odoo` (UID 101) có toàn quyền ghi vào thư mục `/var/lib/odoo/filestore` và `/var/lib/odoo/sessions`.
2. **Cân đối Bộ nhớ & Tránh OOMKilled (A4)**:
   - Điều chỉnh cấu hình trong `odoo.conf`:
     - `limit_memory_soft = 805306368` (~768MB / worker)
     - `limit_memory_hard = 1073741824` (~1GB / worker)
   - Điều chỉnh Container Limits:
     - Web Pod (2 workers + 1 gevent + 1 master): Request `1Gi`, Limit `2.5Gi`.
     - Worker Pod: Request `512Mi`, Limit `1.5Gi`.
     - Ngăn ngừa tình trạng Linux Kernel OOMKill pod trước khi Odoo kịp tái chế tiến trình.
3. **Cấu hình Kết nối PostgreSQL & db_maxconn (A9)**:
   - Sửa `03-postgres.yaml`: Bổ sung tham số khởi động `-c max_connections=300` và `shared_buffers=256MB`.
   - Trong `odoo.conf`: Điều chỉnh `db_maxconn = 16` để tránh cạn kiệt connection pool khi KEDA scale lên 10 Web Pods.
4. **Bảo toàn Docker Entrypoint & Bí mật DB (A5)**:
   - Không ghi đè mù quáng `command: ["odoo", ...]`. Chuyển sang cấu hình chuẩn qua `args:` hoặc entrypoint script để giữ nguyên cơ chế `wait-for-psql.py` và nạp biến môi trường an toàn từ Kubernetes Secret.

---

### Giai đoạn 2: Tái cấu trúc Theo Các Quyết định Kỹ thuật (A1, A2, A3)

1. **Gỡ bỏ Redis, chuẩn hóa Native Session & Bus (Quyết định A3)**:
   - Xóa bỏ `04-redis.yaml` khỏi `kustomization.yaml`.
   - Khẳng định trong kiến trúc: Odoo lưu session an toàn trên Shared Storage (`FilesystemSessionStore`) và Bus đồng bộ thời gian thực qua PostgreSQL `pg_notify`.
2. **Tích hợp Apache APISIX Gateway (Quyết định A1)**:
   - Thay thế `08-ingress.yaml` (ingress-nginx cũ) bằng manifest APISIX Ingress / ApisixRoute:
     - Định tuyến `/websocket` sang cổng 8072.
     - Định tuyến `/` sang cổng 8069.
     - Cấu hình Timeout 600s và Max Body Size 100MB.
   - Cung cấp lệnh cài đặt APISIX Gateway bằng Helm vào `deploy.ps1`.
3. **Triển khai Hàng đợi Bất đồng bộ OCA `queue_job` (Quyết định A2)**:
   - Cấu hình server environment cho Worker Pod hỗ trợ chạy jobrunner:
     - Tham số nạp module `--load=base,web,queue_job`
     - Kênh xử lý jobrunner cấu hình qua biến môi trường.
4. **Cấu hình KEDA Autoscaling Event-Driven (A2 & KEDA)**:
   - Cập nhật `09-keda-autoscaling.yaml`:
     - **Web Scaler**: Scale từ 2 đến 10 Pods theo CPU/Memory và HTTP request rate.
     - **Worker Scaler**: Scale theo độ dài hàng đợi thực tế trong PostgreSQL thông qua trigger query:
       ```sql
       SELECT count(*) FROM queue_job WHERE state IN ('pending', 'enqueued')
       ```
5. **Chuẩn hóa Argo Rollouts Canary (A3/Rollouts)**:
   - Sửa `10-argo-rollout.yaml`:
     - Định nghĩa rõ ràng `stableService` (`odoo-web-stable`) và `canaryService` (`odoo-web-canary`).
     - Tích hợp traffic routing với APISIX để phân tách 20% -> 50% -> 100% không gián đoạn.
6. **Hoàn thiện Kế hoạch Disaster Recovery & Restore (A6)**:
   - Sửa `11-backup-cronjob.yaml`: Nhắm đúng database nghiệp vụ (`odoo17_dev`), sinh checksum SHA256 và lưu vào PVC backup tách biệt.
   - Bổ sung tài liệu / script kiểm thử diễn tập khôi phục (DR Restore Drill).

---

## 3. KẾ HOẠCH BÀN GIAO & DANH SÁCH FILE THỰC HIỆN

| STT | File | Hành động | Mục đích |
|---|---|---|---|
| 1 | `k8s/01-secrets-and-configmap.yaml` | Cập nhật | Tối ưu memory limits, connection pool, proxy_mode |
| 2 | `k8s/02-storage.yaml` | Cập nhật | Chuẩn hóa PVC filestore & backup volume |
| 3 | `k8s/03-postgres.yaml` | Cập nhật | Tăng `max_connections=300`, tối ưu tài nguyên |
| 4 | `k8s/04-redis.yaml` | Xóa/Loại bỏ | Loại bỏ Redis khỏi kustomization theo quyết định A3 |
| 5 | `k8s/05-odoo-web.yaml` | Cập nhật | Bổ sung `securityContext fsGroup`, memory sizing, probes |
| 6 | `k8s/06-odoo-worker.yaml` | Cập nhật | Cấu hình queue_job runner, fsGroup, memory sizing |
| 7 | `k8s/07-service.yaml` | Cập nhật | Tạo stable/canary services phục vụ Argo Rollouts |
| 8 | `k8s/08-apisix-gateway.yaml` | Tạo mới/Thay thế | Apache APISIX Gateway thay thế Ingress-NGINX |
| 9 | `k8s/09-keda-autoscaling.yaml` | Cập nhật | Bổ sung PostgreSQL Scaler đo độ dài queue_job |
| 10 | `k8s/10-argo-rollout.yaml` | Cập nhật | Hoàn chỉnh spec canary với APISIX traffic routing |
| 11 | `k8s/11-backup-cronjob.yaml` | Cập nhật | Nhắm đúng DB Odoo, bổ sung restore script |
| 12 | `k8s/kustomization.yaml` | Cập nhật | Đồng bộ danh sách tài nguyên mới |
| 13 | `k8s/deploy.ps1` | Cập nhật | Script triển khai 1-click mượt mà cho Docker Desktop |
| 14 | `k8s/README.md` | Viết lại hoàn chỉnh | Cẩm nang kiến trúc & Luận điểm bảo vệ đồ án CMC Cloud |
| 15 | `AGENTS.md` | Tạo mới | Quy chuẩn làm việc, context và prompt mẫu cho AI/Codex |

## 4. Trạng thái thực hiện cập nhật ngày 2026-10-13

Phần 1–3 lưu yêu cầu gốc. Các điều chỉnh dưới đây thay thế thông số gốc khi có khác biệt; manifest thực thi nằm trong `k8s/base/`.

- [x] Sửa A4/A5/A8/A9: permissions, memory, entrypoint, DB pool.
- [x] Loại Redis và Ingress NGINX khỏi bộ triển khai.
- [x] APISIX HTTP/WebSocket, 100 MiB upload và 600s timeout; Helm cài controller.
- [x] Image OCA queue ở commit ghim, Job bootstrap DB và cài module.
- [x] Queue dispatcher không HTTP; worker HTTP nội bộ riêng; cron không HTTP.
- [x] KEDA web 2–10 theo CPU/RAM; queue worker 1–8 theo pending/enqueued/started.
- [x] Overlay HTTP request scaling với APISIX Prometheus và cấu hình scrape mẫu.
- [x] Rollout là owner duy nhất web; stable/canary và APISIX 20% → 50% → 100%.
- [x] Backup đúng DB, PVC riêng, quiesce writers, SHA256 và script recovery trạng thái.
- [x] Restore drill vào DB/PVC riêng, verify checksum attachments, từ chối overwrite/corruption.
- [x] README, kiểm tra offline và review cập nhật.
- [ ] Apply và smoke test Kubernetes Docker Desktop: context hiện chưa tồn tại.
- [ ] Xác minh traffic weights APISIX/Argo và HPA KEDA trên cluster thật.
- [ ] Chạy backup CronJob có pause/resume qua Kubernetes API và restore drill trên cluster.
- [ ] Chuẩn bị RWX StorageClass + off-site backup và cấu hình monitoring khi lên CMC Cloud.

Điều chỉnh runtime: queue jobrunner gửi HTTP tới worker; vì vậy worker xử lý job cần HTTP nội bộ. Queue worker dùng 2 HTTP processes và 2.5 GiB để Odoo cho phép in PDF; cron dùng 2 cron processes và 2.5 GiB. Dispatcher 1.5 GiB, kênh root:8. Pool 4 cho cả HTTP/gevent; tại max replicas và canary surge: (12×3 + 8×3 + 2 + 1)×4 = 252; cộng 32 reserve = **284/300**.

Backup nhất quán có khoảng ngừng dịch vụ mỗi ngày lúc 02:00 giờ Việt Nam. Backup PVC riêng không tự đáp ứng DR off-site. Hạ tầng và mọi lệnh mutate mặc định cố định docker-desktop, không đổi current-context.

Bằng chứng và kết quả kiểm tra: [review hoàn thành](../reviews/k8s-plan-completion-review.md).

## 5. Chuyển sang CMC Cloud (2026-10-13)

- [x] CLI cloud chỉ render/preflight; loại đường deploy workload trực tiếp để Argo CD là reconciler duy nhất.
- [x] Image Docker Hub cho mọi tier và init/backup/restore; hỗ trợ imagePullSecrets.
- [x] StorageClass block/RWX rõ ràng, gateway ELB HTTPS + TLS và NetworkPolicy.
- [x] Kiểm tra schema/Helm, tests offline, hướng dẫn và review CMC.
- [x] GitOps app-of-apps: Argo CD quản lý APISIX, Argo Rollouts, KEDA, etcd và overlay Odoo.
- [x] CI build/push image tag `sha-*`, commit promotion vào Kustomize; bootstrap Argo CD chạy thủ công trên self-hosted runner bastion.
- [ ] Người dùng dựng NFS/RWX, cung cấp kubeconfig, domain/TLS, Docker Hub username.
- [ ] Xác nhận lifecycle/bản vá Kubernetes CMC; 1.32 không còn được upstream hỗ trợ.
- [ ] Build/push release image; live preflight và smoke test cloud.
- [ ] Nghiệm thu canary/KEDA, RWX nhiều node và backup/restore trên CMC.
- [ ] HA database/etcd/NFS, off-site backup, monitoring trước production.

Local Kubernetes đã được người dùng yêu cầu dọn sạch trước lượt refactor.
Self-hosted runner chỉ bootstrap Argo CD; phát hành hằng ngày không `kubectl apply`
workload mà cập nhật Git để Argo CD reconcile. Hướng dẫn cloud tại `k8s/cmc/README.md`; bằng chứng tại
[CMC readiness review](../reviews/cmc-cloud-readiness.md).
