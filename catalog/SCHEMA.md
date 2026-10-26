# Catalog item format

Every file in `catalog/` is a JSON list of items in this shape. Unknown values are `null`, never guessed.

```json
{
  "id": "cubemars-ak70-10",                 // vendor-model, lowercase, dashes
  "category": "leg_actuator",               // see the categories below
  "vendor": "CubeMars",
  "model": "AK70-10",
  "price_usd": 459.0,                        // one unit, before shipping and tax; null if no public price
  "price_note": "official store, single unit",
  "price_checked": "2026-10-25",
  "buy": [{"seller": "CubeMars store", "url": "https://...", "in_stock": true, "ships_from": "CN"}],
  "specs": {                                  // units are in the key names
    "mass_g": 521, "diameter_mm": 104, "length_mm": 53,
    "peak_torque_nm": 24.8, "rated_torque_nm": 8.3,
    "no_load_speed_rpm": 310, "rated_speed_rpm": null,
    "gear_ratio": 10, "voltage_nominal_v": 24, "voltage_range_v": [18, 52],
    "peak_current_a": null, "kt_nm_per_a": null,
    "interface": "CAN", "encoder": "14-bit single, dual for output?",
    "hollow_shaft_mm": null, "ip_rating": null
  },
  "cad": {"step_url": "https://...", "available": true},
  "sources": ["https://datasheet...", "https://product page..."],
  "confidence": "datasheet",                 // datasheet | product page | seller listing | estimate
  "notes": "Anything that matters for a wheel-legged robot."
}
```

Categories: `leg_actuator`, `wheel_motor`, `motor_driver`, `wheel`, `tire`, `battery`, `bms`, `charger`,
`dcdc`, `power_distribution`, `estop`, `can_adapter`, `imu`, `compute`, `sensor`, `display`, `light`, `wiring`, `fastener`, `bearing`,
`cf_tube`, `cf_plate`, `sheet_material`, `filament`, `fab_service`, `turret`, `mechanism`.

`"preferred": true` marks the default choice the designer starts from. The BOM groups items into **Sensors & compute**
(`compute`, `sensor`) and **Chassis & actuators** (everything else), each with its own subtotal.
