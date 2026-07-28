# Reference Vehicle Parameters and Validation Targets

**Purpose.** P0 is only delegable if "is the physics right?" is a test rather than a judgement call. This sheet supplies the numbers that make the D1–D6 diagnostics executable. Every value is either sourced, derived from a sourced correlation, or explicitly marked as an assumption.

**Status of each number matters more than its precision.** Three tiers used throughout:
- **[SOURCED]** — from published data or a published correlation.
- **[DERIVED]** — computed from sourced values via a stated formula.
- **[ASSUMED]** — chosen by us. Must be documented in the repo and revisited if a diagnostic fails.

---

## 1. Reference vehicle: "RV-1", a GR86-class sports coupe

Chosen because it is a light, low, RWD, near-balanced sports coupe with a factory LSD — the design sweep sits naturally around it, and it is exactly the kind of car where diff and TV behaviour is interesting. Also: real published dimensions, and enough enthusiast interest that the findings will land with an audience.

| Parameter | Value | Tier | Notes |
|---|---|---|---|
| Curb mass `m` | 1280 kg | [SOURCED] | Reported 1275 kg (2811 lb); other listings give 2774–2833 lb. Use 1280 kg; add 80 kg driver → **1360 kg** as the simulated mass |
| Wheelbase `L` | 2.575 m | [SOURCED] | 101.4 in |
| Overall length | 4.265 m | [SOURCED] | 167.9 in |
| Overall width | 1.775 m | [SOURCED] | 69.9 in |
| Overall height | 1.310 m | [SOURCED] | 51.6 in; roof height 1.280 m |
| Track width `t_f` / `t_r` | 1.505 / 1.495 m | [LIKELY] | Dimensional listing citing SAE J1100 surveys; source quality medium. 84.8% of overall width — in range. **Sensitivity-check all TV magnitude claims at ±3%** |
| Front mass fraction | 0.54 | [SOURCED] | Toyota press kit states an intentional **53:47**, chosen by their engineers as ideal for spirited driving. An enthusiast corner-weighting sheet uses 56:44 (driver aboard). Use 0.54 driver-inclusive; document 0.53–0.56 as known uncertainty |
| CoM height `h` | 0.460 m | [SOURCED] | Toyota press kit: **ultra-low CoG of 460 mm**, with a 400 mm driver hip-point. Independent cross-check at 18 in = 457 mm. Two sources within 3 mm — high confidence. Do not "correct" upward toward generic sedan values |
| Static Stability Factor | 1.63 | [DERIVED] | `(t/2)/h` = 0.7525/0.460. Plausible: NHTSA range runs ~0.95 (SUV) to ~1.8 (Corvette) |
| Drivetrain | RWD, factory LSD | [SOURCED] | |
| Peak engine torque | 250 N·m @ 3700 rpm | [SOURCED] | 184 lb-ft; 228 hp @ 7000 rpm |
| Frontal area | 1.99 m² | [ASSUMED] | ≈ 0.85 × width × height |
| `C_d` | 0.29 | [ASSUMED] | |

### Yaw inertia — the correlations disagree, and geometry wins

Three estimation routes for `m` = 1280 kg:

| Method | Result | Note |
|---|---|---|
| SAE mass regression `I_zz = 2.86·m − 1315` | **2,346 kg·m²** | [SOURCED] formula, but fit to 1980s-era American sedans — a mass-only fit that ignores the GR86's short wheelbase and length |
| German geometric rule `(0.1269–0.1468)·L·length·m` | **1,783 – 2,063 kg·m²** | [SOURCED] formula; uses actual dimensions |
| Radius of gyration ≈ 45% of wheelbase | **1,719 kg·m²** | [SOURCED] heuristic; ignores overhang mass, so reads low |

**Use 1,950 kg·m² as nominal** [DERIVED]. The two geometry-aware methods bracket 1,719–2,063 and agree well; the mass-only SAE regression sits ~20% above them and should be discounted here precisely because a GR86 is short and light for its mass class. This disagreement is worth documenting in the repo — it is a real example of why a mass-only correlation is the wrong tool for a compact sports car.

Cross-checks: `I_yy = 2.56·m − 1103` → 2,174 kg·m² [SOURCED formula] (yaw and pitch are typically close, which the geometric yaw estimate honours better than the regression). `I_xx = 0.28·m − 71.6` → 287 kg·m² [SOURCED formula].

### Engine layout archetypes

Yaw inertia is what separates layouts once weight distribution is controlled for (dumbbell vs barbell). Multipliers are [ASSUMED], ordered by physical reasoning: mass clustered near the CoM lowers `I_zz`; mass at one end raises it. The GR86 itself is front-mid-engined, so it sits between the front-engine and mid-engine archetypes — a useful reminder that these are regions, not categories.

| Archetype | Front fraction | `I_zz` × nominal | `I_zz` (kg·m²) | Drive |
|---|---|---|---|---|
| Front-engine FWD | 0.62 | 1.25 | 2,438 | FWD |
| Front-engine RWD | 0.55 | 1.20 | 2,340 | RWD |
| **RV-1 (GR86, front-mid)** | **0.53** | **1.00** | **1,950** | **RWD** |
| Mid-engine | 0.43 | 0.80 | 1,560 | RWD |
| Rear-engine | 0.38 | 1.22 | 2,379 | RWD |

Rear-engine cars place roughly 60–62% of mass behind the rear axle, which raises polar moment — the car resists direction change but is harder to recover once rotating. That is the physical claim the archetype table encodes and D4 must reproduce.

## 2. Design sweep ranges

| Parameter | Nominal | Sweep | Tier |
|---|---|---|---|
| Front mass fraction | 0.50 | 0.35 – 0.65 | [ASSUMED] |
| `I_zz` multiplier | 1.00 | 0.75 – 1.40 | [SOURCED] band |
| CoM height | 0.52 m | 0.42 – 0.60 m | [ASSUMED] |
| Front spring rate (per corner) | 28 N/mm | 18 – 45 N/mm | [SOURCED] anchor |
| Rear spring rate (per corner) | 26 N/mm | 18 – 45 N/mm | [ASSUMED] |
| Roll stiffness distribution (front share) | 0.55 | 0.40 – 0.70 | [ASSUMED] |
| Diff preload | 100 N·m | 0 – 400 N·m | [ASSUMED] |
| Diff ramp angle (power / coast) | 45° / 60° | 30–70° | [ASSUMED] |

The 28 N/mm front spring anchor comes from a published CarSim B-class hatchback parameter set (mass 1134 kg, wheelbase 2.6 m, roll/pitch/yaw inertia 441 / 1343 / 1343 kg·m²) — a lighter car than RV-1, so treat it as an order-of-magnitude anchor, not a target.

---

## 3. Tire model

### 3.1 Correction to an earlier claim

An earlier draft of this sheet stated that no free, redistributable Pacejka parameter set exists for a passenger car. **That was wrong.** Project Chrono is released under BSD-3 ("one can use, modify, redistribute, sell, etc."), and ships complete MF-Tyre 2002 parameter files. The relevant one:

`data/vehicle/sedan/tire/Sedan_Pac02Tire.tir` — a full MF 2002 set, header reading "Magic Formula Tire from ADAMS/Car TIR file".

The accurate version of the earlier concern is narrower: **commercial vendor-measured sets for a *specific* named tire** (TNO `.tir`, FSAE TTC data) are restricted. Generic, redistributable, physically-sound sets are freely available. That distinction matters a lot for this project — we can use real fitted coefficients rather than invented ones.

### 3.2 The Chrono sedan tire, evaluated

245/40 R18, unloaded radius 0.344 m, tire mass 11.5 kg, `FNOMIN` = 4850 N, vertical stiffness 280.8 kN/m.

Evaluated pure-lateral response (computed directly from the file's coefficients):

| `Fz` (N) | peak μ | `Fy` peak (N) | slip at peak (°) | cornering stiffness (N/deg) |
|---|---|---|---|---|
| 1000 | 1.139 | 1139 | 9.7 | 375 |
| 2000 | 1.095 | 2190 | 9.7 | 715 |
| 3000 | 1.052 | 3155 | 10.0 | 997 |
| 3929 (`Fz0'`) | 1.012 | 3974 | 10.5 | 1197 |
| 5000 | 0.965 | 4826 | 11.3 | 1357 |
| 7000 | 0.878 | 6149 | 13.1 | 1489 |
| 9000 | 0.792 | 7126 | 15.1 | 1486 |

Everything here is physically right: **peak μ falls monotonically with load** (dμ/dFz ≈ −0.043 /kN), cornering stiffness rises and then saturates, and slip-at-peak grows with load. These are exactly the D1 assertions, and this real set passes them.

**Sign convention warning, learned the hard way.** `PKY1` is negative in this file — ISO/TYDEX convention, where `Fy` opposes a positive slip angle. Evaluating it without accounting for that returns zero peak force and negative cornering stiffness, silently. This is a live instance of precisely the failure D2 exists to catch, encountered while writing this sheet. Adopt the file's convention explicitly in the schema and assert it.

### 3.3 Sizing mismatch, and the clean fix

`FNOMIN` = 4850 N implies a nominal corner load for roughly a 1,980 kg car — this tire is sized for something considerably heavier than a GR86. RV-1 at 1360 kg has a static corner load near 3,335 N, giving peak μ ≈ 1.04 and max lateral roughly 1.04 g. That is *plausible* for a GR86 on good summer tires, but it is a bigger tire (245 section vs the real car's 215) so grip is mildly optimistic.

The fix is built into the Magic Formula: the `[SCALING_COEFFICIENTS]` block. `LFZO` rescales nominal load (already 0.81 in this file), `LMUY` scales peak lateral friction, `LKY` scales cornering stiffness. So the honest move is to keep the fitted shape and rescale to a GR86-appropriate tire, documenting the scaling factors used. **Do not hand-edit the `P*` coefficients** — that discards the fit's internal consistency.

### 3.4 Declared validity envelope

The file declares its own ranges — this is the envelope, no longer an assumption:

| Quantity | Declared range | Comment |
|---|---|---|
| Vertical load `Fz` | 225 – 10,125 N | Meaningful and usable. RV-1's operating range sits comfortably inside |
| Slip angle | ±1.5708 rad (±90°) | **Formal bound, not a measurement envelope.** The file is declaring where the formula is *defined*, not where it was *fitted* |
| Slip ratio `κ` | −1.5 – 1.5 | Same caveat |
| Camber | ±0.2618 rad (±15°) | Not modelled in our double-track model |

**So the envelope discipline survives, in modified form.** `FZMIN`/`FZMAX` are real and should be enforced directly. The ±90° slip-angle bound is useless as a validity check, so we still impose our own operating envelope there — ±12° for slip angle and ±0.20 for slip ratio [ASSUMED], on the reasoning that tire rigs sweep roughly that width and the fit is only trustworthy where data existed. Document this as *our* imposed bound, distinct from the file's declared bound.

### 3.5 What this changes about the project's honesty claims

Better than the previous position, but still bounded:
- Absolute grip levels are now traceable to a real fitted tire rather than to invented coefficients. Lap times become meaningful in relative terms and roughly credible in absolute terms.
- The tire is *generic*, not a measured GR86 tire, and is oversized for the car before rescaling. Absolute lap times are still not a claim about any specific real car.
- Comparative findings across designs — the actual output of this project — are unaffected either way, since they use one consistent tire model throughout.

## 4. Validation targets

These are what D3 and D4 assert against. **Understeer gradient `K` in deg/g at the road wheel, computed as the slope of (δ − Ackermann) vs `a_y`, fitted about ±0.5 g.**

| Target | Value | Tier | Source note |
|---|---|---|---|
| `K`, typical passenger car | 3 – 5 deg/g | [SOURCED] | Widely cited range |
| `K`, sports car | 1 – 2 deg/g | [SOURCED] | " |
| `K`, broader passenger band | 2 – 5 deg/g | [SOURCED] | Alternate citation; use 1.8–5.5 as the test band |
| `K`, essentially never seen | < 1 deg/g | [SOURCED] | Practitioner report: virtually no production vehicles below 1 deg/g |
| Tire-submission sensitivity | ~0.2 deg/g | [SOURCED] | Between two submissions of the *same* tire — sets the noise floor for what a meaningful `K` difference is |
| Development drift | up to 0.5 deg/g | [SOURCED] | Expected to be lost during vehicle development |
| Max lateral acceleration | 1.15 – 1.40 g | [ASSUMED] | Follows from `μ` choice; consistent with the tire model above |
| Terminal behaviour | understeer, positive slope throughout | [SOURCED] | Majority of road-going vehicles exhibit linear-range and limit understeer per SAE J266, with a distinct upturn near the limit |
| Step-steer yaw rise time | 0.08 – 0.30 s | [ASSUMED] | |
| Step-steer overshoot | 5 – 40 % | [ASSUMED] | |

**The 0.2 deg/g figure is the most useful number on this page.** It is the real-world noise floor for understeer gradient. Any `K` difference our sweep produces that is smaller than ~0.2 deg/g is below the level at which a professional test program can distinguish two versions of the same tire, and should not be reported as a finding.

**Bundorf reference decomposition** [SOURCED] — a worked example totalling `K = 4.1 deg/g` from front axle cornering compliance 11.0 and rear 6.9 deg/g, with contributions from load transfer + cornering stiffness (8.0 / 7.0), aligning torque (0.2 / −0.2), roll camber (1.2 / 0.0), roll steer (0.6 / −0.4), and compliance steer terms. Useful as a structural check: our model only includes the load-transfer/cornering-stiffness term and roll effects, so our `K` should land *below* a real car's with the same tires, since we omit compliance and aligning-torque contributions. If our `K` comes out *higher*, something is wrong.

---

## 5. What the diagnostics assert

| Diagnostic | Gates | Key assertions |
|---|---|---|
| **D1** Tire model card | tire code | peak μ falls with load; slip at peak 5–10°; `Fy(0)=0`; odd symmetry exact |
| **D2** Invariants & signs | everything | 17 sign/conservation/symmetry asserts; mirror test; timestep convergence |
| **D3** Steady-state handling | model realism | `K` in 1.8–5.5 deg/g; monotone in weight distribution; terminal understeer; max lat g in band |
| **D4** Transient response | `I_zz` wiring | rise time ↑ and overshoot ↓ monotonically with `I_zz`; steady state matches D3 within 2% |
| **D5** Load transfer audit | double-track core | Σ loads = mg to machine precision; no wheel lift below SSF; transfer ∝ CoM height |
| **D6** Training health | every RL run | envelope violation < 2%; gap to OC < 1%; design-space coverage; action saturation; termination mix |

**Read order for D6 is B-then-A**: a converged reward curve on an exploited tire model is worse than no result. Check honesty before convergence.

---

## 6. Open items before P0 handoff

1. **Combined-slip weighting** — friction ellipse is the placeholder; decide whether to implement the cosine weighting functions and accept the extra unvalidated parameters.
2. **Diff model fidelity** — the preload/ramp torque-bias model needs a concrete formulation before D2's diff-related asserts can be written.
3. **Ackermann/steering rack** — currently assumed ideal Ackermann; note that Chrono will have a real rack, and the D2 steering asserts should be written to survive that swap.
4. **Aero** — drag only; no downforce. Fine for a road car, wrong for anything with a wing. Document as a scope boundary.
5. **~~Whether to source a real tire set~~** — RESOLVED. Chrono's BSD-3 `Sedan_Pac02Tire.tir` is a complete MF 2002 set and is the starting point. Remaining work is choosing `LMUY`/`LKY`/`LFZO` scaling to a GR86-appropriate tire size and documenting the choice.
6. **~~Verify track width, weight distribution, CoM height~~** — RESOLVED. Weight distribution and CoM height now have Toyota primary sources (53:47, 460 mm). Track width is [LIKELY] at 1505/1495 mm — good enough to proceed, but every TV magnitude claim gets a ±3% track-width sensitivity check before publication. See `result-evaluation-guide.md` §A.
7. **Decide MF 2002 vs simplified four-parameter form.** Using Chrono's file argues for implementing enough of MF 2002 to consume it directly — which also makes the P6 Chrono handoff near-trivial, since both backends would then run the same tire file. That is a strong argument, and it changes the P0 estimate upward slightly.
