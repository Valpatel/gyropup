# Prior art: closed-loop design of legged and wheel-legged robots

Research date: 2026-10-25. This file covers the loop wobbit wants to build: spec → CAD → URDF/MJCF → simulation → loads → FEA → manufacturability and cost → iterate.

Companion file: [reference-robots.md](reference-robots.md) covers the robots themselves (Diablo, Ascento, Upkie, Open Duck, Microduck). This file covers how other people designed robots in a loop.

**How this was researched.** The web-search budget ran out after a handful of queries. After that I went straight to primary sources:
- arXiv abstracts and full text, fetched by ID;
- citation graphs from the Semantic Scholar API (who cites Text2Robot, RoboMorph, Ascento, BDX, Megaro 2015 and Bjelonic 2023);
- the GitHub API, for repo licences and activity.

Each entry says how deeply it was read: **[full text]** means the paper body was read, **[abstract]** means only the abstract or project page. "Not reported" means the source I read does not give the number. Licences come from the GitHub API (`license.spdx_id`); "none" means no licence file was detected, which legally means all rights reserved.

---

## 1. Executive summary

1. **Nobody has published the full wobbit loop.** I found no work that goes CAD → sim → FEA → printability/cost → iterate automatically, and none that does it for a **wheel-legged biped**. The pieces exist separately:
   - Text2Robot: text → mesh → URDF → evolution + RL → PLA print.
   - RoboForge: agent-generated STEP/STL/URDF, pre-fabrication checks, then RL.
   - Skaterbots and Geilinger 2020: legged-wheeled design with trajectory optimisation.
   - Bjelonic 2023: design-conditioned RL plus Bayesian optimisation.
   - Quadruped skating 2026: BO outer loop, PPO inner loop, wheel angles as design variables.
   - Ascento: a topology-optimised printed wheel-legged robot, designed by hand.

   wobbit would be the first open loop of this kind, which leaves room to contribute but also means no proven recipe to copy end to end.
2. **Do not train RL from scratch for every candidate.** It is the cost that limits everyone:
   - RoboMorph: ≈200 A100 GPU-hours per seed.
   - Disney BDX: ≈22 days on an RTX 4090 for one final policy, though 30 min was enough to preview behaviour.

   The approaches that work amortise training across designs:
   - one policy that takes the design parameters as input (Schaff 2018; Bjelonic 2023; Belmonte-Baeza 2022, which uses meta-RL);
   - pretrain on many designs, then fine-tune the best (Chen 2024; RoboCraft 2025; LACE 2026).
3. **Use a model-based controller for screening.** For a wheel-legged biped, an LQR or MPC balancer (Ascento, Upkie) evaluates a design in seconds and needs no training. Use RL only for finalists.
4. **Toy-simulator co-design does not transfer to hardware.** Evolution Gym, Transform2Act, NGE, BodyGen, RoboMorph and Debate2Create all optimise abstract MuJoCo or voxel bodies. Kriegman's lab (2026) says that of "countless" evolved virtual agents, "vanishingly few were realized as physical robots", because the abstraction throws away motors, electronics and wiring. Reuse their optimisers and benchmarks, not their design representations.
5. **LLMs propose designs well and verify them badly:**
   - In RoboForge, the best model passed 4 of 6 mechanical-feasibility checks and older models passed 0–1. Common failures were missing mounting features, self-intersections and too little actuator clearance.
   - Wilhelm et al. (2026) could not verify any of 30 direct LLM designs as feasible.

   Pattern to copy: let the LLM build or modify an explicit parametric model, or propose samples alongside a numerical optimiser (Kawaharazuka 2025). Deterministic checks should gate everything.
6. **FEA is almost never in the loop.** Most co-design papers treat links as rigid, uniform-density bodies with no stress check (SERL 2024 states it, Text2Robot does not discuss it). Where structure was addressed:
   - Ascento used topology optimisation once, then a manual redesign, printed in SLS PA12.
   - MechStyle (2025) feeds FEA stress back into generative geometry edits.
   - Sathuluri (2023) uses loads from dynamics simulation to optimise the structure.
   - Upkie's printed femurs and tibias broke in use, and v2 redesigned the lower leg as a fork.

   Extracting loads from simulation and running FEA on PLA parts is therefore a real gap wobbit can fill.
7. **Actuator models matter more than morphology for sim-to-real:**
   - Disney BDX: system-identified actuator model with friction, backlash and reflected inertia.
   - Open Duck and Microduck: Rhoban BAM.
   - Bjelonic IJRR 2025: motor energy-loss model.

   A co-design loop optimising against a poor actuator model will push designs to wherever the model is wrong.
8. **Design-conditioned policy + BO is the best template for continuous variables** like leg lengths, wheel radius and spring stiffness:
   - Bjelonic 2023: 33 % better torque-squared efficiency and 30 % lower peak torque on ANYmal.
   - Quadruped skating 2026: 14.6 % lower CoT.
   - SurGE 2026: CMA-ES with surrogate gradients; the trend found in simulation held on hardware.
9. **For discrete choices (actuator SKU, wheel, battery, leg topology), use a grammar or catalogue so that every candidate can be built** (RoboGrammar, Text2Robot modules, Skaterbots components, Vitruvio actuator list). Then search with evolution or multi-objective TPE, with an LLM as an extra proposal operator.
10. **Licences:** most of what wobbit would reuse is permissively licensed:
    - MIT: Eureka/DrEureka, RoboGrammar, Transform2Act, EvoGym, SurGE, onshape-to-robot.
    - Apache-2.0: Text2Robot, BAM, MuJoCo Playground, Upkie, Open Duck Mini, BodyGen.
    - RoboGen is GPL-3.0, and Vitruvio and Open_Duck_Playground have no licence file. Read those, don't copy them.

---

## 2. Comparison table

Abbreviations: EA = evolutionary algorithm, BO = Bayesian optimisation, TO = trajectory optimisation, CoT = cost of transport, DR = domain randomisation.

| Work | Year | Robot type | Design variables | Evaluation | Optimiser | Manufacturing | Code / licence | Link |
|---|---|---|---|---|---|---|---|---|
| Text2Robot (Duke) | 2024–25 (ICRA 2025) | Quadruped, 8 servos | Mesh from text; leg length (0.5 cm steps); joint axes; limb and body shape | Isaac Gym PPO, velocity tracking + joint power | EA (keep top 100, 50 mutation + 50 crossover per generation; 20–50 generations) | PLA on a CR-10; Hiwonder servos, RPi 4; "about a day" to make | Yes, Apache-2.0 | [arXiv 2406.19963](https://arxiv.org/abs/2406.19963), [repo](https://github.com/generalroboticslab/Text2Robot) |
| RoboForge / agentic robot creation | 2026 | Gorilla quadruped (agent-designed), plus Go2, MicroDuck, Ostrich | Full STEP/STL/URDF from an LLM | 23 pre-fabrication checks; Isaac Lab PPO; user ratings | LLM generate → verify → revise (at most 3 trials) | PLA, Bambu X1E, 0.2 mm, 15 % infill; 8 × XL330 | Project page only; no repo found | [arXiv 2610.17881](https://arxiv.org/abs/2610.17881) |
| Disney BDX character | RSS 2024 | Biped, 5-DoF legs + 4-DoF neck, 15.4 kg | Hand-designed, guided by animation and a gait tool | Isaac Gym PPO imitation; hardware shows | Human iteration | Printed links between off-the-shelf actuators; moulded foam feet | No | [arXiv 2501.05204](https://arxiv.org/abs/2501.05204) |
| Bjelonic et al., PEA co-design (ETH) | 2023 RA-L | Quadruped (ANYmal) | Knee parallel-elastic spring | Design-conditioned RL policy | BO over the design, using the trained policy | Hardware PEA tested | No repo found | [arXiv 2301.03509](https://arxiv.org/abs/2301.03509) |
| Belmonte-Baeza et al., meta-RL design (ETH) | 2022 (RA-L/ICRA 2023) | Quadruped | Kinematics, actuator parameters | Meta-RL policy adapted per design, rough terrain | Not stated in abstract | Sim | No repo found | [arXiv 2210.02750](https://arxiv.org/abs/2210.02750) |
| Quadrupedal skating co-design | 2026 (ICRA) | Go1 + 3D-printed passive wheels | Wheel yaw angles (1-D and 2-D) | Isaac Lab PPO, CoT | GP-BO outer loop | Printed roller supports; hardware results not confirmed in what I read | Not reported | [arXiv 2603.18408](https://arxiv.org/abs/2603.18408) |
| Skaterbots (ETH/Disney) | 2018 TOG | Legged-wheeled creatures | Servo / connector / wheel / foot arrangement and dimensions | Trajectory optimisation (walk, roll, skate) | Interactive + semi-/fully-automatic design edits | 3D-printable connectors + servos; prototypes built | No repo found | [DOI 10.1145/3197517.3201368](https://doi.org/10.1145/3197517.3201368) |
| Geilinger et al., legged-wheeled framework | 2020 RA-L | Legged-wheeled robot | End effectors, morphology | Trajectory optimisation with continuation warm-start | Gradient-based | Built robot | No repo found | [DOI 10.1109/LRA.2020.2978444](https://doi.org/10.1109/LRA.2020.2978444) |
| Ascento (ETH) | 2019 ICRA | Two-wheeled jumping biped, 10.4 kg | 6 linkage parameters; topology-optimised parts | Linkage path error; LQR balance; jumps | Numerical least-squares; topology optimisation then manual redesign | SLS PA12 parts, torsion springs | No | [arXiv 2005.11435](https://arxiv.org/abs/2005.11435) |
| Ha et al., task-based limb optimisation (Disney) | 2016 IROS | Legged | Leg link lengths | Σ joint torque² over jump, walk, step | Two-stage TO | Not reported | No | [Disney page](https://la.disneyresearch.com/publication/task-based-limb-optimization-for-legged-robots/) |
| Megaro et al., 3D-printable robotic creatures | 2015 SIGGRAPH Asia | 2/4/5-legged servo creatures | Morphology, proportions, feet, gait | Motion optimisation, physics sim | Interactive | Printed parts + servos; 6 creatures, prototypes built | No | [Disney page](https://la.disneyresearch.com/publication/interactive-design-of-3d-printable-robotic-creatures/) |
| Desai et al., adjoint co-design (CMU) | 2018 | Legged | Morphology + motion | TO | Adjoint gradients, interactive | Sim | No | [arXiv 1801.00385](https://arxiv.org/abs/1801.00385) |
| Dinev et al., versatile co-design (Edinburgh) | 2022 IROS | Quadruped (Solo) | Morphology, payload placement, actuator parameters | Differentiable motion planner (jump, trot) | Bilevel NLP | Sim | Not reported | [arXiv 2103.04660](https://arxiv.org/abs/2103.04660) |
| Vitruvio (ETH) | 2020 | 1–4-legged | Links, density, actuator from list, layout | Joint torque, speed, power and energy along TOWR trajectories | GA | Sim | Yes, **no licence** | [repo](https://github.com/leggedrobotics/vitruvio) |
| SERL / Wow Orin | 2024 | Biped, 10.5 kg | Thigh and shin length (0.2–0.4 m) | Isaac Gym RL reward, CoT, speed | GA (population 250) alternating with RL | CF/Al/PETG; **no FEA** | Project page only | [arXiv 2408.15632](https://arxiv.org/abs/2408.15632) |
| Pretraining–finetuning co-design | 2024 | Quadruped (parkour) | Fore and hind leg lengths | RL parkour | Pretrained policy over designs, fine-tuned per design | Sim | Not reported | [arXiv 2407.06770](https://arxiv.org/abs/2407.06770) |
| RoboCraft (humanoid fall recovery) | 2025 | 7 public humanoids | Morphology | RL fall recovery | Shared pretrained policy + priority buffer + optimiser | Sim | Not reported | [arXiv 2510.22336](https://arxiv.org/abs/2510.22336) |
| SurGE | 2026 (IROS) | Hopper with parallel spring | 4-D (2-D on hardware) | Kino-SRB model + design-aware policy | CMA-ES + surrogate-gradient mean shift | **Hardware: 37.65 % objective reduction** | Yes, MIT | [arXiv 2606.21866](https://arxiv.org/abs/2606.21866), [repo](https://github.com/ARCaD-Lab-UM/surge-codesign) |
| Jointly learning to construct and control | 2018 ICRA | Legged (sim) | Link parameters | RL over a design distribution | Shift the design distribution with the policy gradient | Sim | Not checked | [arXiv 1801.01432](https://arxiv.org/abs/1801.01432) |
| Co-adaptation (Luck) | 2019 CoRL | Sim | Morphology parameters | SAC; Q-function used to estimate designs | Data-efficient design selection | Sim | Yes, MIT | [arXiv 1911.06832](https://arxiv.org/abs/1911.06832), [repo](https://github.com/ksluck/Coadaptation) |
| NGE | 2019 ICLR | Graph creatures (sim) | Graph topology + attributes | GNN policy, skills transferred between designs | Evolution with uncertainty-aware mutation | Sim | Yes, MIT | [arXiv 1906.05370](https://arxiv.org/abs/1906.05370) |
| RoboGrammar (MIT) | 2020 TOG | Modular legged (sim) | Graph-grammar rule sequence | Terrain traversal | Graph Heuristic Search | Grammar limits designs to "designs that can be fabricated"; sim only | Yes, MIT | [DOI](https://doi.org/10.1145/3414685.3417831), [repo](https://github.com/allanzhao/RoboGrammar) |
| Transform2Act | 2022 ICLR | MuJoCo creatures | Skeleton + joint attributes | PPO | Design steps folded into the RL episode | Sim | Yes, MIT | [arXiv 2110.03659](https://arxiv.org/abs/2110.03659) |
| Evolution Gym | 2021 NeurIPS | Soft voxel robots | Voxel grid | PPO per design | GA / BO / CPPN-NEAT baselines | Sim | Yes, MIT | [arXiv 2201.09863](https://arxiv.org/abs/2201.09863) |
| DiffAqua | 2021 SIGGRAPH | Soft swimmers | Wasserstein-barycentre shape | Differentiable simulation | Gradient-based | Sim | Yes, **no licence** | [arXiv 2104.00837](https://arxiv.org/abs/2104.00837) |
| BodyGen | 2025 ICLR | MuJoCo creatures | Topology + attributes | RL | Transformer design + control | Sim | Yes, Apache-2.0 | [arXiv 2503.00533](https://arxiv.org/abs/2503.00533), [repo](https://github.com/Josh00-Lu/BodyGen) |
| RoboMorph | 2024 | Modular legged/wheeled (sim) | Grammar text from GPT-4o | MJX + Brax SAC, head velocity | LLM evolution ("best-shot prompting") | None | Project page | [arXiv 2407.08626](https://arxiv.org/abs/2407.08626) |
| RoboMoRe | 2025 | MuJoCo tasks | Morphology + reward | RL | LLM coarse-to-fine + gradient updates | Sim | Not checked | [arXiv 2506.00276](https://arxiv.org/abs/2506.00276) |
| Debate2Create | 2025 | MuJoCo (Ant, Swimmer, …) | Fixed-topology parameters + reward | RL per candidate | Multi-agent LLM debate + LLM judges | Sim | Not checked | [arXiv 2510.25850](https://arxiv.org/abs/2510.25850) |
| LACE-CRAFT | 2026 | Locomotion benchmarks + 1 prototype | Morphology + reward | RL with inherited actor | Multi-role LLM "blackboard" | One printed prototype walked indoors | Repo, **no licence** | [arXiv 2610.09283](https://arxiv.org/abs/2610.09283) |
| Auto-Robotist | 2026 (EMNLP) | EvoGym | Voxel bodies | EvoGym | GA + LLM edits + natural-language skill library | Sim | Yes, MIT | [arXiv 2605.25832](https://arxiv.org/abs/2605.25832), [repo](https://github.com/wangyf9/Auto-Robotist) |
| Kawaharazuka, BBO + LLM | 2025 IEEE Access | 4-joint arm (URDF) | Base position, joint types, link lengths | IK error + gravity torque | Optuna multi-objective TPE + interleaved GPT-4o samples | Sim | Not reported | [arXiv 2511.17178](https://arxiv.org/abs/2511.17178) |
| LLMs for model-based design | 2026 | Quadcopter, line follower | Component selection | Explicit engineering model | LLM writes the model → multi-objective optimisation | Not reported | Not reported | [arXiv 2609.33423](https://arxiv.org/abs/2609.33423) |
| RobotDesignGPT | 2026 | Bio-inspired legged / flying | Kinematic design from prompt + image | VLM visual feedback; user study | VLM loop | Not reported | Not reported | [arXiv 2601.11801](https://arxiv.org/abs/2601.11801) |
| Eureka / DrEureka | 2023 / 2024 | 29 environments / quadruped | Reward code; DR ranges (DrEureka) | Isaac Gym RL | LLM evolutionary search over code | DrEureka: real quadruped | Yes, MIT | [arXiv 2310.12931](https://arxiv.org/abs/2310.12931), [arXiv 2406.01967](https://arxiv.org/abs/2406.01967) |
| Kriegman lab, manufacturable blueprints | 2026 | Evolved virtual robots | Abstract body → embedded motors, electronics, batteries, wiring | Not reported (abstract only) | Pipeline, not an optimiser | Builder-ready blueprints | Not reported | [arXiv 2603.13582](https://arxiv.org/abs/2603.13582) |
| DOA personalised limbed robots | 2026 npj Robotics | Limbed (Centaur built) | Motors, geometry, structural density | Not reported (abstract only) | A series of optimisation problems | 3D-printed, Centaur fabricated | Not reported | [DOI 10.1038/s44182-026-00101-3](https://doi.org/10.1038/s44182-026-00101-3) |
| MechStyle | 2025 | Printed objects (not robots) | Stylised geometry | **FEA stress** | Generative stylisation guided by stress | FDM | Not reported | [arXiv 2509.20571](https://arxiv.org/abs/2509.20571) |
| Sathuluri et al. | 2023 Robotics | Modular arms | Architecture, then structure | Dynamics-informed structural optimisation | Informed search + structural optimisation | 16 % lower structural mass than aluminium tubes | Not reported | [DOI 10.3390/robotics12040091](https://doi.org/10.3390/robotics12040091) |
| RoboGen (EPFL) | 2014 | Modular printed + servo bots | Body + neural controller | Physics sim | Evolution | 3D-printed parts, servos | Yes, **GPL-3.0** | [repo](https://github.com/lis-epfl/robogen) |
| Open Duck Mini v2 | 2024–26 | 42 cm servo biped | Hand design in Onshape | MuJoCo Playground imitation RL | Human iteration | PLA + STS3215 servos, BOM < $400 | Apache-2.0 (Playground: none) | [repo](https://github.com/apirrone/Open_Duck_Mini) |
| Upkie | 2022–26 | Wheeled biped, mjbots qdd100 | Hand design, parametric FreeCAD in v2 | PyBullet/MuJoCo Gym envs, MPC/PD/RL | Human iteration | FDM parts | Apache-2.0 | [repo](https://github.com/upkie/upkie), [parts](https://github.com/upkie/upkie_parts) |

Survey for more breadth: Wang et al., "Embodied Co-Design for Rapidly Evolving Agents" ([arXiv 2512.04770](https://arxiv.org/abs/2512.04770)) groups more than 100 studies into bi-level, single-level, generative and open-ended frameworks. Its paper list is at [Yuxing-Wang-THU/SurveyBrainBody](https://github.com/Yuxing-Wang-THU/SurveyBrainBody) (Apache-2.0).

---

## 3. Per-work notes

### 3.1 Computational design and co-design of legged and wheel-legged robots

**Disney BDX, "Design and Control of a Bipedal Robotic Character" (RSS 2024) [full text].** [arXiv 2501.05204](https://arxiv.org/abs/2501.05204)
- **Process.** The design loop was human, guided by animation:
  - an animation rig and a procedural gait tool produced joint positions, velocities and torques;
  - these fed "back into the mechanical design to refine geometry, select actuators, and perform structural analysis";
  - the stated aim was "a simple design which satisfies the creative intent" rather than an optimal one. It took less than a year.
- **Robot.** 5-DoF legs, no ankle roll (rounded soles give passive roll), 15.4 kg, 0.66 m tall.
- **Actuators.** Off-the-shelf actuators rated 34 N·m at 20 rad/s and 24 N·m at 30 rad/s. Printed parts join them.
- **Control.** PPO in Isaac Gym, batch 8192 envs × 24 steps, 100k iterations ≈ 22 days on an RTX 4090; 1,500 iterations (≈30 min) previews nominal behaviour.
- **Rewards.** Imitation terms plus regularisation (torque, acceleration, action rate) and a survival reward.
- **Actuator model.** PD law with encoder offset, velocity-dependent torque limits, friction, backlash, noise and reflected inertia, identified on a test bench.
- **Results.** 0.7 m/s walking and ≈10 h of public shows without falls.
- **What went wrong.** The jump hit the knee and head torque limits. Tracking velocity directly with the torso made the feet shuffle.
- **Code.** None released.
- **For wobbit:**
  - Copy the "30-minute preview policy" idea as the RL fidelity tier.
  - Copy the actuator-model structure.
  - Copy the reward structure, which Open Duck re-implemented successfully.
  - Feed the peak torques and the hop's torque saturation back into the design. BDX saturated in a jump, and wobbit's hop scenario should report saturation explicitly.

**Megaro et al. 2015, Coros, Thomaszewski: "Interactive Design of 3D-Printable Robotic Creatures" [abstract].** [Disney page](https://la.disneyresearch.com/publication/interactive-design-of-3d-printable-robotic-creatures/)
- **What it does.**
  - The user edits morphology (2, 4 or 5 legs, point or area feet, actuated spine) and proportions.
  - An optimisation-based motion solver keeps the motion stable for any design.
  - The tool generates fabrication blueprints automatically: printed parts plus off-the-shelf servos.
  - Six creatures were designed and validated in simulation and on printed prototypes.
- **Related work, same group.**
  - Walking automata (Bharaj et al. 2015), using simulation plus evolutionary optimisation ([page](https://la.disneyresearch.com/publication/computational-design-of-walking-automata/)).
  - Task-based limb optimisation (Ha et al. IROS 2016): two-stage optimisation of link lengths that minimises Σ torque² over jumping, walking and step-climbing; described as "preliminary" ([page](https://la.disneyresearch.com/publication/task-based-limb-optimization-for-legged-robots/)).
  - Adjoint co-design (Desai et al. 2018) ([arXiv 1801.00385](https://arxiv.org/abs/1801.00385)).
  - Optimal Design of Robotic Character Kinematics (Maloisel et al. TOG 2023): dynamic programming over design and control for robots with kinematic loops ([DOI](https://doi.org/10.1145/3618404)).
- **Code.** None released.
- **For wobbit:**
  - **The guide UX and the "blueprint" output** (BOM, printable parts, assembly sheet) are exactly what Megaro produced. Copy the pattern of editing in a parametric space with the motion re-solved after each edit.
  - Ha 2016's cost (Σ torque² across a task suite) is a cheap, sensible analytic-screen objective for leg lengths.

**Skaterbots (Geilinger, Poranne, Desai, Thomaszewski, Coros, SIGGRAPH 2018) and Geilinger, Winberg, Coros, "A Computational Framework for Designing Skilled Legged-Wheeled Robots" (RA-L 2020) [abstracts].** [DOI 10.1145/3197517.3201368](https://doi.org/10.1145/3197517.3201368), [DOI 10.1109/LRA.2020.2978444](https://doi.org/10.1109/LRA.2020.2978444)
- **What it does.**
  - Designers combine servos, 3D-printable connectors, wheels and feet.
  - Trajectory optimisation then generates walking, rolling, gliding and skating motions.
  - "motion-aware edits of the robot's physical structure" are user-guided, semi-automatic or fully automatic.
  - The 2020 paper builds a real legged-wheeled robot. It shows the framework "can accurately predict the way in which different design decisions affect the robot's ability to move", and adds a continuation-based warm start for the trajectory optimiser.
- **Relevance.** This is the most direct academic prior art for designing **legged-wheeled** robots computationally.
- **Code.** None found.
- **For wobbit.** The idea of a catalogue of components plus generated connectors matches the wobbit `catalog/` approach. Trajectory optimisation as an evaluator is a mid-fidelity option between LQR and RL.

**Ascento (Klemm et al., ICRA 2019) [full text].** [arXiv 2005.11435](https://arxiv.org/abs/2005.11435)
- **Robot.** Two-wheeled jumping biped, 10.4 kg, height adjustable from 31 to 66 cm.
- **Leg linkage.** A three-bar linkage optimised over **6 geometric parameters**, minimising mean-squared error to a straight vertical wheel path through the CoM. Decoupling jumping from pitch made a simple LQR plus feed-forward jumping controller enough.
- **Structure.**
  - Torsion springs offset gravity load on the hips.
  - Parts were designed with topology optimisation. The raw result was "impractical for post-processing steps and numerical analysis such as finite element method (FEM)" and was **redesigned manually** using it as a template.
  - Printed in SLS PA12.
- **Actuators.** ANYdrive hips (40 N·m peak); Maxon EC90 hub motors (3.5 N·m).
- **Later work.** Klemm, Mannhart and Siegwart, "Design Optimization of a Four-Bar Leg Linkage for a Legged-Wheeled Balancing Robot" (CLAWAR 2022), found via DBLP but not read.
- **For wobbit:**
  - Copy the **linkage-objective idea**: optimise leg geometry for a straight wheel path under the CoM, and for torque spread over the squat range.
  - Copy **gravity-compensating springs** as a design variable.
  - Note that topology optimisation needed a manual cleanup step. Automating that is hard, so prefer parametric ribs, wall thickness and infill as the structural variables.

**Bjelonic et al., "Learning-based Design and Control for Quadrupedal Robots with Parallel-Elastic Actuators" (RA-L 2023) [abstract].** [arXiv 2301.03509](https://arxiv.org/abs/2301.03509)
- **Method.** Train **one design-conditioned policy** with model-free RL, then run **BO** over the design using that policy as the evaluator. The design variable is the ANYmal knee parallel spring.
- **Results.** 33 % better torque-squared efficiency, 30 % lower peak joint torque, 11 % longer operation on flat ground.
- **Code.** None found.
- **Related work, same group.**
  - Belmonte-Baeza et al., meta-RL policy for optimising kinematics and actuator parameters ([arXiv 2210.02750](https://arxiv.org/abs/2210.02750)).
  - Bjelonic, Tischhauser and Hutter, IJRR 2025 ([arXiv 2509.06342](https://arxiv.org/abs/2509.06342)): a motor energy-loss model; "All code, models, and datasets are publicly available"; 32 % lower full CoT on ANYmal.
- **For wobbit.** **This is the core template for the RL tier.** Train one balance/drive/hop policy whose input includes the design vector (leg lengths, wheel radius, masses), then BO or CMA-ES over designs. Use the IJRR energy model for an electrical CoT that is realistic.

**Quadrupedal skating co-design (Wang, Fang, Hanna, Xiong, arXiv 2603.18408, ICRA 2026) [overview + abstract].**
- **Method.** A Go1 with printed passive-wheel mounts. BO with a GP proposes wheel yaw angles; PPO in Isaac Lab trains a policy for each design.
- **Metric.** CoT = ‖τ‖²/(mg‖ξ‖).
- **Results.** The 2-D design gave a further 14.6 % CoT reduction over the 1-D design. The optimiser found an asymmetric design that the policy exploits by turning around.
- **Hardware.** I could not confirm real-robot results.
- **For wobbit:**
  - This is the closest **RL co-design involving wheels**.
  - Note the pitfall: the optimiser found an asymmetric, direction-specific design. wobbit's scenario suite must command both directions, turning and reversing, or it will get "drives well only forwards" designs.

**Dinev et al., "A Versatile Co-Design Approach for Dynamic Legged Robots" (IROS 2022) [abstract].** [arXiv 2103.04660](https://arxiv.org/abs/2103.04660)
- **Method.** Bilevel optimisation in which motion-planning derivatives let an outer nonlinear program optimise morphology, payload distribution and actuator parameters under full dynamics, joint limits and friction cones. The result was a more energy-efficient Solo quadruped.
- **For wobbit.** Battery and electronics placement is a real design variable, as payload distribution here. Gradient-based co-design is possible if the controller is a differentiable trajectory optimiser, but that is overkill for v1.

**Vitruvio (ETH, 2020) [README].** [repo](https://github.com/leggedrobotics/vitruvio)
- **What it does.** Takes trajectories from the TOWR optimiser and computes the joint speed, torque, power and energy a given leg design needs. A GA then optimises link lengths, density and actuator choice from a list (ANYdrive, Neo, …).
- **Licence.** None. Read it, don't copy it.
- **For wobbit.** **This is the analytic-screen tier in its simplest form**: run reference motions (squat, hop, slope hold) through the inverse dynamics of each candidate, check against catalogue actuator torque–speed curves, and reject infeasible designs before any simulation.

**SERL / Wow Orin (Cheng et al., 2024) [full text].** [arXiv 2408.15632](https://arxiv.org/abs/2408.15632)
- **Method.** A GA (population 250) alternates with Isaac Gym RL to choose thigh and shin lengths for a 10.5 kg biped.
- **Results.** Longer shins than thighs were best for general locomotion. Reported CoT was 0.407 in a flat-ground simulation.
- **Structure.** Strength is asserted from material choice; **no FEA**; mass scaled with leg length at uniform density.
- **For wobbit.** This is a cautionary example. Uniform-density mass scaling and no stress check are exactly what wobbit should improve on: take masses from CAD and the slicer, and check stress.

**Rapid co-design of whegged robots (MiniRHex, 2024) [search snippet only].** [arXiv 2405.05096](https://arxiv.org/abs/2405.05096)
- BO over wheg lengths and thickness. The search snippet reports nearly twice the efficiency of the nominal platform in hardware; I did not open the paper.

### 3.2 Morphology–control co-design with RL in simulation: what transfers

**Schaff et al., "Jointly Learning to Construct and Control Agents" (ICRA 2018) [abstract].** [arXiv 1801.01432](https://arxiv.org/abs/1801.01432)
- Keeps a distribution over designs and trains one policy that receives the design parameters. Policy gradients move the distribution toward better designs.
- This is the ancestor of the design-conditioned policy, and the cheapest way to get co-design with one RL training run.

**Luck et al., Co-adaptation (CoRL 2019) [abstract].** [arXiv 1911.06832](https://arxiv.org/abs/1911.06832), [repo, MIT](https://github.com/ksluck/Coadaptation)
- Reuses earlier morphologies' data and the Q-function to estimate how new candidates will perform, which needs "drastically less design prototypes".
- Idea for wobbit: use the critic as a surrogate that screens candidates.

**NGE (ICLR 2019) [abstract], Transform2Act (ICLR 2022) [abstract], BodyGen (ICLR 2025) [abstract].**
- NGE: [arXiv 1906.05370](https://arxiv.org/abs/1906.05370), [repo, MIT](https://github.com/WilsonWangTHU/neural_graph_evolution). Graph evolution with a GNN policy that transfers skills.
- Transform2Act: [arXiv 2110.03659](https://arxiv.org/abs/2110.03659), [repo, MIT](https://github.com/Khrylx/Transform2Act). "Transform" steps are folded into the RL episode.
- BodyGen: [arXiv 2503.00533](https://arxiv.org/abs/2503.00533), [repo, Apache-2.0](https://github.com/Josh00-Lu/BodyGen). Topology-aware self-attention; reports a 60.03 % average gain over baselines.
- All three run on MuJoCo creatures made of capsules. **No hardware and no manufacturing constraints.**
- For wobbit: wobbit's topology is fixed (two legs plus two wheels), so graph-topology search is unnecessary. The ideas that do transfer are **policy sharing across designs** and **morphology-aware observations**.

**Evolution Gym (NeurIPS 2021) [abstract].** [arXiv 2201.09863](https://arxiv.org/abs/2201.09863), [repo, MIT](https://github.com/EvolutionGym/evogym)
- Soft-voxel benchmark with GA, BO and CPPN-NEAT baselines plus PPO.
- The authors report that "all tested algorithms fail to find robots that succeed in our hardest environments".
- Useful only as a benchmark for testing an LLM-plus-evolution optimiser before running it on wobbit, which is what Auto-Robotist did.

**DiffAqua (SIGGRAPH 2021) [abstract].** [arXiv 2104.00837](https://arxiv.org/abs/2104.00837), [repo, no licence](https://github.com/mit-gfx/DiffAqua)
- Uses a differentiable soft-body simulator, which makes gradient-based shape design possible.
- Not relevant to rigid wheel-legged robots, except as a reminder that interpolating shapes between a few base designs keeps the design space smooth.

**RoboGrammar (Zhao et al., TOG 2020) [abstract + README].** [DOI](https://doi.org/10.1145/3414685.3417831), [repo, MIT](https://github.com/allanzhao/RoboGrammar)
- A graph grammar of physical assemblies; "The construction of the grammar limits the design space to designs that can be fabricated".
- Graph Heuristic Search learns a value function over partial designs.
- RoboMorph reports RoboGrammar's search at 31 CPU-hours.
- For wobbit: **the idea of buildable-by-construction is the main lesson**. wobbit's version should be a typed parametric template with catalogue parts, not a free-form graph.

**Kriegman lab, "Creating manufacturable blueprints for coarse-grained virtual robots" (2026) [abstract].** [arXiv 2603.13582](https://arxiv.org/abs/2603.13582)
- **Explains why toy co-design does not transfer:** abstraction "swept away almost all of the physical details of functional body parts". Their pipeline embeds motors, electronics, batteries and wiring into the abstract design step by step to produce builder-ready blueprints.
- For wobbit: confirms the decision to search directly in a CAD-backed parametric space.

**What transfers to real, manufacturable robots, in summary:**
- policy sharing or conditioning across designs;
- BO, CMA-ES or GA as outer optimisers;
- grammars or catalogues that guarantee buildability;
- actuator system identification.

**What does not transfer:**
- free-form graph topologies;
- uniform-density capsule links;
- fitness based on forward velocity alone;
- simulators without actuator limits.

### 3.3 LLM- and agent-driven robot design

**Text2Robot (Ringel et al., Duke, ICRA 2025) [full text + README]: the closest analogue to wobbit.** [arXiv 2406.19963](https://arxiv.org/abs/2406.19963), [repo, Apache-2.0](https://github.com/generalroboticslab/Text2Robot), [project](http://generalroboticslab.com/Text2Robot/)

Pipeline:
1. A text prompt goes to Meshy text-to-3D. Meshes are filtered **manually** for one connected body, bilateral symmetry and four legs.
2. Fusion 360 scripts repair the mesh, convert it to a body and scale it to 6300 cm³.
3. Joints are placed by slicing: shoulder at the minimum cross-section, knee at the maximum cross-section 2 cm above the ground.
4. Servos go in printed snap-in boxes; the electronics box slides into a channel.
5. The design is exported to URDF.
6. Evolution keeps the top 100 designs and makes 100 new ones per generation (50 by mutation, 50 by crossover). Mutations change limb length, limb shape, body shape and joint axis, and are applied symmetrically.
7. Each design gets its own PPO training in IsaacGymEnvs: 4096 envs, 2.46×10⁷ steps, "a few minutes".
8. The design is printed in PLA on a CR-10 with 8 Hiwonder HTD-45H servos, an RPi 4 and a 3S LiPo, taking "about a day" to manufacture.

Results and gaps:
- **Fitness**: velocity tracking plus a joint-power penalty, with user weightings for speed or energy.
- **Real-world speed**: not reported. The paper says only "sufficient performance".
- **No stress analysis** and no cost model.
- **Limitations**: quadrupeds only; manual mesh selection; the text-to-3D step gets no feedback from the optimiser; arched feet snag on rough terrain.
- **RoboGrammar baseline**: designs often had badly placed joints and limbs too close together.

For wobbit, reuse:
- the **modular electronics and servo pods** that fit any body;
- the **symmetric mutation operators**;
- the **"few minutes of PPO per design" budget** as a per-candidate cap;
- the **Apache-2.0 evolutionary driver** (`Evolutionary_Algorithm/driver.py`) as reference code.

Do not copy:
- the mesh-first approach. wobbit's mechanics are parametric CadQuery, so text should map to **parameters and styling**, not raw meshes.

**RoboForge, "Agentic Robot Creation through Generation, Verification, and Revision" (Li et al., Oct 2026) [full text].** [arXiv 2610.17881](https://arxiv.org/abs/2610.17881), [project](https://roboforge-project.github.io/)

How it works:
- An LLM (the paper names "GPT-6 Astra" and three GPT-5.x variants) generates a robot from a reference image, task text and actuator CAD. The output has three forms: **STEP** for editing, **STL** for printing, and **URDF** for simulation.
- **23 computational pre-fabrication checks** in three groups:
  - *Design and assembly*: single solid with positive volume, watertight, fits the build volume, mounting holes and tool access, worst-case tolerance clearance, insertion paths, fasteners, intersections.
  - *Mechanical and actuation*: "structural screening against an assumed allowable stress", load paths, mass reconciliation, fastener length chains, joint-limit margins, cable clearance through the full range of motion.
  - *Motion and task*: consistent joint and inertial model, collision-free motion, tracking error, torque saturation, limit violations, clearance under tracking error.

Results:
- Checks passed by the best model: 6/10, 4/6 and 5/7. Older models passed 0–1 of the mechanical checks.
- Recurring failures: missing mounting features, self-intersections, too little actuator clearance. The authors **fixed the rest by hand** before printing.
- Behaviour pipeline: the agent writes a reference motion, uses DeepMimic-style tracking rewards, and trains in Isaac Lab with RSL-RL PPO (4096 envs). Rollouts are diagnosed so the motion, the reward or both can be revised (at most 3 trials).
- User rating 3.97 vs 2.10 for an Eureka-style baseline.
- The Gorilla was printed in PLA on a Bambu X1E (0.2 mm, 15 % infill) with 8 × XL330 servos, and policies were deployed zero-shot. No quantitative hardware results were reported.
- No code repo found.

For wobbit:
- **Copy the 23-check list almost verbatim** as wobbit's manufacturability and validity gate. It is the most complete published checklist.
- Copy the **diagnose-then-revise** structure: attribute each failure to geometry, control target or reward before changing anything.
- Their PLA, Bambu, 15 % infill setup matches wobbit's first manufacturing target.

**RoboMorph (Qiu et al., 2024; listed as ICRA by Semantic Scholar) [full text].** [arXiv 2407.08626](https://arxiv.org/abs/2407.08626), [project](https://robomorph.github.io)
- **Method.** GPT-4o writes designs in a RoboGrammar-derived grammar, which a compiler checks. Each valid design gets a SAC policy (Brax) in MuJoCo MJX. The top-3 designs come back as few-shot examples **without their fitness scores**; showing scores made the LLM overfit.
- **Setup.** Population 32, 50 generations.
- **Cost.** ≈200 A100 GPU-hours per seed.
- **Failure modes.** Grammar violations, designs that compile but cannot move, and convergence when the prompt lacks diversity. No hardware.
- **For wobbit.** Use a compiler or validator in front of the LLM. Keep the history fed back to the LLM diverse. Expect GPU cost to dominate unless training is amortised.

**RoboMoRe (2025), Debate2Create (2025), LACE-CRAFT (2026) [abstracts].** [arXiv 2506.00276](https://arxiv.org/abs/2506.00276), [arXiv 2510.25850](https://arxiv.org/abs/2510.25850), [arXiv 2610.09283](https://arxiv.org/abs/2610.09283)
- **RoboMoRe** optimises morphology and **reward** together, because a fixed reward makes all morphologies converge to one motion style.
- **Debate2Create** uses design and control agents plus criterion-specific LLM judges. It reports up to 3.2× on Ant and 18–35 % gains over zero-shot generation at matched compute.
- **LACE** continues training from the incumbent's actor instead of retraining. CRAFT uses roles (Feedback, Morphology, Reward, Integration) sharing a common record. One printed prototype walked.
- All of these are MuJoCo benchmark bodies.
- **For wobbit.** Multi-objective **LLM judges** fit the guide's "any specs" requirement. **Actor inheritance** is a cheap form of amortisation.

**Auto-Robotist (EMNLP 2026) [abstract].** [arXiv 2605.25832](https://arxiv.org/abs/2605.25832), [repo, MIT](https://github.com/wangyf9/Auto-Robotist)
- Distils search traces into a **natural-language skill library**: archetypes, rules backed by evidence, and the designs that support them. The GA keeps a mutation path for exploration.
- **For wobbit.** This is a good pattern for "iterate without a human": the agent accumulates auditable design rules. It also suits wobbit's existing habit of writing lessons into files.

**Kawaharazuka et al., BBO + LLM (IEEE Access 2025) [full text].** [arXiv 2511.17178](https://arxiv.org/abs/2511.17178)
- **Method.** Optuna multi-objective TPE does most of the sampling. Every 10th sample comes from GPT-4o, which is shown random Pareto and non-Pareto results with per-target errors and torques.
- **Results.** Hypervolume improved, e.g. 6.70 → 10.25 on one target set, and variance was lower.
- **Limitations.** Gains depend on the task; the LLM rounds values off; spatial reasoning is weak. The test problem was a simple 4-joint arm.
- **For wobbit.** **This is the safest way to add an LLM to the optimiser**: as a proposal operator interleaved with a proper BBO, never as the only optimiser.

**Wilhelm, Zhou, Napp, "LLMs for Model-Based Robot Design" (2026) [abstract].** [arXiv 2609.33423](https://arxiv.org/abs/2609.33423)
- The LLM writes an **explicit engineering model** (physical relations, compatibility constraints, objectives). People inspect and revise it before formal multi-objective optimisation.
- Direct LLM designs: 0 of 30 could be verified as feasible.
- **For wobbit.** The wobbit guide should turn user intent into an explicit, inspectable spec and constraint model, for example `designer/spec.yaml`, before any optimisation.

**Eureka (ICLR 2024) and DrEureka (2024) [abstracts].** [arXiv 2310.12931](https://arxiv.org/abs/2310.12931), [repo, MIT](https://github.com/eureka-research/Eureka); [arXiv 2406.01967](https://arxiv.org/abs/2406.01967), [repo, MIT](https://github.com/eureka-research/DrEureka)
- **Eureka** runs LLM evolutionary search over reward code. It beat human rewards on 83 % of 29 tasks, with an average normalised improvement of 52 %.
- **DrEureka** also writes the **domain-randomisation ranges** and transfers to a real quadruped, including walking on a yoga ball.
- **For wobbit.** Use these for the *controller-side* automation, such as new scenario rewards (curb, hop) and DR ranges, not for morphology.

**RobotDesignGPT (2026) [abstract]**, **Lang2Morph (2025, robotic hands, not read; [arXiv 2509.18937](https://arxiv.org/abs/2509.18937))**, **DOA personalised limbed robots (npj Robotics 2026) [abstract].**
- RobotDesignGPT: [arXiv 2601.11801](https://arxiv.org/abs/2601.11801). A VLM uses visual feedback to make designs "visually appealing and kinematically valid".
- DOA: [DOI 10.1038/s44182-026-00101-3](https://doi.org/10.1038/s44182-026-00101-3). Text or image → **selected motors + 3D-printable parts** through optimisation over "actuators, geometry, and structural density"; a Centaur was fabricated. Full text was paywalled, so details are not reported here.
- **For wobbit.** DOA is worth reading in full when access allows. It is the only LLM-era pipeline I found that names structural density as an optimised quantity.

### 3.4 Printed robots with structural constraints (FEA, strength, anisotropy)

What I found is thin. This part of the loop is not well covered in the robotics literature.

- **Ascento** (above). Topology optimisation was used as inspiration and the result redesigned by hand. Parts were SLS PA12, which is near-isotropic, unlike FDM PLA.
- **Upkie** ([reference-robots.md](reference-robots.md), FOSDEM 2026 transcript). **Printed femurs and tibias broke.** v2's fork-shaped lower leg is "much stiffer". FreeCAD was adopted so leg lengths could be changed. Optional bearing supports protect the knee actuators from radial load ([upkie_parts](https://github.com/upkie/upkie_parts)).
- **MechStyle (2025)** [abstract] ([arXiv 2509.20571](https://arxiv.org/abs/2509.20571)). FEA feedback limits generative geometry changes in regions with high stress. For wobbit: this is the pattern for "styling" from the guide. Cosmetic shell changes must not touch high-stress regions of load-path parts.
- **Sathuluri et al. 2023** [abstract] ([DOI](https://doi.org/10.3390/robotics12040091)). Architecture search, then **dynamics-informed structural optimisation**, giving 16 % less structural mass than aluminium tubes. This is the two-step pattern wobbit should copy: loads from simulation, then structural sizing.
- **Li 2026, strain-energy distribution** [abstract] ([arXiv 2608.29146](https://arxiv.org/abs/2608.29146)). Claims that in an optimal lightweight system the strain energy per unit mass is uniform. That lets a system-level problem be split into per-part optimisations. For wobbit: a cheap global check is to flag parts whose strain energy per gram is far above or below the median.
- **Berkeley Humanoid Lite (RSS 2025)** [abstract] ([arXiv 2504.17249](https://arxiv.org/abs/2504.17249), [repo, MIT](https://github.com/HybridRobotics/berkeley-humanoid-lite)). Printed cycloidal gearboxes with "extensive testing … to validate their durability". **ToddlerBot** ([arXiv 2502.00893](https://arxiv.org/abs/2502.00893), [repo, MIT](https://github.com/hshi74/toddlerbot)) is entirely 3D-printed, costs under $6k and was replicated independently. Both show that printed robots work when parts are tested; neither puts FEA in a design loop.
- **RoboGen (EPFL, 2014)** ([repo, GPL-3.0](https://github.com/lis-epfl/robogen)). Evolution of body and brain with 3D-printable parts and servos, used in teaching. No structural analysis that I could find.
- **Stress Relief (Stava et al., SIGGRAPH 2012)** is the classic graphics paper on automatically reinforcing printed objects against stress. Its ≈200 citations are mostly graphics and printing work, not robots. **I found no robotics paper that handles FDM anisotropy (weak Z / interlayer strength) inside a design loop.** wobbit will have to set its own derating; see section 4.4.

### 3.5 Open Duck Mini, Microduck and Upkie: design → sim → real in practice

Robot details are in [reference-robots.md §2 and §5](reference-robots.md). Only the iteration loop is summarised here.

**Open Duck Mini v2** ([repo, Apache-2.0](https://github.com/apirrone/Open_Duck_Mini); [sim2real.md](https://github.com/apirrone/Open_Duck_Mini/blob/main/docs/sim2real.md))

The loop:
1. Design in Onshape.
2. Export URDF/MJCF with [onshape-to-robot](https://github.com/Rhoban/onshape-to-robot) (MIT).
3. **Override part masses with slicer estimates**, because printed parts have infill.
4. Identify the STS3215 servos with [BAM](https://github.com/Rhoban/bam) (Apache-2.0) and export damping, kp, frictionloss, armature and forcerange to MuJoCo.
5. Generate reference gaits with a parametric walk engine.
6. Train imitation RL in MuJoCo Playground "implementing the imitation reward described by Disney in their BDX paper".
7. Deploy ONNX on a Pi Zero 2W.

The mechanical design was declared "pretty much finalized" in January 2025 before RL began, so there was **no automatic design feedback**. Iteration was human, driven by sim2real failures.

**Microduck** (Pollen, 2026): the same toolchain on mjlab, with voltage sag and backlash modelled. The author notes that actuator fidelity is "most of the sim2real gap".

For wobbit, copy:
- onshape-to-robot-style export, which in wobbit is CadQuery → URDF/MJCF;
- **slicer-derived masses**;
- BAM-style actuator identification;
- imitation rewards for squat and hop motions.

**Upkie** ([repo, Apache-2.0](https://github.com/upkie/upkie))
- The same Gymnasium API serves PyBullet simulation and the real robot. Changing `PyBullet` to `Spine` in the env name deploys.
- Built-in MPC and PD balancers, with RL through mjlab.
- Iteration lessons: printed legs broke; parametric CAD made leg-length changes possible; one shared code path for robot, sim and RL was "too greedy" and was split.

For wobbit:
- Upkie is the **open baseline wheel-legged biped**.
- Its pendulum env and MPC balancer are ready-made **tier-1 evaluators**.
- Its parts list is a sanity check for wobbit's printable-leg FEA. Check whether wobbit's FEA would have predicted the Upkie v1 tibia failure.

---

## 4. Recommended architecture for wobbit's loop, built on prior work

### 4.1 Design representation: buildable by construction

Following RoboGrammar, Text2Robot, Skaterbots and the Kriegman blueprints work, the optimiser never sees free-form geometry. It sees a **typed parametric template** that CadQuery always turns into a buildable assembly.

| Group | Variables | Type | Notes / source |
|---|---|---|---|
| Topology | Leg type: serial 2-link (Upkie), parallel/5-bar (Diablo-like), Ascento-style linkage | categorical | Small fixed set, each with its own CadQuery generator |
| Actuators | Hip and knee motor SKU, wheel motor SKU (from `catalog/`) | categorical | Vitruvio-style list with torque–speed curves, mass, cost, BAM-style parameters |
| Kinematics | Thigh and shin length, hip width, hip offset, knee range | continuous | SERL/Ha 2016/Chen 2024 show leg length ratios matter |
| Wheels | Radius, width, tyre SKU | mixed | Ascento and Upkie both found wheel radius to be a main parameter |
| Mass layout | Battery SKU and position, electronics bay position | mixed | Dinev 2022 payload distribution |
| Compliance | Gravity-compensation spring stiffness and preload (optional) | continuous | Ascento torsion springs; Bjelonic PEA |
| Structure | Wall/shell count, infill, rib thickness, fork vs single-plate leg, print orientation per part, material (PLA → PLA-CF/PETG-CF → sheet metal/CF tube) | mixed | Upkie fork; Ascento topology optimisation; this is how FEA results become design changes |
| Style | Shell shape, colours, "character" parts | free, but only on non-structural shells | MechStyle: styling must not touch high-stress load paths |

The guide writes an **explicit spec and constraint file** (Wilhelm 2026): payload, max size, budget, target speed, slope, curb height, hop height, runtime. Every optimiser run reads only that file, so the human or agent can audit what was asked for.

### 4.2 Evaluation suite: scenarios and metrics

Every scenario must log **per-joint torque, speed and power time series, contact forces, and link wrenches**. The wrenches are what feed FEA, and none of the papers above export them. Run each scenario across commanded directions; the skating paper's optimiser exploited a one-way design.

| Scenario | Pass/fail | Continuous metrics | Loads exported for FEA |
|---|---|---|---|
| Static stand and squat sweep (min to max height) | Torque < continuous rating at every height | Hip/knee holding torque vs height; thermal margin (RMS torque / continuous) | Static link wrenches at the worst height |
| Balance at rest with sensor noise | No fall in 60 s | Pitch RMS, wheel torque RMS | Not needed |
| Push recovery (impulse ramp, front/back/side) | Survives impulse ≥ spec | Max survivable impulse (N·s), recovery time, peak wheel torque | Peak wrenches during recovery |
| Drive: velocity steps, turns, reversing | Tracking error < spec | Speed tracking RMS, max speed, yaw-rate tracking, electrical CoT (Bjelonic IJRR energy model) | Not needed |
| Slope hold and climb (e.g. 5–20°) | Holds the spec slope | Max slope held and climbed, wheel torque margin | Wheel and hub loads |
| Curb / step (drive-up or leg-lift) | Clears the spec height | Max step height | Impact wrenches |
| Hop and landing | Reaches the spec hop height | Jump height, **torque saturation fraction** (BDX hit limits here), landing peak force | **Landing peak wrenches, the main FEA load case** |
| Fall onto the side or front (unpowered) | No part exceeds allowable stress (checked in FEA) | Impact velocity, peak contact force | Impact load case, which Upkie's broken legs suggest is the real killer |
| Domain-randomised repeat of all the above | Pass rate ≥ X % | Pass rate across mass ±10 %, CoM ±, friction, actuator parameters (Open Duck ranges) | Not needed |

Objectives are reported as a **Pareto set**, not one weighted sum: capability margins, mass, cost, print time, worst FEA safety factor and CoT. LLM judges (Debate2Create) can rank the Pareto set against the user's stated priorities, but they never replace the numbers.

### 4.3 Optimiser: multi-fidelity, with amortised control

```
Tier 0  analytic screen   ~10^4 candidates, ms each
        - catalogue compatibility, mass budget, bed fit
        - inverse dynamics of reference motions (Vitruvio / Ha 2016 Σtorque²)
        - static squat and slope torque vs actuator curves, wheel torque for slope
        - linearised wheeled-pendulum LQR: stabilisable? (Ascento/Upkie model)
Tier 1  model-based sim   ~10^2-10^3, seconds each
        - MuJoCo with an LQR/MPC balancer (Upkie MPC as reference), no training
        - full scenario suite except hop/curb, or with scripted hop
Tier 2  design-conditioned RL   one training run per design *family*
        - single policy with the design vector as input (Schaff 2018; Bjelonic 2023)
        - pretrain over the design distribution, fine-tune finalists (Chen 2024; RoboCraft; LACE inheritance)
        - preview budget ~30 min per fine-tune (BDX "preview" idea); full training only for the final design
Tier 3  structural + manufacturing   ~10, minutes each
        - loads from tiers 1-2 → CadQuery parts → FEA (linear static, worst load cases), derated for FDM
        - RoboForge-style 23-check gate, slicer mass + print time + cost
Tier 4  hardware   1-3 builds
        - BAM-style actuator ID, sim-vs-real comparison, update the actuator models, re-run tiers 1-3
```

Outer search:
- **Continuous variables**: CMA-ES or BO. SurGE shows that CMA-ES plus surrogate gradients reduces seed variance, and its trend held on hardware.
- **Mixed or categorical variables**: Optuna multi-objective TPE, which Kawaharazuka used.
- **Topology categories**: one search per category, with no cross-topology crossover.

LLM role, following Kawaharazuka, Auto-Robotist and Wilhelm:
1. Turn the user's intent into the explicit spec.
2. Propose about every 10th sample from the Pareto history.
3. Diagnose failures (RoboForge: geometry, target or reward?).
4. Keep a natural-language rule library learned from runs (Auto-Robotist).
5. Write scenario rewards and DR ranges (Eureka/DrEureka).

The LLM is **never** the only optimiser and **never** skips the deterministic checks.

Pass candidates up a tier only when they are within a margin of the current Pareto front. Keep a priority buffer that re-evaluates promising candidates at higher fidelity (RoboCraft).

### 4.4 Keeping it manufacturable

1. **Buildable by construction.** CadQuery generators only emit assemblies made from catalogue parts, with fastener bosses, tool access and cable channels built in. This avoids RoboForge's top failures: missing mounts, self-intersections and actuator clearance.
2. **Deterministic gate: the RoboForge checklist.** Single watertight solids, fit on the P1S 256 mm bed, insertion paths, tolerance stack-up, fastener length chains, joint-limit margins, clearance through the full range of motion and under tracking error, and mass reconciliation (CAD vs slicer vs URDF).
3. **Masses from the slicer** (Open Duck), not uniform density (SERL). Re-export URDF/MJCF inertials after every structural change.
4. **FEA with FDM derating.** No robotics source I found does this, so it must be set and validated by wobbit:
   - treat each part as transversely isotropic or apply a Z-direction knock-down to allowables;
   - make print orientation a design variable;
   - use separate safety factors for the static squat, hop landing and fall impact cases.
   - Calibrate on hardware: break-test a few printed coupons and one leg. Also check that the FEA would have predicted Upkie v1's tibia break.
5. **Strain energy per gram** (Li 2026) as a cheap system-level indicator of which part to slim or stiffen next.
6. **Cost and time.** BOM from the catalogue, plus filament grams and print hours from the slicer, plus hardware. Later, SendCutSend sheet metal and CF tubes come in as alternative implementations of the same structural variables.

### 4.5 Pitfalls others hit, and how to avoid them

| Pitfall | Who hit it | Mitigation in wobbit |
|---|---|---|
| Optimiser exploits the simulator or actuator model | General co-design; BDX/Open Duck/Microduck say actuator fidelity dominates the gap | BAM-style actuator ID; torque–speed limits, friction, backlash, voltage sag in sim; DR on actuator parameters |
| One-directional or narrow-task designs | Quadruped skating (asymmetric wheel angles) | Scenario suite covers reverse, turns, sideways pushes |
| Fixed reward makes all morphologies converge | RoboMoRe | Per-scenario rewards, Eureka-tuned where needed; imitation targets for squat and hop |
| RL cost explodes | RoboMorph 200 GPU-h/seed; BDX 22 days/policy | Tier 0/1 model-based screening; design-conditioned policy; fine-tune only finalists |
| LLM designs are infeasible | RoboForge; Wilhelm 0/30 | LLM edits parameters of a validated template; deterministic gate; Kawaharazuka-style interleaving |
| LLM overfits to fitness numbers | RoboMorph (scores removed from prompt) | Show diverse elites and rules, not raw score tables only |
| Uniform-density masses, no stress check | SERL; Text2Robot | Slicer masses; FEA tier |
| Printed legs break under impact | Upkie v1 | Fall/landing load cases; fork or closed-section leg templates; bearing supports for radial loads |
| Topology optimisation output not buildable | Ascento (manual redesign) | Parametric ribs and sections instead of free topology optimisation; topology optimisation only as a hint |
| Mesh-first generative designs need manual repair | Text2Robot (manual filtering, Fusion repair) | Parametric CadQuery first; text drives parameters and shell styling only |
| Toy sims never become robots | Kriegman 2026 critique of the virtual-creature literature | Search only in the CAD-backed template space |
| One code path for sim, test and RL is "too greedy" | Upkie | Separate the eval harness from the training envs; share only the robot model and actuator models |

### 4.6 Concrete reuse list (with licences)

| Reuse | What for | Licence |
|---|---|---|
| [Text2Robot](https://github.com/generalroboticslab/Text2Robot) evolutionary driver and modular electronics pods | Reference EA loop and per-design PPO budget | Apache-2.0 |
| RoboForge check taxonomy ([arXiv 2610.17881](https://arxiv.org/abs/2610.17881)) | Manufacturability and validity gate | Paper only; reimplement |
| Bjelonic 2023 design-conditioned RL + BO ([arXiv 2301.03509](https://arxiv.org/abs/2301.03509)); IJRR 2025 energy model ([arXiv 2509.06342](https://arxiv.org/abs/2509.06342)) | Tier-2 method; electrical CoT | Method; IJRR code said to be public (repo not checked) |
| [SurGE](https://github.com/ARCaD-Lab-UM/surge-codesign) | CMA-ES with surrogate gradients for leg and spring parameters | MIT |
| Optuna multi-objective TPE + LLM interleaving (Kawaharazuka) | Mixed-variable outer loop | Method |
| [Eureka](https://github.com/eureka-research/Eureka) / [DrEureka](https://github.com/eureka-research/DrEureka) | Scenario rewards and DR ranges | MIT |
| [Auto-Robotist](https://github.com/wangyf9/Auto-Robotist) | Design-rule memory for the agent | MIT |
| [BAM](https://github.com/Rhoban/bam) | Actuator identification → MuJoCo parameters | Apache-2.0 |
| [onshape-to-robot](https://github.com/Rhoban/onshape-to-robot) | Reference for CAD → URDF/MJCF export conventions (closing loops, inertials) | MIT |
| [MuJoCo Playground](https://github.com/google-deepmind/mujoco_playground) | GPU RL envs | Apache-2.0 |
| [Upkie](https://github.com/upkie/upkie), [upkie_description](https://github.com/upkie/upkie_description), [upkie_parts](https://github.com/upkie/upkie_parts) | Baseline robot, MPC/PD balancers, failure case for FEA validation | Apache-2.0 |
| BDX reward and actuator-model structure ([arXiv 2501.05204](https://arxiv.org/abs/2501.05204)), as reimplemented in [Open_Duck_Playground](https://github.com/apirrone/Open_Duck_Playground) | Imitation rewards for squat and hop | Paper; Playground has **no licence**, so reimplement |
| [RoboGrammar](https://github.com/allanzhao/RoboGrammar) | Reference for grammar and value-guided search | MIT |
| [Vitruvio](https://github.com/leggedrobotics/vitruvio) | Reference for the analytic screen | **No licence**; read only |
| [RoboGen](https://github.com/lis-epfl/robogen) | Historical reference | **GPL-3.0**; don't copy code |

### 4.7 Open questions this research could not settle

- Whether any paper does RL-based co-design of a **wheel-legged biped** specifically. None was found in the citation graphs of Ascento, Skaterbots/Geilinger, or the RL co-design papers, but the web-search budget ran out early. Re-run a targeted search ("wheel-legged" + "co-design"/"morphology optimization", 2025–2026) when the budget refills.
- FDM-anisotropy-aware structural optimisation for robot links: no robotics source found. Check the additive-manufacturing literature and Bambu's PLA/PLA-CF technical data sheets for Z-direction allowables.
- Full text of the DOA npj Robotics 2026 paper (paywalled) and of Klemm et al. CLAWAR 2022 (the four-bar leg optimisation for a legged-wheeled balancing robot).
