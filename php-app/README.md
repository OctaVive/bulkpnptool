# Bulk PNP Tool — PHP

Standalone PHP port of the Flask application. Requires **PHP 8.1 or newer (64-bit)**. No Composer packages, Python runtime, database, or PHP ZIP extension are needed. The included Docker setup uses PHP 8.4.

Includes Provisioning (ADD, DELETE, MOVE), NGIN CSV downloads, ENUM XLSX downloads, special-prefix PE location selection and bulk assignment, the Number Splitter with RAW text and CSV ZIP exports, and the Configuration / Coming soon tab. PBX validation and the same-PBX MOVE error run in both the browser and PHP. All mappings and the logo are copied into this folder.

This folder can be tracked in Git. The original Python app is unchanged.

## Run locally

From this folder:

```powershell
php -S 127.0.0.1:5001 -t public router.php
```

Open http://localhost:5001.

Alternatively, with Docker:

```powershell
docker compose up --build -d
```

Stop it with `docker compose down`.

## Hosting

Set the web server's document root to **`php-app/public`**, so PHP libraries, data, and test fixtures remain outside the public directory. Apache can use the included `.htaccess` with `mod_rewrite` and `AllowOverride FileInfo`. For nginx/PHP-FPM, route missing public files to `/index.php` and pass the query string. The built-in PHP server and supplied Docker image are intended for local use. Routes and asset URLs assume the site is served at the domain root.

## Verification

Run the standalone reference suite (1,651 cases):

```powershell
php tests/test.php
```

Or without installing PHP:

```powershell
docker compose run --rm php-app php tests/test.php
```

The fixtures cover number normalization, input errors, PE mappings, special prefixes, randomized block subtraction, metadata inheritance, CSV rows, and download names, compared with the original Python code.

`tests/test_http.py` also checks the running site on port 5001, including all tabs, PBX validation, location selection, CSV downloads, XLSX workbook contents and styling, ZIP downloads, static assets, and private-file isolation. These additional migration checks require the original Python app's dependencies (`Flask` and `openpyxl`); they are not application runtime dependencies:

```powershell
python tests/test_http.py
```

`tests/build_fixtures.py` regenerates fixtures from the Python app. `convert_templates.py` is the one-time migration helper used to produce native PHP templates; neither script runs when serving the PHP app.
