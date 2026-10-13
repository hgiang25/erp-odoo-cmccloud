# QUY CHUẨN GIAO VIỆC & PROMPT HIỆU QUẢ CHO CODEX / AI AGENTS
> **Mã quy tắc**: `RULE-PROMPT-03`  
> **Áp dụng cho**: Mọi yêu cầu lập trình, sửa lỗi hoặc tái cấu trúc bằng AI.

---

## 1. CÔNG THỨC VIẾT PROMPT CHUẨN 4 THÀNH PHẦN

Khi giao việc cho Codex hoặc các AI Agent, prompt phải luôn có đủ 4 yếu tố:

```
[OUTCOME] + [CONTEXT] + [CONSTRAINTS] + [VERIFICATION]
```

1. **Outcome (Kết quả mong đợi cụ thể)**:
   - *Yếu*: "Sửa lỗi Odoo K8s đi."
   - *Mạnh*: "Cập nhật file `k8s/05-odoo-web.yaml` để bổ sung `securityContext fsGroup: 101` và điều chỉnh memory limit lên `2.5Gi` nhằm ngăn lỗi OOMKilled."
2. **Context (Ngữ cảnh kỹ thuật & file tham chiếu)**:
   - Nêu rõ các file liên quan: [k8s/01-secrets-and-configmap.yaml](file:///e:/Pool-Fresher/Final_Lab/odoo/k8s/01-secrets-and-configmap.yaml), [odoo/tools/config.py](file:///e:/Pool-Fresher/Final_Lab/odoo/odoo/tools/config.py).
   - Chỉ ra phiên bản và môi trường: Odoo 17.0 Community, Docker Desktop K8s, PostgreSQL 15.
3. **Constraints (Ràng buộc cấm vi phạm)**:
   - Không được tự ý đưa vào Redis vì Odoo vanilla không hỗ trợ native.
   - Không được phá vỡ kiến trúc ACID / Decomposed Monolith.
   - Giữ nguyên các comment giải thích kiến trúc quan trọng.
4. **Verification (Yêu cầu kiểm thử trước khi bàn giao)**:
   - Chạy lệnh kiểm tra cú pháp (ví dụ: `kubectl kustomize`, `docker compose config`).
   - Đảm bảo không có lỗi cú pháp hoặc schema trước khi báo hoàn thành.

---

## 2. BỘ PROMPT MẪU CHUẨN (TEMPLATES)

### Mẫu 1: Yêu cầu rà soát & phản biện code (Review & Sanity Check)
```markdown
Hãy đọc kỹ các file [tên_file] trong thư mục [đường_dẫn]. 
Đối chiếu từng dòng cấu hình với mã nguồn thực tế của [công_nghệ] và chỉ ra:
1. Có cấu hình nào trái với hành vi mặc định của framework không?
2. Có nguy cơ lỗi runtime nào (OOM, Permission, Connection timeout) không?
3. Viết kết quả dưới dạng bảng so sánh và lưu vào thư mục `.agents/reviews/`.
Trước khi sửa code, hãy hỏi lại tôi 2 câu ngắn gọn để làm rõ hướng xử lý.
```

### Mẫu 2: Yêu cầu tạo mới hoặc sửa Manifest Kubernetes
```markdown
Hãy cập nhật manifest [tên_manifest] theo quy chuẩn `.agents/rules/02-k8s-standards.md`.
Ràng buộc:
- Bắt buộc có securityContext fsGroup: 101.
- Không ghi đè entrypoint mặc định của container.
- Tài nguyên CPU/RAM phải tuân thủ công thức tính toán bộ nhớ trong rule.
Sau khi sửa, hãy chạy lệnh `kubectl kustomize k8s` để kiểm tra tính hợp lệ của manifest.
```

### Mẫu 3: Yêu cầu lập kế hoạch triển khai tính năng mới
```markdown
Tôi muốn thêm [tính_năng] vào dự án. 
Hãy phân tích kiến trúc, liệt kê các file cần tạo/sửa và lập kế hoạch chi tiết (Plan).
Lưu kế hoạch vào `.agents/plans/[tên_tính_năng]-plan.md`. 
Chưa bắt đầu sửa code ngay cho đến khi tôi xem qua và bấm xác nhận kế hoạch.
```
