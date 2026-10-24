Sahil Awatramani
sahil.awatramani.btech2023@sitpune.edu.in
Video: TO ADD - three-minute narrated recording
Run: python checker.py "../ridgeline_data_pack (2)"

# Ridgeline network checker

Eight stations, six weeks, and two operational decisions: which measurements can enter the period summary, and where one technician should spend an hour. This checker preserves healthy channels, repairs only supported timestamp/duplicate problems, and leaves uncertain measurements out rather than inventing replacements.

## Run

Python 3.10 or newer. **No packages, API keys, network calls, paid services, or installation step.** From this repository:

```sh
python checker.py "path/to/data_pack"
```

The argument is the folder containing `stations.csv`, `data/`, `gps/`, and the maintenance notebook. Quote paths with spaces. Outputs are written in the **current working directory**, even when the script is elsewhere:

| File | Purpose |
|---|---|
| `flags.csv` | Required incident intervals and decisions; exact prescribed seven-column schema |
| `report.html` | Coordinator's report; self-contained and printable on A4 |
| `evidence.html` | Derived clock/temperature diagnostics, station filter, incident ledger and GPS quality counts |
| `audit.json` | Coverage, confidence, quantitative evidence, input SHA-256 hashes and visit ranking |

Open `report.html` in a browser. Print at A4, 100% scale, with browser headers/footers disabled. All assets are embedded; an internet connection is unnecessary. Existing outputs with these names are replaced on each successful run. Input files are never modified.

On the development machine, `python` is an inaccessible Windows Store alias. The available embedded interpreter also works:

```powershell
& 'C:/Program Files/PostgreSQL/18/pgAdmin 4/python/python.exe' checker.py '../ridgeline_data_pack (2)'
```

This local path is an alternative for this workstation, not a dependency for reviewers.

## Checks, in execution order

1. Validate inventory, weather schema, timestamps, numeric values and logging cadence.
2. Reject malformed, checksum-failed or inactive GPS evidence; compare trustworthy RMC time with logger time, using original row order to resolve clock changes.
3. Compare persistent RMC/GGA location with inventory; withhold disputed spatial metadata without substituting coordinates automatically.
4. Resolve exact retransmissions and conflicting duplicates **after** supported time repair; identify absent intervals without filling them.
5. Detect saturated humidity, invalid values, long frozen readings, isolated temperature reversals and persistent GHI during astronomical night.
6. Use nearby, comparable-elevation references to check pressure steps, persistent wind scale changes, sunlight-dependent warming and rain blockage/release.
7. Explicitly retain coherent high-elevation cold when supported by regional behavior.

No station IDs, fault dates or known fault magnitudes are encoded. Maintenance dates do not trigger flags; derived notebook themes are shown separately as context. [METHODS.md](METHODS.md) explains thresholds, assumptions and limitations.

## Read the supplied-pack result

The checker flags **44 intervals**, including **30 separate sunlit windows for one probable temperature-drift incident**. The count is not a station health score. There are 48,314 raw weather rows, 144 proven extra copies, and 48,170 unique observations after clock repair. Across 48,384 expected time slots, 214 are absent.

Supported repairs recover S06's timing and remove S08 retransmissions. Exclusions affect S02 pressure, S03 temperature, S04 sunlit temperature/rain, S05 humidity and S07 wind speed in the intervals recorded in `flags.csv`. S07's conservative hold begins March 26 17:00 UTC, the earliest boundary found across tested reference choices. S05's location remains disputed. S01's cold is retained.

The first visit is **S07**, with **S02** the runner-up. S07's fault survives 4/4 reference omissions; fitted starts span March 26 17:00-19:00 UTC. Checking model, units and logger coefficient is a practical first task. S04's warming is the least certain diagnosis: 3/4 omissions detect it, with fitted starts from March 12 to April 2. That reference sensitivity is not a confidence interval or proof that repainting caused the problem. These judgments are explained in the report and the technical draft of [DECISIONS.md](DECISIONS.md).

Usable percentages are sample availability after these checks, not certification of accuracy. Climate comparisons need shared valid periods; partial rain totals cannot be treated as complete. No whole-spring climatology can be inferred from six weeks alone.

The supplied pack credits ERA5 reanalysis (Copernicus Climate Change Service), via the Open-Meteo archive API, CC BY 4.0. Its station names and maintenance narratives are fictional. These derived outputs are for this assignment; the source pack is not included.

## Validation

```sh
python -m unittest discover -s tests -v
```

The 33-test suite uses synthetic fixtures only. It covers GPS parsing/status/checksums, midnight and fractional time, supported and ambiguous clock transitions, a return to the original clock regime, exact/conflicting duplicates, cadence changes, healthy night/dry conditions, pressure/wind changes, temperature spikes/freezes/daylight drift, rainfall alternatives, missing GPS/files, empty files, installation-date conflicts, off-grid coverage, stale pressure evidence across outages, reference sensitivity, inventory order, malformed timestamps, and invocation-directory outputs. On a healthy pack, `flags.csv` contains just its header.

## Scope left open

There is no attempt to estimate lost rain, certify snow-gauge catch efficiency, derive an exact anemometer conversion from neighboring stations, or identify the physical cause of warming from a maintenance coincidence. The implementation detects one dominant persistent wind change and one daylight-drift regime per station; multiple episodes or shared network faults may require review. Sparse peers cause abstention rather than false precision. See METHODS.md for details.

Before submission: finish personal reasoning and the unaided calculation in DECISIONS.md, export complete chats to `ai_logs/`, add the real recording link, confirm the invitation deadline, and publish a repository named `sahil-awatramani`. No repository has been published or submission form sent by this implementation.

[VIDEO_GUIDE.md](VIDEO_GUIDE.md) provides a three-minute evidence sequence; [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md) tracks remaining submission work. The observed validation results are in [VALIDATION.md](VALIDATION.md).
