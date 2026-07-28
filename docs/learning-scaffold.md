# Learning & Publication Scaffold

**Two jobs, one artifact.** This document is how you teach yourself the vehicle dynamics as the project runs, *and* the incremental draft of the published essays. Filling it in is not overhead on the research — it is how you check that you understand what the code is doing.

**The core device: predict before you run.**

Each module below has a **Prediction** section written *before* the corresponding phase executes, and a **Reality** section filled in after. This ordering is deliberate:

- If you can state what should happen before running it, you understand the concept.
- Your prediction is simultaneously a test assertion — it feeds directly into D1–D5.
- When prediction and reality diverge, you have learned something *or* found a bug, and separating those two is itself the skill this project is teaching you.
- Writing explanations *after* seeing results mostly produces fluent text that conceals the gaps it should reveal.

**Rule:** never write the Reality section without having written the Prediction first. If you skipped it, write the prediction from memory before looking at the output — it is still worth something.

---

## The three orderings

These are not the same sequence, and mixing them up is why documents like this usually collapse.

| Ordering | Driven by | Shape |
|---|---|---|
| **Learning** | Concept dependencies | Front-loaded. You need load sensitivity before you can debug tire code, and you need load transfer before understeer means anything |
| **Research** | Build dependencies + validation gates | P0 → P1 → P2 → P3 → P4 → P5/P6 |
| **Publication** | Audience curiosity | Hook first, mechanism second, result third. Often the *reverse* of the learning order |

The modules below follow the **learning** order and note where each lands in the other two.

---

## Concept dependency map

```
        ┌─ M1 Tire slip ─────────────┐
        │                            ▼
        │                    M3 Load sensitivity ──┐
        ├─ M2 Friction circle ────────┘            │
        │                                          ▼
        └─────────────────► M4 Load transfer ──► M5 Understeer/oversteer
                                                   │
                                    M6 Yaw inertia ┤
                                                   ▼
                                          M7 The racing line
                                                   │
                     ┌─────────────────────────────┤
                     ▼                             ▼
            M8 Optimal control            M9 RL & reward hacking
                     │                             │
                     └──────────┬──────────────────┘
                                ▼
                        M10 Differentials
                                ▼
                     M11 Yaw moment generation
                                ▼
                  M12 Two-layer TV architecture
                                ▼
                    M13 Control allocation
                                ▼
              M14 Generalization & validation
```

M3 is the keystone. Almost everything interesting in this project — why weight transfer matters, why setup matters, why TV helps — traces back to peak μ falling with load. If only one module is understood deeply, make it that one.

---

# Part 1 — Foundation modules (before/during P0)

## M1 · Why a tire makes force at all

**Concept.** A tire generates lateral force because it is pointed slightly away from its direction of travel — the *slip angle*. Not a failure mode; it is the mechanism. Force rises roughly linearly with slip angle, peaks around 6–10°, then falls off as the contact patch slides. Same story longitudinally with *slip ratio*.

**Why you need it.** Every force in the simulation comes from here. Slip angle sign conventions are the single most common silent bug.

**Prediction (write before P0 runs):**
- At what slip angle do you expect peak lateral force for our tire? _____
- What happens to lateral force at 25° slip — higher, lower, or about the same as peak? _____
- If a tire is pointed exactly where it is travelling, how much lateral force? _____

**Reality:** _[fill after D1 runs]_

**Understanding check:** Explain to yourself why a car can be sliding and still turning. If that feels contradictory, M1 is not solid yet.

**Diagram slot:** D1 panel A (tire curve family). **Research phase:** P0. **Publication:** background for essay 1.

---

## M2 · The friction circle and combined slip

**Concept.** A tire has a total force budget. Spend it laterally, longitudinally, or split — but the vector sum is bounded. Braking hard leaves little grip for cornering. This is why trail-braking is a *tradeoff* rather than free speed.

**Why you need it.** This is the entire reason torque vectoring works and the entire reason it has limits. TV adds longitudinal force to a tire that is already cornering, which eats lateral capacity.

**Prediction:**
- If a tire is at 100% of its lateral limit and you add braking, what happens to cornering force? _____
- Where in a corner do you expect each tire to be closest to its friction limit? _____

**Reality:** _[fill after first tire-utilisation plot]_

**Understanding check:** Why does adding drive torque to the outside rear wheel help rotate the car but also cost that tire lateral grip? Both are true simultaneously.

**Diagram slot:** 06 (friction circles), 01 (tire utilisation). **Research phase:** P0/P3. **Publication:** essay 1 core mechanism.

---

## M3 · Load sensitivity — the keystone

**Concept.** Peak μ **falls** as vertical load rises. Our tire: μ ≈ 1.14 at 1 kN, ≈ 0.79 at 9 kN. So two tires sharing 6 kN evenly make *more* total grip than one at 5 kN and one at 1 kN.

**Why this is the keystone.** It is the reason weight transfer costs grip. It is the reason a low CoM is good. It is the reason roll stiffness distribution changes balance. It is the reason spreading tire workload (what control allocation minimizes) is the right objective. Remove load sensitivity and most of this project's subject matter evaporates.

**Prediction:**
- Two tires, 3 kN each, vs. 5 kN + 1 kN. Which pair makes more total lateral force? By roughly what fraction? _____
- Does a car with a higher CoM have more or less total grip in a corner? Why? _____
- Predict the sign of dμ/dFz: _____

**Reality:** _[fill after D1 panel B]_

**Understanding check:** Explain why stiffening the front anti-roll bar makes a car understeer more, using only load sensitivity. If you can do that, M3 and M4 are both solid.

**Diagram slot:** D1 panel B (peak μ vs load). **Research phase:** P0. **Publication:** essay 1 — this is the concept most readers will not have.

---

## M4 · Load transfer

**Concept.** Braking moves load forward, accelerating moves it rearward, cornering moves it outward. Magnitude scales with CoM height and acceleration, and inversely with wheelbase (longitudinal) or track width (lateral). How lateral transfer *splits* front-to-rear is set by roll stiffness distribution — which is what anti-roll bars actually control.

**Why you need it.** Combined with M3, it explains handling balance entirely.

**Prediction:**
- Our car: 1360 kg, CoM 0.460 m, track 1.50 m. At 1.0 g lateral, roughly how much load shifts to the outside? _____ (Answer: `m·a·h/t` ≈ 1360 × 9.81 × 0.460 / 1.50 ≈ 4.1 kN total)
- If CoM height doubled, what happens to that number? _____
- Sum of all four normal loads during hard braking: more than, less than, or equal to `mg`? _____

**Reality:** _[fill after D5]_

**Understanding check:** Predict which wheel is most loaded at corner entry under trail braking, and which is least. Then check against the glyph visual.

**Diagram slot:** D5 (load transfer audit), 05 (wheel-load glyphs). **Research phase:** P0. **Publication:** essay 1.

---

## M5 · Understeer and oversteer, properly defined

**Concept.** Understeer gradient `K` (deg/g) is how much *extra* steering beyond the geometric Ackermann angle you need as lateral acceleration rises. Positive = understeer. It is a measured, steady-state property, not a feeling.

**Why you need it.** It is the one handling metric with published reference values, so it is your primary reality check on the whole model.

**Reference values to hold in your head:** passenger car 3–5 deg/g · sports car 1–2 deg/g · our car expect 1.5–3 · **below 1 deg/g essentially never seen in production** · **0.2 deg/g is the measurement noise floor.**

**Prediction:**
- Moving weight forward: `K` goes up or down? _____
- Stiffer front ARB: `K` up or down? _____
- Our GR86-class car at stock 0.54 front fraction: predict `K` to the nearest 0.5 deg/g _____

**Reality:** _[fill after D3]_

**Understanding check:** Explain why 0.2 deg/g is the noise floor — what physically varies that much? (Answer: two production batches of the same tire model.)

**Diagram slot:** D3 (steady-state validation). **Research phase:** P0/P1. **Publication:** essay 1, and the credibility anchor everywhere.

---

## M6 · Yaw inertia vs weight distribution

**Concept.** Two cars can have identical 53:47 balance and behave completely differently, because *where* the mass sits relative to the CoM sets the polar moment `I_zz`. Mid-engine clusters mass centrally → low `I_zz` → rotates eagerly, twitchy at the limit. Front- or rear-engine puts mass at an extreme → high `I_zz` → slower to rotate, more stable once rotating. Dumbbell vs barbell.

**Why you need it.** It is the parameter that separates engine layouts once balance is controlled for, and it is the axis on which your layout study lives.

**Prediction:**
- Step steer input. Higher `I_zz`: faster or slower yaw rise? More or less overshoot? _____
- Which archetype has the *lowest* `I_zz`? _____
- Front-engine RWD and rear-engine sit at opposite ends of the balance axis. Where do they sit relative to each other on the inertia axis? _____

**Reality:** _[fill after D4]_

**Understanding check:** Why would a *higher* `I_zz` car benefit more from torque vectoring? (This is the P4d-i hypothesis — if you can reason it out, you understand both M6 and M11.)

**Diagram slot:** D4 (transient response), 03 (design-space surface). **Research phase:** P0/P1. **Publication:** essay 4.

---

# Part 2 — Trajectory modules (P1–P2)

## M7 · What "optimal racing line" actually means

**Concept.** A tradeoff between path length and achievable speed. The geometric line maximizes radius (hence speed) but the *fast* line is different, because you are also managing when you can get back to throttle. Late apex costs mid-corner speed and buys exit speed — worth it when a straight follows.

**Prediction:** For our RWD car, does moving weight rearward push the apex earlier or later? Why? _____

**Reality:** _[fill after P1 sweep]_

**Diagram slot:** 02, 05, 10 (morphing line). **Research phase:** P1. **Publication:** essay 1.

---

## M8 · Optimal control — what is being solved

**Concept.** Pose the whole lap as one giant optimization: unknowns are the car's state and controls at ~1000 points along the track; constraints are the physics and the track edges; objective is total time. Hand to a solver (IPOPT). Distance along the track is the independent variable, not time, so the horizon is fixed and time becomes what you minimize.

**Why you need it.** It is the ceiling that tells you whether your RL policy is trained. You do not need the math; you need to know what it can and cannot do.

**Can:** find the true optimum for a fixed car on deterministic physics.
**Cannot:** react to disturbance, optimize a *controller*, handle noise, or run through a black-box simulator.

**Prediction:** Will OC or a trained RL policy produce the faster lap? By roughly how much? _____

**Reality:** _[fill after P2 cross-validation]_

**Diagram slot:** 12 (RL vs OC scatter). **Research phase:** P1/P2. **Publication:** essay 3 methods aside.

---

## M9 · RL and the reward-hacking problem

**Concept.** RL maximizes a number. If the model is optimistic anywhere, the policy will find that place and live there. The tire fit is valid over a measured region and silently returns plausible nonsense outside it — so a policy can discover a fast lap that exists only in the extrapolation.

**Why you need it.** This is the difference between a result about cars and a result about your curve fit.

**Prediction:**
- Where in slip-angle/load space do you expect a naive policy to drift? _____
- What fraction of samples outside the envelope should trigger discarding a result? _____

**Reality:** _[fill after first training run, D6 panel B]_

**Understanding check:** Why does a hand-tuned controller *never* reveal this problem, while RL does within hours?

**Diagram slot:** 11 (envelope occupancy), D6. **Research phase:** P2. **Publication:** essay 3, and it is a genuinely good standalone story.

---

# Part 3 — Torque vectoring modules (P4, the core)

## M10 · Differentials — the capability ladder

**Concept.** Four distinct things share the name. **Passive LSD**: mechanical clutch, reacts to input torque, can only transfer toward the slower wheel. **Active LSD**: same hardware, commanded lock, still one-directional. **True TV**: superposition gearset, can *overdrive* one wheel. **Independent motors**: arbitrary per-wheel torque, either sign, millisecond response.

The jump from 2 to 3 is the substantive one: levels 1–2 can only *remove* capability from one side; 3–4 *add* yaw moment on demand.

**Prediction:** Can a passive LSD help rotate a car that is off-throttle? Why or why not? _____

**Reality:** _[fill after P4a]_

**Diagram slot:** 14 (yaw decomposition, passive panel). **Research phase:** P4a. **Publication:** essay 2.

---

## M11 · How longitudinal force creates rotation

**Concept.** Drive the outside wheels harder than the inside, and the force difference times the moment arm (half the track width) is a yaw moment. `Mz = ΔF × t/2`. That is torque vectoring in one line. It is why track width matters so much and why it is the highest-leverage uncertain parameter in the model.

**Prediction:**
- Our car, 1000 N difference left-to-right, track 1.50 m. Yaw moment? _____ (`1000 × 0.75 = 750 N·m`)
- Compare to the yaw moment from lateral tire forces at 1 g. Bigger or smaller? _____
- What does that ratio tell you about how much authority TV really has? _____

**Reality:** _[fill after P4b]_

**Understanding check:** This prediction is the one that will most calibrate your intuition about whether TV results are plausible. Do it carefully.

**Diagram slot:** 14 (yaw decomposition, TV panel). **Research phase:** P4. **Publication:** essay 3.

---

## M12 · The two-layer architecture

**Concept.** Industry splits it: an **upper layer** decides *how much* yaw moment is wanted (reference bicycle model → target yaw rate, clipped to what friction allows → `Mz` request), and a **lower layer** decides *how to produce it* (distribute across four wheels subject to limits). Clean separation: upper layer needs no hardware knowledge, lower layer needs no driver knowledge.

**Why you need it.** It is the baseline your RL must beat, and it structures the three-way P4b experiment.

**Prediction:** Which layer do you expect RL to improve on more — deciding how much, or deciding how to distribute? _____

**Reality:** _[fill after P4b]_

**Diagram slot:** 07 (control law surface), 04 (Mz comparison). **Research phase:** P4b. **Publication:** essay 3 — the "what engineers designed vs what the machine found" arc.

---

## M13 · Control allocation and tire workload

**Concept.** The lower layer solves a small optimization every millisecond: minimize Σ(used force / available force)² across the four tires, subject to matching the driver's demand, matching the `Mz` request, and respecting per-wheel limits. Minimizing squared workload naturally spreads load and keeps every tire off saturation — which works *because of M3*.

**Prediction:** Will an end-to-end RL policy beat the workload-minimizing allocator, match it, or reinvent it? _____

**Reality:** _[fill after P4b variant E]_

**Understanding check:** Explain why minimizing squared tire workload is a sensible objective, using load sensitivity. If M3 is solid this should be quick.

**Diagram slot:** 04 (workload bars). **Research phase:** P4b. **Publication:** essay 3 climax.

---

## M14 · Generalization and model validation

**Concept.** Two separate questions. *Generalization*: does one setup work across tracks, and what does the compromise cost (the specialization gap)? *Validation*: does the finding survive a better physics model — and if not, which omitted mechanism carried it?

**Prediction:** Which car type do you expect to pay the *largest* penalty for a single compromise setup across tracks? _____

**Reality:** _[fill after P5/P6]_

**Diagram slot:** 17, 18, 13. **Research phase:** P5/P6. **Publication:** essays 7–8.

---

# Part 4 — Publication mapping

The essays are **not** in learning order. Each is hook-first.

| Essay | Hook | Modules used | Ready after |
|---|---|---|---|
| 1 · Why FWD and RWD want different lines | "Same corner, same grip, two different fastest paths — why?" | M1–M5, M7 | P3 |
| 2 · What a differential actually does | "The part of your car you have never seen work" | M10, M4 | P4a |
| 3 · **Engineers vs the machine** | "We gave an AI the same problem engineers solved 20 years ago. It found something else." | M11–M13, M9 | P4b |
| 4 · Front, mid, or rear engine | "Same weight balance. Completely different car. Here is the number that explains it." | M6 | P1 + P4d-i |
| 5 · How TV changes the driving | "Rotating without steering" | M11, M7 | P4c |
| 6 · Does TV make setup matter less? | "Is the art of chassis tuning about to be automated away?" | M3–M6, M13 | P4e |
| 7 · Speed vs fragility | "The fastest setup is the one you will crash" | M2, M9 | P3 + P4 |
| 8 · Did it survive real physics? | "Everything above was a simulation. Here is the audit." | M14 | P6 |

**Sequencing note.** Essay 1 needs the most groundwork (M1–M5) but is the most accessible read — that inversion is normal and is why publication order ≠ learning order. Essay 3 is the flagship and the one your architecture is uniquely positioned to write.

---

# Part 5 — How to actually run this

**Per phase, in order:**

1. **Before the phase:** fill in the Prediction sections for that phase's modules. Timebox it — 30 minutes, from your current understanding, no looking things up. The point is to surface what you do not know, not to be right.
2. **Convert predictions to assertions.** Anything you predicted with confidence becomes a test in D1–D5. Anything you could not predict is a flagged learning gap — go read about that one thing specifically.
3. **Run the phase.**
4. **Fill in Reality.** Where prediction ≠ reality, write one line on which it was: gap in understanding, or bug. This distinction is the most valuable thing in the document.
5. **Draft the essay fragment** while it is fresh — a paragraph, not a polished piece. The essays accrete rather than getting written.

**What this protects against.** The failure mode for a solo research project is producing results you cannot interpret and therefore cannot write about, six months in, with no memory of why any choice was made. Predictions dated and recorded are the antidote: they are a log of what you believed and when, which is also the only honest way to claim a finding was predicted rather than rationalized.

**One caution.** Do not let the scaffold become the project. If a module's prediction section is blocking progress, write "no intuition yet" and move on — that is a legitimate and informative entry.
