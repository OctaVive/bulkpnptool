from __future__ import annotations

import csv
import io
import math
import re
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Sequence, Tuple

BlockSize = Literal[1, 10, 100, 1000, 10000]
OutputMode = Literal["pe_code", "location_id"]

VALID_BLOCK_SIZES: Tuple[int, ...] = (1, 10, 100, 1000, 10000)

SPECIAL_LOCATION_PREFIXES: Tuple[str, ...] = (
    "050",
    "0521",
    "0522",
    "0524",
    "0527",
    "0598",
    "0599",
)

_METADATA_SPLIT_RE = re.compile(
    r"\s+-\s+(?=PBX:|Locatie:|Location:)",
    re.IGNORECASE,
)
_PBX_RE = re.compile(r"PBX:\s*(\d{7})", re.IGNORECASE)
_LOCATION_RE = re.compile(
    r"(?:Locatie|Location):\s*(.+?)(?:\s*-\s*(?:PBX:|Locatie:|Location:)|$)",
    re.IGNORECASE,
)


@dataclass
class ParsedBlockInput:
    raw: str
    start_number: str
    size: BlockSize
    is_valid: bool
    error: Optional[str] = None
    pbx_comment: str = ""


@dataclass
class FinalTelecomBlock:
    start_number: str
    size: BlockSize
    formatted: str
    source_metadata: str = ""


@dataclass
class BulkSplitResult:
    parsed_sources: List[ParsedBlockInput] = field(default_factory=list)
    parsed_removes: List[ParsedBlockInput] = field(default_factory=list)
    resulting_blocks: List[FinalTelecomBlock] = field(default_factory=list)
    modified_sources: List[ParsedBlockInput] = field(default_factory=list)
    resulting_modified_blocks: List[FinalTelecomBlock] = field(default_factory=list)


@dataclass
class SpecialSplitterBlock:
    notation: str
    lookup_key: str
    lookup_national: str
    prefix: str


def split_input_lines(raw: str) -> List[str]:
    lines: List[str] = []
    for part in re.split(r"[\n,]+", raw):
        cleaned = part.strip()
        if cleaned:
            lines.append(cleaned)
    return lines


def convert_range_wildcards_to_lowercase(text: str) -> str:
    """Lowercase X wildcards in number portions only, not in metadata labels."""
    if not text:
        return text

    parts = _METADATA_SPLIT_RE.split(text, maxsplit=1)
    number_part = parts[0]
    suffix = parts[1] if len(parts) > 1 else ""

    number_part = re.sub(r"X", "x", number_part)
    if suffix:
        return number_part + " - " + suffix
    return number_part


def extract_pbx_id(line: str) -> str:
    match = _PBX_RE.search(line)
    return match.group(1) if match else ""


def extract_location_id(line: str) -> str:
    match = _LOCATION_RE.search(line)
    if not match:
        return ""
    return match.group(1).strip()


def reconstruct_line_with_metadata(
    line: str, pbx_id: str, location_id: str = ""
) -> str:
    number_part = _METADATA_SPLIT_RE.split(line, maxsplit=1)[0].strip()
    if location_id:
        return f"{number_part} - PBX: {pbx_id} - Locatie: {location_id}"
    return f"{number_part} - PBX: {pbx_id}"


def normalize_number(value: str) -> str:
    if not value:
        return ""

    s = value.strip()
    if s.startswith("+31"):
        s = "0" + s[3:]

    cleaned_chars: List[str] = []
    for ch in s:
        if ch.isdigit():
            cleaned_chars.append(ch)
        elif ch in {"X", "x"}:
            cleaned_chars.append("x")

    cleaned = "".join(cleaned_chars)
    if not cleaned:
        return ""

    if cleaned.startswith("0031"):
        cleaned = "0" + cleaned[4:]
    elif cleaned.startswith("31") and not cleaned.startswith("310"):
        cleaned = "0" + cleaned[2:]

    if len(cleaned) == 9 and not cleaned.startswith("0"):
        cleaned = "0" + cleaned

    return cleaned


def _normalize_wildcard_token(token: str) -> str:
    """Normalize block notation to 10-digit national form (digits + wildcards)."""
    normalized = normalize_number(token)
    if not normalized or "x" not in normalized:
        return normalized

    if len(normalized) == 10 and normalized.startswith("0"):
        return normalized

    if len(normalized) == 9 and not normalized.startswith("0"):
        return "0" + normalized

    if len(normalized) == 10 and not normalized.startswith("0"):
        # Common typo: 45568820xx should be 9-digit local 4556882xx (100-block).
        typo_match = re.fullmatch(r"(\d{7})0(xx)", normalized)
        if typo_match:
            return "0" + typo_match.group(1) + typo_match.group(2)
        return "0" + normalized[-9:]

    return normalized


def is_valid_block_alignment(normalized: str, size: BlockSize) -> bool:
    digits = normalized.replace("x", "")
    if not digits.isdigit() or len(digits) != 10:
        return False

    if size == 1:
        return True

    trailing_zeros = int(math.log10(size))
    return digits.endswith("0" * trailing_zeros)


def format_to_telecom_notation(start_number: str, size: BlockSize) -> str:
    start = normalize_number(start_number).replace("x", "0")
    if len(start) < 10:
        start = start.zfill(10)
    start = start[:10]

    if size == 1:
        return start

    wildcard_count = int(math.log10(size))
    return start[: 10 - wildcard_count] + ("x" * wildcard_count)


def _split_number_and_metadata(line: str) -> Tuple[str, str]:
    parts = _METADATA_SPLIT_RE.split(line.strip(), maxsplit=1)
    number_part = parts[0].strip()
    metadata = ""
    if len(parts) > 1:
        metadata = " - " + parts[1].strip()
    return number_part, metadata


def _parse_range_token(token: str) -> Tuple[Optional[str], BlockSize, Optional[str]]:
    if "-" not in token:
        return None, 1, "Invalid range format"

    beg_raw, end_raw = token.split("-", 1)
    beg = normalize_number(beg_raw.strip())
    end = normalize_number(end_raw.strip())

    if not beg or not end or "x" in beg or "x" in end:
        return None, 1, "Invalid range endpoints"

    if len(beg) != 10 or len(end) != 10:
        return None, 1, "Range endpoints must be 10 digits"

    beg_int = int(beg)
    end_int = int(end)
    if end_int < beg_int:
        return None, 1, "Range end must be greater than or equal to start"

    span = end_int - beg_int + 1
    if span not in VALID_BLOCK_SIZES:
        return None, 1, f"Range span {span} is not a valid telecom block size"

    size: BlockSize = span  # type: ignore[assignment]
    if not is_valid_block_alignment(beg, size):
        return None, 1, f"Range start is not aligned for block size {size}"

    return beg, size, None


def _parse_wildcard_token(token: str) -> Tuple[Optional[str], BlockSize, Optional[str]]:
    normalized = _normalize_wildcard_token(token)
    if "x" not in normalized:
        return None, 1, "No wildcard markers found"

    wildcard_count = normalized.count("x")
    if wildcard_count not in (1, 2, 3, 4):
        return None, 1, "Wildcard count must be 1, 2, 3, or 4"

    size = 10**wildcard_count
    if size not in VALID_BLOCK_SIZES:
        return None, 1, f"Block size {size} is not supported"

    size_typed: BlockSize = size  # type: ignore[assignment]

    if not normalized.endswith("x" * wildcard_count):
        return None, 1, "Wildcards must be trailing"

    start = normalized.replace("x", "0")
    if len(start) != 10:
        return None, 1, "Wildcard block must resolve to 10 digits"

    if not is_valid_block_alignment(start, size_typed):
        return None, 1, f"Block is not aligned for size {size_typed}"

    return start, size_typed, None


def parse_block_string(line: str) -> ParsedBlockInput:
    raw = line.strip()
    if not raw:
        return ParsedBlockInput(
            raw=raw,
            start_number="",
            size=1,
            is_valid=False,
            error="Empty line",
        )

    number_part, metadata = _split_number_and_metadata(raw)
    normalized_token = normalize_number(number_part)

    if not normalized_token:
        return ParsedBlockInput(
            raw=raw,
            start_number="",
            size=1,
            is_valid=False,
            error="No recognizable number or block",
            pbx_comment=metadata,
        )

    start_number: Optional[str] = None
    size: BlockSize = 1
    error: Optional[str] = None

    if "-" in number_part and "x" not in normalized_token:
        start_number, size, error = _parse_range_token(number_part)
    elif "x" in normalized_token:
        start_number, size, error = _parse_wildcard_token(number_part)
    elif len(normalized_token) == 10 and normalized_token.isdigit():
        start_number = normalized_token
        size = 1
        if not is_valid_block_alignment(start_number, 1):
            error = "Invalid single number"
    else:
        error = "Could not determine block size"

    if error or not start_number:
        return ParsedBlockInput(
            raw=raw,
            start_number=start_number or "",
            size=size,
            is_valid=False,
            error=error or "Invalid block",
            pbx_comment=metadata,
        )

    return ParsedBlockInput(
        raw=raw,
        start_number=start_number,
        size=size,
        is_valid=True,
        pbx_comment=metadata,
    )


def _ranges_overlap(start1: int, size1: int, start2: int, size2: int) -> bool:
    end1 = start1 + size1 - 1
    end2 = start2 + size2 - 1
    return start1 <= end2 and start2 <= end1


def _number_in_range(number: int, start: int, size: int) -> bool:
    return start <= number <= start + size - 1


def _range_fully_removed(start: int, size: int, removes: Sequence[Tuple[int, int]]) -> bool:
    for number in range(start, start + size):
        if not any(_number_in_range(number, r_start, r_size) for r_start, r_size in removes):
            return False
    return True


def _subtract_removes(
    start: int,
    size: int,
    removes: Sequence[Tuple[int, int]],
) -> Tuple[List[Tuple[int, int]], bool]:
    if size <= 0:
        return [], False

    overlapping = [
        (r_start, r_size)
        for r_start, r_size in removes
        if _ranges_overlap(start, size, r_start, r_size)
    ]

    if not overlapping:
        return [(start, size)], False

    if _range_fully_removed(start, size, removes):
        return [], True

    if size == 1:
        if any(_number_in_range(start, r_start, r_size) for r_start, r_size in removes):
            return [], True
        return [(start, 1)], False

    sub_size = size // 10
    retained: List[Tuple[int, int]] = []
    for index in range(10):
        sub_start = start + index * sub_size
        sub_retained, _ = _subtract_removes(sub_start, sub_size, removes)
        retained.extend(sub_retained)

    return retained, True


def _int_to_start_string(value: int) -> str:
    return str(value).zfill(10)


def _inherit_metadata(source: ParsedBlockInput, fallback: ParsedBlockInput) -> str:
    if source.pbx_comment:
        return source.pbx_comment
    return fallback.pbx_comment


def _find_containing_source(
    remove: ParsedBlockInput,
    sources: Sequence[ParsedBlockInput],
) -> Optional[ParsedBlockInput]:
    rem_start = int(remove.start_number)
    rem_end = rem_start + remove.size - 1

    for source in sources:
        if not source.is_valid:
            continue
        src_start = int(source.start_number)
        src_end = src_start + source.size - 1
        if rem_start >= src_start and rem_end <= src_end:
            return source
    return None


def get_special_prefix(lookup_national: str) -> Optional[str]:
    for prefix in sorted(SPECIAL_LOCATION_PREFIXES, key=len, reverse=True):
        if lookup_national.startswith(prefix):
            return prefix
    return None


def is_special_location_lookup(lookup_national: str) -> bool:
    return get_special_prefix(lookup_national) is not None


def block_lookup_key(block: FinalTelecomBlock) -> str:
    return f"{block.start_number}_{block.size}"


def block_lookup_national(block: FinalTelecomBlock) -> str:
    return normalize_number(
        format_to_telecom_notation(block.start_number, block.size)
    ).replace("x", "0")


def source_lookup_key(start_number: str, size: int) -> str:
    return f"source_{start_number}_{size}"


def _source_lookup_national(start_number: str, size: int) -> str:
    return normalize_number(
        format_to_telecom_notation(start_number, size)
    ).replace("x", "0")


def _special_sources_for_add(result: BulkSplitResult) -> List[ParsedBlockInput]:
    modified_keys = {(source.start_number, source.size) for source in result.modified_sources}
    sources: List[ParsedBlockInput] = list(result.modified_sources)

    for source in result.parsed_sources:
        if not source.is_valid:
            continue
        key = (source.start_number, source.size)
        if key in modified_keys:
            continue
        sources.append(source)

    return sources


def _find_containing_special_source_key(
    block: FinalTelecomBlock,
    result: BulkSplitResult,
) -> Optional[str]:
    block_start = int(block.start_number)
    block_end = block_start + block.size - 1
    best: Optional[Tuple[int, str]] = None

    for source in _special_sources_for_add(result):
        lookup = _source_lookup_national(source.start_number, source.size)
        if not is_special_location_lookup(lookup):
            continue

        src_start = int(source.start_number)
        src_end = src_start + source.size - 1
        if src_start <= block_start and block_end <= src_end:
            key = source_lookup_key(source.start_number, source.size)
            if best is None or source.size < best[0]:
                best = (source.size, key)

    return best[1] if best else None


def collect_special_add_blocks(
    result: BulkSplitResult,
    pe_overrides: Optional[Dict[str, str]] = None,
) -> List[SpecialSplitterBlock]:
    overrides = pe_overrides or {}
    items: List[SpecialSplitterBlock] = []
    seen: set[str] = set()

    for source in _special_sources_for_add(result):
        lookup = _source_lookup_national(source.start_number, source.size)
        if not is_special_location_lookup(lookup):
            continue

        key = source_lookup_key(source.start_number, source.size)
        if key in seen:
            continue
        if overrides.get(key):
            continue

        prefix = get_special_prefix(lookup)
        if not prefix:
            continue

        seen.add(key)
        items.append(
            SpecialSplitterBlock(
                notation=format_to_telecom_notation(source.start_number, source.size),
                lookup_key=key,
                lookup_national=lookup,
                prefix=prefix,
            )
        )
    return items


def block_display_notation(block: FinalTelecomBlock) -> str:
    return format_to_telecom_notation(block.start_number, block.size)


def build_splitter_raw_text(result: BulkSplitResult) -> str:
    remove_blocks = [
        format_to_telecom_notation(item.start_number, item.size)
        if item.is_valid
        else item.raw
        for item in result.parsed_removes
    ]
    add_blocks = [
        block_display_notation(block)
        for block in result.resulting_modified_blocks
    ]
    del_blocks = [
        block_display_notation(block)
        for block in _collect_delete_items(result)
    ]

    lines = [
        "To be removed",
        "",
    ]
    lines.extend(remove_blocks if remove_blocks else ["(none)"])
    lines.extend(
        [
            "",
            "Step 1 — Add (retained blocks)",
            "",
        ]
    )
    lines.extend(add_blocks if add_blocks else ["(none)"])
    lines.extend(
        [
            "",
            "Step 2 — Delete (parent blocks + removes)",
            "",
        ]
    )
    lines.extend(del_blocks if del_blocks else ["(none)"])
    return "\n".join(lines) + "\n"


def _block_from_parsed(parsed: ParsedBlockInput, metadata_source: ParsedBlockInput) -> FinalTelecomBlock:
    notation = format_to_telecom_notation(parsed.start_number, parsed.size)
    metadata = _inherit_metadata(parsed, metadata_source)
    if metadata and not metadata.startswith(" - "):
        metadata = " - " + metadata.lstrip(" -")
    return FinalTelecomBlock(
        start_number=parsed.start_number,
        size=parsed.size,
        formatted=notation,
        source_metadata=metadata,
    )


def _is_remove_contained_in_sources(remove_line: str, sources: Sequence[str]) -> bool:
    rem_parsed = parse_block_string(remove_line)
    if not rem_parsed.is_valid:
        return False

    rem_start = int(rem_parsed.start_number)
    rem_end = rem_start + rem_parsed.size - 1

    for src_line in sources:
        src_parsed = parse_block_string(src_line)
        if not src_parsed.is_valid:
            continue
        src_start = int(src_parsed.start_number)
        src_end = src_start + src_parsed.size - 1
        if rem_start >= src_start and rem_end <= src_end:
            return True
    return False


def sources_missing_pbx(source_lines: Sequence[str]) -> bool:
    for line in source_lines:
        parsed = parse_block_string(line)
        if not parsed.is_valid:
            continue
        pbx = extract_pbx_id(line)
        if not (pbx and len(pbx) == 7 and pbx.isdigit()):
            return True
    return False


def sources_missing_metadata(source_lines: Sequence[str]) -> bool:
    for line in source_lines:
        parsed = parse_block_string(line)
        if not parsed.is_valid:
            continue
        pbx = extract_pbx_id(line)
        has_pbx = bool(pbx) and len(pbx) == 7 and pbx.isdigit()
        has_loc = bool(re.search(r"locatie|location", line, re.IGNORECASE))
        if not has_pbx or not has_loc:
            return True
    return False


def removes_missing_pbx(remove_lines: Sequence[str], source_lines: Sequence[str]) -> bool:
    for line in remove_lines:
        parsed = parse_block_string(line)
        if not parsed.is_valid:
            continue
        if _is_remove_contained_in_sources(line, source_lines):
            continue
        pbx = extract_pbx_id(line)
        if not (pbx and len(pbx) == 7 and pbx.isdigit()):
            return True
    return False


def removes_missing_metadata(remove_lines: Sequence[str], source_lines: Sequence[str]) -> bool:
    for line in remove_lines:
        parsed = parse_block_string(line)
        if not parsed.is_valid:
            continue
        if _is_remove_contained_in_sources(line, source_lines):
            continue
        pbx = extract_pbx_id(line)
        has_pbx = bool(pbx) and len(pbx) == 7 and pbx.isdigit()
        has_loc = bool(re.search(r"locatie|location", line, re.IGNORECASE))
        if not has_pbx or not has_loc:
            return True
    return False


def apply_metadata_to_source_lines(
    lines: Sequence[str],
    pbx_id: str,
    location_id: str,
) -> List[str]:
    updated: List[str] = []
    for line in lines:
        parsed = parse_block_string(line)
        if parsed.is_valid:
            updated.append(reconstruct_line_with_metadata(line, pbx_id, location_id))
        else:
            updated.append(line)
    return updated


def apply_metadata_to_remove_lines(
    lines: Sequence[str],
    source_lines: Sequence[str],
    pbx_id: str,
    location_id: str,
) -> List[str]:
    updated: List[str] = []
    for line in lines:
        parsed = parse_block_string(line)
        if not parsed.is_valid:
            updated.append(line)
            continue
        if _is_remove_contained_in_sources(line, source_lines):
            updated.append(line)
        else:
            updated.append(reconstruct_line_with_metadata(line, pbx_id, location_id))
    return updated


def calculate_bulk_split(sources: Sequence[str], removes: Sequence[str]) -> BulkSplitResult:
    parsed_sources = [parse_block_string(line) for line in sources]
    parsed_removes = [parse_block_string(line) for line in removes]

    valid_removes: List[Tuple[int, int]] = [
        (int(item.start_number), item.size)
        for item in parsed_removes
        if item.is_valid
    ]

    resulting_modified_blocks: List[FinalTelecomBlock] = []
    modified_sources: List[ParsedBlockInput] = []
    resulting_blocks: List[FinalTelecomBlock] = []

    valid_source_items = [item for item in parsed_sources if item.is_valid]

    for source in valid_source_items:
        start = int(source.start_number)
        retained, was_modified = _subtract_removes(start, source.size, valid_removes)

        if was_modified:
            modified_sources.append(source)

        for retained_start, retained_size in retained:
            retained_size_typed: BlockSize = retained_size  # type: ignore[assignment]
            retained_parsed = ParsedBlockInput(
                raw=source.raw,
                start_number=_int_to_start_string(retained_start),
                size=retained_size_typed,
                is_valid=True,
                pbx_comment=source.pbx_comment,
            )
            block = _block_from_parsed(retained_parsed, source)
            resulting_modified_blocks.append(block)
            resulting_blocks.append(block)

    for remove in parsed_removes:
        if not remove.is_valid:
            continue
        container = _find_containing_source(remove, valid_source_items)
        metadata_source = container if container else remove
        block = _block_from_parsed(remove, metadata_source)
        resulting_blocks.append(block)

    return BulkSplitResult(
        parsed_sources=parsed_sources,
        parsed_removes=parsed_removes,
        resulting_blocks=resulting_blocks,
        modified_sources=modified_sources,
        resulting_modified_blocks=resulting_modified_blocks,
    )


def _export_phone_value(notation: str) -> str:
    if notation.startswith("0"):
        return notation[1:]
    return notation


def _resolve_column_four_for_block(
    block: FinalTelecomBlock,
    output_mode: OutputMode,
    pe_processor,
    pe_overrides: Optional[Dict[str, str]] = None,
    result: Optional[BulkSplitResult] = None,
) -> Optional[str]:
    if output_mode == "location_id":
        for text in (block.source_metadata, block.formatted):
            loc = extract_location_id(text)
            if loc:
                return loc
        return None

    lookup = block_lookup_national(block)
    overrides = pe_overrides or {}

    if is_special_location_lookup(lookup):
        if result is not None:
            source_key = _find_containing_special_source_key(block, result)
            if source_key:
                return overrides.get(source_key)
        return overrides.get(block_lookup_key(block))

    return pe_processor.resolve_pe_code(lookup)


def _column_four_for_operation(
    block: FinalTelecomBlock,
    output_mode: OutputMode,
    pe_processor,
    operation: str,
    pe_overrides: Optional[Dict[str, str]] = None,
    result: Optional[BulkSplitResult] = None,
) -> Optional[str]:
    if output_mode == "pe_code" and operation == "deletePNP":
        return "00"
    return _resolve_column_four_for_block(
        block,
        output_mode,
        pe_processor,
        pe_overrides=pe_overrides,
        result=result,
    )


def _collect_delete_items(result: BulkSplitResult) -> List[FinalTelecomBlock]:
    items: List[FinalTelecomBlock] = []
    valid_sources = [s for s in result.parsed_sources if s.is_valid]

    modified_parents = [m for m in result.modified_sources if m.size > 1]

    for modified in modified_parents:
        items.append(_block_from_parsed(modified, modified))

    parent_keys = {(m.start_number, m.size) for m in modified_parents}

    for remove in result.parsed_removes:
        if not remove.is_valid:
            continue
        if (remove.start_number, remove.size) in parent_keys:
            continue
        # Singles/sub-blocks inside a parent being deleted are implied by the
        # parent delete + retained ADD rows — they were not individually provisioned.
        if modified_parents and _find_containing_source(remove, modified_parents):
            continue
        container = _find_containing_source(remove, valid_sources)
        metadata_source = container if container else remove
        items.append(_block_from_parsed(remove, metadata_source))

    deduped: List[FinalTelecomBlock] = []
    seen: set[Tuple[str, int]] = set()
    for item in items:
        key = (item.start_number, item.size)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _pbx_for_block(block: FinalTelecomBlock, default_pbx_id: str) -> str:
    for text in (block.source_metadata, block.formatted):
        inline = extract_pbx_id(text)
        if inline and len(inline) == 7 and inline.isdigit():
            return inline
    return default_pbx_id


def build_splitter_csv_files(
    result: BulkSplitResult,
    output_mode: OutputMode,
    pe_processor,
    default_pbx_id: str = "",
    pe_overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    files: Dict[str, str] = {}

    add_groups: Dict[str, List[FinalTelecomBlock]] = {}
    for block in result.resulting_modified_blocks:
        pbx_id = _pbx_for_block(block, default_pbx_id) or "onbekend"
        add_groups.setdefault(pbx_id, []).append(block)

    for pbx_id, blocks in add_groups.items():
        rows: List[List[str]] = []
        row_number = 1
        for block in blocks:
            col4 = _column_four_for_operation(
                block,
                output_mode,
                pe_processor,
                "addPNP",
                pe_overrides=pe_overrides,
                result=result,
            )
            if col4 is None:
                continue
            notation = format_to_telecom_notation(block.start_number, block.size)
            rows.append(
                [
                    str(row_number),
                    "addPNP",
                    _export_phone_value(notation),
                    col4,
                    pbx_id,
                ]
            )
            row_number += 1
        if rows:
            files[f"add{pbx_id}.csv"] = _rows_to_csv(rows)

    delete_groups: Dict[str, List[FinalTelecomBlock]] = {}
    for block in _collect_delete_items(result):
        pbx_id = _pbx_for_block(block, default_pbx_id) or "onbekend"
        delete_groups.setdefault(pbx_id, []).append(block)

    for pbx_id, blocks in delete_groups.items():
        rows = []
        row_number = 1
        for block in blocks:
            col4 = _column_four_for_operation(
                block,
                output_mode,
                pe_processor,
                "deletePNP",
                pe_overrides=pe_overrides,
                result=result,
            )
            if col4 is None:
                continue
            notation = format_to_telecom_notation(block.start_number, block.size)
            rows.append(
                [
                    str(row_number),
                    "deletePNP",
                    _export_phone_value(notation),
                    col4,
                    pbx_id,
                ]
            )
            row_number += 1
        if rows:
            files[f"del{pbx_id}.csv"] = _rows_to_csv(rows)

    return files


def _rows_to_csv(rows: List[List[str]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def build_zip_filename(files: Dict[str, str]) -> str:
    pbx_ids = sorted(
        {
            filename[3:-4]
            for filename in files
            if (filename.startswith("add") or filename.startswith("del"))
            and filename.endswith(".csv")
        }
    )
    parts: List[str] = []
    for pbx_id in pbx_ids:
        if f"add{pbx_id}.csv" in files:
            parts.append(f"add{pbx_id}")
        if f"del{pbx_id}.csv" in files:
            parts.append(f"del{pbx_id}")
    if not parts:
        return "splitter_export.zip"
    return "_".join(parts) + ".zip"


def build_splitter_zip(
    result: BulkSplitResult,
    output_mode: OutputMode,
    pe_processor,
    default_pbx_id: str = "",
    pe_overrides: Optional[Dict[str, str]] = None,
) -> Tuple[bytes, str]:
    files = build_splitter_csv_files(
        result,
        output_mode,
        pe_processor,
        default_pbx_id=default_pbx_id,
        pe_overrides=pe_overrides,
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename, content in files.items():
            archive.writestr(filename, content)
    return buffer.getvalue(), build_zip_filename(files)


def default_zip_filename(files: Dict[str, str]) -> str:
    return build_zip_filename(files)
