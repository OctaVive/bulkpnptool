from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from flask import Flask, Response, render_template, request, send_from_directory

from pe_processor import get_pe_processor


app = Flask(__name__)


@dataclass
class ParsedNumber:
    raw_input: str
    is_wildcard: bool
    lookup_national: Optional[str]  # national format with leading 0, digits only
    export_value: str               # exact value to write into CSV


def _clean_input_line(line: str) -> str:
    # Strip surrounding whitespace but otherwise keep as-is for wildcard export.
    return line.strip()


def _normalize_for_lookup(raw: str) -> Tuple[Optional[str], bool]:
    """
    Normalize a user-entered phone number for PE lookup.

    Behaviour:
    - Remove all characters except digits and 'X'/'x'.
    - Convert '+31' prefix to '0'.
    - Convert 9-digit numbers (without leading 0) to 10-digit by prefixing '0'.
    - For wildcard blocks, 'X' is only used for lookup by treating it as '0'.

    Returns:
        (national_number_with_leading_zero_or_None, is_wildcard)
    """
    if not raw:
        return None, False

    s = raw.strip()

    # Handle +31 country code (only for normalization, NOT export).
    if s.startswith("+31"):
        s = "0" + s[3:]

    # Keep digits and X/x only.
    cleaned_chars: List[str] = []
    is_wildcard = False
    for ch in s:
        if ch.isdigit():
            cleaned_chars.append(ch)
        elif ch in {"X", "x"}:
            cleaned_chars.append("X")
            is_wildcard = True
        # all other characters are discarded for lookup purposes

    if not cleaned_chars:
        return None, False

    cleaned = "".join(cleaned_chars)

    # For wildcard lookup, treat X as 0.
    lookup_str = cleaned.replace("X", "0")

    # Ensure we have a national-format number (leading 0, 10 digits) for lookup.
    digits_only = "".join(ch for ch in lookup_str if ch.isdigit())

    # If we see a local 050-range number (starting with "50"), make it explicit
    # national format "050..." so that it is treated as ambiguous and triggers
    # the 050 selection flow. We do not apply the generic 9-digit rule again
    # in this case to avoid ending up with "0050...".
    if digits_only.startswith("50") and not digits_only.startswith("050"):
        digits_only = "0" + digits_only
    elif len(digits_only) == 9:
        # Local form, add leading 0.
        digits_only = "0" + digits_only
    # If already 10 digits starting with 0, leave as-is; otherwise we still try
    # prefix resolution with whatever we have, as long as length >= 3.

    if len(digits_only) < 3:
        return None, is_wildcard

    return digits_only, is_wildcard


def _parse_numbers(raw_numbers: str) -> List[ParsedNumber]:
    """
    Parse and normalize raw user input into structures used for lookup and export.
    """
    parsed: List[ParsedNumber] = []

    for line in raw_numbers.splitlines():
        cleaned_line = _clean_input_line(line)
        if not cleaned_line:
            continue

        lookup_national, is_wildcard = _normalize_for_lookup(cleaned_line)

        if is_wildcard:
            # For wildcard blocks, the exported number must remain exactly as entered.
            export_value = cleaned_line
        else:
            # For non-wildcard numbers, export without the leading 0.
            export_value = cleaned_line
            if lookup_national:
                digits = "".join(ch for ch in lookup_national if ch.isdigit())
                if digits.startswith("050") and len(digits) == 9:
                    # Special case for 050 region: keep the 50 prefix but drop the
                    # leading 0 so that, for example, 050688200 → 50688200.
                    export_value = digits[1:]
                elif digits.startswith("0") and len(digits) >= 10:
                    # Generic national format: strip leading 0 and keep next 9 digits.
                    export_value = digits[1:10]
                elif len(digits) == 9:
                    export_value = digits

        parsed.append(
            ParsedNumber(
                raw_input=cleaned_line,
                is_wildcard=is_wildcard,
                lookup_national=lookup_national,
                export_value=export_value,
            )
        )

    return parsed


def _load_050_locations() -> List[Dict[str, str]]:
    from pathlib import Path

    locations_file = Path(__file__).parent / "data" / "050_locations.txt"
    locations: List[Dict[str, str]] = []

    if not locations_file.exists():
        return locations

    with locations_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(";")
            if len(parts) < 2:
                continue
            city = parts[0].strip()
            pe_code = parts[1].strip()
            if not city or not pe_code:
                continue
            locations.append({"city": city, "pe_code": pe_code})

    return locations


def _collect_050_numbers(parsed_numbers: List[ParsedNumber]) -> List[ParsedNumber]:
    fifty_numbers: List[ParsedNumber] = []
    for p in parsed_numbers:
        if p.lookup_national and p.lookup_national.startswith("050"):
            fifty_numbers.append(p)
    return fifty_numbers


def _build_csv_rows(
    parsed_numbers: List[ParsedNumber],
    operation: str,
    pbx_id_from: str,
    pbx_id_to: str,
    pe_050_overrides: Dict[str, str],
) -> List[List[str]]:
    pe_processor = get_pe_processor()

    rows: List[List[str]] = []
    row_number = 1

    op = operation.upper()

    for p in parsed_numbers:
        if not p.lookup_national:
            # Cannot resolve PE for this entry; skip it silently to avoid
            # generating potentially unsafe provisioning rows.
            continue

        # Handle ambiguous 050 numbers with user-provided PE override.
        if p.lookup_national.startswith("050"):
            pe_code = pe_050_overrides.get(p.lookup_national)
            if not pe_code:
                # No user selection; do not auto-resolve.
                continue
        else:
            pe_code = pe_processor.resolve_pe_code(p.lookup_national)
            if not pe_code:
                # No mapping; skip to avoid unsafe provisioning.
                continue

        # Determine which PBX ID(s) to use based on operation.
        if op == "ADD":
            logical_ops = [("addPNP", pbx_id_to)]
        elif op == "DELETE":
            logical_ops = [("deletePNP", pbx_id_from)]
        elif op == "MOVE":
            # MOVE → deletePNP + addPNP
            logical_ops = [
                ("deletePNP", pbx_id_from),
                ("addPNP", pbx_id_to),
            ]
        else:
            # Unknown operation; nothing to generate.
            continue

        for logical_op, pbx in logical_ops:
            rows.append(
                [
                    str(row_number),
                    logical_op,
                    p.export_value,
                    pe_code,
                    pbx,
                ]
            )
            row_number += 1

    return rows


@app.route("/assets/<path:filename>")
def asset(filename: str):
    """
    Serve static assets (e.g. Vodafone logo) from the local assets directory.
    """
    import os

    assets_dir = os.path.join(os.path.dirname(__file__), "assets")
    return send_from_directory(assets_dir, filename)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("index.html")

    # POST: process numbers
    numbers_raw = request.form.get("numbers", "")
    operation = request.form.get("operation", "ADD")
    pbx_id_from = request.form.get("pbx_id_from", "")
    pbx_id_to = request.form.get("pbx_id_to", "")

    parsed_numbers = _parse_numbers(numbers_raw)
    fifty_numbers = _collect_050_numbers(parsed_numbers)

    confirm_050 = request.form.get("confirm_050")

    if fifty_numbers and not confirm_050:
        # Render 050 selection popup.
        locations = _load_050_locations()
        # Use lookup_national as the key, which will be a 10-digit national-format
        # number beginning with 050, e.g. 0501234567. This matches the example
        # pe_0501234567=01.
        return render_template(
            "select_050.html",
            numbers_050=fifty_numbers,
            locations=locations,
            numbers_raw=numbers_raw,
            operation=operation,
            pbx_id_from=pbx_id_from,
            pbx_id_to=pbx_id_to,
        )

    # If we are here, either there were no 050 numbers or the user already
    # confirmed the PE codes for them.
    pe_050_overrides: Dict[str, str] = {}
    if confirm_050:
        # Collect all submitted PE codes for 050 numbers.
        for key, value in request.form.items():
            if not key.startswith("pe_"):
                continue
            national_number = key[len("pe_") :]
            pe_050_overrides[national_number] = value

    rows = _build_csv_rows(
        parsed_numbers=parsed_numbers,
        operation=operation,
        pbx_id_from=pbx_id_from,
        pbx_id_to=pbx_id_to,
        pe_050_overrides=pe_050_overrides,
    )

    # Generate CSV content.
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\n")
    for row in rows:
        writer.writerow(row)

    csv_data = output.getvalue()
    output.close()

    # Serve as file download.
    headers = {
        "Content-Disposition": 'attachment; filename="bulk_pnp_operations.csv"',
        "Content-Type": "text/csv; charset=utf-8",
    }
    return Response(csv_data, headers=headers)


if __name__ == "__main__":
    # Simple built-in server for local testing and Docker.
    # Bind to 0.0.0.0 so the container's port 5000 is reachable.
    app.run(host="0.0.0.0", port=5000, debug=True)

