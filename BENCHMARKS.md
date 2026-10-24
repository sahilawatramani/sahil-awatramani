# Synthetic evaluation: results and limits

The first-stage detector was frozen at commit `41b940e` before running its evaluation seeds. Those results are preserved below; the current hardening and second weather model are documented in the final section. After evaluation, output-hash normalization and report layout were improved, and spatial reference use was disabled for targets whose own location is disputed (a separate regression covers this guard). Evaluation stations have undisputed locations, so the guard does not change any scored case. The preserved JSON hashes identify the evaluated core; these scenarios do not validate the new guard. Source hashes in each JSON result identify the detector and benchmark text. There are **57 development and 57 evaluation scenarios**, with disjoint seeds. All are synthetic; both splits use the same disclosed generator and scenario families. These are new random realizations, not an independent field dataset or hidden organizer test.

Run:

```sh
python benchmarks/evaluate.py --split development --output tmp/development.json
python benchmarks/evaluate.py --split evaluation --output tmp/evaluation.json
python benchmarks/review_cases.py --output tmp/review_results.json
```

The baseline review is preserved in [baseline_review.json](benchmarks/baseline_review.json). The redesign results are in [redesign_review.json](benchmarks/redesign_review.json), [development.json](benchmarks/development.json), and [evaluation.json](benchmarks/evaluation.json).

## What is generated and scored

Six stations (four in the ambiguous case), 24 days or 42 for drift, with 10- and 20-minute cadence. Baselines combine coherent fronts/pressure cycles, solar-dependent temperature/radiation, variable wind, fixed site/elevation offsets, autocorrelated local variation and independent measurement noise. Fault injection is separate: pressure offsets, wind multipliers, temperature bursts, frozen readings and sunny drift. Controls include regional fronts, local +8 C warmth, legitimate sustained humidity, calm/dry/night conditions and heterogeneous wind. Two faulty pressure stations in six test contaminated references; two in four test non-identifiability. GPS/duplicate/file handling remains covered by separate regression fixtures rather than being misrepresented as measured field calibration accuracy.

An exclusion is scored against every station's labeled channel samples; precautionary holds of valid samples count as false positives. Other excluded channels count as collateral loss. Precision = TP/(TP+FP); recall = TP/(TP+FN). Healthy-data loss = 1,000 FP/(FP+TN). An event is a contiguous run of labeled bad samples at the station cadence (separate sunlit windows for drift); event recall measures overlap, not an exact boundary. IoU is overlap/union of a true interval and its best overlapping predicted interval. Boundary errors and case-level outcomes are in the JSON. Undefined precision/recall is shown as a dash, never as 100% accuracy.

## Evaluation results

| Scenario | Sample precision | Sample recall | Event recall | Mean event IoU | False exclusions / 1,000 healthy |
|---|---:|---:|---:|---:|---:|
| pressure short | 100.00% | 100.00% | 100.00% | 1.0 | 0.000 |
| pressure recovery | 100.00% | 100.00% | 100.00% | 1.0 | 0.000 |
| pressure persistent | 100.00% | 100.00% | 100.00% | 1.0 | 0.000 |
| wind short | 100.00% | 100.00% | 100.00% | 1.0 | 0.000 |
| wind recovery | 100.00% | 100.00% | 100.00% | 1.0 | 0.000 |
| wind persistent | 100.00% | 100.00% | 100.00% | 1.0 | 0.000 |
| burst short | 100.00% | 100.00% | 100.00% | 1.0 | 0.000 |
| burst long | 100.00% | 100.00% | 100.00% | 1.0 | 0.000 |
| frozen | 100.00% | 100.00% | 100.00% | 1.0 | 0.000 |
| healthy front | - | - | - | - | 0.000 |
| healthy pressure | - | - | - | - | 0.000 |
| healthy wind | - | - | - | - | 0.000 |
| heterogeneous wind | - | - | - | - | 0.000 |
| healthy saturated | - | - | - | - | 0.000 |
| local warm weather | - | - | - | - | 0.000 |
| small pressure | - | 0.00% | 0.00% | 0.0 | 0.000 |
| shared pressure | 100.00% | 100.00% | 100.00% | 1.0 | 0.000 |
| ambiguous pressure | - | 0.00% | 0.00% | 0.0 | 0.000 |
| sunny drift | 97.27% | 100.00% | 100.00% | 0.9796988505747126 | 1.807 |

## Interpret the successes and failures together

- The 30 identifiable abrupt/frozen/shared-minority fault cases reach 100% sample precision and recall in this generator, with exact boundaries at the logger cadence. This clears the proposed 95% precision / 90% event-recall development gate for these particular severe synthetic cases; it does not predict field accuracy.
- All three drift cases are detected. Early precautionary windows cause **154 healthy temperature samples to be withheld** in two cases, so drift precision is lower and its onset is less certain. This cost is retained in the score.
- All three +2 hPa pressure faults are missed. They are below the configured abrupt-jump and sustained-shift thresholds. The system is a severe-fault screen, not a detector of every calibration change.
- All three unanchored 2:2 cases produce unresolved reference outcomes, no numerical correction, and no asserted bad station. Their faulty samples are still counted as false negatives for exclusion recall (0%); appropriate abstention is reported separately, not turned into perfect recall. There are 24 station/boundary unresolved outcomes across these three cases (four stations at the opening and return). All other evaluation cases produce none, giving a reported unresolved-case fraction of 3/57; this is not a probability that a diagnosis is correct.
- All 18 healthy-control cases retain every scored healthy sample. There are no collateral exclusions from other channels in the 57 evaluation scenarios. Zero observed false exclusions in these controls is not proof of zero false-alarm rate in the field.

Three seeds per family are a small sample. Closely related time samples are dependent, so no binomial sample-based confidence interval is claimed. The generator lacks real storm diversity, wind exposure changes, relocation histories, correlated hardware failures and trustworthy field calibration labels. Fault magnitudes/durations are disclosed rather than selected after evaluation. Do not quote a single overall accuracy that is dominated by healthy samples. Weak or common-mode faults, bad majorities, pack-edge events and gaps around transitions remain open risks.

## Second weather model: outages, short baseline and faulty majorities

[challenge.py](benchmarks/challenge.py) constructs weather separately from the first generator: stochastic hourly synoptic states, delayed storm arrivals, altitude-dependent pressure response, nocturnal cold pools, direction-dependent wind exposure, measurement noise and quantized rain. Cadences are 10 and 20 minutes. There are 34 diagnostic cases (seeds 8273/9282) and 34 reserved cases (10301/11412). The identifiable/ambiguous strata were defined in source before diagnostics. The new detector was frozen at `31f21e9` before reserved execution. None of the reserved outcomes were used to tune it.

The earlier engine was replayed from a separate checkout against the **same diagnostic observations**, not against a different generator realization. [challenge_baseline.json](benchmarks/challenge_baseline.json) preserves that replay; [challenge_diagnostic.json](benchmarks/challenge_diagnostic.json) and [challenge_reserved.json](benchmarks/challenge_reserved.json) preserve the revised results and source hashes. The diagnostics exposed three concrete failures: hidden recovery, wrong orientation of a short initial regime, and blaming an unchanged target after reference changes.

```sh
python benchmarks/challenge.py --split diagnostic --output tmp/challenge_diagnostic.json
python benchmarks/challenge.py --split reserved --output tmp/challenge_reserved.json
# Optional before/after replay using an earlier checkout:
python benchmarks/challenge.py --split diagnostic --engine-root path/to/earlier-checkout --output tmp/challenge_baseline.json
```

The changes require independent target temporal evidence, permit short gap-bracketed transitions only when the 75% context gate still passes, and avoid orienting failure/recovery before three days of baseline history. Large coincident pressure jumps are reported as unresolved when there is no independent anchor. An insufficient-context warning itself needs a large low-noise partial shift; missing data alone is not a fault.

| Reserved scenario (two seeds each) | TP | FP | FN | Precision | Recall | Cases with explicit unresolved outcome |
|---|---:|---:|---:|---:|---:|---:|
| healthy pressure storms | 0 | 0 | 0 | - | - | 0/2 |
| healthy wind exposure | 0 | 0 | 0 | - | - | 0/2 |
| healthy temperature coldpool | 0 | 0 | 0 | - | - | 0/2 |
| pressure 12h | 108 | 0 | 0 | 100.00% | 100.00% | 0/2 |
| pressure gap open | 639 | 0 | 0 | 100.00% | 100.00% | 0/2 |
| pressure gap recovery | 639 | 0 | 0 | 100.00% | 100.00% | 0/2 |
| pressure at start | 0 | 0 | 324 | - | 0.00% | 2/2 |
| pressure at end | 0 | 0 | 54 | - | 0.00% | 2/2 |
| pressure faulty majority | 0 | 0 | 2592 | - | 0.00% | 2/2 |
| pressure all common | 0 | 0 | 3888 | - | 0.00% | 2/2 |
| wind 12h | 108 | 0 | 0 | 100.00% | 100.00% | 0/2 |
| wind gap recovery | 639 | 0 | 0 | 100.00% | 100.00% | 0/2 |
| wind at start | 0 | 0 | 324 | - | 0.00% | 2/2 |
| wind at end | 0 | 0 | 54 | - | 0.00% | 2/2 |
| wind faulty majority | 0 | 0 | 2592 | - | 0.00% | 0/2 |
| burst in storm | 18 | 0 | 0 | 100.00% | 100.00% | 0/2 |
| drift with weather | 2262 | 0 | 0 | 100.00% | 100.00% | 0/2 |

On the matched diagnostic cases, healthy samples wrongly held fall from **14,886 to 0**. In the reserved cases, all **14 identifiable fault cases** have exact observed-sample masks, all 6 healthy controls retain their scored samples, and there is no collateral channel loss.

Across **all 34** reserved cases, exclusion precision is 100.00% and sample recall is **30.99%** (4,413 TP, 0 FP, 9,828 FN). The lower overall recall is disclosed: the set deliberately includes many long ambiguous/common faults. It must not be replaced with a claim of universal 100% detection. Twelve edge/shared-pressure cases have explicit unresolved outcomes; both faulty-majority wind cases remain undetected without an automatic warning. An initial faulty regime lasting longer than the minimum baseline can still be misoriented; three days are a policy gate, not a calibration anchor.

Sample scores count observed records; outages do not supply fabricated truth samples. A gap's physical fault boundary remains bracketed even when every observed good/bad sample is correctly retained/held. Event masks are contiguous observed runs, so overlap scores do not establish a precise physical onset across missing data.

The original 57-case evaluation was also replayed as a **regression check**, not a new held-out trial, in [evaluation_hardened.json](benchmarks/evaluation_hardened.json); its sample metrics are unchanged. These two synthetic weather models improve stress coverage, but neither is independent field calibration truth. Common-mode wind faults, an untrusted long initial regime, exposure diversity, small shifts and outages exceeding the context budget remain limitations.
