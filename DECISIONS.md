# Decisions

## 1. Where I would send the technician

I would have the technician visit **S07, Riverbend Farm**. It shows a wind channel shift by a factor of 0.27 compared to weather-matched sites, and it persists until the end of the reporting period. It is enough to exclude the data from the summary, but not enough to convert 0.27 to a calibration factor.

First of all, I would examine the replacement anemometer’s exact model, output units, wiring and logger coefficient. Then I would compare these parameters with the manufacturer’s specifications, and compare the instrument to a reference instrument installed at the same level and under similar conditions. Then I would write down the old and new instrument settings and exact UTC intervention time. I would save the latter part of the hour for checking live wind speed and direction values.

My alternative choice is **S02**. Its pressure is higher than that of other stations by 7.8 hPa after board replacement; however, pressure needs a calibrated reference instrument at the same level. S07 is my top choice as it allows detecting and fixing a configuration mistake on one visit. Should the specification or a reference instrument be unavailable, I would switch the order.

## 2. The decision I trust least

The most uncertain one is the elimination of the **sunlit temperatures of S04**. The first week-last week sunny residuals of the temperature rises are +2.30, +4.30, +2.75 and +4.20 C against the four individual references, while those for nighttime are rather small. This is a very compelling sunlight-dependant behavior, and the note on exposure-relevant maintenance makes it a good idea to be cautious about this feature.

What I am uncertain about is when it started and what the cause is. No truth thermometer is available at the location. Three out of four omitted reference models have detected the start, but their starting dates vary between 12 March and 2 April. The light-hours model indicates a very clear departure during three days of 9 April. I consider the 14 March date a precautionary policy, but not as evidence of a physical problem nor that repainting was the cause.

The sunny readings will be excluded from the dataset while keeping the nights and using no numerical correction. The nights should not be used to calculate the daily means and maximums since the sample will be changed. The best follow-up for the data is the installation of a sheltered reference thermometer next to the current one during the sunny period. This choice is not without its costs: the policy rejects 1,826 observations while keeping 69.81% of S04 temperatures.

## 3. What I learned from an AI error

While I used AI to aid the creation and analysis of the checker itself, the results were taken as hypotheses and not evidence. One very helpful case where the updated checker seemed to be able to identify the persistent S07 wind condition in the provided pack turned out to have generated a false S02 wind exclusion, and no S07 warning in the ledger. This required that I follow the evidence back to the station comparisons and not accept the comforting summary.

The fix to this situation involved the requirement of the target's temporal change in addition to the references' agreement with each other, as well as the testing of reference omission. This corrected result identifies the S07 condition, denies the S02 wind without any supporting evidence, and identifies S07 for all four possible reference exclusions. Other examples of recovery, short burst, and equal references have been found in the engineering analysis of the checker itself.

This is one simple lesson that I will carry forward – an AI-generated explanation is not a validation result. I must examine the raw evidence, generate counterexamples, and see what issues remain.

## 4. If this had to run unattended at 500 stations

I would not increase the scale of the current eight-station script to 500 stations by just running the same code 500 times. Rather, I would version the station identity and location, sensor history, maintenance history; precompute equivalent-reference graphs and robust time summaries; and process data in batch sizes rather than keeping all objects in memory.

Alerts need to be put into incidents, deduped, ranked by their current impact, confidence, and probable resolution. Duplicate alerts for known incidents need to be filtered out, but every alert needs to include input hashes, version of the algorithm, evidence and a reason for abstaining from taking action. I would keep track of independently verified precision, false positives, missingness and open incidents by seasons, terrains, and hardware type.

The autonomous system can suggest a queue. It must not silently change coordinates, estimate a calibration factor, spread the rain, or attribute the hardware cause to maintenance coincidence. These actions need a person and a physical reference.

## 5. Rough solar-noon check for S04

For S04 (longitude 105.146 degrees West), on 20 March 2025 my manual estimate for solar noon UTC is as follows:

* Longitude correction: 105.146 x 4 minutes = 420.6 minutes.
* Equation-of-time correction around the March equinox is -7 minutes.
* UTC solar noon will be about 720 + 420.6 + 7 = 1,147.6 minutes, which means **19:08 UTC**.

This is a very rough sanity check, not meant to substitute the detector's solar position computation. This estimate informs that the local solar noon takes place later in UTC at S04 site; hence, in order to compare temperatures based on sunlight, it must be based on solar elevation angle instead of UTC hour. This estimate will help me verify whether a reading is a daylight one and cannot be categorized as astronomical night just because of occurring after 19:00 UTC.