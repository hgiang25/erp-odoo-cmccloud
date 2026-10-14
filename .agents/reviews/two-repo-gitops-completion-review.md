# Review hoàn tất two-repository GitOps - 2026-10-13

## Kết luận

Ranh giới CI/CD và GitOps đã được triển khai ở source:

- `erp-odoo-cmccloud`: test, build, smoke-test, push image, commit promotion.
- `odoo-cmc-gitops`: desired state, environment config, bootstrap và DR.
- Argo CD: thành phần duy nhất reconcile workload vào CMC Kubernetes.

Ba lỗi blocking trước lượt này đã được xử lý: app repo còn bản sao manifest; image
release không chứa source checkout; cloud overlay vẫn chạy PostgreSQL trong cluster và
backup chỉ nằm trên PVC.

## Liên kết CMC

- DBaaS: headless Service + EndpointSlice tới private IP/VIP; Odoo, init, KEDA và
  backup dùng cùng DNS `postgres-service.odoo-system.svc.cluster.local`.
- S3: backup upload DB dump, filestore, metadata, checksum rồi mới tạo `_SUCCESS`;
  restore tải từ S3 khi PVC staging không có bộ backup.
- ELB/Ingress: CMC LoadBalancer HTTPS 443 -> APISIX -> stable/canary HTTP và WebSocket.
- State: NFS RWX dùng chung filestore/sessions; UID/GID 101.
- Secrets: bootstrap lấy DB/S3/TLS từ GitHub Secrets, không commit credential.

## Kiểm chứng đã chạy

- `python validate.py`: base/local/http/CMC và app-of-apps render, cross-resource pass.
- 10 unit/integration cloud boundary tests pass.
- APISIX, Argo Rollouts, KEDA, Argo CD Helm render pass; 13 custom resources qua
  schema CRD ghim; ELB HTTPS-only được xác nhận.
- Python release helpers compile và Docker Compose config hợp lệ.
- Docker daemon local không chạy nên chưa thể build/smoke image tại máy này; workflow
  CI có gate import Odoo từ `/opt/odoo-src` và import boto3 trước khi push.

## Chưa thể kết luận nếu chưa có CMC runtime

- Chưa có giá trị thật cho DBaaS IP, NFS StorageClass, S3, domain/TLS, ELB flavor.
- Chưa chạy bootstrap, image pull, DB init, canary/KEDA, WebSocket, RWX cross-node.
- Chưa chạy backup lên S3 và restore drill với DBaaS thật.
- APISIX etcd đã chuyển thành ba member với PDB; chưa production-ready nếu chưa nghiệm
  thu mất node/volume và bổ sung monitoring/alerting.

## Rà soát bổ sung 2026-10-14

- DB runtime đã chuyển sang Secret `odoo-db-connection`; thay GitHub DB Variable/Secret và
  chạy lại bootstrap sẽ rotate endpoint/credential mà không sửa manifest.
- DBaaS preflight xác nhận PostgreSQL 16, TLS và credential từ pod trong cluster.
- Overlay thật đã có `odoo-registry`; canary dùng AnalysisTemplate gọi health endpoint có
  kiểm tra database trước khi tăng traffic.
- Workflow `configure-cmc.yml` thay placeholder hạ tầng không nhạy cảm; workflow
  `verify-cmc.yml` đợi Argo Synced/Healthy, Rollout Healthy, image tag và public health.
- Offline validation chạy được với kubectl v1.32.7/Kustomize v5.5.0 ghim trong CI.
- APISIX external etcd chạy ba member, anti-affinity và PDB `minAvailable: 2`.
- Phần backup/restore/DR không thuộc phạm vi hoàn thiện này và vẫn chưa được nghiệm thu.
