# Turret carrier purchasing audit — 2026-10-29

**Most scoped parts have supplier offers; the carrier is not purchase-ready or build-qualified.** Of 29 existing catalog/material lines, 22 have an in-stock indication at the checked supplier, one resistor has zero stock, one regulator is rationed, and five remain unverified. Stock is independent of fit, wiring correctness and safety. No purchase or substitution was made.

This is the removable base-board carrier in PR #67 at `faed5f510586ab282db4a27f6453165ac56f70d2`, before the subsequent C2 disconnect design. Integration base: `154d4de`. Tracking: #79 / PR #80; program #61. The rotor, cartridge, stand mating harness and whole robot are excluded. The [structured observations](turret-carrier-2026-10-29.json) contain exact keys, quantities, URLs, price tiers, source limits, and ten source-file hashes. They are a dated audit, not a replacement for the live catalog.

## Findings that must be resolved

1. **The selected holder's voltage evidence conflicts.** `docs/turret-wiring.md:139,457–458` explicitly places `0FHM0001ZXJ` upstream of the regulator on the robot's 30–42 V BUS. [Newark's exact SKU](https://www.newark.com/littelfuse/0fhm0001zxj/fuse-holder-in-line/dp/56P4440) lists 32 VDC, and the [2023 Littelfuse family sheet, rev 062923-B](https://www.mouser.com/datasheet/2/240/Littelfuse_Fuse_Holder_MINI_FHM_Datasheet-3313789.pdf) also says 32 V. However, [manufacturer rev 113020](https://www.mouser.com/datasheet/2/240/Littelfuse_Fuse_Holder_Inline_2520MINI_Datasheet-3311020.pdf) gives 58 V and explicitly includes bare `0FHM0001ZXJ`. The [newer rev 020425](https://www.littelfuse.com/assetdocs/littelfuse-fuse-holder-mini-fhm-datasheet.pdf?assetguid=339fa35e-eabc-45c5-9093-8abceaa8a2cf) lists 58 V for several suffixed variants but omits bare ZXJ while retaining 32 V headings. **The exact part needs an accepted current rating basis; this is not proof that the physical part is inherently limited to 32 V.** The initial draft's stronger mismatch conclusion is superseded. A 58 V fuse alone never establishes the holder rating. The separate 15–20.5 V stand does not create this same voltage conflict.
2. **The documented DT12 crimps and cable seal are incompatible.** [TE 0460-202-16141](https://www.te.com/en/product-0460-202-16141.html) is 16–20 AWG. Wiring lines 77–87 and 269 assign it directly to 24 AWG CAN pins 5–6 and safety pins 7–8, with no documented splice/adapter. The catalog's 14–16 AWG description is also wrong. [The selected DT04-12PA-L012 housing](https://www.te.com/en/product-DT04-12PA-L012.html) requires insulation OD 2.23–3.68 mm; selected Pololu 24 AWG wire is 1.4 mm. Changing only the contact does not fix sealing.
3. **Substrate identity and retail unit need correction.** The model uses a 50.8×30×1.6 mm board; catalog `proto-board-52x50` describes generic 50×70 material, but its linked [SparkFun PRT-08619](https://www.sparkfun.com/protoboard-wombat-pth.html) is an 80×100 mm PTH blank. Catalog `pack_qty: 2` means assumed fabrication yield, not two retail boards. One bought blank is distinct from the resulting cut piece. The linked [manufacturer v_1.4 board source](https://raw.githubusercontent.com/sparkfun/ProtoBoard_Wombat-PTH/v_1.4/Hardware/SparkFun_Protoboard-PTH-v14.brd) has a 78.74×99.06 mm outline, so the catalog’s claimed two 52×50 mm pieces do not fit as ordinary aligned cuts: even two 50 mm spans exceed the long edge by 0.94 mm before kerf. This is an unsupported yield assumption, not a revised pack quantity. The smaller carrier outline fits within the blank; thickness, custom hole placement, edge clearance and solder routing still require qualification. PR #67 subsequently documents a custom drill pattern; that newer work is outside this frozen audit.
4. **Protection coordination is still open.** `cad/turret_boards.py:140–141` places D14 across BUS to protect U2. [Taiwan Semiconductor P6KE51A](https://services.taiwansemi.com/storage/resources/datasheet/P6KE%20SERIES_P2203.pdf) allows a 70.1 V clamp and breakdown up to 53.6 V, above [Pololu 4095's 50 V input limit](https://www.pololu.com/product/4095). This comparison does not predict the actual transient; the claimed protection still needs a bounded electrical analysis/test. Catalog manufacturer choice remains “Taiwan Semiconductor or Diotec.” D8/fuse crowbar coordination is likewise not established by a diode surge rating alone. F1's 30 V rating is on reduced 12 V PAN and is not the holder/BUS mismatch.

## Supplier observations

All observations were read on 2026-10-29. Use the linked exact product, not a family result or suggested substitute. Web readers can initially return cached pages; the table prefers the latest successfully read page. The fuse snapshot reported a two-day cache age. These are not stock reservations or checkout-confirmed delivery promises. Factory lead times below concern replenishment and do not replace quoted delivery for listed stock. Prices are displayed USD; freight, tax and supplier-specific tariff treatment are not normalized.

McMaster current stock/ship dates are **unknown**, separately from the private M3×8 STEP login gap. Cached 2026-10-27 catalog terms are: 91290A111, 100/$11.59; 91290A113, 100/$13.28; 94459A140, 50/$10.91. No current pack terms were independently confirmed. Licensed CAD remains private.

### Carrier hardware

| Exact part | Needed | Checked stock | Order unit / displayed USD | Factory lead |
|---|---:|---|---|---|
| [91290A111](https://www.mcmaster.com/91290A111/) | 4 | Unknown | pack; price unknown | Unstated |
| [91290A113](https://www.mcmaster.com/91290A113/) | 4 | Unknown | pack; price unknown | Unstated |
| [94459A140](https://www.mcmaster.com/94459A140/) | 8 | Unknown | pack; price unknown | Unstated |

### Base-board circuit — one each

| Exact part | Needed | Checked stock | Order unit / displayed USD | Factory lead |
|---|---:|---|---|---|
| [NE555P](https://www.digikey.com/en/products/detail/texas-instruments/NE555P/277057) | 1 | 49,072 | piece; $0.59 | 12 wk |
| [MFR-25FBF52-1K](https://www.digikey.com/en/products/detail/yageo/MFR-25FBF52-1K/13011) | 1 | 44,751 | piece; $0.1 | 18 wk |
| [MFR-25FBF52-6K8](https://www.digikey.com/en/products/detail/yageo/MFR-25FBF52-6K8/9138205) | 1 | 0; expected Oct 30 | piece; $0.1 | 18 wk |
| [MKS2C031001A00JSSD](https://www.newark.com/wima/mks2c031001a00jssd/cap-0-1-f-63v-5-pet-potted/dp/46T6775) | 1 | 15,141 | piece; $0.452; min/multiple 10 | 17 wk |
| [K104K15X7RF53L2](https://www.digikey.com/en/products/detail/vishay-beyschlag-draloric-bc-components/K104K15X7RF53L2/2820506) | 1 | 24,958 | piece; $0.29 | 18 wk |
| [FG24X7R1H105KRT06](https://www.digikey.com/en/products/detail/tdk/FG24X7R1H105KRT06/5802988) | 1 | 30,377 | piece; $0.54 | 24 wk |
| [1N4148](https://www.digikey.com/en/products/detail/onsemi/1N4148/458603) | 1 | 555,750 | piece; $0.1 | 68 wk |
| [RSF100JB-73-2K2](https://www.digikey.com/en/products/detail/yageo/RSF100JB-73-2K2/18091) | 1 | 5,737 | piece; $0.2 | 18 wk |
| [D36V50F12](https://www.pololu.com/product/4095) | 1 | Rationed; backorders allowed | piece; $39.95 | Unstated |
| [MF-R300](https://www.digikey.com/en/products/detail/bourns-inc/MF-R300/259975) | 1 | 43,096 | piece; $0.6 | 4 wk |

### Adjacent harness and connectors

| Exact part | Needed | Checked stock | Order unit / displayed USD | Factory lead |
|---|---:|---|---|---|
| [MF-R010](https://www.digikey.com/en/products/detail/bourns-inc/MF-R010/259959) | 1 | 7,426 | piece; $0.4 | 4 wk |
| [1N5408G](https://www.newark.com/onsemi/1n5408g/standard-diode-3a-1kv-axial/dp/42K2941) | 1 | 31,895 | piece; $0.619 | 15 wk |
| [P6KE51A](https://www.newark.com/taiwan-semiconductor/p6ke51a/tvs-diode-600w-43-6v-unidir-do/dp/99AC4212) | 1 | 1,476 | piece; $1.28 | 20 wk |
| [0997010.WXN](https://www.digikey.com/en/products/detail/littelfuse-inc/0997010-WXN/701059) | 1 | 6,661 | piece; $1.04 | 12 wk |
| [0FHM0001ZXJ](https://www.newark.com/littelfuse/0fhm0001zxj/fuse-holder-in-line/dp/56P4440) | 1 | 779 | piece; $9.71 | 23 wk |
| [43020-1200](https://www.digikey.com/en/products/detail/molex/0430201200/252495) | 1 | 9,554 | piece; $0.85 | 8 wk |
| [43031-0001](https://www.digikey.com/en/products/detail/molex/0430310001/467798) | 12 | 462,110 | piece; $0.1 | 10 wk |
| [43025-1200](https://www.digikey.com/en/products/detail/molex/0430251200/252501) | 1 | 36,796 | piece; $0.81 | 9 wk |
| [43030-0010](https://www.digikey.com/en/products/detail/molex/0430300010/252480) | 12 | 119,975 | piece; $0.2 | 13 wk |
| [DT04-12PA-L012](https://www.digikey.com/en/products/detail/te-connectivity-deutsch-connectors/DT04-12PA-L012/7220237) | 1 | 533 | piece; $9.49 | 13 wk |
| [W12P](https://www.digikey.com/en/products/detail/te-connectivity-deutsch-ict-connectors/W12P/6566598) | 1 | 32,867 | piece; $0.4 | 5 wk |
| [0460-202-16141](https://www.digikey.com/en/products/detail/te-connectivity-deutsch-ict-connectors/0460-202-16141/7200926) | 12 | 619,223 | piece; $0.45 | 13 wk |

### Substrate, wire and print material

| Exact part | Needed | Checked stock | Order unit / displayed USD | Factory lead |
|---|---:|---|---|---|
| [PRT-08619](https://www.sparkfun.com/protoboard-wombat-pth.html) | 1 | In-stock label; count unstated | board blank; $7.25 | Unstated |
| [2630 / 2632 / 2634 / 2639](https://www.pololu.com/product/2630) | 1.44 m cut estimate | Unknown | 60 ft spool; $10.95 | Unstated |
| [18PTFESTRBLA25](https://www.digikey.com/en/products/detail/remington-industries/18PTFESTRBLA25/11613433) | 0.288 m cut estimate | 50 | 25 ft length; $64.56 | Unstated |
| [PA6-CF black 1 kg (exact store variant not verified)](https://us.store.bambulab.com/products/pa6-cf) | Current slice required | Unknown | spool; price unknown | Unstated |

DigiKey's one-piece tiers are recorded as displayed minimums, not verified order multiples. Manufacturer reels/boxes do not force full-reel purchases when cut tape or single pieces are offered. WIMA's Newark minimum is explicitly ten pieces: $4.52 to buy one needed capacitor. Remington's listing is fulfilled by the manufacturer and states approximately eight days to ship; its order unit is 25 ft, not a meter. WIMA and the checked TVS offer state UK stock and 4–6 business-day delivery. Pololu shows no regulator ship date. Wire colors are separate SKUs, not a four-color pack.

The 24 AWG requirement is C2 `4×120 mm` plus C3 `12×60 mm` = 1.20 m, or 1.44 m after the document's 20% cut allowance. The 18 AWG requirement is C2 `2×120 mm` = 0.24 m, or 0.288 m with allowance. These are estimates, not measured service slack. Red identification heatshrink, cable ties and protective sleeves lack exact selections; a complete harness order cannot yet be produced. The STS3215's existing three-pin lead is not a newly selected removable-board disconnect.

## Correction candidates — none selected

| Candidate | Verified evidence | Remaining decision |
|---|---|---|
| Littelfuse **0FHM0003ZXJS** | Rev 020425 exact row: 58 VDC, 20 A, 18 AWG leads; [DigiKey](https://www.digikey.com/en/products/detail/littelfuse-commercial-vehicle-products/0FHM0003ZXJS/29571868): 699, $6.39 each, one-piece tier, 10-week factory lead. | Accept exact current revision; older sheets differ, including GXL/TXL lead type. Verify body support, joints, routing and fuse access. This is an option if bare ZXJ cannot be qualified, not a mandatory redesign. |
| TE **0460-003-16329 / 2300908-1** | [Manufacturer drawing 2300908 rev A](https://www.te.com/commerce/DocumentDelivery/DDEController?Action=srchrtrv&DocFormat=pdf&DocLang=English&DocNm=2300908&DocType=Customer+Drawing&PartCntxt=2300908-1): gold size-16 pin; 24 AWG hand crimp needs M22520/7-1 with M22520/7-3 positioner. [DigiKey](https://www.digikey.com/en/products/detail/te-connectivity-deutsch-ict-connectors/0460-003-16329/26277860): 5,436, $1.51 each, one-piece tier, 19-week factory lead. | Select mating socket/plating, compatible sealing or a qualified wire transition, and validated tooling. Existing IWISS IWD-1620 is not established as acceptable for this 24 AWG operation. |

[TE application specification 114-151009 C3](https://www.te.com/commerce/DocumentDelivery/DDEController?Action=srchrtrv&DocFormat=pdf&DocLang=English&DocNm=114-151009&DocType=Specification+Or+Standard&PartCntxt=DT04-12PA-L012) p14 gives E-seal OD 1.35–3.05 mm and requires sealing plugs in unused cavities; this is a possible architecture direction, not a selected replacement housing. P24 requires wire OD within the seal range, and p42 recommends 20 mm straight wire exit without a backshell. The document also identifies P004 as a standard/no-modification code (p16), so W12P-P004 is not automatically an incompatible wedge, but its order identity/stock must remain separate. Contacts need manufacturer drawings and crimp acceptance, not merely an AWG label.

## C2 disconnect availability — design candidates only

The carrier owner requested these offers after the frozen 29-line audit. They are separate from that snapshot and do not select a connector or update the BOM. Each pair needs one housing of each type; four new pin/socket contacts would be additional to the existing stator contacts.

| Candidate | Checked supplier stock | Displayed USD each | Factory lead |
|---|---:|---:|---|
| [AMASS XT30U-M](https://www.tme.com/us/en-us/details/xt30u-m/dc-power-connectors/amass/) | 42,091 | $1.12 | Unstated |
| [AMASS XT30U-F](https://www.tme.com/us/en-us/details/xt30u-f/dc-power-connectors/amass/) | 38,342 | $0.99 | Unstated |
| [Molex 43020-0400](https://www.digikey.com/en/products/detail/molex/0430200400/252491) | 26,290 | $0.68 | 15 wk |
| [Molex 43025-0400](https://www.digikey.com/en/products/detail/molex/0430250400/252497) | 173,439 | $0.42 | 7 wk |
| [Molex 43031-0001](https://www.digikey.com/en/products/detail/molex/0430310001/467798) | 462,110 | $0.10 | 10 wk |
| [Molex 43030-0001](https://www.digikey.com/en/products/detail/molex/0430300001/467796) | 780,198 | $0.10 | 10 wk |

All were read on 2026-10-29. TME explicitly permits one-piece minimum and multiple; DigiKey shows one-piece price tiers with bulk housings and cut-tape contacts. Shipment dates were not confirmed. The [AMASS 2023V2 manufacturer sheet](https://www.china-amass.com/public/upload/20240608/810c62b3f7ace2287989748538eb2a6b.pdf) bases 15 A on 16 AWG and at most 30 K temperature rise; TME's 18 AWG field does not establish that same performance. AMASS specifies 100 mating cycles, whereas TME lists 1,000; preserve the manufacturer limit pending clarification. PR #67 owns the proposed 16 AWG pigtail change, solder/heatshrink, retention, crimp qualification, mounting and service paths.

## Carrier checklist handoff

- [ ] Electrical owner: settle exact holder rating/revision or select and validate the candidate.
- [ ] Electrical/mechanical owners: settle DT contact, actual conductor OD, sealing, mating socket/plating, crimp tools, unused cavities and pull acceptance together. Docs list 12 pins while only four positions are active.
- [ ] Carrier owner: finish C2 removable disconnect architecture, latch access, connector support, bend radii and measured service slack; refresh this dated scope afterward.
- [ ] Electrical owner: demonstrate D14/U2 transient and D8/fuse coordination; freeze the TVS manufacturer.
- [ ] Manufacturing owner: verify substrate thickness, cut outline, mounting holes and solder/lead clearance; correct retail units separately from yields.
- [ ] Purchasing owner: recheck McMaster current terms, Pololu regulator ship date, exact wire colors and Bambu US variant before ordering. Verify the expected resistor delivery; an expected date is not stock.
- [ ] Catalog owner: reconcile old 5 A/+24 V holder text against the 10 A/BUS design; review the fuse's LCSC alternative identity and the resistor's FRF versus FBF backup SKU.

No supplier communications or purchases were made. No geometry, CAD licensing boundary or installed hardware specification was changed. This audit does not qualify assembly fit, printability, protection, physical serviceability or safe operation.

## Reproduce the data checks

With PR #67 source history fetched, run `python research/supply/validate_carrier_audit.py` from the repo root. It compares ten frozen source hashes, catalog-key identity, all ten base-board designators plus the three adjacent harness designators, mounting-instance totals and wire arithmetic. It never imports CAD or queries suppliers. D7 (Feather USB) and C23 (hall sensor) are explicitly outside the carrier scope. Local fault injections remove U1, change a source digest, duplicate a catalog row, and turn unknown stock into zero; each must be rejected. This checker does not validate live inventory or the unselected correction candidates’ physical compatibility.
