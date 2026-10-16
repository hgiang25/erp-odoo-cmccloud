# Review Dev/Prod private CMC - 2026-10-15

## Kết quả

Đã triển khai và push cấu hình trong sibling `odoo-cmc-gitops` commit `9204cd0`, đồng
thời đổi app CI sang promote Dev. Không cấu hình firewall/DNS hoặc apply workload trực tiếp.

- Dev/Prod: namespaces, exact taint tolerations, required node affinity cho tất cả
  workload và bootstrap/restore Job; preferred pod anti-affinity web/worker và
  dispatcher affinity cùng namespace.
- Platform giữ nhóm hiện tại; file node-group contract + lệnh label/taint trên bastion.
- Dev không route/ELB, localhost port-forward qua proxy hỗ trợ HTTP/WebSocket.
  Prod private ELB TCP443 -> APISIX TLS, giữ upload100MiB/timeouts600s.
- ResourceQuota, LimitRange, ingress deny mặc định, namespaced developer RBAC,
  AppProjects riêng; shared DB account/grants preflight và budget272/300.
- Shared cmc-common không image pin: test đã phát hiện và sửa lỗi Kustomize child
  không override được tag đã đổi tên ở parent. Dev promotion không đổi Prod.
- Legacy Application manual/non-cascading; opt-in cmc-retired dừng writers và gỡ route,
  giữ dữ liệu. Dev/Prod explicit workflow sync, promote exact tested SHA, không rebuild.

## Verification

- `python validate.py`: base/local/http/legacy/Dev/Prod/retirement render và invariant pass.
- `python -m unittest discover -s tests -v`: 30 tests pass, có negative tests.
- `python tests/validate_cloud_charts.py`: APISIX2.10.0, Rollouts2.43.6, KEDA2.18.0,
  ArgoCD10.10.3 pinned Helm render + official CRD schema checks pass.
- Actionlint pass hai repo; `bash -n`: 22 GitOps + 8 app shell blocks pass.
  `git diff --check` pass.

## Chưa nghiệm thu live

- Hai node Dev và hai node Prod đã Ready; label/taint chưa được xác nhận. Private API
  vẫn timeout từ workspace nhưng đã truy cập lại được từ bastion.
- Source publish giữ APISIX ClusterIP; Configure chỉ bật private ELB sau khi nhận flavor
  đúng region. Runtime Secret/DB roles từng env chưa được xác nhận.
- Chưa migration DB/filestore, chưa TLS/ELB/WebSocket/KEDA/network-negative/RBAC/
  RWX cross-node/node-failure tests. Docker daemon local không chạy nên chưa smoke proxy.
- Chưa chạy Deploy CMC workflow. GitOps helper đã push trước app workflow.
- NetworkPolicy chỉ ingress, không thay firewall hoặc DBaaS grants. Dùng cluster chung
  vẫn chia sẻ control plane/controllers và quyền admin; GitOps access phải được giới hạn.
- PVC mới không tự migrate dữ liệu namespace cũ; backup/restore/S3 vẫn cần nghiệm thu.
