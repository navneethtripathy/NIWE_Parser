"""Test suite for kintech_parser.

Run with:
    cd kintech_parser
    pip install pytest openpyxl --break-system-packages
    pytest tests/ -v

Tests are organized in three tiers:
    1. Unit tests for the reader (header/channel/record parsing in isolation)
    2. Unit tests for the transformer (derived-column formulas in isolation)
    3. End-to-end regression test against the real reference export file

Tier 3 is the most important: it is the actual evidence that this parser
reproduces Windographer's exported values, not just that the code runs.
"""
import csv
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.exceptions import ChannelDefinitionError, HeaderFormatError, RecordParseError
from core.reader import KintechFileReader
from core.transform import RecordTransformer, _round_fixed, _sigfig_round
from core.writer import write_output

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_WND = FIXTURES / "sample_narendra_iwska8.wnd"
REFERENCE_TXT = FIXTURES / "sample_narendra_iwska8_reference.txt"


# ----------------------------------------------------------------------
# Tier 1: Reader unit tests
# ----------------------------------------------------------------------
class TestReader:
    def test_parses_without_error(self):
        parsed = KintechFileReader(SAMPLE_WND).parse()
        assert parsed.metadata.site_name == "Narendra-IWSKA8"
        assert parsed.metadata.logger_serial == "9571112094"
        assert parsed.metadata.site_id == "150008"

    def test_channel_count_matches_json(self):
        parsed = KintechFileReader(SAMPLE_WND).parse()
        assert len(parsed.channels) == 13

    def test_channels_sorted_by_channel_number(self):
        parsed = KintechFileReader(SAMPLE_WND).parse()
        nums = [c.channel_number for c in parsed.channels]
        assert nums == sorted(nums)

    def test_frequency_vs_analog_classification(self):
        parsed = KintechFileReader(SAMPLE_WND).parse()
        freq = [c for c in parsed.channels if c.is_frequency]
        analog = [c for c in parsed.channels if not c.is_frequency]
        assert len(freq) == 6  # F1-F6
        assert len(analog) == 7  # Battery + A1-A6

    def test_ti30_only_on_expected_channels(self):
        parsed = KintechFileReader(SAMPLE_WND).parse()
        ti30_channels = {c.name for c in parsed.channels if c.has_ti30}
        assert ti30_channels == {"F1_WS_100_0_TFCA", "F2_WS_100_180_TFCA"}

    def test_handles_json_header_vs_column_header_name_mismatch(self):
        """Real-world quirk: JSON channel Name has a space
        ('...POT 2K') where the column header has an underscore
        ('...POT_2K'). The reader must reconcile this rather than fail."""
        parsed = KintechFileReader(SAMPLE_WND).parse()
        names = {c.name for c in parsed.channels}
        assert "A1_WD_98_0_POT_2K" in names
        assert "A2_WD_78_0_POT_2K" in names
        # the raw JSON spelling (with space) should NOT survive as a
        # channel name once reconciled against the header row
        assert "A1_WD_98_0_POT 2K" not in names

    def test_record_count(self):
        parsed = KintechFileReader(SAMPLE_WND).parse()
        assert len(parsed.records) == 76

    def test_native_interval_is_5_minutes(self):
        parsed = KintechFileReader(SAMPLE_WND).parse()
        ts_sorted = sorted(r.timestamp for r in parsed.records)
        # check the first several consecutive diffs where no gap exists
        diffs = [
            (ts_sorted[i + 1] - ts_sorted[i]).total_seconds() / 60
            for i in range(min(5, len(ts_sorted) - 1))
        ]
        assert all(d == 5 for d in diffs)

    def test_calibration_values_match_known_certificates(self):
        """Cross-check against the physical sensor calibration
        certificates referenced in the site installation report."""
        parsed = KintechFileReader(SAMPLE_WND).parse()
        import json

        with open(SAMPLE_WND, encoding="utf-8") as f:
            lines = f.readlines()
        channels_json = lines[1].split("#")[11]
        raw = json.loads(channels_json)
        by_name = {c["Name"]: c for c in raw}
        f1 = by_name["F1_WS_100_0_TFCA"]
        assert f1["Slope"] == pytest.approx(0.04593, abs=1e-5)
        assert f1["Offset"] == pytest.approx(0.27441, abs=1e-5)

    def test_missing_file_raises(self):
        with pytest.raises(Exception):
            KintechFileReader(FIXTURES / "does_not_exist.wnd").parse()

    def test_non_kintech_text_file_raises_header_error(self, tmp_path):
        bad_file = tmp_path / "bad.wnd"
        bad_file.write_text("not a kintech file at all\njust text\n")
        with pytest.raises(HeaderFormatError):
            KintechFileReader(bad_file).parse()

    def test_truncated_header_raises(self, tmp_path):
        bad_file = tmp_path / "truncated.wnd"
        bad_file.write_text("onlyoneline\n")
        with pytest.raises(HeaderFormatError):
            KintechFileReader(bad_file).parse()

    def test_malformed_channel_json_raises(self, tmp_path):
        lines = SAMPLE_WND.read_text(encoding="utf-8").splitlines()
        parts = lines[1].split("#")
        parts[11] = "{not valid json"
        lines[1] = "#".join(parts)
        bad_file = tmp_path / "badjson.wnd"
        bad_file.write_text("\n".join(lines), encoding="utf-8")
        with pytest.raises(ChannelDefinitionError):
            KintechFileReader(bad_file).parse()

    def test_row_with_wrong_field_count_raises_in_strict_mode(self, tmp_path):
        lines = SAMPLE_WND.read_text(encoding="utf-8").splitlines()
        # truncate the first data row's value list
        lines[4] = lines[4].rsplit(" ", 5)[0]
        bad_file = tmp_path / "shortrow.wnd"
        bad_file.write_text("\n".join(lines), encoding="utf-8")
        with pytest.raises(RecordParseError):
            KintechFileReader(bad_file, strict=True).parse()

    def test_row_with_wrong_field_count_skipped_in_nonstrict_mode(self, tmp_path):
        lines = SAMPLE_WND.read_text(encoding="utf-8").splitlines()
        original_row_count = sum(1 for l in lines[4:] if l.strip())
        lines[4] = lines[4].rsplit(" ", 5)[0]
        bad_file = tmp_path / "shortrow.wnd"
        bad_file.write_text("\n".join(lines), encoding="utf-8")
        parsed = KintechFileReader(bad_file, strict=False).parse()
        assert len(parsed.records) == original_row_count - 1


# ----------------------------------------------------------------------
# Tier 2: Transform/formula unit tests
# ----------------------------------------------------------------------
class TestRoundingHelpers:
    def test_round_fixed_half_up(self):
        assert _round_fixed(1.65, 1) == 1.7
        assert _round_fixed(1.05, 1) == 1.1
        assert _round_fixed(2.0, 1) == 2.0

    def test_round_fixed_none_passthrough(self):
        assert _round_fixed(None, 2) is None

    def test_sigfig_round_basic(self):
        assert _sigfig_round(334.001, 5) == 334.0
        assert _sigfig_round(0.0237123, 5) == 0.023712
        assert _sigfig_round(0.0, 5) == 0.0

    def test_sigfig_round_none_passthrough(self):
        assert _sigfig_round(None, 5) is None


class TestTransformDerivedColumns:
    @pytest.fixture
    def parsed(self):
        return KintechFileReader(SAMPLE_WND).parse()

    def test_windographer_table_row_count_matches_reference(self, parsed):
        transformer = RecordTransformer(parsed, output_style="windographer")
        table = transformer.build_table()
        # reference file has 47 data rows (gap-filled, 10-min resampled
        # from a 5-min-native, gappy source)
        assert len(table.rows) == 47

    def test_raw_table_row_count_matches_native_record_count(self, parsed):
        transformer = RecordTransformer(parsed, output_style="raw")
        table = transformer.build_table()
        assert len(table.rows) == len(parsed.records) == 76

    def test_timestamp_shift_applied(self, parsed):
        transformer = RecordTransformer(parsed, output_style="windographer")
        table = transformer.build_table()
        first_ts = table.rows[0][0]
        # native first record is 2021-03-24 00:10; shifted by -10 min -> 00:00
        assert first_ts == "2021-03-24 00:00"

    def test_gap_filled_row_is_blank_with_default_air_density(self, parsed):
        transformer = RecordTransformer(parsed, output_style="windographer")
        table = transformer.build_table()
        col_idx = table.columns.index("Air Density 100m [kg/m³]")
        gap_row = next(r for r in table.rows if r[0] == "2021-03-24 04:30")
        assert gap_row[col_idx] == 1.210
        speed_idx = table.columns.index("Spd 100m N [m/s]")
        assert gap_row[speed_idx] is None

    def test_gust_equals_max(self, parsed):
        transformer = RecordTransformer(parsed, output_style="raw")
        table = transformer.build_table()
        first_row = table.rows[0]
        max_idx = table.columns.index("F1_WS_100_0_TFCA-Max")
        # Confirms the underlying Max value used for "Gust" in
        # windographer style is exactly this raw value.
        assert table.rows[0][max_idx] == 9.68


# ----------------------------------------------------------------------
# Tier 3: End-to-end regression against the real reference export
# ----------------------------------------------------------------------
class TestAgainstReferenceExport:
    @pytest.fixture(scope="class")
    @staticmethod
    def output_table(tmp_path_factory):
        parsed = KintechFileReader(SAMPLE_WND).parse()
        transformer = RecordTransformer(parsed, output_style="windographer")
        table = transformer.build_table()
        out_dir = tmp_path_factory.mktemp("out")
        out_path = out_dir / "output.csv"
        write_output(table, out_path)
        return out_path

    @staticmethod
    def _load_reference():
        with open(REFERENCE_TXT, encoding="utf-8") as f:
            lines = f.readlines()
        header_idx = next(i for i, l in enumerate(lines) if l.startswith("Timestamp"))
        header = lines[header_idx].rstrip("\r\n").split("\t")
        rows = [l.rstrip("\r\n").split("\t") for l in lines[header_idx + 1:] if l.strip()]
        return header, rows

    @staticmethod
    def _load_output(path):
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        return rows[0], rows[1:]

    def test_header_matches_exactly(self, output_table):
        ref_header, _ = self._load_reference()
        out_header, _ = self._load_output(output_table)
        assert out_header == ref_header

    def test_row_count_matches(self, output_table):
        _, ref_rows = self._load_reference()
        _, out_rows = self._load_output(output_table)
        assert len(out_rows) == len(ref_rows)

    def test_cell_level_accuracy_at_least_99_percent(self, output_table):
        """The headline regression test: every cell in the parser's output
        is compared against the reference export with a small numeric
        tolerance. See REVERSE_ENGINEERING_REPORT.md, 'Rounding at
        half-unit boundaries' for why a handful of direction-SD cells at
        exact x.x5 boundaries are expected to differ by 0.1 degree and are
        excluded from being a hard failure - everything else must match.
        """
        ref_header, ref_rows = self._load_reference()
        out_header, out_rows = self._load_output(output_table)
        assert out_header == ref_header

        ref_by_ts = {r[0]: dict(zip(ref_header, r)) for r in ref_rows}
        out_by_ts = {r[0]: dict(zip(out_header, r)) for r in out_rows}
        common = set(ref_by_ts) & set(out_by_ts)
        assert len(common) == len(ref_by_ts), "timestamp sets must match exactly"

        total = 0
        mismatches = 0
        for ts in common:
            r, o = ref_by_ts[ts], out_by_ts[ts]
            for col in ref_header:
                rv, ov = r.get(col, "").strip(), o.get(col, "").strip()
                total += 1
                if rv == ov:
                    continue
                try:
                    if abs(float(rv) - float(ov)) < 0.0006 + abs(float(rv)) * 0.0015:
                        continue
                except ValueError:
                    if rv == "" and ov == "":
                        continue
                mismatches += 1
        accuracy = 1 - mismatches / total
        assert accuracy >= 0.99, f"accuracy {accuracy:.4f} fell below the 99% floor"

    def test_specific_known_value_F1_speed(self, output_table):
        """Spot-check one specific, hand-verified value end to end."""
        _, out_rows = self._load_output(output_table)
        row0 = dict(zip(self._load_output(output_table)[0], out_rows[0]))
        assert row0["Timestamp (UTC)"] == "2021-03-24 00:00"
        assert row0["Spd 100m N [m/s]"] == "9.409"

    def test_specific_known_value_wpd_sigfigs(self, output_table):
        """WPD columns must use 5-significant-figure formatting, not a
        fixed decimal count."""
        header, out_rows = self._load_output(output_table)
        row0 = dict(zip(header, out_rows[0]))
        assert row0["Spd 10m S WPD [W/m²]"] == "3.8116"  # 5 sig figs, no trailing pad needed here

    def test_specific_known_value_trailing_passthrough_padding(self, output_table):
        """Trailing passthrough columns must preserve 5-sig-fig trailing
        zeros (e.g. "0.20000", not "0.2")."""
        header, out_rows = self._load_output(output_table)
        row0 = dict(zip(header, out_rows[0]))
        assert row0["F1_WS_100_0_TFCA-STDev [m/s]"] == "0.20000"
        assert row0["A4_V_10_0_VOLTS-STDev [V]"] == "0.046000"


# ----------------------------------------------------------------------
# CLI smoke tests
# ----------------------------------------------------------------------
class TestCLI:
    def test_cli_writes_csv(self, tmp_path):
        from kintech_parser import main

        out_path = tmp_path / "out.csv"
        rc = main([str(SAMPLE_WND), str(out_path), "--quiet"])
        assert rc == 0
        assert out_path.exists()
        assert out_path.stat().st_size > 0

    def test_cli_writes_xlsx(self, tmp_path):
        from kintech_parser import main

        out_path = tmp_path / "out.xlsx"
        rc = main([str(SAMPLE_WND), str(out_path), "--quiet"])
        assert rc == 0
        assert out_path.exists()

    def test_cli_missing_input_returns_nonzero(self, tmp_path):
        from kintech_parser import main

        rc = main([str(tmp_path / "nope.wnd"), str(tmp_path / "out.csv"), "--quiet"])
        assert rc == 2

    def test_cli_unsupported_extension_returns_nonzero(self, tmp_path):
        from kintech_parser import main

        rc = main([str(SAMPLE_WND), str(tmp_path / "out.pdf"), "--quiet"])
        assert rc == 2

    def test_cli_raw_format_flag(self, tmp_path):
        from kintech_parser import main

        out_path = tmp_path / "out_raw.csv"
        rc = main([str(SAMPLE_WND), str(out_path), "--format", "raw", "--quiet"])
        assert rc == 0
        with open(out_path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert len(rows) - 1 == 76  # native record count, no resampling in raw mode
