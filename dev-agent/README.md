# Swayz Autonomous Development Agent

Development branch for the separately hosted Swayz development coordinator.

## Intended deployment
- Host: dedicated Swayz development Droplet
- User: non-root `swayzdev`
- App directory: `/home/swayzdev/swayz-agent/app`
- Source repository: `/home/swayzdev/swayz-agent/workspace/swayz-ai-bridge`
- Python: 3.12 virtual environment at `/home/swayzdev/swayz-agent/.venv`

## Current state
The consolidated agent source and tests are still in the offline checkpoint
`swayz_dev_agent_worker_preflight.zip` and are **not yet committed here**.
This branch is a staging target, not an installable release.

## Deployment gates
1. Import and review the actual source and tests from the checkpoint.
2. Run the full Python suite on this branch in CI.
3. Run Docker isolation checks on the dedicated Droplet.
4. Configure authenticated GitHub access restricted to development branches.
5. Configure provider API credentials via secret storage, with cost caps.
6. Prove one bounded OpenAI -> test -> Claude -> draft PR cycle.
7. Test emergency stop, restart recovery and reporting.

No live trading, automated merging, or unattended operation is authorised.
