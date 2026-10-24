# Supplied-pack decision review

A separate [raw-data audit](tools/audit_pack.py) reads CSV and NMEA itself, without importing the checker, production loader or detectors. It uses the submitted source-row time mapping, independently checks that mapping against RMC offsets, reconstructs unique UTC observations and recalculates supporting statistics. [pack_review.json](pack_review.json) records all **44 intervals**, their sample counts, source rows, pairwise evidence and input/output hashes. No original CSV/GPS file is copied into the repository.

```sh
python tools/audit_pack.py "path/to/data_pack" --output pack_review.json
```

This is a separately implemented consistency review of the supplied data, not an external human review or calibrated field truth. Reference checks omit conclusive direct sensor failures, not the uncertain hypothesis being evaluated. Maintenance dates supply context and never define the boundaries.

## Every decision family

| Station / decision | Raw-data check | Judgment and boundary |
|---|---|---|
| S01 / keep mountain cold | All 6,048 observations; temperature -18.7 to +14.1 C; independent correlation 0.9206, median difference -9.65 C, site 1,220 m above reference median | Cold conditions are coherent and elevation-consistent; retain, without inventing a snow-gauge correction. |
| S02 / exclude pressure | Four individual 72-hour paired comparisons change +6.5 to +7.3 hPa; the detector's shorter 12-hour estimate is +7.8 hPa | First changed record March 21 17:20; no observed recovery. Window-dependent magnitude supports exclusion, not an exact subtraction. |
| S03 / exclude four temperature errors | Two 85 C readings violate the broad bound; two -40 C readings are abrupt reversals relative to their immediate context | Four single-sample exclusions, not a lowland climate limit. The -40 C magnitude alone is not the justification. |
| S03 / exclude frozen temperature | 481 consecutive observations, exactly one value (6.5 C), source rows 2486-2966, while surrounding conditions vary | Hold March 18 06:00-March 21 14:00. Other channels remain usable. |
| S04 / precautionary sunlit-temperature hold | All 30 windows contain only GHI >100 W/m2; 1,826 readings withheld. Every individually checked reference supports later sunny warming | Retain the cautious March 14 policy, with medium confidence and explicit onset uncertainty; no numerical correction or causal paint claim. Detailed alternatives below. |
| S04 / exclude uncertain rain accumulation/timing | Zero run lasts 250.17 h before release; 1,120 minutes within the held interval are warm and wet at >=2 references; reference totals 27.6-44.4 mm; release 33.4 mm | Hold only from first corroborated missed wet record March 29 03:10 through April 2 16:30. Earlier dry zeros are not automatically bad. Do not redistribute the release or claim a complete total. |
| S05 / exclude RH episode | 505 readings from 99 to 105%, including 451 above 100% | Hold the complete saturated episode March 7 12:00-March 11 00:00; 54 in-range readings are still inside an untrusted episode. Other weather channels are preserved. |
| S05 / restrict spatial metadata | 982 active checksum-valid RMC positions and 164 good GGA messages agree near 39.75395,-104.89569, about 20.5 km from inventory | RMC/GGA are different messages from the same receiver, not independent field surveys. Neither proves which coordinate source is correct. Retain the mapping/elevation-use restriction and geographic-peer abstention. |
| S06 / correct UTC | Independent decoder finds 552 normal and 435 shifted active RMC fixes, shifted logger-minus-RMC = -21,600 s, receipt jitter <=2 s | Source lines 3411-6049 receive +6 h; 2,639 distinct observations are preserved. Repair before duplicate detection. |
| S07 / exclude wind speed | Four 72-hour pair changes give ratio factors 0.2277-0.3172; combined fit ~0.27; all four reference omissions still detect the change | Hold from the earliest tested March 26 16:00 boundary; nominal opening 19:50 and reference uncertainty remain visible. Configuration/specification comparison is needed for any physical correction. |
| S08 / leave outage missing | 214 absent ten-minute slots, March 16 14:00-March 18 01:30 | Missing values are not zero and cannot produce a complete rainfall total. |
| S08 / remove proven extra copies | Independent canonical reconstruction finds exactly 144 repeated timestamps with all seven identical values | Retain the first copy of each April 5 observation. Do not deduplicate S06's distinct pre-repair overlapping times. |

Accounting reconciles independently: **48,314 raw rows - 144 extra copies = 48,170 unique observations = 48,384 expected slots - 214 absent**. No other conflicting duplicate times occur. All 18 source hashes remain unchanged.

## S04: pattern strength and holding policy are different questions

Changes below compare matched target-minus-individual-reference differences during the first and last seven days, with sunny GHI >300 and night GHI <5 W/m2. They do not fit a fault date.

| Reference | Sunny residual change (C) | Night residual change (C) |
|---|---:|---:|
| S02 | +2.30 | -0.10 |
| S06 | +4.30 | +0.40 |
| S03 | +2.75 | -0.20 |
| S08 | +4.20 | -1.30 |

The late sunny-warming pattern is supported by all four individual comparisons. Onset remains much less secure: only 3/4 hinge fits survive reference omission, and their starts span March 12-April 2. The separate sunlight/hour time-block check has 0.775 C held-out error and first finds a strong sustained departure April 9. That later threshold crossing is not proof the earlier readings are clean.

| Hypothetical holding policy | Sunlit readings withheld | Temperature retained | Available-sample mean (C) |
|---|---:|---:|---:|
| full model (2025-03-14) | 1,826 | 69.81% | 3.953 |
| earliest omission (2025-03-12) | 1,950 | 67.76% | 3.674 |
| latest successful omission (2025-04-02) | 652 | 89.22% | 5.753 |
| strong matched departure (2025-04-09) | 209 | 96.54% | 6.004 |

These means are **selection-sensitivity diagnostics**, not valid complete-period climate estimates. Changing the hold changes the day/night and date mix as well as possibly removing bias. It would be misleading to choose the policy with the most retained samples or to present a mean from predominantly nighttime observations as a complete daily mean.

**Decision:** preserve the explicit precautionary full-model hold until a co-located shielded reference resolves the exposure hypothesis. Use the earlier shared valid period or an explicitly nighttime-only comparison; do not silently relax the hold to raise coverage. This policy can withhold valid readings. Its cost is recorded, rather than disguised as proven fault truth.

## The visit remains conditional

S07 and S02 both have continuing channel restrictions. S07 comes first under the assumption that the sensor model/units/logger configuration can be checked within an hour, with a suitable reference comparison. Request the model/settings photograph remotely first. If that resolves S07, or a pressure reference is available while the wind specification is not, S02 becomes the stronger destination. For wind verification compare simultaneous readings at comparable height and exposure; do not treat the fitted historical ratio as a factory coefficient.

S04 needs a sunny shielded-reference comparison and may need longer co-location. S05's coordinate/identity reconciliation should begin remotely. Ended S03/S05 sensor episodes and software-repaired clock/duplicates do not automatically consume the field hour.
