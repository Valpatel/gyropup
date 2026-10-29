# Removable carrier input protection — requirements and candidate architectures

**The existing D14/U2 combination has no guaranteed overvoltage protection. Neither examined replacement architecture is ready for selection.** This note resolves the numerical requirements and the next design decisions: preserve the small converter footprint only with a qualified active protection stage, or allocate substantially more room for a wider-input converter. It does not release the carrier or select parts.

Scope: one removable base-board carrier, its U2 PAN supply and D14 interface. C2 also feeds the slip ring, but the remaining turret power system is not redesigned here. Tracking [issue81](https://github.com/Valpatel/gyropup/issues/81) / [PR82](https://github.com/Valpatel/gyropup/pull/82), coordinated with carrier PR67; follows [supplier audit](../supply/turret-carrier-2026-10-29.md). Calculations bind four source files at integration `6133c18fc735f47bac2e8eabde7967e27d9ae16e`. All supplier observations are dated 2026-10-29.

## Source and load contract

| Quantity | Required interpretation |
|---|---|
| Robot supply | 30–42 V documented steady BUS. The 42 V maximum excludes unmeasured charging tolerance, switching spikes and faults. |
| Stand supply | 15–20.5 V documented source range. Verify the minimum **at U2 terminals** under simultaneous head loads; source voltage is not terminal voltage after wiring/dropout. |
| U2 load | One 12 V pan servo plus the pendant/555 circuit. Tilt and feed have other supplies. |
| C2 load | Whole head branch behind the 10 A fuse: PAN plus slip-ring loads. The separate Jetson branch is excluded. A 10 A fuse is not an instantaneous 10 A clamp. |
| Existing current model | `sim/turret_power.py:49–61`: 0.15 A hold, 0.6 A move, 1.5 A torque-cap estimate, 90% efficiency. These do not bound a fault, startup or blocked motor. |
| Source impedance | Model estimates: pack 60 mΩ, robot 40 mΩ, head wiring 15 mΩ. No frequency response, inductance or measured surge envelope was found. |

The selected [Waveshare SKU22414 documentation](https://docs.waveshare.com/ST3215_Servo) specifies the **12 V** variant: 6–12.6 V operating range, 0.9 A rated current and 2.7 A stall. It states no current tolerance or worst startup/reversal peak. The separate 7.4 V variant is not interchangeable. Adding the estimated 10 mA loop gives **2.71 A / 32.52 W at 12 V**. A deliberately explicit 20% servo-current contingency gives **3.25 A**; this is a screening assumption, not a guaranteed upper bound.

For 2.71 A output, the efficiency sensitivity is:

| Assumed efficiency | Input current at 15 V / 42 V | Converter loss |
|---:|---:|---:|
| 80% | 2.710 / 0.968 A | 8.13 W |
| 90% | 2.409 / 0.860 A | 3.61 W |
| 95% | 2.282 / 0.815 A | 1.71 W |

These are `Pout/(Vin×η)` calculations; no efficiency curve is being promoted to a guaranteed minimum. The exact circuit's 10 mA auxiliary estimate, servo current and enclosure thermal behavior still require verification.

## Why the current protection fails its claim

[Pololu D36V50F12](https://www.pololu.com/product/4095) permits 13.3–50 V input, specifies 12 V ±4%, and limits its reverse protection to 40 V. Its 4.5 A headline is typical at 36 V and depends on heat removal. The existing authored envelope is 25.4×25.4×9.5 mm.

[Taiwan Semiconductor P6KE51A, P2203](https://services.taiwansemi.com/storage/resources/datasheet/P6KE%20SERIES_P2203.pdf) has 43.6 V standoff, 48.5–53.6 V breakdown at 1 mA and 70.1 V maximum clamp at 8.6 A. The 600 W rating uses a 10/1000 µs waveform. Thus a compliant device can still be below its breakdown test current at U2's 50 V limit; selecting the 48.5 V minimum does not prove even slow-overvoltage protection. The specified clamp is **20.1 V above U2's limit**. Catalog maker identity is still unfrozen, so another vendor needs its own data.

A numerical counterexample exposes the missing source bound: a hypothetical 90 V source through 0.1 Ω would demand 199 A if the clamp stayed at 70.1 V; through 1 Ω, 19.9 A. Both exceed the 8.6 A test point. This is **not a predicted waveform** or energy rating; it proves that a fixed clamp number cannot be applied independently of source impedance. Even a benign-looking inductance estimate is incomplete: 100 µH at 10 A stores 5 mJ, while a connected source can continue delivering energy. No finite worst-case surge energy has been established.

The 42 V normal source also exceeds U2's published 40 V reverse-protection limit. D8 and its fuse may provide upstream reverse clamping, but their fault-current/time/temperature coordination remains unproven. They cannot be credited as a guaranteed protector by this calculation.

## Two correction architectures

| Candidate architecture | Dimensions and capability | Consequence for this carrier |
|---|---|---|
| **A: wider-input U2 converter**, TRACO TEP40-7212UIR | 14–160 V operating input; 185 V for at most 1 s; 12 V / 3.33 A / 40 W. Body 57.9×36.8×12.7 mm; pins protrude separately. | Body alone exceeds the 50.8×30 mm PCB. Requires a new support/thermal/routing arrangement. It tolerates the cited D14 clamp point but does not bound D14 energy or protect other BUS loads. |
| **B: active input disconnect**, LTC4368 with back-to-back MOSFETs, preferably evaluated with 60 V U2 candidate with the same board outline | LTC4368IMS package: approximately 3×4.9 mm including leads, 1.10 mm maximum height; two candidate CSD19531Q5AT MOSFETs each 5×6 mm. D42V55F12 is 25.4×25.4×9.017 mm. | The converter board outline remains 25.4×25.4 mm, but protection needs a custom PCB, copper, passives, capacitance and a validated thermal path. Package dimensions are **not** a complete board footprint or a fit approval. Placement before all C2 loads versus only U2 changes the requirements substantially. |

A 60 V converter by itself is an incomplete shortcut: [Pololu D42V55F12](https://www.pololu.com/product/5577) remains **10.1 V below** the cited 70.1 V clamp. Its published current is typical; 12 V ±3% improves static output margin but does not establish transient immunity. [Manufacturer dimensions](https://www.pololu.com/product/5577/specs) are not proof of pin/keepout interchangeability.

### A — wider-input conversion

The [manufacturer TRACO sheet, 7 February 2024, distributor mirror](https://atta.szlcsc.com/upload/public/pdf/source/20240410/9508BE6CC3D74E556CF61D2C04F6A5CF.pdf) supplies the ratings and drawing; the direct manufacturer PDF returned403 during this check. Its temperature-dependent power curves were not retrieved. Full 40 W over the entire ambient/input range is **not established**.

Conservative addition of set, line, load and full specified temperature coefficients yields a **12.30 V static upper estimate**, before ripple, startup or load steps. At the 3.25 A screening load this is **39.975 W**, essentially the 40 W ceiling before further margin. Only **1 V** separates the documented 15 V stand source from the 14 V converter minimum before source/wiring drops.

Using the sheet's typical 8.3 K/W case-to-ambient resistance and a hypothetical 50°C ambient, the 32.52 W load gives approximately **76.7°C case at 91% efficiency**, but **117.5°C at 80%**, above the 105°C case limit. Both are sensitivity calculations, not predictions inside the carrier. Verify the missing derating curves and actual heat path before accepting this option. Input/output capacitors, fuse guidance, sense connections, isolation-ground treatment and servo regenerated energy also need engineering; the module's internal output OVP range is above the servo's maximum and does not qualify the servo rail.

### B — active cutoff and converter margin

[ADI LTC4368 rev C](https://www.analog.com/media/en/technical-documentation/data-sheets/ltc4368.pdf) supports 2.5–60 V operation and input overvoltage protection to 100 V. Its −40 V reverse limit is insufficient for an unprotected −42 V reversal. A positive transient clamp, reverse-fault protection, MOSFET rating and loop inductance still need coordination. This controller disconnects; it is not a linear surge regulator.

The calculator enumerates an **independent OV divider**, 4.99 kΩ bottom, 0.1% resistors, comparator 492.5–507.5 mV, ±10 nA leakage and 20–32 mV hysteresis. Values are illustrative, not selected circuit parts:

| Top resistor | Rising cutoff range | Recovery range | Tradeoff |
|---:|---:|---:|---|
| 430 kΩ | 42.843–44.332 V | 40.059–42.585 V | Cuts early, but does not guarantee reconnection at a healthy 42 V after a fault. |
| 464 kΩ | 46.192–47.797 V | 43.190–45.914 V | Static reconnection margin exists at 42 V, but there is little margin for the existing 50 V U2. |

The specified 2 µs comparator delay requires **50 mV overdrive at 12 V VIN**. With the second divider, reaching that overdrive can correspond to **52.506 V input**, already above the existing U2 limit. The specified gate delay has its own 2.2 nF condition. Adding those delays and applying them blindly at 42 V with a different MOSFET/gate network would invent a guarantee. The lower divider leaves only 1.301 V to 50 V at the same overdrive condition, before gate discharge and wiring overshoot.

A candidate 60 V converter gives room to propose a **55 V terminal-peak design target**, leaving 5 V to its limit; this is an acceptance target requiring measured waveform and tolerance evidence, not a proven output of the cutoff. It applies **only to that U2 branch**. Other 50 V BUS devices would still require their own lower target or qualified shared protection.

[MOSFET candidate TI CSD19531Q5A rev B](https://www.ti.com/lit/ds/symlink/csd19531q5a.pdf) is rated100 V and has at most6.4 mΩ at10 V gate/25°C. A pair dissipates1.28 W at10 A versus0.115 W at3 A. An assumed doubling of resistance makes those2.56 W and0.230 W; it is not a guaranteed hot-resistance bound. Its safe operating area and actual board cooling, not the headline drain-current rating, must cover turn-on and interruption. The ADI example's SiR870DP was out of stock at the checked distributor; the TI candidate is not an approved substitute.

For a 1%-tolerance sense resistor, a nominal12.5 mΩ example has a **3.168–4.848 A** steady forward trip range; 4 mΩ gives **9.901–15.152 A**. Neither is a precise current limiter. The former can trip below the low-voltage contingency input current; the latter can interrupt an estimated head pulse near10 A. Thresholds during output startup differ. Do not copy one U2 threshold into the complete C2 branch.

The shared940 µF bank stores **0.829 J at42 V** (0.995 J with a20% capacitance scenario). An illustrative33 nF gate capacitor, −10% tolerance,60 µA pull-up and+20% bank tolerance gives **2.279 A charging current**, before active loads. This is a source-follower sizing estimate; its isolated-gate resistor, stability, startup safe operating area, discharge and measured capacitance remain open. A U2-only stage sees a different bank and needs its own calculation.

## Output rail and fault behavior are separate requirements

The existing12 V ±4% rail leaves only **0.12 V** below the servo's12.6 V limit; the60 V replacement's±3% leaves0.24 V. At100 µF, the existing worst static level can absorb only **0.150 mJ** before crossing12.6 V. That energy arithmetic does not claim the real servo regenerates any particular amount; it shows why input protection cannot qualify output braking/reversal behavior. Neither larger capacitance nor the converter's internal OVP is automatically sufficient.

Any cutoff may drop the pendant/555 rail and reset the servo. The intended response must be fail-off, with no automatic arming and a defined recovery procedure. Check signal backfeed into unpowered parts and retained charge before treating the carrier as removable. Those behaviors require circuit/firmware review and controlled bench evidence; no test was energized here.

## Dated availability, not a purchase list

| Exact candidate | Observed offer | Remaining supply limit |
|---|---|---|
| [TEP40-7212UIR](https://www.digikey.com/en/products/detail/traco-power/TEP-40-7212UIR/12471340) | 3 listed; $138.18 each;21-week factory lead | Small stock, no delivery commitment. |
| [D42V55F12 /5577](https://www.pololu.com/product/5577) | $47.95; rationed, backorders allowed | Quantity and ship date unverified. Earlier cached prices differed. |
| [LTC4368IMS-2#PBF](https://www.digikey.com/en/products/detail/analog-devices-inc/LTC4368IMS-2-PBF/6820038) | 1,295 listed; $8.05 each;25-week factory lead | Complete board/passive selections absent. |
| [CSD19531Q5AT](https://www.digikey.com/en/products/detail/texas-instruments/CSD19531Q5AT/4840661) | 1,756 listed; $3.35 each cut tape;12-week factory lead | Candidate pair needs electrical/layout qualification. |

One-piece price tiers were displayed; order multiples and checkout delivery were not confirmed. Replenishment lead is distinct from listed stock. No purchases or supplier communications occurred.

## Decision and release requirements

**Proposed next design work, not a selected architecture:** develop the active cutoff plus a 60 V converter with the same board outline as a U2-only option, because it preserves more carrier space. Keep TRACO as a larger-layout fallback. Do not freeze the U2 mounting or print a final electronics carrier until its owner resolves these gates:

1. Freeze source maximum/tolerance and fault envelope at the carrier terminals: positive/negative peak, rise time, duration, repetition, source impedance and available energy. Measure safe operating events and use controlled injection for the agreed fault envelope; do not extrapolate this arithmetic into a destructive test recipe.
2. Freeze maximum servo/input load and temperature, including startup, blocked motion, reversal and auxiliary current. Use an electrically justified limit or measured worst case with margin; firmware torque percentage alone is insufficient.
3. For unchanged U2, propose ≤48 V terminal peak and verify the full envelope; for60 V U2, propose ≤55 V. Both targets require qualification. A shared stage must satisfy **every** downstream limit and head inrush/current, not merely U2.
4. Demonstrate servo pads remain6–12.6 V throughout the accepted operating envelope, including converter tolerance, wiring, load steps and regeneration. Define permitted brief brownouts and safe recovery rather than concealing them.
5. Close thermal/SOA, reverse polarity, D8/fuse/holder coordination and residual-energy requirements. Higher input rating does not close those items.
6. Publish selected schematic/BOM, manufacturer footprints, connector pose, removal path and measured service slack in PR67. Until then, this note's package dimensions are comparison evidence only.

## Reproduce and inspect

`python research/protection/calculate_carrier_protection.py --check` verifies frozen source hashes and the deterministic [result receipt](carrier-input-protection.results.json). `python research/protection/test_carrier_protection.py` checks independent arithmetic examples, invalid input rejection and boundaries between static margins and unproven transient behavior. Regenerate reviewed changes with `--write`.

The [inputs](carrier-input-protection.inputs.json) distinguish manufacturer facts from scenario assumptions and retain primary URLs/revisions and unavailable evidence. The receipt hashes inputs and calculator. This is algebraic screening, not SPICE, transient FEA, a completed circuit, supplier qualification or proof of safe hardware.
