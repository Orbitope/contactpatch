# Content Series Plan

**What this is.** A sequence of articles/videos that build on each other: explain a concept, test the simplest version that demonstrates it, show what happened, then raise the complexity. The series is the deliverable. The research serves it.

**What this is not.** A research project with essays bolted on. If something novel emerges by the end, formal write-up is a separate decision made then, with the advantage that every step will already be documented.

---

## The structural principle

Every episode has the same four beats:

1. **A question** a curious non-expert would actually ask.
2. **The simplest model that can answer it** — deliberately underpowered, and honest about that.
3. **An experiment with a result** — not a demo. Something is measured, and it could have come out otherwise.
4. **The crack** — what this model can't explain, which sets up the next episode.

Beat 4 is what makes it a series rather than a playlist. Each episode earns the next by failing at something specific.

## What this changes about the build order

The research plan said double-track physics from P0. That was correct *for the research*. For the series, it's wrong to start there — you'd be explaining four-wheel load transfer before the audience knows why load transfer matters at all.

**Resolution:** build the bicycle model first as a content artifact and keep it. It is ~a day of work, it carries episodes 1–4, and it is *required* for episode 5, which is the comparison that motivates the upgrade. The double-track model then arrives as an answer to a demonstrated problem rather than as an assumption.

This is not wasted work. Two models sharing one interface is also how you get a free consistency check on the double-track physics — a genuine research benefit that fell out of a pedagogical decision.

**Cadence reality.** 16 articles at 2–3 weeks each is roughly 9–12 months, with one video per season as the payoff — four videos. Season boundaries are natural stopping points if bandwidth changes.

---

# Season 1 — How a car actually turns
*Bicycle model. Ships fastest. Complete on its own if you stop here.*

### Ep 1 · Why does a tire make grip at all?
- **Question:** A tire is pointed where you steer. So why does a car ever slide?
- **Model:** One tire. Slip angle sweep.
- **Experiment:** Sweep slip angle, plot lateral force. Find the peak.
- **Result to show:** Force rises, peaks near 7–10°, then *falls*. A tire's best grip happens when it is already slipping slightly.
- **Payoff line:** "Grip is not a threshold you cross. It is a curve with a top, and the fast part is near the top but not past it."
- **Crack:** One tire tells you nothing about a car. It has four, and they don't share load equally.
- **Code:** Tire model only. **Diagram:** D1 panel A.

### Ep 2 · The most important graph in vehicle dynamics
- **Question:** Why does weight transfer hurt? The car weighs the same either way.
- **Model:** Two tires sharing a fixed total load.
- **Experiment:** Split 6 kN as 3+3, then 4+2, then 5+1. Sum the peak lateral force each time.
- **Result to show:** Even split makes the most total grip. Peak μ falls with load (1.14 at 1 kN → 0.79 at 9 kN on our tire), so an overloaded tire never repays what the unloaded one lost.
- **Payoff line:** "This single fact — that tires get worse as you push harder on them — is why low centres of gravity, anti-roll bars, and half of motorsport engineering exist."
- **Crack:** Fine, but a real car's load split isn't a choice — it's set by physics you haven't modelled yet.
- **Code:** Tire model + load sweep. **Diagram:** D1 panel B.
- **Note:** This is the keystone episode. If only one lands, make it this one.

### Ep 3 · Building the simplest car that can understeer
- **Question:** What actually *is* understeer? Not the feeling — the measurement.
- **Model:** Bicycle model (two axles), longitudinal load transfer.
- **Experiment:** Constant-radius skidpad. Sweep speed, measure steering angle vs lateral g. Then move the weight forward and back and repeat.
- **Result to show:** Understeer gradient in deg/g. Ours should land 1.5–3. Moving weight forward raises it. Published bands: passenger car 3–5, sports car 1–2, **below 1 essentially never seen in production**.
- **Payoff line:** "Understeer isn't a fault. It's a number, it's deliberate, and every manufacturer picks one."
- **Crack:** The model has two wheels. A real car rolls, and the outside wheels do more work than the inside — which this model cannot represent.
- **Code:** Bicycle model + skidpad harness. **Diagram:** D3.

### Ep 4 · The fastest way around a corner isn't the obvious one
- **Question:** Why don't racers just take the widest arc?
- **Model:** Same bicycle model + optimal control (CasADi/IPOPT).
- **Experiment:** Minimum-lap-time solve on one corner. Then re-solve with a longer straight after it.
- **Result to show:** The apex moves later when exit speed matters more. Show the two lines overlaid.
- **Payoff line:** "The fast line isn't a shape. It's the answer to a question about what comes next."
- **Crack:** This solves for a *plan*, assuming perfect knowledge and no surprises. Real driving is reactive.
- **Code:** OC formulation. **Diagram:** 02, and a two-line overlay.

### Ep 5 · Where the simple model breaks — SEASON PAYOFF
- **Question:** We've been using a two-wheeled car. What are we getting wrong?
- **Model:** Bicycle *and* double-track, side by side.
- **Experiment:** Identical inputs through both. Compare understeer gradient, load distribution, and what happens when you stiffen a front anti-roll bar.
- **Result to show:** The bicycle model literally cannot respond to an anti-roll bar — it has no left and right. Roll stiffness distribution is invisible to it. That's a whole tuning dimension the simple model erases.
- **Payoff line:** "Every model is wrong somewhere. The skill is knowing exactly where yours is, before it lies to you."
- **Crack:** Now we have a car worth driving properly. But we've been driving it with a solver that knows the future.
- **Code:** Double-track model. **Diagram:** D5, D3 overlaid, D2.
- **Video:** Season 1 video covers Ep 1–5.

---

# Season 2 — What makes cars different
*Double-track + optimal control. **No RL needed for any of this.** All findings, no methods. Ships without any training risk.*

### Ep 6 · Front-wheel drive vs rear-wheel drive: the same corner, two different fast lines
- **Question:** Everyone knows FWD and RWD "feel different." What actually changes about the fastest way round a corner?
- **Model:** Double-track + OC. Change only which axle receives drive torque.
- **Experiment:** Solve minimum-lap-time for the same corner, same everything, FWD then RWD. Then plot per-wheel friction-circle usage along both laps.
- **Result to show:** The lines differ — and the *reason* is visible: which tire saturates first, and where. FWD asks the front tires to steer and accelerate simultaneously (they run out on exit); RWD splits those jobs across axles but the rear can overwhelm itself on power.
- **Payoff line:** "The difference isn't grip. Both cars have the same tires. The difference is which tires are being asked to do two things at once."
- **Crack:** We changed which axle drives. But we haven't touched *where the weight sits* — and that changes how much grip each axle has to work with.
- **Code:** Drivetrain routing in the double-track model. Nothing new beyond Ep 5.
- **Diagram:** 01 (per-wheel tire utilisation) as the centrepiece, 05, 02.
- **Note:** The most accessible episode in the series. Everyone with a licence has an intuition here, and the tire utilisation map either confirms or corrects it visually. Strong candidate for the widest-reaching piece.

### Ep 7 · Where you put the weight
- **Question:** Why does 50:50 get treated as the ideal? Is it?
- **Model:** Same. Sweep front mass fraction 0.35 → 0.65.
- **Experiment:** Re-solve OC at each point (fast — warm-start each solve from its neighbour). Measure understeer gradient, apex location, brake point, lap time.
- **Result to show:** The apex migrates continuously as weight moves rearward. The lap-time optimum is probably *not* at 50:50, and where it sits depends on the corner. Show `K` moving alongside it — the same number introduced in Ep 3, now doing real work.
- **Payoff line:** "50:50 is a marketing number. The fast answer depends on the corner, and it moves."
- **Crack:** Two cars can have identical weight distribution and still behave completely differently. Balance is not the whole story.
- **Code:** Design sweep driver. **Diagram:** 03 (weight-distribution slice), 02.
- **Note:** This is a *findings* episode. The conditioned-policy technique that makes sweeps cheap is a Season 3 topic — here OC does the work and the audience never needs to hear about it.

### Ep 8 · Front, mid, or rear engine — SEASON PAYOFF
- **Question:** Everyone says mid-engine is better. Better how, exactly?
- **Model:** Same, with yaw inertia as an axis independent of weight distribution.
- **Experiment:** Two cars, identical balance, different `I_zz`. Step steer, then a full corner. Then the 2D surface over balance × inertia with layout archetypes marked.
- **Result to show:** Low `I_zz` rotates faster and is twitchier at the limit; high `I_zz` turns in slower but is more forgiving. And the surface shows the non-collinearity — front-engine RWD and rear-engine sit at opposite ends of the *balance* axis but both high on *inertia*.
- **Payoff line:** "Weight distribution tells you where the mass is. Polar moment tells you how far it is from the middle. Those are different questions, and the second one is why a 911 doesn't drive like a Corvette."
- **Crack:** Everything so far assumes a driver who knows the future — the solver plans the whole lap in advance. Real driving is reactive, and some questions can't be asked that way at all.
- **Code:** `I_zz` sweep. **Diagram:** D4, 03 (full surface).
- **Video:** Season 2 video covers Ep 6–8. Probably the most broadly appealing of the three.

---

# Season 3 — Teaching it to drive
*RL enters, and it enters because there is something OC genuinely cannot do.*

### Ep 9 · Teaching a car to drive, and watching it cheat
- **Question:** Can something learn to drive fast with no instruction, just a stopwatch?
- **Model:** Double-track + PPO.
- **Experiment:** Train a policy. Then look at *where in tire state space* it spent its time.
- **Result to show:** The first policy finds a fast lap by operating where the tire model was never fitted — arithmetically real, physically fictional.
- **Payoff line:** "It didn't learn to drive. It learned that my tire model was optimistic at 25 degrees of slip, and drove there."
- **Crack:** Fixed. But now every car needs its own training run, and Season 2 swept hundreds of designs.
- **Diagram:** 11, D6.
- **Note:** Strongest standalone story in the series.

### Ep 10 · One policy, a thousand cars
- **Question:** How do you get a driver who can drive *any* car, so you can compare them fairly?
- **Model:** Design-conditioned policy — the car's parameters go into the observation.
- **Experiment:** Train once across randomized designs. Sweep weight distribution continuously and watch the line deform. Cross-check against the Season 2 OC results.
- **Result to show:** The morphing line animation, plus RL-vs-OC agreement — two completely different methods, same trend.
- **Payoff line:** "Two methods that share no assumptions agreed. That's worth more than either one alone."
- **Diagram:** 10, 12.

### Ep 11 · The fastest setup is the one that crashes — SEASON PAYOFF
- **Question:** Why don't racers just run the fastest setup?
- **Model:** Same policy, perturbed conditions. **This is the first question OC structurally could not answer** — it needs a driver who reacts, not a plan.
- **Experiment:** Inject steering noise and grip variation. Measure lap-time consistency and spin rate per design.
- **Result to show:** The speed-vs-fragility Pareto front. Fast setups are knife-edged.
- **Payoff line:** "Every setup is a bet on how good your day is going to be."
- **Diagram:** 16.
- **Video:** Season 3 video covers Ep 9–11.

---

# Season 4 — Torque vectoring
*The core. Everything above was setup.*

### Ep 12 · What a differential actually does
- **Question:** Your car has one. You've never seen it work. What is it for?
- **Experiment:** Open vs passive LSD vs welded, same corner. Decompose yaw acceleration into lateral tire forces, load transfer, and drivetrain asymmetry.
- **Result to show:** The drivetrain contributes almost nothing until power-down, then it matters. A locked diff pushes wide on power — a visible yaw deficit.
- **Payoff line:** "A differential is a machine for deciding which wheel gets to be in charge."
- **Crack:** All of these only react. What if it could decide?
- **Diagram:** 14 (passive panel).

### Ep 13 · How engineers built a car that steers with its wheels
- **Question:** If pushing one wheel harder rotates the car, why not just do that?
- **Experiment:** Implement the classical two-layer controller — reference model + PID → `Mz`, then QP allocation minimizing tire workload.
- **Result to show:** It works. Expect 1–4% lap time for our car (best published figure is ~9%, FSAE car on a skidpad — maximally favourable, so treat >9% as a bug).
- **Payoff line:** "Two layers: one decides how much you want to rotate, one decides which wheels pay for it. That split is 20 years of engineering consensus."
- **Diagram:** 07 (classical panel), 04.

### Ep 14 · What the machine found instead — FLAGSHIP
- **Question:** Give it the same problem, no hints. Does it agree with us?
- **Experiment:** Variants H (RL upper layer + QP allocator) and E (end-to-end four-wheel torques). Overlay learned `Mz` against classical. Compare tire workload.
- **Result to show:** The difference map between control surfaces. Published work found best lap times come from *allowing deviations from neutral yaw-rate tracking* — if our policy independently finds that, it's corroboration, and it's something a linear reference-model controller structurally cannot express.
- **Payoff line:** TBD — depends on the result, and that's the point.
- **Diagram:** 07 (all three panels), 04.
- **Note:** Do not script the conclusion. "It reinvented the allocator" is a fine outcome and a better story than a forced one.

### Ep 15 · Is chassis tuning about to be automated away?
- **Question:** If the car changes its own behaviour, does mechanical setup still matter?
- **Experiment:** Re-run the Season 2 sweeps — FWD/RWD, weight distribution, engine layout — with TV active. Compare sensitivity curves.
- **Result to show:** Whether TV flattens design sensitivity, and whether it flattens *layout* differences too.
- **Payoff line:** If flattening holds: "The thing that made a 911 a 911 might be something software can now simulate."
- **Diagram:** 15.
- **Note:** This episode only works because Season 2 measured the unflattened baseline. It is the payoff for having done the findings episodes first.

### Ep 16 · Did any of this survive real physics? — SERIES PAYOFF
- **Question:** All of that was a simulation I wrote. How much of it is true?
- **Experiment:** Three design points re-run in Chrono. Compare trend direction, not lap times.
- **Result to show:** The z-score overlay. Parallel lines = the finding transfers. Inverted = the effect depended on something the simple model discarded, and you can name what.
- **Payoff line:** "Here's the part where I try to prove myself wrong."
- **Diagram:** 13, and the P6 overlay.
- **Video:** Season 4 video covers Ep 12–16.

---

## Honest notes on this structure

**If you stop after Season 1**, you have five articles and a video that teach vehicle dynamics from first principles with working code. That is a complete thing, and it's a real contribution to a topic that is badly served online.

**Seasons 1–2 carry no training risk at all.** Eight episodes, entirely tire model + double-track + optimal control. No RL, no reward shaping, no convergence problems. If the RL work turns out harder than expected, two thirds of a season still ships on schedule.

**Season 4 is the reason for the project**, but 1–3 are not a tax paid to reach it. Ep 14 lands only if the audience understood Ep 2, and Ep 15 is only possible because Season 2 measured the baseline it compares against.

**The riskiest episode is 14**, because its payoff depends on a result you don't have. Every other episode can be written from a result you're confident you'll get. Plan for the possibility that the honest version is "the machine agreed with the engineers" — still worth publishing, and a more interesting claim than most people expect.

**A structural lesson worth keeping.** An earlier draft of this plan organised Season 2 around *methods* — RL, then design-conditioning, then inertia. Two of three episodes were about technique rather than findings, and FWD vs RWD disappeared entirely despite being the most accessible question in the project. Watch for that failure mode at every season boundary: **the audience came for the car, not the algorithm.** Methods episodes earn their place only when the method is itself the story (Ep 9, reward hacking) or when it unlocks something otherwise impossible (Ep 10, Ep 11).

**On formal publication:** the natural candidates, if anything emerges, are the design-sensitivity flattening result (Ep 15) and the layout/yaw-inertia interaction (Ep 8 + 15). Both are comparative claims that nobody appears to have made. Decide at the end. The series documentation will already contain everything a paper would need.
