# World-frame reduced-order gait trajectory v2

`gait.trajectory.v2` replaces the old three-waypoint swing reference with a
world-frame, continuously sampled control contract.  It is intentionally named
`reduced_order_lipm_kinodynamic`: this version is not a full multibody
kinodynamic optimizer.

## Planning contract

Each `world_footstep_plan.v1` step contains measured/estimated start and support
foot poses, a nominal and applied six-DoF touchdown pose, terrain normal,
LIPM/DCM placement correction, support-foot-frame reachability bounds, and the
projection residual.  Explicit unknown input frames are rejected.  Legacy
targets without a frame are transformed from the base frame and marked
non-authoritative.

The swing and pelvis references use quintic boundary polynomials.  Position,
velocity, and acceleration are continuous at their endpoints.  Swing height is
a bounded polynomial clearance bump.  Foot orientation follows shortest-path
quaternion interpolation to a sole frame whose local z-axis matches the terrain
normal.  Toe-off and heel-strike are represented both as pose changes and as
contact/CoP regions (`forefoot`, `flight`, `heel`, `full_sole`).

On every gait-loop tick the module publishes `locomotion.gait_setpoint` with:

- active plan revision and step index;
- timestamp and application deadline;
- swing-foot pose, twist, and spatial acceleration;
- pelvis pose, twist, and acceleration;
- contact mode, CoP region, and impedance mode.

WBC consumes the active step rather than permanently using segment zero.  Its
floating-base QP tracks the six-dimensional swing acceleration, and
model-based IK tracks swing position and SO(3) orientation when the setpoint is
available.

## Online adaptation

The touchdown target is adjusted from measured or reconstructed DCM error and
then projected into a convex reachable region in the support-foot frame.  Step
time is shortened for bounded capture/disturbance response and extended for
terrain height changes.  A late touchdown splices a C2-continuous, bounded
vertical contact-search polynomial into the active swing trajectory.  Search
depth and accumulated extension are capped; exhausting the budget requests a
safe hold instead of continuing an unbounded search.

## Evidence boundary

Software tests prove schema, coordinate transforms, trajectory invariants,
constraint projection, retiming continuity, and controller plumbing.  They do
not prove that a physical humanoid walks without falling.

Locomotion artifacts use exact validation classes:

1. `mock_contract`
2. `offline_scripted_bus`
3. `offline_telemetry_replay`
4. `software_shadow`
5. `sim_runtime_smoke`
6. `physics_simulation`
7. `hardware_shadow`
8. `physical_hil`
9. `physical_robot`

The current EventBus/`SimRobotAdapter` stability suite is
`offline_scripted_bus`.  The current Isaac scene is `sim_runtime_smoke`: it
checks runtime/articulation behavior, not closed-loop contact dynamics.  Neither
may set `physical_locomotion_proven=true`.

File-backed native harnesses also remain `offline_scripted_bus`.  A live
controller/bus trace without observed actuators is `software_shadow`, not
`hardware_shadow`.  The latter requires an identified physical device in the
observation lineage.

A future `physics_simulation` acceptance must run the actual estimator → WBC/QP
→ command-frame → plant feedback loop with gravity/contact dynamics, motor
latency, measured root motion, CoM/support margins, tracking error, perturbation
recovery, and fall detection across multiple seeds.  `physical_hil` additionally
requires live command → acknowledgement → actuator/IMU/contact feedback,
hardware identity and clock lineage, e-stop/harness evidence, and a
non-synthetic source.
