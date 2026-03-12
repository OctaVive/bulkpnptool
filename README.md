# Bulk PNP Provisioning Tool

Python/Flask web application for generating deterministic CSV provisioning commands for Dutch telephone numbers.

The tool is designed for telecom engineers and focuses on safety, predictability, and clear control over ambiguous prefixes such as **050**.

---

## Features

- **Bulk input**: Paste between ~500 and 10,000 numbers.
- **Supported operations**:
  - `ADD` → `addPNP`
  - `DELETE` → `deletePNP`
  - `MOVE` → `deletePNP` + `addPNP`
- **CSV output**:
  - Semicolon-separated
  - Columns (fixed order): `RowNumber;Operation;PhoneNumber;PE Code;PBX-ID`
  - Filename: `bulk_pnp_operations.csv`
- **PE code resolution**:
  - Uses `data/pe_codes.txt`
  - 4‑digit prefix lookup first, then 3‑digit
  - `050` is treated as ambiguous and is **never** auto-resolved
- **050 workflow**:
  - 050 numbers are detected and collected
  - A dedicated screen (`select_050.html`) lets you select the correct location/PE for each
  - Locations come from `data/050_locations.txt`
- **Wildcard blocks**:
  - Accepts patterns like `45568820X`
  - Used for PE lookup only (with `X` interpreted as `0` for lookup)
  - **Never expanded** in the CSV; exported exactly as entered

---

## Installation

1. Create and activate a virtual environment (recommended):

   ```bash
   cd bulkpcaptool
   python3 -m venv .venv
   source .venv/bin/activate  # on Windows: .venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run the Flask application:

   ```bash
   export FLASK_APP=app.py
   flask run
   ```

   Or, directly:

   ```bash
   python app.py
   ```

4. Open the UI in a browser:

   ```text
   http://127.0.0.1:5000/
   ```

---

## Running with Docker

You can run the application without installing Python locally by using Docker.

### Build and run with plain Docker

From the project root:

```bash
docker build -t bulk-pnp-tool .
docker run --rm -p 5000:5000 bulk-pnp-tool
```

Then open:

```text
http://127.0.0.1:5000/
```

### Build and run with Docker Compose

From the project root:

```bash
docker compose up --build
```

This will:

- **Build** the image from the `Dockerfile`.
- **Run** the container exposing port `5000` on your machine.

Stop it with:

```bash
docker compose down
```

---

## Data files

### `data/pe_codes.txt`

PE mappings are stored in `data/pe_codes.txt` and loaded at process startup by `pe_processor.py`.

Format:

```text
Prefix;PE Code;City
020;13;Amsterdam
010;17;Rotterdam
071;16;Leiden
045;24;Heerlen
```

Notes:

- `050` must **not** be present here, as it is ambiguous and handled separately.
- The processor:
  - Tries 4‑digit prefix first (e.g. `0455`)
  - Falls back to 3‑digit prefix (e.g. `045`)

### `data/050_locations.txt`

Locations and PE codes for ambiguous `050` numbers are stored in `data/050_locations.txt`.

Format:

```text
City;PE Code
Groningen;01
Adorp;01
Bedum;01
Eelde;03
Roden;03
```

These entries populate the dropdown in `select_050.html`.

---

## Number normalisation and export rules

- **Accepted input formats**:
  - `455688200`
  - `0455688200`
  - `+31455688200`
  - `45568820X`
- **Normalisation for PE lookup**:
  - Remove all characters except digits and `X/x`
  - Convert `+31` prefix to `0`
  - Convert 9‑digit numbers to 10‑digit national form by prefixing `0`
  - For wildcard blocks, use `X→0` **only for lookup**
- **Exported phone numbers**:
  - Non‑wildcard numbers are exported as **9 digits** (no leading `0`), e.g.:
    - `0455688200` → `455688200`
  - Wildcard blocks are exported **exactly as entered** and are never expanded:
    - Input: `45568820X` → CSV: `45568820X`

---

## Operations and CSV format

The CSV columns are always:

```text
RowNumber;Operation;PhoneNumber;PE Code;PBX-ID
```

Operation mapping:

- `ADD`:
  - Generates a single `addPNP` row per number
  - Uses the **Target PBX-ID** field from the form
- `DELETE`:
  - Generates a single `deletePNP` row per number
  - Uses the **Source PBX-ID** field from the form
- `MOVE`:
  - Generates two rows per number:
    1. `deletePNP` using Source PBX-ID
    2. `addPNP` using Target PBX-ID

Example MOVE output:

```text
1;deletePNP;455688200;24;1000000
2;addPNP;455688200;24;2000000
```

---

## Safety and behaviour guarantees

- **Never expands wildcard numbers** in the CSV.
- **Never auto-resolves ambiguous prefixes** such as `050`; user input is required.
- **Never changes CSV column order**.
- **PE processor**:
  - Loads mappings once at startup
  - Performs O(1) prefix lookups (4‑digit then 3‑digit)
  - Skips numbers that cannot be resolved safely (no row generated)

These constraints are intended to keep provisioning behaviour stable, deterministic, and suitable for telecom operations.

