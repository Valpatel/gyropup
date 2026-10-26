# LiFePO4 (LFP) batteries for gyropup

Prices were checked on 2026-10-25. Every pack, BMS and charger named here is in
[`catalog/lfp_batteries.json`](../catalog/lfp_batteries.json), with its sources and confidence.
"Not published" means exactly that. Computed packs (ids `custom-8s…`) are labelled **estimate**: mass = cells × 1.15.

**Target:** 8S LFP: 25.6 V nominal (26.4 V with A123-type 3.3 V cells), 28.8–29.2 V full, ~20 V at cut-off.
That sits inside the J501's 12–36 V range with 7 V of headroom; 10S (36.5 V full) would not.

**Requirements:** ≥ 250 Wh, ≥ 60 A continuous, short peaks of 60–150 A, as light as possible.

**Baseline to beat:** WREKD 7S2P Molicel P50B Li-ion: 1.05 kg, 252 Wh, 120 A, $294 (`wrekd-nexus-7s2p-molicel-p50b-10000`).

## The short answer

| Choice | What | Wh | Cont. A | Mass | vs 7S Li-ion | Price |
|---|---|---|---|---|---|---|
| **Best ready-made** | 2× EarthX ETX36D in series | 327 | 100 (EarthX series rating) | 3.60 kg | **+2.55 kg** (3.4×) | $738 |
| **Best custom** | 8S4P Lithium Werks/A123 ANR26650M1-B + 100–200 A BMS | 264 | 208 (cells) → BMS limit | ~2.80 kg *est.* | **+1.75 kg** (2.7×) | cells ~€254 ex VAT (NKON) + BMS $65–£90 |
| Lighter custom, less margin | 8S2P Vapcell G65 IFR32700 | 333 | 60 (110 A 5 s) | ~2.71 kg *est.* | +1.66 kg | cell price not verified |

LFP stores roughly 100–145 Wh/kg at cell level, against about 240 Wh/kg for the P50B pack. Every LFP option that meets 250 Wh is **2.6–3.4× heavier** than the current Li-ion pack.
On a 14 kg robot that is 12–18 % of the total mass. The leg actuators and the balance controller must carry it, and it should sit low in the body.

---

## 1. Ready-made 8S (or 2 × 4S) LFP packs

| Pack | V nom / full / cut-off | Ah | Wh | Cont. A | Peak A | BMS | Mass | Size (mm) | Connector | Price, seller, stock |
|---|---|---|---|---|---|---|---|---|---|---|
| **2× EarthX ETX36D** (series) | 26.4 / **28.8** / 23.0¹ | 12.4 | 327 | **100**² | 680 (PCA) | 1 per battery; no comms; low-temp charge cut-off not published | 3600 | 2 × 175×86×155 | terminal adapters, M6 | $738 (2 × $369), [EarthX](https://earthxbatteries.com/product/etx36d/), stock not shown |
| 2× EarthX ETX18F (series) | 26.4 / 28.8 / 23.0¹ | 6.2 | 164 | 60² | 340 (PCA) | as above | 2000 | 2 × 150×86×93 | as above | $458 (2 × $229), [EarthX](https://earthxbatteries.com/product/etx18f/) |
| EarthX ETX400-24-VNT (one 24 V box) | 26.4 / n.p. / n.p. | 7.8 | 206 | n.p. | 400 (PCA) | redundant BMS, balancing, fault LED extra | 2400 | 166×76×168 | M6 screws | $779, [Aircraft Spruce](https://www.aircraftspruce.com/catalog/pnpages/11-20927.php) |
| BatterySpace 25.6 V 9.9 Ah, 40 A | 25.6 / 28.8 / 20.0 | 9.9 | 253 | **40** (PCM trips) | n.p. | PCM, OVP 31.2 V, UVP 16 V; no comms | 2510 | 165×112×96 | 12 AWG open leads | $347.88, [BatterySpace](http://www.batteryspace.com/LFP-Battery-25.6V-9.9Ah-253Wh-40A-rate-with-PCM.aspx), build to order |
| BatterySpace 25.6 V 13.2 Ah, 40 A (8S4P) | 25.6 / 28.8 / 20.0 | 13.2 | 338 | **40** | n.p. | 40 A PCM | 3260 | 266×108×79 | 45 A Anderson | $405.95, [BatterySpace](http://www.batteryspace.com/lifepo4-battery-25-6v-13-2ah-338wh-40a-rate.aspx), build to order |
| Battle Born BB5024 | 25.6 / n.p. / n.p. | 50 | 1280 | n.p. | n.p. | yes | 14061 | 324×174×227 | posts | $879, [Battle Born](https://battlebornbatteries.com/products/50ah-24v-lifepo4-deep-cycle-battery), in stock |
| Bioenno BLF-2410AS (already in catalog) | 25.6 / 29.2 / – | 10 | 256 | **10** | 20 | PCM | 2600 | 182×77×171 | screw terminals | $189.99, sold out |

n.p. = not published. PCA = EarthX peak cranking amps (a few seconds).
¹ EarthX AN-1609 calls a battery below 11.5 V (2.8 V/cell) over-discharged; the BMS cut-off point is not published.
² Continuous rating from EarthX application note [AN-1609](https://Aircraftspruce.Com/catalog/pdf/earthxparallel.pdf), Table 1, for the series pair.

**Series use of 12 V starter batteries.** The note said to check this before using two 4S batteries in series.
- **EarthX allows it.** AN-1609 approves up to 2 in series and/or 2 in parallel with no extra electronics. Use the same model and age, and no cross-ties between strings.
  The series pair is **de-rated**: ETX680/ETX36 pairs get 100 A continuous, 54 A charge and **28.8 V max charge**. ETX18 pairs get 60 A, 27 A and 28.8 V.
  So charge EarthX pairs at 3.6 V/cell (28.8 V), not with a 29.2 V LFP charger.
- **Antigravity forbids it.** Its powersports RE-START manual says: "Do not attempt to use the battery product … in series or parallel with each other; damage or fire may occur"
  ([manual](https://antigravitybatteries.com/downloads/AG-Powersports-RS-Batteries-User-Manual.pdf)). Excluded.
- **Battle Born** quotes a 48 V maximum series voltage, but its 24 V packs are 14 kg. Excluded on mass.

**Other ready-made options, rejected:**
- **K2 Energy 25.6 V 9.6 Ah (SuperDroid Robots).** Search listing: $359, "Not Available". Under 25 A continuous, 40 A for < 2 s. The page is behind a bot wall and was not opened ([listing](https://www.superdroidrobots.com/shop/item.aspx/k2-25-6v-lifepo4-battery-pack-9-6ahr/1140)).
- **RC LiFe packs** (Turnigy nano-tech LiFePO4) are only 2S transmitter/receiver packs of 1.45–2.2 Ah ([HobbyKing](https://hobbyking.com/es_es/turnigy-nano-tech-2200mah-2s-30c-lifepo4-transmitter-receiver-pack-w-futaba-ph1-0-connector.html)).
  Four in series gives about 56 Wh. Far too small.
- **Bioenno, DNK Power, National Battery Supply and similar 24 V packs** are BMS-limited to 10–30 A. Examples: DNK's 8S3P 15 Ah tops out at 30 A and 3.5 kg; National's 25.6 V 12 Ah is 12 A.
- **Robot-combat LFP** today is almost all custom A123 builds; no current off-the-shelf 8S A123 robot pack was found.
  BatterySpace's two ANR26650M1B 8S packs are "not for general sales".

Only the **EarthX ETX36D pair** meets both ≥ 250 Wh and ≥ 60 A off the shelf.

---

## 2. High-rate LFP cells

| Cell | V nom / max / cut-off | Ah | Cont. A | Pulse A | Mass g | Size mm | Price | Notes, source |
|---|---|---|---|---|---|---|---|---|
| **Lithium Werks (ex-A123) ANR26650M1-B** | 3.3 / 3.6 / 2.0 | 2.6 typ, 2.5 min | 52 (20C) | 120 (10 s) | 76.0 | 26 × 65.4 | ~€7.95 ex VAT (1 pc), €6.55 at 400³ | charge −25…60 °C (< 250 mA below 0 °C); 26 A max charge. [Lithium Werks](https://lithiumwerks.com/?p=3097); the 2011 [A123 sheet](https://piekarz.pl/pdf/49579) says 70 A continuous |
| Vapcell T25 IFR26650 | 3.2 / 3.6 / n.p. | 2.5 (2.4 min) | 60 | 100 "under 80 °C" | n.p. (92 g shipping weight) | 26.2 × 65.2 | **$4.99**, Liion Wholesale, in stock | re-wrapped cell, maker not disclosed. [listing](https://liionwholesale.com/products/vapcell-t25-lifepo4-ifr26650-60a-100a-flat-top-2500mah-battery-genuine) |
| **Vapcell G65 IFR32700** | 3.2 / 3.65 / 2.0 | 6.5 (6.4 min) | 30 | 55 (5 s) | 147.4 measured | 32.4 × 70.3 | no current price found (G64 ~€9.29 on eBay.de³) | HKJ measured 6.61 Ah at 5 A, no loss at 30 A. [lygte-info](https://lygte-info.dk/review/batteries2012/Vapcell%20IFR32700%206500mAh%20G65%20(Blue)%202020%20UK.html) |
| LiitoKala Lii-70A 32700 | 3.2 / 3.65 / 2.5 | "7.0" | "30" | n.p. | 145 | 32 × 70 | 286 UAH ([vencon.ua](https://vencon.ua/products/liitokala-lifepo4-32700-7000mah-30a-3-2v-2-5-3-65v-blue-pvc-lii-70a)) | seller claim only. Similar "7000 mAh" 32700s test at ~6.0–6.3 Ah ([BLF](https://budgetlightforum.com/node/65598), [lygte-info VBatty](https://lygte-info.dk/review/batteries2012/VBatty%2032700%203.2V%207000mAh%20(Grey)%20UK.html)) |
| Generic 32700 6 Ah "3C" | 3.2 / 3.65 / 2.0 | 6.0 | 18 (3C) | – | ~145 | 32.4 × 70.1 | $4.99, [Rotor Village](https://rotorvillage.ca/lifepo4-32700-6000mah-3c-1pc/) | too low-rate: 8S2P gives only 36 A |
| **Headway HW-38120HP** | 3.2 / 3.65 / 2.5 (2.0 on short sheet) | 8.0 (7.5 min) | 120 (15C) | 240 (30C, 30 s) | 330 | 38.5 × 136 | **$14.99**, Liion Wholesale, in stock (118) | 0.1C charge below 0 °C; screw terminals. [spec](https://img01.71360.com/file/read/www/M00/0B/28/wKj0iWK7y42AdMF9AAXpIIHG6ms774.pdf), [short sheet](https://cdn.shopify.com/s/files/1/0697/3395/files/data_sheet.pdf), [buy](https://liionwholesale.com/products/headway-lifepo4-38120hp-8000mah-battery) |
| Headway 38120S 10 Ah | 3.2 / 3.65 / 2.0 | 10 | 30 (3C) | 10C pulse per sellers | ~330 | 38 × 120 | $13.59, Liion Wholesale, out of stock | too low-rate for 60 A in 8S1P. [Tell-way sheet](https://99mpg.com/Data/resources/downloads/miscstuff/38120sspecifications.pdf) |
| Murata US26650FTC1A | 3.2 / – / – | 3.0 | 25 (distributor) | – | 83.3 ([Batemo](https://www.batemo.com/?p=135115)) | 26.1 × 64.8 | not found | no maker datasheet found; heavier per Wh than A123 |

³ From search-result snippets of NKON / eBay.de. The pages are behind bot walls and were not opened.

**A123 availability and fakes (2026).**
- **Genuine cells are now an EU distributor item.** NKON (NL) lists the ANR26650M1B (its "production year 2023" listing is marked discontinued), and akkuteile.de lists it too.
  No trusted US retail listing was found. Liion Wholesale and 18650BatteryStore do not stock it, and Lithium Werks' page gives only a contact form.
- **Treat eBay/AliExpress "A123" with suspicion.** Many are used pulls (often the older 2.3 Ah M1A) or relabels. An EEVblog seller of used modules warned that many A123 cells sold online are knock-offs.
- **Buy only from NKON-class sellers.** Ask for lot or date codes, check 76 g ± 1.5 g and about 6 mΩ AC IR, and capacity-test a sample at 10–20 A.
- **US-stock substitute:** Vapcell T25 (60 A, $4.99) at Liion Wholesale.

### Computed 8S packs (estimates; catalog ids `custom-8s…`)

Mass = cells × 1.15 (*estimate*; the BMS adds 50–200 g on top). Dims = bare cell block.

| Pack | Cells | Ah | Wh | Cont. A (cells) | Peak A | Cell mass | **Pack mass est.** | Cell cost | Meets ≥ 250 Wh / ≥ 60 A? |
|---|---|---|---|---|---|---|---|---|---|
| 8S3P A123 ANR26650M1-B | 24 | 7.5 | 198 | 156 | 360 (10 s) | 1824 g | 2098 g | ~€191 ex VAT | no (Wh) |
| **8S4P A123 ANR26650M1-B** | 32 | 10.0 | 264 | 208 | 480 (10 s) | 2432 g | **2797 g** | ~€254 ex VAT | **yes**, large current margin |
| 8S4P Vapcell T25 | 32 | 10.0 | 256 | 240 | 400 | 2944 g⁴ | 3386 g⁴ | $159.68 | yes |
| **8S2P Vapcell G65 32700** | 16 | 13.0 | 333 | 60 | 110 (5 s) | 2358 g | **2712 g** | n.p. | yes, but 60 A is the limit and 150 A peaks exceed the pulse rating |
| 8S1P Headway 38120HP | 8 | 8.0 | 205 | 120 | 240 (30 s) | 2640 g | 3036 g | $119.92 | no (Wh) |
| 8S2P Headway 38120HP (not in catalog) | 16 | 16.0 | 410 | 240 | 480 | 5280 g | 6072 g | $239.84 | yes, but 6 kg |

⁴ Uses the store's 92 g shipping weight per cell; the true cell mass is not published.

---

## 3. BMS for 8S LFP, 60–150 A

| BMS | Cells | Cont. / peak A | Balance | Comms | Low-temp charge cut-off | Price, stock |
|---|---|---|---|---|---|---|
| **Battery Hookup 100 A LFP, CAN variant** | 7–17S LFP | 100 / 200 (10 s); 60 A charge | 60 mA passive | **CAN, RS485, UART**; BT module optional | **0 °C** | **$65**, in stock, ships from PA ([listing](https://batteryhookup.com/products/12v-lifepo4-smart-bms-w-low-temp-cutoff)) |
| JK-B2A8S20P | 4–8S | 200 / 350 | 2 A active | Bluetooth only (the -HC variant adds CAN) | not stated | £94.99 at Fogstar, out of stock; no US seller in stock ([Fogstar](https://www.fogstar.co.uk/products/jk-smart-bms-with-active-balancer-4s-8s-12v-24v)) |
| JK-B2A8S30P | 4–8S | 300 / – | 2 A active | Bluetooth only | not stated | £89.99 at Fogstar, in stock (57) ([Fogstar](https://www.fogstar.co.uk/products/smart-bms-jk-b2a8s30p-with-active-balancer-300a-4s-8s)) |
| Daly M-series smart | 3–24S | 150 or 200 (continuous vs peak not stated) | n.p. | CAN, RS485, dual UART, app | n.p. | no price on [dalybms.com](https://www.dalybms.com/bms-12v-200a-daly-m-series-smart-bms-3s-to-24s-150a-product/); marketplace listings ran ~$9–$202 depending on options (unverified) |
| ANT smart 8–22S (not in catalog) | 8–22S | 40–230 A options | – | Bluetooth | – | only eBay listings found (an 8–20S 230 A unit sold for $75.16, ended Aug 2025) |
| JBD 24 V/100 A 8S, Overkill Solar's base (not in catalog) | 8S | 100 | ~50 mA passive | BT, USB | – | Current Connected says it is **discontinued**. No 8S unit is listed on Overkill Solar now |

**For the robot,** CAN plus a 0 °C charge block matter more than 300 A.
- **The Battery Hookup unit fits.** Its 100 A continuous and 200 A for 10 s cover peaks of 60–150 A, and the robot can read SOC and faults on the CAN bus it already has.
- **Choose a JK for more current headroom.** Pick the 200 A or 300 A JK if 150 A peaks last longer than about 10 s. Note that a JK reports over Bluetooth only.

---

## 4. Chargers for 8S LFP (28.8–29.2 V)

| Charger | 8S LiFe? | Current | Input | Balance | Price, stock | Catalog id |
|---|---|---|---|---|---|---|
| **Junsi iCharger X8** | yes, 1–8S | 30 A, 1100 W | DC only | 2 A | $129.99, ProgressiveRC / BuddyRC, in stock | `junsi-icharger-x8` (new) |
| **ToolkitRC M8AC** | yes, 1–8S | 20 A (DC 600 W); AC 200 W ≈ 6.8 A at 29 V | AC or 7–35 V DC | 1 A | $121.99, Pyrodrone, in stock | `toolkitrc-m8ac` (new) |
| Victron Blue Smart IP65 24/5 | whole-pack LiFePO4 mode | 5 A (2 A low mode) | 120 VAC | none (relies on the BMS) | $117.30, The Solar Store, in stock | `victron-blue-smart-ip65-24-5` (new) |
| ISDT K4 | yes, 1–8S | 20 A, AC 400 W / DC 1200 W | AC or DC | – | $229.99 | `isdt-k4-dual-charger` (existing) |
| ISDT Q8 Max | yes, 1–8S | 30 A, 1000 W | DC only | – | $88.99 | `isdt-q8-max` (existing) |
| Junsi iCharger X12 | yes, 1–12S | 30 A, 1100 W | DC only | 2 A | $179.99 | `junsi-icharger-x12` (existing) |
| Bioenno BPC-2410A | 29.2 V fixed | 10 A | AC | none | $99.99 | `bioenno-bpc-2410-charger` (existing) |
| ToolkitRC M6DAC Pro, ISDT K2 Air, Ovonic Mate2 | **no**, 6S max | – | – | – | – | existing |
| ToolkitRC M8S (400 W, 18 A, 1–8S LiFe) | yes, per search snippet | 18 A | DC | – | $49.99 pre-order at RaceDayQuads (page not opened) | not in catalog |

- **EarthX pair or A123 cells:** set 3.6 V/cell (28.8 V).
- **Generic 3.65 V/cell LFP:** 29.2 V is allowed, but 28.8 V costs little capacity and leaves room for regen.

---

## 5. Recommendation

- **Best ready-made: two EarthX ETX36D in series.** It gives 327 Wh at 26.4 V. EarthX's own series rating is 100 A continuous and 28.8 V / 54 A charge.
  It weighs 3.6 kg, **2.55 kg heavier than the 1.05 kg WREKD 7S2P P50B**, and costs **$738**.
  - It is the only off-the-shelf option found that meets ≥ 250 Wh and ≥ 60 A.
  - The downsides are two boxes, no data link and no published low-temperature behaviour.
- **Best custom: an 8S4P pack of genuine Lithium Werks/A123 ANR26650M1-B cells.** It gives 264 Wh, a 208 A continuous cell rating and 480 A for 10 s.
  It weighs about 2.8 kg (estimate), **about 1.75 kg heavier than the Li-ion pack**.
  - **BMS:** the Battery Hookup 100 A CAN BMS with a 0 °C charge cut-off ($65), or a JK-B2A8S20P/30P for more current.
  - **Cost:** about €254 ex VAT in cells from NKON, plus about $65 for the BMS, plus spot-welding and nickel.
  - **US-stock alternative:** Vapcell T25 cells in the same 8S4P layout, $160 in cells, about 3.4 kg on the store's shipping weight.
  - **For maximum energy per kg,** an 8S2P Vapcell G65 32700 pack gives 333 Wh at about 2.7 kg. It has no current margin (60 A continuous, 110 A for 5 s), so it is second choice.

Every LFP option makes the robot about 1.7–2.6 kg heavier for the same energy. Keep the Li-ion pack unless charging safety outweighs about 12–18 % more robot mass.

## 6. Design notes for an LFP gyropup

- **Regen at full charge can open the BMS.** A full pack (28.8–29.2 V) has no room to absorb wheel or leg regen. The BMS opens on over-voltage, and the J501 and motors lose power.
  Stop charging at about 95 %, keep a brake resistor or clamp on the motor bus, and use a BMS whose charge limit is above the worst regen current (Battery Hookup: 60 A).
- **The flat LFP curve makes voltage a poor fuel gauge.** Use the BMS's coulomb counter over CAN.
  Suggested UVLO thresholds: warn at about 3.0 V/cell (24 V), crouch and stop at about 2.8 V/cell (22.4 V), BMS cut at 2.5 V/cell (20 V).
- **Charging below 0 °C:** A123 cells tolerate small currents. Headway allows only 0.1C below 0 °C. Pick a BMS with a hardware 0 °C charge block.
- **The J501's 36 V limit is not at risk.** An 8S LFP pack peaks at 29.2 V, so it has more headroom than 7S Li-ion (29.4 V).

## Sources

Every row above links its source inline. The main documents:
- EarthX: [AN-1609 series/parallel note](https://Aircraftspruce.Com/catalog/pdf/earthxparallel.pdf), [ETX36D](https://earthxbatteries.com/product/etx36d/), [ETX18F](https://earthxbatteries.com/product/etx18f/), [ETX24C](https://earthxbatteries.com/product/etx24c/), [Aircraft Spruce EarthX page](https://www.aircraftspruce.com/catalog/elpages/earthxbatteries.php).
- Antigravity: [RS user manual](https://antigravitybatteries.com/downloads/AG-Powersports-RS-Batteries-User-Manual.pdf) (series use prohibited).
- Lithium Werks: [ANR26650M1B page](https://lithiumwerks.com/?p=3097); [A123 2011 datasheet](https://piekarz.pl/pdf/49579).
- Headway: [HW 38120HP spec](https://img01.71360.com/file/read/www/M00/0B/28/wKj0iWK7y42AdMF9AAXpIIHG6ms774.pdf), [short sheet](https://cdn.shopify.com/s/files/1/0697/3395/files/data_sheet.pdf).
- Vapcell / lygte-info: [G65 32700 test](https://lygte-info.dk/review/batteries2012/Vapcell%20IFR32700%206500mAh%20G65%20(Blue)%202020%20UK.html), [IFR26650 test](https://lygte-info.dk/review/batteries2012/Vapcell%20IFR26650%202600mAh%20(Red)%20UK.html).
- BatterySpace: [25.6 V LFP pack list](https://www.batteryspace.com/256vlifepo4batterypacks.aspx).
- BMS: [Battery Hookup](https://batteryhookup.com/products/12v-lifepo4-smart-bms-w-low-temp-cutoff), [Fogstar JK 8S30P](https://www.fogstar.co.uk/products/smart-bms-jk-b2a8s30p-with-active-balancer-300a-4s-8s), [Daly M-series](https://www.dalybms.com/bms-12v-200a-daly-m-series-smart-bms-3s-to-24s-150a-product/).
- Chargers: [iCharger X8](https://www.progressiverc.com/products/icharger-x8), [ToolkitRC M8AC](https://pyrodrone.com/products/toolkitrc-m8ac-1-8s-ac-200w-dc-600w-20a-battery-charger-xt60), [Victron IP65 24/5](https://thesolarstore.com/products/victron-energy-bluesmart-ip65-24-5-120v-nema-1-15p-battery-charger).
