# Behavior Tree Engine v2

`BehaviorTreeEngineModule` is the tick-based runtime bridge between high-level
task graphs and action execution.  It keeps the legacy `behavior.tree.run`
topic, but each run now creates a session with node state and a blackboard.

## Status Model

Node status values:

- `SUCCESS`
- `FAILURE`
- `RUNNING`
- `CANCELLED`
- `TIMEOUT`
- `ERROR`

Terminal results are published on `behavior.tree.result`.  Per-tick state is
published on `behavior.tree.tick_result`.

## Runtime Topics

| Topic | Purpose |
|-------|---------|
| `behavior.tree.run` | Start a BT session and tick once by default. |
| `behavior.tree.tick` | Advance one session by `run_id`, or all active sessions. |
| `behavior.tree.cancel` | Cancel a running session and its active async action nodes. |
| `behavior.tree.action.request` | Async action node dispatch request. |
| `behavior.tree.action.result` | External completion/failure for an async action node. |
| `behavior.tree.action.cancel` | Cancellation request for a running async action node. |
| `behavior.tree.trace` | Per-tick/terminal replay record for BT runtime evidence. |
| `behavior.tree.query` | Capability and active-session snapshot. |

## Blackboard

Run messages may include an initial `blackboard` dictionary.  Action nodes can
write to it:

```json
{
  "type": "action",
  "id": "remember_object",
  "params": {
    "set_blackboard": {"object_visible": true}
  }
}
```

Condition nodes can read from it:

```json
{
  "type": "condition",
  "id": "object_visible",
  "params": {"key": "object_visible", "expect": true}
}
```

Async action results may also include `blackboard_update`.

## Async Action Nodes

An action is asynchronous when one of these flags is true:

- `async`
- `async_action`
- `wait_for_result`
- `params.async`

The engine publishes `behavior.tree.action.request` and returns `RUNNING`.
The node completes only after `behavior.tree.action.result` is received and the
session is ticked again.

Each async request includes `run_id`, `node_id`, `action_id`, `action_type` and
an unguessable `result_token`.  Action results are accepted only when they match
an action that this engine dispatched and that is still `RUNNING`.  The
`result_token` is a single-use nonce; a second submission of the same accepted
result is rejected with `behavior.tree.action_result_ack` status
`duplicate_action_result_nonce`.  A result with an unknown, missing, or
mismatched `action_id`, `node_id`, `action_type`, or `result_token` is rejected
with `unauthorized_action_result`.

## Cancellation And Timeout

`behavior.tree.cancel` moves the session to `CANCELLED` and publishes
`behavior.tree.action.cancel` for every running async action.

Any node may define `timeout_ms`.  When the elapsed time since node/action start
exceeds that value, the node returns `TIMEOUT`, active async action is cancelled,
and the session publishes a terminal timeout result.

`parallel` nodes also cancel still-running child async actions when one child
forces a terminal outcome (`FAILURE`, `TIMEOUT`, `CANCELLED`, `ERROR`) or when a
configured `success_threshold` is met before every child completes.

## Resource Limits And Cleanup

The engine validates every submitted tree before creating a session:

| Limit | Default |
|-------|---------|
| Maximum tree depth | `32` |
| Maximum node count | `256` |
| Maximum blackboard JSON bytes | `65536` |
| Maximum session JSON bytes | `262144` |
| Maximum in-memory trace events | `512` |
| Maximum tick wall-clock budget | `50 ms` |
| Duplicate explicit node ids | rejected |

Generated path ids remain allowed; duplicate validation applies to explicit
`id`, `node_id`, or `name` fields.  Invalid trees publish
`behavior.tree.result` with `status=invalid_tree`, `bt_status=ERROR`, and
`validation_errors`.

Sessions also have runtime cleanup:

| Cleanup | Default |
|---------|---------|
| Active session TTL | `600000 ms` |
| Terminal session retention | `60000 ms` |

When an active session exceeds its TTL, the engine cancels running async
actions, marks the session `TIMEOUT`, publishes terminal result evidence, and
removes the stale session from memory.

The blackboard byte budget is checked before a session starts and after runtime
updates.  Session byte budget covers blackboard, node state, accepted action
results, and in-memory trace.  Tick wall-clock budget is enforced per tick; if
it is exceeded, the session moves to `TIMEOUT` and running async actions are
cancelled with reason `tick_cpu_budget_exceeded`.

## Trace And Replay Evidence

Every tick publishes a `behavior.tree.trace` record with schema
`behavior_tree.trace.v1`; terminal completion publishes a final trace record.
If `BehaviorTreeEngineModule(trace_path="...")` is configured, the same records
are appended as JSONL.  These records contain `run_id`, BT status, tick count,
recent node-status trace, and the result payload, so they can be fed into the
existing file replay/evidence tooling without relying on live process memory.

For release evidence, validate the persisted trace with:

```bash
python -m core.tools.behavior_tree_trace_replay \
  logs/behavior_tree/bt_trace.jsonl \
  --expect-run-id bt-public-demo \
  --expect-status SUCCESS \
  --out logs/behavior_tree/behavior_tree_trace_replay_report.json
```

The generated report uses schema `behavior_tree.trace_replay.v1` and records
`observed_status`, artifact SHA-256, terminal BT status, tick ordering,
node-status transitions, and validation findings.  The release readiness matrix
can consume it with `--behavior-tree-trace-replay-report`.

## Supported Node Types

- `sequence`, `seq`, `memory_sequence`
- `selector`, `sel`, `fallback`, `priority_selector`
- `parallel`, `par`
- `condition`, `cond`
- `inverter`, `invert`
- `action`
