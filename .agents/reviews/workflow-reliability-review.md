# Workflow and Argo CD review - 2026-10-16

Scope: GitOps sibling repo và app CI, một private CMC cluster, Dev/Prod riêng namespace/
node group. Không sửa firewall/DNS, không thực hiện data migration hoặc live deployment.

## Reference decisions

- `hgiang25/k8s-gitops` main `8a3c5f11153f48123c94cae69b11fce8faaf45b1`:
  `apps/dev`, `apps/prod`, cluster Applications riêng, Dev auto-sync/Prod manual.
- `hgiang25/aws-eks-gitops-platform` main `ef26fd34d6eb8f64c263d654e2a98c93eaa86a34`:
  CI chọn môi trường rõ ràng. Chuyển mô hình nhiều cluster sang AppProjects, namespace
  và node groups riêng trong một cluster; không copy AWS infra/networking.
- GitOps hiện dùng `clusters/cmc/{platform,dev,prod,legacy}` và
  `overlays/{cmc-common,dev,prod}`; image pins độc lập, Application names được giữ nguyên.

## Fixed deployment gaps

- Thêm Deploy CMC environments: Configure trả SHA → bootstrap Dev/Prod → Argo sync →
  verify; both chạy Dev rồi Prod. Promote Prod commit image được chấp nhận rồi sync/verify.
- Dev/Prod workload Applications đều explicit sync. Commit nguồn ban đầu giữ APISIX
  ClusterIP và không tự chạy workload; Configure chỉ bật private ELB sau khi flavor hợp lệ.
  App CI có thể gọi controlled Dev deploy bằng `CMC_AUTO_DEPLOY_DEV=true`.
- Bootstrap trước đây chỉ register root, Prod manual nên không tự deploy. Nay workflow
  explicit sync đúng environment, project và revision, theo thứ tự platform dependencies.
- Healthy/Synced cũ không được nhận; check SHA, workload generation/restart, actual pod
  image/readiness, KEDA, node placement và HTTP JSON có db_server_status=true.
- Không overwrite Argo operation đang chạy; resourceVersion CAS có retry. Failed sync
  được báo lỗi, không coi Healthy của revision trước là deploy thành công.
- Venv cho runner, mount kubeconfig hiện có, default DBaaS SSL disable được giữ.
- Runtime Secret hash chỉ acknowledge sau verification; rerun sau thất bại vẫn restart
  nếu cần, rerun sau thành công không restart vô điều kiện.
- App CI chỉ promote Dev, chặn stale source main, reuse và smoke-test sha tag hiện có.
  GitOps push rebase/validate retry khi main có thay đổi không conflict; không force push.
- DB preflight xác nhận quyền CONNECT management DB và DDL transactional trên DB đích.
- Platform AppProject không có namespaced destination Dev/Prod; dedicated projects riêng.

## Validation evidence

- `python validate.py`: all rendered resource invariants passed, shared DB budget 272/300.
- `python -m unittest discover -s tests -v`: 30 passed, including actual local bare-Git
  concurrent push/rebase fixture and negative Argo health/generation/operation cases.
- `python tests/validate_cloud_charts.py`: four pinned charts rendered, 36 custom resources
  validated against official CRDs; APISIX private HTTPS only, no Dev ELB.
- actionlint v1.7.12: GitOps and application workflows passed.
- `bash -n`: 22 GitOps + 8 app workflow scripts passed; Python/YAML parsed.
- `git diff --check`: passed (line-ending notices only).

## Runtime limits / handoff

Private Kubernetes API request timed out from workspace; no live acceptance performed.
Node groups not created per user confirmation; GitHub environment credentials/variables,
DB provisioning, registry and TLS trust must be supplied. Legacy writer/data migration
must finish before deploy. Backup remains suspended; S3/restore, WebSocket, NetworkPolicy,
RBAC, cross-node RWX and HA drills still require live tests. No automatic destructive migration.
Local Docker daemon unavailable, so new image/proxy smoke needs CI/runtime.
GitOps helpers are published first at commit `9204cd0`; the app workflow is published
afterward. Use a new Run workflow on main, not a rerun of the old workflow revision.
