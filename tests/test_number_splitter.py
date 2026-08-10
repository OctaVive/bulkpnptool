import io
import unittest
import zipfile

from number_splitter import (
    _collect_delete_items,
    block_display_notation,
    build_splitter_csv_files,
    build_splitter_raw_text,
    build_splitter_zip,
    calculate_bulk_split,
    collect_special_add_blocks,
    convert_range_wildcards_to_lowercase,
    extract_location_id,
    extract_pbx_id,
    format_to_telecom_notation,
    get_special_prefix,
    is_special_location_lookup,
    normalize_number,
    parse_block_string,
    reconstruct_line_with_metadata,
    source_lookup_key,
)
from pe_processor import get_pe_processor


class ParseBlockStringTests(unittest.TestCase):
    def test_wildcard_100_block(self):
        parsed = parse_block_string("08888450xx")
        self.assertTrue(parsed.is_valid)
        self.assertEqual(parsed.start_number, "0888845000")
        self.assertEqual(parsed.size, 100)

    def test_single_number(self):
        parsed = parse_block_string("0888845050")
        self.assertTrue(parsed.is_valid)
        self.assertEqual(parsed.size, 1)

    def test_international_format(self):
        parsed = parse_block_string("+31888845000")
        self.assertTrue(parsed.is_valid)
        self.assertEqual(parsed.start_number, "0888845000")

    def test_metadata_suffix(self):
        line = "08888450xx - PBX: 1234567 - Locatie: Utrecht"
        parsed = parse_block_string(line)
        self.assertTrue(parsed.is_valid)
        self.assertEqual(extract_pbx_id(line), "1234567")
        self.assertEqual(extract_location_id(line), "Utrecht")

    def test_wildcard_100_block_local_format(self):
        parsed = parse_block_string("4556882xx")
        self.assertTrue(parsed.is_valid)
        self.assertEqual(parsed.start_number, "0455688200")
        self.assertEqual(parsed.size, 100)

    def test_wildcard_10_block_local_format(self):
        parsed = parse_block_string("45568820x")
        self.assertTrue(parsed.is_valid)
        self.assertEqual(parsed.size, 10)
        self.assertEqual(parsed.start_number, "0455688200")

    def test_ambiguous_ten_char_local_uses_last_nine_digits(self):
        parsed = parse_block_string("45568820xx")
        self.assertTrue(parsed.is_valid)
        self.assertEqual(parsed.start_number, "0455688200")
        self.assertEqual(parsed.size, 100)

    def test_contained_single_not_in_delete_when_parent_split(self):
        result = calculate_bulk_split(["04556882xx"], ["0455688201"])
        delete_items = [
            format_to_telecom_notation(b.start_number, b.size)
            for b in _collect_delete_items(result)
        ]
        add_items = [
            format_to_telecom_notation(b.start_number, b.size)
            for b in result.resulting_modified_blocks
        ]
        self.assertEqual(delete_items, ["04556882xx"])
        self.assertNotIn("0455688201", delete_items)
        self.assertNotIn("0455688201", add_items)
        self.assertIn("0455688200", add_items)

    def test_wildcard_case_normalization(self):
        self.assertEqual(
            convert_range_wildcards_to_lowercase("08888450XX - PBX: 1"),
            "08888450xx - PBX: 1",
        )

    def test_wildcard_10000_block(self):
        parsed = parse_block_string("088884xxxx")
        self.assertTrue(parsed.is_valid)
        self.assertEqual(parsed.start_number, "0888840000")
        self.assertEqual(parsed.size, 10000)

    def test_wildcard_10000_block_local_format(self):
        parsed = parse_block_string("88884xxxx")
        self.assertTrue(parsed.is_valid)
        self.assertEqual(parsed.start_number, "0888840000")
        self.assertEqual(parsed.size, 10000)

    def test_format_10000_block_notation(self):
        self.assertEqual(
            format_to_telecom_notation("0888840000", 10000),
            "088884xxxx",
        )

    def test_split_10000_block(self):
        result = calculate_bulk_split(["088884xxxx"], ["0888845000"])
        delete_items = [
            format_to_telecom_notation(b.start_number, b.size)
            for b in _collect_delete_items(result)
        ]
        self.assertEqual(delete_items, ["088884xxxx"])
        self.assertNotIn("0888845000", delete_items)


class BulkSplitTests(unittest.TestCase):
    def test_manual_example(self):
        sources = ["08888450xx - PBX: 1234567 - Locatie: Utrecht"]
        removes = ["0888845050"]
        result = calculate_bulk_split(sources, removes)

        retained = [
            format_to_telecom_notation(b.start_number, b.size)
            for b in result.resulting_modified_blocks
        ]
        self.assertEqual(len(retained), 18)
        self.assertIn("088884500x", retained)
        self.assertIn("088884504x", retained)
        self.assertIn("0888845051", retained)
        self.assertIn("0888845059", retained)
        self.assertIn("088884506x", retained)
        self.assertIn("088884509x", retained)

        modified = [
            format_to_telecom_notation(s.start_number, s.size)
            for s in result.modified_sources
        ]
        self.assertEqual(modified, ["08888450xx"])

        delete_items = [
            format_to_telecom_notation(b.start_number, b.size)
            for b in _collect_delete_items(result)
        ]
        self.assertEqual(delete_items, ["08888450xx"])

    def test_raw_text_export_format(self):
        sources = ["08888450xx - PBX: 1234567 - Locatie: Utrecht"]
        removes = ["0888845050"]
        result = calculate_bulk_split(sources, removes)
        text = build_splitter_raw_text(result)

        self.assertIn("To be removed", text)
        self.assertIn("0888845050", text)
        self.assertIn("Step 1 — Add (retained blocks)", text)
        self.assertIn("Step 2 — Delete (parent blocks + removes)", text)
        self.assertIn("08888450xx", text)
        self.assertIn("088884500x", text)

    def test_metadata_inherited_on_retained_blocks(self):
        sources = ["08888450xx - PBX: 1234567 - Locatie: Utrecht"]
        removes = ["0888845050"]
        result = calculate_bulk_split(sources, removes)

        for block in result.resulting_modified_blocks:
            self.assertEqual(block.formatted, block_display_notation(block))
            self.assertNotIn("PBX:", block.formatted)

    def test_plain_blocks_without_metadata(self):
        sources = ["04556882xx"]
        removes = ["0455688250"]
        result = calculate_bulk_split(sources, removes)
        self.assertTrue(result.modified_sources)
        for block in result.resulting_modified_blocks:
            self.assertNotIn("PBX:", block.formatted)
            self.assertTrue(block.formatted.endswith("x") or block.formatted.isdigit())

    def test_no_split_when_no_overlap(self):
        sources = ["08888450xx - PBX: 1234567 - Locatie: Utrecht"]
        removes = ["0612345678"]
        result = calculate_bulk_split(sources, removes)

        self.assertEqual(len(result.modified_sources), 0)
        self.assertEqual(len(result.resulting_modified_blocks), 1)
        self.assertEqual(
            format_to_telecom_notation(
                result.resulting_modified_blocks[0].start_number,
                result.resulting_modified_blocks[0].size,
            ),
            "08888450xx",
        )


class CsvOutputTests(unittest.TestCase):
    def setUp(self):
        self.pe_processor = get_pe_processor()
        self.sources = ["08888450xx - PBX: 1234567 - Locatie: Utrecht"]
        self.removes = ["0888845050"]
        self.result = calculate_bulk_split(self.sources, self.removes)

    def test_location_id_csv_format(self):
        files = build_splitter_csv_files(
            self.result, "location_id", self.pe_processor, default_pbx_id="1234567"
        )
        self.assertIn("add1234567.csv", files)
        self.assertIn("del1234567.csv", files)

        add_lines = files["add1234567.csv"].splitlines()
        self.assertTrue(add_lines[0].endswith(";Utrecht;1234567"))
        self.assertIn(";addPNP;", add_lines[0])

        del_lines = files["del1234567.csv"].splitlines()
        operations = {line.split(";")[1] for line in del_lines}
        self.assertEqual(operations, {"deletePNP"})

    def test_pe_code_csv_format(self):
        files = build_splitter_csv_files(
            self.result, "pe_code", self.pe_processor, default_pbx_id="1234567"
        )
        self.assertIn("add1234567.csv", files)

        add_line = files["add1234567.csv"].splitlines()[0]
        parts = add_line.split(";")
        self.assertEqual(parts[1], "addPNP")
        self.assertEqual(parts[4], "1234567")
        self.assertTrue(parts[3])

        del_line = files["del1234567.csv"].splitlines()[0]
        del_parts = del_line.split(";")
        self.assertEqual(del_parts[1], "deletePNP")
        self.assertEqual(del_parts[3], "00")

    def test_zip_contains_add_and_del_files(self):
        zip_data, filename = build_splitter_zip(
            self.result, "pe_code", self.pe_processor, default_pbx_id="1234567"
        )
        self.assertEqual(filename, "add1234567_del1234567.zip")
        with zipfile.ZipFile(io.BytesIO(zip_data), "r") as archive:
            names = set(archive.namelist())
        self.assertIn("add1234567.csv", names)
        self.assertIn("del1234567.csv", names)

    def test_delete_deduplication(self):
        delete_items = _collect_delete_items(self.result)
        keys = {(b.start_number, b.size) for b in delete_items}
        self.assertEqual(len(keys), len(delete_items))

    def test_plain_block_csv_uses_default_pbx(self):
        result = calculate_bulk_split(["04556882xx"], ["0455688250"])
        files = build_splitter_csv_files(
            result, "pe_code", self.pe_processor, default_pbx_id="9999999"
        )
        self.assertIn("add9999999.csv", files)
        self.assertIn("del9999999.csv", files)

    def test_special_prefix_requires_pe_override(self):
        result = calculate_bulk_split(["05012345xx"], ["0501234501"])
        special = collect_special_add_blocks(result)
        self.assertTrue(special)
        self.assertEqual(special[0].prefix, "050")

        files = build_splitter_csv_files(
            result, "pe_code", self.pe_processor, default_pbx_id="1234567"
        )
        self.assertNotIn("add1234567.csv", files)

    def test_special_prefix_uses_pe_override(self):
        result = calculate_bulk_split(["05241234xx"], ["0524123401"])
        source = result.modified_sources[0]
        key = source_lookup_key(source.start_number, source.size)
        self.assertEqual(get_special_prefix("0524123400"), "0524")

        files = build_splitter_csv_files(
            result,
            "pe_code",
            self.pe_processor,
            default_pbx_id="1234567",
            pe_overrides={key: "03"},
        )
        self.assertIn("add1234567.csv", files)
        add_line = files["add1234567.csv"].splitlines()[0]
        self.assertIn(";03;", add_line)

    def test_collect_special_blocks_skips_resolved_overrides(self):
        result = calculate_bulk_split(["05012345xx"], ["0501234501"])
        source = result.modified_sources[0]
        key = source_lookup_key(source.start_number, source.size)
        unresolved = collect_special_add_blocks(result)
        resolved = collect_special_add_blocks(result, {key: "01"})
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(resolved, [])


class HelperTests(unittest.TestCase):
    def test_reconstruct_line_with_metadata(self):
        line = reconstruct_line_with_metadata("08888450xx", "1234567", "Utrecht")
        self.assertEqual(line, "08888450xx - PBX: 1234567 - Locatie: Utrecht")

    def test_reconstruct_line_pbx_only(self):
        line = reconstruct_line_with_metadata("08888450xx", "1234567")
        self.assertEqual(line, "08888450xx - PBX: 1234567")

    def test_normalize_number(self):
        self.assertEqual(normalize_number("0455688200"), "0455688200")
        self.assertEqual(normalize_number("455688200"), "0455688200")

    def test_is_special_location_lookup(self):
        self.assertTrue(is_special_location_lookup("0501234567"))
        self.assertTrue(is_special_location_lookup("0524123400"))
        self.assertFalse(is_special_location_lookup("0888845000"))


if __name__ == "__main__":
    unittest.main()
