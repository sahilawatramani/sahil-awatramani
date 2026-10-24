# Validation record

Verified on 24 October 2026 using Python 3.13.12 on Windows. These are observed engineering checks, not organizer scores or calibrated field accuracy. Detector redesign: `41b940e`; output/report improvements: `2912976`; disputed-target location guard: `e08737f`.

| Check | Observed result |
|---|---|
| Regression suite | **43 tests pass**, in the working repository and a clean local clone; `python -m unittest discover -s tests -v` |
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
| Clean checkout reproducibility | Latest code passes 43 tests; `flags.csv`, `report.html`, `evidence.html`, `audit.json` and `manifest.json` reproduce byte for byte |
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

The 44 CSV intervals include 30 separate sunlit windows for one S04 drift hypothesis. The evidence ledger groups those windows without dropping the exact CSV intervals. S07 remains the first visit, S02 the strongest alternative. S04's early holding boundary remains less certain than its later sunny-warming pattern; no historical temperature, rain or wind calibration is invented.

The evaluation JSON preserves the frozen core's hashes. The subsequent disputed-target guard has its own regression; the synthetic evaluation stations have undisputed coordinates, so those scores do not measure that guard's effectiveness. The source pack has no independent calibration labels. Real precision/recall, common faults, faulty majorities, terrain diversity, small shifts and missing transition evidence remain limitations.

The read-only submission check currently passes engineering/schema/manifest/history checks and reports three human requirements outstanding: the real narrated video link, the personal DECISIONS.md including the unaided calculation, and complete genuine chat exports. It does not pretend to verify those requirements or submit the application.
