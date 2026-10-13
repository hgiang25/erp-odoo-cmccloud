# CMC readiness review — 2026-10-13

Phạm vi: refactor lớp triển khai Kubernetes cho CMC staging, giữ Odoo modular
monolith, một DB PostgreSQL và shared filestore/sessions. Không refactor core ERP.

## Kết luận

Trước refactor, repo chưa deploy CMC trực tiếp được: image local, context cố định,
StorageClass mặc định, NodePort localhost, restore helper local và chưa có TLS.
Sau refactor có luồng GitOps: CI build/push → commit image tag → Argo CD reconcile.
Self-hosted runner trên bastion chỉ chạy bootstrap Argo CD một lần; `cmc.py` chỉ
render và preflight, không còn action deploy workload trực tiếp.
Chưa thể kết luận production-ready hoặc cloud runtime đã chạy: người dùng mới
chọn Docker Hub, chưa dựng NFS và chưa cung cấp kubeconfig/domain.

## Các thay đổi

| Vấn đề | Xử lý |
|---|---|
| Context/local image | cmc.py nhận config, từ chối docker-desktop và chỉ preflight; Kustomize dùng image Docker Hub bất biến |
| Deploy trực tiếp gây drift | Argo CD app-of-apps là reconciler; runner bastion chỉ cài Argo CD và đăng ký root Application |
| Windows-only deploy | GitHub Actions bootstrap chạy Linux self-hosted; restore/recovery PowerShell vẫn nhận Context và Template |
| RWO không dùng chung nhiều node | Chỉ định blockClass cho Postgres/etcd và sharedClass RWX cho 3 PVC Odoo |
| HTTP/redirect localhost | CMC ELB 443, ApisixTls, forwarded host/proto domain HTTPS |
| Gateway subchart mở NodePort phụ | Chuyển Service phụ sang ClusterIP, kiểm tra Helm render |
| Truy cập DB/worker/admin rộng | NetworkPolicy ingress app/DB/gateway/etcd; egress để mở cho API, DNS, NFS, SMTP/external integrations |
| Web cùng node/drain | Preferred topology spread + PDB minAvailable 1; không tuyên bố HA cho DB/etcd |
| Backup trong canary | Backup từ chối Rollout chưa Healthy; RBAC read cụ thể; lịch cloud mặc định suspended |
| Restore Job trùng tên | Bổ sung hash database đích vào tên Job |
| Cleanup theo current-context | undeploy chỉ docker-desktop, yêu cầu DeleteLocalData và hỗ trợ WhatIf |
| Lost DB Secret | Preflight từ chối tạo credential khác cho PVC PostgreSQL đã tồn tại |

Workflow kế thừa repo `hcm3-k8s-lab` ở việc tách build image, tag theo commit và
dùng self-hosted runner có kubeconfig. Phần `kubectl apply/set image` trực tiếp được
thay bằng commit promotion để Git luôn phản ánh trạng thái cluster mong muốn.

Image Dockerfile dựa trên image Odoo chính thức, không chạy source checkout của
repo. Cần build lại backup image vì thêm kiểm tra Rollout và push tag mới. Không
ghi Secrets vào artifact/Git. Init giữ nguyên mật khẩu DB cũ khi chạy lại.

## Kiểm thử

- Base/local/http-scaling và CMC overlay được render bằng Kustomize; app-of-apps có
  5 Application con và root Application tự động prune/self-heal.
- Tests unit/integration offline: image registry của init/backup/restore và private
  pull secrets; storage/TLS/NetworkPolicy; chặn placeholder/local context/version
  mismatch; restore cùng snapshot sang DB khác sinh tên Job khác; DB init lỗi
  không chạy app; StorageClass thiếu hoặc PVC mất Secret bị chặn trước mutation.
- PowerShell parser cho scripts; CRD schema chính thức của các chart ghim.
- Helm render APISIX/Argo/KEDA; xác minh ELB HTTPS-only và Service phụ ClusterIP.
- Không tạo cluster, NFS VM, ELB, Secret, không bootstrap Argo CD và chưa push image trong lượt refactor.

## Những điều còn phải nghiệm thu

- Portal CMC/version/kubeconfig thật. 1.32 EOL upstream 2026-02-28; tài liệu CMC
  ghi hỗ trợ tới 1.32.7 không chứng minh extended security maintenance. Cần xác
  nhận support/patch với CMC; KEDA 2.18 chỉ tested 1.31–1.33, không nhận 1.36.
- NFS provisioner thực sự RWX, UID/GID 101, shared session/attachment cross-node.
- Docker Hub pull từ tất cả node, proxy/firewall/rate limit, image vulnerability scan.
- ELB regional annotation, external IP, DNS, certificate và WebSocket.
- Autoscaling, canary, NetworkPolicy enforcement, backup pause/resume và restore drill.
- Production: PostgreSQL HA/DBaaS, etcd HA, NFS availability, offsite backup/PITR,
  monitoring/alerts và upgrade controller. Hiện backup chỉ nằm trên PVC.

Nguồn: [CMC NFS](https://cmccloud.vn/document/kubernetes/huong-dan/cau-hinh-nfs-lam-storageclass-cho-cum-k8s),
[CMC ELB](https://cmccloud.vn/document/Kubernetes/huong-dan/tao-service-cho-cum-k8s-voi-dich-vu-elastic-load-balancer),
[Kubernetes lifecycle](https://kubernetes.io/releases/patch-releases/),
[KEDA matrix](https://keda.sh/docs/2.18/operate/cluster/).
