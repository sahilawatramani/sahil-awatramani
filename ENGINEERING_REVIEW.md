# Engineering assessment and improvement plan

Review date: 24 October 2026. Engine baseline: `dd05bd7`.

## Remediation status

The redesign is implemented; the analysis below preserves the findings that motivated it. See [BENCHMARKS.md](BENCHMARKS.md) for the new evaluation and [VALIDATION.md](VALIDATION.md) for reproducibility checks.

- Pressure and temporary wind incidents now close on supported recovery; bounded temperature bursts are detected.
- Pairwise coherent-group checks avoid blaming every station in an unanchored equal split. Unresolved outcomes are distinct from a CSV keep claim.
- Fifty-seven development scenarios and 57 unused-seed evaluation scenarios quantify per-family detection and data loss. The generator remains a limited synthetic model, not field ground truth. Small +2 hPa faults are deliberately reported as missed.
- A separate matched sunlight/hour time-block model supports S04's later warming but leaves its earlier onset unresolved; precautionary over-exclusion is disclosed and scored.
- Evidence is staged before masks within direct/peer stages; incident recovery/source rows, typed thresholds, climate-use restrictions, timed visit procedures, four diagnostic charts and a generation manifest are implemented.
- Coordinator decisions now foreground usable periods and aggregation restrictions. Remaining scientific limits include faulty majorities, common-mode faults, real terrain diversity, pack-edge/gap events, small shifts and uncertain drift boundaries.

A subsequent raw-data review and second synthetic weather model found additional outage, initial-baseline and faulty-reference problems. Those identified failures are now guarded, with a paired diagnostic replay, 34 reserved cases and six additional regressions. The new model still misses faulty-majority wind cases and cannot provide calibration truth; see BENCHMARKS.md and PACK_REVIEW.md. The preserved baseline assessment below describes the earlier engine.

## Baseline assessment (preserved)

The project has a useful, reproducible baseline and a presentable coordinator report. It does **not yet have enough evidence to claim high detection accuracy or strong unseen-pack performance**. The existing 33 tests verify selected cases and contracts. They are not an independent accuracy benchmark. Earlier clean-checkout and test results remain valid, but should not be read as scientific validation of the flags.

The main improvement should be a focused redesign of event detection, reference handling and evaluation. Preserve the one-command interface, raw-data protection, source-row provenance, correction discipline, and printable report. There is no evidence that adding a dashboard, database, LLM classifier or deep model would improve this assignment.

No organizer scoring rubric, labeled hidden pack or field calibration truth is available. A numeric hiring score or claimed real-world accuracy would be unsupported.

## Independent counterexamples

Run `python benchmarks/review_cases.py --output tmp/review_results.json`.

The saved [baseline results](benchmarks/baseline_review.json) use four synthetic stations, six weeks and ten-minute records. Faults are injected into a simple coherent weather baseline to isolate failure mechanisms. These are deliberately targeted counterexamples, not a representative sample of real weather or an estimate of supplied-pack accuracy. A broader benchmark still needs varied terrain, noise, weather regimes and station counts.

Here precision means correctly excluded faulty samples / all excluded samples, and recall means correctly excluded faulty samples / all injected faulty samples, evaluated for the affected channel across all four stations. Undefined precision is shown as a dash when nothing was excluded.

| Scenario | Precision | Recall | Observed failure |
|---|---:|---:|---|
| Pressure +7 hPa for five days, then recovery | 16.7% | 100% | 720 faulty samples excluded, plus 3,600 healthy samples after recovery |
| Wind scale x0.28 for three days, then recovery | - | 0% | All 432 faulty samples missed |
| Temperature +30 C for two hours, then recovery | - | 0% | All 12 faulty samples missed despite remaining below the broad upper bound |
| Two of four pressure boards shift together | 50% | 100% | Both healthy stations are flagged as well as the faulty pair |
| Real temperature change shared by the region | - | - | No false exclusions in this control; all 24,192 channel samples retained |

The shared-pressure scenario also exposes an identification limit: two internally coherent groups cannot necessarily be assigned correct/incorrect identities without independent evidence. The desired behavior includes an explicit unresolved state and a request for a trusted reference; false certainty about every station is not an acceptable substitute.

## Findings in priority order

### P0: Measure detection performance independently

The current fixtures largely use highly coherent station signals, fixed offsets and strong faults. They do not measure a distribution of error magnitudes, durations, locations in the pack, recovery patterns or false alarms. Renaming IDs demonstrates the absence of ID-specific rules; it does not establish meteorological generalization.

Build a seeded fault-injection benchmark with development and untouched evaluation scenarios. Include healthy controls, small/large additive shifts, scaling faults, isolated and clustered spikes, freezes, gradual drift, short faults, recovery, multiple faults, gaps, clock changes and contaminated references. Generate ordinary weather variation independently of the faults. Vary noise, correlation, cadence, station geometry and available references. Use time blocks for validation and uncertainty analysis because adjacent observations are not independent.

Report per-family sample precision/recall, event recall, interval overlap, onset/recovery error, false exclusions per 1,000 healthy observations, damage to unaffected channels, and abstention rate. Do not emphasize raw accuracy: retaining every sample can score well when faults are rare. Keep benchmark targets separate from unknown organizer scoring.

### P0: Detect bounded incidents and recovery

[Pressure detection](ridgeline/advanced.py#L10) currently creates each exclusion through the final observation, including a later return to baseline. [Wind detection](ridgeline/advanced.py#L53) fits one dominant split with at least seven eligible days on either side; a short middle episode can disappear in the medians.

Represent a fault as an incident with onset, active span, recovery evidence, confidence and current status. Fit multiple stable segments with robust loss and an explicit complexity penalty. Use shorter-window candidates as well as long-regime checks. Confirm a return to the prior peer residual before closing the incident, using duration-based hysteresis to avoid flicker. Never recover by simply assuming that a maintenance visit fixed it.

Acceptance examples: the five-day pressure case should stop excluding after independently supported recovery; the three-day wind case should be detectable when references and signal strength are sufficient. Unknown physical calibration still requires exclusion rather than a guessed correction.

### P0: Catch short error bursts

The [temperature spike check](ridgeline/basic.py#L73) requires neighboring values to have a small range. Consecutive bad readings contaminate those neighbors, so a large short burst can fail the spike rule without meeting the twelve-hour freeze rule.

Add multiscale run/segment candidates with clean windows on both sides, abrupt entry/exit checks, peer-residual support, and channel-specific limits. Test isolated spikes, two-hour bursts and real fronts separately. A Hampel-style residual screen is a useful candidate generator, but a filter alone does not prove that an excursion is faulty. Validate each candidate using independent evidence before excluding it.

### P0: Handle unreliable references and group ambiguity

[Reference selection](ridgeline/peers.py) uses distance and elevation, without a demonstrated reliability model. A minority of stations can dominate a small local reference set. Current pressure corroboration can therefore flag the healthy group as well as the faulty group.

Use robust pairwise residual histories and spatially diverse references. Check whether apparent target faults are actually reference changes. Track coherent groups of changed stations and whether any independent anchor can identify the faulty group. A split network should not be forced into a single confident answer. Preserve the distinction between an observation inconsistency, the identity of a failed sensor, and a climate-use holding decision.

NOAA MADIS explicitly reanalyzes spatial disagreements after removing individual neighbors, marks suspect references, and treats complex terrain in the comparison model. That supports improving reference handling; it does not establish that MADIS thresholds or a full interpolation system should be copied into this eight-station task. [NOAA MADIS surface QC](https://madis.ncep.noaa.gov/madis_sfc_qc_notes.shtml).

### P1: Reassess S04's scope of exclusion

The existing reference-omission results are useful but show substantial uncertainty: three of four detect the pattern, with successful fitted starts from March 12 to April 2. The full-model March 14 cutoff is a policy choice, not a known onset. The warmer sunny residuals support investigation, but the current evidence does not prove every withheld sunlit observation is bad.

Compare alternative residual models that account for stable station differences, solar time, sunlight and weather regime. Evaluate on held-out time blocks. Examine sensitivity to the reference pool and separate the strength of the warming pattern from the location of its onset. Choose and justify a conservative climate-use policy based on the resulting evidence, rather than obtaining an apparently precise start from one hinge fit. Preserve an explicit statement of what a co-located reference would settle.

### P1: Make climate-summary suitability explicit

The report currently foregrounds percentages of samples retained after checks. High retained coverage does not establish suitability for every statistic. S04 nighttime temperatures cannot stand in for a complete daily mean. S08's missing interval prevents claiming a complete period rainfall total. S05's unresolved location restricts spatial interpretation even when individual weather values look plausible.

For each affected channel, give an explicit use decision and any supported comparison period or aggregation restriction. Separate full-period use, repaired use, partial-period use, and a hold pending verification. Keep missingness and sampling bias visible. The Met Office's HadISD description likewise distinguishes automated QC from subsequent climate-use filtering and warns that the data have not automatically been homogenized. [HadISD description](https://hadleyserver.metoffice.gov.uk/hadisd/).

### P1: Strengthen the technician decision

[Visit ranking](ridgeline/report.py#L12) uses fixed numbers per issue type. These are policy preferences, not measured benefit or fault probabilities. A false ongoing incident can consequently drive a false dispatch recommendation. Fix incident recovery before refining ranking.

Compare current fault impact, confidence, achievable one-hour repair, required instruments/spares, and whether a software or remote metadata check can resolve it. Give a timed visit procedure, a verification criterion and a contingency when a reference or specification is missing. Explicitly discuss the strongest alternative and how assumptions would change the ordering. S07 remains defensible on current evidence, but its priority should result from this argument rather than a score of 10 versus 8.

### P1: Separate evidence from decisions in the implementation

[Analysis.add](ridgeline/model.py#L118) immediately changes exclusion masks. Some detectors stage results, while basic checks still mix candidate generation and masking. This makes evidence dependencies harder to inspect and increases the risk of order-dependent behavior as more rules are added.

Keep raw observations immutable; build a canonical time/provenance view; calculate check outcomes against an explicit quality snapshot; and apply a separate decision policy. Introduce typed configuration and evidence records with units, durations, support counts, competing explanations and recovery status. Generate CSV intervals from incident objects. Keep the mandated CSV schema unchanged; put additional provenance in the audit.

Respect the required action meanings: `keep` should describe an investigated oddity supported as real, not serve as a generic unresolved bucket. Internally record insufficient evidence explicitly, then choose a narrowly scoped climate-use hold or omit an unsubstantiated fault claim according to a documented decision policy. Count any withholding of genuinely valid data when measuring data loss.

Stage all output files before replacement and include a consistent generation manifest or hashes so a failed run cannot leave a believable mixture of old/new artifacts. Add small targeted robustness checks for malformed inventory fields, station histories and parser edge cases. Refactor dense helper functions and inline thresholds for readability; a large framework is unnecessary.

### P2: Improve the report's information hierarchy

The A4 layout is polished and reproducible. The dense seven-channel percentage matrix nevertheless spends substantial space repeating 100, leaving small text for the actual decisions. Simplify toward affected channels, usable periods and the action required. Use larger, comfortably printable decision text, with detailed percentages and diagnostics in the evidence notebook. Retain one page where it remains readable; the brief allows a second page if essential.

Use qualitative certainty consistently and explain its basis. Do not convert the omission count into a probability that the diagnosis is correct. Add concise diagnostics for pressure and wind alongside clock and temperature evidence so every important exclusion can be defended from observed data.

## Proposed implementation sequence

1. Freeze this baseline and turn the counterexamples into regression cases; build the broader benchmark and its metrics before tuning rules.
2. Introduce bounded incident segmentation and recovery; fix pressure recovery, temporary wind faults and temperature bursts.
3. Improve reference reliability and explicit handling of ambiguous/shared changes; validate false alarms on ordinary weather and common-mode events.
4. Reevaluate S04 using alternate models and held-out blocks; quantify the sensitivity of retained coverage and summary suitability to the holding policy.
5. Separate evidence generation, adjudication and output; centralize configuration and preserve current provenance/correction guarantees.
6. Regenerate the actual-pack flags and compare every changed interval and action. Revise visit reasoning and the coordinator report from the revised evidence.
7. Run clean-checkout, portability, determinism and print checks after correctness improves; keep personal decision reasoning grounded in the final behavior.

## Proposed acceptance gates

These are initial engineering targets for a labeled benchmark, not organizer criteria or promises of field accuracy. Final targets should reflect error costs and which cases are identifiable from the available evidence.

- No invented time/location/calibration correction and no loss of distinct valid observations in the correction fixtures.
- Correct detection and closure of the unambiguous counterexample incidents; recovery must not erase healthy data through pack end.
- Aim for at least 95% sample precision and 90% incident recall on the predefined, identifiable severe-fault evaluation set, reported separately by fault family and severity; investigate every regression.
- Abrupt clear faults should have onset/recovery errors within one logger interval; gradual or ambiguous faults need honest ranges rather than artificial precision.
- Report healthy-data false-exclusion rates and collateral channel loss; regional storms, night zeros, dry runs, mountain cold and legitimate saturation need explicit controls.
- Score appropriate abstention separately in observationally ambiguous scenarios. Do not conceal withheld valid data by excluding abstentions from the data-loss accounting.
- Publish benchmark scope and its limits; without independent truth, the supplied-pack's real precision/recall remains unknown.

The useful improvement is a stronger chain from observation to evidence to incident to operational decision. A larger feature list or an unsupported accuracy percentage would not establish that chain.
