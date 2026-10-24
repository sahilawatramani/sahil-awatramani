# Validation record

Verified on 24 October 2026 using Python 3.13.12 on Windows. These are observed engineering checks, not organizer scores or calibrated field accuracy. Detector redesign: `41b940e`; output/report improvements: `2912976`; disputed-target location guard: `e08737f`; outage/baseline/reference hardening: `31f21e9`.

| Check | Observed result |
|---|---|
| Regression suite | **49 tests pass**, in the working repository and a clean local clone; `python -m unittest discover -s tests -v` |
| Independent-seed synthetic evaluation | 57 development and 57 evaluation cases; scenario definitions, hashes, metrics and limitations in [BENCHMARKS.md](BENCHMARKS.md) |
| Identifiable severe faults | All 30 abrupt/frozen/shared-minority evaluation cases have 100% sample precision/recall and exact cadence boundaries in the disclosed generator |
| Drift holding cost | All three evaluation drift cases detected; 97.27% sample precision, 100% recall, 154 healthy samples withheld; gradual onset remains uncertain |
| Sensitivity limits | All three +2 hPa faults missed; all three unanchored equal-group cases unresolved with 0% exclusion recall; no false claim of perfect accuracy |
| Healthy controls / collateral loss | 18 evaluation controls retain 311,040 scored healthy samples; no unrelated-channel exclusions in the 57 evaluation scenarios |
| Original counterexamples | Five-day pressure, three-day wind and two-hour temperature incidents now exclude exactly the faulty interval; equal reference groups are unresolved rather than all blamed |
| Separate recovered incidents | Two pressure and two wind episodes preserve the healthy middle period and all data after supported recovery |
| Shared reference quality snapshot | Direct and advanced stage decisions do not depend on inventory iteration order |
| Disputed target coordinates | Geographic peer selection is withheld for a disputed target as well as for a disputed reference; direct physical checks still apply |
| GPS/time parsing | Checksums, inactive/poor fixes, hemisphere signs, fractional seconds and midnight dates covered |
| Supported / ambiguous clock regimes | Supported backward/initial/returning offsets preserve distinct observations; unresolved mappings withhold rather than deduplicate unsupported time |
| Duplicate/cadence contracts | Exact retransmissions retain one copy; conflicts are held; alternate cadence, gaps, missing/empty files and off-grid records covered |
| Pack/schema edge cases | Missing GPS, malformed timestamps, installation-date conflicts and arbitrary IDs covered; an empty eligible period displays N/A |
| Elapsed-time pressure evidence | An outage cannot supply old observations to satisfy the new 12-hour context window |
| Exact CLI / working directory | Quoted paths with spaces work; outputs are written in the invocation directory |
| Clean checkout reproducibility | Latest code passes 49 tests; `flags.csv`, `report.html`, `evidence.html`, `audit.json` and `manifest.json` reproduce byte for byte |
| Cross-checkout source hashing | Source text hashes normalize Git's LF/CRLF differences; input hashes remain hashes of original bytes |
| Renamed / reversed inventory | All 44 station/channel/start/end/issue/action tuples match after mapping renamed station IDs back; maintenance notes do not trigger the detections |
| Output failure handling | Simulated rendering and rename failures preserve the previous generation; readiness check verifies manifest hashes |
| Supplied-pack accounting | 48,314 raw rows - 144 extra copies = 48,170 unique observations; 48,384 expected slots - 214 absent = 48,170 |
| Clock provenance | S06 +21,600 seconds from source CSV line 3411 recovers 2,639 rows, without removing distinct physical observations |
| Input protection | All 18 source-file SHA-256 hashes match the frozen baseline |
| Full baseline interval comparison | 43 of 44 interval/action tuples unchanged; S07 wind hold moves from March 26 17:00 to 16:00 to cover nearby tested reference uncertainty |
| Reference sensitivity | S07 detected in 4/4 omissions, tested openings March 26 16:00-19:50; S04 3/4, March 12-April 2; ranges are not confidence intervals |
| Alternate S04 time-block model | First week trains sunlight/hour residual cells; second-week median absolute error 0.775 C; late sunny change +2.925 C; three-day strong departure first April 9; early hinge onset remains a precaution |
| Climate-summary eligibility | Audit/report distinguish full, repaired, partial, held and review use; retained S04 nights do not support complete daily temperature means/maxima; missing rain is not a complete-period total |
| A4 print check | **One A4 page**, including all footer text, rendered with headless Chrome and visually inspected; no font-size reduction was needed for the final footer fix |
| Evidence browser check | Four SVG charts render; ledger has 15 summaries; S04 filter shows only its two summaries; reset and S07 deep link work; no horizontal overflow at 1200 px |
| Publication audit | No obvious source-pack files in tracked paths or Git history; no repository publication or submission form has been performed |

## Additional raw-data and second-model review

- A separate CSV/NMEA arithmetic implementation checks all 44 intervals and binds its results to the current generation and input hashes; see [PACK_REVIEW.md](PACK_REVIEW.md) and [pack_review.json](pack_review.json). It is not a calibrated field label set.
- Individual S04 sunny residual changes are +2.3, +4.3, +2.75 and +4.2 C; night changes are -0.1, +0.4, -0.2 and -1.3 C. Alternative holding policies retain 67.76-96.54% of temperatures, demonstrating the cost of uncertain onset and biased sample selection.
- The second generator covers storms, cold pools, elevation-dependent pressure response, direction-dependent exposure, 10/20-minute cadence, missing transition data, short initial regimes, partial trailing context and faulty-majority/common-mode faults.
- A paired diagnostic replay exposes 14,886 healthy samples wrongly excluded by the earlier engine. The revised engine reduces this to zero on the same diagnostic observations, while detecting previously missed observed post-gap fault data.
- Thirty-four reserved cases run only after the detector freeze. All 14 identifiable fault cases have exact observed-sample masks; all six healthy controls retain their scored samples; collateral exclusions are zero. Sample recall across **all** reserved cases is only about 31%, because ambiguous/majority/common faults are still unresolved or missed. Both wind-majority cases have no automatic warning. Full counts and source hashes are in BENCHMARKS.md.
- The original 57 evaluation cases were replayed as a regression, preserving their sample metrics. This replay is not presented as a new held-out trial.

The 44 CSV intervals include 30 separate sunlit windows for one S04 drift hypothesis. The evidence ledger groups those windows without dropping the exact CSV intervals. S07 remains the first visit, S02 the strongest alternative. S04's early holding boundary remains less certain than its later sunny-warming pattern; no historical temperature, rain or wind calibration is invented.

The first-stage evaluation JSON preserves the frozen core's hashes; the new challenge JSON separately identifies the hardened engine. The subsequent disputed-target guard has its own regression; the synthetic evaluation stations have undisputed coordinates, so those scores do not measure that guard's effectiveness. The source pack has no independent calibration labels. Real precision/recall, common faults, faulty majorities, terrain diversity, small shifts and missing transition evidence remain limitations.

The read-only submission check currently passes engineering/schema/manifest/history checks and reports three human requirements outstanding: the real narrated video link, the personal DECISIONS.md including the unaided calculation, and complete genuine chat exports. It does not pretend to verify those requirements or submit the application.
