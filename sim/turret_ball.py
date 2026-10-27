"""The ball: Rival-size foam rounds, what is published, what is swept, and how the bench measures the rest.

    .venv/bin/python sim/turret_ball.py        # writes exports/turret/launch/ball.json (sources, ranges, bench plan)

Every number below carries its source and the date it was checked, or is marked `est` with its basis. The launch
(sim/turret_launch.py, sim/turret_launch3d.py), the barrel and flight (sim/turret_flight.py) and the feed
(sim/turret_feed.py, sim/turret_feed_dyn.py) all take their balls from population() here, so one spread runs through
every stage. The unknowns (foam stiffness, restitution, friction on TPU and PETG, wear and water) are swept over wide
ranges; the worst corner of each sweep is what the 70 fps cap is held against, and BENCH_PLAN says how to shrink them.
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'sim'))
import turret_launch as tl  # noqa: E402

OUT = R / 'exports' / 'turret' / 'launch'
CHECKED = '2026-10-27'

# ------------------------------------------------------------------------------------------------ sources (checked 2026-10-27)
SOURCES = {
    'hasbro_patent_size_hardness': {
        'url': 'https://patents.google.com/patent/US10648765B2/en',
        'quote': 'the foam balls 12 may each have a diameter range of about 22.5 to about 23.5 mm; a hardness of about 1.5 to 2.1 Kg or less than 55 Durometer Shore A',
        'used_for': 'diameter spec band; the hardness bracket for the foam stiffness sweep (the deflection at 1.5-2.1 kgf is not stated)'},
    'blasterhub_mass_fps': {
        'url': 'https://blasterhub.com/2017/12/adventure-force-tactical-strike-rounds-review/',
        'quote': 'Rival rounds only averaged 1.83g each ... Adventure Force 1.88g each, with little variation; 100 shots each: Rival 97 fps, AF 95 fps, none below 92 or above 101',
        'used_for': 'Hasbro and Adventure Force mean mass; the 92-101 fps spread of a stock blaster (a launcher + ball spread we compare against)'},
    'worker_cheetah': {
        'url': 'https://outofdarts.com/products/worker-cheetah-rounds-rival-compatible-ammo-100-pack',
        'quote': 'Dimensions: 22.7mm OD; Weight: 1.75g each; Material: EVA Foam; ultra-squishy EVA foam won\'t stall or burn out flywheels',
        'used_for': 'Worker size, mass, material'},
    'dart_zone_powerstrike': {
        'url': 'https://outofdarts.com/products/dart-zone-ballistix-ops-powerstrike-rounds-rival-compatible-ammo-200-pack',
        'quote': 'Featuring a 22.8mm diameter; Weight: 1.85g each; made with medium-density polyurethane foam',
        'used_for': 'Dart Zone / Adventure Force size, mass, material'},
    'eva_foam_modulus': {
        'url': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC10780418/',
        'quote': 'closed-cell EVA: E = 2.77 / 4.27 / 5.37 / 5.48 / 6.98 MPa at 80 / 95 / 106 / 124 / 180 kg/m^3; stress at 10 % strain 0.09-0.29 MPa; strain rate has little influence on the elastic modulus',
        'used_for': 'the small-strain modulus of EVA foam vs density (a Rival ball is ~290 kg/m^3: above this data, so the Hertz-effective modulus is swept, not taken from here)'},
    'pu_foam_ball_cor': {
        'url': 'https://arxiv.org/html/2411.05891',
        'quote': 'for a dry [PU foam] ball, e^2 = 0.55 is nearly constant [at hand-drop speeds]; the coefficient of restitution shows a strong decrease ... in the high-velocity regime',
        'used_for': 'restitution bracket: e = 0.74 at low speed, lower at launch and impact speeds'},
    'eva_sheet_datasheet': {
        'url': 'https://www.koepp.de/de-wAssets/docs/service-center/datenblaetter/zellpolyethylen/K-EV35_schwarz_06.2026_preliminary.pdf',
        'quote': 'closed-cell EVA, 35 kg/m^3: rebound resilience 60 +- 5 % (ISO 4662); water uptake <= 12 % (ISO 7214)',
        'used_for': 'the resilience and water-uptake order of magnitude for EVA foam (sheet, far lighter than a ball)'},
    'eva_friction': {
        'url': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC9571719/',
        'quote': 'Neat EVA: coefficient of friction 1.18 +- 0.03 (dry, vs alumina ball)',
        'used_for': 'the upper end of the ball-on-tyre friction sweep'},
    'hasbro_flywheel_patent': {
        'url': 'https://patents.google.com/patent/US11719504B1/en',
        'quote': 'approximately 30% slippage can be measured between conventional flywheels and dart projectiles; tyres Shore 30A-90A; the tire may be allowed to expand approximately 4 mm in diameter when spinning',
        'used_for': 'slip is real on stock wheels (the friction sweep reaches down to 0.6); a spinning elastomer tyre grows (sim/turret_launch3d.py models the TPU tyre\'s centrifugal growth)'},
    'tpu95_ultimaker': {
        'url': 'https://um-support-files.ultimaker.com/materials/2.85mm/tds/TPU-95A/TDS-TPU95A-V2.01-250915.pdf',
        'quote': 'TPU 95A printed: Young\'s modulus 67 +- 6 MPa (XY), 56 +- 3 (Z); 96 Shore A; 1.22 g/cm^3',
        'used_for': 'the stiff end of the tyre modulus (small-strain, D3039)'},
    'tpu95_bambu': {
        'url': 'https://www.additive-x.com/shop/mpattachments/file/viewonline/id/823/product_id/2584',
        'quote': 'Bambu TPU 95A HF: tensile modulus 9.8 +- 0.7 MPa (XY), 7.4 +- 0.6 (Z), ISO 527',
        'used_for': 'the soft end of the tyre modulus; the tyre growth sweep uses 10-30 MPa (NinjaTek Cheetah 26 MPa, Polymaker PolyFlex 33.6 MPa sit between)'},
    'hyper_hopper_patent': {
        'url': 'https://patents.google.com/patent/US11346624B2/en',
        'quote': 'soft spherical, but tacky, projectiles ... tend to aggregate or bind in the hopper and on the projectile feed track (14.8 mm TPE Hyper rounds, Shore A 3-30, not Rival foam)',
        'used_for': 'why rigid-sphere feed physics must be confirmed on the bench with real balls (tack is not modelled)'},
    'wet_rounds_forum': {
        'url': 'https://www.tapatalk.com/groups/britnerf/rival-apollo-xv-100-t2180.html',
        'quote': 'performance is adversely affected by dirt, debris and moisture so scavenged rounds perform significantly differently to their dry counter-parts',
        'used_for': 'wet/dirty balls are a different population: the damp condition is an estimate until the bench weighs soaked balls'},
}

# ------------------------------------------------------------------------------------------------ what is known, what is swept
BRANDS = {                                  # nominal diameter (mm), mean mass (g), foam, source key
    'hasbro': {'d_mm': 22.9, 'm_g': 1.83, 'foam': 'PU (Hasbro states only "soft foam")', 'src': 'blasterhub_mass_fps',
               'note': 'diameter: the middle of the patent band 22.5-23.5 (hasbro_patent_size_hardness); no measured mean is published'},
    'adventure_force': {'d_mm': 22.8, 'm_g': 1.88, 'foam': 'PU', 'src': 'blasterhub_mass_fps'},
    'worker_cheetah': {'d_mm': 22.7, 'm_g': 1.75, 'foam': 'EVA', 'src': 'worker_cheetah'},
    'dart_zone': {'d_mm': 22.8, 'm_g': 1.85, 'foam': 'PU, medium density', 'src': 'dart_zone_powerstrike'},
}
SPEC_D = (22.5, 23.5)                       # mm, the patent band: anything in it must feed and must stay under the cap
# Within a brand: no published spread. est: diameter SD 0.15 mm, mass SD 0.10 g (5 %), clipped at +-2.5 SD. Basis: "little
# variation" (blasterhub), a customer note that Worker rounds vary in density (worker_cheetah page reviews), and the
# 92-101 fps band over 100 shots of a stock blaster, most of which the launcher itself causes.
SD_D_MM, SD_M_G = 0.15, 0.10
RANGES = {
    # the Hertz-effective foam modulus (MPa): swept log-uniform. Basis: with E = 1 MPa the 25 % crush between the tyres
    # takes 20 N per side (sim/turret_launch.py's law), the same order as the patent's "1.5-2.1 kg" hardness; small-strain
    # EVA data (eva_foam_modulus) extrapolates to ~10 MPa at the ball's density but foam plateaus well below that at the
    # 12-25 % strains of the nip. est band 0.75-3.0 (x4), as in sim/turret_launch.py.
    'E_mpa': (0.75, 3.0),
    # restitution at launch/impact speeds: PU foam ball 0.74 at hand-drop speed, falling with speed (pu_foam_ball_cor);
    # EVA resilience 60 % (eva_sheet_datasheet) -> e ~ 0.77 at pendulum speeds. est band 0.45-0.75.
    'e': (0.45, 0.75),
    # foam on the TPU 95A tyre: solid EVA on a hard counterface reaches 1.18 dry (eva_friction); stock wheels slip ~30 %
    # (hasbro_flywheel_patent). est band 0.6-1.0.
    'mu_tpu': (0.6, 1.0),
    # foam on the PETG barrel and the PA6-CF chute (dry): est 0.4-0.7 (no data; printed plastics are smoother than TPU).
    'mu_plastic': (0.4, 0.7),
    'nu': 0.2,                              # foam Poisson's ratio: est (closed-cell foams 0.1-0.3)
}
CONDITIONS = {
    'new': {'d_scale': 1.0, 'm_scale': 1.0, 'E_scale': 1.0, 'mu_scale': 1.0, 'note': 'out of the pack'},
    'worn': {'d_scale': 0.985, 'm_scale': 1.0, 'E_scale': 0.6, 'mu_scale': 1.1, 'note': 'est: a few hundred shots: 0.3 mm smaller, 40 % softer, fuzzier (grippier); the bench measures it'},
    'damp': {'d_scale': 1.0, 'm_scale': 1.3, 'E_scale': 0.8, 'mu_scale': 0.6, 'note': 'est: picked up off damp grass: +30 % mass, softer, slippery on the tyre (wet_rounds_forum, eva_sheet_datasheet water uptake)'},
}


@dataclass
class BallSpec:
    name: str
    brand: str
    d_mm: float
    m_g: float
    E_mpa: float
    e: float
    mu_tpu: float
    mu_plastic: float
    nu: float = 0.2
    condition: str = 'new'

    @property
    def r_m(self):
        return self.d_mm / 2000

    @property
    def m_kg(self):
        return self.m_g / 1000

    @property
    def area_m2(self):
        return math.pi * self.r_m ** 2

    @property
    def density_kg_m3(self):
        return self.m_kg / (4 / 3 * math.pi * self.r_m ** 3)

    def launch(self) -> tl.Ball:
        """The same ball as sim/turret_launch.py's dataclass (for shot() and launch3d())."""
        return tl.Ball(self.name, self.d_mm, self.m_g, self.E_mpa, self.nu, self.e, self.mu_tpu)


def nominal(brand='hasbro', condition='new') -> BallSpec:
    b = BRANDS[brand]
    c = CONDITIONS[condition]
    return BallSpec(f'{brand}-nominal', brand, b['d_mm'] * c['d_scale'], b['m_g'] * c['m_scale'], 1.2 * c['E_scale'], 0.6,
                    0.8 * c['mu_scale'], 0.55, RANGES['nu'], condition)


def worst_for_cap() -> BallSpec:
    """The fastest ball the launcher can meet: the largest (most crush), lightest, stiffest and grippiest in the bands."""
    return BallSpec('worst-for-cap', 'spec', SPEC_D[1], min(b['m_g'] for b in BRANDS.values()) - 2.5 * SD_M_G, RANGES['E_mpa'][1], RANGES['e'][1],
                    RANGES['mu_tpu'][1], RANGES['mu_plastic'][1])


def population(n=400, seed=1, condition='new', brand='mixed'):
    """n balls: brand means with the est within-brand spread, the unknowns swept over their bands (log-uniform for E)."""
    rng = np.random.default_rng(seed)
    c = CONDITIONS[condition]
    names = list(BRANDS) if brand == 'mixed' else [brand]
    out = []
    for k in range(n):
        br = names[k % len(names)]
        b = BRANDS[br]
        d = float(np.clip(rng.normal(b['d_mm'], SD_D_MM), b['d_mm'] - 2.5 * SD_D_MM, b['d_mm'] + 2.5 * SD_D_MM)) * c['d_scale']
        m = float(np.clip(rng.normal(b['m_g'], SD_M_G), b['m_g'] - 2.5 * SD_M_G, b['m_g'] + 2.5 * SD_M_G)) * c['m_scale']
        E = float(np.exp(rng.uniform(math.log(RANGES['E_mpa'][0]), math.log(RANGES['E_mpa'][1])))) * c['E_scale']
        e = float(rng.uniform(*RANGES['e']))
        mu = float(np.clip(rng.uniform(*RANGES['mu_tpu']) * c['mu_scale'], 0.2, 1.3))
        mup = float(rng.uniform(*RANGES['mu_plastic']))
        out.append(BallSpec(f'{br}-{k}', br, d, m, E, e, mu, mup, RANGES['nu'], condition))
    return out


def energy(spec: BallSpec, v):
    """Kinetic energy (J) and energy density over the ball's cross-section (J/m^2) at speed v (m/s)."""
    ke = 0.5 * spec.m_kg * v ** 2
    return ke, ke / spec.area_m2


# ------------------------------------------------------------------------------------------------ the bench plan
BENCH_PLAN = [
    {'test': 'Size and mass', 'how': '50 balls per brand (Hasbro, Worker, Dart Zone/AF): calipers in two axes, 0.01 g scale; 20 of them again after 300 shots and after 10 min on wet grass',
     'gives': 'd and m means and SDs per brand (replaces SD_D_MM, SD_M_G), the worn and damp scale factors', 'feeds': 'population(), the cap margin'},
    {'test': 'Compression', 'how': 'ball between two flat plates on a kitchen scale with a height gauge: force at 1, 2, 3, 4, 5 mm total squeeze, 10 balls per brand, new and worn',
     'gives': 'the Hertz-effective modulus E (fit F = K d^1.5 with the two-plate R_eff) and the plateau', 'feeds': 'RANGES[E_mpa]; also checks the patent\'s 1.5-2.1 kg hardness'},
    {'test': 'Restitution', 'how': 'drop 10 balls from 1 m and from 2 m onto a tile; phone video at 240 fps; bounce height -> e = sqrt(h1/h0). Then fire at 55 fps into a plate and read the rebound on the same video',
     'gives': 'e at 4.4 and 6.3 m/s, and at 17 m/s', 'feeds': 'RANGES[e] (launch damping, barrel bounces, the knock-down impulse)'},
    {'test': 'Friction on the tyre and the barrel', 'how': 'a printed TPU 95A tile and a PETG tile on a tilting board; a ball under a 20 g and a 100 g weight in a printed cup; the angle it starts to slide; dry, damp, fuzzed',
     'gives': 'mu_tpu and mu_plastic', 'feeds': 'RANGES[mu_tpu], RANGES[mu_plastic]'},
    {'test': 'Chronograph vs wheel speed', 'how': 'the barrel\'s two IR gates 50 mm apart (cad/turret.py barrel()); 20 shots at each of 6, 7, 8, 9, 9.4 and 10.4 krpm set speeds (AM32 telemetry), per brand; then 20 shots at 100 % throttle on the nominal rail and on the rail +4 %',
     'gives': 'fps vs rpm (the launch efficiency eta), the SD per set speed, and the measured hardware ceiling', 'feeds': 'launch.json/launch3d.json: the set speed for 55 fps, the ceiling check (must be <= 70 fps on every brand, every shot)'},
    {'test': 'Tyre growth', 'how': 'strobe or high-speed video of the tyre edge against a scale at 0, 5, 9.4 and 10.4 krpm; or a dial gauge on a stopped wheel vs the chrono shift',
     'gives': 'the TPU tyre\'s radial growth at speed', 'feeds': 'launch3d tyre_E_mpa (the gap at speed)'},
    {'test': 'High-speed video of the nip and the muzzle', 'how': '1000+ fps phone video (or a Chronos) through a window in the cage: contact time, the ball\'s crush, slip (mark the ball), spin at the muzzle (mark the ball), exit angle vs the bore',
     'gives': 'contact time (model: ~4.8 ms), spin, exit angle', 'feeds': 'launch3d hand-over, turret_flight barrel model'},
    {'test': 'Dispersion and drop', 'how': 'paper targets at 2, 4, 6, 8 m, 20 shots each at the 55 fps set speed from a clamped turret; mark the laser dot; measure the group centre (drop, drift) and the 1-sigma radius',
     'gives': 'drop vs range (drag Cd), drift (spin/Magnus), the dispersion budget', 'feeds': 'turret_flight validation (Cd, C_L), the accuracy check at 2/4/6 m'},
    {'test': 'Jam-rate counts', 'how': '300 balls through the feed at each pose (tilt 0 and -25, the robot leaned +-10 deg pitch, +-15 deg roll on a tilting bench), at 3/s and at the maximum rate; count misses, doubles, stalls (the feed servo\'s load reading), reverses; repeat with worn and damp balls and with the 30-ball and 5-ball hopper',
     'gives': 'the feed reliability per pose and condition', 'feeds': 'feed.json / feed_dyn.json checks (model: 0 doubles, misses only by bridging)'},
    {'test': 'Slew and jolt feeding', 'how': 'the turret on the bench stand on a lazy-susan: pan at 90 deg/s with hard starts while feeding at 3/s; then drop the stand 20 mm onto a mat during a feed step', 'gives': 'misfeeds under slew and jolts', 'feeds': 'feed_dyn.json'},
    {'test': 'Knock-down', 'how': 'the printed game target (20 g plate, 4 deg rest lean) and a 150 g plywood plate at 2, 4, 6 m; 10 shots each; count knock-overs', 'gives': 'the knock-down criterion check', 'feeds': 'target.json'},
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pop = population(400)
    nom = nominal()
    w = worst_for_cap()
    res = {'checked': CHECKED, 'sources': SOURCES, 'brands': BRANDS, 'spec_d_mm': SPEC_D, 'within_brand_sd_est': {'d_mm': SD_D_MM, 'm_g': SD_M_G},
           'ranges': RANGES, 'conditions': CONDITIONS,
           'nominal': nom.__dict__, 'worst_for_cap': w.__dict__,
           'nominal_density_kg_m3': round(nom.density_kg_m3), 'nominal_energy': {f'{fps}_fps': [round(x, 4) for x in energy(nom, fps * tl.FPS)] for fps in (55, 65, 70, 90, 100)},
           'population_400': {'d_mm': [round(float(np.min([b.d_mm for b in pop])), 2), round(float(np.max([b.d_mm for b in pop])), 2)],
                              'm_g': [round(float(np.min([b.m_g for b in pop])), 3), round(float(np.max([b.m_g for b in pop])), 3)],
                              'E_mpa': [round(float(np.min([b.E_mpa for b in pop])), 3), round(float(np.max([b.E_mpa for b in pop])), 3)]},
           'bench_plan': BENCH_PLAN,
           'not_published': ['within-brand size and mass spread (no SD, min/max or sample sizes anywhere reachable)', 'any force-deflection, durometer or bounce test of an actual Rival round',
                             'foam friction on TPU, rubber, PETG or nylon', 'mass of a soaked round; velocity vs shot count; temperature effects']}
    (OUT / 'ball.json').write_text(json.dumps(res, indent=1, default=str) + '\n')
    print(json.dumps({k: res[k] for k in ('brands', 'ranges', 'nominal', 'worst_for_cap', 'nominal_energy', 'population_400')}, indent=1, default=str))


if __name__ == '__main__':
    main()
