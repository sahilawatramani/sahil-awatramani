# Three-minute evidence walkthrough

Record your own voice and screen. Use the actual files and explain what you understand; there is no need for slides or editing. Do not claim work or observations you did not make.

| Time | Show | Explain |
|---|---|---|
| 0:00-0:20 | Run the documented command, then open report.html | What the coordinator must decide; why the report preserves healthy channels rather than rejecting entire stations. |
| 0:20-1:20 | Open S06's source weather CSV near lines 3410-3411, its GPS log, and the clock chart in evidence.html | The raw logger moves from 16:00 to 10:10 on March 24 while measurements remain distinct. Trust only checksum-valid active RMC fixes. Adding six hours from source line 3411 restores cadence and preserves 2,639 observations; simply dropping repeated raw timestamps loses valid data. |
| 1:20-2:20 | S04's orange/green residual chart, reference-sensitivity note and temperature flags | Sunny residuals rise while first/last-week night residuals change little. Only 3/4 reference omissions detect it; fitted starts range March 12-April 2. The daylight hold is cautious, not proof of an exact onset or paint mechanism. Nights remain usable; a co-located shielded reference in sunlight would test the diagnosis. |
| 2:20-3:00 | Coordinator report and one or two CSV notes | Why S07's continuing wind scale problem gets the one-hour visit, why S02 is next, and why neither a guessed wind coefficient nor redistributed blocked-gauge rain becomes a correction. |

Before recording, practice finding the relevant source rows and explaining the distinction between raw and corrected UTC. If you cannot explain a threshold or decision yet, review METHODS.md and the relevant function first. Add the actual recording URL to README line three; this file is guidance, not a substitute recording.
