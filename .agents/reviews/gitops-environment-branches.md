# GitOps environment branches (2026-10-18)

Application source remains on main. Release CI builds immutable images and updates
only overlays/dev on the GitOps repository's dev branch (never main or prod).
GitOps main owns platform Applications, dev/prod branches own their workload overlays.
GitOps promotion verifies a pinned Dev revision then copies its image pair to prod,
without rebuilding or merging Dev namespace/configuration into Production.
See sibling odoo-cmc-gitops/cmc/BRANCH-WORKFLOW.md for migration and protection setup.
