# AGENTS.MD - QUY CHUẨN ĐIỀU PHỐI & CONTEXT CHO AI AGENTS / CODEX
> **Dự án**: Odoo ERP trên Cloud-Native Kubernetes (CMC Cloud Final Lab)  
> **Thư mục trung tâm**: `.agents/`  
> **Mục đích**: Cung cấp toàn bộ Context, Rules, Kiến trúc và Kế hoạch để mọi Agent (Antigravity, Codex, Cursor...) đọc và tuân thủ nhất quán.

---

## 1. TỔNG QUAN DỰ ÁN & VAI TRÒ HỆ THỐNG
- **Bản chất phần mềm**: Odoo 17.0 là một **Modular Monolith** bằng Python/PostgreSQL.
- **Mô hình triển khai Cloud**: **Decomposed Monolith** trên Kubernetes:
  1. **Web Tier**: Stateless, co giãn ngang 2 -> 10 Pods, tắt cron (`--max-cron-threads=0`).
  2. **Worker Tier**: Xử lý tác vụ ngầm và hàng đợi bất đồng bộ (OCA `queue_job`), co giãn theo độ dài hàng đợi (KEDA).
  3. **Gateway Tier**: Apache APISIX Ingress / Gateway (thay thế Ingress-NGINX đã retire).
  4. **State Tier**: Shared Storage (PVC) cho Filestore (`/var/lib/odoo/filestore`) và Sessions (`/var/lib/odoo/sessions`).
  5. **Data Tier**: PostgreSQL 15 StatefulSet (mô phỏng DBaaS trên Cloud).

---

## 2. CẤU TRÚC THƯ MỤC `.AGENTS/`
Mọi tài liệu, quy tắc và kế hoạch phải được lưu trữ tập trung tại đây:

```
.agents/
├── AGENTS.md                   # File này (Hub trung tâm quy tắc và context)
├── rules/                      # Các ràng buộc và tiêu chuẩn kỹ thuật bắt buộc
│   ├── 01-architecture.md      # Quy chuẩn kiến trúc Decomposed Monolith & Odoo Native
│   ├── 02-k8s-standards.md      # Quy chuẩn bảo mật, memory limits, probe cho Kubernetes
│   └── 03-prompting-rules.md   # Công thức prompt chuẩn cho Codex / AI Agents
├── plans/                      # Các bản kế hoạch thực thi (Implementation Plans)
│   └── k8s-decomposed-monolith-plan.md
└── reviews/                    # Các báo cáo đánh giá code, lỗi vận hành & kiểm thử
    └── k8s-code-review-findings.md
```

---

## 3. NGUYÊN TẮC BẮT BUỘC ĐỐI VỚI MỌI AI AGENT
1. **Luôn đọc `.agents/rules/` trước khi chỉnh sửa code**: Không được tự ý đưa vào các công nghệ không khớp với mã nguồn thực tế của Odoo (ví dụ: Odoo vanilla không dùng Redis để lưu session hay cache, không được tự ý thêm Redis).
2. **Tuân thủ toàn vẹn dữ liệu ACID**: Không được biến tướng Odoo thành Microservices phân tán dữ liệu.
3. **Kiểm tra tính tương thích thực tế (Reality Check)**: Mọi câu lệnh, tham số cấu hình (flags) phải được kiểm chứng bằng code thật trong repo hoặc container image trước khi đề xuất cho người dùng.
4. **Cập nhật Plans & Reviews**: Khi có yêu cầu mới hoặc phát hiện lỗi, luôn cập nhật vào `.agents/plans/` hoặc `.agents/reviews/`.

## Cập nhật thực thi 2026-10-13
Manifest thực thi nằm trong k8s/base; web dùng một Argo Rollout. Worker tier tách cron, queue dispatcher và HTTP worker nội bộ theo OCA runtime. Xem plan mục 4 và reviews/k8s-plan-completion-review.md.
