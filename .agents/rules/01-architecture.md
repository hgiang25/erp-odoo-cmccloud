# QUY CHUẨN KIẾN TRÚC: ODOO DECOMPOSED MONOLITH
> **Mã quy tắc**: `RULE-ARCH-01`  
> **Áp dụng cho**: Mọi Agent phát triển, tối ưu hoặc triển khai hạ tầng Odoo.

---

## 1. NGUYÊN TẮC DECOMPOSED MONOLITH
- **Không chia cắt cơ sở dữ liệu**: Toàn bộ nghiệp vụ (Kế toán, Kho, Bán hàng, Mua hàng) **bắt buộc** phải chia sẻ chung một cơ sở dữ liệu PostgreSQL để đảm bảo tính toàn vẹn giao dịch (ACID). Tuyệt đối không áp dụng Database-per-service (Microservices) cho core ERP.
- **Phân rã hạ tầng (Infrastructure Decomposition)**:
  - **Tách Web và Worker**:
    - Web Pods: Chạy với `--max-cron-threads=0`, chuyên tiếp nhận lưu lượng HTTP/WebSocket, cấu hình co giãn ngang tự do (2 -> 10 Pods).
    - Cron Pods: `--no-http --workers=2 --max-cron-threads=2`, chuyên chạy ir_cron.
    - Queue dispatcher: `--no-http --workers=1 --max-cron-threads=0`, nạp queue_job và gửi job tới Service nội bộ.
    - Queue Worker Pods: `--workers=2 --max-cron-threads=0`, HTTP nội bộ xử lý /queue_job/runjob; tắt runner bằng ODOO_QUEUE_JOB_CHANNELS=root:0.

---

## 2. NGUYÊN TẮC TRẠNG THÁI & LƯU TRỮ (STATE MANAGEMENT)
1. **Sessions**:
   - Odoo vanilla sử dụng `FilesystemSessionStore` (`odoo/http.py`), lưu phiên đăng nhập tại `data_dir/sessions` (mặc định `/var/lib/odoo/sessions`).
   - Tầng Web Pods đạt trạng thái **Stateless** khi mount chung Persistent Volume Claim (PVC) chứa thư mục này.
   - **Cấm**: Tự ý chèn Redis làm session store trừ khi có cài đặt thêm module bên thứ 3 chuyên biệt (`session_redis`).
2. **Realtime Notifications & WebSocket (Bus)**:
   - Các sự kiện thời gian thực (Chatter, Livechat, Thông báo) giữa các Web Pods được đồng bộ qua cơ chế **PostgreSQL `pg_notify`** (`addons/bus/models/bus.py`).
   - Không cần message broker bên ngoài (Kafka/RabbitMQ) cho luồng bus nội bộ.
3. **Shared Storage (Filestore)**:
   - Toàn bộ file đính kèm (`ir.attachment`), ảnh sản phẩm, PDF hóa đơn lưu tại `/var/lib/odoo/filestore`.
   - Trên Kubernetes multi-node (Cloud), PVC **bắt buộc phải hỗ trợ `ReadWriteMany` (RWX)** như NFS, Ceph, hoặc CMC File Storage.

---

## 3. NGUYÊN TẮC HÀNG ĐỢI TÁC VỤ & CO GIÃN (QUEUE & KEDA)
1. **Cơ chế khóa an toàn của Odoo Cron**:
   - `ir_cron` sử dụng câu lệnh SQL `LIMIT 1 FOR NO KEY UPDATE SKIP LOCKED` (`odoo/addons/base/models/ir_cron.py`).
   - Khóa dòng ngăn nhiều cron processes cùng xử lý một dòng đồng thời; cần xử lý retry/idempotence sau crash.
2. **Hàng đợi tác vụ thật (OCA `queue_job`)**:
   - Các tác vụ nặng (kết xuất báo cáo, in hàng loạt chứng từ, đồng bộ dữ liệu) được đưa vào hàng đợi `queue.job`.
   - KEDA sẽ co giãn Worker Pods dựa trên độ dài hàng đợi thực tế trong PostgreSQL bằng truy vấn:
     `SELECT count(*) FROM queue_job WHERE state IN ('pending', 'enqueued', 'started')`.

Thông số đã kiểm chứng 2026-10-13: Web 2–10 pods; queue worker 1–8 pods; dispatcher root:8. Source thực thi: k8s/base/. Không tuyên bố cron exactly-once; SKIP LOCKED bảo vệ chạy đồng thời, crash có thể cần retry/idempotence.
