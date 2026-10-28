# Body thermal: the J501's cooler in the closed body (B7, D61)

The P3 shell closes the body round the J501 and its G48R cooler. This page is the hand model the plan asks for first:
where the cooler's 9215 fan works once the body is closed, what the body's inlet and outlet add to its load, the
louvres that let the air in, and the temperatures at 40 W.

**The fan blows up** (the j501-agx project, commit 94da39d, from the user's look at the fitted cooler; this page was
first written for a fan blowing down and was turned round the same day). It draws air in through the fin block's open
±y sides and blows it out of its top. In the body: the room's air comes in through the side walls' louvres, crosses
the body past the power supplies, goes through the fins and the fan, up the fan duct, through the deck's cells and the
turret plate's opening, and out of the riser's open sides under the turret. The losses are the same openings either
way; what changes is the temperatures: the cooler now breathes the body's air, warmed by everything else in it. Numbers: `cad/body_thermal.py` →
`exports/body/thermal/hand_model.json` (regenerate, never edit). Every input says where it comes from: the J501
project's parameters (vendored in `references/vendor/j501/`, B10), this body's CAD, Idel'chik's *Handbook of
Hydraulic Resistance* for the loss coefficients, or "assumed". Written 2026-10-27.

**The acceptance is a thermometer on the robot (B16, D61): the cooler's inlet (at the fins' sides) within 3 K of the
room, the module's plate <= 70 °C, the exhaust <= 45 °C where it leaves the riser, at 40 W.** The CFD (the j501-agx project's `tools/thermal.py` on
cadagent.cfd) runs only once the J501's own Rev 0.9-g48r case reports itself calibrated and steady; today its
`exports/simulation-checks.json` says the fins are not calibrated and the plate's margin is unknown, so no CFD was run
here (one heavy solver at a time; the shared machines are loaded).

## 1. The model

| | Value | Source |
|---|---|---|
| Fan | 9215-Y at full speed: 28.1 Pa at no flow, 93.9 m³/h free air, a straight line between | J501 `thermal.fan` (S06) |
| Cooler's own resistance | 19.9 Pa at 27.5 m³/h (16.2 CFM), as k Q² | the J501 box's CFD operating point at ce018d5 (run with the fan blowing down; all of it given to the cooler: conservative) |
| Deck outlet (P1 deck as cut) | 31 cells, 8 mm square on an 11 mm pitch: 1,924 mm², open ratio 0.51, ζ = 1.39 on the cells' velocity | CAD (`body_frame.intake_cells`, round the fan at robot (-60, 9)); Idel'chik thin perforated plate |
| Riser's open sides (out) | 4 x 62 x 21 mm = 5,208 mm², ζ 1.5 (a 90° turn and out) | CAD; ζ assumed |
| Inlet louvres | 14 slots 4 x 46 mm a side (2,528 mm²), ζ 2.0 | CAD (`body_shell.LOUVRE`); Idel'chik grilles (1.6-2.4) |
| Heat into the body | 57.7 W: the module 40, the carrier 5, the TRACO TEP 150-4812WI 8.7 (70 W out at 89 %), the VESCs and boards 4 | J501 power modes; TRACO efficiency; the rest assumed |
| Plate | 0.6 K/W heatsink + 0.15 K/W pad and spreader | assumed (Seeed publishes no G48R curve) |

The room's air comes in through the louvres in the side walls' rear halves (beside the cooler's fins, above the
J501's port hatch), into the fins at ±y; the fan blows it up a printed duct from 2 mm over the fan frame to the turret
plate's opening (`body_shell.fan_duct`), out through the deck's cells and the riser's sides. The duct keeps the
exhaust from spilling into the body and coming back round through the fins (the J501 box re-breathed its exhaust:
+3.5 K without its skirt). The exhaust leaves 20-40 mm above the deck, sideways under the turret; the louvres are
below the deck's lip, 20-70 mm lower, and warm air rises, so it should not come back in (B16 checks the inlet).

## 2. Results

| Case | Flow | The body adds | Deck outlet | Louvre inlet | Cooler's inlet over the room | Through the cooler | Out of the riser |
|---|---|---|---|---|---|---|---|
| **P1 deck as cut, P3 louvres** | 12.9 CFM (21.9 m³/h) | 9.0 Pa | 7.3 Pa | **1.7 Pa** | **2.5 K** | 5.6 K | 33.1 °C |
| Rev B deck, cells on the minimum web over the fan's circle | 13.2 CFM | 8.3 Pa | 6.5 Pa | 1.8 Pa | 2.4 K | 5.5 K | 32.9 °C |
| Rev B deck with a plenum to r 60 (57 cells) | 14.3 CFM | 5.5 Pa | 3.4 Pa | 2.1 Pa | 2.2 K | 5.1 K | 32.3 °C |

- **The louvres meet the plan's rule** (the fan sees <= 5 Pa more from them): 1.7 Pa. Half the budget would ask
  2,605 mm² a side; the walls hold 2,528 under the deck's lip, close enough at 1.7 Pa.
- **The deck's cells are the body's restriction**, not the louvres: finger-safe 8 mm cells (the fan is 18 mm under
  the deck with the plate) on the sheet's minimum web cannot hold enough open area over the fan's circle. With the P1
  deck the body adds 9.0 Pa and the fan moves 12.9 CFM instead of the J501 box's 16.2: 5.6 K through the cooler
  instead of 4.4.
- **The cooler's inlet is 2.5 K over the room** (the limit is 3): the 17.5 W of the power supplies, boards and VESCs
  all end up in the air the fins draw (the walls lose some, so this is high). It is the tightest of the three numbers;
  B16 measures it at the fins' sides.
- **The temperatures pass** on this model: 33 °C out of the riser (limit 45), the plate about 60 °C (limit 70) with
  the assumed resistances.
- **Decision (D61):** keep the P1 deck's cells, fit the duct and the louvres, and let B16's thermometer decide. If
  the plate reads over 65 °C (5 K of margin), the fallback is a Rev B deck (lever 3) with the plenum field (57 cells to
  r 60 round the fan, the turret plate's opening opened to match, D2 re-run), which halves the outlet's loss. If the
  cooler's inlet reads over 3 K, the louvres move forward over the DDR-120C (the warmest supply) so its heat leaves
  with the air before the fins, or a second slot row is cut.
- **For the turret:** the J501's exhaust (about 33 °C, 13 CFM) now leaves the riser's sides under the turret's pan
  base. The turret box (`cad/turret_box.py`, the turret workstream's) was drawn for a fan drawing in through the
  deck: its intake shroud's idea is now the wrong way round.

## 3. Open

- The G48R's real thermal resistance at 13-16 CFM, and the fan's real curve: B16 measures the plate and the intake.
- The J501 project's CFD once its case is calibrated and steady: then this body's case (the cells, the shroud, the
  louvres) can run on a GB10, one solver at a time.
- The fan's PWM: the J501 drives it by temperature; the model takes full speed (the most it can move).
- The J501 project's CFD operating point (16.2 CFM) is from its run with the fan blowing down (ce018d5); its rerun
  with the fan blowing up gives the cooler's k again.
