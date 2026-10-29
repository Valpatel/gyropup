# CAN ESC, position-servo and motor candidates

Checked **2026-10-29** against manufacturer sources. Research for [issue #45](https://github.com/Valpatel/gyropup/issues/45), separate from the playground UI release. No BOM substitution, hardware modification, purchase or physical validation has occurred.

## Architecture to evaluate

The preferred arrangement is **MAD ESCs powered directly by the main battery, with ESCs and position servos sharing a physical CAN bus**. Each device may use its own application protocol; the controller supplies the appropriate driver. Matching the nominal bitrate and validating coexistence matters more than selecting one command vocabulary.

The MAD's stated 16–64 V input covers the project's 10S **30–41 V** battery range. A dedicated flywheel converter is therefore **not required by this ESC's input rating**. This does not automatically qualify the existing motor or other components on that power path.

Baseline references: [D65/D66 and battery selection at c17ce2f](https://github.com/Valpatel/gyropup/blob/c17ce2f/docs/decisions.yaml), and the newer turret/program [wiring](https://github.com/Valpatel/gyropup/blob/14a4127cefa1f67ecbc4d70986beb9b56adceedf/docs/turret-wiring.md) and [physics](https://github.com/Valpatel/gyropup/blob/14a4127cefa1f67ecbc4d70986beb9b56adceedf/docs/turret-physics.md). The latter uses SunnySky X2216 1400 KV motors rated 2–4S, a trimmed 10.8–11.9 V flywheel rail and a separate 12 V auxiliary supply. That rail implements a physical speed ceiling; the direct-battery proposal means reviewing how that intent is retained or revised, rather than treating the old rail as a permanent requirement. The single-pack stand reaches about 15 V near discharge, below MAD's 16 V startup minimum.

## Exact MAD candidate

[AMPX 40A 5–14S boxed ESC](https://store.mad-motor.com/products/ampx-40a-5-14s-esc-hv-waterproof-high-voltage-for-long-range-fright-time-professional-drone-vtol), listed at **$65**, offers DroneCAN and CyphalCAN variants. Availability and shipping were not confirmed. The following values are from its boxed **V2** [specification card](https://cdn.shopify.com/s/files/1/0697/2293/1501/files/AMPX-ESC-40A-_5-14S_-WBOX-V2_01.jpg?v=1763974065) and [dimension/protection card](https://cdn.shopify.com/s/files/1/0697/2293/1501/files/AMPX-ESC-40A-_5-14S_-WBOX-V2_02.jpg?v=1763974065):

| Property | Published value |
| --- | --- |
| Startup input | 16–64 V; marketed as 5–14S |
| Current | 40 A continuous with adequate cooling; 48 A limiting |
| Packaging | About 60 g without wires; 62.2 × 31 × 16 mm stated envelope; IPX4 |
| Auxiliary power | No BEC |
| Inputs | CAN or 3.3/5 V PWM, 50–500 Hz; default PWM endpoints 1050–1940 µs |
| Deceleration | Synchronous freewheeling with energy recovery |
| Lost throttle | Output stops after >2 seconds; previous power resumes when the signal returns |
| Temperature | Protection is described, but the specification's temperature-detection field says unsupported; verify actual telemetry |

The older [V1.0 manual](https://ueeshop.ly200-cdn.com/u_file/UPAZ/UPAZ594/2407/04/file/AMPX40A5-14S.pdf), linked from MAD's heat-sink product page, gives different dimensions, current protection and timeout behavior. Do not combine those values with boxed V2. Confirm the supplied hardware and firmware revision before designing around these behaviors.

### Commands, status and configuration

MAD's [DroneCAN protocol v1.0.2, 2026-02-25](https://ueeshop.ly200-cdn.com/u_file/UPAZ/UPAZ594/2605/07/file/DroneCANProtocol-V102-2026.pdf) describes **classical CAN 2.0B**, 29-bit identifiers, eight-byte frames, default **1 Mbps**, configurable to 250/500/800/1000 kbps. It accepts RawCommand type 1030, throttle 0–8191, up to 500 Hz. Vendor messages 20130/20131 report RPM, current, status, voltage, throttle and temperature fields. NodeStatus and node-information services are present.

Register services configure node/throttle addressing, motor pole pairs, CAN/PWM mode, telemetry and bitrate. Record firmware version: v1.0.2 changed a speed field from electrical frequency to actual RPM. Some table labels/byte offsets remain inconsistent, so validate captured packets. The reviewed tables do **not establish a native RPM-setpoint command or a user-adjustable motor-current ceiling**; throttle plus RPM feedback could support a host speed loop, an integration inference still requiring validation.

The separate [Cyphal protocol](https://ueeshop.ly200-cdn.com/u_file/UPAZ/UPAZ594/2409/20/file/SquareWaveESCCyphalCANCommunicationProtocol-2.pdf) also describes classical CAN, but defaults to 500 kbps and uses different messages/services. Its bitrate is configurable through 1 Mbps. Select and record the ordered firmware variant; neither variant requires all other bus devices to use its protocol.

## Position-servo shortlist

Stall/peak torque is not continuous torque. None of these has been checked against the turret's mounting, load, travel or bearing requirements.

| Candidate | Manufacturer evidence | Integration assessment |
| --- | --- | --- |
| **Hitec MDB951WP-CAN-DroneCAN-28V**, 40951C | [Product](https://www.hiteccs.com/actuators/product-details/MDB951WP-CAN-28V): 8–32 V, 90 g, 40 × 20 × 39 mm, IP67, $254.99. [Target datasheet v2.1](https://www.hiteccs.com/public/uploads/data_sheet/2.MDB951WP-CAN28VTarget-1757113111.pdf): at 12 V, 45 kgf·cm stall, 6.7 A stall, 0.10 s/60°. | Strong compact candidate for 12 V auxiliary power; not direct 41 V. CAN/DroneCAN firmware choice must be explicit. The datasheet is provisional; turn-mode versus continuous-rotation wording needs confirmation for unrestricted pan. |
| **Hitec MD950TW-DroneCAN**, 40950U | [Product](https://www.hiteccs.com/actuators/product-details/MD950TW-DroneCAN): 4–8.4 V, 66.4 g, $214.99. [Datasheet](https://www.hiteccs.com/public/uploads/data_sheet/HRC_MD950TW-DroneCAN_Specsheet-1726255539.pdf): 35 kgf·cm stall and 6.2 A stall at 7.4 V; programmable ±150°. | Genuine DroneCAN position servo, but requires a suitable lower-voltage supply. Continuous rotation is not specified. |
| **MYACTUATOR RMD-X4-P36-36-E** | [Product](https://www.myactuator.com/x4-36details) and [V4 manuals](https://www.myactuator.com/downloads-xseries): 24 V nominal, 20–55 V range, 360 g, 36:1 gearing; custom classical CAN position commands. The September 2026 manual lists 10.5 N·m rated and 34 N·m peak, despite the product name's 36 N·m interpretation. | Supply range covers the main battery, but this is a larger actuator, not an RC-servo drop-in. Confirm torque-spec revision, required load and mechanical fit. |

Hitec's [CAN/DroneCAN protocol rev 2.5](https://www.hiteccs.com/public/uploads/ckeditor/69f10885c7bb61777404037.pdf) supports configurable bitrates including 1 Mbps, with separate node and actuator identifiers, position commands/status, and firmware-dependent parameter/update services. Confirm the delivered firmware, save configuration, and verify it after reboot. Existing STS3215 units are TTL serial bus servos; “bus servo” alone does not imply CAN.

MYACTUATOR's [V4 archive](https://www.myactuator.com/_files/archives/cab28a_3c574913978243a99767646da75afa3c.zip?dn=%28X-V4%29+Protocol+and+manual+of+V4+260920.zip), *CAN BUS Motor Motion Protocol V4.4*, uses 11-bit frames: request `0x140 + ID`, reply `0x240 + ID`, broadcast `0x280`. Default is 1 Mbps; command `0xB4` selects 1M/500k/250k and requires a power cycle. Thus **MAD, Hitec and this custom-CAN actuator have a common 1 Mbps option**.

Other categories should remain distinct: [moteus-n1](https://mjbots.com/products/moteus-n1) is a controller needing a motor/encoder, with a [custom CAN-FD protocol](https://mjbots.github.io/moteus/protocol/can/) using 1 Mbps arbitration and 5 Mbps data by default. [maxon EPOS4](https://support.maxongroup.com/hc/en-us/articles/360015382019-EPOS4-ESCON2-ESCON-What-controller-should-I-select) offers CANopen position control, also as a controller-based integration. Neither is a turnkey DroneCAN RC servo.

## User-proposed threaded-shaft motor

On 2026-10-29 the user proposed [Amazon ASIN B0GJNX17YX](https://www.amazon.com/dp/B0GJNX17YX?th=1), citing easier availability and a threaded shaft. The exact retrieved variant is **Deeahdah PRO 3115-900KV, four motors**. Amazon names Deeahdah as brand/manufacturer; an independent manufacturer site, drawing or manual for this exact part was not found. Other manufacturers' “3115-900KV” specifications must not be substituted: for example, [Techno's TM3115](https://technomotor.cn/En_Pr_d_gci_114_id_220.html) has different dimensions, mass and voltage limits.

| Property | Deeahdah listing claim | Original SunnySky X2216 880 KV baseline |
| --- | --- | --- |
| KV | 900 | 880; the candidate is approximately 2.3% higher, not identical |
| Supply | 4–8S in title/bullets; 24 V in attributes | Manufacturer specifies 2–4S |
| Size | Ø37.1 × 47.8 mm; height datum unspecified | Ø27.7, 32 mm mount-to-bell face, 36.5 mm overall before prop adapter |
| Mass with leads | 120 g | 72 g manufacturer figure; candidate adds about 48 g each / 96 g per pair |
| Shaft/mount | 5 mm shaft; thread and smooth shoulder visible in photos; mounting dimensions absent | 3.175 mm motor shaft; separate bolt-on prop adapter; 16/19 mm M3 mounting cross |
| Current | Attribute says 50 A without duration or test conditions | Manufacturer page conflicts: 20 A/30 s in detailed 880 table, 30 A/30 s in overview; neither is an indefinite thermal rating |

The listing also has inconsistent power fields (1245 versus 2070 W). These are unqualified seller data, not a validated flywheel duty-cycle rating. The dated page confirms the listing exists; the retrieved offer did not establish stock, price or delivery. [SunnySky USA's variant data](https://sunnyskyusa.com/products/sunnysky-x2216.js) returned `available: true` and $24.99 for both 880 Short and 1400 Short on the same date, without a stock count. This does not establish either supplier's sustained availability.

The SunnySky dimensions above come from its [manufacturer drawing](https://www.rcsunnysky.com/Uploads/ueditor/image/20190903/6370311669556908787898053.jpg) and [specifications](https://en.rcsunnysky.com/x-fixedwingseries/1102.html). Its existing adapter already provides an **M5 × 0.8 stud**, 13 mm threaded length, and a Ø5 mm pilot 5.5 mm long. The current [CAD baseline](https://github.com/Valpatel/gyropup/blob/14a4127cefa1f67ecbc4d70986beb9b56adceedf/cad/turret.py#L97) clamps the flywheel against that adapter flange. Deeahdah's integral threaded extension may simplify that arrangement, but its **thread diameter/pitch/handedness, usable thread length, pilot diameter/length, shoulder/flange face, mounting-hole pattern/depth and runout** remain unverified. A photo cannot establish those tolerances. Retention must be checked for both counter-rotating wheels and braking torque; do not infer handedness from intended motor rotation or assume the existing hub fits.

Distinguish design revisions: D42 selected 880 KV, while turret/program D68 selects **1400 KV** in the same SunnySky package. A 900 KV substitution therefore needs a review against the intended current operating point, not merely the old KV. The advertised 8S limit also does not qualify this motor for the full 41 V 10S bus, even though the MAD ESC supports that battery. Motor voltage/thermal qualification remains separate from ESC input compatibility; neither a higher-current motor label nor a duty cap settles it. Keep this as a candidate pending an exact drawing/specification or sample inspection, with no catalog, CAD or inventory substitution yet.

## Shared-bus and power validation still needed

1. **Use classical frames on the proposed shared segment.** Equal arbitration bitrate alone does not make CAN-FD frames acceptable to classical nodes; [Microchip's controller documentation](https://onlinedocs.microchip.com/oxy/GUID-2ACDA668-0A87-46A1-B7FC-9DC74A5461AD-en-US-3/GUID-B3CCEBA7-8270-4685-9C23-8B13FD477A55.html) documents the resulting protocol error. A CAN-FD device needs a verified classical mode or a separate segment/gateway.
2. **Inventory complete identifiers and traffic.** Node IDs belong to each application protocol, not a universal namespace. Check actual 11/29-bit identifiers, broadcasts and receiver filtering; ensure no incompatible producers share an identifier. Measure arbitration latency and bus load with telemetry and configuration traffic. “Same bitrate” is necessary, not a coexistence test result.
3. **Validate wiring.** Use a suitable differential bus with termination at its two ends, controlled stubs and the required reference/isolation arrangement; inspect built-in termination before adding resistors. [Analog Devices AN-1123](https://www.analog.com/en/resources/app-notes/an-1123.html) covers the physical-layer constraints.
4. **Qualify direct battery power independently of CAN.** Review the present motor's 2–4S rating, rotor speed, effective phase voltage, motor/ESC thermal limits and configurable current controls. Revisit the physical speed ceiling and independent ARM/brake behavior rather than assuming software duty limits reproduce them. Recheck every component moved onto battery voltage. Confirm the battery/disconnect path can accept deceleration energy and manage transients, including full-charge and disconnected-source cases. The existing AM32 setup disables regeneration into its buck rail; MAD's advertised behavior differs.

Next step is a hardware-design review of these candidate choices and unresolved specifications, followed by a separately scoped bench plan. No motor spin, CAN coexistence, dimensional fit or electrical validation is claimed by this research.
