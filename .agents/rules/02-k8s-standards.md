# QUY CHUẨN KỸ THUẬT KUBERNETES CHO ODOO
> **Mã quy tắc**: `RULE-K8S-02`  
> **Áp dụng cho**: Mọi manifest trong repo sibling `odoo-cmc-gitops` và cấu hình container trong repo này.

---

## 1. PHÂN QUYỀN & BẢO MẬT POD (SECURITY CONTEXT)
- **Non-Root & UID 101**: Container Odoo chính thức chạy với `uid=101(odoo)` và `gid=101(odoo)`.
- **Bắt buộc cấu hình Pod Security Context**:
  ```yaml
  securityContext:
    fsGroup: 101
    runAsUser: 101
    runAsGroup: 101
  ```
  Cấu hình này cấp quyền nhóm cho volume có hỗ trợ fsGroup. Phải xác minh quyền ghi của provisioner thực tế, đặc biệt trên NFS.

---

## 2. TÍNH TOÁN BỘ NHỚ & CHỐNG OOMKILLED (MEMORY SIZING)
- **Nguyên lý Odoo Worker Memory**:
  - `limit_memory_soft` và `limit_memory_hard` trong `odoo.conf` là giới hạn tính **trên từng tiến trình worker con**, không phải trên toàn bộ container!
  - Một Pod Web Odoo gồm: 1 Master Process + 2 HTTP Workers + 1 Gevent/Websocket Worker = **4 processes**.
- **Công thức an toàn**:
  ```
  Container Memory Limit >= (Số Worker x limit_memory_hard) + 512MB (Master + Gevent overhead)
  ```
- **Giá trị chuẩn hóa**:
  - `odoo.conf`: `limit_memory_soft = 805306368` (768MB), `limit_memory_hard = 1073741824` (1GB).
  - Web Pod (2 workers): Request `1Gi`, Limit `2.5Gi`.
  - Queue Worker Pod (2 HTTP workers): Request `1Gi`, Limit `2.5Gi`.
  - Cron Pod (2 cron processes): Request `512Mi`, Limit `2.5Gi`.
  - Queue dispatcher (1 runner process): Request `512Mi`, Limit `1.5Gi`.
  - **Quy tắc**: Tuyệt đối không để Container Limit thấp hơn `limit_memory_hard` của Odoo, vì Kernel sẽ gửi tín hiệu `SIGKILL` (Exit 137) trước khi Odoo kịp tái chế worker!

---

## 3. QUẢN LÝ KẾT NỐI DATABASE (CONNECTION POOLING)
- Pool tính theo từng process HTTP, gevent, cron và runner; tính cả canary surge. Master đóng pool kế thừa trước khi fork.
- PostgreSQL: `max_connections=300`, `shared_buffers=256MB`.
- `db_maxconn=4` và `db_maxconn_gevent=4`.
- Web tối đa 10 pods + 20% surge = 12 pods × (2 HTTP + 1 gevent).
- Queue tối đa 8 pods × (2 HTTP + 1 gevent), cron 2 processes, dispatcher 1 process.
- Ngân sách: (12×3 + 8×3 + 2 + 1)×4 + 32 reserve = **284/300**.
- Tăng replicas/workers/surge phải tính lại; 16/process từ plan ban đầu vượt ngân sách khi cả web và queue scale.

---

## 4. HEALTH CHECK PROBES & LIFECYCLE
- **Endpoint**: `/web/health` (type: http, auth: none, save_session: False).
- **Probes**:
  - `startupProbe`: Cho phép thời gian nạp module ban đầu (initialDelaySeconds: 15, failureThreshold: 30, periodSeconds: 5).
  - `readinessProbe`: Đảm bảo Pod chỉ nhận traffic khi đã sẵn sàng.
  - `livenessProbe`: Tự động khởi động lại Pod khi bị treo.

---

## 5. GATEWAY, API SHIELD & ARGO ROLLOUTS
- **Gateway**: Sử dụng Apache APISIX Ingress Controller (thay thế Ingress-NGINX đã retire từ 03/2026).
- **Traffic Routing**: Tích hợp với Argo Rollouts thông qua `trafficRouting.apisix` hoặc dịch vụ phân tách `stableService` & `canaryService`.
- **Cấu hình Gateway bắt buộc**:
  - Upload limit: `client_max_body_size: 100m`.
  - Timeout Web/Websocket: ApisixRoute `timeout.read/send: 600s`.
  - Websocket: Định tuyến `/websocket` sang cổng 8072.
- **API Shield (Bảo vệ cổng RPC `/jsonrpc`, `/xmlrpc/2`, `/web/dataset/call_kw`)**:
  - **Consumer & Key Auth**: Định nghĩa `ApisixConsumer` (`partner-standard`, `partner-vip`) tham chiếu tới Kubernetes Secret qua `secretRef` (`odoo-partner-standard-key`, `odoo-partner-vip-key`), bật `authentication.type: keyAuth` và `consumer-restriction`.
  - **Rate Limiting (`limit-count`)**: Đối tác thường giới hạn `50 req/60s`, đối tác VIP (`X-Partner-Tier: vip`) giới hạn `500 req/60s`; vượt ngưỡng trả về `HTTP 429 Too Many Requests` ngay tại Gateway.
  - **Connection Limiting & Circuit Breaker**: Áp dụng `limit-conn`, `api-breaker` (ngắt mạch với `503` khi backend lỗi liên tiếp) và giới hạn `timeout.read/send: 60s` trên các route RPC để tránh query nặng làm cạn kiệt worker hoặc gây OOM.

RWX provisioner phải hỗ trợ ownership/fsGroup hoặc cấp quyền UID/GID 101 trước. fsGroup không tự khắc phục mọi cấu hình NFS root_squash. Overlay local RWO chỉ dùng trên Docker Desktop một node.
