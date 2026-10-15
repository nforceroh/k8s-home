# Repository Guide

## Deployment Ownership

- `virt01/automated/` contains applications managed through GitOps by Argo CD. Make desired-state changes in this repository and follow the app's existing Helm or Kubernetes-manifest structure. Argo CD reconciles these files to the cluster.
- `virt01/manual/` contains applications deployed and maintained manually, outside Argo CD. Follow the instructions and deployment method documented for each app; do not assume Argo CD will apply changes there.
- `virt01/deprecated/` contains retired or superseded app material. Treat it as historical unless a task explicitly targets it.

## Repository Map

- `virt01/argocd/` and `virt01/appsConfigurator/` configure Argo CD and application discovery. Changes here can affect how apps are installed or reconciled.
- `virt01/globalValues.yaml` contains values shared by the virt01 app configuration.
- `ansible-k8s/` contains Ansible roles and dependencies for preparing hosts and installing Kubernetes.
- `ref/` holds operational notes, reference configurations, and supporting scripts.
- `scripts/` contains repository utilities; `updatecli/` contains chart-update automation.
- `README.md` contains workstation setup and operational procedures.

## Working in This Repository

- Before changing an app, inspect its local README, chart or manifests, and a neighboring app with the same deployment style.
- For `virt01/automated/`, change the checked-in desired state rather than making an untracked live-cluster change. Check the relevant Argo CD ApplicationSet when changing app discovery or ownership.
- For `virt01/manual/`, preserve the app's manual deployment workflow and update its documentation when the procedure changes.
- Keep credentials and other secrets in the repository's established secret-management workflow; do not add plaintext credentials.
- Validate with the tools appropriate to the changed files, such as `helm lint` and `helm template` for charts, `kustomize build` for Kustomize apps, or Ansible syntax checks for playbooks and roles. State any checks that could not be run.

## Agent skills

### Issue tracker

Issues are tracked on GitHub. See `docs/agents/issue-tracker.md`.

### Triage labels

Default triage labels are used: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout. See `docs/agents/domain.md`.
