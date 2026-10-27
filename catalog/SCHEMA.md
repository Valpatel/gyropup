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
`cf_tube`, `cf_plate`, `sheet_material`, `filament`, `fab_service`, `turret`.

`"preferred": true` marks the default choice the designer starts from. The BOM groups items into **Sensors & compute**
(`compute`, `sensor`) and **Chassis & actuators** (everything else), each with its own subtotal.

## Pictures and alternates

Three more files sit beside the catalogue (they are objects, not item lists, and are not in `index.json`):

- **`images.json`**: a picture of every part on a parts list, by catalogue key (or printed part name):
  `{source_url, image_url, fetched, path, kind}`. `kind` is `mcmaster` or `vendor` (a product photo, kept in
  `references/vendor/thumbs/`, gitignored: not ours to redistribute) or `render` (our CAD, `exports/thumbs/`).
  McMaster entries also keep the product page's delivery line on the day it was read (`availability`).
  Written by `tools/part_images.py`.
- **`alternates.json`**: other places to buy each bought part, by catalogue key: a list of
  `{supplier, part_number, url, price, price_usd_each, pack_qty, stock, drop_in, changes, checked}`. `drop_in` is true
  only when the alternate fits the same seat and does the same job with no CAD change; otherwise `changes` says what
  would change. `price` and `stock` are as the page showed them on `checked`.
- **`sourcing.json`**: what a parts list's plain-text line means (`names`: text or part name -> key, or a list of
  keys when one line buys several products), lines that are part of another (`skip`), where a vendor part's picture
  is taken from when its buy link is not the right page (`image_pages`, `image_urls`), parts that are hard to buy
  (`risk`: `{level: high | medium | cost | fit | missing | check, note, checked}`: hard to buy, single source,
  a much cheaper option, a part that does not fit the design as drawn, parts the list leaves out, a rating to check;
  shown on the progress page), and the bought parts no
  catalogue file has yet (`parts`, in the item shape above plus `key`).

`cad/bom_media.py` `enrich(lines)` adds `thumb` and `alternates` to parts-list lines from these files.
