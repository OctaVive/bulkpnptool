<?php
declare(strict_types=1);

const SPECIAL_PREFIXES = ['050', '0521', '0522', '0524', '0527', '0598', '0599'];
const METADATA_PATTERN = '/\s+-\s+(?=PBX:|Locatie:|Location:)/i';

function e(mixed $value): string { return htmlspecialchars((string)($value ?? ''), ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function form(string $key, string $default = ''): string { return is_string($_POST[$key] ?? null) ? $_POST[$key] : $default; }
function lines(string $raw): array { return array_values(array_filter(array_map('trim', preg_split('/[\n,]+/', $raw)), fn($s) => $s !== '')); }
function special_prefix(string $number): ?string {
    foreach (SPECIAL_PREFIXES as $prefix) if (str_starts_with($number, $prefix)) return $prefix;
    return null;
}
function normalize_number(string $raw): string {
    $s = trim($raw);
    if (str_starts_with($s, '+31')) $s = '0' . substr($s, 3);
    $s = strtolower(preg_replace('/[^0-9xX]/', '', $s));
    if (str_starts_with($s, '0031')) $s = '0' . substr($s, 4);
    elseif (str_starts_with($s, '31') && !str_starts_with($s, '310')) $s = '0' . substr($s, 2);
    if (strlen($s) === 9 && !str_starts_with($s, '0')) $s = '0' . $s;
    return $s;
}
function resolve_pe(string $number): ?string {
    static $mapping = null, $local = [];
    if ($mapping === null) {
        $mapping = [];
        foreach (file(__DIR__ . '/data/pe_codes.txt', FILE_IGNORE_NEW_LINES) as $line) {
            $parts = array_map('trim', explode(';', trim($line)));
            if (count($parts) < 2 || str_starts_with($parts[0], '#') || !$parts[0] || !$parts[1] || $parts[0] === '050') continue;
            [$prefix, $code] = $parts;
            $mapping[$prefix] = $code;
            if (strlen($prefix) === 3 && str_starts_with($prefix, '0')) $local[substr($prefix, 1)] ??= $code;
        }
    }
    if (strlen($number) < 3 || str_starts_with($number, '050')) return null;
    foreach ([$number, '0' . $number] as $candidate) {
        foreach ([4, 3] as $length) if (isset($mapping[substr($candidate, 0, $length)])) return $mapping[substr($candidate, 0, $length)];
        if (str_starts_with($number, '0')) break;
    }
    $digits = preg_replace('/\D/', '', $number);
    if (str_starts_with($digits, '0')) $digits = substr($digits, 1);
    return $local[substr($digits, 0, 2)] ?? null;
}
function locations(): array {
    $all = [];
    foreach (SPECIAL_PREFIXES as $prefix) {
        $all[$prefix] = [];
        foreach (file(__DIR__ . "/data/{$prefix}_locations.txt", FILE_IGNORE_NEW_LINES) as $line) {
            $parts = array_map('trim', explode(';', trim($line)));
            if (count($parts) < 2 || !$parts[0] || !$parts[1] || str_starts_with($parts[0], '#')) continue;
            $all[$prefix][] = ['city' => $parts[0], 'pe_code' => $parts[1]];
        }
        usort($all[$prefix], fn($a, $b) => strcasecmp($a['city'], $b['city']));
    }
    return $all;
}
function parse_numbers(string $raw): array {
    $result = [];
    foreach (preg_split('/\R/', $raw) as $line) {
        $line = trim($line);
        if ($line === '') continue;
        $s = str_starts_with($line, '+31') ? '0' . substr($line, 3) : $line;
        $clean = preg_replace('/[^0-9xX]/', '', $s);
        $wild = stripos($clean, 'x') !== false;
        if (str_starts_with($clean, '0031')) $clean = '0' . substr($clean, 4);
        elseif (str_starts_with($clean, '31')) $clean = '0' . substr($clean, 2);
        $lookup = str_ireplace('x', '0', $clean);
        if (str_starts_with($lookup, '50') || strlen($lookup) === 9) $lookup = '0' . $lookup;
        if (strlen($lookup) < 3) $lookup = null;
        $export = preg_replace('/[^0-9xX]/', '', $line);
        if ($lookup && special_prefix($lookup)) {
            if (!$wild) $export = strlen($lookup) >= 10 ? substr($lookup, 1, 9) : (strlen($lookup) === 9 ? substr($lookup, 1) : $lookup);
            elseif (strlen($export) >= 10 && str_starts_with($export, '0')) $export = substr($export, 1, 9);
            elseif (strlen($export) >= 9) $export = substr($export, -9);
        } elseif (strlen($export) >= 9) $export = substr($export, -9);
        $result[] = ['raw_input' => $line, 'is_wildcard' => $wild, 'lookup_national' => $lookup, 'export_value' => $export ?: $line];
    }
    return $result;
}
function csv_data(array $rows, string $eol = "\n"): string {
    $stream = fopen('php://temp', 'r+');
    foreach ($rows as $row) fputcsv($stream, $row, ';', '"', '', $eol);
    rewind($stream); $data = stream_get_contents($stream); fclose($stream); return $data;
}
function provisioning_rows(array $numbers, string $operation, string $from, string $to, array $overrides): array {
    $rows = [];
    foreach ($numbers as $item) {
        $lookup = $item['lookup_national'];
        if (!$lookup) continue;
        $pe = $operation === 'DELETE' ? '00' : (special_prefix($lookup) ? ($overrides[$lookup] ?? null) : resolve_pe($lookup));
        if (!$pe) continue;
        $actions = match ($operation) { 'ADD' => [['addPNP', $to]], 'DELETE' => [['deletePNP', $from]], 'MOVE' => [['deletePNP', $from], ['addPNP', $to]], default => [] };
        foreach ($actions as [$action, $pbx]) $rows[] = [strval(count($rows) + 1), $action, $item['export_value'], $pe, $pbx];
    }
    return $rows;
}
function notation(string $start, int $size): string {
    $start = substr(str_pad(str_replace('x', '0', normalize_number($start)), 10, '0', STR_PAD_LEFT), 0, 10);
    $wildcards = (int)log10($size);
    return $wildcards ? substr($start, 0, 10 - $wildcards) . str_repeat('x', $wildcards) : $start;
}
function parse_block(string $line): array {
    $raw = trim($line);
    $parts = preg_split(METADATA_PATTERN, $raw, 2);
    $token = trim($parts[0]); $metadata = isset($parts[1]) ? ' - ' . trim($parts[1]) : '';
    $normalized = normalize_number($token); $start = ''; $size = 1; $error = null;
    if (!$raw) $error = 'Empty line';
    elseif (!$normalized) $error = 'No recognizable number or block';
    elseif (str_contains($token, '-') && !str_contains($normalized, 'x')) {
        [$beg, $end] = array_map(fn($s) => normalize_number(trim($s)), explode('-', $token, 2));
        if (!$beg || !$end || str_contains($beg . $end, 'x')) $error = 'Invalid range endpoints';
        elseif (strlen($beg) !== 10 || strlen($end) !== 10) $error = 'Range endpoints must be 10 digits';
        elseif ((int)$end < (int)$beg) $error = 'Range end must be greater than or equal to start';
        else {
            $span = (int)$end - (int)$beg + 1;
            if (!in_array($span, [1,10,100,1000,10000], true)) $error = "Range span $span is not a valid telecom block size";
            elseif ((int)$beg % $span !== 0) $error = "Range start is not aligned for block size $span";
            else { $start = $beg; $size = $span; }
        }
    } elseif (str_contains($normalized, 'x')) {
        if (strlen($normalized) === 10 && !str_starts_with($normalized, '0')) {
            if (preg_match('/^(\d{7})0(xx)$/', $normalized, $m)) $normalized = '0' . $m[1] . $m[2];
            else $normalized = '0' . substr($normalized, -9);
        }
        $count = substr_count($normalized, 'x');
        if ($count < 1 || $count > 4) $error = 'Wildcard count must be 1, 2, 3, or 4';
        elseif (!str_ends_with($normalized, str_repeat('x', $count))) $error = 'Wildcards must be trailing';
        elseif (strlen($normalized) !== 10) $error = 'Wildcard block must resolve to 10 digits';
        else { $start = str_replace('x', '0', $normalized); $size = 10 ** $count; }
    } elseif (strlen($normalized) === 10 && ctype_digit($normalized)) $start = $normalized;
    else $error = 'Could not determine block size';
    return ['raw' => $raw, 'start_number' => $start, 'size' => $size, 'is_valid' => $error === null && $start !== '', 'error' => $error, 'pbx_comment' => $metadata];
}
function subtract_removes(int $start, int $size, array $removes): array {
    $remaining = [[$start, $start + $size - 1]];
    foreach ($removes as $r) {
        $next = []; $rs = (int)$r['start_number']; $re = $rs + $r['size'] - 1;
        foreach ($remaining as [$a, $b]) {
            if ($rs > $b || $re < $a) $next[] = [$a,$b];
            else { if ($a < $rs) $next[] = [$a,$rs-1]; if ($b > $re) $next[] = [$re+1,$b]; }
        }
        $remaining = $next;
    }
    $blocks = [];
    foreach ($remaining as [$a,$b]) while ($a <= $b) {
        foreach ([10000,1000,100,10,1] as $n) if ($a % $n === 0 && $a + $n - 1 <= $b) break;
        $blocks[] = [$a,$n]; $a += $n;
    }
    return [$blocks, $remaining !== [[$start, $start + $size - 1]]];
}
function final_block(array $item, array $fallback): array {
    return ['start_number'=>$item['start_number'], 'size'=>$item['size'], 'formatted'=>notation($item['start_number'], $item['size']), 'source_metadata'=>$item['pbx_comment'] ?: $fallback['pbx_comment']];
}
function containing_source(array $block, array $sources): ?array {
    foreach ($sources as $s) if ($s['is_valid'] && (int)$block['start_number'] >= (int)$s['start_number'] && (int)$block['start_number'] + $block['size'] <= (int)$s['start_number'] + $s['size']) return $s;
    return null;
}
function calculate_split(array $sources, array $removes): array {
    $ps = array_map('parse_block', $sources); $pr = array_map('parse_block', $removes);
    $valid = array_values(array_filter($pr, fn($i) => $i['is_valid']));
    $result = ['parsed_sources'=>$ps, 'parsed_removes'=>$pr, 'resulting_blocks'=>[], 'modified_sources'=>[], 'resulting_modified_blocks'=>[]];
    foreach ($ps as $source) {
        if (!$source['is_valid']) continue;
        [$retained, $modified] = subtract_removes((int)$source['start_number'], $source['size'], $valid);
        if ($modified) $result['modified_sources'][] = $source;
        foreach ($retained as [$start,$size]) {
            $item = $source; $item['start_number'] = str_pad((string)$start, 10, '0', STR_PAD_LEFT); $item['size'] = $size;
            $block = final_block($item, $source);
            $result['resulting_modified_blocks'][] = $block; $result['resulting_blocks'][] = $block;
        }
    }
    foreach ($valid as $remove) $result['resulting_blocks'][] = final_block($remove, containing_source($remove, $ps) ?? $remove);
    return $result;
}
function delete_items(array $result): array {
    $parents = array_values(array_filter($result['modified_sources'], fn($s) => $s['size'] > 1));
    $items = array_map(fn($s) => final_block($s,$s), $parents);
    foreach ($result['parsed_removes'] as $r) {
        if (!$r['is_valid'] || containing_source($r, $parents)) continue;
        $items[] = final_block($r, containing_source($r, $result['parsed_sources']) ?? $r);
    }
    $seen = []; $unique = [];
    foreach ($items as $item) { $key = $item['start_number'].'_'.$item['size']; if (isset($seen[$key])) continue; $seen[$key]=true; $unique[]=$item; }
    return $unique;
}
function special_blocks(array $result, array $overrides = []): array {
    $items=[]; $seen=[];
    foreach (array_merge($result['modified_sources'], $result['parsed_sources']) as $s) {
        if (!$s['is_valid']) continue;
        $key='source_'.$s['start_number'].'_'.$s['size']; $prefix=special_prefix($s['start_number']);
        if (!$prefix || isset($seen[$key]) || !empty($overrides[$key])) continue;
        $seen[$key]=true; $items[]=['notation'=>notation($s['start_number'],$s['size']), 'lookup_key'=>$key, 'lookup_national'=>$s['start_number'], 'prefix'=>$prefix];
    }
    return $items;
}
function splitter_files(array $result, string $pbx, array $overrides): array {
    $files=[];
    foreach (['add'=>$result['resulting_modified_blocks'], 'del'=>delete_items($result)] as $kind=>$blocks) {
        $groups=[];
        foreach ($blocks as $block) {
            preg_match('/PBX:\s*(\d{7})/i', $block['source_metadata'], $match);
            $id=$match[1] ?? $pbx;
            $pe='00';
            if ($kind === 'add') {
                if (special_prefix($block['start_number'])) {
                    $candidates=array_filter($result['parsed_sources'], fn($s) => $s['is_valid'] && special_prefix($s['start_number']) && containing_source($block,[$s]));
                    usort($candidates, fn($a,$b) => $a['size'] <=> $b['size']);
                    $s=$candidates[0] ?? null;
                    $pe=$s ? ($overrides['source_'.$s['start_number'].'_'.$s['size']] ?? null) : ($overrides[$block['start_number'].'_'.$block['size']] ?? null);
                } else $pe=resolve_pe($block['start_number']);
            }
            if ($pe === null) continue;
            $groups[$id] ??= [];
            $phone=notation($block['start_number'],$block['size']);
            if (str_starts_with($phone,'0')) $phone=substr($phone,1);
            $groups[$id][]=[strval(count($groups[$id])+1), $kind === 'add' ? 'addPNP' : 'deletePNP', $phone, $pe, (string)$id];
        }
        foreach ($groups as $id=>$rows) $files[$kind.$id.'.csv']=csv_data($rows,"\r\n");
    }
    return $files;
}
function zip_filename(array $files): string {
    $ids=[]; foreach (array_keys($files) as $name) $ids[]=substr($name,3,-4);
    $ids=array_unique($ids); sort($ids,SORT_STRING); $parts=[];
    foreach ($ids as $id) foreach (['add','del'] as $kind) if (isset($files[$kind.$id.'.csv'])) $parts[]=$kind.$id;
    return $parts ? implode('_',$parts).'.zip' : 'splitter_export.zip';
}
function raw_text(array $result): string {
    $remove=array_map(fn($i) => $i['is_valid'] ? notation($i['start_number'],$i['size']) : $i['raw'], $result['parsed_removes']);
    $add=array_map(fn($i) => notation($i['start_number'],$i['size']), $result['resulting_modified_blocks']);
    $delete=array_map(fn($i) => notation($i['start_number'],$i['size']), delete_items($result));
    return implode("\n",array_merge(['To be removed',''], $remove ?: ['(none)'], ['', 'Step 1 — Add (retained blocks)',''], $add ?: ['(none)'], ['', 'Step 2 — Delete (parent blocks + removes)',''], $delete ?: ['(none)']))."\n";
}

// ZIP store format needs no extension; used for CSV bundles and OOXML workbooks.
function zip_data(array $files): string {
    $body=''; $directory=''; $count=0;
    foreach ($files as $name=>$data) {
        $offset=strlen($body); $length=strlen($data); $crc=crc32($data); $nl=strlen($name);
        $body.=pack('VvvvvvVVVvv',0x04034b50,20,0,0,0,33,$crc,$length,$length,$nl,0).$name.$data;
        $directory.=pack('VvvvvvvVVVvvvvvVV',0x02014b50,20,20,0,0,0,33,$crc,$length,$length,$nl,0,0,0,0,0,$offset).$name;
        $count++;
    }
    return $body.$directory.pack('VvvvvVVv',0x06054b50,0,0,$count,$count,strlen($directory),strlen($body),0);
}
function xlsx_data(string $raw): string {
    $rows=[['BlockType','Block']];
    foreach (preg_split('/\R/',$raw) as $line) {
        $s=trim($line); if (str_starts_with($s,'+31')) $s='0'.substr($s,3);
        $s=strtolower(preg_replace('/[^0-9xX]/','',$s));
        if (str_starts_with($s,'0031')) $s='0'.substr($s,4);
        elseif (str_starts_with($s,'31')) $s='0'.substr($s,2);
        if (strlen($s)===9 && !str_starts_with($s,'0')) $s='0'.$s;
        if (!$s) continue;
        $wild=substr_count($s,'x'); $rows[]=[$wild ? (10**$wild).' numbers' : 'Single number',$s];
    }
    $sheet='<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>';
    foreach ($rows as $i=>$row) {
        $n=$i+1; $sheet.='<row r="'.$n.'">';
        foreach ($row as $j=>$value) $sheet.='<c r="'.chr(65+$j).$n.'" t="inlineStr" s="'.($i===0 ? '1':'0').'"><is><t>'.e($value).'</t></is></c>';
        $sheet.='</row>';
    }
    $sheet.='</sheetData></worksheet>';
    return zip_data([
        '[Content_Types].xml'=>'<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        '_rels/.rels'=>'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml'=>'<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Blocks" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels'=>'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        'xl/styles.xml'=>'<?xml version="1.0"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFE60000"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
        'xl/worksheets/sheet1.xml'=>$sheet,
    ]);
}
