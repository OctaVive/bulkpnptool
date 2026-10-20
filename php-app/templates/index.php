<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Bulk PNP Provisioning Tool</title>
    <style>
      body {
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        margin: 0;
        padding: 0;
        background: #ffffff;
        color: #000000;
      }
      .container {
        max-width: 960px;
        margin: 0 auto;
        padding: 32px 16px 48px;
      }
      h1 {
        font-size: 1.9rem;
        margin-bottom: 0.5rem;
      }
      h2 {
        font-size: 1.1rem;
        margin-top: 0;
        margin-bottom: 0.5rem;
      }
      h3 {
        font-size: 0.95rem;
        margin: 0 0 0.5rem;
      }
      p {
        color: #111827;
        line-height: 1.5;
      }
      .card {
        background: #ffffff;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05);
        border: 1px solid #e5e7eb;
        margin-top: 24px;
      }
      .tab-bar {
        display: flex;
        gap: 8px;
        margin-top: 24px;
        border-bottom: 1px solid #e5e7eb;
        padding-bottom: 0;
      }
      .tab-btn {
        appearance: none;
        border: none;
        background: transparent;
        padding: 10px 18px;
        font-size: 0.9rem;
        font-weight: 600;
        color: #6b7280;
        cursor: pointer;
        border-bottom: 2px solid transparent;
        margin-bottom: -1px;
        transition: color 0.15s ease, border-color 0.15s ease;
      }
      .tab-btn:hover {
        color: #111827;
      }
      .tab-btn.active {
        color: #e60000;
        border-bottom-color: #e60000;
      }
      .tab-btn[data-tab="configuration"] {
        font-size: 1.15rem;
        font-weight: 700;
      }
      .tab-panel {
        display: none;
      }
      .tab-panel.active {
        display: block;
      }
      label {
        display: block;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 6px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #4b5563;
      }
      textarea, select, input[type="text"] {
        width: 100%;
        box-sizing: border-box;
        border-radius: 8px;
        border: 1px solid #d1d5db;
        padding: 10px 12px;
        font-size: 0.95rem;
        background: #ffffff;
        color: #111827;
        outline: none;
        transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
      }
      textarea:focus, select:focus, input[type="text"]:focus {
        border-color: #e60000;
        box-shadow: 0 0 0 1px rgba(230, 0, 0, 0.25);
        background: #ffffff;
      }
      textarea {
        min-height: 180px;
        resize: vertical;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      }
      .row {
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
        margin-top: 12px;
      }
      .col {
        flex: 1 1 0;
        min-width: 0;
      }
      .col-1-3 {
        flex: 0 0 33%;
      }
      .helper-text {
        font-size: 0.8rem;
        color: #6b7280;
        margin-top: 4px;
      }
      .btn-primary {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 10px 18px;
        border-radius: 999px;
        border: none;
        background: #e60000;
        color: #ffffff;
        font-weight: 600;
        font-size: 0.95rem;
        letter-spacing: 0.02em;
        cursor: pointer;
        margin-top: 20px;
        box-shadow: 0 10px 25px rgba(230, 0, 0, 0.35);
        transition: transform 0.1s ease, box-shadow 0.1s ease, filter 0.1s ease;
      }
      .btn-primary:hover {
        filter: brightness(1.05);
        transform: translateY(-1px);
        box-shadow: 0 14px 35px rgba(230, 0, 0, 0.45);
      }
      .btn-primary:active {
        transform: translateY(0);
        box-shadow: 0 8px 18px rgba(0, 0, 0, 0.2);
      }
      .btn-secondary {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 10px 18px;
        border-radius: 999px;
        border: 1px solid #d1d5db;
        background: #ffffff;
        color: #111827;
        font-weight: 600;
        font-size: 0.95rem;
        cursor: pointer;
        transition: border-color 0.15s ease, background 0.15s ease;
      }
      .btn-secondary:hover {
        border-color: #e60000;
        background: #fff5f5;
      }
      .btn-dark {
        background: #111827;
        color: #ffffff;
        box-shadow: 0 8px 20px rgba(17, 24, 39, 0.25);
      }
      .btn-dark:hover {
        filter: brightness(1.08);
        box-shadow: 0 12px 28px rgba(17, 24, 39, 0.35);
      }
      .button-row {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        margin-top: 20px;
      }
      .button-row .btn-primary,
      .button-row .btn-secondary,
      .button-row .btn-dark {
        margin-top: 0;
      }
      code {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        font-size: 0.85em;
        background: #f3f4f6;
        padding: 2px 5px;
        border-radius: 4px;
        border: 1px solid #e5e7eb;
      }
      .hidden {
        display: none !important;
      }
      .split-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
      }
      @media (max-width: 720px) {
        .split-grid {
          grid-template-columns: 1fr;
        }
      }
      .result-panel {
        border-radius: 10px;
        padding: 16px;
        margin-top: 16px;
      }
      .result-panel-add {
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
      }
      .result-panel-del {
        background: #fef2f2;
        border: 1px solid #fecaca;
      }
      .result-panel-warn {
        background: #fffbeb;
        border: 1px solid #fde68a;
      }
      .result-panel-special {
        background: #fff5f5;
        border: 1px solid #fecaca;
      }
      .result-panel-special h3 {
        color: #b91c1c;
        margin: 0 0 8px;
      }
      .result-panel-special p {
        color: #4b5563;
        margin: 0 0 8px;
        font-size: 0.85rem;
      }
      .result-list {
        margin: 0;
        padding-left: 1.1rem;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        font-size: 0.82rem;
        line-height: 1.6;
      }
      .radio-row {
        display: flex;
        gap: 20px;
        flex-wrap: wrap;
        margin-top: 8px;
      }
      .radio-row label.inline {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        text-transform: none;
        letter-spacing: normal;
        font-weight: 500;
        margin-bottom: 0;
      }
      .radio-row input[type="radio"] {
        width: auto;
      }
      .zip-banner {
        background: linear-gradient(135deg, #e60000, #b91c1c);
        color: #ffffff;
        border-radius: 12px;
        padding: 20px;
        margin-top: 20px;
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
        align-items: center;
        justify-content: space-between;
      }
      .zip-banner p {
        color: #fee2e2;
        margin: 0;
        font-size: 0.85rem;
        max-width: 560px;
      }
      .zip-banner code {
        background: rgba(0, 0, 0, 0.2);
        color: #ffffff;
        border: 1px solid rgba(255, 255, 255, 0.25);
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.8em;
      }
      .zip-banner .btn-primary,
      .zip-banner .btn-secondary {
        background: #ffffff;
        border-color: #ffffff;
        color: #b91c1c;
        margin-top: 0;
        box-shadow: none;
      }
      .zip-banner .btn-primary:hover,
      .zip-banner .btn-secondary:hover {
        background: #fff5f5;
        border-color: #ffffff;
        filter: none;
        transform: none;
      }
      .location-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 12px;
        font-size: 0.9rem;
      }
      .location-table th,
      .location-table td {
        padding: 8px 6px;
        text-align: left;
      }
      .location-table th {
        border-bottom: 1px solid #e5e7eb;
        color: #4b5563;
        font-weight: 600;
      }
      .location-table tr:nth-child(even) td {
        background: #fef2f2;
      }
    </style>
    
<script>
  function updatePbxVisibility() {
    const opSelect = document.getElementById('operation');
    const fromGroup = document.querySelector('.pbx-from-group');
    const toGroup = document.querySelector('.pbx-to-group');
    if (!opSelect || !fromGroup || !toGroup) return;

    const op = opSelect.value;
    if (op === 'ADD') {
      fromGroup.classList.add('hidden');
      toGroup.classList.remove('hidden');
    } else if (op === 'DELETE') {
      fromGroup.classList.remove('hidden');
      toGroup.classList.add('hidden');
    } else if (op === 'MOVE') {
      fromGroup.classList.remove('hidden');
      toGroup.classList.remove('hidden');
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    const opSelect = document.getElementById('operation');
    const form = document.getElementById('generator-form');
    if (opSelect) {
      opSelect.addEventListener('change', updatePbxVisibility);
      updatePbxVisibility();
    }
    if (form) {
      form.addEventListener('submit', function (event) {
        const fromPbx = document.getElementById('pbx_id_from');
        const toPbx = document.getElementById('pbx_id_to');
        const error = document.getElementById('provisioning-error');
        const requiredFields = opSelect.value === 'MOVE' ? [fromPbx, toPbx]
          : opSelect.value === 'DELETE' ? [fromPbx] : [toPbx];
        const invalidField = requiredFields.find(function (field) {
          return !/^[0-9]{7,}$/.test(field.value.trim());
        });
        if (invalidField) {
          event.preventDefault();
          const fieldName = invalidField === fromPbx ? 'Delete from PBX-ID' : 'Add to PBX-ID';
          error.textContent = fieldName + ' must contain at least 7 digits (numbers only).';
          error.classList.remove('hidden');
          invalidField.focus();
          return;
        }
        if (opSelect.value === 'MOVE' && fromPbx.value.trim() === toPbx.value.trim()) {
          event.preventDefault();
          error.textContent = 'You cannot move to the same PBX-ID';
          error.classList.remove('hidden');
          toPbx.focus();
          return;
        }
        error.classList.add('hidden');
        window.setTimeout(function () {
          form.reset();
          updatePbxVisibility();
        }, 900);
      });
    }
  });
</script>

  </head>
  <body>
    <div class="container">
      <header>
        <div style="display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;">
          <div style="display:flex;align-items:center;gap:12px;">
            <img src="/assets/Icon-88248495-6083-4dcf-8cb0-1d42d1fb34e3.png" alt="Vodafone logo" style="width:40px;height:40px;border-radius:50%;">
            <div>
              <h1>Provisioning Interface for NGIN Transactions</h1>
              <p>Import file generator for VOF NGIN and ENUM.</p>
            </div>
          </div>
        </div>
      </header>

      <nav class="tab-bar" role="tablist">
        <button type="button" class="tab-btn<?php if ($active_tab === 'provisioning'): ?> active<?php endif; ?>" data-tab="provisioning" role="tab">Provisioning</button>
        <button type="button" class="tab-btn<?php if ($active_tab === 'splitter'): ?> active<?php endif; ?>" data-tab="splitter" role="tab">Number Splitter</button>
        <button type="button" class="tab-btn<?php if ($active_tab === 'configuration'): ?> active<?php endif; ?>" data-tab="configuration" role="tab">Configuration</button>
      </nav>

      
<div class="tab-panel<?php if ($active_tab === 'provisioning'): ?> active<?php endif; ?>" data-tab-panel="provisioning">
  <div class="card">
    <form id="generator-form" method="post" action="/">
      <div id="provisioning-error" class="result-panel result-panel-warn<?php if (!($provisioning_error)): ?> hidden<?php endif; ?>" role="alert"><?= e($provisioning_error) ?></div>
      <div>
        <label for="numbers">Phone numbers</label>
        <textarea id="numbers" name="numbers" spellcheck="false" placeholder="Examples:
455688200
0455688200
+31455688200
45568820X"><?= e(form('numbers', '')) ?></textarea>
        <div class="helper-text">
          One number or number block per line. Wildcards like <code>45568820X</code> are supported and are <strong>not</strong> expanded in the CSV.
        </div>
      </div>

      <div class="row">
        <div class="col col-1-3">
          <label for="operation">Operation</label>
          <select id="operation" name="operation">
            <option value="ADD"<?php if (form('operation', 'ADD') === 'ADD'): ?> selected<?php endif; ?>>ADD → addPNP</option>
            <option value="DELETE"<?php if (form('operation') === 'DELETE'): ?> selected<?php endif; ?>>DELETE → deletePNP</option>
            <option value="MOVE"<?php if (form('operation') === 'MOVE'): ?> selected<?php endif; ?>>MOVE → deletePNP + addPNP</option>
          </select>
        </div>
        <div class="col pbx-from-group">
          <label for="pbx_id_from">Delete from PBX-ID</label>
          <input id="pbx_id_from" name="pbx_id_from" type="text" placeholder="e.g. 1000001" value="<?= e(form('pbx_id_from', '')) ?>">
        </div>
        <div class="col pbx-to-group">
          <label for="pbx_id_to">Add to PBX-ID</label>
          <input id="pbx_id_to" name="pbx_id_to" type="text" placeholder="e.g. 1000002" value="<?= e(form('pbx_id_to', '')) ?>">
        </div>
      </div>

      <div class="button-row">
        <button class="btn-primary" type="submit" name="output_format" value="csv">
          Generate NGIN file
        </button>
        <button class="btn-primary" type="submit" name="output_format" value="xlsx">
          Generate ENUM file
        </button>
      </div>
    </form>
  </div>
</div>

<div class="tab-panel<?php if ($active_tab === 'splitter'): ?> active<?php endif; ?>" data-tab-panel="splitter">
  <div class="card">
    <h2>Number Block Splitter</h2>
    <p class="helper-text" style="margin-top:0;">
      Split telecom number blocks by removing specific numbers or sub-ranges. Results can be exported as NGIN CSV files (add and delete).
    </p>

    <?php if ($splitter_error): ?>
    <div class="result-panel result-panel-warn">
      <strong>Could not calculate split</strong>
      <p style="margin:8px 0 0;"><?= e($splitter_error) ?></p>
    </div>
    <?php endif; ?>

    <form method="post" action="/splitter/calculate">
      <div class="split-grid">
        <div>
          <label for="sources">1. Blocks to split</label>
          <textarea id="sources" name="sources" spellcheck="false" placeholder="04556882xx
45568820x
08888450xx"><?= e($splitter_sources) ?></textarea>
          <div class="helper-text">One number block per line or comma-separated. Wildcards like <code>04556882xx</code> or <code>45568820x</code> are supported.</div>
        </div>
        <div>
          <label for="removes" style="color:#b91c1c;">2. Remove</label>
          <textarea id="removes" name="removes" spellcheck="false" placeholder="0455688250
455688250"><?= e($splitter_removes) ?></textarea>
          <div class="helper-text">Numbers or blocks to remove from the source ranges.</div>
        </div>
      </div>

      <div class="row" style="margin-top:16px;">
        <div class="col col-1-3">
          <label for="splitter_pbx_id">PBX-ID (for CSV export)</label>
          <input id="splitter_pbx_id" name="splitter_pbx_id" type="text" maxlength="7" placeholder="e.g. 1234567" value="<?= e($splitter_pbx_id) ?>">
          <div class="helper-text">Required for NGIN file generation. Applied to all rows.</div>
        </div>
      </div>

      <div class="button-row">
        <button class="btn-primary" type="submit">Generate NGIN file</button>
        <button class="btn-secondary" type="submit" formaction="/splitter/export-text" formmethod="post">Export RAW text</button>
      </div>
    </form>

    <?php if ($splitter_result): ?>
    <?php $invalid_sources = array_values(array_filter($splitter_result['parsed_sources'], fn($item) => !$item['is_valid'])); ?>
    <?php $invalid_removes = array_values(array_filter($splitter_result['parsed_removes'], fn($item) => !$item['is_valid'])); ?>
    <?php if (($invalid_sources || $invalid_removes)): ?>
    <div class="result-panel result-panel-warn">
      <strong>Some input lines could not be parsed</strong>
      <ul class="result-list">
        <?php foreach ($invalid_sources as $item): ?>
        <li>Source: <code><?= e($item['raw']) ?></code> — <?= e($item['error']) ?></li>
        <?php endforeach; ?>
        <?php foreach ($invalid_removes as $item): ?>
        <li>Remove: <code><?= e($item['raw']) ?></code> — <?= e($item['error']) ?></li>
        <?php endforeach; ?>
      </ul>
    </div>
    <?php endif; ?>

    <div class="result-panel result-panel-add">
      <h3>Step 1 — Add (retained blocks)</h3>
      <?php if ($splitter_add_blocks): ?>
      <ul class="result-list">
        <?php foreach ($splitter_add_blocks as $block): ?>
        <li><?= e($block) ?></li>
        <?php endforeach; ?>
      </ul>
      <?php else: ?>
      <p style="margin:0;font-size:0.85rem;">No retained blocks.</p>
      <?php endif; ?>
    </div>

    <div class="result-panel result-panel-del">
      <h3>Step 2 — Delete (parent blocks + removes)</h3>
      <?php if ($splitter_del_blocks): ?>
      <ul class="result-list">
        <?php foreach ($splitter_del_blocks as $block): ?>
        <li><?= e($block) ?></li>
        <?php endforeach; ?>
      </ul>
      <?php else: ?>
      <p style="margin:0;font-size:0.85rem;">No delete operations.</p>
      <?php endif; ?>
    </div>

    <form method="post" action="/splitter/download" id="splitter-download-form">
      <textarea name="sources" hidden><?= e($splitter_sources) ?></textarea>
      <textarea name="removes" hidden><?= e($splitter_removes) ?></textarea>
      <input type="hidden" name="splitter_pbx_id" value="<?= e($splitter_pbx_id) ?>">

      <?php if ($splitter_special_blocks): ?>
      <div class="result-panel result-panel-special">
        <h3>Select location for special-prefix blocks</h3>
        <p>
          The following ADD blocks use prefixes 050 / 0521 / 0522 / 0524 / 0527 / 0598 / 0599
          and need a manual PE location before download.
        </p>
        <table class="location-table">
          <thead>
            <tr>
              <th>Block</th>
              <th>Prefix</th>
              <th>Select location (PE code)</th>
            </tr>
          </thead>
          <tbody>
            <?php foreach ($splitter_special_blocks as $block): ?>
            <?php $locs = ($splitter_locations_by_prefix[$block['prefix']] ?? []); ?>
            <tr>
              <td><code><?= e($block['notation']) ?></code></td>
              <td><code><?= e($block['prefix']) ?></code></td>
              <td>
                <?php if ($locs): ?>
                <select name="spe_<?= e($block['lookup_key']) ?>" class="splitter-row-select" required>
                  <option value="">-- choose location --</option>
                  <?php foreach ($locs as $loc): ?>
                  <option value="<?= e($loc['pe_code']) ?>"
                          <?php if (($splitter_pe_overrides[$block['lookup_key']] ?? null) === $loc['pe_code']): ?>selected<?php endif; ?>>
                    <?= e($loc['city']) ?> (PE<?= e($loc['pe_code']) ?>)
                  </option>
                  <?php endforeach; ?>
                </select>
                <?php else: ?>
                <em>No locations configured (data/<?= e($block['prefix']) ?>_locations.txt)</em>
                <?php endif; ?>
              </td>
            </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
      <?php endif; ?>

      <div class="zip-banner">
        <div>
          <h3 style="color:#ffffff;margin-bottom:6px;">Download all CSV files as ZIP</h3>
          <p>Generates all <code>add&lt;PBX-ID&gt;.csv</code> and <code>del&lt;PBX-ID&gt;.csv</code> files in one package.</p>
        </div>
        <button class="btn-primary" type="submit">Download ZIP</button>
      </div>
    </form>
    <?php endif; ?>
  </div>
</div>
<div class="tab-panel<?php if ($active_tab === 'configuration'): ?> active<?php endif; ?>" data-tab-panel="configuration">
  <div class="card">
    <p>Coming soon</p>
  </div>
</div>

    </div>

    <script>
      function switchTab(tabName) {
        document.querySelectorAll('.tab-btn').forEach(function (btn) {
          btn.classList.toggle('active', btn.getAttribute('data-tab') === tabName);
        });
        document.querySelectorAll('.tab-panel').forEach(function (panel) {
          panel.classList.toggle('active', panel.getAttribute('data-tab-panel') === tabName);
        });
        var url = new URL(window.location.href);
        if (tabName === 'splitter' || tabName === 'configuration') {
          url.searchParams.set('tab', tabName);
        } else {
          url.searchParams.delete('tab');
        }
        window.history.replaceState({}, '', url);
      }

      document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.tab-btn').forEach(function (btn) {
          btn.addEventListener('click', function () {
            switchTab(btn.getAttribute('data-tab'));
          });
        });
      });
    </script>
    
<script>
  document.addEventListener('DOMContentLoaded', function () {
    <?php if ($active_tab === 'splitter'): ?>
    switchTab('splitter');
    <?php endif; ?>
  });
</script>

  </body>
</html>
