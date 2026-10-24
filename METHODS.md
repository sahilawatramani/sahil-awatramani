# How the decisions are made

## Output contract and timing

`python checker.py PACK` writes `flags.csv` in the invocation directory. Its columns are exactly `station_id,channel,start_utc,end_utc,issue,action,note`. Intervals are inclusive, minute-formatted UTC. For absent data, boundaries are the first and last absent expected samples. For clock-affected records, flag boundaries use **corrected UTC**; the note identifies the source CSV line and correction. This avoids using an ambiguous original logger timestamp as the key to a repair.

`correct` means a reproducible mapping is justified, not that the input has been overwritten. The internal timeline is repaired for comparisons and coverage. `exclude` with a weather channel masks just that channel; `all` masks all seven. `metadata` exclusions restrict spatial interpretation, not all weather measurements. Overlapping masks are unions, so samples are not subtracted twice. A `keep` interval never overrides a more specific exclusion. Healthy intervals are otherwise implicit. Exact retransmissions are removed by source-row identity, not by an all-channel exclusion.

The CLI fails clearly on malformed timestamps or a missing required schema rather than silently losing unaddressable records. Missing or empty station files produce warnings and whole-station exclusion intervals inferred from the common network period and inventory cadence; absent trustworthy GPS produces a warning. An entirely empty pack is an error. Existing output files are overwritten only after analysis succeeds. There is no resampling or imputation.

## GPS and clock repair

NMEA payloads are separated from their logger timestamp at the first comma, and the XOR checksum between `$` and `*` must match. RMC accepts active `A` fixes and rejects invalid/estimated/manual/simulated modes. Coordinates use degrees plus minutes/60 with hemisphere signs and range checks. Fractional seconds and RMC date rollover are retained. GGA needs a real GNSS fix (quality 1, 2, 4 or 5), at least four satellites, finite HDOP in (0, 5], and altitude units M. Its altitude is mean-sea-level height; **GGA alone supplies no date** and is not used to infer one from the possibly wrong logger clock.

Logger-minus-RMC offsets are rounded to minutes to remove the pack's small receipt jitter. A clock regime needs at least three valid RMC fixes spanning two hours, each within three seconds of the rounded offset. Subminute drift is not repaired. Shifts larger than a day are withheld for review. A later regime is mapped to a unique original weather-row transition only when applying the change restores the inventory cadence within the bracket between old/new GPS regimes. The initial regime must have valid GPS evidence within two hours of the initial logger row. Unresolvable transitions withhold the station rather than risk deleting valid overlapping observations. Missing GPS does not prove bad weather, but limits time verification.

For S06, the repaired transition begins at corrected 2025-03-24 16:10, source CSV line 3411, with +21,600 seconds. It recovers 2,639 observations. The first valid shifted RMC is later than the transition; original row order localizes the break. Timestamps that repeat before repair represent distinct physical times, unlike S08's 144 identical retransmissions.

## Location, cadence and completeness

A location comparison requires at least 12 valid RMC fixes spanning a day. A mismatch exceeds both 1 km and ten times median GPS scatter. At least three independent good GGA positions agreeing within 100 m increase confidence. Neither source is blindly declared correct. S05's ~20.5 km discrepancy therefore restricts coordinate-dependent use, and it is omitted as a reference station in spatial checks.

Expected coverage uses the network's earliest/latest supported corrected observations, each station's inventory cadence and installation date. This assumes a common reporting period; a uniformly missing network prefix/suffix cannot be discovered. Missing whole files have nominal slots inferred from that period, with the inferred phase explicitly identified. Observed stations preserve their own cadence phase. Only timestamps on that grid count toward expected-slot coverage; extra off-grid rows cannot raise coverage above 100%. They remain available for review, with an irregular-cadence metadata flag. Records predating installation cause a metadata conflict; an empty eligible period displays N/A rather than a false percentage. Missing nominal slots are flagged in contiguous intervals. Proven retransmissions retain one first copy; unresolved clock data is never deduplicated. Unique out-of-order observations are sortable with source provenance preserved.

## Direct sensor checks

| Check | Evidence required | Decision |
|---|---|---|
| Numeric / sanity | Non-finite or outside broad bounds: temp [-90,60] C; RH [0,100]%; station pressure [300,1100] hPa; wind [0,350] km/h; direction [0,360]; rain >=0; GHI [-5,1600] W/m2 | Exclude; never clip |
| Saturated humidity | At least 12 h continuously >=98%, with >=3 readings >100% or sunny target-minus-peer RH >25 percentage points | Exclude entire episode, including apparently plausible saturation |
| Frozen temperature, RH or pressure | Identical readings for >=12 h and substantial independent peer range (3 C, 15 RH points or 2 hPa); temperature may also use >=24 h persistence plus GHI range >200 | Exclude affected sensor only; do not apply to dry rain, zero nighttime GHI or calm winds |
| Temperature spike | More than 12 C from median of >=4 neighbors, within three cadences or 30 min, whose range is <5 C | Exclude isolated reversal; a sustained front is not this pattern |
| Astronomical night GHI | >30 W/m2 for >=30 min with solar elevation <-6 degrees at interval midpoint, after clock repair | Exclude with medium confidence; twilight noise tolerated |
| Coherent mountain cold | Target >750 m above reference median, colder by >3 C and temperature correlation >0.8 across >=144 paired samples | Explicit keep, subject to other exclusions |

Bounds are broad screening heuristics for a weather network, not universal climatology or instrument specifications. Rain is interval accumulation; there is no cumulative-counter reset test. Direction 360 is accepted as north, and no arithmetic direction averaging is performed. Solar geometry follows NOAA's fractional-year approximation with east-positive longitude and UTC; it is a broad night check, not a precision radiation model.

## Peer evidence and uncertain diagnoses

For each target, select up to four stations within 180 km and 700 m elevation difference, ordered by distance plus elevation difference/50. Require at least two usable simultaneous peers. Locations under dispute cannot act as references. Broad elevation-aware selection and pairwise pressure baseline centering avoid treating normal elevation pressure differences as faults. Peers need not have identical local weather; no spatial-only outlier is enough for a numerical repair. Reference rows already rejected for time or direct sensor problems are omitted.

**Pressure step.** Center each target-peer pressure difference on its robust pack median (at least 144 valid pairs). A residual jump >=2.5 hPa must persist across actual 48-hour before/after windows, each with at least a day's paired observations. Windows are selected by elapsed time, so outages cannot supply stale records to meet the evidence threshold. The shift must exceed 4 hPa and six robust within-window noise scales; at least two individual peer differences must change >3 hPa in the same direction. Exclude from the detected boundary pending calibration. In this pack, S02 shifts about +6.8 hPa by this estimator; that is not proof the correct repair is subtracting exactly 6.8.

**Wind scale.** Use log((target+0.5)/(peer-median+0.5)) where reference wind >=5 km/h. Hourly medians need at least 20 minutes of observations, daily medians >=6 eligible hours, and >=21 eligible days overall. A two-regime median fit with >=7 days each side must reduce absolute loss >=40% and change the ratio by at least a factor of two. Refine the boundary at hourly resolution, then repeat the fit omitting each reference where at least two remain. Hold from the earliest successful tested onset, with the full-model estimate and empirical range recorded. This is a conservative boundary decision, not a confidence interval or exact physical onset. S07 survives 4/4 omissions; fitted boundaries span March 26 17:00-19:00 UTC, and the hold now begins at 17:00. Its full-model ratio factor ~0.27 is not uniquely a unit conversion, so no factory correction is asserted.

**Daylight temperature drift.** Daily target-minus-peer median temperatures are split into GHI >300 and <5 W/m2, each needing >=2 h of data. Need >=28 days, first/last-week sunny shift >=2.5 C, night shift <=1.5 C, and day/residual correlation >=0.65. A robust nonnegative hinge trend is fitted across candidate onset days; slope must be >=0.06 C/day and absolute loss improve >=30%. Exclude individual contiguous GHI >100 windows from the full-model estimated onset, preserving nighttime values. Repeat the fit omitting each reference to expose sensitivity, without treating these runs as independent probability trials. S04 is detected in 3/4 omission checks, with successful fitted starts ranging March 12-April 2. The March 14 full-model boundary remains a cautious hold, not a known physical onset. Alternative weather, siting or peer artifacts remain possible. The model is evidence of a pattern, not a causal paint diagnosis. Wind and temperature fits are staged before their masks are applied, avoiding inventory-order effects within each detector.

**Rain blockage/release.** A zero run >=48 h must be followed by >=5 mm within an hour and a pulse >=5 times the peer median. During the zero run, at least an hour's records must show two wet peers and target temperature >2 C; at least two peers must total >=5 mm. Exclude from the first corroborated missed wet interval through the nonzero release. This bounds evidence, not the physical start of blockage; the problem may begin earlier while dry. Do not distribute the pulse backward or estimate a complete storm total. Local intense rain without preceding missed peer events is retained by this check.

## Technician priority

The report uses an explicit, inspectable triage ordering for problems continuing into the final day: major wind-scale change (10), frozen sensor (9), pressure step or saturated RH (8), probable sunlight drift (7), location verification (3). Clock/duplicate problems already repaired in software do not consume the visit by default. The ordering encodes impact and plausible one-hour repair, not a scientifically measured utility score. It is a coordinator decision that can change with technician skills, spare parts, access or reference instruments.

For this pack S07 outranks S02: a configuration/specification check can recover future wind rapidly, whereas a pressure-board calibration needs a suitable reference. S04 is important but the warming diagnosis and onset are less certain. S03's freeze and S05's RH episode end before the pack ends; they do not outrank a continuing failure merely by accumulating flags.

## Limits and scaling

There is no trusted co-located ground truth. Common-mode faults can pass peer tests, and uncommon local weather can resemble a fault. S01 snow-related rain undercatch is plausible but unquantified, so there is no invented correction. No tests certify calibration, predict faults, reconstruct missing data, or turn partial-period statistics into a season. A single dominant wind regime change and a single temperature-drift onset are modeled; multiple or short episodes may be missed. Fixed thresholds are defensible screening choices, not tuned universal constants. Source schema changes need explicit parser updates. The full dataset's hidden-test performance is unknown.

Spatial reference selections are cached during each run. At 500 stations, persist suitable preaggregated features across runs, version station history/thresholds, track input hashes, group incident windows and alert on current impact rather than every row. Validate using independently labeled examples and monitor alert volume and precision by season, terrain and station hardware. Require human signoff for geographic relocation, recalibration factors, rain redistribution and causal hardware diagnoses.

## Primary references

- [u-blox X20 interface description, NMEA protocol](https://content.u-blox.com/sites/default/files/documents/u-blox-X20-HPG-2.02_InterfaceDescription_UBXDOC-304424225-19967.pdf): fix-status semantics and RMC/GGA field interpretation. The checker does not assume the fictional stations use this receiver.
- [NOAA General Solar Position Calculations](https://gml.noaa.gov/grad/solcalc/solareqns.PDF): fractional-year solar geometry for the broad night check.

The remaining thresholds and operational decisions are stated design choices; neither reference endorses them.
