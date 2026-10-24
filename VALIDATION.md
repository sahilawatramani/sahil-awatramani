# Validation record

Development verification on 24 October 2026, Python 3.13.12 on Windows. This records observed checks, not a claim about the unseen evaluation pack.

| Check | Result |
|---|---|
| Synthetic regression suite | 33 tests pass; `python -m unittest discover -s tests -v` |
| Exact CLI with quoted pack path | Success; outputs generated in invocation directory |
| Clean Git checkout | All 33 tests pass; checker runs independently of the original source directory and reproduces all four committed output files byte for byte |
| Healthy pack, arbitrary station ID/date, optional GPS absent | Header-only flags.csv, explicit GPS warning, successful report |
| Alternate 20-minute cadence and missing intervals | Correct gap count; no assumed 6,048-record requirement |
| Absent/empty weather files | Explicit whole-station exclusion and inferred missing-slot counts |
| Off-grid observations / impossible installation history | Coverage cannot exceed 100%; empty eligible periods display N/A |
| Outage adjacent to pressure step | Old observations outside the actual 48-hour window do not establish a step |
| Unresolved clock ambiguity | No duplicate correction is applied to unsupported timestamps |
| Multiple drift targets | Detector outputs do not depend on inventory order |
| Reference omissions | S07 detected in 4/4 checks, onset 26 March 17:00-19:00; S04 detected in 3/4, onset 12 March-2 April |
| Only two usable peers | Wind evidence explicitly marks omission sensitivity untested rather than claiming unsupported robustness |
| Changed working directory and path containing spaces | Outputs appear in invocation directory, not the input pack |
| Supplied-pack reconciliation | 48,314 raw rows - 144 extra copies = 48,170 unique observations; 48,384 expected slots - 214 missing = 48,170 |
| Renamed every station and reversed inventory order | Identical station/channel/start/end/issue/action tuples after ID mapping |
| Repeated generation | Byte-identical CSV, HTML and JSON outputs; input file hashes unchanged |
| Clock provenance | S06 corrected from CSV line 3411; 2,639 rows recovered without deduplicating distinct observations |
| A4 report | Headless Chrome print verification: one A4 page, including all footnotes; rendered page visually inspected |
| Evidence browser behavior | Both SVG charts render; all-station ledger has 15 summarized rows; S04 filter returns only its two incident summaries; reset works; no horizontal overflow at 1200 px |

The 44 CSV intervals include 30 individual sunlit windows for S04; the evidence ledger groups those as one incident summary. It does not omit the exact intervals from the CSV.

These tests address correctness and some transfer risks; they do not provide measured precision/recall on independently labeled real faults. Peer-supported temperature/rain/wind diagnoses and estimated boundaries retain medium confidence. Known limitations and threshold assumptions are explicit in METHODS.md.
