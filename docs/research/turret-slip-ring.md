# Slip rings for the turret's pan joint

Sourced research for the Gyropup foam-ball turret (cad/turret.py in the turret worktree): a slip ring on the pan
axis so the turret can pan without limit. Every number below carries its source and the date it was read. Prices are
single-unit, US dollars unless marked. "est" marks an estimate and gives its basis. Written 2026-10-27; the plan that
uses this is docs/turret-plan.md.

## 1. Summary

- **The joint.** The pan axis is free below the tilt yoke: the pan ring (turntable) has a Ø40 open centre from
  z = 23 to 69 mm above the mounting face, the base's housing tube a Ø65 cavity from z = 0 to 34, and the yoke bridge a
  Ø30 hole at z = 69..77 (cad/turret.py: `pan_ring`, `pan_base`, `tilt_yoke`, read 2026-10-27). A **capsule** ring of
  Ø22-25 mm and up to ~52 mm long fits on the axis with its flange in the base foot; nothing else needs the axis.
- **What must cross.** 24 V power (≤ 11 A for < 50 ms at flywheel spin-up, ≤ 2.5 A game average), CAN (2), the
  safety line (2), the pan servo's TTL bus (1 + a signal ground), and 2 spare for a camera later: **2-3 power rings at
  8-10 A plus 6-8 signal rings at 2 A** (section 11).
- **Form factor and contacts.** Capsule, gold-on-gold V-groove rings with wire or fibre brushes. Every vendor below
  makes one; noise ratings run from < 4 mΩ (Moflon's "9" grade, Servotecnica < 10 mΩ dynamic) to 60 mΩ (Moog's
  commercial capsules); lives from 10 million revolutions (Moflon standard, Servotecnica) to 20 million (Moflon "9")
  and "> 50 million" (JINPAT LPC-36A); 150-500 rpm rated (we need 15 rpm: 90 deg/s).
- **Buy today in the US:** SparkFun ROB-13065 (Senring M220-12 / SNM022A-12, 12 × 2 A, $27.95, Digi-Key stocks it)
  and Adafruit 1196 (12 × 2 A, $19.95). Neither has power rings; four 2 A circuits paralleled each way carry the bench
  turret if the flywheels soft-start (section 12).
- **Buy for the robot (quote):** Senring **M220-0210-12S** (2 × 10 A + 12 signal, Ø22 × 40 mm, a catalogue standard),
  Moflon **MC330-P0308-S06** (3 × 8 A + 6 × 2 A, Ø22 × 33 mm) or its "MC3309" grade, Servotecnica **SVTS A 03-S-A-04/06**
  (4 × 6 A + 6 × 2 A, Ø22 × 41.2 mm, US office in California), Moog **AC6310** (3 × 10 A + 6 × 2 A, 1.38 in long,
  US made). No public prices; Moog's 12 × 2 A AC6023-12 shows about $192 on a distributor listing, which brackets the
  Moog tier. Estimates in section 5.
- **RoboMaster practice** is exactly this: 12-24 wire gold capsule or small through-bore rings (Moflon MT, JINPAT
  LPC/LPM, Senring) carrying 24 V and CAN from chassis to gimbal; the camera's USB does **not** go through the ring
  (section 6).
- **Hybrid (USB/Ethernet) rings** exist in the same Ø22 capsule (Moflon MUSB1221, ME1222; Servotecnica E1M option;
  Moog AC7203 at $938 from a US stockist) but cost 5-30× more. Reserve two signal rings now; buy a USB-rated ring only
  if a wired turret camera is wanted (section 7).
- **Contactless** (inductive power + wireless data) is an industrial product at this power (Spinner's 24 V / 100 W
  module, quote only; Balluff's 24 V 5 A coupler is discontinued); Qi-class receivers stop at 15 W. Not for this
  turret (section 8). **Mercury-wetted** rings (Mercotac) are excluded for a kids' toy (section 9).

## 2. The joint as built, and what the ring must do

From cad/turret.py (turret worktree, read 2026-10-27), T frame, z up from the TM mounting face:

| Feature | Value | Where |
|---|---|---|
| Pan bearing | 6810-2Z, 50 × 65 × 7, bottom at z = 40 | `BRG`, `Geo.brg_z` |
| Turntable (pan ring) | 63 T m1.25 gear, Ø40 open centre z 23..69, Ø50 journal z 28..47, circlip z 34..36 (Ø60.8 reach) | `pan_ring`, `circlip_z` |
| Base housing | tube ID Ø65 z 5..38, foot 5 mm with a Ø65 centre opening, cable window −y at z 5..23 (20 wide), the servo lead channel to the centre | `pan_base` |
| Yoke bridge | z 69..77, Ø30 cable hole | `tilt_yoke` |
| TM interface | 4 × M5 on 80 × 80, 2 × Ø5 dowels, Ø45 hole; head ring ID Ø60 | `TM_*`, `head_ring_tm` |
| Pan drive | STS3215 at (−52.6, 0), 21 T pinion, 3:1; stop post at r 68.5..74 (front), finger on the turntable, hard stop ±173.5°, software ±170° | `Geo`, `pan_base`, `pan_ring` |
| Pan speed | 90 deg/s at most (servo 45 rpm / 3), 100 deg/s cap near people | cad/turret_motion.py, exports/turret/motion.json |
| Panning mass / inertia | 1047 g, 0.0033 kg m² about the pan axis (full hopper) | motion.json |
| Tilt axis | on the pan axis, z = 136 | `Geo.tilt_t` |

So the axis is free from the mounting face up to the yoke bridge (69 mm), with Ø40 clear between z 23 and 69 and
Ø65 below. The ring's revolutions are few: 600 per day at an average 30 deg/s for 2 h (calc), so 10⁷ rated revolutions
is about 46 years. Speed is never above 15 rpm. What matters is contact noise under the flywheel current pulse, CAN
integrity, and a mounting that does not load the ring's own bearings.

## 3. Form factors

| Form | What it is | Sizes seen | Fit here |
|---|---|---|---|
| **Capsule** | Rotor shaft in a plastic or aluminium can; leads out of both ends; stator flange or none; its own miniature ball bearings | Ø12.4-25 mm, 14-66 mm long: Moflon MC190/260/330 (Ø22, 26/33 mm), Senring M220 (Ø22, 19-54.5 mm), Servotecnica SVTS A 01-07 (Ø12-25), Orbex 312/322 (Ø12.4/22), Moog AC6023/6305/6310 (0.57-1.38 in long), Adafruit 775/1195 (Ø12), 736/1196 (Ø22) | **Yes**: in the Ø40 bore with the flange in the foot |
| **Through-bore (hollow shaft)** | Hollow rotor for a shaft, cable or optics; a stator with an anti-rotation tab | Moflon MT012: 12.7 mm bore, Ø56, 25.8-155.6 mm long; Moflon MT (XMU's: 20 bore, 42 OD); Senring SNH012: 12.7 bore, Ø56; Rotary Systems SR013: through bore, 2.14-4.94 in long; Ingiant DHK012-12 | Ø56 does not fit the Ø40 bore or the Ø45 TM hole; a 20/42 ring fits only in the Ø65 cavity below z 23 (23 mm tall: too short). Would allow a magnet encoder on the axis, at the cost of a deeper base |
| **Pancake (flat / platter)** | Rings on a disc, axial brushes; thin, wide | Moflon MP/MF series; Senring SNF flat series (a Mouser-hosted sheet exists); Adafruit 776 toroid 2.1 in OD × 0.5 in ID, 6 × 5 A (no longer stocked) | Thin but wide; could sit under the turntable only by widening the base; no advantage here |

Sources: Moflon MC260/MC330 sheets ([mc260.pdf](https://www.moflon.com/pdf/mc260.pdf), [mc330.html](https://www.moflon.com/mc330.html), read 2026-10-27);
[Moflon MT012](https://www.moflon.com/mt012.html) (read 2026-10-27); Senring M220 catalogue via
[SparkFun](https://cdn.sparkfun.com/assets/5/b/0/2/3/Senring-M220-Series-SlipRing-Catalog_ROB-13065.pdf) (read 2026-10-27);
[Servotecnica SVTS A series](https://servotecnica.com/wp-content/uploads/2025/09/SVTS-A-Series.pdf) (read 2026-10-27);
[Rotary Systems SR013](https://rotarysystems.com/slip-rings/product/10-amps-to-600-vac-capsule) (read 2026-10-27);
[Adafruit slip ring category](https://www.adafruit.com/category/223) (read 2026-10-27); Ingiant DHK012-12 via search
(2026-10-27). The Senring SNH012 figures come from a reseller listing seen in search (bore 12.7, OD 56, 4 circuits at 5 A,
300 rpm) and are unverified.

## 4. Contacts and what the ratings mean

- **Gold-on-gold, V-groove rings and wire brushes** are the standard in every capsule above: Moflon "90° V-groove ring
  design", "gold-gold" (MC260 sheet); Senring "gold-on-gold contacts"; Servotecnica "gold-gold technology used for
  both rings and brushes"; Moog "gold" contacts; Rotary Systems "gold rings with compatible gold alloy wire brushes";
  Orbex "gold on gold"; Adafruit "gold plated slip ring".
- **Fibre brush** (a bundle of fine wires per contact): Senring calls its SNM022A "fiber brush technology ... multiple
  points of contact per brush bundle, low contact force per fiber and low contact wear rates"
  ([SNM022A-12 sheet](https://cdn.sparkfun.com/datasheets/Robotics/SNM022A-12%20updated.pdf), read 2026-10-27).
  Servotecnica USA added a **multi-wire brush** option to SVTS A that "increases the service life by 5-10 times
  compared to traditional single-wire brush solutions" ([press release](https://us.servotecnica.com/en/servotecnica-usa-launches-new-multi-wire-brush-option-for-svts-a-series-slip-rings/), read 2026-10-27).
  Rotary Systems' SR013/SR015 use "multiple gold alloy wire brushes" per ring. JINPAT's LPC-12 catalogue: "advanced
  fiber brush technology, maintenance-free, no lubrication required".
- **Electrical noise / dynamic resistance** is the contact resistance variation while turning, measured at low speed
  and small current: Moog specifies "60 milliohms max" at 6 V DC, 50 mA, 5 rpm ([AC6310 page](https://www.moog.com/products/slip-rings/commercial-industrial-slip-rings/compact-slip-ring-capsules/ac6310.html));
  Moflon 10 mΩ at 10 rpm for MC260/MC330 and 4 mΩ for MC2609/MC3309; Servotecnica "dynamic contact resistance
  < 10 mΩ"; Rotary Systems "< 50 mΩ peak at 5 rpm" (SR010), "< 100 mΩ peak" (SR013/SR015); Moflon MT012 "< 5 mΩ"
  with contact resistance "< 2 mΩ". The number is per contact; a 10 A pulse across a 10 mΩ contact is a 0.1 V step,
  across 60 mΩ 0.6 V (calc). For CAN and TTL these are harmless; for the power path they set the ride-through
  capacitor (section 12).
- **Life** is quoted in revolutions at the rated speed: Moflon > 10 million (MC260/330), > 20 million (MC2609/3309);
  Servotecnica 10⁷ "depending on speed, environmental conditions and size"; JINPAT LPC-36A "> 50,000,000 runs ref.";
  Orbex 200 series "up to 80 million" ([Orbex IP65 release](https://orbexgroup.com/orbex-slip-rings-offer-ip65-protection-for-demanding-environments/)).
  Moog and Rotary Systems give no number ("precision ball bearings meet or exceed life requirements for most
  commercial applications").
- **Speed:** Moflon 250 rpm (1000 for the "9" grade, 150 for IP65); Senring 150 rpm (M220 catalogue) or 250 rpm
  (SNM022A sheet and SparkFun page: the two disagree); Servotecnica 500 rpm; Moog 250 rpm; Rotary Systems SR015
  600 rpm; JINPAT LPC-12A 300 rpm; Adafruit 300 rpm. All far above our 15 rpm.
- **IP:** IP51 is the capsule default (Moflon, Senring, Servotecnica "S", Orbex); IP65 is an option (Moflon
  "-IP65" in aluminium at 150 rpm; Servotecnica "U" aluminium housing, not on SVTS A 02; Orbex). Moog's sealed
  units are "dust and light splash only". The turret is a kids' outdoor toy: IP51 inside the base is acceptable
  because the ring sits inside the housing tube under the turntable; the base has a drip skirt.
- **Temperature:** −30..80 °C (Moflon, Senring), −20..80 (Servotecnica, −40 option), −40..80 (Moog, Orbex, Moflon
  MT012).
- **Torque:** 0.02-0.05 N·m plus 0.01 N·m per 6 rings (Moflon, Senring): nothing against the pan servo's 8.8 N·m at the
  turntable (cad/turret_motion.py).

## 5. Vendors

Prices and stock read 2026-10-27 unless noted. "Quote" means the vendor publishes no price.

### 5.1 Moog (Blacksburg VA; Moog Components Group)

| Model | Rings | Rating | Size | Noise | Speed | Leads | Price / buy |
|---|---|---|---|---|---|---|---|
| [AC6023](https://www.moog.com/products/slip-rings/commercial-industrial-slip-rings/compact-slip-ring-capsules/ac6023.html) | 6, 12, 18, 24 | 2 A, 240 VAC | 0.57-1.38 in long; Ø0.87 in (22 mm) per distributor listings | 60 mΩ max | 250 rpm | 28 AWG silver-plated, PTFE, 12-48 in | AC6023-12 about $192 on an Octopart listing (search snippet, 2026-10-27, not verified on the page); "quick shipment"; "Find a distributor" |
| [AC6305](https://www.moog.com/products/slip-rings/commercial-industrial-slip-rings/compact-slip-ring-capsules/ac6305.html) | 3 × 5 A + 6/9/12 × 2 A | 240 VAC | 1.38 in long | 60 mΩ | 250 rpm | 20 AWG (5 A), 26 AWG (2 A) | quote |
| [AC6310](https://www.moog.com/products/slip-rings/commercial-industrial-slip-rings/compact-slip-ring-capsules/ac6310.html) | **3 × 10 A + 3 or 6 × 2 A** | 120 VAC | 1.38 in long | 60 mΩ at 6 V / 50 mA / 5 rpm | 250 rpm | 16 AWG tin-plated (10 A), 26 AWG (2 A) | quote; sealed and metal-housing options |
| SRA-73587 | 4 × 10 A + 24 × 2 A, 240 VAC | | | | | | search snippet only; product page 404 on 2026-10-27 |
| AC7203 (ESE224 at DSTI) | 2 × 2 A + 2 × 10 A + 1 Ethernet 100 Mbps | | 43 mm long | | | | **$938** at [store.dsti.com](https://store.dsti.com/ese224-8-circuit-slip-ring) (search snippet; page returned 403) |

Mounting advice (Moog AC6023 installation guide, via search 2026-10-27; the PDF itself returned 404): flange-mount the
capsule with the barrel cantilevered; drive the rotor "through a flexible coupling such as rubber tubing, a helical
coupling, or a bellows type to absorb eccentricity"; the ring "is not built to bear the weight of the attached
equipment"; never hard-mount both ends.

Moog's data-sheet PDFs under moog.com/content/dam/... returned HTTP 404 to a plain fetch on 2026-10-27; the product
pages above are the sources used.

### 5.2 Moflon (Shenzhen; ships DHL/UPS; "best selling standard models in stock")

| Model | Rings | Size | Grade | Price / buy |
|---|---|---|---|---|
| [MC260](https://www.moflon.com/mc260.html) | 12 × 2 A; mixed: MC260-P0304-S06 (3 × 4 A + 6 × 2 A), MC260-P0208-S02 (2 × 8 A + 3 × 4 A + 2 × 2 A per the sheet's table), MC260-P0308 (3 × 8 A) | Ø22 × 26 mm | MC260: 250 rpm, > 10 M revs, 10 mΩ at 10 rpm, engineering plastic; **MC2609**: 1000 rpm, > 20 M revs, 4 mΩ, plastic + aluminium, thicker gold, "imported bearings" | quote (sales@moflon.com); a "Buy Online" link to a store |
| [MC330](https://www.moflon.com/mc330.html) | 18 × 2 A; **MC330-P0308-S06 (3 × 8 A + 6 × 2 A)**, MC330-P0604-S06 (6 × 4 A + 6 × 2 A), MC330-P0408-S02 (4 × 8 A + 2 × 2 A), MC330-P0215 (2 × 15 A) | Ø22 × 33 mm | same two grades (MC330 / MC3309) | quote |
| [MT012](https://www.moflon.com/mt012.html) through-bore | 2-48 rings, 10 A or 2 A each, any mix | 12.7 mm bore, Ø56, 54.8 mm long at 12 rings | 1000 rpm, < 5 mΩ noise, < 2 mΩ contact, IP51, −40..80 °C, 22 AWG / 16 AWG leads | quote |
| MUSB1221 / 1222 | 1 or 2 USB 2.0 channels + power (5 A rings listed) | Ø22 | 250 rpm, 10 M revs | quote (search 2026-10-27) |
| ME1222 | Ethernet + 5 A power | Ø22 | | quote (DirectIndustry listing, 2026-10-27; page returned 403) |

Common MC data (sheets read 2026-10-27): 0-240 VAC/VDC, insulation ≥ 100 MΩ at 500 VDC, dielectric 500 VAC 60 s,
28 AWG PTFE leads 300 mm standard (longer on request), torque 0.05 N·m + 0.01 N·m per 6 rings, IP51, −30..80 °C,
0-85 % RH. The sheet notes "N channels 2A rings parallel can be used as 1 channel N × 2A current", i.e. paralleling is
sanctioned. Flange options FL01-FL07 are drawn in the sheet (no dimensions in the text layer). Moflon's
[installation guide](https://www.moflon.com/pdf/install.pdf) (read 2026-10-27): fix one side with screws to keep
concentricity, "make sure it rotate fluently before tighten the screws", and "do not fix anti-rotating pin forcibly".

### 5.3 Senring (Shenzhen; sold in the US through SparkFun / Digi-Key / RobotShop for the 2 A models)

Catalogue ([M220 series](https://cdn.sparkfun.com/assets/5/b/0/2/3/Senring-M220-Series-SlipRing-Catalog_ROB-13065.pdf), read 2026-10-27), all Ø22 mm:

| Part | Rings | Leads | Length |
|---|---|---|---|
| M220-06 / -12 / -18 / -24 / -36 | 6-36 × 2 A | 26 AWG PTFE silver-plated | 19 / 26 / 33 / 40 / 54.5 mm |
| M220-0605 / -0805 / -1205 | 6 / 8 / 12 × 5 A | 22 AWG | 40 mm |
| M220-0210 / -0310 / -0410 | 2 / 3 / 4 × 10 A | 17 AWG | 26 / 33 / 40 mm |
| **M220-0210-12S** | **2 × 10 A + 12 signal** | 17 AWG + 26 AWG | 40 mm |
| M220-0310-06S | 3 × 10 A + 6 signal | 17 + 26 AWG | 40 mm |
| M220-0410-04S | 4 × 10 A + 4 signal | 17 + 26 AWG | 40 mm |
| M220-0205-12S / -0305-12S / -0605-06S | 2/3 × 5 A + 12 signal, 6 × 5 A + 6 signal | 22 + 26 AWG | 40 mm |
| M220-0230 / -0330, M220-0320-04S | 2/3 × 30 A, 3 × 20 A + 4 signal | 12 / 14 AWG | 40-47 mm |

Specification (same catalogue): 150 rpm, −30..80 °C, gold-gold, plastic housing, torque 0.05 N·m + 0.01 per 6
circuits, IP51, 0-240 VAC/VDC, insulation ≥ 300 MΩ, dielectric 300 VAC, noise < 0.01 Ω, leads 150 mm standard. Flange
type "A" (M220A) or none; the SNM022A-12 sheet says "speeds up to 250 rpm continuous", "compatible with data bus
protocols", "Transfers analog and digital signals, Ethernet, USB, RS, Canbus".

US retail of the plain 2 A versions: [SparkFun ROB-13065](https://www.sparkfun.com/slip-ring-12-wire-2a.html) (12 wires,
28 AWG, 250 mm leads, 2 A, 210 VDC / 240 VAC, 250 rpm, Ø22 × 26.5 mm, flange Ø44.5, IP51) **$27.95**, in stock; the
same at [Digi-Key](https://www.digikey.com/en/products/detail/sparkfun-electronics/13065/5762402) $27.95, 21 in stock
(search snapshot 2026-10-27; the page itself returned 403); RobotShop US $27.95. ROB-13064 (6 wires) $21.50. The mixed
power models are not stocked by these resellers: quote from sales@senring.com.

### 5.4 JINPAT (Shenzhen; claims a North America office in the LPC-12 catalogue header)

- LPC-12A: 240 V, 2 A, 300 rpm (DirectIndustry listing, search 2026-10-27); "12 circuits × 2A; dielectric
  ≥ 500 V at 50 Hz between circuits".
- LPC-36A catalogue: "operating life > 50,000,000 runs ref."
- LPT025-0610: 10 A primary current (a through-bore series).
- Capsule rings with USB 3.0: JINPAT says "only the capsule slip rings can integrate USB3.0 signals"; hollow-shaft
  rings carry USB 2.0 (JINPAT RoboMaster article, search 2026-10-27; the page returned 403 to a fetch).
- No price found; the catalogue pages on pdf.directindustry.com returned 403. US purchase path unverified.

### 5.5 Orbex Group (Austin TX)

- 300 series miniature capsules: Ø12.4 mm (312Mx) and Ø22 mm (322Mx), 2-56 circuits, gold on gold, ABS, IP51 with IP65
  on request, −40..80 °C option, M1/M2/M3 flange types; e.g. [312M3-1200](https://orbexgroup.com/product-category/slip-rings/miniature-slip-rings/)
  (12 × 2 A, Ø12.4 × 19.5 mm), [322M3-1800](https://orbexgroup.com/?p=628) (18 × 2 A, Ø22 × 33.4 mm),
  [322M1-0202](https://orbexgroup.com/?p=620) (**2 × 6 A + 2 × 2 A**, Ø22 × 28 mm). Read 2026-10-27.
- No prices ("Add to Quote"); phone +1-408-945-8980; STEP and PDF drawings on each product page.
- Orbex [installation guide](https://orbexgroup.com/?p=561) (read 2026-10-27): "The rotor should be driven with a
  flexible drive coupling"; rubber tubing, heat-shrink or a flexible coupling; "for applications that run at 5 rpm or
  less, the rotor leads can be used as the flexible coupling"; "the slip ring's bearings are not designed to support
  external or radial loads"; flat washers under the flange screws.

### 5.6 Rotary Systems (Ramsey MN; made in USA)

- [SR010](https://rotarysystems.com/slip-rings/product/2-amp-to-250-vdc-capsule): 6/12/18 rings, 2 A, 250 VDC, < 50 mΩ
  peak at 5 rpm, 1.12 / 1.48 / 1.84 in long; part numbers 30050-1006/1012/1018-000.
- [SR015](https://rotarysystems.com/slip-rings/product/5-amps-to-500-vac-capsule/): 6-36 rings, 5 A, 500 VAC, 600 rpm,
  < 100 mΩ peak, 22 AWG, anodised aluminium, through bore; 30050-1512-000 (12 rings) 2.10 in long.
- [SR013](https://rotarysystems.com/slip-rings/product/10-amps-to-600-vac-capsule): 6-24 rings, 10 A, 600 VAC, through
  bore, 2.14 in (6 rings) to 4.94 in; 30050-1306-000.
- No prices, no mass, no diameter on the pages ("Request More Info", 800-959-0146). Read 2026-10-27.

### 5.7 Servotecnica (Nova Milanese, Italy; Servotecnica USA, Fair Oaks CA, +1 925-640-7042)

From the [SVTS A series sheet](https://servotecnica.com/wp-content/uploads/2025/09/SVTS-A-Series.pdf) (read
2026-10-27): capsules Ø12 (A 01), Ø15 (A 02), **Ø22 (A 03)**, Ø25 (A 04); high-current A 05 (Ø22: 3 × 4/8/10/20 A),
A 06 / A 07. Common data: 240 VDC/VAC, silver-plated PTFE colour-coded leads 250 mm (multiples of 250 on request),
dielectric 500 VAC, insulation > 500 MΩ, **dynamic contact resistance < 10 mΩ**, up to 500 rpm, stainless miniature
bearings, ABS or aluminium housing, gold-gold, −20..80 °C, IP51 (S) or IP65 (U), **expected lifetime 10⁷ revolutions**.
Lead gauge by rating: 1 A continuous / 2 A peak 28 AWG; 2 A 26 AWG; 4 A 22 AWG; 6 A 20 AWG; 8 A 16 AWG.

SVTS A 03 (Ø22) standard models (L1 body length, L2 rotor stub, mm): 00/06 (19), 00/12 (28), **02/02 (2 × 6 A + 2 × 2 A,
28)**, 00/18 (33.4), 03/00 (3 × 8 A, 33.4), 00/24 (41.2), **04/06 (4 × 6 A + 6 × 2 A, 41.2)**, 00/36 (57). IP65 "U"
versions are 27-66 mm. Ethernet option E1M (100BASE-T) adds 5 rings: e.g. A 03-S-A-00/06-E1M, 28 mm. The drawing text
gives the A 03 flange as Ø44 with 3 × Ø5.5 holes (PCD read as Ø35), a Ø7.8 rotor stub, 2.4 mm flange. SVTS A 04 (Ø25):
04/18 (4 × 6 A + 18 × 2 A, 51.5 mm), 03/15 (3 × 8 A + 15 × 2 A). No prices; quote through the US office.

### 5.8 Adafruit and SparkFun (the cheap baseline, in stock in the US)

| Part | Rings | Size | Rating | Price (2026-10-27) |
|---|---|---|---|---|
| [Adafruit 736](https://www.adafruit.com/category/223) | 6 × 2 A | Ø22, 44 mm flange | 240 V, 26 AWG | $14.95 |
| [Adafruit 1196](https://www.adafruit.com/product/1196) | 12 × 2 A | Ø22, 44 mm flange | 240 V, 28 AWG 6 in leads, 300 rpm | $19.95 (6 in stock) |
| Adafruit 775 / 1195 | 6 / 12 × 2 A | Ø12 | | $17.50 / $24.95 |
| Adafruit 776 toroid | 6 × 5 A | 2.1 in OD, 0.5 in ID | | no longer stocked |
| [SparkFun ROB-13064](https://www.sparkfun.com/slip-ring-6-wire-2a.html) | 6 × 2 A | Ø22 | 250 rpm | $21.50 |
| [SparkFun ROB-13065](https://www.sparkfun.com/slip-ring-12-wire-2a.html) | 12 × 2 A | Ø22 × 26.5, flange Ø44.5 | 210 VDC, 250 rpm, IP51 | $27.95 |

The Adafruit ring is a Hangzhou Prosper SRC022A ([drawing sheet](https://cdn-shop.adafruit.com/datasheets/SRC022A-6.pdf),
read 2026-10-27: 2 A per ring, 26 AWG silver-plated FEP, 250 mm leads, dielectric 500 VAC, insulation 1000 MΩ, noise
< 0.01 Ω, 0-300 rpm, −20..80 °C, precious-metal contacts; the A1 flange drawing shows three Ø5 holes). SparkFun's is
Senring's M220-12 (section 5.3). Both are the same Ø22 / Ø44 capsule class as the quality rings, so one printed carrier
fits all of them with a per-model hole pattern.

### 5.9 Others seen

Ingiant (Jiujiang): DHK012-12 through-bore (12.7 mm, 12 circuits at 5 or 10 A, 380 VAC, 300 rpm, IP51; also sold as a
"CAN bus slip ring"), DHM022 capsules, USB capsules "up to 20 amps" power (search 2026-10-27). RotaRX RX-HS012C-QS1-02010S
(12.7 bore, 2 × 10 A + 10 × 5 A, 250 rpm, 20 M revs, IP51). Not pursued: no US path found, and the capsules above cover
the need.

## 6. What RoboMaster teams actually use

RoboMaster infantry robots spin the chassis under a continuous-yaw gimbal; the chassis battery (24 V) and the CAN bus
reach the gimbal through a slip ring. Sources read 2026-10-27:

- **Xiamen University Robot Team, infantry BOM** ([ArmsBOM](https://asr-crash.github.io/XMU-Robot-Team/ArmsBOM.html)),
  gimbal yaw axis, row quoted exactly: "导电滑环 1 硬件 非官方成品模块 采购（定制） MT MOFLON 内径20,外径42，12路 420 1 420":
  a **Moflon MT through-bore, 20 mm bore, 42 mm OD, 12 circuits, ¥420 (about $58), custom-ordered**.
- **Central South University FYT, 2024 infantry technical document**
  ([PDF](https://hz-rm-bbs-web-prod.oss-cn-hangzhou.aliyuncs.com/bbs-prod/a047210666c94cf7b8acd189e8712fac/RoboMaster2024FYT%E6%88%98%E9%98%9F%E6%9C%BA%E7%94%B2%E5%A4%A7%E5%B8%88%E8%B6%85%E7%BA%A7%E5%AF%B9%E6%8A%97%E8%B5%9B%E6%8A%80%E6%9C%AF%E6%96%B9%E6%A1%88.pdf)):
  the balancing (wheel-legged) infantry and the four-steer infantry use a **24-wire ring** ("中间通过 24 线电滑环来实现云台的
  全角度自由转动"), the low-profile under-feed infantry a **12-wire hollow ring** ("12 线的中空电滑环"); their stated design
  rule "相机信号线不穿过滑环" (**the camera's signal cable does not pass through the slip ring**); the yaw link carries a CNC
  6061 "电滑环加强件" (slip-ring reinforcement); the M2006 feed motor's rotor is kept clear of the ring.
- **JINPAT on RoboMaster** (DirectIndustry article, search snippet): "infantry robots mainly consume two series of
  standard slip rings ... LPC and LPM", channel counts "between 24 and 30"; USB 3.0 only on capsule rings; hollow-shaft
  rings up to 60 mm bore for the teams.
- **South China University of Technology, 2025 hero open-source report** (search snippet): a 12-way ring, 119 mm OD,
  50 mm ID on the gimbal (a hero: larger than an infantry).
- **DJI's own parts:** the GM6020 gimbal motor has an 18 mm hollow shaft so "a slip ring or other accessories" can be
  mounted through it ([GM6020 page](https://www.robomaster.com/zh-CN/products/components/general/gm6020/info), snippet);
  DJI's [2020 AI robot](https://www.robomaster.com/zh-CN/products/components/detail/2499) limits yaw to ±90° and lists
  no ring; the RoboMaster PM01 power module's gimbal channel is rated 10 A continuous and 30 A for < 500 ms
  ([PM01 page](https://www.robomaster.com/zh-CN/products/components/detail/1252), snippet). A 2020 forum thread asks how
  to specify a ring for 360° yaw with a GM6020 ([bbs 7028](https://bbs.robomaster.com/article/7028); replies not
  retrievable).

What this teaches: 12-24 gold rings, 2 A class signals plus paralleled or dedicated power rings, CAN through the ring
as a matter of course, USB kept off it, and the ring mounted on a stiff metal part concentric with the yaw bearing.

## 7. Hybrid rings: CAN, Ethernet, USB

- **CAN** needs no special ring: it is a differential pair at ≤ 1 Mbit/s. Senring lists "Canbus" among the signals its
  plain capsule carries; Ingiant sells the DHK012-12 as a "CAN bus slip ring" with ordinary rings. RoboMaster teams run
  CAN through plain rings (section 6). Keep the pair on adjacent rings, twisted on both sides, and terminate at the two
  ends of the bus (docs/turret-plan.md, section 2).
- **Ethernet:** Servotecnica E1M/E1G options on SVTS A 03/04 (100BASE-T adds 5 rings; 1000BASE-T 9 rings); Moflon
  ME1222 (Ø22, Ethernet + 5 A power); Moog AC7203 (100 Mbps) sold by DSTI as ESE224 at $938; Moog AC7195 (1 Gbps,
  45 circuits, ESE2358). A 100BASE-TX link needs two pairs; a single-pair 100BASE-T1 PHY would need one pair on a plain
  ring (not seen offered; it is an automotive PHY, untested here).
- **USB:** Moflon MUSB1221/1222 (Ø22, 1-2 USB 1.0/2.0 channels, 5 A power rings, 250 rpm, 10 M revs); JINPAT LPC with
  USB 3.0; Ingiant USB capsules ("USB 2.0 class"). Plain gold capsules pass USB full-speed (12 Mbit/s) reliably and
  high-speed (480 Mbit/s) marginally: the vendors' USB models are the same rings with impedance-matched pairs and short
  internal leads.
- **For us:** nothing hybrid is needed for CAN and the servo bus. Reserve two adjacent signal rings as a pair for a
  turret camera later; if a wired high-rate camera is wanted, buy a USB-rated capsule of the same Ø22 size then
  (Moflon MUSB1221 class), or put an ESP32-S3 Wi-Fi camera on the turret and cross nothing.

## 8. The contactless alternative

Inductive power across the joint plus a wireless data link:

- **Spinner** (Munich) sells contactless DC rotary joints "100 W at 24 VDC and 300 W at 24 VDC", "> 200 million
  rotations", with capacitive data coupling (IPROS listing and Spinner catalogue, search 2026-10-27; the catalogue PDF
  returned 404 to a fetch; data sheet BN 637493 covers the 24 V / 300 W unit). Industrial pricing, quote only (est
  well over $1,000: the class of Moog's $938 Ethernet capsule and above).
- **Balluff BIC0076** inductive coupler, 24 VDC, 5 A rated output, IP67, 7/8 in connector: marked **"Canceled"** on
  Balluff's pages ([BIC0076](https://www.balluff.com/en-tw/products/BIC0076), search 2026-10-27); its signal sibling
  BIC000A (0.5 A) lists at $654.45 on Octopart.
- **Würth Elektronik / Infineon 760308EMP-WPT-200W** development kit (200 W, with bidirectional data over the coil):
  "no longer manufactured" at Farnell (search 2026-10-27).
- **Qi-class** receivers (5-15 W) cannot feed a 240 W spin-up pulse; they could feed only the electronics if the
  flywheel power stayed on the turret with its own battery, which breaks the 1.5 kg head budget (docs/head-payload.md).
- **Data** could go over Wi-Fi/ESP-NOW, Bluetooth or an IR link, but the safety line must stay a wired, dynamically
  tested circuit (docs/turret-plan.md section 2.8).

Verdict: not for this turret. A $30-300 gold capsule does the job; contactless costs more than the rest of the turret
and still needs a radio for data.

## 9. Excluded: mercury-wetted rings

Mercotac's rotary connectors use "a pool of liquid metal" ([Mercotac FAQ](https://mercotac.com/html/faqs.html), read via
search 2026-10-27); resellers describe the Mercotac 630 as using "mercury as a conductive medium". Mercury inside a
toy that children handle and that can be dropped is not acceptable regardless of the (small, unpublished) quantity;
excluded without further evaluation.

## 10. Mounting practice (from the vendors' guides)

1. Fix the **stator flange** rigidly to the stationary part with flat washers under the screws (Orbex; Moog).
2. Drive the **rotor through a flexible coupling**: rubber or silicone tubing over the rotor stub, heat-shrink, or a
   pin in a slot with clearance; the ring's own bearings carry the rotor; "do not fix the anti-rotation pin forcibly"
   (Moflon); at ≤ 5 rpm the leads alone may act as the coupling (Orbex). Never hard-mount both ends (Moog).
3. Keep **axial and radial loads off** the ring's bearings (Orbex, Moog): the turret's pan bearing (6810) carries the
   turret; the ring only turns.
4. Secure the **leads** so they touch nothing while turning and apply no side load (Orbex); strain-relieve within
   30 mm of each connector (docs/mechanical-interfaces.md cable rules).
5. Check it turns freely before tightening (Moflon).

## 11. The loads, from their data sheets (for the ring's channel list)

| Load | Where it rides | Numbers | Source (read 2026-10-27) |
|---|---|---|---|
| DJI Snail 2305 flywheel motor, ×2 | cartridge (tilts) | 875 rpm/V, 10.9 mN·m/A, phase R 181.5 mΩ, L 25.9 µH, 7 pole pairs, rotor 1.84 kg·mm², 27.8 g, 24 V rated; no-load 0.4 A at 21,000 rpm (catalog) | [RoboMaster Snail 2305](https://www.robomaster.com/en-US/products/components/detail/2397); catalog/turret.json |
| DJI C615 ESC (the DJI option) | cartridge | 24 V rated, 26 V max, 15 A continuous phase, 20 A for 3 s, 3S-6S, 500 Hz PWM, 9.7 g | RoboMaster C615 (search snippet); catalog |
| Repeat Robotics AM32 35 A ESC (the chosen ESC) | cartridge | 35 A, 3-6S; AM32 firmware EEPROM has `limits.current`, `current_P/I/D`, `max_ramp` (0.1-25 % per ms), `startup_power`, `use_sine_start`, `stall_protection`, `brake_on_stop`, `low_voltage_cut_off`, KISS telemetry, DShot and servo PWM input | catalog/turret.json; [AM32 eeprom.h](https://raw.githubusercontent.com/am32-firmware/AM32/main/Inc/eeprom.h); forum reports that the current limit became a closed PID loop in v2.19 RC1 (2025) and was unreliable before: **verify on the bench** |
| DJI M2006 P36 + C610 (feed dial) | cartridge | motor 90 g, 36:1, 500 rpm no load, 1 N·m continuous, 416 rpm at 1 N·m; C610 **10 A max continuous**, CAN, 17 g, 50 × 22 × 7.3 mm; $41 (committee) | [RoboMaster M2006](https://www.robomaster.com/zh-CN/products/components/detail/1277) |
| Feetech STS3215 12 V (tilt on the turret, pan in the base) | both sides | 6-12.6 V, **stall 2.7 A**, no-load 0.2 A, 45 rpm, 4096 counts, 1 Mbit/s half-duplex TTL; registers: min/max angle limit 9/11 (set 0 for multi-turn), max torque 16, protection current 28 (6.5 mA units, default 511 = 3.3 A), overload 35/36, mode 33 (0 position, 1 constant speed, 2 PWM, 3 step), torque limit 48, goal position 42 (−32767..32767 × 0.087° = ±7.9 turns), present current 69; "±7 circles" relative mode, turn count not kept over power-off | [Waveshare ST3215 wiki](https://www.waveshare.com/wiki/ST3215_Servo); [STS memory table](https://aifitlab-wiki.super.site/feetech-servo-motor-docs/feetech-sts-servo-memory-table-analysis) (third-party; verify against Feetech's sheet) |
| Picotronic DD520-1-24(12x40) laser | cradle (tilts) | 12-24 VDC, 5-20 mA (10 typ), 520 nm, 1 mW class 2, 1 kHz internal modulation | [Picotronic 70121025](https://www.picotronic.de/picopage/en/product/detail/id/356547) |
| Lights (WS2812 ring or similar) | turret | budget 0.5 A at 5 V = 0.15 A at 24 V (est: 12 LEDs at 40 mA) | est |
| Turret MCU + sensors | turret | Adafruit Feather M4 CAN Express 4759: SAME51 120 MHz, built-in CAN transceiver with its own 5 V boost, 3.3 V logic, 21 GPIO, 16 PWM, 6 ADC, 50.8 × 22.8 × 7 mm, 5 g, **$24.95**, in stock; budget 0.2 A at 5 V | [Adafruit 4759](https://www.adafruit.com/product/4759) |
| 24 → 12 V regulators (Pololu) | turret and base | D24V150F12: 12 V ±4 %, 15 A typ, 4.5-40 V in, instantaneous limit ~32 A, thermal shutdown, 43 × 32 × 11 mm, **$79.95**, rationed (newer D42V110Fx family to 60 V, 6-16 A, $69.95 recommended by Pololu); D36V50F12: 12 V ±4 %, 4.5 A typ at 36 V in (2.3-6.5 A over the range), 13.3-50 V in, 25.4 × 25.4 × 9.5 mm, **$39.95** | [Pololu 2885](https://www.pololu.com/product/2885); [Pololu 4095](https://www.pololu.com/product/4095); [category](https://www.pololu.com/category/131/step-down-voltage-regulators) |
| Flywheel-rail switch for the safety line | turret | Pololu Big MOSFET Slide Switch HP 2815: 4.5-40 V, 16 A continuous (6 A before it is "noticeably warm"), 8.6 mΩ, ON pin > ~1 V turns it on, default off, reverse protected, **$8.49**; Pololu: "Do not use this switch as an emergency cutoff" (so it is one layer, not the only one) | [Pololu 2815](https://www.pololu.com/product/2815) |
| TE Deutsch DT04-12PA-L012 (the TM connector) | base | 12 positions, size 16 pins, **13 A max per contact**, 250 VDC, IP68 / IP6K9K, panel mount, 45.9 × 55.1 × 35.6 mm; the page says "not currently available" (use a distributor); mates DT06-12SA with W12S wedge and 0462-201-16141 sockets (cad/build_turret.py) | [TE DT04-12PA-L012](https://www.te.com/en/product-DT04-12PA-L012.html) |

## 12. The current through the ring: the spin-up pulse and what limits it

The physics agent's launch model (sim/turret_launch.py, exports/turret/launch/launch.json in the turret worktree,
read 2026-10-27) fixes the flywheel design point: Ø36 mm wheels, 25 % crush, **a 12 V regulated rail** for the
flywheel ESCs (the velocity ceiling: 10,437 rpm no load, the worst ball at 100 % throttle on a +5 % motor and a +4 %
regulator leaves at 64.2 fps, 3.6 fps under the 70 fps cap), set speed 9,408 rpm (985 rad/s) for 55 fps, wheel
inertia 3.92e-6 kg·m² each, ESC current limit 10 A, 7 % speed drop per shot. With those numbers (a current-limited
spin-up on the Snail's 875 rpm/V, 0.363 Ω phase-to-phase, friction from the 0.4 A no-load current; both motors; the
24 V side through a 90 %-efficient regulator; calc, 2026-10-27):

| Case | ESC input peak per motor | **24 V ring current peak, both motors** | Charge | Time to 98 % speed | RMS over 1 s |
|---|---|---|---|---|---|
| 12 V rail, 10 A ESC limit, step command | 10.0 A | **11.1 A** | 0.37 C | 39 ms | 1.5 A |
| 12 V rail, 4.5 A limit (one D36V50F12 per ESC) | 4.5 A | 5.0 A | 0.31 C | 79 ms | 0.9 A |
| 12 V rail, 10 A limit, **200 ms speed ramp** | 1.9 A | **2.1 A** | 0.27 C | 197 ms | 0.5 A |
| 12 V rail, 10 A limit, 350 ms ramp | 1.1 A | 1.2 A | 0.24 C | 344 ms | 0.4 A |
| 24 V rail (no regulator), 10 A limit | 5.9 A | 13.1 A | 0.38 C | 35 ms | 1.7 A |
| 24 V rail, 15 A limit | 9.9 A | 22.0 A | 0.44 C | 23 ms | 2.4 A |

Also: kinetic energy at set speed 1.9 J per wheel; steady friction current 0.18 A per motor; energy restored per shot
0.26 J per wheel, i.e. 5.2 W mechanical at 10 shots/s, about 0.3 A average at 24 V; the burst's re-acceleration pulses
are shorter than the spin-up (recovering 7 % of speed at the 10 A limit takes about 6 ms, calc).

What this means for the ring:

- The spin-up is a **40 ms pulse of 11 A at 24 V** if the ESCs are stepped to full speed with a 10 A limit, and a
  **2 A pulse** if the firmware ramps the set speed over 200 ms (the laser-on warning before the first shot is 0.35 s,
  so the ramp costs nothing). The I²t of a 40 ms, 11 A pulse is 4.8 A²s: thermally nothing for a 10 A ring or a 16 AWG
  lead; even four paralleled 2 A rings on 28 AWG leads survive it (0.7 V drop per lead at 11 A, calc), which is why the
  cheap ring works on the bench once the ramp is in.
- **Contact drop:** 10 mΩ × 11 A = 0.11 V, 60 mΩ × 11 A = 0.66 V (calc). The regulators accept 13.3-40 V, so a 24 V bus
  may sag 8 V before anything notices.
- **Ride-through:** a contact bounce of 2 ms at 11 A costs 2,750 µF for an 8 V droop; 5 ms costs 6,900 µF (calc). Three
  1,000 µF / 35 V low-ESR electrolytics at the regulators' input on the turret cover 2 ms; the firmware treats a
  longer dropout as a fault (the MCU keeps running from its own capacitor-backed 5 V).
- **The dial** (M2006 / C610) is limited to 10 A by the C610; the firmware caps its current command (3 A to step, 5 A
  jam threshold) and never steps during a spin-up, so the two pulses do not add.
- **Continuous** draw: 0.3 A (idle at speed) to about 2 A (a burst with lights, servos holding) at 24 V, inside the
  40 W head budget (docs/head-payload.md).

Hence the channel list in docs/turret-plan.md: **two power rings per rail at ≥ 8 A** (or one at 10 A each way with the
ramp as the primary limit), six to eight 2 A signal rings.

Two more numbers the plan rests on (calc, 2026-10-27, same motor constants):

- **The rail is the speed ceiling.** The simulator's breakdown (gyropup main cc58794) found that on 24 V the Ø36 wheels
  reach 21,000 rpm, a 39.6 m/s surface speed and about 123 fps; on the launch model's 12 V rail the no-load speed is
  10,437 rpm (19.7 m/s surface, 61-64 fps for the worst ball). An ESC cannot exceed its rail voltage, so the fixed 12 V
  regulator, not a throttle number, is the cap; the barrel's chronograph gates (2.34 ms for 50 mm at 70 fps, 2.49 ms
  at 66 fps, 1.33 ms at 123 fps) give an independent trip.
- **Braking by a phase short.** With the three phases shorted, the back-EMF drives 29.6 A at the set speed and the
  speed decays with τ = I·R/(ke·kt) = 12 ms: 5 % at 36 ms, 1.5 % at 50 ms. Unbraked, the 0.18 A friction gives
  τ ≈ 2 s. The simulator found a dropped ball reaches the wheels 96 ms after a release, so a 12 ms brake catches it.

## 13. Not verified, and what would settle it

- Prices and lead times of every quality ring (Moog, Moflon, Senring mixed models, Servotecnica, Orbex, Rotary
  Systems, JINPAT): all "quote". The user sends the requests (Gyropup is private; no vendor was contacted for this
  research). Octopart's $192 for AC6023-12 and DSTI's $938 for ESE224 are search snippets, not fetched pages.
- Moog's PDF data sheets and installation guides (404 to plain fetches on 2026-10-27): the Moog numbers above come from
  the product pages and a search summary of the AC6023 installation guide.
- JINPAT's North America office and US purchasing: only a garbled catalogue header mentions it.
- AM32's current-limit behaviour on the Repeat Robotics 35 A board (firmware version, units of `limits.current`,
  whether the 2025 PID loop is in the shipped build): a bench test with a current probe.
- The Senring M220 speed rating: 150 rpm (catalogue) vs 250 rpm (SNM022A sheet, SparkFun). Irrelevant at 15 rpm.
- The exact flange hole patterns of the Senring M220A and Adafruit SRC022A rings (the text layers of the drawings give
  Ø44-44.5 flanges and "3 × Ø5" for the Prosper A1 type): measure the ring in hand before printing the carrier.
- Feetech STS multi-turn behaviour (register map from a third-party wiki; Waveshare's "±7 circles" statement): confirm
  on the servo in hand that the turn count resets at power-up and that mode 3 (step) behaves as described.
