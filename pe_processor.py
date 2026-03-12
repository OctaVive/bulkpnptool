import threading
from pathlib import Path
from typing import Dict, Optional


_PE_CODES_PATH = Path(__file__).parent / "data" / "pe_codes.txt"


class PEProcessor:
    """
    Loads and resolves PE codes based on Dutch telephone prefixes.

    Behaviour:
    - Mappings are loaded once on first use and cached.
    - 050 is intentionally NOT in the mapping file; it must be handled separately.
    - Resolution:
        1) Try 4-digit prefix
        2) Fallback to 3-digit prefix
    """

    _instance_lock = threading.Lock()
    _instance: Optional["PEProcessor"] = None

    def __new__(cls) -> "PEProcessor":
        # Simple singleton – ensure mappings are only loaded once per process.
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_mappings()
        return cls._instance

    def _init_mappings(self) -> None:
        self._prefix_to_pe: Dict[str, str] = {}
        # Local (subscriber) prefix mapping, e.g. "45" -> "24" derived from "045".
        self._local_prefix_to_pe: Dict[str, str] = {}

        if not _PE_CODES_PATH.exists():
            return

        with _PE_CODES_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(";")
                if len(parts) < 2:
                    continue
                prefix = parts[0].strip()
                pe_code = parts[1].strip()
                if not prefix or not pe_code:
                    continue
                # 050 must be treated as ambiguous and is therefore not loaded.
                if prefix == "050":
                    continue
                self._prefix_to_pe[prefix] = pe_code

                # Also build a local-prefix map for short/local numbers.
                # Example: "045" -> local "45" (PE24), "071" -> "71" (PE16).
                if prefix.startswith("0") and len(prefix) == 3:
                    local_prefix = prefix[1:]
                    # Do not derive a "50" mapping from "050" (already skipped above).
                    if local_prefix and local_prefix not in self._local_prefix_to_pe:
                        self._local_prefix_to_pe[local_prefix] = pe_code

    def resolve_pe_code(self, national_number: str) -> Optional[str]:
        """
        Resolve the PE code for a given national-format number.

        Args:
            national_number: Number in Dutch national format, expected
                             to start with '0' and be at least 3 digits.

        Returns:
            The PE code as a string, or None if no mapping exists.

        Notes:
            - This method NEVER auto-resolves 050; callers must handle
              050 separately before calling this method.
        """
        if not national_number or len(national_number) < 3:
            return None

        # Ensure we're not auto-resolving 050.
        if national_number.startswith("050"):
            return None

        # Try 4-digit prefix first, then 3-digit.
        if len(national_number) >= 4:
            prefix4 = national_number[:4]
            pe = self._prefix_to_pe.get(prefix4)
            if pe is not None:
                return pe

        prefix3 = national_number[:3]
        pe = self._prefix_to_pe.get(prefix3)
        if pe is not None:
            return pe

        # Fallback: look at the first digits of the subscriber part
        # (local number without the leading '0' of the national format),
        # e.g. "455688211" -> "45" -> PE24, "71688200" -> "71" -> PE16.
        digits = "".join(ch for ch in national_number if ch.isdigit())
        if not digits:
            return None

        # Strip a single leading 0 if present to get the local portion.
        if digits.startswith("0"):
            digits = digits[1:]
        if len(digits) < 2:
            return None

        local_prefix2 = digits[:2]
        return self._local_prefix_to_pe.get(local_prefix2)


def get_pe_processor() -> PEProcessor:
    """
    Helper to obtain the singleton PEProcessor instance.
    """
    return PEProcessor()

