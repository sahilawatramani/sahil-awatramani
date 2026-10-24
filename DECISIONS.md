# Operational decisions - technical draft for review

These recommendations summarize the implemented evidence. Replace this draft with your own reasoning before submission; the personal reflections and unaided calculation remain yours to complete.

## 1. The one-hour visit

Send the technician to **S07, Riverbend Farm**. Check the replacement anemometer's exact model, output units and logger coefficient before replacing hardware. Compare the configuration with the manufacturer specification; use a suitable reference instrument to verify the result. Record the old/new settings and the true UTC intervention time. Reserve the last part of the hour for confirming live readings and checking that direction remains plausible.

S07's weather-matched wind ratio falls by a factor of about 0.27 and remains low through the final day. That supports a continuing scale problem, but does not establish an exact conversion. Do not multiply historic readings by an assumed factor merely because it resembles a familiar unit conversion.

The runner-up is **S02**, whose pressure changes by about +7.8 hPa against peers after the board change. It needs a calibrated reference at the same height. S07 comes first because a compatibility/configuration check may restore future wind within the hour. If that specification or a reference is unavailable, this ordering should be revisited.

## 2. The least certain call

The exclusion of **S04's sunlit temperatures** is less certain than the clock repair or frozen sensor. The first/last-week sunny temperature residual rises from -0.65 to +2.62 C, while the night residual changes about -0.2 C. That pattern and the exposure-related maintenance note support a sunlight-dependent bias.

Against it: no co-located truth exists; local weather and reference differences affect residuals. Only three of four reference-omission checks detect the pattern; successful fitted onsets range from March 12 to April 2. The full-model March 14 boundary is a cautious holding decision, not a known physical start or proof that repainting caused it. A shielded, co-located reference thermometer compared through a sunny period would be the single most useful observation. A separate first-week sunlight/hour model tested on the second week also supports late sunny warming (+2.925 C), but only finds a strong three-day departure on April 9. This supports the pattern while weakening confidence in the early hinge boundary. Retain nights, avoid a speculative numerical correction, and do not use nights to construct complete daily means or maxima.

## 3. Where AI was wrong - complete personally

Use an actual moment from the complete chat and explain your own checking process. One exact quote from this implementation session is: "The revised checker again detects the supplied pack’s continuing S07 wind problem." Inspection of the generated ledger then showed a false S02 wind exclusion and no S07 flag. A subsequent correction restored S07, rejected the S02 wind claim and was tested against development scenarios. Explain this case in your own words; do not claim checks or actions you did not perform. Include the full source chat export.

## 4. Running unattended at 500 stations

Cache comparable references, precompute robust summaries and version sensor/location history. Group related flags into incidents; route a short queue by current impact, confidence and likely repair. Monitor false alarms against independently reviewed examples, season and hardware type. Drop noisy per-sample notifications and suppress repeated alerts for acknowledged incidents. Keep an audit trail and an explicit abstention when peers or GPS are insufficient. Refuse unattended coordinate replacement, guessed calibration factors, rain redistribution and causal hardware diagnosis.

## 5. By hand - complete without code or AI

Add your own rough UTC solar-time calculation for S04 on 20 March 2025, show a few lines of working, and explain its use here. This answer is deliberately left for you because the brief explicitly requests unaided work.
