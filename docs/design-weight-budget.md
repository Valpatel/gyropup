# Robot weight ceiling

The complete-robot product weight ceiling is **100 lb (45.36 kg)**, per the user's 2026-10-28 instruction and decision D72. It includes the operating battery, compute, sensors, turret and loaded consumables. This is the current requirement for product copy and future design budgets.

The current CAD/design baseline is 37.5 kg (about 83 lb). That leaves about 7.86 kg (17.3 lb) below the product ceiling, before a physical weigh-in. It is budget headroom, not measured spare payload capacity.

Existing physics and structural reports retain their actual inputs. In particular, D71 describes 37.5 kg overall, 18.75 kg per leg and a 37.0 kg as-built gate for that configuration. Those historical conditions do not establish passing dynamics or strength at 45.36 kg. Do not replace numeric report inputs, exported masses or sensor/actuator ratings with the new ceiling.

Before manufacturing a configuration above the tested baseline, update its mass ledger and centre of mass, derive its dynamic load cases, and repeat the affected actuator, joint, structure, balance and stopping checks. Any runs that need substantial compute use the project's remote-run workflow. No such physical or structural revalidation is claimed by this documentation update.
