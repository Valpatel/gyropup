# Prior art: the toolchain wobbit should build on

Research date: 2026-10-25. Stars, licences and "last push" dates come from the GitHub API on that date. PyPI versions and release dates come from `pypi.org/pypi/<name>/json` on that date. Where a capability could not be confirmed from a repo, its docs or a local test, the text says **not documented** or **not verified**. Some behaviour was checked locally against the wobbit venv (Python 3.12.3, MuJoCo 3.17.0, CadQuery 2.8.0, RTX 3080 12 GB, driver 580.178.04, Ubuntu 24.04). Those results are marked **(tested locally)**.

The wobbit loop this survey serves: parametric design → CadQuery CAD → URDF + MJCF with CAD mass properties → scenarios (balance, push, drive, slope, curb, squat, hop) with a baseline controller → loads → FEA of printed parts → manufacturability and cost → optimiser or agent → repeat. Later: RL in Isaac Lab, deployed to a Jetson AGX Orin 32 GB.

---

## Executive summary

1. **Nobody has built a CadQuery/build123d → URDF/MJCF exporter worth adopting.** GitHub searches for "cadquery urdf", "build123d urdf", "cadquery mujoco" and "build123d mujoco" turned up only one zero-star hobby repo. All the mature exporters are tied to a GUI CAD tool: [onshape-to-robot](https://github.com/Rhoban/onshape-to-robot) (Onshape), [fusion2urdf](https://github.com/syuntoku14/fusion2urdf), [solidworks_urdf_exporter](https://github.com/ros/solidworks_urdf_exporter), [phobos](https://github.com/dfki-ric/phobos) (Blender) and [freecad.cross](https://github.com/galou/freecad.cross). So **keep our own small writer**, but:
   - build the MJCF with MuJoCo's official `mujoco.MjSpec` API rather than XML strings;
   - copy onshape-to-robot's conventions: `closing_*` loop markers become MJCF `<equality>`, plus `joint_properties`, `geom_properties`, frames as sites, and a generated `scene.xml`;
   - gate every URDF with the vendored `cadgen urdf validate`;
   - hand the Isaac side to NVIDIA's own converters, `urdf-usd-converter` and `mujoco-usd-converter`. Isaac Sim 6's importers are built on them.
2. **Closest existing robot: Upkie.** [Upkie](https://github.com/upkie/upkie) (Apache-2.0) is an open wheeled biped with exactly wobbit's joints: hip, knee and wheel per leg. It comes with a PD/MPC balancer and an RL velocity task in **mjlab** ([MarcDcls/mjlab_upkie](https://github.com/MarcDcls/mjlab_upkie), Apache-2.0). This is the nearest template for both the baseline controller and RL.
3. **Fastest path to "load a generated robot and score it on a drive course": plain MuJoCo 3.17 on the CPU, which is already installed**, plus our own scenario harness and an LQR/VMC baseline. Port the LQR from Upkie's examples, or from the RoboMaster "balance infantry" pattern (LQR gains fitted as a function of leg length, see [RP_Balance](https://github.com/WilliamGwok/RP_Balance), MIT). No simulator framework currently ships a wheel-legged scenario suite we could reuse.
4. **Fastest path to RL: [mjlab](https://github.com/mujocolab/mjlab)** (Apache-2.0, pip, Python 3.10–3.13). It is Isaac Lab's manager-based API running on MuJoCo Warp, so it trains on the same MJCF the evaluation loop uses, with no USD conversion step. **Isaac Lab 3.0** ([released 2026-10-20](https://github.com/isaac-sim/IsaacLab/releases/tag/v3.0.0)) now has the same API on a Newton/MuJoCo-Warp backend, with Isaac Sim optional. That gives a clean upgrade path for rendering, sensors and the Isaac Sim tooling later. Note that Isaac Lab 3.0 targets Isaac Sim **6.2**, while we have 6.0.
5. **Actuators: model them at the MuJoCo layer, not in our own code.**
   - MuJoCo now has a native `<dcmotor>` actuator (3.7.0), with electrical dynamics, cogging, LuGre friction and a **winding-temperature state**. That last one is exactly what the Diablo "15 min squat" limit needs.
   - MuJoCo also has actuator delays (3.5.0) and a system-identification toolbox (3.5.0). MuJoCo Warp supports `dcmotor` and the delay history.
   - mjlab and Isaac Lab both ship a linear torque–speed `DcMotor` model, delay models and learned actuator nets. Isaac Lab adds a `BamActuator` on the Newton backend only.
   - [BAM](https://github.com/Rhoban/bam), which Open Duck Mini uses, identifies extended friction models. Its model library covers only Dynamixel, Feetech and eRob, not CubeMars, Robstride or Damiao.
6. **FEA in the loop: `gmsh` (pip) for meshing plus `scikit-fem` (pip, BSD-3, only numpy and scipy) for fast linear-elastic screening.** Use **CalculiX** (`apt install calculix-ccx`, GPL-2.0) as the high-fidelity check. It supports orthotropic printed-part materials (`*ELASTIC, TYPE=ENGINEERING CONSTANTS`) and contact. Loads come from MuJoCo `force`/`torque` sensors placed on sites at each joint, or from `efc_force` for loop-closure constraints.
7. **Optimiser: Optuna 5.0** (MIT, September 2026) is the orchestrator. It handles categorical and conditional component choices, multi-objective search (TPE is now the default there), a first-class `trial.set_constraint()`, a stable `GPSampler` with qLogEHVI, and shared storage for parallel workers. One catch: Optuna's pruning (its multi-fidelity mechanism) **does not work for multi-objective studies**. We run multi-fidelity as staged evaluation with early rejection, and keep BoTorch MOMF (multi-objective multi-fidelity) or SMAC3 as the upgrade. Use pymoo NSGA-II on the cheap analytic model and pycma for controller gains.
8. **Web: a static three.js page.**
   - [urdf-loader](https://github.com/gkjohnson/urdf-loaders) draws the robot.
   - A JSON qpos trajectory replays the sim run. MuJoCo's **official** WASM bindings (`@mujoco/mujoco` on npm, Apache-2.0) can replay or re-simulate in the browser instead.
   - GLB meshes with baked vertex colours show stress.
   - **Rerun** `.rrd` files, embedded with `@rerun-io/web-viewer`, cover engineering debugging.
   - Avoid Foxglove: the open-source repo is archived and the product is now proprietary.

---

## 1. CAD → robot description

### 1.1 Comparison

| Tool | What it does | Licence | Stars / last push | Maturity | Fit for wobbit |
|---|---|---|---|---|---|
| [Rhoban/onshape-to-robot](https://github.com/Rhoban/onshape-to-robot) ([docs](https://onshape-to-robot.readthedocs.io/en/latest/)) | Onshape assembly → URDF, SDF or MuJoCo via the Onshape API. MuJoCo export: "Actuators will be created for all actuated joints"; frames become `site`s; loops marked by mates named `closing_*` become `<equality>` (fixed→`weld`, ball→`connect`, revolute→two `connect`s) ([kinematic loops](https://onshape-to-robot.readthedocs.io/en/latest/kinematic_loops.html), [MuJoCo exporter](https://onshape-to-robot.readthedocs.io/en/latest/exporter_mujoco.html)); also writes `scene.xml`. Loop export for URDF/SDF: **not documented**. | MIT | 642 / 2026-08-26 (PyPI 1.8.3) | Mature; used by Open Duck Mini ([prepare_robot.md](https://github.com/apirrone/Open_Duck_Mini/blob/v2/docs/prepare_robot.md): "design you robot according to onshape-to-robot constraints") | **Cannot be used directly** (Onshape only). **Copy its config schema and loop conventions.** |
| CadQuery/build123d-based URDF/MJCF generators | GitHub searches ("cadquery urdf", "build123d urdf", "cadquery mujoco", "build123d mujoco") returned nothing relevant; one 0-star build123d robot ([cogu](https://github.com/laroccathebrux/cogu)) | — | — | None exist | Keep our own writer |
| `mujoco.MjSpec` (in [MuJoCo](https://github.com/google-deepmind/mujoco)) | Official Python API to build and edit models programmatically, then compile and save as MJCF. Also loads URDF (`MjSpec.from_file("model.urdf")`, [changelog 3.7.0](https://github.com/google-deepmind/mujoco/blob/main/doc/changelog.rst)) | Apache-2.0 | 15,876 / 2026-10-25 (3.17.0) | Core API | **Use as the MJCF back end of our writer**: the compiler validates every model |
| MuJoCo URDF import ([URDF extensions](https://mujoco.readthedocs.io/en/stable/modeling.html#curdf)) | Loads URDF with an optional `<mujoco><compiler …/></mujoco>` block | Apache-2.0 | (as above) | Mature, with quirks (§1.2) | OK for a check; author MJCF directly |
| [kscalelabs/urdf2mjcf](https://github.com/kscalelabs/urdf2mjcf) | URDF → MJCF converter | MIT | 143 / 2025-09-26 (PyPI 0.2.39, 2025-08) | Stale for a year | Skip; MjSpec covers it |
| [robot-descriptions/robot_descriptions.py](https://github.com/robot-descriptions/robot_descriptions.py) | 200+ URDF/MJCF descriptions with loaders for MuJoCo, Pinocchio, yourdfpy and others. "Wheeled" list includes `upkie_description` (6 DOF), `cookie_description`, `tron1_wf_tron1a_mj_description`, `wl_p311d_description` | Apache-2.0 | 847 / 2026-10-22 (PyPI 3.3.0) | Mature | **Use for test fixtures and reference models** (Upkie, TRON1-WF) |
| [clemense/yourdfpy](https://github.com/clemense/yourdfpy) | Python URDF parser with FK and trimesh scene; viser and robot_descriptions use it | MIT | 297 / 2026-05-10 | Mature | Use in tests (FK checks) |
| [earthtojake/text-to-cad](https://github.com/earthtojake/text-to-cad) (vendored) | `cadgen urdf validate` (structure, joints, inertials, mesh refs); viewer; a `tcad:four_bar` URDF vendor extension for loop coupling in its viewer only ("Other consumers ignore the namespaced element", [authoring contract](https://github.com/earthtojake/text-to-cad/blob/main/skills/urdf/references/authoring-contract.md)) | MIT | 23,126 / 2026-10-25 | Active | Keep as a **validation gate**. Its skill says "do not build a Python generation pipeline". wobbit has to be parametric, so we generate and then validate. |
| [newton-physics/urdf-usd-converter](https://github.com/newton-physics/urdf-usd-converter) | URDF → OpenUSD. **Isaac Sim 6's URDF importer 3.0 is built on it** ([Isaac Lab import guide](https://github.com/isaac-sim/IsaacLab/blob/main/docs/source/how-to/import_new_asset.rst)). Mimic → `NewtonMimicAPI`; "Transmission, Gazebo, and other out-of-spec URDF extensions have no equivalent in UsdPhysics" ([CHANGELOG](https://github.com/newton-physics/urdf-usd-converter/blob/main/CHANGELOG.md)) | Apache-2.0 | 75 / 2026-10-22 (PyPI 0.3.4, Python <3.13) | **Alpha** (README) | Use (through Isaac Lab's `UrdfConverterCfg`) |
| [newton-physics/mujoco-usd-converter](https://github.com/newton-physics/mujoco-usd-converter) | MJCF → OpenUSD; **Isaac Sim's MJCF importer has used it since 5.0** ([Isaac Lab import guide](https://github.com/isaac-sim/IsaacLab/blob/main/docs/source/how-to/import_new_asset.rst)). Converts Connect, Joint and Weld equalities, tendons and actuators. Known limitation: "Collision filtering via the contype & conaffinity algorithm is not implemented" ([CHANGELOG](https://github.com/newton-physics/mujoco-usd-converter/blob/main/CHANGELOG.md)) | Apache-2.0 | 75 / 2026-10-21 | **Alpha** | Use for MJCF → Isaac |
| GUI-CAD exporters: [fusion2urdf](https://github.com/syuntoku14/fusion2urdf) (MIT, 763, 2025-03), [solidworks_urdf_exporter](https://github.com/ros/solidworks_urdf_exporter) (MIT, 702), [phobos](https://github.com/dfki-ric/phobos) (BSD-3, 911), [freecad.cross](https://github.com/galou/freecad.cross) (LGPL-2.1, 162) | Export from a GUI CAD tool | various | — | Mature | Not applicable (no code-CAD path) |

### 1.2 MuJoCo URDF import quirks (checked in the docs and the parser source, and **tested locally** with MuJoCo 3.17.0)

- Compiler defaults differ for URDF: `fusestatic` and `discardvisual` are "true" for URDF and "false" for MJCF ([XML reference](https://mujoco.readthedocs.io/en/stable/XMLreference.html#compiler-fusestatic)). Since 3.7.0, `strippath` defaults to false for URDF and you set it yourself ([changelog](https://github.com/google-deepmind/mujoco/blob/main/doc/changelog.rst)).
- URDF is **not schema-checked**: "mis-typed attribute names are silently ignored" ([modeling guide](https://mujoco.readthedocs.io/en/stable/modeling.html#curdf)). MuJoCo recommends converting to MJCF once and then working in MJCF.
- Local test with a three-link URDF:
  - The root link is fused into `world`, so **there is no free joint**. A floating-base robot needs one added.
  - Fixed-joint children are fused into their parent.
  - **No actuators are created** (`nu = 0`), and `<transmission>` is ignored.
  - `<limit effort>` becomes the joint `actfrcrange`, while `<limit velocity>` is dropped. The parser has the comment "no maxvel in MuJoCo" ([xml_urdf.cc](https://github.com/google-deepmind/mujoco/blob/main/src/xml/xml_urdf.cc)).
  - `<dynamics damping/friction>` becomes `damping` and `frictionloss`.
  - `<mimic>` becomes a **joint equality** constraint (`eq_type = mjEQ_JOINT`).
- Conclusion: **generate MJCF directly**, with free joint, actuators, sensors and equalities, and treat the URDF as a secondary output for ROS, Isaac and the browser.

### 1.3 Closed loops (four-bar knee transmission)

| Engine | How a loop is closed | Source |
|---|---|---|
| MuJoCo / MJCF | Keep the tree and add `<equality><connect>`, which "effectively defines a ball joint outside the kinematic tree" ([XML ref](https://mujoco.readthedocs.io/en/stable/XMLreference.html#equality-connect)). Two connects, or one connect plus the planar joint axes, close a planar revolute loop; onshape-to-robot emits "two `connect` constraints" per revolute closure. MuJoCo Warp supports `CONNECT`, `WELD` and `JOINT` equalities ([types.py](https://github.com/google-deepmind/mujoco_warp/blob/main/mujoco_warp/_src/types.py)). | cited |
| URDF | Cannot express loops. Options: an equivalent serial chain plus `<mimic>`, or a vendor extension (`tcad:four_bar`, which only text-to-cad's viewer reads) | cited above |
| Isaac Sim 5.1 / 6.x (PhysX articulations) | "Articulations must be kinematic trees". Pick one loop joint "with no limits, no resistance, and no drive" and tick **Exclude From Articulation**; that joint becomes a maximal-coordinate joint and "accumulate[s] the most simulation error" ([Tutorial 10: Rig Closed-Loop Structures, 6.0](https://docs.isaacsim.omniverse.nvidia.com/6.0.0/robot_setup_tutorials/rig_closed_loop_structures.html)). Whether the URDF or MJCF importers do this automatically is **not documented** ([6.0 importer migration guide](https://docs.isaacsim.omniverse.nvidia.com/6.2.0/migration_guides/isaac_sim_6_0/urdf_mjcf_importer_exporter_pipeline.html) only says to re-test "tendon or equality constraints"). | cited |
| RL practice | Train an **open-chain equivalent** leg and map it to the real linkage. [Wheel-Legged-Gym](https://github.com/clearlab-sustech/Wheel-Legged-Gym) uses "VMC to unify motion control of open-chain and closed-chain mechanisms"; DDT's own Diablo RL URDF replaces the linkage with a serial 2-link leg (see `research/reference-robots.md`) | cited |

**Recommendation:** emit two models from one design.
- **`wobbit_closed.xml`**: the true linkage, with `connect` equalities. It drives the evaluation and load extraction, because four-bar link loads exist only here.
- **`wobbit_serial.xml` / `.urdf`**: the serial equivalent with reflected inertia. It drives RL, Isaac import and the browser.

A test checks that both models give the same foot trajectory and joint torques under quasi-static loads.

### 1.4 Install

```bash
pip install robot_descriptions yourdfpy urdf-usd-converter mujoco-usd-converter   # mujoco 3.17 already installed
uvx --from cadgen==0.7.26 cadgen urdf validate path/to/robot.urdf                 # vendored validator (version from text-to-cad skill)
```

---

## 2. Wheel-legged simulation and control baselines

### 2.1 Open-source wheel-legged projects

| Project | Robot / joints | Sim / framework | Controller | Licence | Stars / last push | Notes |
|---|---|---|---|---|---|---|
| [upkie/upkie](https://github.com/upkie/upkie) ([docs](https://upkie.github.io/upkie/)) | Upkie: hip, knee, wheel per leg (6 DOF, [robot_descriptions](https://github.com/robot-descriptions/robot_descriptions.py)), mjbots actuators | PyBullet + "Spine" real/sim interface; Gymnasium envs (`pip install upkie`, 13.1.0) | PD balancer, MPC balancer, torque balancer (`examples/pybullet/{pd,mpc,torque}_balancing.py`) | Apache-2.0 | 452 / 2026-10-11 | **Same morphology as wobbit.** Hardware build docs. `stephane-caron/mpc_balancer` (Apache-2.0) uses ProxQP but targets upkie 8.0.0 (old) |
| [MarcDcls/mjlab_upkie](https://github.com/MarcDcls/mjlab_upkie) | Upkie (own design variant) | **mjlab** (MuJoCo Warp), RSL-RL; CPU MuJoCo playback (`sim.py`) | RL velocity tracking, "resist external disturbances"; pretrained checkpoint | Apache-2.0 | 39 / 2026-05-26 | **Closest RL template for wobbit** |
| [zyicome/Wheel-Legged-Lab](https://github.com/zyicome/Wheel-Legged-Lab) | Open-chain 2-leg wheel-legged | Isaac Lab 2.3.2 / Isaac Sim 5.1 / Python 3.11, RSL-RL PPO | Policy outputs virtual leg angle, length and wheel speed → **VMC** torques. Balance, velocity, height, **jumps (0.09–0.12 m), moving jumps up to 1.0 m/s, 7 cm obstacle** | Apache-2.0 | 29 / 2026-08-02 | Best reference for **hop/curb rewards and curricula**. README says no sim-to-real yet |
| [limxdynamics/tron1-rl-isaaclab](https://github.com/limxdynamics/tron1-rl-isaaclab) | TRON1 **WF**: abad, hip, knee + wheel per leg ("6 leg position actions + 2 wheel velocity actions") | Isaac Lab, Python 3.10, rsl_rl; physics 200 Hz, policy 50 Hz | PPO, velocity-estimator MLP, privileged critic; ONNX export | Apache-2.0 | 73 / 2026-10-23 | Commercial robot, industrial-quality task code. Blind, **flat ground only**. Sim-to-sim in [tron1-mujoco-sim](https://github.com/limxdynamics/tron1-mujoco-sim) (Apache-2.0) |
| [jaykorea/Isaac-RL-Two-wheel-Legged-Bot](https://github.com/jaykorea/Isaac-RL-Two-wheel-Legged-Bot) ("Flamingo") | 2-wheel-legged | Isaac Lab 2.0 / Isaac Sim 4.5 | PPO + off-policy, Constraints-as-Terminations; Lab→MuJoCo sim2sim branch; zero-shot sim2real claimed | MIT | 352 / 2026-03-26 | Older Isaac versions |
| [scutrobotlab/wheeled-legged_RL](https://github.com/scutrobotlab/wheeled-legged_RL) | RoboMaster "wheelbipe" | Isaac Lab 2.1 or 2.3 | PPO, DreamWaQ, HIMLoco, NP3O; jump/stair state machine | MIT | 91 / 2026-10-08 | Competition-proven team |
| [clearlab-sustech/Wheel-Legged-Gym](https://github.com/clearlab-sustech/Wheel-Legged-Gym) | Five-bar wheel-legged | **Isaac Gym** (Python 3.8) | PPO, open-chain or **VMC** closed-chain tasks | BSD-3 | 695 / 2024-06-19 | Stale and on Isaac Gym. [L-SY/wheeled_bipedal_gym](https://github.com/L-SY/wheeled_bipedal_gym) (no licence) adapts it to DDT Diablo |
| [DDTRobot/tita_rl](https://github.com/DDTRobot/tita_rl) | DDT TITA | Isaac Gym; Webots sim2sim; TensorRT on Jetson Orin NX | NP3O | MIT | 139 / 2025-11-04 | Shows **Orin + TensorRT** deployment |
| [Albusgive/wheel_legged_genesis](https://github.com/Albusgive/wheel_legged_genesis) | Wheel-legged | Genesis (main branch), MuJoCo sim2sim | PPO (rsl_rl) | MIT | 374 / 2025-07-10 | Genesis API churn ("not possible to install 0.2.1 … with pip") |
| [WilliamGwok/RP_Balance](https://github.com/WilliamGwok/RP_Balance) | RoboMaster five-bar balance chassis | MATLAB + Webots | **LQR with K fitted against leg length**, five-bar VMC, A/B-matrix fitting; real-robot tuning notes | MIT | 44 / 2024-12-02 | Best documented classical controller |
| [Skythinker616/foc-wheel-legged-robot](https://github.com/Skythinker616/foc-wheel-legged-robot) | Five-bar desk-size robot | MATLAB/Simulink/Simscape; ESP32 | Model-based (LQR/VMC per README sections) | **GPL-3.0** | 1,810 / 2023-11-23 | Read, don't copy (GPL) |
| [MuShibo/Micro-Wheeled_leg-Robot](https://github.com/MuShibo/Micro-Wheeled_leg-Robot) | Tiny desktop wheeled biped | — | — | **No licence** | 3,770 / 2024-12-12 | Read only |
| [DDTRobot/Col_DIABLO_Issac_RL](https://github.com/DDTRobot/Col_DIABLO_Issac_RL) | Diablo | Isaac Gym | PPO | **No licence** | 13 / 2025-02-24 | Diablo URDF reference only |
| [XinLang2019/awesome-wheeled-legged](https://github.com/XinLang2019/awesome-wheeled-legged) | List of projects and papers | — | — | CC0 (badge) | 62 / 2025-07-31 | Paper index |

### 2.2 Simulator and RL frameworks

| Framework | Wheel-legged task built in? | Loads | Licence | Stars / last push / version | Fit |
|---|---|---|---|---|---|
| **MuJoCo 3.17 (CPU, Python)** | No (none of these frameworks has one) | MJCF, URDF, MjSpec | Apache-2.0 | 15,876 / 2026-10-25 / 3.17.0 | **Evaluation loop.** Already installed; deterministic; `mujoco.rollout` batches rollouts across threads ([sysid README](https://github.com/google-deepmind/mujoco/blob/main/python/mujoco/sysid/README.md)) |
| **[mjlab](https://github.com/mujocolab/mjlab)** ([docs](https://mujocolab.github.io/mjlab/)) | No (G1, Go1, YAM in the zoo); Upkie task in [mjlab_upkie](https://github.com/MarcDcls/mjlab_upkie) | MJCF (MuJoCo Warp 3.16) | Apache-2.0 | 3,270 / 2026-10-25 / 1.6.0 (Python 3.10–3.13) | **RL, step 1.** "Isaac Lab's manager-based API with MuJoCo Warp"; needs an NVIDIA GPU to train; `--agent zero/random` sanity checks |
| **[Isaac Lab 3.0](https://github.com/isaac-sim/IsaacLab)** ([release](https://github.com/isaac-sim/IsaacLab/releases/tag/v3.0.0)) | No (velocity tasks: ANYmal, Cassie, G1, Go2, H1, Digit, Spot, A1, Go1) | USD via URDF/MJCF converters; Newton backends include MuJoCo-Warp | BSD-3 (PyPI `isaaclab` 3.0.0); repo LICENSE "see README" | 8,469 / 2026-10-25 | **RL, step 2.** "kit-less execution with Newton"; Isaac Sim "now fully optional"; targets **Isaac Sim 6.2, Python 3.12, PyTorch 2.11 + CUDA 13.0**. Our Isaac Sim 6.0 dev install is behind the target |
| [MuJoCo Playground](https://github.com/google-deepmind/mujoco_playground) | No. Locomotion envs: apollo, barkour, berkeley_humanoid, g1, go1, h1, op3, spot, t1 ([tree](https://github.com/google-deepmind/mujoco_playground/tree/main/mujoco_playground/_src/locomotion)) | MJCF via MJX (JAX) or MuJoCo Warp | Apache-2.0 | 2,261 / 2026-10-25 / 0.2.0 | Good, but JAX-centric and off Isaac Lab's API. [Open_Duck_Playground](https://github.com/apirrone/Open_Duck_Playground) builds on it (**no licence**) |
| [Genesis](https://github.com/Genesis-Embodied-AI/genesis-world) | No (community: wheel_legged_genesis) | URDF, MJCF, USD, … | Apache-2.0 | 30,118 / 2026-10-25 / 1.4.5 | A third physics engine to validate; no benefit for us now |
| [Newton](https://github.com/newton-physics/newton) | No | URDF, MJCF, USD | Apache-2.0 | 5,834 / 2026-10-24 / 1.7.0 | Comes in via Isaac Lab 3.0; no need to use it directly |
| [legged_gym](https://github.com/leggedrobotics/legged_gym) | No | URDF | BSD-3 | 3,156 / 2025-05-29 | **Avoid**: "will receive limited updates", Isaac Gym, Python 3.6–3.8 |

### 2.3 Recommendation

- **Evaluation loop (now): plain MuJoCo on the CPU plus our own scenario harness.**
  - Each scenario (balance, push, drive course, slope, curb, squat, hop) is a Python function: MJCF in, metrics out.
  - Baseline controller: a wheeled-inverted-pendulum **LQR whose gains are scheduled on leg length** (the RP_Balance pattern), with leg-length and roll handled by a PD/VMC layer.
  - Upkie's `pd_balancing.py` and `mpc_balancing.py` are the Python references (Apache-2.0, safe to adapt). The LQR is recomputed for every design from the MJCF's own linearisation (`mujoco.mjd_transitionFD`). Each new design then gets a fair, tuned controller rather than fixed gains.
- **RL (next): mjlab**, starting from `mjlab_upkie`'s velocity task. Borrow reward and curriculum ideas from Wheel-Legged-Lab (jump, clearance, obstacle) and TRON1 (privileged critic, velocity estimator, ONNX export). One MJCF serves evaluation and training, so there is no USD drift.
- **Isaac Lab 3.0 later**, when we need Isaac Sim rendering, sensors or ROS. The task code ports, because the manager API is the same.
- **Avoid** porting Isaac Gym projects (legged_gym, Wheel-Legged-Gym, tita_rl): Isaac Gym is deprecated and stuck on Python 3.8. Read them for reward terms only.

```bash
# mjlab (needs uv); our venv is Python 3.12, within mjlab's 3.10–3.13
git clone https://github.com/mujocolab/mjlab.git && cd mjlab && uv run demo
git clone https://github.com/MarcDcls/mjlab_upkie.git && cd mjlab_upkie && uv sync
uv run play Mjlab-Velocity-Upkie --checkpoint-file logs/rsl_rl/upkie_velocity/bests/default.pt
pip install upkie          # Gymnasium envs + PyBullet balancers for reference
# Isaac Lab 3.0, kit-less Newton/MuJoCo-Warp path
git clone --branch v3.0.0 --depth 1 https://github.com/isaac-sim/IsaacLab.git
cd IsaacLab && uv run isaaclab train --rl_library rsl_rl --task Isaac-Cartpole --viz newton_gl physics=newton_mjwarp
```

---

## 3. Actuator models for simulation

| Option | What it models | Where | Licence | Notes |
|---|---|---|---|---|
| MuJoCo `<dcmotor>` | Added in **3.7.0** (2026-04): "optional electrical dynamics (inductance), cogging torque, thermal resistance variation, and LuGre friction". Redesigned in **3.12.0** with an on-board PID (`input` = any subset of pos/vel/ff/voltage). `thermal` "Adds one activation variable for **winding temperature**"; `saturation` sets continuous torque/current limits ([XML ref](https://mujoco.readthedocs.io/en/stable/XMLreference.html#actuator-dcmotor), [tech note](https://mujoco.readthedocs.io/en/stable/_static/dcmotor.pdf), [changelog](https://github.com/google-deepmind/mujoco/blob/main/doc/changelog.rst)) | MuJoCo ≥3.7; MuJoCo Warp has `DCMOTOR` dyn, gain and bias types ([types.py](https://github.com/google-deepmind/mujoco_warp/blob/main/mujoco_warp/_src/types.py)) | Apache-2.0 | **Best physical model.** Needs R and Kt (our catalog often has `kt_nm_per_a: null`). The thermal state is what the "can it hold a squat" scenario needs |
| MuJoCo actuator delays | "Actuators and sensors now support arbitrary delays via history buffers" (**3.5.0**); MuJoCo Warp has `history.py` | MuJoCo | Apache-2.0 | CAN bus and policy latency |
| MuJoCo sysid toolbox | "Given a MuJoCo model and recorded sensor data, find parameters that make simulation match reality"; Gauss-Newton with batched rollouts; HTML report ([README](https://github.com/google-deepmind/mujoco/blob/main/python/mujoco/sysid/README.md)) | `mujoco.sysid` (3.5.0) | Apache-2.0 | **Use for bench-test identification** of our actual motors |
| mjlab actuators | `DcMotorActuatorCfg`: "Linear torque-speed curve: full saturation_effort at zero velocity falling to zero at velocity_limit, further bounded by the continuous force_limit"; `LearnedMlpActuator` (TorchScript, joint history); every actuator has `armature`, `frictionloss`, `delay_min_lag`/`delay_max_lag` ([src/mjlab/actuator](https://github.com/mujocolab/mjlab/tree/main/src/mjlab/actuator)) | mjlab | Apache-2.0 | **Maps 1:1 onto our catalog fields**: `peak_torque_nm` → saturation_effort, `no_load_speed_rpm` → velocity_limit, `rated_torque_nm` → effort_limit |
| Isaac Lab actuators | Implicit, IdealPD, **DCMotor** ("linear four-quadrant torque-speed curve"), **DelayedPD**, RemotizedPD (angle-dependent torque limit), **ActuatorNetMLP/LSTM**, **BamActuator** ("Newton only") ([docs](https://isaac-sim.github.io/IsaacLab/main/source/concepts/actuators.html)) | Isaac Lab | BSD-3 | Same concepts as mjlab, so models carry across |
| [Rhoban/bam](https://github.com/Rhoban/bam) ("Better Actuator Models", [docs](https://bam.readthedocs.io/en/latest/)) | Identification pipeline plus extended friction models (Stribeck, load-dependent, quadratic; [ICRA 2025 paper](https://arxiv.org/pdf/2410.08650v1)). Library of identified models for **Dynamixel MX-64/106, XL-320, XL330, eRob80:50/100, Feetech STS3215** only. "simple API to use these models in MuJoCo CPU and MuJoCo Warp" | `pip install better-actuator-models` (1.0.2, **Python 3.12 only**) | Apache-2.0 | 568 / 2026-09-28. Open Duck Mini: "Actuator identification — We used Rhoban's BAM" ([README](https://github.com/apirrone/Open_Duck_Mini)). Most useful for **geared** joints with high friction |
| Learned actuator nets | [zitongbai/legged_actuator_net](https://github.com/zitongbai/legged_actuator_net) (Apache-2.0, 8 stars, 2025-01); [sunzhon/actuator_net](https://github.com/sunzhon/actuator_net) (no licence) | — | — | Small, unmaintained. mjlab and Isaac Lab already include the network runtime |
| Vendor drivers (for logging bench data) | Damiao: [cmjang/DM_Control_Python](https://github.com/cmjang/DM_Control_Python) (MIT, 78); friction-ID GUI [qt5_damiao_motor_friction_detection](https://github.com/cdssywc/qt5_damiao_motor_friction_detection) (Apache-2.0, 30). Robstride: [sirwart/robstride](https://github.com/sirwart/robstride) (MIT, 31, 2024-07). CubeMars: [sam0rr/cubemars_servo_can](https://github.com/sam0rr/cubemars_servo_can) (MIT, 6, 2026-09), [ziteh/tmotor-ak-actuators-driver](https://github.com/ziteh/tmotor-ak-actuators-driver) (MIT) | — | — | **No open library of identified sim models for CubeMars, Robstride or Damiao was found.** We identify our own |

**Recommendation.** Use one actuator description in the catalog and the design, rendered three ways:
1. **Level 0 (every evaluation):** a linear four-quadrant torque–speed clip, plus reflected rotor inertia (`armature` = rotor inertia × gear²), `frictionloss`, `damping` and a command delay. The formula is identical to mjlab's and Isaac Lab's `DcMotor`, so evaluation and RL agree.
2. **Level 1 (squat, endurance and hop scenarios):** MuJoCo `<dcmotor>` with `thermal` and `saturation`, built from datasheet R, Kt and thermal resistance. It answers "how long can it hold a crouch", which the Diablo spec sheet shows matters.
3. **Level 2 (after hardware arrives):** a bench log, then the `mujoco.sysid` fit (and BAM if the joint is geared and friction-dominated). An actuator net is a last resort.

---

## 4. Structural analysis (FEA) in the loop

### 4.1 Comparison

| Tool | Role | Install | Licence | Stars / last push | Anisotropy | Verdict |
|---|---|---|---|---|---|---|
| **[scikit-fem](https://github.com/kinnala/scikit-fem)** | FE assembly in pure Python ("minimal dependencies are numpy and scipy"); tets P1/P2; `skfem.models.elasticity.linear_elasticity(Lambda, Mu)`; meshio import | `pip install scikit-fem[all]` (12.0.2) | BSD-3 | 668 / 2026-10-25 | Isotropic helper built in; orthotropic needs a custom `BilinearForm` with a 6×6 D matrix (a few lines) | **Use for the in-loop screen** |
| [SfePy](https://github.com/sfepy/sfepy) | General FE framework | `pip install sfepy` (2026.3) | BSD-3 | 849 / 2026-10-23 | Built in: `LinearElasticTerm` takes "D_ijkl given in the usual matrix form … in 3D it is 6×6" ([terms_elastic.py](https://github.com/sfepy/sfepy/blob/master/sfepy/terms/terms_elastic.py)) | Good alternative; heavier API |
| [FEniCSx / dolfinx](https://github.com/FEniCS/dolfinx) | Research-grade FE | conda (`conda install -c conda-forge fenics-dolfinx`) or Docker; pip wheels are "beta" on Test PyPI and "pip does not include PETSc yet" | LGPL-3.0 | 1,238 / 2026-10-25 | Any (variational forms) | Avoid for now: install friction |
| **CalculiX ccx** ([source](https://github.com/Dhondtguido/CalculiX), [site](https://www.dhondt.de/)) | Production structural solver (Abaqus-like `.inp`): contact, nonlinear, buckling | `sudo apt install calculix-ccx` (2.21 on Ubuntu 24.04, **checked locally**) | GPL-2.0 | 226 / 2026-10-23 | `*ELASTIC, TYPE=ORTHO` or `TYPE=ENGINEERING CONSTANTS` ([manual](https://web.mit.edu/calculix_v2.7/CalculiX/ccx_2.7/doc/ccx/node193.html)); forum reports of ordering mistakes and silent failures ([1](https://calculix.discourse.group/t/calculix-crashes-for-edited-input-file/2886), [2](https://calculix.discourse.group/t/silent-termination-in-orthotropic-material-analysis/3883)) | **Use as the high-fidelity verifier** (runs as a subprocess, so GPL is not an issue) |
| [calculix/pygccx](https://github.com/calculix/pygccx) | Python model builder: gmsh → ccx keywords → solve → post-process | `pip install git+https://github.com/calculix/pygccx.git` (not on PyPI) | GPL-3.0 | 49 / 2025-02-18 | via ccx | Optional; writing `.inp` ourselves is simple |
| [calculix/ccx2paraview](https://github.com/calculix/ccx2paraview) | `.frd` → VTK/VTU | `pip install ccx2paraview` (3.2.0, 2024-12) | GPL-3.0 | 130 / 2026-09-21 | — | Use to get results into pyvista |
| [spacether/pycalculix](https://github.com/spacether/pycalculix) | Older ccx wrapper | PyPI 1.1.4 (2019) | Apache-2.0 | 185 / 2024-02-13 | — | Avoid (stale) |
| [calculix/beso](https://github.com/calculix/beso) | Topology optimisation with CalculiX | — | LGPL-3.0 | 478 / 2025-04-03 | — | Later: lightweighting brackets |
| [Elmer](https://github.com/ElmerCSC/elmerfem) | Multiphysics FE | apt/source | GPL/LGPL (repo "NOASSERTION") | 1,747 / 2026-10-23 | yes | Overkill |
| Code_Aster | Industrial FE | source/containers | GPL | — | yes | Overkill; not pip |
| [PrePoMax](https://prepomax.fs.um.si/) | CalculiX GUI pre/post-processor ([manual v2.4.0](https://prepomax.fs.um.si/wp-content/uploads/2025/10/PrePoMax-v2.4.0-manual.pdf)) | Desktop app | licence **not verified** | — | "orthotropic material definitions are not yet supported in PrePoMax GUI" ([forum](https://prepomax.discourse.group/t/problem-importing-orthotropic-material/2937)) | Manual inspection only |
| **[gmsh](https://pypi.org/project/gmsh/)** | CAD (OpenCASCADE kernel, imports STEP) → tet mesh; physical groups for load and fixture faces | `pip install gmsh` (4.15.2) | GPL-2.0-or-later | — | — | **Use**. `pyvista-cad` avoids it because "gmsh is GPLv2+ and would virally license any closed-source product that linked it" ([pyvista-cad](https://github.com/pyvista/pyvista-cad)). Fine as an internal tool; keep it an optional extra in public cad-agent |
| [pyvista/tetgen](https://github.com/pyvista/tetgen) | Tet meshing from a surface | `pip install tetgen` | wrapper MIT, but "TetGen library is licensed under AGPL" | 315 / 2026-10-05 | — | Avoid (AGPL) |
| [pyvista/pytetwild](https://github.com/pyvista/pytetwild) | Robust tet meshing of dirty surfaces (fTetWild) | `pip install pytetwild` | MPL-2.0 | 18 / 2026-10-19 | — | Fallback when STEP meshing fails |
| [meshio](https://github.com/nschloe/meshio) / [pyvista](https://github.com/pyvista/pyvista) | Mesh I/O, post-processing, glTF export | pip | MIT | 2,335 (last push 2024-07) / active | — | Use |

**CadQuery/build123d + FEA integration projects:** none of note. Searches for "cadquery fea", "cadquery gmsh", "build123d fea" and "cadquery calculix" found only 0–1-star templates ([mechanical-model](https://github.com/engineering-with-ai/mechanical-model), [LLM-FEA-Bench](https://github.com/kumar1441/LLM-FEA-Bench)). The pattern is well established in the literature, for example [FeaGPT](https://arxiv.org/pdf/2510.21993): gmsh's Python API, physical groups for fixed and loaded faces, CalculiX `.inp`, first-order tets for complex geometry. We write the ~300-line glue ourselves.

### 4.2 Getting loads out of the simulation

- MuJoCo `<sensor><force site=…/>` and `<torque>` give "the interaction force between a child and a parent body, expressed in the site frame". The sensor "takes into account all forces acting on the system, including contacts as well as external perturbations" ([XML ref](https://mujoco.readthedocs.io/en/stable/XMLreference.html#sensor-force)). **Put a site at every joint and every bolt interface**, log the 6-axis wrench in every scenario, and keep the per-part worst cases (max |F|, max |M|, and the combined case at peak von Mises from a unit-load superposition).
- Whole-body alternative: `mjData.cfrc_int` (computed by `mj_rnePostConstraint`).
- Loop-closure (four-bar) pin loads: the equality-constraint rows of `mjData.efc_force` in the closed-loop model.
- Isaac Lab's PhysX backend exposes `body_incoming_joint_wrench_b` (found in the [Isaac Lab repo](https://github.com/isaac-sim/IsaacLab)); availability on the Newton backend is **not verified**.
- Turning a load into an FEA case: apply each wrench as a distributed traction (RBE3-style) on the bolt-hole faces of the part, with the opposite interface fixed. Use superposition of six unit cases per interface, so one solve per part covers every logged time step. That makes FEA cost independent of scenario length.

### 4.3 Printed-material modelling

FDM parts are weakest across layers (Z). Practical tiers, cheapest first:
1. **Isotropic with a knock-down:** E and allowable stress from the *Z-direction* (worst-case) datasheet value of the filament, safety factor ≥ 2–3. Works in scikit-fem today.
2. **Transversely isotropic or orthotropic** stiffness, oriented by the part's print orientation, with a Tsai-Hill or max-stress check per direction. Use SfePy's general D matrix, a custom scikit-fem form, or CalculiX `TYPE=ENGINEERING CONSTANTS`.
3. Infill homogenisation: not needed while we print structural parts at high infill.

The constants must come from filament datasheets or coupon tests. None of these tools supplies FDM material data.

### 4.4 Recommendation and install

- **In the loop:** CadQuery STEP → `gmsh` (OCC import, size field, physical groups) → `scikit-fem` linear elastic, P2 tets, isotropic knock-down. Output: max von Mises, safety factor and max deflection per part, plus a per-vertex stress field for the web viewer.
- **Verification** (top-N designs or flagged parts): the same mesh → CalculiX with orthotropic material (and contact at bolted joints if needed) → `ccx2paraview` → pyvista.

```bash
pip install gmsh "scikit-fem[all]" meshio pyvista ccx2paraview
sudo apt install calculix-ccx
```

---

## 5. Design optimisation

| Library | Multi-objective | Multi-fidelity | Categorical / conditional | Expensive evals | Licence | Version / date | Notes |
|---|---|---|---|---|---|---|---|
| **[Optuna](https://github.com/optuna/optuna)** | Yes. In **5.0** "TPESampler replaces NSGAIISampler as the default" for multi-objective; `GPSampler` is now stable with **qLogEHVI / qLogCEHVI** ([v5.0.0 notes](https://github.com/optuna/optuna/releases/tag/v5.0.0)) | Pruners (Hyperband, SHA), but **`Trial.report` "is not supported for multi-objective optimization"** ([source](https://github.com/optuna/optuna/blob/master/optuna/trial/_trial.py)) | Yes, native (define-by-run); GPSampler handles categoricals | Good: shared storage (RDB, Journal) for parallel workers; constant-liar on by default | MIT | 5.0.0 / 2026-09-07; 14,966 stars | **Orchestrator.** New core constraint API `trial.set_constraint()` |
| [pymoo](https://github.com/anyoptimization/pymoo) | Yes (NSGA-II/III, MOEA/D, …) | No | Yes (`pymoo.core.mixed`) | Weak (population-based) | Apache-2.0 | 0.6.2 / 2026-06-28; 2,980 stars | **Use on the cheap analytic model** (thousands of evaluations) |
| [BoTorch](https://github.com/meta-pytorch/botorch) | Yes (qLogNEHVI, ParEGO, HVKG, …) | **Yes**: `gp_regression_fidelity`, `acquisition/multi_objective/multi_fidelity.py` (MOMF) | `gp_regression_mixed` (MixedSingleTaskGP) | Best sample efficiency | MIT | 0.18.1 / 2026-06-08; 3,634 stars | Upgrade path when sim evaluations get expensive (RL-in-the-loop) |
| [Ax](https://github.com/facebook/Ax) | Yes ("multiple objectives, constraints on both parameters and outcomes") | Built on BoTorch; whether the Ax 1.x Client exposes multi-fidelity is **not verified** | Yes | Yes | MIT | 1.3.1 / 2026-06-09; 2,831 stars | Heavier platform than we need |
| [SMAC3](https://github.com/automl/SMAC3) | README: "All facades/intensifiers support multi-objective, multi-fidelity, and multi-threading natively" | Yes (Hyperband / successive halving) | Yes (random-forest surrogate) | Yes | BSD-3 | 2.4.1 / 2026-09-10; 1,262 stars | Credible alternative if we need MO + MF + categorical in one box |
| [pycma](https://github.com/CMA-ES/pycma) | No | No | No | Moderate | BSD-3 | 4.5.0 / 2026-09-13; 1,363 stars | **Inner loop: controller gains / LQR weights** per design |
| [Nevergrad](https://github.com/facebookresearch/nevergrad) | Partial (**not verified**) | No | Yes | Moderate | MIT | 1.0.12 / 2025-04-23; 4,217 stars | Last release 18 months ago; skip |

**Recommendation.**
- **Outer loop: Optuna 5 multi-objective study.** Objectives: cost, mass, a performance score aggregated over scenarios, and worst-part safety factor (or keep the safety factor as a constraint). Categoricals cover motors, wheel, battery, material and leg topology. Constraints use `trial.set_constraint()`.
- **Multi-fidelity, implemented by hand.** Optuna cannot prune multi-objective studies, so staging happens inside the objective:
  1. analytic budget model (ms), rejecting via constraint;
  2. CAD + mass properties + a short balance sim (seconds);
  3. the full scenario suite (minutes);
  4. FEA on parts that survive.

  A failed gate returns penalised values plus a violated constraint.
- **pymoo NSGA-II** pre-screens on stage 1 alone, which seeds Optuna with good regions.
- **pycma** tunes controller weights inside stage 3, so each design is compared with a tuned controller.
- **Switch to BoTorch MOMF** (or SMAC3) only if stage-3 cost becomes the bottleneck. That would be RL-in-the-loop.

```bash
pip install optuna pymoo cma            # core
pip install botorch ax-platform smac    # only if/when needed
```

---

## 6. Web visualisation (designer)

| Tool | Robot (URDF/MJCF) | Playback of a sim run | Stress heat-map | Static page? | Licence | Stars / last push | Verdict |
|---|---|---|---|---|---|---|---|
| **[three.js](https://threejs.org/) + [urdf-loader](https://github.com/gkjohnson/urdf-loaders)** | URDF ("Utilities for loading URDF files into THREE.js and a Web Component"); `npm i urdf-loader` | Ours: set joint values per frame from a JSON or binary qpos log | GLB with per-vertex colours (three.js renders vertex colours natively) | Yes | Apache-2.0 (urdf-loaders) / MIT (three.js) | 820 / 2026-10-22 | **Use for the designer** (it is already plain ES modules) |
| **[MuJoCo JS/WASM bindings](https://github.com/google-deepmind/mujoco/tree/main/wasm)** (`npm i @mujoco/mujoco`) | MJCF (full MuJoCo in the browser) | Re-simulate or replay exactly, in the browser | via three.js | Yes | Apache-2.0 (npm 3.17.0) | — | "canonical JavaScript and TypeScript bindings"; "still a WIP"; Windows support "experimental". **Use for exact replay or live demos** |
| [zalo/mujoco_wasm](https://github.com/zalo/mujoco_wasm) | MJCF | Live sim demos | — | Yes | MIT | 497 / 2026-08-23 | Now "just a small demo suite" on the official bindings: **example code to copy** |
| **[Rerun](https://github.com/rerun-io/rerun)** | Built-in URDF importer; `rr.urdf.UrdfTree`; animate joints with `Transform3D` ([URDF howto](https://rerun.io/docs/howto/logging-and-ingestion/urdf)). MJCF **not documented** | Native (timelines, plots, scrubbing) | Mesh3D with vertex colours | Embed via iframe `app.rerun.io/version/{v}/index.html?url={rrd}` or `npm i @rerun-io/web-viewer`; the viewer version must match the SDK ([embed](https://rerun.io/docs/howto/integrations/embed-web)) | Apache-2.0 | 11,638 / 2026-10-23 (rerun-sdk 0.40.0) | **Use for engineering debugging** (sim traces, contact forces, loads) |
| [viser](https://github.com/viser-project/viser) | URDF visualiser example with joint controls (via yourdfpy) | Record with `get_scene_serializer()` + `insert_sleep()` → `.viser` file → `viser-build-client` static client with `?playbackPath=` ([embedded visualisations](https://viser.studio/main/embedded_visualizations/)), "experimental and not yet polished" | Meshes yes; vertex colours **not verified** | Yes (experimental) | Apache-2.0 (GitHub) | 2,838 / 2026-09-25 (1.1.1) | Good for Python-side interactive tuning; not the designer |
| Foxglove | — | — | — | — | [foxglove/studio](https://github.com/foxglove/studio) **archived** (last push 2024-07); product now closed | — | **Avoid** |
| [Lichtblick](https://github.com/lichtblick-suite/lichtblick) | ROS-oriented | Yes | — | Desktop/web app | MPL-2.0, "open core" | 1,187 / 2026-10-22 | Only if we go ROS-bag-centric |

**Recommendation.** The designer stays a static page.
- three.js + `urdf-loader` draw the serial model. The robot is animated from a compact `run.json`: time, qpos and a few metrics per frame.
- Each printed part has a `part_stress.glb` with a von Mises colour ramp baked into vertex colours, toggled per part.
- `@mujoco/mujoco` is added when we want "press play and push the robot" in the browser, using the same MJCF as the evaluation loop.
- Rerun `.rrd` files are linked from each evaluation report for deep inspection.

```bash
npm i three urdf-loader @mujoco/mujoco @rerun-io/web-viewer
pip install rerun-sdk viser
```

---

## 7. Recommended stack for wobbit

| Stage | Tool (build on) | Why | Write ourselves |
|---|---|---|---|
| Parametric design + CAD | CadQuery 2.8 (installed) | Already our CAD kernel | Part generators |
| Mass properties | CadQuery / OCP | Exact from B-rep | Thin wrapper |
| Robot model, MJCF | `mujoco.MjSpec` (MuJoCo 3.17) | Official, compiler-validated; free joint, actuators, sensors and equalities set explicitly | Our writer: closed-loop and serial variants; onshape-to-robot-style `joint_properties` / `geom_properties` config |
| Robot model, URDF | Our writer → `cadgen urdf validate` (text-to-cad) → yourdfpy FK test | Validation gate already vendored | URDF emitter (serial model only) |
| Isaac assets | Isaac Lab `UrdfConverterCfg` / `MjcfConverterCfg` (→ `urdf-usd-converter` / `mujoco-usd-converter`, alpha) | What Isaac Sim 6 itself uses | Exclude-from-articulation fix-up if we ever import the closed loop |
| Reference models / fixtures | `robot_descriptions` (Upkie, TRON1-WF) | Known-good wheel-legged models for testing the harness | — |
| Actuators | mjlab-compatible `DcMotor` clip + armature + delay (L0) → MuJoCo `<dcmotor>` with `thermal` (L1) → `mujoco.sysid` / BAM on bench data (L2) | Same model in evaluation and RL; thermal answers the squat question | Catalog → actuator-params mapping |
| Scenarios + baseline control | MuJoCo CPU + our harness; LQR (gain-scheduled on leg length) + VMC leg control, ported from Upkie (Apache-2.0) and the RP_Balance method (MIT) | No framework ships a wheel-legged scenario suite | Scenario suite, scorer, per-design LQR synthesis |
| Loads | MuJoCo `force`/`torque` sensors at joint/interface sites; `efc_force` for loop pins | Documented, includes contacts | Worst-case extraction, unit-load superposition |
| FEA (screen) | gmsh + scikit-fem (P2 tets, isotropic Z knock-down) | pip-only, BSD core, robust | Glue: STEP → mesh → BCs → SF per part |
| FEA (verify) | CalculiX `ccx` (apt) + ccx2paraview | Orthotropic printed materials, contact | `.inp` writer |
| Manufacturability / cost | text-to-cad `dfam-check`, `bambu-labs`, `sendcutsend` skills (vendored) | Already in our toolkit | Cost roll-up into the objective |
| Optimiser | Optuna 5 (MO TPE / GPSampler, constraints, Journal storage) + staged fidelity; pymoo for analytic pre-screen; pycma for controller gains; BoTorch MOMF later | Categoricals + MO + constraints, minimal engineering | Staging gates |
| RL (phase 1) | mjlab + RSL-RL, starting from `mjlab_upkie`; rewards from Wheel-Legged-Lab and TRON1 | Same MJCF, pip-installable, Python 3.12 | wobbit task config |
| RL (phase 2) | Isaac Lab 3.0 (Newton/MuJoCo-Warp backend first, Isaac Sim 6.2 when needed) | Same manager API; Isaac Sim tooling | Port of task config |
| Deployment | ONNX export (all of the above) → TensorRT on Jetson AGX Orin (pattern shown by DDT `tita_rl`) | Proven path | Runtime node |
| Web designer | three.js + urdf-loader; GLB vertex-colour stress; `@mujoco/mujoco` for live replay | Static page, no server | `run.json` / GLB exporters |
| Debug viz | Rerun (`.rrd` + web viewer) | Timelines, URDF, meshes | Logging calls |

### Licence notes

- Everything recommended for the code we ship is permissive: MIT, BSD, Apache-2.0 or MPL-2.0.
- **GPL** (gmsh, CalculiX, ccx2paraview, pygccx) is fine for internal tools invoked as libraries or subprocesses. Keep these as *optional* extras in the public MIT cad-agent repo.
- **AGPL TetGen:** avoid.
- **No-licence repos** (DDT Diablo RL, MuShibo, Open_Duck_Playground, L-SY): read for ideas, do not copy code.
- **GPL-3 Skythinker616:** read for ideas, do not copy code.

### Open questions and risks

1. **Isaac version mismatch.** Isaac Lab 3.0 targets Isaac Sim 6.2 and CUDA 13.0. Our vp-isaac-sim is 6.0 dev. The kit-less Newton path avoids the mismatch for training.
2. **Isaac closed loops.** PhysX loop handling ("Exclude From Articulation") is manual, and whether the importers do it is **not documented**. This is why RL uses the serial model.
3. **Converter maturity.** `urdf-usd-converter` and `mujoco-usd-converter` are alpha, and `contype`/`conaffinity` collision filtering is not converted. Expect to check self-collision settings after every import.
4. **Motor data.** CubeMars, Robstride and Damiao have no identified sim models anywhere we looked. Budget a bench rig: one leg actuator, a load arm, a CAN logger, then `mujoco.sysid`.
5. **Printed-material constants.** These come from datasheets or coupons, not from any tool. Treat early safety factors as screening numbers.
