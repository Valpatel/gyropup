# Fabrication rules and prices for gyropup

Checked 2026-10-25. Every number has a source tag like [B1]. The sources are listed at the end. If a value was not published or could not be fetched, it says so. Values we calculated ourselves are marked **derived** or **estimate**, and their inputs are shown. The machine-readable version is `catalog/fabrication.json`.

Plan of record: gyropup is **mostly 3D printed**. The first build is PLA on the Bambu P1S. Later builds move to carbon-fibre-filled filament on an upgraded or newer Bambu printer. SendCutSend metal and CF tubes are **optional upgrades** for single parts. This report follows that order: printing first, upgrades after.

---

## 1. Rules the designer should apply

### 1.1 Printed parts (default)

1. **Orient leg links flat**, so bending stress runs along the layers. In CNC Kitchen's test, PLA printed upright reached 31 MPa against 63 MPa printed flat, about 50%. Printing at 45° gave 40 MPa [K5]. Bambu's datasheets give the Z-to-XY tensile ratio as 0.89 for PLA Basic, 0.47 for PET-CF and 0.34 for PPA-CF (**derived** from [B1][B11][B14]). So the CF filaments are much weaker across layers than plain PLA.
2. **Stress allowables for PLA.** Ezeh & Susmel suggest a conservative static reference strength of **22 MPa**. They also give a fatigue limit at 2×10⁶ cycles of **10% of UTS** (90% survival), with an S-N inverse slope of 5.5 [P1]. For PLA Basic (35 MPa XY [B1]), the cyclic stress limit is therefore 3.5 MPa (**derived**).
3. **Heat.** PLA Basic softens at 54 °C (HDT at 1.8 MPa), with a Vicat temperature of 57 °C and Tg of 60 °C [B1]. In a loaded oven test, PLA started to give at 60 °C, PETG at 80 °C and ASA at 110 °C [K1]. **No PLA part should touch a motor housing** unless the housing temperature has been measured well below 54 °C. On a stock P1S, the fallbacks are:
   - PETG (HDT 68 °C [B5])
   - ASA (92 °C [B8])
   - annealed Polymaker HT-PLA Pro (HDT at 0.45 MPa rises from 56.3 to 107.6 °C after 30 min at 100 °C; no hardened nozzle or enclosure needed) [M3]

   We did not research motor temperatures.
4. **Fill the outer skin first.** Bending and torsion loads are carried at the outside of a part. Gradient (outer-dense) infill was about 30% stiffer at equal weight [K2]. In tension-tension fatigue, 100% infill lasted 43,406 cycles against 28,325 at 50% infill, and its modulus was 2553 MPa against 2004 MPa [P2]. No cited source gives a wall count, so pick one by test.
5. **Threads in printed parts: use heat-set inserts.**
   - M3 hole: 4.0 mm nominal if drilled. For an as-printed PLA hole, 4.2 mm worked best, because printed holes come out about 0.25 mm undersize [K6].
   - Pull-out strength is about 1400 N per M3 insert [K6].
   - Iron temperature is about 225 °C for PLA and 245 °C for PETG.
   - Make blind holes about 1 mm deeper than the insert [K7].
   - In PETG, torque-out was 3 Nm with an insert against 1 Nm for a screw driven straight into the plastic [K8].
6. **Pivots: use bearings in printed seats, with a shoulder bolt as the shaft.** A printed hole should never act as the bearing surface. This is the Stanford Doggo five-bar pattern: two deep-groove bearings stacked in one link, with a shoulder bolt through them into the opposing link [D1]. Size the seats from a printed test coupon, then correct with Bambu Studio's XY hole compensation [B20]. Bambu publishes no press-fit allowance.
7. **CF-filled filament needs a hardened steel nozzle.** Use 0.6 mm as the first choice. A 0.4 mm hardened nozzle is fine for Bambu PLA-CF and PETG-CF. Never use 0.2 mm [B19]. A P1S stainless nozzle showed visible wear after 10 h of PETG-CF [B21].
   - PA, PC, ABS and ASA, and their CF/GF versions, need an enclosed printer.
   - PLA, PETG and TPU print fine on an open frame. An enclosure is recommended for PETG [B19].
8. **Rescaling a part to another material** (rectangular section, width fixed; table in §2.3). The new thickness is the larger of:
   - `t_new = t_PLA·(E_PLA/E_new)^(1/3)` for equal stiffness
   - `t_new = t_PLA·(σ_PLA/σ_new)^(1/2)` for equal strength

### 1.2 Metal and CF upgrades (optional)

- **SendCutSend holes.** Use `max(quoter minimum, 1.0 × t)` for metals. The quoter accepts smaller holes (§4.2). SendCutSend's guidance is laser holes ≥ 50% of thickness [S2], and the 5052 and 6061 pages say holes ≥ thickness [S4][S5]. Keep holes 1.5–2× t from edges for 6061 [S5] and 2× t for 5052 [S4].
- **Bending at SendCutSend.** Bent brackets must be **5052, steel or stainless**. 6061 and 7075 sheet have no bending option in the quoter [S1]. Bend radius and K-factor are fixed per thickness (table in §4.3). Keep features at least half the die width from the bend centreline [S3].
- **CF tubes cannot be threaded** [C1]. Join them with clamps or bonded inserts.

### 1.3 Price model for the guide

- **Printed part:** filament mass (g) × $/kg ÷ 1000. PLA costs $14.99/kg refill or $17.99/kg on a spool [B1s]. The other filaments are in the table in §2.2.
- **SendCutSend part (estimate):** price ≈ bounding-box in² × rate × quantity factor + services. SendCutSend does not publish a formula; this is fitted to their examples (§4.5).
  - Rate: about $1.0–1.1/in² for small, simple 5052 parts at qty 1. This is **estimate** from 2 examples.
  - Quantity factor at qty 100: 0.21–0.55, median 0.31 (**derived** from 15 examples).
  - Bent parts have a minimum charge of about $19 (implied by their blog).
  - Always label the result "estimate – upload the DXF to confirm".
- **CF tube:** $/m by OD (§3).

---

## 2. 3D printing (primary path)

### 2.1 Printers and what each can print

| Printer | Price (US store) | Build (mm) | Stock nozzle | Max nozzle | Chamber | CF filament? | Src |
|---|---|---|---|---|---|---|---|
| **P1S** (current) | $399; AMS Combo $549; AMS 2 Pro Combo $579 | 256×256×256 | 0.4 mm **stainless** | 300 °C | enclosed, **passive** (regulator fan, no heater) | Not out of the box. Bambu: "not recommended… before an extruder and hotend upgrade" | [B16] |
| P1S upgrade | Hardened Steel Upgrade Combo **$49.48** (0.4 hardened hotend + hardened extruder gears) | – | hardened 0.4/0.6/0.8 complete hotend $34.99 each (hotend only $14.99); gear assembly $19.99 | 320 °C (hardened hotend, retailer listing) | – | yes, PLA-CF/PETG-CF/PET-CF/PA-CF | [B17][B18][B21][R1] |
| P2S | $549; Combo $749 | 256×256×256 | **hardened** nozzle and extruder gears | n/p | enclosed, no active heat, "50 °C chamber ready" | yes | [B22] |
| X2D | $649; AMS Combo $899 | n/p | n/p on store page | 300 °C | **65 °C active heating**, dual nozzle | n/p | [B23] |
| H2S | $1,199; AMS Combo $1,399 | 340×320×340 | n/p on store page | 350 °C | 65 °C active heating | n/p | [B24] |
| H2D | $1,549–1,749 (two "standard" listings) | 325×320×325 | **hardened** 0.4 mm, hardened gear | 350 °C | 65 °C active heating, dual nozzle | yes | [B25] |
| H2C | $2,199–2,499 | 330×320×325 | 0.4/0.6 hardened hotends | 350 °C | 65 °C active heating | yes | [B26] |
| X1C / X1E | not sold new in the US store sitemap; refurbished X1C Combo $649 | – | – | – | – | – | [B27] |

n/p = not published on the page we fetched.

Chamber temperatures from Bambu's datasheets:

| Material | Chamber | Src |
|---|---|---|
| PET-CF, PA6-CF, PAHT-CF | 45–60 °C | [B11][B12][B13] |
| PPA-CF | 50–80 °C | [B14] |
| PPS-CF | H2 series and X1E only | [B19] |

**So:** a P1S with the $49.48 combo, plus a $34.99 0.6 mm hardened hotend, can print PLA-CF, PETG-CF and (passively warmed) PET-CF and PA-CF. PPA-CF wants a heated-chamber machine (X2D, H2S, H2D or H2C).

### 2.2 Filament properties and prices

All values come from Bambu datasheets [B1–B15]: 100% infill printed specimens, ISO 527/178/75. Prices are from the Bambu US store on 2026-10-25, per kg, refill price where sold, otherwise the spool price [B1s–B15s].

| Filament | $/kg | ρ g/cm³ | Tensile XY / Z MPa | E (tensile XY) GPa | Flex mod XY GPa | Flex str XY / Z MPa | HDT 1.8 MPa °C | Hardened nozzle | Enclosure | Src |
|---|---|---|---|---|---|---|---|---|---|---|
| **PLA Basic** | 14.99 (spool 17.99) | 1.24 | 35 / 31 | 2.58 | 2.75 | 76 / 59 | 54 | no | no | [B1] |
| PLA Matte | 15.99 | 1.31 | 30 / 22 | 1.96 | 2.36 | 53 / 29 | 52 | no | no | [B2] |
| **PLA Tough+** | 20.99 | 1.21 | 34.9 / 20.9 | 1.86 | 2.14 | 65 / 54 | 58 | no | no | [B3] |
| **PLA-CF** | 31.99 | 1.22 | 38 / 26 | 2.79 | 3.95 | 89 / 49 | 54 | **yes** | no | [B4] |
| **PETG Basic** | 13.99 | 1.25 | 51 / 35 | 2.78 | 1.95 | 75 / 56 | 68 | no | recommended | [B5] |
| PETG HF | 15.99 | 1.28 | 34 / 23 | 1.81 | 2.05 | 64 / 48 | 62 | no | recommended | [B6] |
| **PETG-CF** | 31.99 | 1.25 | 35 / 29 | 2.46 | 2.91 | 70 / 48 | 68 | **yes** | recommended | [B7] |
| ASA | 29.99 (spool) | 1.05 | 37 / 31 | 2.45 | 1.92 | 65 / 40 | 92 | no | yes | [B8] |
| ABS | 15.99 | 1.05 | 33 / 28 | 2.20 | 1.88 | 62 / 39 | 84 | no | yes | [B9] |
| PC | 39.99 (spool) | 1.20 | 62 / 56 | 2.11 | 2.31 | 108 / 55 | 117 | no | yes | [B10] |
| **PET-CF** | 84.99 (0.5 kg $44.99) | 1.29 | 74 / 35 | 4.73 | 5.32 | 131 / 49 | 182 | **yes** | yes | [B11] |
| **PA6-CF** | 79.99 (0.5 kg $42.99) | 1.09 | 102 / 48 | 4.43 | 5.46 | 151 / 80 | 164 | **yes** | yes | [B12] |
| PAHT-CF | 94.99 (0.5 kg $49.99) | 1.06 | 92 / 47 | 3.86 | 4.23 | 125 / 61 | 170 | **yes** | yes | [B13] |
| PPA-CF | 199.99 (**derived**: $149.99 per 0.75 kg) | 1.25 | 168 / 57 | 11.8 | 9.86 | 208 / 63 | 196 | **yes** | yes, 50–80 °C chamber | [B14] |

Hardened-nozzle and enclosure columns are from [B19].

Two things to note:

- **PETG Basic is stronger than PLA in tension but *less stiff* in bending** (1.95 vs 2.75 GPa). It needs about 12% more thickness for equal stiffness (§2.3).
- The **PA** grades lose a lot when wet. Conditioned PA6-CF (about 3% water) kept 56% of its dry strength and about one third of its stiffness. Dry it at 80 °C for about 20 h [K4].

**TPU for tyres and bumpers** [B15][B28][B29]:

| TPU | $/kg | ρ | Tensile XY / Z MPa | E XY MPa | Elongation XY | Notes |
|---|---|---|---|---|---|---|
| TPU 95A HF | 41.99 | 1.22 | 27.3 / 22.3 | 9.8 | >650% | tyre tread candidate |
| TPU 90A | 41.99–44.99 | 1.24 | 12.5 / 10.1 | 5.3 | >650% | softer, grippier |
| TPU 85A | 41.99–44.99 | 1.18 | 12.0 / 10.5 | 6.8 | >700% | softest |
| TPU for AMS (68D) | 34.99 | 1.26 | 22.4 / 11.2 | 1190 | >650% | stiff; bumpers, not tyres |

The 85A/90A/95A grades are **not AMS-compatible**; feed them from an external spool [B19].

**Third-party filament prices**, US stores on 2026-10-25:

| Filament | Price | Notes | Src |
|---|---|---|---|
| Polymaker PolyLite PLA | $19.99/kg (3 kg $49.99) | | [M1] |
| Polymaker PolyLite PLA Pro | $23.99/kg | | [M2] |
| Polymaker HT-PLA Pro | $24.99/kg | | [M3] |
| Polymaker Fiberon PET-CF17 | $44.99/kg | | [M4] |
| Polymaker Fiberon PA6-CF20 | $52.99/kg | product page claims 109 MPa and over 8.6 GPa XY | [M5] |
| eSUN PLA+ | about $20.99/kg | third-party Amazon seller, 2026-08-01; no official price found | [E1] |

eSUN's published tensile figures conflict: 63 MPa on an eSUN-affiliated page against 53.3 MPa XY / 31.2 MPa Z at a retailer. The official datasheet was not retrieved.

PLA+ is not simply better than PLA. In CNC Kitchen's test, PolyMax PLA+ against PolyLite PLA gave 43 vs 57 MPa tensile and about 2200 vs 3000 MPa stiffness, with about 4× the impact toughness and the same 65 °C failure [K3]. Annealing PLA (100 °C, 45 min) added 7.5% tensile but shrank the part up to 10% in XY [K9]. **Don't anneal precision PLA parts.**

### 2.3 Material ladder: thickness factors for the designer (**derived**)

Inputs are the XY flexural modulus and strength from §2.2 [B1–B14], with standard beam formulas. Factors are relative to a PLA Basic part of the same width. "Mass" uses the governing thickness, which is the larger of the stiffness and strength factors. "Cost" means filament cost.

| Material | E ratio | σ ratio | Z-σ ratio | t for equal stiffness | t for equal strength | t for equal Z strength | Mass × | Cost × | HDT °C |
|---|---|---|---|---|---|---|---|---|---|
| PLA Basic | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 54 |
| PLA Tough+ | 0.78 | 0.86 | 0.67 | 1.09 | 1.08 | 1.22 | 1.06 | 1.49 | 58 |
| PLA-CF | 1.44 | 1.17 | 0.84 | 0.89 | 0.92 | 1.09 | 0.91 | 1.94 | 54 |
| PETG Basic | 0.71 | 0.99 | 1.13 | 1.12 | 1.01 | 0.94 | 1.13 | 1.06 | 68 |
| PETG HF | 0.75 | 0.84 | 0.74 | 1.10 | 1.09 | 1.16 | 1.14 | 1.21 | 62 |
| PETG-CF | 1.06 | 0.92 | 0.94 | 0.98 | 1.04 | 1.03 | 1.05 | 2.24 | 68 |
| ASA | 0.70 | 0.86 | 1.00 | 1.13 | 1.08 | 1.00 | 0.95 | 1.91 | 92 |
| PET-CF | 1.93 | 1.72 | 1.13 | 0.80 | 0.76 | 0.94 | 0.83 | 4.73 | 182 |
| PA6-CF | 1.99 | 1.99 | 1.55 | 0.80 | 0.71 | 0.80 | 0.70 | 3.73 | 164 |
| PAHT-CF | 1.54 | 1.64 | 1.52 | 0.87 | 0.78 | 0.81 | 0.74 | 4.69 | 170 |
| PPA-CF | 3.59 | 2.74 | 1.84 | 0.65 | 0.60 | 0.74 | 0.66 | 8.79 | 196 |

**Recommended ladder for gyropup:**

1. **PLA Basic.** Cheapest; for parts away from motors.
2. **PETG Basic.** Same price, +14 °C HDT. Make parts 12% thicker for equal stiffness.
3. **PETG-CF or PLA-CF** on a P1S with the hardened combo. About the same stiffness as PLA, but PETG-CF has HDT 68 °C.
4. **PET-CF or PA6-CF.** About 20–29% thinner and 17–30% lighter than PLA, at 3.7–4.7× the filament cost. HDT 164–182 °C, so these can sit next to motors.
   - PA6-CF has to be dried. It should also be annealed: un-annealed PA6-CF bolted joints crept and needed re-tightening almost daily; 8 h at 110 °C fixed it [K4].
   - PET-CF absorbs far less water: saturated absorption at 25 °C / 55% RH is 0.37%, against 2.35% for PA6-CF and 0.88% for PAHT-CF [B11][B12][B13]. That makes **PET-CF the low-maintenance step up**.

Caveat: datasheet specimens are 100% infill and dried or annealed. Real parts with walls and infill are weaker, so keep the safety factor from rule 1.1.2.

### 2.4 Structural PLA details

**Creep**

- No vendor creep data for PLA was found. Design to the static reference above (22 MPa) and test bolted joints over days.
- Polymaker says HT-PLA Pro needs annealing to hold shape "under load" in heat [M3].

**Fatigue**

- Size for 10% of UTS at 2×10⁶ cycles [P1].
- 100% infill multiplies life (rule 4 above) [P2].

**Layer orientation**

- See §1.1. Split-and-fold or angled designs can do better than standing parts [K5].

**Inserts**

- See §1.1.
- CNC Kitchen store prices [K10]:
  - M3×5.7: 100 pcs $9.40
  - M4×8.1: 50 pcs $9.90
  - M5×9.5: 50 pcs $9.90
  - M3/M4/M5 set of 200: $25.90
- A captive nut in a bottom pocket had the highest pull-out in PETG (166 kg) [K8].

**Bearing seats**

- Print them, measure, then apply Bambu XY hole compensation [B20].
- CNC Kitchen found printed holes about 0.25 mm undersize on their printer [K6]. Use that only as a starting point.

---

## 3. Carbon-fibre tubes and plates (optional upgrade)

### 3.1 Tube prices

$/m is **derived** as list price ÷ length.

| Seller | OD×ID mm | Type | List | $/m | Mass g/m | E GPa | Src |
|---|---|---|---|---|---|---|---|
| Easy Composites (UK) | 16×14 | roll-wrapped (UD + 3k twill) | £17.35/m ex VAT | £17.35 (qty breaks £15.60/£13.90) | 74.2 | 64 | [C2] |
| Easy Composites | **20×18** | roll-wrapped | £20.40/m ex VAT | £20.40 (£18.35/£16.35) | 86.5 | 64 | [C1] |
| Easy Composites | 25×22 | roll-wrapped | £33.65/m ex VAT | £33.65 (£30.30/£26.95) | 168.5 | 64 | [C3] |
| Easy Composites | 12×10 | pultruded UD | £12.50/m | £12.50 | n/p | 28–40 | [C4] |
| Rock West | 17.96×15.88 | roll-wrapped fabric | $78.99 / 1.829 m | $43.19 | n/p | n/p | [C5] |
| Rock West | 21.74×19.05 | roll-wrapped std-mod twill (INFINITube V size 04) | $129.99 / 1.880 m | $69.15 | n/p | n/p | [C6] |
| Rock West | 24.31×22.23 | roll-wrapped fabric | $106.99 / 1.829 m | $58.50 | n/p | n/p | [C7] |
| Rock West | 25.60×23.83 | roll-wrapped fabric | $98.99 / 1.524 m | $64.95 | n/p | n/p | [C8] |
| Rock West | 18.03×15.88 | roll-wrapped unidirectional | $69.99 / 1.829 m | $38.27 | n/p | n/p | [C9] |
| Rock West | 12×9.8 | pultruded UD | $40.99 / 1.829 m | $22.41 | n/p | n/p | [C10] |
| CarbonFiberTubeShop | 17.78×15.88 | roll-wrapped uni (SM7072U) | $67.70 / 1.829 m | $37.02 | n/p | n/p | [C11] |
| CarbonFiberTubeShop | 20.96×19.05 | roll-wrapped uni (ME8272U) | $75.61 / 1.829 m | $41.34 | n/p | n/p | [C12] |
| CarbonFiberTubeShop | 25.27×22.23 | roll-wrapped uni (ME9972U) | $117.07 / 1.829 m | $64.01 | n/p | n/p | [C12] |
| DragonPlate | – | – | not retrieved | – | – | – | – |

**Pultruded vs roll-wrapped.** The largest pultruded round tube offered is 12 mm OD at both Easy Composites and Rock West [C4][C10]. Pultruded tubes give the most longitudinal strength but are "more vulnerable to crushing or torsional fracture". Roll-wrapped tubes are more resilient to crush and twist [C13].

**Leg-sized tubes** (16–25 mm) are therefore roll-wrapped. They cost $37–69/m in the US, or £17–34/m ex VAT from the UK.

Easy Composites roll-wrapped tubes:

- tensile strength 650 MPa
- max service temperature 80 °C
- cannot be threaded [C1]

### 3.2 20 mm CF tube against aluminium (**derived**, beam theory)

| Tube | EI N·m² | Moment limit N·m | Mass g/m | Inputs |
|---|---|---|---|---|
| CF 20×18 roll-wrapped | 172.9 | 175.6 (tension-based upper bound) | 86.5 | E 64 GPa, 650 MPa [C1] |
| Al 6061-T6 20×18 | 186.2 | 74.5 (yield) | 161.1 | E 68.9 GPa (10 Msi) [C14]; yield about 40 ksi; 0.0975 lb/in³ [S5] |
| Al 6061-T6 20×16 | 319.7 | 127.9 | 305.2 | same |
| CF 16×14 | 85.2 | 108.2 | 74.2 | [C2] |
| CF 25×22 | 491.2 | 399.1 | 168.5 | [C3] |
| PLA Basic solid Ø20 rod | 21.6 | 59.7 | 389.6 | 2.75 GPa, 76 MPa, 1.24 g/cm³ [B1] |

A same-size CF tube is about as stiff as aluminium, at about half the mass. The CF moment limit is calculated from tensile strength, so it is an upper bound. In practice, crushing at the clamps and the bond fail first.

A solid printed PLA rod is about 8× less stiff than the CF tube and 4.5× heavier. Tubes pay off on the long links.

### 3.3 Joining CF tubes

- **Printed clamps or sleeves.** Doggo-style stacked bearings plus shoulder bolts at the joints; tubes captured in printed or aluminium clamps.
- **Bonded aluminium inserts.** 3M DP420 is the usual structural epoxy, but its datasheet could not be fetched because 3M blocks automated access. Its strength values are left **null**. Check the TDS before relying on it.
- The tube resin limits service temperature to 80 °C [C1]. Keep bonded joints and tubes away from hot motors.

### 3.4 CF plates

- **SendCutSend cut-to-shape** [S6][S7]:
  - 2×2 twill epoxy, 1.02 / 1.6 / 2.01 / 3.0 / 3.99 / 5.0 / 8.0 mm
  - waterjet, ±0.009 in, kerf about 0.030 in
  - web ≥ 2× thickness
  - example: 1 mm, 3.35×3.25 in = $53.42 at qty 1, $29.60 at qty 100
- **Easy Composites double-sided sheet** [C15]:
  - 0.25–3 mm
  - 641 MPa, 50.1 GPa at 0/90°
  - Tg 80 °C
  - 1 mm nominal is actually 0.86 mm and weighs 1.42 kg/m²
  - uncut only, no cutting service

---

## 4. SendCutSend (optional upgrade)

### 4.1 Materials relevant to robots

Thicknesses are from the materials page [S8] and the quoter JSON [S1].

| Material | Process | Thicknesses (in) | Bend | Density g/cm³ |
|---|---|---|---|---|
| 5052-H32 Al | fiber laser | .040 .063 .080 .090 .100 .125 .187 .250 .313 .375 .500 | **yes**, ≤ .250 | 2.685 (0.097 lb/in³) [S4] |
| 6061-T6 Al | fiber laser | .040 .063 .080 .100 .125 .187 .250 .313 .375 .500 .625 .750 | **no** | 2.699 (0.0975 lb/in³) [S5] |
| 7075-T6 Al | fiber laser | .125 .190 .250 | no | 2.796 (0.101 lb/in³) [S9] |
| Mild steel A36/1008 | fiber laser | .030–.500 (12 sizes) | yes, ≤ .250 | 7.83 [S10] |
| 304 stainless | fiber laser | .030–.500 (10 sizes) | yes, ≤ .250 | 8.00 (0.289 lb/in³) [S11] |
| 316 stainless | fiber laser | .060 .125 .187 .250 | yes | n/p |
| 4130 chromoly | fiber laser | .050 .063 .125 .190 .250 | yes | 7.83 [S12] |
| Ti-6Al-4V grade 5 | fiber laser | .040 .063 .125 .187 .250 | no; no tap/hardware | 4.43 [S13] |
| Carbon fibre | waterjet | .040 .063 .079 .118 .157 .197 .315 | no; no services | about 1.66 (about 0.06 lb/in³) [S6] |
| G10/FR-4 | waterjet | .063 .125 .187 .250 .375 .500 | no | n/p |
| Delrin | CO₂ laser (.125) / router (.270) | .125 .270 | no; tap + countersink | n/p |
| UHMW | router | .375 .500 | no | n/p |

Densities in g/cm³ are converted from lb/in³ where the page gives lb/in³.

The CF page's figures (500+ ksi, 20–30 Msi) describe the **fibre**, not the laminate. Don't design with them [S6].

### 4.2 Holes, edges, tolerances, sizes

- **Quoter hard-minimum hole** (from `min_hole_diameter` in SendCutSend's public materials JSON [S1]):

  | Material | Thickness → min hole |
  |---|---|
  | 5052 | 1.6→0.36, 3.18→0.81, 4.75→1.07, 6.35→1.45 mm |
  | 6061 | 15.9→6.35, 19.05→7.62 mm |
  | CF and G10 | 1.78 mm up to 3 mm; 3.18 mm above 3 mm (CF) |
  | Router plastics | 3.18 mm |

  These are quoter limits, not recommendations; use rule 1.2.
- **Waterjet hole minimum:** 0.070 in. **Router hole minimum:** 0.125 in [S2].
- **Internal corner radius:** 0.032 in with kerf (laser and waterjet), 0.063 in on the router [S2][S7].
- **Laser kerf** is not published; their software compensates. **Waterjet CF kerf** is about 0.030 in [S6][S7].
- **Minimum web:** not published for metals [S2]. CF ≥ 2× thickness [S6].
- **Tolerance** [S7]:
  - laser ±0.005 in under 12 in, ±0.010 in over 12 in
  - waterjet ±0.009 in
  - router ±0.005 in
- **Part size** [S14]:
  - laser instant max 44×30 in, custom typically 56×44 in
  - minimum 0.25×0.375 in (thin Al), rising with thickness: for example, 6061 .250 is 0.5×0.75 in
  - CF minimum 1×2 in (≤ .118) or 3×3 in (.157–.197)
- **Files:** .ai .dxf .dwg .eps .stp .step. A PDF goes to custom quote [S15]. Draw at 1:1 [S2].

### 4.3 Bending (fixed tooling; values from the quoter JSON [S1])

Rules from the bending page [S3]:

- max angle 130°; angle tolerance ±1° up to 24 in
- bend-to-edge ±0.015 in, plus ≥ 0.015 in per extra bend
- flat part 0.375×1.5 in to 30×44 in
- U-channel base ≥ 2× flange
- no custom radii

| 5052 t (mm) | K | Inside R (mm) | Min flange (mm) | Keep features from bend CL (mm) |
|---|---|---|---|---|
| 1.02 | 0.45 | 0.61 | 6.45 | 6.0 |
| 1.60 | 0.42 | 0.89 | 6.45 | 6.0 |
| 2.03 | 0.48 | 0.97 | 6.45 | 6.0 |
| 2.29 | 0.37 | 0.81 | 6.45 | 6.0 |
| 2.54 | 0.40 | 3.18 | 9.32 | 8.0 |
| 3.18 | 0.44 | 3.18 | 9.32 | 8.0 |
| 4.75 | 0.43 | 6.35 | 15.72 | 12.5 |
| 6.35 | 0.42 | 6.35 | 29.19 | 20.0 |

K-factors for steel (0.32–0.40), 304 stainless (0.34–0.38) and 4130 (0.36–0.43) are per thickness in the JSON.

### 4.4 Services and lead times

Lead times are from the rush-production page [S16] and the shipping page [S17].

**Base lead time:** cutting 2–4 business days; CNC 2–5.

**Added time by service:**

| Service | Added time (business days) | Notes |
|---|---|---|
| Bending | +1–2 | the shipping page says 2–3 |
| Tapping | +1–2 | metric M2–M16 by thickness: e.g. 5052 3.18 mm takes M2–M12 [S1] |
| Countersinking | +1–2 | 5052/6061/7075 from .125 in |
| Hardware (PEM nuts/standoffs/studs) | +1–3 | Al from .040 in; part 1×1.5 to 36×46 in [S18] |
| Deburring | +0 | |
| Tumbling | +1–2 | |
| Anodize (Type II, 5052/6061/7075) | +1–3 clear/black, +5–7 colours | 1×3 to 23×23 in [S19] |
| Powder coat | +3–5 | |
| Plating | +7–10 | |

**Rush tiers:**

| Tier | Ships |
|---|---|
| Fast | 1–3 days |
| Faster | 1–2 days, with overnight shipping |
| Fastest | within 24 h; order by noon PT |

Rush prices are not published [S16].

**Volume adders:**

- 100+ parts: +2–4 days
- over 46 in: +1–2 days
- over 80 lb: +1–2 days
- over 40 sq ft: +2–5 days [S16]

**Shipping and minimums:**

- Free US shipping at $39 or more. They ship to the US and Canada only [S17].
- No minimum order quantity on most processes [S20].
- OSH Cut's own comparison page calls this a "$39 minimum" [A1]. SendCutSend's pages treat $39 as the free-shipping threshold.

### 4.5 Pricing behaviour

**Cost drivers** [S20][S21][S7]:

- Material and thickness ("one of the biggest factors").
- Pierce count: 40 holes cost less than 100.
- Cut length and complexity.
- Part size: keep the largest dimension under 28 in.
- Quantity: discounts start at 2 identical parts, per line item. "50 of the same part can give you a 50% discount"; bulk orders save "up to 80%".
- Each post-process service, which also gets quantity discounts.
- One part per file; pre-nested files cost more.

**Bending minimum:** the blog's table implies a $19 minimum for 1–2 bent parts. An older version of the same post said $9 [S20].

**Published examples.** SendCutSend labels all of these as estimates that may be out of date.

| Part | Qty 1 | Qty 100 | Src |
|---|---|---|---|
| 5052 .187 in, 3.5×2.5 in, laser + deburr | $9.90 | $3.70 | [S7] |
| CF .039 in, 3.35×3.25 in, waterjet | $53.42 | $29.60 | [S7] |
| ABS .125 in, 3.5×3.5 in, router | $7.42 | $2.99 | [S7] |
| 5052 .100 in, 2.5×4.75 in, laser + deburr + tap | $12.09 | $4.40 | [S22] |
| HRP&O .187 in, 4×4 in, laser + tap | $23.32 | $5.77 | [S22] |
| Delrin 2.5×3 in, route + tap | $15.16 | $5.66 | [S22] |
| HRP&O .188 in, 3.5×1 in, laser + PEM | $14.14 | $3.24 | [S18] |
| CRS .135 in, 3×3 in, laser + bend + PEM | $27.05 | $6.44 | [S18] |
| 5052 .063 in, 5.5×6 in, laser + bend + deburr + PEM + anodize | $44.51 | $19.48 | [S18] |
| G90 .059 in, 5.4×6 in, laser + bend + PEM | $31.76 | $8.32 | [S3] |
| CRS .119 in, 6.3×7.4 in, bend + others | $73.33 | $16.21 | [S3] |
| Polycarbonate .118 in, 4×5.5 in, route + bend | $24.98 | $7.84 | [S3] |
| 5052 .125 in, 4×3.25 in, laser + bend + csk + deburr + anodize | $41.58 | $12.86 | [S19] |
| 5052 .090 in, 6.5×7.5 in, laser + bend + tap + dimple + deburr + anodize | $72.63 | $24.62 | [S19] |
| 6061 billet 2.5×2.5 in, CNC + blast + anodize | $357.23 | $73.32 | [S19] |
| Same sprocket: 304 .060 in vs Ti .063 in | $6.76 vs $19.60 | – | [S20] |

**Derived from these examples:**

- Qty-100/qty-1 ratio: 0.21–0.55, median 0.31 (n = 15).
- Simple 5052 cost per bounding-box in² at qty 1: $1.13 and $1.02; at qty 100: $0.42 and $0.37.
- CF, qty 1: $4.91/in².
- Titanium cost about 2.9× 304 stainless for the same sprocket.

**API and quoting access:**

- No public API is documented: `/api` and `/developers` return 404.
- Quotes come from uploading a file on the site, or from the Fusion and SolidWorks plug-ins [S15][S23].
- An undocumented, unauthenticated JSON of per-material rules sits at `app.sendcutsend.com/materials`; their bending calculator uses it [S1]. It has no prices. It is useful for refreshing the rules in `fabrication.json`, but it may change without notice.
- For the design guide, link users to the upload page and to the bending calculator at https://sendcutsend.com/bending-calculator/.

---

## 5. Alternatives (one line each)

- **OSH Cut** [A1]: best for multi-part jobs with bends and tube cutting.
  - Instant quote; job-level nesting with automatic discounts.
  - "No minimum" and same-day rush (self-reported); US only.
- **Xometry** [A2]: one portal for sheet, CNC and moulding.
  - Instant quotes; CAD add-ins for SolidWorks, Fusion and Onshape.
  - "No minimum for the majority of services" (seen only in a search snippet of their help article).
- **JLCCNC sheet metal** [A3]: cheapest small parts from China (5052, SS201/304, CRS, galvanized).
  - Instant quote; "minimum order price starts from $0.4"; fastest production 1 day, plus shipping.
- **JLC3DP** [A4]: MJF PA12/PA11 nylon and SLA, for parts the P1S can't make.
  - Starting prices: SLA from $0.30 (2 d); MJF, SLS and FDM from $1.00 (3 d); SLM metal $8; CNC $5.
  - Some materials cut up to 21.5% from 2025-08-13.
- **PCBWay CNC/sheet** [A5]: manual RFQ (not instant), 10–12 days.
- **Protolabs sheet metal** [A6]: US-made, ISO 9001 and ITAR.
  - Online quote averaging one day.
  - 3-day tier for parts ≤ 0.125 in with ≤ 12 bends; 5-day standard.
  - No published prices or minimum.

---

## 6. Bearings, pivots and fasteners

Single-unit prices from VXB on 2026-10-25, with load ratings from the VXB listings [V1]. McMaster and Misumi block automated fetching, so their prices were not retrieved.

| Bearing | d×D×B mm | $ each | Cr / C0 N | Max rpm (grease) |
|---|---|---|---|---|
| 6800-2RS | 10×19×5 | 7.77 | 1380 / 585 | 22,000 |
| 6801-2RS | 12×21×5 | 7.77 | n/p | n/p |
| 6802-2RS | 15×24×5 | 9.99 | 2080 / 1260 | 17,000 |
| 6804-2RS | 20×32×7 | 7.77 | 4000 / 2640 | 13,000 |
| 6805-2RS | 25×37×7 | 7.77 | 4360 / 2600 | 11,000 |
| 6806-2RS | 30×42×7 | 9.99 | 4490 / 2900 | 9,500 |
| 6900-2RS | 10×22×6 | 7.77 | n/p | n/p |
| 6902-2RS | 15×28×7 | 9.99 | 4300 / 2250 | 17,000 |
| 6904-2RS | 20×37×9 | 9.99 | 6350 / 3700 | 12,000 |
| 6000-2RS | 10×26×8 | 7.77 | 4750 / 1960 | 19,000 |
| 6001-2RS | 12×28×8 | 7.77 | 5400 / 2360 | n/p |
| 6002-2RS | 15×32×9 | 9.99 | 5850 / 2850 | 14,000 |
| RU42UU crossed roller | 20×70×12 | 199.99 | 7350 / 8350 | – |
| CRBH3510AC1 crossed roller | 35 bore, 10 wide | 313.99 | n/p | – |

10-packs of the 68xx, 69xx and 60xx sizes cost $29.99–49.99 (about $3–5 each) [V1].

For the knee and hip pivots, a pair of 6802 or 6902 bearings in a printed seat is the cheap default. Check the real joint loads against the Cr/C0 values above. Crossed-roller bearings cost 20–40× more (**derived** from the prices above).

**Shoulder bolts.** VXB sells a 20-pack of M6×1.0 thread, 8 mm shoulder × 12 mm, for $49.98, about $2.50 each [V2].

**Five-bar legs (Stanford Doggo)** [D1]:

- Each leg is a five-bar linkage with the two upper links driven co-axially, through 3 mm-pitch GT2 belts at 16T→48T.
- Side panels are 4 mm waterjet-cut CF.
- Each joint has two stacked deep-groove bearings in one link, with a shoulder bolt through them into the other link.
- Drive links are drilled and tapped for a set screw.
- The bearing block and pulleys are 3D printed (SLS); print pulleys upright to keep tooth shape.
- The robot costs under $3000 [D2].

The DDT Diablo's leg mechanism was not researched here.

---

## 7. Gaps

- No PLA creep data was found.
- No wall-count study was found.
- Motor case temperatures were not researched.
- The 3M DP420 datasheet was blocked.
- McMaster and Misumi prices were not retrieved.
- DragonPlate tube prices were not retrieved.
- X2D and H2S nozzle material is not stated on the store pages.
- eSUN's official datasheet and price were not found.
- No public SendCutSend API exists.
- The web-search budget for this session ran out partway through. Everything above came from pages fetched directly.

---

## Sources

**Bambu Lab** (US store, datasheets and wiki; fetched 2026-10-25)
- [B1] PLA Basic TDS: https://store.bblcdn.com/s1/default/58b85d0f3db94878854a28fdb8a0006e/Bambu_PLA_Basic_Technical_Data_Sheet.pdf · [B1s] https://us.store.bambulab.com/products/pla-basic-filament
- [B2] PLA Matte TDS: https://store.bblcdn.com/s7/default/5b061f2feeac4ba88f355a33248bbda7/Bambu_PLA_Matte_Technical_Data_Sheet.pdf
- [B3] PLA Tough+ TDS: https://store.bblcdn.com/s7/default/80a85371db2e40bda97069d283fed76c/BambuPLA_Tough_TechnicalData_Sheet_(2).pdf · https://us.store.bambulab.com/products/pla-tough-upgrade
- [B4] PLA-CF TDS: https://store.bblcdn.com/842f399d4e274507953a5231126ec8c1.pdf · https://us.store.bambulab.com/products/pla-cf
- [B5] PETG Basic TDS: https://store.bblcdn.com/s1/default/cb94589bf7994fdcbfa833badefae9cd/Bambu_PETG_Basic_Technical_Data_Sheet.pdf · https://us.store.bambulab.com/products/petg-basic
- [B6] PETG HF TDS: https://store.bblcdn.com/3a230e260a3a47c2b0db0156e07eef91.pdf
- [B7] PETG-CF TDS: https://store.bblcdn.com/626e4f424bf345ae965ad0ddfcaf2459.pdf · https://us.store.bambulab.com/products/petg-cf
- [B8] ASA TDS: https://store.bblcdn.com/ad7b08230c164e72856cffbe06bb7dc9.pdf
- [B9] ABS TDS: https://store.bblcdn.com/s7/default/23b4cf2b83d5470bb96d19970b5f3ae8/Bambu_ABS_Technical_Data_Sheet_V3.pdf
- [B10] PC TDS: https://store.bblcdn.com/a52afdccddfd448583d119587122c8c5.pdf
- [B11] PET-CF TDS: https://store.bblcdn.com/9690d6226f024acab2ba0dd52dabb654.pdf · https://us.store.bambulab.com/products/pet-cf
- [B12] PA6-CF TDS: https://store.bblcdn.com/b2abc59ac250492b979a52f1ce3e61b3.pdf · https://us.store.bambulab.com/products/pa6-cf
- [B13] PAHT-CF TDS: https://store.bblcdn.com/7166b20bc68f4c87b32c972b856eeb4b.pdf
- [B14] PPA-CF TDS: https://store.bblcdn.com/05b0e4ca5ee14a4cb378cfa48df24f91.pdf · https://us.store.bambulab.com/products/ppa-cf
- [B15] TPU 95A HF TDS: https://store.bblcdn.com/58df32731eab4c90a7dac9b12e13ba88.pdf
- [B16] P1S: https://us.store.bambulab.com/products/p1s
- [B17] Hardened Steel Upgrade Combo: https://us.store.bambulab.com/products/hardened-steel-upgrade-combo
- [B18] P1 hotends: https://us.store.bambulab.com/products/bambu-hotend-p1-series · gear: https://us.store.bambulab.com/products/hardened-steel-extruder-gear-assembly
- [B19] Filament compatibility table: https://wiki.bambulab.com/en/general/filament-guide-material-table
- [B20] XY hole/contour compensation: https://wiki.bambulab.com/en/software/bambu-studio/xy-hole-contour-compensation
- [B21] P1S abrasive upgrade guide: https://wiki.bambulab.com/en/p1/manual/p1s-extruder-upgrade
- [B22] P2S: https://us.store.bambulab.com/products/p2s · [B23] X2D: https://us.store.bambulab.com/products/x2d · [B24] H2S: https://us.store.bambulab.com/products/h2s · [B25] H2D: https://us.store.bambulab.com/products/h2d · [B26] H2C: https://us.store.bambulab.com/products/h2c · [B27] https://us.store.bambulab.com/products/refurbished-x1c and https://us.store.bambulab.com/sitemap_products_1.xml
- [B28] TPU 85A / 90A TDS: https://cdn.shopify.com/s/files/1/0645/5876/0155/files/Bambu_TPU_85A_Technical_Data_Sheet_a7233668-497b-487f-af8a-3adb49fafaa1.pdf · https://cdn.shopify.com/s/files/1/0645/5876/0155/files/Bambu_TPU_90A_Technical_Data_Sheet_582bf8f6-1f0a-474c-aeda-9e72af3689dc.pdf · https://us.store.bambulab.com/products/tpu-85a-tpu-90a
- [B29] TPU for AMS TDS: https://store.bblcdn.com/s5/default/0a98353dce6d486ca848b21d2b19a207.pdf
- [R1] Retailer listing, hardened hotend 320 °C: https://www.memoryexpress.com/Products/MX00136444

**Other filament**
- [M1] https://us.polymaker.com/products/polylite-pla · [M2] https://us.polymaker.com/products/polylite-pla-pro · [M3] https://us.polymaker.com/products/polymaker-ht-pla-pro · [M4] https://us.polymaker.com/products/fiberon-pet-cf17 · [M5] https://us.polymaker.com/products/fiberon-pa6-cf20
- [E1] https://camelcamelcamel.com/product/B0F6LG6BYR

**Tests and papers**
- [K1] https://www.cnckitchen.com/blog/comparing-pla-petg-amp-asa-feat-prusament
- [K2] https://www.cnckitchen.com/blog/gradient-infill-for-3d-prints
- [K3] https://www.cnckitchen.com/blog/the-difference-of-pla-and-pla-tested-feat-polymaker
- [K4] https://www.cnckitchen.com/blog/carbon-fiber-nylon-in-3d-printing-pa6-vs-pa12-tested
- [K5] https://www.cnckitchen.com/blog/stop-printing-flat-the-45-secret-for-stronger-parts
- [K6] https://www.cnckitchen.com/blog/are-our-heat-set-insert-datasheets-wrong
- [K7] https://www.cnckitchen.com/blog/tips-and-tricks-for-heat-set-inserts
- [K8] https://www.cnckitchen.com/blog/helicoils-threaded-insets-and-embedded-nuts-in-3d-prints-strength-amp-strength-assessment
- [K9] https://www.cnckitchen.com/blog/better-performing-3d-prints-with-annealing-but-part-1-pla
- [K10] https://cnckitchen.store/products.json (insert listings)
- [P1] Ezeh & Susmel 2019, reference strength values for AM PLA: https://eprints.whiterose.ac.uk/id/eprint/142395/
- [P2] Gaweł et al. 2023, *Polymers* 15(7):1651: https://pmc.ncbi.nlm.nih.gov/articles/PMC10096656
- [D1] https://github.com/Nate711/StanfordDoggoProject · [D2] https://arxiv.org/abs/1905.04254

**Carbon fibre**
- [C1] https://www.easycomposites.co.uk/20mm-woven-finish-carbon-fibre-tube · [C2] …/16mm-woven-finish-carbon-fibre-tube · [C3] …/25mm-22mm-woven-finish-carbon-fibre-tube · [C4] …/12mm-pultruded-carbon-fibre-tube · [C13] https://www.easycomposites.co.uk/carbon-fibre-tube · [C15] https://www.easycomposites.co.uk/double-sided-high-strength-carbon-fibre-sheet
- [C5] https://www.rockwestcomposites.com/45526.html · [C6] …/46404.html · [C7] …/45529.html · [C8] …/45682.html · [C9] …/45353.html · [C10] …/t-rnd-472-l72.html
- [C11] http://www.carbonfibertubeshop.com/small%20tubing.html · [C12] http://www.carbonfibertubeshop.com/medium%20tubing.html · [C14] http://www.carbonfibertubeshop.com/tube%20properties.html

**SendCutSend**
- [S1] Public materials JSON (used by their bending calculator): https://app.sendcutsend.com/materials
- [S2] https://sendcutsend.com/guidelines/sheet-cutting/ · [S3] https://sendcutsend.com/services/cnc-bending/
- [S4] https://sendcutsend.com/materials/5052-aluminum/ · [S5] https://sendcutsend.com/materials/6061-aluminum/ · [S6] https://sendcutsend.com/materials/carbon-fiber/
- [S7] https://sendcutsend.com/services/laser-cutting/ · [S8] https://sendcutsend.com/materials/ · [S9] https://sendcutsend.com/materials/7075-aluminum/ · [S10] https://sendcutsend.com/materials/mild-steel/ · [S11] https://sendcutsend.com/materials/stainless-steel/ · [S12] https://sendcutsend.com/materials/4130-chromoly/ · [S13] https://sendcutsend.com/materials/titanium/
- [S14] https://sendcutsend.com/materials/min-max/ · [S15] https://sendcutsend.com/faq/ · [S16] https://sendcutsend.com/rush-production · [S17] https://sendcutsend.com/shipping/ · [S18] https://sendcutsend.com/services/hardware/ · [S19] https://sendcutsend.com/services/anodizing/
- [S20] https://sendcutsend.com/blog/4-ways-to-save-money-on-your-sendcutsend-order/ · [S21] https://sendcutsend.com/blog/designing-your-products-for-pricing-efficiency/ · [S22] https://sendcutsend.com/services/tapping/ · [S23] https://sendcutsend.com/add-ins/

**Alternatives**
- [A1] https://www.oshcut.com/osh-cut-vs-send-cut-send · [A2] https://community.xometry.com/kb/articles/642-what-is-your-minimum-order-quantity · [A3] https://jlccnc.com/blog/sheet-metel-online · [A4] https://jlc3dp.com/ and https://jlc3dp.com/blog/drastic-material-price-cuts-and-adjusted-post-processing-service-fees · [A5] https://www.pcbway.com/rapid-prototyping/manufacture/?type=3 · [A6] https://www.protolabs.com/services/sheet-metal-fabrication/

**Bearings and fasteners**
- [V1] VXB product listings, e.g. https://vxb.com/products/6802-2rs-sealed-bearing-15x24x5 (and the other `vxb.com/products/` links in `catalog/fabrication.json`)
- [V2] https://vxb.com/products/20-pack-shoulder-bolts-m6-10-x-12-mm-thread-8-mm-d
