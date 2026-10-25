Sahil Awatramani
sahil.awatramani.btech2023@sitpune.edu.in
Video: https://drive.google.com/file/d/12FyeNxtcgp1WBgzT2KzrgGsHCSqmywkG/view?usp=sharing
Run: python checker.py "../ridgeline_data_pack (2)"

# Ridgeline network checker

Ridgeline is a dependency-free Python checker for an eight-station weather
network covering six weeks of observations. It supports two operational
decisions:

1. Which measurements and intervals are suitable for a climate summary?
2. Where should one technician spend a one-hour field visit?

The checker favors traceable decisions over false precision. It repairs only
supported timestamp and duplicate problems, excludes affected channels rather
than entire stations where possible, and abstains when peer evidence is
insufficient. It does not invent calibration factors, redistribute missing
rainfall, or replace disputed coordinates automatically.

## Running the checker

Requirements:

- Python 3.10 or newer
- No third-party packages
- No network access or API keys

From this repository, run:

```sh
python checker.py "path/to/data_pack"
```

The argument must be the private data-pack folder containing `stations.csv`,
`data/`, `gps/`, and the maintenance notebook. Paths containing spaces should
be quoted. Outputs are written to the current working directory, and input
files are never modified.

## Generated outputs

| File | Purpose |
|---|---|
| `flags.csv` | Required seven-column incident and decision ledger |
| `report.html` | Printable coordinator report, designed for one A4 page |
| `evidence.html` | Interactive evidence notebook with charts, filters and audit details |
| `audit.json` | Coverage, restrictions, unresolved checks, provenance and visit ranking |
| `manifest.json` | SHA-256 manifest tying the four generated outputs to one generation |

The output process stages a complete generation before publishing it. The
manifest makes mixed outputs from an interrupted run detectable.

## What the checker does

Checks run in this order:

1. Validate station inventory, schemas, timestamps, numeric values and cadence.
2. Validate GPS checksums and fix quality, then use trustworthy RMC evidence to
   identify supported logger-clock regimes.
3. Compare persistent GPS locations with inventory metadata without silently
   choosing which disputed source is correct.
4. Repair supported clock changes before resolving duplicates, preserving
   distinct observations that only appear to share a raw timestamp.
5. Detect invalid values, saturated humidity, frozen sensors, isolated
   temperature reversals, bounded bursts and implausible night-time sunlight.
6. Use nearby, elevation-comparable references for bounded pressure and wind
   incidents, recovery, sunlight-dependent warming and rain blockage/release.
7. Retain coherent high-elevation cold when regional evidence supports it.

Maintenance notes provide context only; they do not define flags or fault
boundaries. No station ID, known fault date or supplied fault magnitude is
hard-coded.

## Supplied-pack result

The supplied pack produces 44 ledger intervals, including 30 sunlit windows
for one probable S04 temperature-drift incident. The input contains 48,314
raw weather rows. After supported S06 clock repair and removal of 144 proven
S08 retransmissions, there are 48,170 unique observations across 48,384
expected slots; 214 slots are absent.

Key decisions:

- **S06:** repair a supported six-hour clock regime on the internal timeline,
  preserving 2,639 observations.
- **S07:** hold the continuing wind-speed issue; it is the first technician
  visit because the sensor model, units and logger coefficient can be checked
  directly.
- **S04:** hold sunlit temperatures cautiously, retain nights, and do not
  apply a numerical correction. The sunny-warming pattern is supported, but
  its onset and physical cause remain uncertain.
- **S02:** hold the pressure change; it is the runner-up visit because it
  requires a calibrated pressure reference.
- **S01:** retain coherent high-elevation cold rather than treating altitude
  differences as a sensor fault.
- **S05:** restrict coordinate-dependent peer use while its inventory/GPS
  discrepancy remains unresolved.
- **S08:** record the outage as missing data and remove only exact repeated
  copies; missing values are not filled.

The detailed reasoning is in [DECISIONS.md](DECISIONS.md). The independent
raw-data review is in [PACK_REVIEW.md](PACK_REVIEW.md), and implementation
thresholds and limitations are in [METHODS.md](METHODS.md).

## Validation

The regression suite contains 49 tests:

```sh
python -m unittest discover -s tests -v
```

Additional disclosed synthetic evaluations are documented in
[BENCHMARKS.md](BENCHMARKS.md). They cover severe identifiable faults,
recovery, bursts, drift, ambiguous references, outages and healthy controls.
They are engineering evidence for the disclosed synthetic cases, not a claim
of field calibration accuracy. Small faults, common-mode failures, faulty
reference majorities, sparse peers and pack-edge events remain limitations.

The repository also contains the complete AI conversation export under
`ai_logs/`, the submission decision record, validation evidence and the
recording link above. The private source data pack and its ZIP archive are not
part of this repository.
