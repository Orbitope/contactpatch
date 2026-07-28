# Vehicle Dynamics Co-Design: Research Plan

**Project:** How do optimal racing lines, driving strategy, and mechanical setup change as a function of car design (weight distribution, drive layout, differential, suspension) — and how does adding torque vectoring change all of it?

**Deliverables:** A validated open Python environment for design-conditioned vehicle RL with per-wheel torque authority; comparative findings derived independently via optimal control and reinforcement learning; a learned torque-vectoring controller studied against classical industry architecture; and a series of visual essays/videos built on those findings.

---

## 1. Motivation and Framing

### 1.1 The core question

Industry tunes limited-slip differentials, torque vectoring, and suspension via rule-based controllers (reference bicycle models, yaw-rate error feedback, gain-scheduled maps) calibrated by human engineers across thousands of parameters. The tuning is coupled to driving strategy: a stiff-locking diff is optimal for an aggressive trail-braker and terrible otherwise. This project asks two linked questions industry doesn't publish:

1. **How do the optimal line and optimal setup morph as design parameters sweep** — weight distribution front-to-rear, FWD vs RWD vs AWD, diff parameters, suspension?
2. **What changes when the car gains active yaw authority** — i.e. torque vectoring? How does a learned TV policy compare to the classical two-layer architecture, how does its strategy differ between FWD and RWD, and does TV *flatten* the design sensitivity measured in (1)?

Question 2 is the project's centre of gravity. Question 1 is not a detour to it — it is the **denominator** for every claim in question 2. "TV changes the driving dynamics" is only meaningful against a measured baseline of what the dynamics were without it.

### 1.2 Positioning relative to prior work

Literature review (July 2026) found the technical core partially occupied:

- **Toyota Racing Development, "Towards an Autonomous Test Driver" (arXiv 2412.03803):** trained a single RL agent simultaneously across four vehicle setups (Lexus RC F GT3, proprietary Dymola multibody model wrapped as a Gym env via FMU), evaluated against a professional driver in a motion-base simulator. Closest prior work; validates the multi-setup training architecture. Their motivation matches ours: GT Sophy-style per-car/track training doesn't scale, and hyper-specialized agents behave pathologically (lap time can *worsen* when grip increases).
- **SPARC (AAAI 2026, arXiv 2511.09737):** single policy racing 100 unseen vehicles in Gran Turismo 7 via context-adaptive RL — infers latent vehicle dynamics from interaction history rather than explicit conditioning.
- **Staged GT3 setup optimization (Vehicles, 2026):** 134 setup configs in Assetto Corsa under a fixed AI driver; notes explicitly that the mechanical setup layer is usually left fixed in motorsport AI research.
- **Configurable MDPs (arXiv 1806.05415):** formalizes the design–policy coupling; racetrack example notes a vehicle setting induces an optimal policy and vice versa, and optimal pairs don't transfer across tracks.
- **Classical laptime-driven suspension optimization (Vehicle System Dynamics 2026); 14-DOF 4-IWD optimal design and control (arXiv 1803.09411):** mature non-learning approaches; the latter is the closest prior work on the *TV* side, jointly optimizing 14 design variables including per-axle spring/damper parameters against lap time for a four-in-wheel-drive vehicle.
- **TV control literature generally:** dominated by the two-layer architecture (§1.4) with MPC or sliding-mode upper layers and QP/weighted-pseudo-inverse control allocation below.

**What remains open (our contribution):**
1. The **comparative framing** — nobody visualizes how the optimal line/setup morphs as design parameters sweep continuously.
2. An **open Python environment** where design parameters *and* per-wheel torque authority are first-class (Toyota's is proprietary; SPARC's is a commercial game).
3. **Learned vs hand-designed control allocation** — does an end-to-end RL policy find something the tire-workload cost function doesn't capture, or does it reinvent the allocator? Sharper than "can RL drive fast."
4. **Does TV flatten design sensitivity?** — a difference of two design sweeps, only answerable because we measure both.
5. **Envelope instrumentation as a core loop component** — the tire-exploitation failure mode is documented in the literature but not treated as first-class tooling.
6. The **specialization gap** analysis (P5): how much lap time a single generalist setup sacrifices vs per-track-optimal, as a function of car type.

As novel research this is a modest delta; as a visualization/explainer project with technical spine, it is strong. Presentation is a first-class goal, not an afterthought.

### 1.3 The torque-vectoring capability ladder

Four distinct levels, often conflated under one name. The jump from 2 to 3/4 is the substantive one: levels 1–2 can only *remove* capability from one side (transfer torque toward the slower wheel); levels 3–4 can add yaw moment on demand, making it genuine control authority rather than a limited-slip modifier.

| Level | Mechanism | Authority | In scope |
|---|---|---|---|
| 1. Passive LSD | Mechanical clutch pack; lock is a *function* of input torque and ramp geometry | None (reactive only) | **P1–P3** — the baseline / denominator |
| 2. Active LSD (eLSD) | Same clutch pack, electronically actuated | Commanded lock; still only slows the faster wheel | **P4** — warm-up case |
| 3. True TV | Superposition gearset (AYC, Audi sport diff, Ricardo) — can *overdrive* one wheel | Yaw moment on demand, even off-throttle | **P4** |
| 4. Independent electric drives | Motor per wheel | Arbitrary per-wheel torque, +/-, ms response | **P4** — primary study |

Level 4 is where the field is going (cf. the 4-IWD literature) and where the action space is richest.

### 1.4 The classical TV architecture (baseline to beat, and a hint about action-space design)

Industry near-universally uses a **two-layer split**:

**Upper layer — how much yaw moment do we want?** A reference bicycle model takes steering, speed, and estimated µ and computes a target yaw rate, *clipped* to what the friction estimate says is achievable so the controller doesn't chase an impossible target. Sideslip is constrained in parallel (rotation is wanted; going sideways is not). Output: a single scalar desired corrective yaw moment `Mz`. Implementations range from gain-scheduled PID (still common in production) through sliding-mode (academic favourite for robustness to parameter uncertainty) to MPC (most recent literature and premium production, because it handles actuator and friction constraints explicitly over a short horizon).

**Lower layer — control allocation.** Distribute `Mz` across four wheels, solved every timestep (~1 ms) as a small constrained optimization: minimize weighted **tire workload** — sum of (used force / available force)² per tire, which naturally spreads load and keeps every tire off saturation — subject to total longitudinal force matching driver demand, generated yaw moment matching the `Mz` request, per-wheel actuator limits, and per-wheel friction circle. Weighted pseudo-inverse or QP solves it in real time.

The elegance: the upper layer needn't know the hardware; the lower layer needn't know the driver. Swap an eLSD for four in-wheel motors and only the allocator changes.

Above both sit arbitration with ABS/ESC/TC, driver-mode abstraction, and fault handling (serious for 4-IWD — motor dropout).

**Estimation is the practical bottleneck.** Both layers need sideslip angle and tire–road friction; neither is directly measurable. Sideslip comes from Kalman-variant observers that drift; µ estimation is unreliable and typically only updates once already sliding. Much of the conservatism in production TV traces to distrust of these estimates. *(In simulation we have ground truth — worth noting explicitly as a way our results are optimistic relative to a real car, and a possible ablation: degrade the estimates and see what the policy loses.)*

**This architecture directly structures our P4 experiment** into three comparable variants — see §3, Phase 4.

### 1.5 Key architectural decisions and their justifications

**Double-track (four-wheel) physics from the start.** TV requires individual wheel torques and individual wheel loads; a single-track model cannot express it. Retrofitting four-wheel dynamics later would mean redoing the physics, schema, OC formulation, and every metric — so this is a P0 decision, not a P4 one. Cost: roughly 2–3× the model complexity of a bicycle model and ~1 extra week up front. Benefits beyond TV: per-wheel tire utilization (the flagship visual is better with four tires), lateral load transfer and roll stiffness distribution become real design parameters rather than lumped approximations, and the Chrono mapping in P6 gets substantially cleaner. Still fast Python.

**Design-conditioned policy, not nested optimization.** The naive structure (outer loop proposes design → train RL policy from scratch → evaluate) costs weeks: ~hours per training run × ~200 outer evaluations. Instead: sample a random design vector each episode, append it to the observation, train **one** policy across the randomized design space. Evaluating a candidate design is then a *rollout* (seconds), not a training run (hours). This is a code-structure decision, not a hardware decision — buying GPUs to accelerate the nested loop is accelerating the wrong algorithm.

- Known cost: a generalist policy is slightly worse per-design than a specialist. Mitigation: rankings are what matter and the bias is roughly uniform; fine-tune the top ~10 designs individually and confirm the ordering holds.
- Bonus: the conditioned policy is itself an artifact — action gradients w.r.t. design inputs are computable ("how does exit throttle strategy change per kg of rear weight").

**Optimal control (OC) before and alongside RL.** Direct collocation (CasADi + IPOPT, distance-domain formulation, ~500–2000 collocation points) solves minimum lap time to local optimality on the same model in seconds-to-minutes per design. Three roles:
1. **Ceiling for RL convergence.** RL within ~1% of OC lap time ⇒ trained; 5% off ⇒ every downstream "finding" is suspect.
2. **Independent derivation of trends.** Re-solve OC at each design point (warm-starting from neighbors for continuous sweeps). If OC and RL agree on trend direction, the finding doesn't depend on RL at all — two methods with unrelated failure modes agreeing is worth more than either alone.
3. **Answers "why RL?"** precisely: OC needs deterministic, differentiable dynamics and produces one open-loop trajectory. It cannot do stochastic robustness evaluation, closed-loop/reactive control, feedback controller optimization (active diff, TV), or black-box physics (Chrono). RL earns its place exactly where OC stops.

Honest note: OC alone could deliver the entire passive-design core result (lines vs weight distribution, FWD/RWD) in about a week with no training. The RL layer exists for robustness, active control, the conditioned-policy artifact, and Chrono validation — the parts OC can't express. Note also that on the double-track model the OC problem is heavier than the bicycle version but stays tractable.

**Passive design first; active control as a measured delta.** Diffs are *passive design parameters* (preload, ramp angles) through P3. Rationale for not going active earlier:
1. An active diff / TV controller is a feedback law — OC cannot optimize a controller, so activating it destroys the OC convergence check that anchors P3.
2. An active controller compensates for suboptimal passive setups, flattening the "optimal setup vs corner type" findings — you'd measure "how well RL compensates," not "what the design wants." *(This flattening is itself a target finding in P4 — but only measurable if the unflattened baseline exists first.)*
3. Attribution: with passive diffs, FWD/RWD line differences are cleanly attributable to layout, not to a learned torque-distribution strategy.

**Simple-but-sufficient model; fidelity as validation, not foundation.** Double-track + Pacejka Magic Formula tires + longitudinal and lateral load transfer + roll stiffness distribution, hand-written in NumPy. Not a multibody model. Rationale:
- Fast iteration on reward design is the dominant schedule variable. Each bad reward function costs a full training run; the model must be cheap enough to be wrong five times.
- Every finding is re-derivable in Chrono later at three design points to check trend direction (P6). Trend survival is the claim, not absolute numbers.
- Compute reality: policy is a small MLP; the bottleneck is environment steps, not gradients. NumPy on 16 CPU cores ≈ 100–200k steps/sec aggregate for a bicycle model, call it 50–100k for double-track ⇒ a 10–30M-step PPO run still overnight. A JAX port (batched, branch-free) buys 10–100× on a CUDA GPU and makes training interactive — port only after the physics is validated; debugging tire dynamics through a `vmap` is not a good time. Apple Silicon/MPS is not a viable GPU path for this workload.

**Tire-model envelope instrumentation is core-loop, not polish.** The Pacejka formula is a curve fit valid inside its measured envelope (slip angle, load, combined slip). It fails *silently* outside — returns plausible numbers nobody validated. A reward maximizer will actively seek wherever the model is most optimistic (standard reward hacking in vehicle-dynamics costume): e.g., unphysical grip at 25° slip / 8 kN load produces a beautiful, fictional racing line. Human drivers and hand-tuned controllers never visit those regions, which is why classical workflows don't need this tooling and ours does.
- Every rollout logs min/max/occupancy over slip angle, slip ratio, vertical load, **per wheel**.
- Lap times achieved outside the validated envelope are **discarded**, not celebrated — they measure model error, not car behavior (the arithmetic checks out; the physics doesn't; it won't transfer).
- Soft penalties / clamps at the envelope boundary as needed.
- Envelope occupancy is also *published* per setup — it doubles as the credibility argument.
- **TV raises this risk sharply.** Four independent torques give the policy far more ways to reach weird states — notably high slip ratio *and* high slip angle simultaneously on one tire, precisely where combined-slip models are least validated. Envelope discipline is tighter in P4, not looser.

---

## 2. Design Vector and Scope

Initial design vector (subject to refinement in P0):

| Parameter | Range (initial) | Notes |
|---|---|---|
| Weight distribution (front fraction) | 0.35 – 0.65 | CoM longitudinal position — the dominant effect of engine placement |
| **Yaw inertia (I_zz)** | ~0.7× – 1.4× nominal | **Polar moment about the vertical axis — the parameter that separates engine layouts once weight distribution is controlled for.** See §2.1 |
| Drive layout | {FWD, RWD, AWD} | One-hot in observation. AWD in scope once TV is (P4) |
| CoM height | TBD | Drives load transfer magnitude |
| Front / rear spring rate | TBD | Real per-corner rates on double-track |
| ARB stiffness front / rear | TBD | **Roll stiffness distribution** — a first-class handling-balance parameter on double-track, unlike the lumped bicycle version |
| Diff preload | TBD | Passive LSD (P1–P3) |
| Diff ramp angles (power / coast) | TBD | Passive LSD (P1–P3) |
| Front/rear torque split (AWD) | TBD | P4 only |
| Per-axle motor torque limits | TBD | P4 only; replaces diff params in the electric-TV study |
| Track width | Fixed initially | Sets the TV moment arm; revisit if TV results are moment-arm-limited |

Notes:
- Damper rates deferred until the model's transient load-transfer dynamics are worth exciting (revisit in P0).
- The design vector's *meaning shifts* between the passive study and the electric-TV study: preload and ramp angles stop existing as parameters when there is no clutch pack. Handle by keeping two named design-space presets sharing one schema, with unused slots masked and documented — not by forking the vector definition.

### 2.1 Engine layout as a region of the design space, not a category

Front / mid / rear engine placement is **not a separate parameter** — it is a *combination* of two parameters already in the vector:

1. **CoM longitudinal position** (weight distribution), and
2. **Yaw inertia I_zz** (polar moment), which is the physically distinct effect and the reason layout deserves attention at all.

Two cars can share an identical 40/60 balance and behave completely differently in rotation:

- **Mid-engine** — masses clustered near the CoM ⇒ **low** I_zz. Rotates eagerly, changes direction quickly, but is twitchy near the limit and less forgiving once sliding.
- **Front- or rear-engine** — mass concentrated far from the CoM ⇒ **high** I_zz. Slower to initiate rotation, more stable and more predictable once rotating.

("Dumbbell vs. barbell.") The double-track model already uses I_zz; it was previously fixed. Making it a swept parameter costs one scalar in the design vector and one line in the model.

**Why treating layout as a region rather than a category is better:** it gives the *continuum* — the full 2D surface over (weight distribution × yaw inertia) — and then places real layouts on it as annotated markers rather than as three isolated cases. Approximate archetype markers to overlay on every relevant sweep plot:

| Archetype | Front fraction (approx) | I_zz (approx) | Drive |
|---|---|---|---|
| Front-engine FWD | 0.60 – 0.65 | High | FWD |
| Front-engine RWD | 0.50 – 0.55 | High | RWD |
| Mid-engine | 0.40 – 0.45 | **Low** | RWD |
| Rear-engine | 0.35 – 0.40 | High | RWD |

Note the archetypes are not collinear: front-engine RWD and rear-engine sit at opposite ends of the weight-distribution axis but *both* have high yaw inertia, while mid-engine is distinguished almost entirely by the inertia axis. That non-collinearity is exactly what makes the 2D sweep informative and a 1D weight-distribution sweep misleading.

**Presentational discipline:** sweep I_zz and weight distribution semi-independently so readers don't conflate them, present the 2D surface first, and only then annotate where real cars sit. The clean two-car comparison — *same balance, different yaw inertia* — is the confound-separating experiment this architecture exists to run and is rarely visualized anywhere.

**Measurement:** no new machinery required. Yaw inertia effects appear directly in the transient metrics already specified in P0/P3 — step-steer yaw-rate rise time and overshoot, turn-in behavior, sine-with-dwell response.

---

## 3. Phases

### Phase 0 — Physics core, schema, validation harness

**Goal:** A trusted, fast, instrumented double-track simulator behind a backend-agnostic interface, with per-wheel torque authority present in the interface from day one (even though P1–P3 constrain it).

**Build:**
1. **Double-track model**: four wheels, per-wheel normal load from static distribution + longitudinal load transfer + lateral load transfer split by roll stiffness distribution; Pacejka pure-slip lateral and longitudinal with a combined-slip weighting per wheel; per-wheel slip angle and slip ratio; wheel rotational dynamics; simple aero drag; Ackermann steering geometry.
2. **Torque interface**: the drivetrain layer accepts a per-wheel torque vector. Modes:
   - `passive_lsd` — per-wheel torques *derived* from a mechanical diff model (preload + ramp bias) given a single driver demand. Used P1–P3.
   - `active_lsd` — commanded lock, still constrained to transfer toward the slower wheel. P4.
   - `tv_free` — arbitrary per-wheel torques within actuator limits. P4.
   Same physics; the mode is a constraint on the torque vector, not a separate codebase. This is what makes the passive study cheap to keep.
3. **Versioned observation/action schema** in a single module, with explicit units, sign conventions, and normalization constants. Both backends, the OC formulation, and all analysis code import it. Observation: vehicle state (speed, yaw rate, sideslip, roll proxy, per-wheel slip/load, …), **track lookahead** (curvature/width over next ~100 m — ego-relative, no absolute position, which is what makes multi-track free later), **design vector**. Action: steering, brake, and a drivetrain command whose dimensionality is mode-dependent (scalar demand / demand+lock / demand+Mz / four torques) — declared in the schema per mode.
4. **Backend interface**: `reset()`, `step(action)`, `set_design(vec)`, `set_mode(mode)`, `get_obs()`. RL code never touches a simulator directly. NumPy backend implements it now; Chrono implements it in P6.
5. **Track representation + minimal generator**: centerline as arc-length-parameterized curvature profile + width. One hand-built test track; generator kept simple until P5.
6. **Validation maneuvers** (no RL): constant-radius skidpad with slow speed ramp → understeer gradient (slope of δ vs a_y minus Ackermann) and max lateral g; step steer → yaw-rate rise time and overshoot; slow steering ramp; **sine-with-dwell** and **µ-split acceleration** (the classic TV showcase maneuvers, included now so P4 has an established reference). Compare against published figures for a comparable car class. These same maneuvers are the model-agreement check reused verbatim in P6.
7. **Envelope logging** wired into the step loop from day one, per wheel.
8. **Logging schema**: per-timestep arc length, lateral offset, speed, steering, brake, per-wheel torque, yaw rate, sideslip, per-wheel slip angle / slip ratio / normal load / used-force fraction, dumped identically by every backend. **All metrics computed downstream from these arrays by shared code, never inside the sim loop** — metric definitions will be revised repeatedly and must not require re-running simulations.

**Exit criteria:** validation maneuvers produce physically plausible, published-comparable numbers; roll stiffness distribution demonstrably shifts handling balance in the expected direction; yaw inertia demonstrably changes step-steer rise time at fixed weight distribution; a hand-scripted open-loop lap completes in all three drivetrain modes; envelope logs populate per wheel.

---

### Phase 1 — Optimal control baseline and core passive findings

**Goal:** The central comparative results, derived without any learning. This is the **denominator** for everything in P4.

**Build:**
1. Distance-domain minimum-lap-time formulation in CasADi: state/control trajectories at collocation points, dynamics as equality constraints, track-edge and actuator/friction inequality constraints, IPOPT as solver. Drivetrain fixed to `passive_lsd`.
2. Design sweep driver: re-solve per design point; warm-start each solve from the neighboring design's solution for continuous sweeps (faster and smoother than RL's equivalent).
3. **Corner-parameterized studies**: track design is otherwise an uncontrolled variable (hairpin circuits reward different setups than sweeper circuits — the Configurable MDP point). Parameterize corners (radius, entry speed, camber) and run design sweeps per corner type. "Optimal preload as a function of corner radius" decomposes the finding and is arguably more interesting than lap time.

**Findings targeted:**
- Racing line (apex location, brake point, throttle application) vs weight distribution, per corner type.
- FWD vs RWD line and control differences on identical corners.
- Effect of roll stiffness distribution on balance and line — now a real parameter thanks to double-track.
- **Yaw inertia at matched weight distribution** — the confound-separated layout comparison (§2.1). Expected signature: low-I_zz cars carry a different entry line (earlier, sharper rotation) and are more sensitive to brake-point precision; high-I_zz cars need earlier turn-in but tolerate more error. 2D surface over (front fraction × I_zz) with archetype markers overlaid.
- Lap-time surfaces over 2D design slices (e.g., weight dist × preload) — valleys, ridges, discontinuities are findings.
- **Design-sensitivity curves** — how much lap time varies across each design axis. These are the specific curves P4 tests for flattening.

**Exit criteria:** OC sweep results reproduce known qualitative vehicle-dynamics behavior (e.g., rearward weight → later apex under power, FWD exit-understeer signature, stiffer front ARB → more understeer); envelope check confirms OC solutions live inside the tire fit's validity region (OC will ride the friction limit — verify the limit itself is inside the envelope).

---

### Phase 2 — Design-conditioned RL, passive drivetrain

**Goal:** A trained conditioned policy whose per-design performance is validated against OC. Establishes that the pipeline produces trustworthy answers before any un-calibratable control work begins.

**Build:**
1. PPO (or SAC — decide empirically) over the P0 environment in `passive_lsd` mode; design vector randomized per episode within the ranges of §2; small MLP policy.
2. Parallel envs via subprocess vectorization; 16+ CPU cores; target 10–30M steps overnight. JAX port is an *optional* later acceleration, gated on validated physics.
3. Reward: primarily progress-along-track per step with track-limit termination; expect ~5 iterations of shaping — this is the budgeted schedule risk, which is why the sim must be fast. Start deliberately small (reduced design ranges, single corner, short episodes) to validate the pipeline end-to-end before scaling.
4. Seed discipline from the start: ≥3 seeds per experimental configuration; any design-space trend smaller than seed spread is noise.
5. Evaluation harness: freeze weights, pin design vector, deterministic rollouts; 500-design evaluation in ~minutes; CMA-ES over the design vector using rollout lap time as objective; fine-tune top ~10 designs to confirm ranking stability.

**Cross-validation vs OC (the actual point of this phase):**
- **Convergence check:** RL lap time within ~1% of OC per design. Expect RL to trail slightly — OC is open-loop and rides the friction limit exactly; a small gap is normal, not failure.
- **Trend check:** rank agreement (Spearman across design points) and trend *direction* per metric. Values are not expected to match; shapes are.

**Exit criteria:** convergence check passes across the design space; RL and OC agree on the P1 trend directions. **The passive optimum per layout is recorded and locked here** — it is the baseline against which every P4 result is measured.

---

### Phase 3 — Measurement, robustness, and visualization framework

**Goal:** Make the findings interpretable; produce the artifacts the essays/videos are built from. Built before P4 so that TV results land in a finished measurement framework rather than driving ad-hoc analysis.

**Metric definitions (computed from the shared logging schema):**
- **Apex location**: point of minimum distance to inside edge within a corner window, as *fraction of corner arc length* (0.5 = geometric mid-corner). Companion metric: minimum-speed point as arc-length fraction (less sensitive to lateral position noise).
- **Brake point**: arc distance where brake first exceeds 10%, relative to turn-in, normalized by corner length. **Throttle application**: first sustained exceedance of 50% on exit, same normalization.
- **Per-wheel tire utilization maps**: fraction of friction circle used by each of the four tires, along the lap. *The flagship visual* — directly shows which tire is the binding constraint and where, i.e. *why* FWD and RWD want different lines, and later exactly what TV is buying. Build the pipeline around producing this well.
- **Tire workload metric**: Σ (used/available)² across wheels — the same objective classical control allocation minimizes. Computing it for *every* policy (passive, classical TV, learned TV) makes the P4 comparison directly interpretable in the allocator's own currency.
- **Yaw moment decomposition**: split yaw acceleration into contributions from steering/lateral forces, drivetrain torque asymmetry, and lateral load transfer, per timestep. Shows what the diff or TV system is actually *doing* through a corner — rarely visualized anywhere.
- **Policy design-sensitivity** (RL-only, novel artifact): gradients of policy actions w.r.t. design inputs of the conditioned network.
- **Envelope occupancy** per setup, per wheel, published.

**Robustness / drivability (RL-only — OC cannot do this):**
- Lap time alone rewards knife-edge setups; real engineering optimizes lap time subject to drivability, which is exactly the subjective-driver-rating component classical calibration can't automate and we can proxy.
- Proxy: inject perturbations (steering noise, µ variation, and — for P4 — sensor noise on sideslip/µ estimates) into evaluation rollouts; record lap-time variance and spin/track-limit-violation rate per design.
- Output: **lap time vs robustness Pareto front** per car class. Expected headline: "the fastest setup is also the most fragile" — legible to anyone who has tuned a racing-game setup. P4 then asks where TV moves each point on that front.

**Trend-comparison presentation standard** (used again in P4 and P6): normalize each metric within its own method/simulator (z-score across design points), overlay the curves. Parallel lines ⇒ the finding transfers regardless of absolute offsets. Require effect size > ~2× seed spread before calling any trend real; report mean ± std everywhere.

**Exit criteria:** metric pipeline runs end-to-end from logs; Pareto front computed for passive designs; per-wheel tire utilization visual at publication quality.

---

### Phase 4 — Torque vectoring: the core study

**Goal:** Understand, measure, and explain what active yaw authority does — to lap time, to the racing line, to design sensitivity, and how a learned controller compares to the architecture industry actually builds. This phase is the project's centre of gravity and the primary personal/pedagogical interest.

**4a. Warm-up: active LSD.** Take the locked passive optimum per layout (P2). Switch to `active_lsd`; add one action dimension (commanded lock); fine-tune from passive weights. Cheap (~1 day of code + a few runs) and it isolates the *commanded vs reactive* variable before adding the *per-wheel authority* variable. Deliverable: the learned lock command profile against corner phase, yaw-rate error, and throttle state. Expected pedagogical payoff — the policy should rediscover the logic engineers hand-code (open on entry to avoid locking-induced understeer, progressive lock on power application, stabilizing lock under trailing throttle) — and seeing that emerge from lap-time pressure alone rather than from rules is the story.

**4b. The three-way comparison (core experiment).** Same car, same track, same design point; three ways of generating yaw moment:

| Variant | Upper layer | Lower layer | Purpose |
|---|---|---|---|
| **C — Classical** | Reference bicycle model + PID/MPC → `Mz` | QP control allocation minimizing tire workload | The baseline RL must beat to be interesting; industry-representative |
| **H — Hybrid** | RL policy outputs `Mz` demand | Same QP allocator | Small action space, easy exploration, **highly interpretable** — plot learned `Mz` against corner phase and compare directly to C's |
| **E — End-to-end** | RL policy outputs four wheel torques directly | none | Biggest search space; tests whether learning finds something the workload cost function misses, or merely reinvents the allocator |

The research question — **does learning beat hand-designed allocation, and if so where?** — is sharper than "can RL drive fast," and this architecture is unusually well suited to answer it. Analyze divergence per corner phase and in tire-workload currency: if E beats H, inspect whether E's allocation deviates from minimum-workload and in which direction (e.g. deliberately overloading one tire to buy rotation).

Exploration note: E's four-dimensional continuous allocation with a lap-time reward is a much larger search than C or H. If E fails to train, that is itself a reportable result about action-space structure — but attempt mitigations first (action parameterization as total demand + distribution, curriculum from H's solution, initializing E from H+allocator behavior via a short imitation phase).

**4c. How TV changes the driving.** Compare line, brake point, throttle timing, and apex fraction of the TV policies against the passive optimum on the same car. Hypotheses to test:
- TV permits earlier throttle and a tighter exit line — the diff changes optimal *strategy*, not just grip.
- With direct yaw control the car can rotate without steering input, decoupling steering from rotation; expect the line to change more dramatically than anything an LSD does.
- Combined slip becomes the whole game: optimal TV continuously trades longitudinal against lateral per tire against the friction circle. The tire utilization map becomes the *explanation* of the policy, not just a diagnostic.

**4d-i. Does TV compensate for layout?** Yaw inertia determines how much moment is needed to rotate the car, so TV is directly substituting for agility the layout doesn't have. **Hypothesis: high-I_zz cars (front- and rear-engine) benefit more from TV than low-I_zz mid-engine cars** — i.e. TV compresses the difference between layouts, not just between weight distributions. Test by measuring the TV-vs-passive lap-time and line delta across the (front fraction × I_zz) surface from P1, with archetype markers. This is a second, sharper instance of the P4e flattening question: if it holds, the claim generalizes from "setup matters less" to "*layout* matters less," which is a stronger and more surprising statement about where electric drivetrains are taking vehicle design.

Watch the confound: low-I_zz cars are already fast to rotate, so a smaller TV gain there could reflect a ceiling effect rather than a layout interaction. Control by also reporting the *absolute* rotation performance (peak yaw rate, time-to-target-heading) alongside the delta, and by checking whether the TV command magnitude itself scales with I_zz as predicted.

**4d-ii. FWD vs RWD vs AWD strategy.** The same controller problem has opposite failure modes across layouts: RWD vectoring manages power oversteer and corner-entry rotation; FWD vectoring fights power understeer and torque steer on exit — and vectors the same tires that steer, which is genuinely non-obvious. AWD adds front/rear split as an additional design axis. Overlay learned command profiles on identical corners. Rarely shown anywhere and falls directly out of the architecture.

**4e. Does TV flatten design sensitivity?** Re-run the P1/P2 design sweeps with TV active and compare the design-sensitivity curves against the passive baselines — across weight distribution, roll stiffness distribution, and yaw inertia (the layout axis, per 4d-i). Candidate headline: *"electric torque vectoring makes mechanical setup matter less"* — directly connecting the design sweep to the industry trajectory toward per-wheel electric drives. This is a difference of two sweeps and is only answerable because P1–P2 measured the denominator.

**4f. Estimation ablation (optional, cheap, honest).** Simulation gives ground-truth sideslip and µ that a real car cannot measure. Degrade them (noise, lag, drift) and re-evaluate C, H, and E. Tests whether the learned policies' advantage survives realistic sensing, and explains why production TV is conservative.

**Methodological guards:**
- Passive results are locked before this phase begins; TV policies train against the passive *optimum*, so any gain is attributable to control, not setup slack.
- Matched training budgets across H and E (and matched fine-tune budgets against passive) so deltas aren't just extra training.
- Same seed and effect-size rules as everywhere.
- Envelope discipline tightened per §1.5 — TV is the highest tire-exploitation risk in the project.
- **OC substitute:** no OC baseline exists for a feedback law. Partial substitute: OC with per-wheel torques as additional open-loop control trajectories gives an upper bound for a *clairvoyant* TV system on a deterministic lap. Learned closed-loop policies should land between the passive optimum and that bound; landing above the bound indicates a bug or envelope violation, which makes this a useful automatic check rather than just a reference number.

**Exit criteria:** C, H, and E all complete laps at the reference design point with ≥3 seeds each; the three-way comparison table (lap time, tire workload, robustness) is populated; learned `Mz` profiles extracted and overlaid against classical; design-sensitivity flattening measured or ruled out with effect sizes.

---

### Phase 5 — Multi-track training and the specialization gap

**Goal:** Best characteristics *in general* for a given car; cost of running one setup everywhere.

**Why it's cheap:** the P0 observation is ego-relative lookahead — the policy never knew which track it was on. Extension: procedural track generator (tracks are curvature profiles; splice corners of varying radius/length and straights), sample a track per episode alongside the design.

**Build:**
1. Procedural generator with controllable feature distribution (mean curvature, corner density, straight fraction).
2. Joint design × track conditioned training. Expect 2–3× the P2 training steps and higher variance; curriculum from modest track variety outward. Verify generator distribution covers the evaluation set.
3. **Fixed evaluation track set** (same ~20 tracks for every design) — paired comparison removes most track-sampling variance from design comparisons.
4. OC counterpart: solve per design per track, average — same baseline logic.

**Findings targeted:**
- **Specialization gap**: per design, (per-track-optimal lap times) − (generalist design's lap times) = the setup-compromise cost. How it varies by car type is the headline (hypotheses: FWD less setup-sensitive than RWD; preload matters more on tight tracks).
- Optimal design vector as a function of track-feature space (e.g., optimal weight distribution vs mean corner radius).
- **TV × track interaction**: does TV shrink the specialization gap? If TV flattens design sensitivity (P4e), it should also reduce the cost of running one setup everywhere — a second, independent test of the same underlying claim.

**Exit criteria:** generalist policy laps the held-out evaluation set; specialization-gap chart with seed-spread error bars, passive and TV.

**Scoping note:** P5 and P6 are independent; either can be cut without harming the other.

---

### Phase 6 — Chrono validation

**Goal:** Test whether the findings are claims about cars or claims about our double-track model. Trend *survival* is the result; trend *inversion* is also a result (it names which discarded mechanisms — real suspension kinematics, compliance, transient damper behavior — carry the effect).

**Scope discipline:** a *reduced* study, not a second project. Three design points at the extremes and middle of the headline sweep, one or two corner types, ≥3 seeds each, passive drivetrain plus one TV variant. ~2–3M steps total, ≈ half an hour at ~1,600 aggregate steps/sec.

**Build:**
1. **Chrono backend** implementing the P0 interface. Python bindings; subclass `ChDriver`, override `Synchronize()` for steering/throttle/brake. ONNX/TorchScript export of the policy; ONNX Runtime C++ path available if Python loop overhead matters.
2. **Observation adapter**: reduce Chrono's multibody state to the exact schema vector — same units, same sign conventions, same normalization. *Sign conventions on yaw rate and slip angle are the classic silent failure: everything runs, the car drives into a wall.* **Note this is materially easier than it would have been from a bicycle model:** our observation is already per-wheel, so Chrono's four-tire state maps across directly rather than needing an axle-aggregation convention invented for the occasion. This is a second dividend of the P0 double-track decision.
3. **Action adapter**: normalized steering through Chrono's steering rack ratio / Ackermann; per-wheel torque commands into Chrono's driveline.
4. **Design mapping**: abstract parameters → concrete Chrono elements (spring rates → `ChLinkTSDA`; weight distribution → CoM/mass; ARB → antiroll subsystem; diff parameters → Chrono differential model, documented where the mapping is loose).
5. **Speed configuration**: N parallel single-threaded instances (the dominant lever — Chrono's multicore/GPU modules target granular/DEM, not vehicle multibody); headless (no Irrlicht/VSG) except the one recorded rollout; test timestep 5e-4 vs 1e-4 against validation maneuvers; control at 100 Hz with zero-order hold over physics substeps; cheapest tire model that responds to the swept parameters (Pacejka/MF or Fiala, not FEA/rigid-ring); rigid flat terrain.

**Validation sequence (in order, each gating the next):**
1. **Model agreement, no RL** (an afternoon, run first): identical open-loop inputs (steering ramp, step steer, constant throttle, µ-split) through both backends; overlay yaw rate and lateral acceleration — agreement in sign, rough magnitude, timing. Then the P0 steady-state maneuvers: understeer gradient within ~10–15%, max lateral g within a few percent. If the models disagree on basic handling character, no policy comparison downstream means anything.
2. **Zero-shot sanity check**: the pretrained policy is *expected* to lap slowly and badly (dynamics gap: real suspension kinematics, compliance, transient damping). Slow-and-bad ⇒ adapters correct. Can't hold the track ⇒ interface bug, not dynamics gap — fix before proceeding.
3. **Fine-tune per design point** from the pretrained conditioned policy (same architecture/observation space, lower LR, far fewer steps than scratch — this is what makes the half-hour budget real, and the reason the schema was frozen in P0).
4. **Trend comparison**: absolute lap times are never comparable across simulators. Compare rank ordering, trend sign (Spearman across the three points — weak with n=3, so lean on effect size: change across the range > 2× seed spread), and qualitative line signatures (apex fraction, brake point) via the P3 z-score overlay. Watch the convergence confound: an undertrained design point reads as a physics finding — seed-spread reporting is the defense.

**Exit criteria:** model-agreement checks pass; per-design fine-tunes converge (stable lap times across seeds); z-score overlay produced; verdict written either way.

**Caveat:** Chrono is a better model, not a true one. It has its own tire fit with its own envelope; slip instrumentation matters just as much there. Higher fidelity narrows the gap to reality; only a real car closes it.

**Explicitly rejected alternative:** BeamNG. Soft-body simulation is heavier per step and its value (crash/deformation/rough terrain) is orthogonal to this project; Chrono offers validated suspension kinematics with an inspectable tire model and source access. If Chrono proves painful, the fallback is accepting the double-track model as final and reporting the limitation — not a heavier engine.

---

## 4. Publication Plan

One visual essay / video per question, each with a concrete question, a visual answer, and a payoff:

1. **How racing lines differ FWD vs RWD** — per-wheel tire utilization maps as centerpiece; which tire is the binding constraint, and where. (Material complete after P3.)
2. **What a differential actually does** — yaw moment decomposition on passive diffs, building to the learned active-LSD command profiles: the policy rediscovering the entry-open/exit-lock logic engineers hand-code. (P4a.)
3. **Torque vectoring: what engineers designed vs what the machine found** — the flagship piece. The classical two-layer architecture explained, then the learned `Mz` profile overlaid on it, then the end-to-end policy's allocation compared against minimum-tire-workload. Clean pedagogical arc: here is what engineers designed, here is what the machine found, here is where they differ and why. (P4b.)
4. **Front, mid, or rear engine — what actually changes?** The (weight distribution × yaw inertia) surface with layout archetypes marked; the same-balance/different-inertia comparison; why mid-engine feels different from a 40/60 front-engine car despite similar numbers. Then: does TV erase the difference? (P1 + P4d-i.)
5. **How TV changes the driving** — line, brake point, throttle timing vs the passive baseline; rotation without steering; FWD vs RWD vs AWD strategy inversion. (P4c, P4d-ii.)
6. **Does TV make setup matter less?** — design-sensitivity flattening, tied to the industry shift toward per-wheel electric drives. (P4e, reinforced by P5.)
7. **The setup Pareto front** — speed vs fragility, and where TV moves each point. (P3 + P4.)
8. **Did it survive a real physics engine** — the P6 z-score overlay. (P6.)

Essays 3–6 are the personal-priority pieces: the TV work exists as much for understanding-and-explaining how these controllers work as for the lap-time results.

---

## 5. Compute Plan

| Stage | Hardware | Wall clock |
|---|---|---|
| P0–P1 (physics, OC) | Laptop/desktop CPU | Solves in seconds–minutes each; OC heavier on double-track but tractable |
| P2 training run | 16-core desktop CPU, NumPy | ~6–12 h (overnight) per run |
| P2 500-design evaluation | Same | ~1–2 min |
| P4 training runs (C/H/E × layouts) | Same | Several overnights; E is the expensive one |
| Optional JAX port (post-validation) | CUDA GPU (rented A100 hours if needed) | Training 10–30 min |
| P5 training | Same as P2, ×2–3 | 1–2 overnights per run |
| P6 Chrono | 16 parallel instances | ~30 min for the full reduced study |

Notes: double-track roughly halves step throughput vs a bicycle model — absorbed, not fatal. No hardware purchase is justified by this project alone; the JAX port is what makes cloud GPU hours worth it, decided only if iteration speed is actually the bottleneck after P2. The dominant schedule risks are (1) tire-physics debugging and (2) reward-shaping iterations — neither is GPU-addressable; both are addressed by keeping the model fast and the pipeline small until trusted.

## 6. Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Tire-model exploitation (reward hacking) | High | Envelope logging core-loop, per wheel; discard out-of-envelope results; boundary penalties; tightened in P4 |
| Reward shaping iterations eat schedule | High | Fast sim; start on single corner; OC baseline defines target behavior |
| Physics bugs (sign conventions, load transfer, roll distribution) | High | P0 validation maneuvers; open-loop backend comparison in P6 |
| Double-track P0 overruns the extra week | Medium | Build passive-mode physics first and validate; TV modes are constraint changes on an existing torque interface, not new physics |
| End-to-end TV (variant E) fails to train | Medium | Action reparameterization; curriculum from H; imitation warm-start; failure is itself reportable |
| TV gain confounded with extra training | Medium | Matched training budgets across C/H/E and against passive |
| Generalist-policy bias scrambles rankings | Medium | Fine-tune top-10 confirmation |
| Trend < seed variance (no result) | Medium | ≥3 seeds everywhere; effect-size > 2× spread rule; paired track sets in P5 |
| Chrono design mapping too loose (esp. diff/TV driveline) | Medium | Document mapping; validate maneuvers per design point; accept qualitative-only comparison for loose parameters |
| P5 training instability (design × track) | Medium | Curriculum; P5 independent of P6, cuttable |
| Yaw-inertia effect confounded with weight distribution in presentation | Medium | Sweep semi-independently; present 2D surface before archetype markers; report absolute rotation metrics alongside deltas |
| Scope creep | High (base rate) | TV scoped to the three named variants at one reference design point before any breadth; BeamNG rejected; P6 capped at 3 design points; estimation ablation (4f) explicitly optional |

## 7. Sequencing Summary

```
P0 double-track physics + schema + validation
        │
        ▼
P1 OC baseline + passive design sensitivity  ◄── first publishable checkpoint (OC-only findings)
        │
        ▼
P2 conditioned RL (passive) + OC cross-validation ──► passive optimum LOCKED
        │
        ▼
P3 metrics / robustness / visualization framework  ◄── essays 1–2 complete
        │
        ▼
P4 TORQUE VECTORING (core study)
   4a active LSD warm-up
   4b classical vs hybrid vs end-to-end
   4c how TV changes the driving
   4d-i does TV compensate for engine layout (yaw inertia)?
   4d-ii FWD / RWD / AWD strategy
   4e design-sensitivity flattening
   4f estimation ablation (optional)
        │                              ◄── essays 3–6
   ┌────┴────┐
   ▼         ▼
P5 multi-  P6 Chrono
  track     validation
(independent, either cuttable) ──► essay 7 / final synthesis
```

P1 is the first publishable checkpoint on its own. P3 completes essays 1–2 and the measurement framework. P4 is the core study and the reason for the project. P5 and P6 are parallel, independent, individually cuttable extensions.
