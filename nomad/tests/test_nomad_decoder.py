"""
test_nomad_decoder.py
------------------------
Lightweight validation tests for the Nomad NDF decoder, checking decoded
output against ground-truth values for TWO independently confirmed
deployments:

  1. "somagudda_460" (logger serial 8772) -- 4 anemometers, 2 vanes, 1
     thermistor, 1 pyranometer, 4 internal channels. 53 slots/scan.
  2. "ROJMAL-2" (logger serial 9601) -- 5 anemometers, 2 vanes, 1
     thermistor, 1 barometer, 1 humidity sensor, 4 internal channels.
     35 slots/scan (10 of which are unresolved raw/diagnostic values).

Having two independently-confirmed deployments is what lets us test that
the DeploymentLayout fingerprint-matching machinery in nomad_ndf.py
actually selects the right layout for each file, rather than only ever
exercising one hardcoded table.

Run with:  python3 tests/test_nomad_decoder.py
(No pytest dependency required, to keep this runnable in minimal
environments -- plain asserts with clear messages.)
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from decoders.nomad_ndf import NomadNDFDecoder

SOMAGUDDA_FILE = Path("/mnt/user-data/uploads/data_source")
ROJMAL_FILE = Path("/mnt/user-data/uploads/01-00001.NDF")
ROJMAL_REFERENCE = Path("/mnt/user-data/uploads/ROJMAL-2_10_min_Exported.txt")

TOLERANCE = 0.06  # absolute; reference values are rounded to 1-3 dp in the
                   # export, so e.g. 218.3528 displayed as "218.4" can differ
                   # from the raw decoded value by up to ~0.05


def approx_equal(a: float, b: float, tol: float = TOLERANCE) -> bool:
    return abs(a - b) <= tol


def test_somagudda() -> int:
    if not SOMAGUDDA_FILE.exists():
        print(f"SKIP (somagudda): sample file not present at {SOMAGUDDA_FILE}")
        return 0

    EXPECTED_FIRST_SCAN = {
        "WindSpeed_80m": 0.511,
        "WindSpeed_80m_SD": 0.558,
        "WindSpeed_80m_Gust": 2.928,
        "WindSpeed_78m": 0.321,
        "WindSpeed_50m": 0.239,
        "WindSpeed_20m": 0.270,
        "WindDirection_80m": 218.4,
        "WindDirection_80m_SD": 14.3,
        "WindDirection_50m": 0.9,
        "Temperature_10m": 191.48,
    }

    data = SOMAGUDDA_FILE.read_bytes()
    decoder = NomadNDFDecoder()

    assert decoder.sniff(data), "sniff() failed to recognize the Somagudda file"

    metadata = decoder.parse_metadata(data)
    assert metadata.logger_info.serial_number == "8772"
    assert metadata.logger_info.site_name == "somagudda_460"
    assert abs(metadata.logger_info.elevation_m - 599.0) < 0.01
    assert len(metadata.sensors) == 12, f"expected 12 sensors, got {len(metadata.sensors)}"

    sensor_80m = metadata.sensor_by_index(0)
    assert sensor_80m.height_m == 80.0
    assert sensor_80m.serial_number == "11033"
    assert approx_equal(sensor_80m.calibration_slope, 0.7675, tol=0.001)

    stream = decoder.parse_records(data, metadata)
    assert stream.layout_name == "somagudda_460_serial_8772", \
        f"wrong layout selected: {stream.layout_name}"
    assert stream.layout_confirmed is True
    assert stream.num_scans == 125, f"expected 125 scans, got {stream.num_scans}"

    names = stream.column_names()
    assert len(names) == len(set(names)), "duplicate column names found!"

    name_to_idx = {n: i for i, n in enumerate(names)}
    first_row = stream.values[0]

    failures = []
    for col, expected in EXPECTED_FIRST_SCAN.items():
        idx = name_to_idx.get(col)
        if idx is None:
            failures.append(f"  MISSING COLUMN: {col}")
            continue
        actual = first_row[idx]
        if not approx_equal(actual, expected):
            failures.append(f"  {col}: expected {expected}, got {actual:.4f}")

    if failures:
        print("FAILURES (somagudda):")
        print("\n".join(failures))
        return 1

    print(f"PASS (somagudda): all {len(EXPECTED_FIRST_SCAN)} ground-truth checks matched.")
    print(f"PASS (somagudda): metadata, layout selection, {stream.num_scans} scans, "
          f"{len(names)} unique columns.")
    return 0


def test_rojmal() -> int:
    if not ROJMAL_FILE.exists() or not ROJMAL_REFERENCE.exists():
        print(f"SKIP (rojmal): sample files not present")
        return 0

    data = ROJMAL_FILE.read_bytes()
    decoder = NomadNDFDecoder()

    assert decoder.sniff(data), "sniff() failed to recognize the Rojmal-2 file"

    metadata = decoder.parse_metadata(data)
    assert metadata.logger_info.serial_number == "9601"
    assert metadata.logger_info.site_name == "ROJMAL-2"
    assert len(metadata.sensors) == 14, f"expected 14 sensors, got {len(metadata.sensors)}"

    anem0 = metadata.sensor_by_index(0)
    assert anem0.serial_number == "13077"
    assert approx_equal(anem0.calibration_slope, 0.769, tol=0.001)
    assert approx_equal(anem0.calibration_offset, 0.295, tol=0.001)
    assert anem0.height_m == 80.0

    barometer = metadata.sensor_by_index(21)
    assert approx_equal(barometer.calibration_slope, 100.0, tol=0.01)
    assert approx_equal(barometer.calibration_offset, 590.0, tol=0.01)

    stream = decoder.parse_records(data, metadata, start_time=datetime(2011, 1, 1, 0, 0),
                                    interval_minutes=10)
    assert stream.layout_name == "rojmal_2_serial_9601", f"wrong layout selected: {stream.layout_name}"
    assert stream.layout_confirmed is True
    assert stream.num_scans == 144, f"expected 144 scans, got {stream.num_scans}"

    names = stream.column_names()
    assert len(names) == len(set(names)), "duplicate column names found!"
    name_to_idx = {n: i for i, n in enumerate(names)}

    with open(ROJMAL_REFERENCE, encoding="utf-8") as f:
        lines = f.read().splitlines()
    header = lines[14].split("\t")[1:]
    data_lines = [l for l in lines[15:] if l.strip()]
    ref_rows = [[float(x) for x in l.split("\t")[1:]] for l in data_lines]

    checks = [
        ("WindSpeed_80m_SN13077", "Spd 80m SE [m/s]"),
        ("WindSpeed_80m_SN13082", "Spd 80m NW [m/s]"),
        ("WindSpeed_65m", "Spd 65m SE [m/s]"),
        ("WindSpeed_50m", "Spd 50m SE [m/s]"),
        ("WindSpeed_33.5m", "Spd 33.5m SE [m/s]"),
        ("WindDirection_78m", "Dir 78m SE [\u00b0]"),
        ("WindDirection_48m", "Dir 48m SE [\u00b0]"),
        ("Temperature_5m", "Tmp 5m [\u00b0C]"),
        ("Pressure", "A9-Setra 276 Avg [mbar]"),
        ("Humidity", "A10-Humidity Avg [%]"),
        ("Battery1", "BattV A [V]"),
        ("Battery2", "BattV B [V]"),
        ("12VPower", "BattV C [V]"),
    ]

    failures = []
    for col_name, ref_col in checks:
        ci = name_to_idx.get(col_name)
        if ci is None:
            failures.append(f"  MISSING COLUMN: {col_name}")
            continue
        ri = header.index(ref_col)
        max_diff = max(abs(stream.values[s][ci] - ref_rows[s][ri]) for s in range(len(ref_rows)))
        if max_diff > TOLERANCE:
            failures.append(f"  {col_name} vs {ref_col}: max_diff={max_diff:.4f}")

    # CONFIRMED finding: slots 0-9 are individual 1-minute VectorStdDev
    # sub-samples of wind vane #2 (channel 19), verified against a
    # companion 1-minute Windographer export.
    onemin_ref = Path("/mnt/user-data/uploads/ROJMAL-2_1_min_Exported.txt")
    if onemin_ref.exists():
        with open(onemin_ref, encoding="utf-8") as f:
            onemin_lines = f.read().splitlines()
        onemin_data_lines = [l for l in onemin_lines[15:] if l.strip()]
        onemin_values = [float(l.split("\t")[1]) for l in onemin_data_lines[:10]]
        for i in range(10):
            ci2 = name_to_idx.get(f"WindDirection_48m_VectorStdDev_1min_sample{i + 1}")
            if ci2 is None:
                failures.append(f"  MISSING COLUMN: VectorStdDev_1min_sample{i + 1}")
                continue
            actual = stream.values[0][ci2]
            if not approx_equal(actual, onemin_values[i], tol=0.001):
                failures.append(
                    f"  VectorStdDev_1min_sample{i + 1}: expected {onemin_values[i]}, got {actual:.5f}"
                )

    if failures:
        print("FAILURES (rojmal):")
        print("\n".join(failures))
        return 1

    print(f"PASS (rojmal): all {len(checks)} ground-truth checks matched across "
          f"{len(ref_rows)} scans.")
    print(f"PASS (rojmal): metadata, layout selection, {stream.num_scans} scans, "
          f"{len(names)} unique columns.")
    return 0


def main() -> int:
    result = 0
    result |= test_somagudda()
    print()
    result |= test_rojmal()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
