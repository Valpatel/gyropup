# Preferred sensors and compute for gyropup

Checked 2026-10-25. Data lives in `catalog/sensors_compute.json` (10 items).
Prices are single-unit list prices before shipping and tax, for reference only. "n/p" means not published.

The preferred payload is:
- a Seeed reServer Industrial J501 carrier with a Jetson AGX Orin 32GB, in the printed j501-agx enclosure
- a Velodyne VLP-16 Puck
- a Stereolabs ZED X or ZED 2i
- an Intel/RealSense depth camera, model to be decided: D435i, D455, D457 or D405

The ZED Link Duo is listed only as a possible adapter (`"preferred": false`). It turns out not to fit the J501.

## Bottom line

- **The J501 works with:**
  - the VLP-16 over Ethernet
  - the ZED 2i over USB 3
  - a USB RealSense (D435i, D455 or D405)
- **Both GMSL cameras (ZED X and D457) are blocked on the J501.**
  - Neither vendor ships a driver for Seeed's MAX96724 GMSL board.
  - Stereolabs' ZED Link Duo cannot plug into the J501 at all, because the connector is different.
- **The VLP-16 cannot run directly from a 6S or 7S pack.** It needs a regulated 12 V rail that can deliver at least 3 A.
- **Recommended set today:** VLP-16 + ZED 2i + D435i (or D455). It is all Ethernet/USB, needs no custom kernel work, and the sensors weigh about 1.13 kg.

## Specs

Sources:
- **[ZX]** [ZED X datasheet](https://cdn.sanity.io/files/s18ewfw4/staging/7e01a2228a00212daa4daed50035ef87250bf7d5.pdf/ZED%20X%20-%20ZED%20X%20Mini%20-%20Datasheet.pdf)
- **[Z2i]** [ZED 2i datasheet V1.5](https://cdn.sanity.io/files/s18ewfw4/staging/17e28531d47c0c5feab2be4ca304abf06ffa889a.pdf/ZED%202i%20-%20Datasheet%20-%20V1.5%20-%202026-09-22.pdf)
- **[VLP]** [VLP-16 datasheet 63-9229 Rev K (zip)](https://data.ouster.io/downloads/datasheets/velodyne/Puck%20Datasheets.zip) and [VLP-16 user manual Rev F](https://data.ouster.io/downloads/velodyne/user-manual/vlp-16-user-manual-revf.pdf)
- **[RS]** [RealSense D400 datasheet, Mar 2026](https://www.realsenseai.com/wp-content/uploads/2026/03/RealSense-D400-Series-Datasheet-Mar-2026.pdf)
- **[D457]** [D457 datasheet, Dec 2025](https://realsenseai.com/wp-content/uploads/2025/12/RealSense-D457-Datasheet-Dec-2025.pdf)
- **[J501]** [J501 datasheet](https://files.seeedstudio.com/wiki/reComputer-Jetson/J501/reServer_Industrial_J501_Carrier_Board_Datasheet.pdf)
- **[NV]** [NVIDIA AGX Orin technical brief](https://www.nvidia.com/content/dam/en-zz/Solutions/gtcf21/jetson-orin/nvidia-jetson-agx-orin-technical-brief.pdf)

### Sensors

| | VLP-16 | ZED X | ZED 2i | D435i | D455 | D457 | D405 |
|---|---|---|---|---|---|---|---|
| Mass | ~830 g, without cable or box [VLP] | 239 g [ZX] | 229 g [Z2i] | 75 g ±10% [RS] | 116 g ±10% [RS] | ~145 g [D457] | 58 g ±10% [RS] |
| Mass with cable | n/p | n/p | n/p | n/p | n/p | n/p | n/p |
| Size (mm) | Ø103.3 × 71.7 | 163.4 × 31.8 × 36.7 | 175.3 × 30.3 × 43.1 | 90 × 25 × 25 | 124 × 29 × 26 | 124 × 29 × 36 | 42 × 42 × 23 |
| Mounting | 1/4-20, 7.1 mm deep, plus 2 locating-pin holes (5/32 in pins) in the base | Bottom: 1/4-20 plus 2× M3 at 36 mm. Back: 4× M4 on 80 × 10 mm | Bottom: 1/4-20 plus 2× M3 at 36 mm. Back: 4× M3 on 153.4 × 14 mm | Bottom: 1/4-20. Back: 2× M3, 45 mm apart, 3 mm deep max, 0.4 N·m | Bottom: 1/4-20, 9 mm deep max. Back: 2× **M4**, 95 mm apart, 4 mm deep max | Bottom: 1/4-20. Back: 2× M4 inserts, 61.5 mm apart, 3.0 N·m max | Bottom: 1/4-20. Back: 2× M3, 20 mm apart |
| Supply | 9–18 V (regulated) | 5–20 V over the coax (PoC) | USB 5 V | USB 5 V | USB 5 V | 10.8–13.2 V over the coax (PoC) | USB 5 V |
| Power | 8 W typical. Up to 3.0 A surge at spin-up | 1.46 W typical | 1.9 W typical | 3.40 W at max mode | 3.46 W | 3.72 W | 1.48 W |
| Interface / connector | 100 Mbps Ethernet (UDP), via a 3.0 m captive cable to the interface box (RJ45) | GMSL2, FAKRA Z | USB 3.0, Type-C with locking screws | USB 3.1 Gen 1, Type-C | USB 3.1 Gen 1, Type-C | GMSL2 on FAKRA. USB-C is for debug only | USB 3.1 Gen 1, **Micro-B** |
| FOV (H × V) | 360° × 30° (+15° to −15°) | 110° × 80° (2.2 mm lens). 73° × 45° (4.6 mm lens) | 110° × 70° (2.1 mm). 68° × 38° (4.6 mm) | Depth 87° × 58°. RGB 69° × 42° | Depth 87° × 58°. RGB 90° × 65° | Depth 87° × 58°. RGB 90° × 65° | Depth 84° × 58° |
| Minimum range | n/p | 0.3 m (2.2 mm). 1.0 m (4.6 mm) | 0.3 m (2.1 mm). 0.5 m (4.6 mm) | 0.28 m at 720p, 0.105 m at 424 × 240 | 0.52 m at 720p | 0.52 m at 720p | 0.10 m at 720p, 0.04 m min |
| Maximum / ideal range | 100 m | 20 m / 0.3–12 m (2.2 mm) | 20 m / 0.3–12 m (2.1 mm) | n/p / 0.3–3 m | n/p / 0.6–6 m | n/p / 0.6–6 m | n/p / 0.07–0.5 m |
| IMU | none listed | accelerometer ±12 g, gyro ±1000 dps, 200 Hz | accelerometer ±8 g, gyro ±1000 dps (400 Hz), magnetometer, barometer | BMI055 or BMI085 | BMI055 or BMI085 | BMI085 | none |
| Shutter | — | global | rolling | global (depth) | global | global | global (depth) |
| IP rating | IP67 | IP67 | IP66 | n/p | n/p | IP65 | n/p |
| Operating temperature | −10 to 60 °C | −20 to 60 °C | −10 to 45 °C | 0 to 35 °C ambient | 0 to 35 °C | 0 to 35 °C | 0 to 35 °C |
| Shock / vibration | 500 m/s², 11 ms; 3 Grms, 5–2000 Hz | 2 g RMS, 3–500 Hz | n/p | n/p | n/p | n/p | n/p |
| CAD | n/p (none on [Ouster downloads](https://ouster.com/downloads/velodyne-downloads)) | [STEP, wide](https://cdn.sanity.io/files/s18ewfw4/staging/0ddd9d208a26fcfc08cd91e402a4493e06a805ec.step/ZED%20X%20Wide.step), [STEP, narrow](https://cdn.sanity.io/files/s18ewfw4/staging/02f9b19bcb895b0a5f4699d5ce2bcb197d23a786.step/ZED%20X%20Narrow.step) | [STEP](https://cdn.sanity.io/files/s18ewfw4/staging/1eae249387d9bde53972abbe470483024c31c6fb.step/ZED2i.step) | [SLDPRT zip](https://dev.realsenseai.com/download/41950) (no STEP) | same zip | same zip | same zip |
| Price | n/p | $599 | $499 | $399 | $499 | $599 (backorder) | $325 |

Notes on the table:
- **ZED X and ZED 2i mounting:** hole spacings are from the datasheet drawings. The ZED X has max thread depths of 6.4 mm (bottom) and 5 mm (back).
- **D457 range:** its datasheet range of 0.4 to >10 m is a datasheet figure, not an ideal range.
- **D405 connector:** the datasheet says Micro-B, which contradicts the garbled store page. Trust the datasheet.
- **Where to buy:**
  - Stereolabs prices: [Stereolabs store](https://www.stereolabs.com/store).
  - RealSense prices: [store.realsenseai.com](https://store.realsenseai.com/). Since 2026-02-03 the store adds a tariff surcharge; the amount is not published.
- **The D456** ($560) is the IP65 USB version of the D455, with the same size and mass.

**VLP-16 identity check.** Ouster's current [VLP-16 page](https://ouster.com/products/hardware/vlp-16) quotes different figures: 590 g, 200 m, 40° vertical FOV, IP68/69K, −40 to 65 °C. These do not match the classic Puck datasheet above. The specs here assume the classic 63-9229 Puck. Weigh the unit to confirm (about 830 g expected).

### VLP-16 interface box ([VLP] manual 5.4, Appendix C/D)

- **Size and mass:** n/p. Drawing 50-6001 Rev B shows a flanged Polycase box with two flange holes, but gives no overall size.
- **Connectors:**
  - RJ45 Ethernet
  - 5.5 × 2.5 mm DC barrel jack, centre positive
  - 6-pin GPS port
  - internal screw terminals for PPS/NMEA
- **Cables:** the sensor cable is about 3.0 m and permanently attached. A 1.0 m Ethernet cable is supplied.
- **Power input:** the box does **not regulate**. Input goes through a 3.0 A fuse straight to the sensor, with a 5KP30A TVS diode across it (30 V standoff). The only regulator is a 7805, and it feeds the GPS only. The sensor's 9–18 V range therefore applies at the barrel jack.
- **Running without the box:** allowed, if your harness provides equivalent fuse, reverse-polarity and over-voltage protection (manual 5.4.2).
- **Cable:** do not cut it without a Velodyne waiver, because there is a minimum length requirement.

### Compute box

| Item | Value | Source |
|---|---|---|
| J501 carrier | 176 × 163 mm, 225 g without module | [J501] |
| GMSL extension board (optional) | 103 × 45 mm, 47 g; 2× MAX96724; 8× GMSL1/2; −20 to 60 °C | [J501] |
| AGX Orin 32GB module | 100 × 87 mm, 15–40 W (64GB: 15–60 W). **Mass n/p** | [NV] |
| Seeed heatsink with fan | 100 × 87 × 34 mm; fan 5 V, 0.16 A. **Mass n/p**; $49 | [heatsink datasheet](https://files.seeedstudio.com/wiki/reComputer-Jetson/J501/323011387Jetson_AGX_Orin_Heatsink_100x87x34mm-datasheet.pdf), [store](https://www.seeedstudio.com/Aluminum-heatsink-with-Fan-for-Jetson-AGX-Orin-p-5970.html) |
| Printed enclosure | 206 × 181 × 112 mm; **0.4–0.7 kg (estimate, not measured)** | j501-agx repo |
| Input | DC 12–36 V on a 2-pin terminal block. Board power "within 15–60 W" | [J501] |
| I/O | 1× GbE + 1× 10GbE (RJ45); 3× USB 3.1-A, 1× USB 3.1-C host; CAN; 2× SATA; M.2 M/B/E; mPCIe | [J501] |
| CAD | [carrier STEP](https://files.seeedstudio.com/wiki/reComputer-Jetson/J501/RESERVER_AGX_ORIN_CARRIER_BOARD.stp), [module STEP](https://developer.nvidia.com/downloads/jetson-agx-orin-module-3d-step-modelzip), and the enclosure assembly STEP in the j501-agx repo | |

Catalog `mass_g` is `null`, because the module and heatsink masses are not published. Weigh the assembled box.

## Integration answers

### 1. ZED X on the J501: blocked

**Seeed's GMSL board, electrically:**
- It looks compatible. The board feeds 12 V over the coax through MAX20087 protectors ([GMSL board schematic](https://files.seeedstudio.com/wiki/reComputer-Jetson/J501/GMSL2_Adapter_Board_For_J501_v1_SCH.pdf)), and the ZED X accepts 5–20 V over the coax [ZX].
- The board's 4-port FM4-NZRP jacks are not the ZED X's single FAKRA Z. Stereolabs sells a 1-to-4 FAKRA cable whose hub end is a "Mini Z plug" ([cable datasheet](https://cdn.sanity.io/files/s18ewfw4/staging/5e6000357620db56f0ec57cb522b6377880c4790.pdf/GMSL2%20Cables%20-%20Datasheet.pdf)). Whether that keying mates with the Seeed jack is unverified.

**Seeed's GMSL board, software:**
- Not supported. Stereolabs' GMSL2 drivers are packaged per capture card and deserializer, e.g. `stereolabs-zedlink-duo_1.3.2-LI-MAX96712-all-L4T36.4.0_arm64.deb` ([driver install page](https://docs.stereolabs.com/docs/products/embedded/zed-link-capture-card/gmsl2/install-and-upgrade-the-drivers/)).
- The [ZED Link compatibility page](https://docs.stereolabs.com/docs/embedded/zed-link) marks "Other Jetson carrier boards" as having no GMSL2 support, and says to contact support@stereolabs.com.
- Seeed's GMSL documentation lists only Seeed SENSING cameras, such as the SG3S-ISX031C. It names no ZED X ([Seeed GMSL cameras wiki](https://wiki.seeedstudio.com/sensing_gmsl_cameras/)).
- No document found says the MAX96724 is driver-compatible with the MAX96712.

**ZED Link Duo on the J501: does not fit.**
- **ZED Link Duo:** connects through a Samtec QTH-060-04-H-D-A (120-pin, 0.5 mm, 16 mm stack) built for the **AGX Orin devkit** camera connector. It is powered from that port, draws about 0.32 W, and weighs about 30 g [ZED Link Duo datasheet](https://cdn.sanity.io/files/s18ewfw4/staging/917f28656b640bfdb4d056294e9aad9ad5fc77be.pdf/ZED%20Link%20Capture%20Card%20Duo%20-%20Datasheet%20-%20V1.3%20-%202026-09-08.pdf).
- **J501:** the carrier's camera expansion is **2× Samtec QSH-030-01-L-D-A (60-pin)** ([carrier schematic](https://files.seeedstudio.com/wiki/reComputer-Jetson/J501/202003906_reServer_Industrial_J501_Carrier_Board_v1.0_SCH_PDF_20240529.pdf), sheet 29). Seeed's GMSL board mates with these through QTH-030 plugs.
- **Mismatch:** both the connector size and the pinout are different.
- **Other ZED Link cards:** the Quad also targets the AGX devkit, and the Mono is Orin Nano/NX only.

**Paths forward:**
- **(a)** Use the ZED 2i over USB (works now).
- **(b)** Ask Stereolabs support whether they will provide a MAX96724 or J501 driver.
- **(c)** Run the ZED X on a Stereolabs-supported host (AGX Orin devkit or ZED Box). This adds a second computer.

### 2. RealSense on AGX Orin / JetPack 6

**USB (D435i, D455, D405, and D456): supported.**
- librealsense v2.58.1 added JetPack 6 / 6.2.2 support and fixed missing metadata on JetPack 6 USB3. The current release is v2.59.1, which lists JetPack 5.0.2, 6.0–6.2 and 7.0 ([release notes](https://github.com/realsenseai/librealsense/releases/tag/v2.59.1)).
- The [Jetson install guide](https://github.com/realsenseai/librealsense/blob/master/doc/installation_jetson.md) offers three routes:
  - **Debian packages:** need JetPack ≥ 5.0.2.
  - **RSUSB user-space backend:** `libuvc_installation.sh`. No kernel changes, but it has multi-camera and performance limits.
  - **Native backend via `patch-realsense-ubuntu-L4T.sh`:** verified on AGX Orin with JetPack 6.0, and recommended for production.
- With one camera, RSUSB is the low-risk start.

**D457 over GMSL: blocked on the J501.**
- The official [realsense_mipi_platform_driver](https://github.com/realsenseai/realsense_mipi_platform_driver) supports JetPack 5.0.2–7.1. On AGX Orin it expects the RealSense MAX9296 deserializer board plus a Leopard Imaging LI-JTX1-SUB-ADPT passive adapter on the devkit connector.
- The README says other deserializer boards "might need modification".
- Overlays exist for some third-party boards, including Seeed's Orin Nano **J401** robotics GMSL board. None exists for the J501 or for AGX Orin with MAX96724.

**D457 over USB:**
- The D457 datasheet says its USB-C is "targeted for production and debug purposes only" (§3.7.5).
- If you need IP65 over USB, the D456 is the supported part.

### 3. VLP-16 to the J501

- **Data:**
  - Connect the interface box's RJ45 to the J501's **1 GbE port (LAN0)**. The sensor is 100 Mbps, and this keeps the 10GbE port free.
  - The sensor's default IP is 192.168.1.201. Give the J501 port a static 192.168.1.x address on its own subnet.
  - The sensor broadcasts UDP, so do not bridge that port onto a shared network.
  - PPS/NMEA from a GPS can be wired through the box for time sync.
- **Power:**
  - The datasheet range is **9–18 V**, "with Interface Box and Regulated Power Supply". The box passes input straight through, as described above.
  - A 6S pack (18.0–25.2 V) and a 7S pack (21–29.4 V) both exceed 18 V, so **neither can feed it directly**.
  - Use a regulated **12 V DC-DC rated for at least 3 A**. The manual asks for up to 3.0 A during rotor spin-up, then about 0.3–1.0 A in operation (manual 10.2.3.3.9).
  - The J501 itself runs straight from the pack (12–36 V).

### 4. Vibration, shock and gyroscopic effects

**VLP-16 robustness:**
- It is rated for 500 m/s² (about 51 g), 11 ms shock and 3 Grms, 5–2000 Hz vibration. The manual says it "does not need shock proofing" (manual 5.2).
- Mount it rigidly; the 1/4-20 plus locating pins prevents it rotating on the stud.
- Bearing life is best at 0° tilt. A balancing robot pitches continuously, but only by a few degrees.
- Repeated jump landings above 50 g are outside the rating, so add an elastomer isolator if jumps are aggressive.

**Rotor vibration:**
- The rotor spins at 5–20 Hz (300–1200 RPM in steps of 60).
- Any rotor imbalance shows up at that frequency, which overlaps the balance loop's bandwidth.
- Measures:
  - Keep the balance IMU off the lidar mast.
  - Choose a fixed RPM, e.g. the default 600 RPM (10 Hz).
  - Add a notch filter at that frequency if the IMU sees it.

**Camera IMUs and shutters:**
- The ZED X (global shutter, ±12 g IMU, rated 2 g RMS 3–500 Hz) is the most robust camera for a jumping robot.
- The ZED 2i is rolling-shutter, so expect skew during fast pitch.
- The RealSense IMUs are limited to ±4 g, so they will clip on landings.
- Use a dedicated body IMU for balance, not camera IMUs.

**Gyroscopic effect: an upper bound only.**
- Rotor mass and inertia are **not published**.
- As a deliberately pessimistic bound, treat the entire 0.83 kg unit as a solid cylinder of radius 51.65 mm:
  - I ≤ ½ · 0.83 · 0.05165² ≈ 1.1 × 10⁻³ kg·m²
  - Angular momentum L = I·ω ≤ 0.035 / 0.070 / 0.139 N·m·s at 5 / 10 / 20 Hz.
- The real rotating part is only a fraction of the unit (base and cap are fixed), so the true value is lower.
- With the spin axis vertical:
  - A **pitch** rate Ω produces a torque L·Ω about the **roll** axis. At 3 rad/s that is at most 0.10 / 0.21 / 0.42 N·m.
  - A **roll** rate (e.g. leaning into turns) produces a torque about pitch, which the balance controller must reject.
  - **Yaw** produces none.
- For scale: a 15 kg robot with a 0.4 m track has a static roll-restoring moment of about 15 · 9.81 · 0.2 ≈ 29 N·m. The gyroscopic term is therefore at most about 1–2%. It is small but real; model it as a disturbance.
- Spin-up also applies a one-off yaw reaction torque while the rotor accelerates. Start the lidar before enabling balance.

## Sensor-head layout recommendation

1. **Lidar on top, clear horizon.**
   - Put the VLP-16 at the highest point, with nothing above the plane of its −15° to +15° beams. Allow for the lidar's own mast.
   - Cables should exit downward (the cable is side-exit).
   - **Blind ring:** the lowest beam reaches the ground at h / tan 15° ≈ 3.7·h. For example:
     - lidar at 0.5 m: about 1.9 m blind ring
     - lidar at 0.8 m: about 3.0 m
   - Body pitch changes this by roughly ±tan(pitch). Use the depth cameras to cover the near field.
   - Publish the lidar's pose through the leg and IMU TF tree. Do not assume the lidar stays level.
2. **Cameras forward, below the lidar.**
   - **ZED (stereo):** face forward, tilted 10–20° down so it sees the ground from about 0.3 m out. That is the ZED 2i/X minimum range with the wide lens.
   - **RealSense:** pick by job.
     - D435i (min-Z 0.28 m) or D405 (7–50 cm): near-field obstacles or terrain at the feet.
     - D455: 0.6–6 m.
   - Back-face mounting on an aluminium plate is the vendor's recommended thermal path [RS §3.8.2.2].
   - Keep all cameras out of the lidar's beam plane.
3. **Mass placement.**
   - **Compute box (about 0.6–1.0 kg of known parts plus the unpublished module and cooler):** the largest and heaviest item. Mount it low in the torso, close to the hip axis. It sets the body's inertia and needs airflow for its fan.
   - **Sensor head (VLP-16 830 g + ZED 229–239 g + RealSense 58–145 g ≈ 1.1–1.2 kg):** keep it compact and as low as the lidar horizon allows.
   - A higher CoM slows the inverted-pendulum dynamics, which makes it easier to balance. It also raises the wheel torque needed for a given acceleration, the tip-over risk on slopes, and the energy needed to jump.
   - A short mast over the torso beats a tall one.
4. **Cables:**
   - GMSL2 coax: 33 mm static and 66 mm loaded bend radius.
   - USB-C: use locking cables (the ZED 2i has thumbscrews).
   - The VLP-16 has a 3 m captive cable to the interface box. Mount the box on the torso next to the 12 V DC-DC.

## Payload mass and power budget

| Item | Mass (published) | Power, steady | Notes |
|---|---|---|---|
| J501 + AGX Orin 32GB + cooler + enclosure | 225 g carrier + 400–700 g enclosure (estimate) + module (n/p) + heatsink (n/p) | 15–60 W (board); module alone 15–40 W | +47 g if the GMSL board is fitted (its power is n/p) |
| VLP-16 | 830 g + cable/box (n/p) | 8 W typical; up to 3.0 A surge at spin-up | on its own 12 V DC-DC; converter loss not included |
| ZED 2i or ZED X | 229 g or 239 g | 1.9 W or 1.46 W | |
| RealSense | 58 g (D405) to 145 g (D457) | 1.48 W (D405) to 3.72 W (D457) | D435i: 75 g, 3.40 W |
| **Total** | **≈ 1.74–2.19 kg of known parts + estimate**, plus the module, heatsink, VLP box and cable, DC-DC and brackets (all n/p) | **≈ 26–74 W steady** | at 6S nominal (22.2 V): ≈ 1.2–3.3 A |

**How the totals are built:**
- **Mass, low end:** 830 + 229 + 58 + 225 + 400 g.
- **Mass, high end:** 830 + 239 + 145 + 225 + 47 + 700 g.
- **Power, low end:** 15 + 8 + 1.46 + 1.48 W.
- **Power, high end:** 60 + 8 + 1.9 + 3.72 W.
- USB camera power is added separately, because it is not known whether the J501's "15–60 W" figure includes it. That makes the estimate conservative.
- Size the VLP-16 rail for a 3 A transient, and the J501 feed for at least 60 W.

**Recommended set (VLP-16 + ZED 2i + D435i):**
- Sensors: 1134 g and about 13.3 W.
- With compute: about 1.76–2.06 kg plus the unpublished items, and about 28–73 W.

## Open questions for the user

1. **Which RealSense?**
   - D435i: best near field, has an IMU.
   - D455: better at 2–6 m.
   - D405: close range only.
   - D457: GMSL, blocked on the J501.
2. **Which ZED?**
   - The ZED 2i works today over USB.
   - The ZED X needs either a Stereolabs answer on a MAX96724 or J501 driver, or a different host.
   - If ZED X, which lens: 2.2 mm (0.3 m min) or 4.6 mm (1.0 m min)?
3. **Is the Seeed GMSL board fitted?** If no GMSL camera is used, leave it out to save 47 g and use the P4 front plate.
4. **Which VLP-16 do you have?** The classic Puck datasheet says 830 g, while Ouster's current page says 590 g. Please weigh the lidar, interface box and cable, and the assembled compute box. The module and heatsink masses are not published.
5. **What is the battery?** At 6S, 7S or 8S the J501 can run directly from the pack, but the VLP-16 needs a 12 V regulator either way. Keep the interface box, or build a custom protected harness?
6. **Do any sensors need IP ratings outdoors?** The D435i and D455 have none. The D456 is the IP65 USB option.
