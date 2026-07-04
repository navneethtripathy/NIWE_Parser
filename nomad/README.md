# Universal Data Logger Decoder

A modular, plugin-based system for reverse-engineering proprietary wind
data logger binary formats and converting them into structured Excel
files. Built for NIWE's Energy Analytics workflows. The Nomad logger's
`.ndf` binary format has been reverse-engineered and **independently
validated against two real sites** with different sensor configurations:

| Site | Logger Serial | Sensors | Slots/scan | Reference export used |
|---|---|---|---|---|
| somagudda_460 | 8772 | 4 anemometers, 2 vanes, 1 thermistor, 1 pyranometer, 4 internal | 53 | 125-row/40-col 10-min |
| ROJMAL-2 | 9601 | 5 anemometers, 2 vanes, 1 thermistor, 1 barometer, 1 RH sensor, 4 internal | 35 | 144-row/36-col 10-min + 1440-row 1-min |

See `REVERSE_ENGINEERING_REPORT.md` for the complete findings, including
section 10's documentation of what generalized between the two sites and
what didn't (slot-count-per-channel is deployment-specific, not a fixed
Nomad-wide constant — hence the `DeploymentLayout` registry described
below).

## Project structure

```
universal_logger_decoder/
├── decoders/
│   ├── base_decoder.py        # Abstract plugin interface every decoder implements
│   ├── nomad_ndf.py           # Fully reverse-engineered Nomad NDF decoder
│   ├── template_new_decoder.py# Skeleton for adding a new brand
│   └── __init__.py            # Plugin registry + auto-detection
│
├── parsers/
│   ├── metadata_parser.py     # Dataclasses: SensorDefinition, LoggerInfo, LoggerMetadata
│   ├── record_parser.py       # Dataclasses: ChannelSlot, RecordStream (long/wide export helpers)
│   └── timestamp_parser.py    # Uniform time-index reconstruction
│
├── exporters/
│   └── excel_exporter.py      # Long-format, wide-format, and full multi-sheet .xlsx export
│
├── analysis/
│   ├── binary_scanner.py      # Format-agnostic hex dump / string / tag-frequency tools
│   ├── structure_detector.py  # Automatic record-boundary & stride inference
│   └── channel_detector.py    # Heuristics for locating sensor metadata blocks
│
├── tests/
│   └── test_nomad_decoder.py  # Ground-truth validation against the reference export
│
├── outputs/                   # Generated .xlsx files land here by default
├── main.py                    # CLI entry point
├── requirements.txt
├── REVERSE_ENGINEERING_REPORT.md
└── README.md
```

## Quick start

```bash
pip install -r requirements.txt

# Decode a Nomad file (auto-detected) and export to outputs/<name>.xlsx
python3 main.py /path/to/your_logger_file

# Phase-1 only: dump the binary structure without decoding
python3 main.py /path/to/your_logger_file --analyze-only

# Print the decoder's reverse-engineering findings report
python3 main.py /path/to/your_logger_file --findings

# Override start time / interval (needed because Nomad NDF stores no
# embedded per-scan timestamp -- see the findings report, section 7)
python3 main.py /path/to/your_logger_file \
    --start-time "2012-03-13 03:10" --interval-minutes 10 \
    --output outputs/my_site.xlsx
```

## Output

The generated `.xlsx` always has 4 sheets:

| Sheet | Contents |
|---|---|
| `Logger Info` | Site name, logger serial, elevation, etc. |
| `Sensor Metadata` | Every detected sensor: type, model, serial, unit, height, calibration |
| `Data (Wide Format)` | `Timestamp \| WindSpeed_80m \| WindSpeed_78m \| ... \| BatteryVoltage` |
| `Data (Long Format)` | `Timestamp \| Channel Name \| Value \| Unit` (tidy/database style) |

## Adding a new logger format (Campbell, Ammonit, Kintech, Second Wind, ...)

1. Copy `decoders/template_new_decoder.py` to e.g. `decoders/campbell_dat.py`.
2. Reverse-engineer the new format using the tools in `analysis/` —
   `binary_scanner.py` for hex dumps/string search, `structure_detector.py`
   to confirm record boundaries, `channel_detector.py` to locate sensor
   metadata blocks. Follow the same evidence discipline used for Nomad:
   every claim about a field's meaning should be checked against a known
   reference value before being trusted.
3. Implement `sniff()`, `parse_metadata()`, and `parse_records()` per the
   `BaseLoggerDecoder` contract in `decoders/base_decoder.py`.
4. Register an instance of your new class in `decoders/__init__.py`'s
   `DECODER_REGISTRY`.

`main.py`, the exporters, and every existing decoder require **zero**
changes — this was verified with an automated smoke test during
development (a dummy decoder was registered alongside the real Nomad
decoder and auto-detection correctly continued to route the sample file to
the Nomad decoder).

## Validation

`tests/test_nomad_decoder.py` checks the decoder's output against
ground-truth values established during reverse engineering (calibration
certificates, the installation report, and the first row of the
Windographer reference export). Run it with:

```bash
python3 tests/test_nomad_decoder.py
```

## Known limitations (see REVERSE_ENGINEERING_REPORT.md §8-10 for detail)

- Several structural fields remain **INFERRED** rather than **CONFIRMED**
  (two preamble uint32 fields, a per-record "session" field, the
  anemometer "model" field in the Rojmal-2 file reading as the unexplained
  literal text "Maximum #40"). These did not block decoding but are
  flagged honestly rather than presented as certain.
- The decoder selects between **confirmed** `DeploymentLayout`s via a
  fingerprint derived from the channel table. A Nomad file whose sensor
  configuration matches neither confirmed layout falls back to a
  best-effort, clearly-labeled **UNCONFIRMED** layout derived only from
  stub-record counts — `main.py` prints a warning and the Excel output's
  "Logger Info" sheet records the layout name and confirmation status for
  every decode, so this is never silent.
- No per-record timestamp was found in the binary in either confirmed
  file; timestamps are reconstructed from a supplied start time + fixed
  interval, not decoded from file bytes.
- Slot statistic meanings (Avg/SD/Gust/etc.) are confirmed by direct
  cross-validation against reference exports for each `DeploymentLayout`,
  not derived from a universal code table — a stub-record "counter" byte
  was tested as a possible universal statistic-code and found to be
  inconsistent across the two confirmed files, so it is not relied upon
  for that purpose.
