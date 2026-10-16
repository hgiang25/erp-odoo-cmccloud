# Workflow reliability review - 2026-10-16

Mục tiêu: một entry workflow deploy từ desired state đã publish, có thứ tự và kiểm tra
đúng revision; chạy lại an toàn. Không thay firewall/DNS, không tự migrate dữ liệu cũ.

1. Rà soát app CI, Configure, Bootstrap, Promote, Verify và Argo app-of-apps.
2. Sửa runner Python bằng venv, ref/main guards, Git push retry không force, checkout
   revision sau Configure; giữ kubeconfig mount hiện tại và policy TLS DBaaS.
3. Thêm entry workflow gọi Configure -> Bootstrap+sync+verify Dev/Prod tuần tự; Prod
   chỉ được sync khi legacy đã dừng và dữ liệu đã được chuẩn bị.
4. Chờ Argo operation/revision và workload observedGeneration; không nhận Healthy cũ.
   Restart chỉ khi runtime Secret thay đổi; không restart giữa rollout đang chạy.
5. Kiểm tra image/pods, DB/DDL, storage, node placement, metrics và health JSON;
   báo lỗi có timeout. Kiểm tra điều kiện môi trường trước khi thay runtime Secret.
6. Kiểm tra workflow schema/actionlint, Python tests có fake Kubernetes/Git fixtures,
   Kustomize/Helm/CRDs và Bash syntax. Ghi rõ phần chưa thể chạy thật.

Các điều kiện bên ngoài: CMC groups/DB roles/Secrets, private API access, registry,
ELB flavor/TLS và data migration. GitHub workflow không tự tạo các tài nguyên này.

Status: source implementation và offline verification hoàn tất; GitOps commit `9204cd0`
đã push. Live acceptance còn chờ label/taint, DB roles/Secrets và data migration. Xem
`../reviews/workflow-reliability-review.md`. Chưa chạy workflow deploy.
