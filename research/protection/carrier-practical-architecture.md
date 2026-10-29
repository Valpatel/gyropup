# Practical PAN power architecture before carrier allocation

**Recommendation for the next circuit revision:** develop the complete LTC4359 Rev F Figure 10 reverse-input front end ahead of the existing LTC4368 cutoff/current-sense stage and Pololu D42V55F12 converter. Replace the high-loss series diode; preserve the 12 V PAN supply and existing source contract. Budget a separate protection PCB and a real heat path before mechanical placement. This is a direction for review, **not a selected BOM, completed circuit or permission to build/energize**. [Issue 91](https://github.com/Valpatel/gyropup/issues/91) / [PR92](https://github.com/Valpatel/gyropup/pull/92) follow the candidate merged at `912439f9bc9d5338319db50ed71c75d3136466d4`.

The larger RECOM module below is the fallback if compact converter thermal/startup qualification fails. Its greater positive input range does not eliminate reverse-input protection, output regeneration or layout work. No circuit, catalog, carrier or actuator selection changes in this checkpoint.

## Two concrete directions

| Direction | Conditional electrical screen | Physical and supply consequence | Decision |
|---|---|---|---|
| Full LTC4359 Figure 10 network + IPB200N25N3G + retained LTC4368/current sense/EN + Pololu 5577 | At a proposed **60 mΩ hot front-FET bound**, about **0.954 W** front-path dissipation and **1.303 V** enable margin at the 15 V source, **after gate enhancement**. Candidate B gave 5.980 W / 0.069 V. | D2PAK and clamp network require a new PCB. A useful manufacturer thermal condition uses **6 cm² copper on 40×40 mm FR4**, not merely the transistor footprint. Pololu is rationed; one reference zener is scarce. | Preferred next circuit candidate; qualify its full floating-reference network, startup and real heat path first. |
| Same qualified reverse front end + **RP60Q-11012SRUWB/P** and reviewed branch protection/control | 14–160 V, 12 V/5 A, 60 W. Conservative summed output corner is 12.30 V, or 39.975 W at 3.25 A. Only **1 V** remains at 15 V before input-path drops. | Body **57.9×36.8×12.7 mm**, about **1.40×** the legacy board's planar area, plus leads/mounting/cooling. Distributor lists two units at $226.98 each. | Fallback requiring a substantial layout change. No demonstrated startup or thermal advantage at the actual low-line/ambient corner. |

The first screen reuses the reviewed candidate's conservative enabled-load input current, 3.986754 A, and 4.434 A onset current budget. It changes only the already-enhanced series element: `P=I²R`, and `margin_new=margin_B+1.5−I_budget×R`. The 60 mΩ value is a **design acceptance assumption**, not an Infineon guaranteed hot maximum. The comparison does not inherit the old diode candidate's startup pass. Front-controller current, gate charging, cold body-diode drop and changed intermediate-node dynamics need a new native circuit analysis. See the [reproducible results](carrier-practical-architecture.results.json).

## Reverse-input decision and its limits

The existing D8 is a **shunt** across BUS/GND after the shared 10 A head fuse; it is not a series reverse barrier. No fuse/diode I²t coordination or negative-clamp credit is established. The source can be −42 V while the front end's downstream node is charged to an assumed +55 V: **97 V differential**. The +55 V value is a screening ceiling, not a measured transient limit. [Candidate B contract and topology](../../hardware/carrier-pan-protection/README.md)

The [ADI LTC4359 Rev F datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ltc4359.pdf), pp.2–3,10,12, distinguishes its raw −40 V input limit from **Figure 10's complete −72 V reverse-input application**. Its floating VSS diode, sense resistor and zener network matter; they constrain internal pin differences while the power MOSFET blocks the external voltage. Figure 10 names IPB200N25N3G, SMAT70A, MMSZ5231B, BZG03C75, DDZ9699T, S1B, SMCJ150A, 2 kΩ and 47 nF. Preserve the complete reference topology. Do not tie VSS back to ground or omit clamps while retaining its extended-range claim. The manufacturer's application supports this direction, not an already-proven −42/+55 V hot-insertion waveform in our wiring.

Two simpler families were screened out: [LM7480-Q1 Rev C](https://www.ti.com/lit/ds/symlink/lm7480-q1.pdf) permits 85 V C−A; [LM74910H-Q1 in Rev C family datasheet](https://www.ti.com/lit/ds/symlink/lm74900-q1.pdf) permits 88 V. Both are below 97 V. Additional pin-to-input restrictions also apply; passing one differential would not establish whole-device acceptance. A negative-input headline cannot replace this check.

This checkpoint does **not** claim the reference clamps are fully qualified. [SMAT70A](https://www.diodes.com/datasheet/download/SMAT70A.pdf) specifies 100 V maximum clamp at 3.5 A under its stated temperature/pulse conditions; its temperature coefficient does not establish a 100 V ceiling over the enclosure envelope. The candidate modern [BZG03C75 M-series](https://www.vishay.com/docs/86138/bzg03c-m-series.pdf) order code needs comparison with the exact reference grade. Resistor pulse energy, the SMCJ150A/FET temperature margin, gate-zener leakage and negative hot-insertion coupling remain open. Source inductance/energy/repetition and clamp peak voltages remain **unknown**. No sum of nominal zener voltages is used as a pass.

## Thermal and package boundary

[Infineon IPB200N25N3G Rev2.5](https://www.infineon.com/assets/row/public/documents/24/49/infineon-ipp-b-i-200n25n3-g-datasheet-en.pdf) gives 250 V VDS and 20 mΩ maximum at 10 V gate, 25°C; these are not hot operating guarantees. Its D2PAK maximum lead/body envelope is 15.88×10.31×4.57 mm and land envelope 16.25×10.90 mm. The 40 K/W thermal condition uses 6 cm² copper on a 40×40×1.5 mm vertical FR4 board in still air; minimum-footprint θJA is 62 K/W. Our 0.954 W screen needs ≤41.94 K/W to hold a **chosen**125°C junction target at a **scenario**85°C ambient. Thus the generous copper condition is plausible, while the minimal footprint fails this screen. Neither establishes the assembled enclosure temperature; converter, cutoff and clamp losses add heat nearby.

[Pololu 5577](https://www.pololu.com/product/5577) is a 25.4×25.4 mm board with maximum input 60 V and nominal12 V output ±3%. Its 4.5 A continuous figure is typical at 42 V input and depends on heat dissipation. The 3.25 A screening load is not a proven continuous enclosed rating. Rationed supply and unknown actual low-line efficiency/dropout/startup remain selection gates.

[RECOM RP60Q-RUW Rev5-2024](https://recom-power.com/pdf/Powerline_DC-DC/RP60Q-RUW.pdf) gives the listed B/P module's body and input/output ratings. Summing set/line/load/temperature magnitudes yields 12.30 V for this screen. At 39.975 W output, efficiency assumptions 80/85/89% give 9.99/7.05/4.94 W loss. The 89% figure is typical at 72 V/full load/25°C, **not guaranteed at 15 V**. At 85°C ambient and 110°C baseplate ceiling, required thermal resistance is 2.50/3.54/5.06 K/W: all below the unheatsinked 6.3 K/W condition. Derating plots use a 160×100 mm 105 µm Eurocard; do not transfer them to a small carrier. Its 120–135% output overvoltage protection corresponds to 14.4–16.2 V, above the servo's 12.6 V limit; it does not solve output regeneration. Exact `/P` control and `B` bus/UVLO pins require a fresh interface map.

The older **RP60Q-11012SRUW/P** distributor record instead states 16 V minimum and nonstock. Do not borrow the newer 14 V rating for that order code or assume a pin-compatible substitution. The exact B/P module and its delivered revision need confirmation before an order.

Mechanical coordination on 2026-10-29: **no additional protection-board envelope is allocated**. Existing U2 reservation 25.4×25.4×9.5 mm is unqualified. Legacy PCB 50.8×30 mm and opt-in C3 support X56..93,Y−27..19,Z6..56 mm do not provide free area. Three logical boundaries remain BUS_HEAD_FUSED, GND and 12V_PAN; the protected PAN input is not the shared C3 BUS. No package here is placed in CAD or declared serviceable.

## Dated availability, not a shopping commitment

The [structured input/source record](carrier-practical-architecture.inputs.json) contains exact manufacturer order codes, primary-document revisions, available PDF hashes, supplier links, quantities, price, minimum order and limitations observed on 2026-10-29. Licensed PDFs stay outside Git. Observations can come from indexed pages; they are neither reserved stock nor quotes.

| Exact part | Observed offer | Limitation |
|---|---|---|
| [LTC4359IDCB#TRPBF](https://www.digikey.com/en/products/detail/analog-devices-inc/LTC4359IDCB-TRPBF/3306828) | 1,712; $9.47; cut tape minimum 1 | 10-week factory lead; 2×3 mm DFN, I-grade−40..85°C ambient |
| [IPB200N25N3GATMA1](https://www.digikey.com/en/products/detail/infineon-technologies/IPB200N25N3GATMA1/2344863) | 10,794 indexed; $8; cut tape minimum 1 | 52-week factory lead; indexed count can lag |
| [DDZ9699T-7](https://www.mouser.com/en/ProductDetail/Diodes-Incorporated/DDZ9699T-7?qs=mQbszxtPdlOBwg08InvD3Q%3D%3D) | Cached Mouser page 1 at $0.53; 40-week factory lead; DigiKey 0 | Refresh403; **not confirmed reliable build stock**. Qualify an exact replacement or confirm stock before selection. |
| [Pololu 5577](https://www.pololu.com/product/5577) | $47.95; rationed; backorders allowed | Count and committed lead time unknown |
| [RP60Q-11012SRUWB/P](https://www.digikey.com/en/products/detail/recom-power/RP60Q-11012SRUWB-P/24390369) | 2; $226.98; tray minimum 1; 17-week factory | Do not add factory-stock 2 to listed-stock 2; exact B/P identity matters |

The structured record also covers each Figure 10 diode and a 2 kΩ pulse-resistor candidate. These are obtainable **offers**, not a fully qualified replacement BOM: current MMSZ5231B-7-F replaces the discontinued seller code, BZG03C75-M3_A-08 needs grade confirmation, and the resistor's actual pulse curve is not yet accepted. A 47 nF capacitor and complete mounting/thermal BOM are not selected at this architecture stage.

## Next bounded checkpoint

Before a larger schematic/layout commitment, agree an actual candidate PCB contour, component-side heights, connector access and strain-relief zones with the carrier author. No such contour is established here; the 40×40 mm thermal test board is neither a minimum board size nor proof that a smaller design fails. An eventual bench reference board would be explicitly unmounted and would not count as carrier integration. Then proceed with the preferred direction's **native schematic revision and per-pin fault-state check**, preserving the complete Figure 10 network and source references. Confirm gate-zener availability/equivalence and evaluate clamp/current/pulse tolerances before declaring it viable. Then examine initial body-diode conduction and retained converter EN sequencing at 15 V; do not count the fully-enhanced margin as startup proof. Agree a real board/thermal envelope with the carrier author before physical placement. Output-regeneration protection, actual source transient envelope and assembled thermal validation remain separate explicit qualification requirements.

No local heavy solve was needed. Reproduce the arithmetic and its source binding:

```sh
python research/protection/calculate_practical_architecture.py --check
python -m unittest discover -s research/protection -p 'test_practical_architecture.py' -v
```

The receipt binds the comparison inputs, note, tests, calculator and the actual candidate-B calculation/circuit source. Tests include raw-controller differential failures, excess hot resistance collapsing voltage/heat margins, old 16 V variant rejection, nonfinite values, qualification-flag rejection and current receipt identity. This is not a simulation or hardware test report. Native KiCad files remain unchanged.
