# BÁO CÁO REVIEW BỘ MANIFEST K8S & ĐỐI CHIẾU MÃ NGUỒN ODOO
> **Thư mục quản lý**: `.agents/reviews/`  
> **Mục đích**: Bằng chứng kỹ thuật, các lỗi vận hành phát hiện và đối chiếu mã nguồn Odoo thực tế.

> Báo cáo này là snapshot trước triển khai. Trạng thái hiện tại: [review thực hiện plan](k8s-plan-completion-review.md).

---

## 🔴 A. 9 LỖI VẬN HÀNH THỰC TẾ (BLOCKING ISSUES)

| # | File | Vấn đề | Bằng chứng |
|---|------|--------|-----------|
| A1 | môi trường | Kubernetes chưa được bật trong Docker Desktop: không có context `docker-desktop`. Context hiện tại đang trỏ vào **AWS EKS `dev-cluster`** (trong kubeconfig còn có cả `prod-cluster`). Lỡ chạy `kubectl apply` là áp lên cluster thật. | `kubectl config get-contexts` |
| A2 | `08-ingress.yaml` | Docker Desktop không cài sẵn Ingress Controller nên resource Ingress sẽ không có tác dụng. Thêm nữa, **ingress-nginx đã bị retire từ 3/2026** (không còn bản vá bảo mật). Annotation `kubernetes.io/ingress.class` cũng đã deprecated. | Thông báo của SIG Network |
| A3 | `10-argo-rollout.yaml` | Thiếu `canaryService`/`stableService`, là trường bắt buộc khi có `trafficRouting` (controller sẽ báo `InvalidSpec`). Rollout này còn tạo một bộ Pod **thứ hai** (label `web-rollout`) chạy song song với Deployment `odoo-web`, trong khi Service không trỏ tới bộ Pod này. | Đặc tả của Argo Rollouts |
| A4 | `05`/`06` | Memory: `limit_memory_hard = 2.5GiB` **cho mỗi worker** nhưng container chỉ có limit `2Gi` cho 2 worker + gevent + master. Kernel sẽ OOMKill (exit 137) trước khi Odoo kịp tự recycle worker. | `odoo.conf` so với `resources.limits` |
| A5 | `05`/`06` | Dùng `command:` thì **ghi đè `/entrypoint.sh`**. Hệ quả: env `HOST/USER/PASSWORD` lấy từ Secret thành vô dụng, phải chép `db_password` dạng plaintext vào ConfigMap, và mất bước `wait-for-psql.py`. | `/entrypoint.sh` trong image |
| A6 | `11-backup` | `pg_dump -d postgres` đang dump **database `postgres` rỗng**, không phải DB nghiệp vụ của Odoo. File backup được ghi vào chính `postgres-pvc` (cùng failure domain với DB), nên không phải DR thật. Cũng chưa có quy trình restore. | script trong CronJob |
| A7 | toàn bộ | Chưa có bước khởi tạo DB. Web và worker khởi động khi DB còn trống, lại để `list_db=True`, nên Database Manager (tạo/xoá/backup DB qua web) bị lộ ra ngoài. | `01-secrets-and-configmap.yaml` |
| A8 | `02`/`05` | PVC mới mount thuộc sở hữu `root`, trong khi Odoo chạy với uid `101`, nên có nguy cơ `Permission denied` khi ghi `filestore/` và `sessions/`. | `id odoo` → `uid=101` |
| A9 | `01` | `db_maxconn=64` là giới hạn **cho mỗi process**. 10 web pod × 3 process × 64 = 1.920 kết nối, trong khi PostgreSQL mặc định chỉ cho `max_connections=100`. KEDA scale lên là DB từ chối kết nối. | `odoo/tools/config.py:271` |

---

## 🟠 B. LUẬN ĐIỂM KIẾN TRÚC ĐỐI CHIẾU MÃ NGUỒN ODOO THẬT

| # | Luận điểm phổ biến thường nhầm | Thực tế trong mã nguồn Odoo |
|---|---|---|
| B1 | "Worker phải chạy Singleton, nếu không cron sẽ chạy trùng" | **Sai.** `odoo/addons/base/models/ir_cron.py:235-243` dùng `LIMIT 1 FOR NO KEY UPDATE SKIP LOCKED`. PostgreSQL tự động lock dòng cron đang chạy, các worker khác bỏ qua dòng đó. Do vậy Worker **hoàn toàn có thể scale ngang an toàn**. |
| B2 | "Redis lưu session tập trung cho Odoo" | **Sai.** Odoo 17 vanilla lưu session bằng `FilesystemSessionStore` (`odoo/http.py:2329`) trong `data_dir/sessions`. Nếu không cài module bên ngoài thì Pod Redis chạy độc lập không hề được kết nối. |
| B3 | "Odoo có sẵn hàng đợi ngầm cho in PDF/báo cáo" | Odoo vanilla **không có job queue**. In PDF chạy đồng bộ trong web request. Muốn có queue thực thụ phải cài **OCA `queue_job`**, từ đó KEDA mới có metric queue depth để scale. |
| B4 | "Bắt buộc phải bật Sticky Session" | Không bắt buộc. Session nằm trên Shared Storage, còn Bus/WebSocket đồng bộ qua PostgreSQL `pg_notify` (`addons/bus/models/bus.py`). Web Pods thực sự là **Stateless**. |
