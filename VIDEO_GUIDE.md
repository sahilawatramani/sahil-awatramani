# Three-minute evidence walkthrough

Record your own voice and screen. Use the actual files and explain what you understand; there is no need for slides or editing. Do not claim work or observations you did not make.

| Time | Show | Explain |
|---|---|---|
| 0:00-0:15 | Run the documented command, then open report.html | The two decisions: usable climate data and one field hour. Channel-level holds preserve unaffected measurements. |
| 0:15-1:05 | S06's source weather CSV near lines 3410-3411, GPS log and clock chart | The raw logger moves from 16:00 to 10:10 on March 24 while measurements remain distinct. The separate decoder finds 435 shifted active checksum-valid RMC fixes. Adding six hours from source line 3411 restores cadence and preserves 2,639 observations. Deduplicating raw time first would lose data. |
| 1:05-2:05 | S04's orange/green chart, reference-sensitivity note and temperature flags | All four individual comparisons support later sunny warming, but only 3/4 hinge omission fits detect it; starts span March 12-April 2. The March 14 hold is cautious. Retained nights do not provide complete daily means/maxima. A shielded co-located reference in sunlight would resolve more than another fitted onset. |
| 2:05-2:45 | S07 wind chart, coordinator report and field procedure | Why S07's continuing wind issue comes first, what can be checked within the hour, why S02 is next, and why a fitted ~0.27 ratio is not a factory calibration. Explain when a remote fix would change the visit choice. |
| 2:45-3:00 | Validation section / CSV contract | 49 passing tests and two disclosed synthetic weather models; remaining common-mode and baseline limits. Corrections require stronger evidence than an exclusion. |

Before recording, practice finding the relevant source rows and explaining the distinction between raw and corrected UTC. If you cannot explain a threshold or decision yet, review METHODS.md and the relevant function first. Add the actual recording URL to README line three; this file is guidance, not a substitute recording.

[DEFENSE_GUIDE.md](DEFENSE_GUIDE.md) answers likely technical questions. [PACK_REVIEW.md](PACK_REVIEW.md) gives the separately checked arithmetic and S04 holding-policy tradeoff. Use these to understand the evidence rather than reciting a personal work history.
