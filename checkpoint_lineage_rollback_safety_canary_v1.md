# Checkpoint Lineage, Rollback Gate and Safety Canary v1

This profile adds the missing promotion safety layer on top of the distributed trainer fleet.

## What it does
- Tracks checkpoint lineage with stable/runtime/candidate roles
- Runs a deterministic safety-canary evaluation for new checkpoints
- Recommends `apply`, `canary`, `shadow`, `rollback`, or `reject`
- Supports rollback to the last stable checkpoint
- Publishes results that can be consumed by trainer deployment and household autonomy dashboards

## Main events
- `learning.checkpoint_lineage.submit`
- `learning.checkpoint_lineage.query`
- `learning.checkpoint_lineage.rollback`
- `learning.checkpoint_lineage.status`
- `learning.checkpoint_lineage.canary_completed`
- `learning.checkpoint_lineage.rollback_result`
- `learning.checkpoint_lineage.result`

## Result model
The module keeps a lineage registry with:
- `stable_checkpoint`
- `runtime_checkpoint`
- `candidate_checkpoint`
- `lineage`
- `canary_evaluations`
- `rollback_history`

## Recommended usage
1. Produce a checkpoint from the distributed trainer fleet
2. Submit it to `learning.checkpoint_lineage.submit`
3. Use `apply_recommended=true` for controlled canary/application
4. If safety regresses, let the module request rollback automatically or send `learning.checkpoint_lineage.rollback`
