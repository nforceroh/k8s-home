# Local MCP servers

This directory contains repo-local MCP server source references, launchers, and
setup guidance. Keep per-computer credentials outside this repository.
Future MCP servers should live under this directory and be registered in
[`.vscode/mcp.json`](../.vscode/mcp.json) using workspace-relative paths.

## Arr MCP

The [Knuckles-Team Arr MCP server](https://github.com/Knuckles-Team/arr-mcp) is
included as a Git submodule pinned to upstream commit
`d4babd8070ac8336634b8fc68fd3a661f70354f` (release `v2.3.4`). Its upstream
`uv.lock` is used when launched.

### Set up on this computer

1. Initialize the pinned upstream submodule if it was not cloned recursively:

   ```bash
   git submodule update --init --recursive
   ```

2. Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/) and
   ensure it is available on `PATH`. The launcher also checks the existing
   `~/.local/share/k8s-home/uv/bin/uv` and `~/.local/bin/uv` locations.
3. Create the private env file used by `.vscode/mcp.json`. In the current
   workspace layout it lives in the sibling `k8s-home-secrets` repository. Add
   this computer's service URLs and API keys, and set `MCP_ENABLED_TOOLS` to the
   approved tool allowlist. Do not leave example values in place:

   ```bash
   mkdir -p ../k8s-home-secrets/mcp
   if [ ! -e ../k8s-home-secrets/mcp/arr-mcp.env ]; then
     install -m 600 mcp/.env.example ../k8s-home-secrets/mcp/arr-mcp.env
   fi
   ```

   Edit `../k8s-home-secrets/mcp/arr-mcp.env` locally. To carry an existing
   setup to another computer, transfer it through a secure channel; it contains
   API credentials and must never be committed to this repository.
4. Open the repository in VS Code and enable the `arr-mcp` server when prompted.
   The workspace configuration launches it over stdio and disables telemetry.

The current service toggles enable Sonarr, Radarr, Prowlarr, and Seerr. Generic
raw-HTTP passthrough tools are not in the approved allowlist. Prowlarr
configuration and Seerr user or request data may contain sensitive information.
Keep VS Code tool approvals enabled, review writes carefully, and do not select
**Always Allow**.

### Adding another MCP server

Keep its server-specific launcher, pinned source/dependency reference, and
non-secret setup notes under `mcp/<server>/`. Add its stdio entry to
`.vscode/mcp.json` with paths rooted at `${workspaceFolder}`; put credentials in
an ignored local env file and add only a placeholder template to the repository.
Do not commit secrets, local virtual environments, or unpinned third-party
source.
