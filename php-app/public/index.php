<?php
declare(strict_types=1);
require dirname(__DIR__) . '/lib.php';

function render_index(array $values = [], int $status = 200): never {
    $defaults = ['active_tab'=>'provisioning', 'provisioning_error'=>'', 'splitter_sources'=>'', 'splitter_removes'=>'', 'splitter_pbx_id'=>'', 'splitter_result'=>null, 'splitter_error'=>'', 'splitter_pe_overrides'=>[]];
    extract(array_merge($defaults,$values));
    $splitter_add_blocks=[]; $splitter_del_blocks=[]; $splitter_special_blocks=[]; $splitter_locations_by_prefix=[];
    if ($splitter_result) {
        $splitter_add_blocks=array_map(fn($b)=>notation($b['start_number'],$b['size']),$splitter_result['resulting_modified_blocks']);
        $splitter_del_blocks=array_map(fn($b)=>notation($b['start_number'],$b['size']),delete_items($splitter_result));
        $splitter_special_blocks=special_blocks($splitter_result,$splitter_pe_overrides);
        $splitter_locations_by_prefix=locations();
    }
    http_response_code($status);
    require dirname(__DIR__).'/templates/index.php'; exit;
}
function download(string $data, string $filename, string $type): never {
    header('Content-Type: '.$type); header('Content-Disposition: attachment; filename="'.$filename.'"');
    header('Content-Length: '.strlen($data)); echo $data; exit;
}

$path=parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
if ($_SERVER['REQUEST_METHOD']==='GET' && $path==='/') {
    $tab=$_GET['tab'] ?? 'provisioning';
    render_index(['active_tab'=>in_array($tab,['provisioning','splitter','configuration'],true) ? $tab : 'provisioning']);
}
if ($_SERVER['REQUEST_METHOD']==='POST' && in_array($path,['/splitter/calculate','/splitter/export-text','/splitter/download'],true)) {
    $sources=form('sources'); $removes=form('removes'); $pbx=form('splitter_pbx_id');
    // Match the original conversion: preserve metadata spelling after its first separator.
    $lower=function(string $text): string {
        $parts=preg_split(METADATA_PATTERN,$text,2);
        return str_replace('X','x',$parts[0]).(isset($parts[1]) ? ' - '.$parts[1] : '');
    };
    $sourcesText=$lower($sources); $removesText=$lower($removes);
    $state=['active_tab'=>'splitter','splitter_sources'=>$sources,'splitter_removes'=>$removes,'splitter_pbx_id'=>$pbx];
    if ($path!=='/splitter/export-text' && !preg_match('/^[0-9]{7}$/D',trim($pbx))) render_index($state+['splitter_error'=>'Enter a valid 7-digit PBX-ID for CSV export.']);
    if ($path!=='/splitter/download' && !lines($sourcesText) && !lines($removesText)) render_index($state+['splitter_error'=>'Enter at least one source block or remove entry.']);
    $result=calculate_split(lines($sourcesText),lines($removesText));
    if ($path==='/splitter/export-text') download(raw_text($result),'split_result.txt','text/plain; charset=utf-8');
    $overrides=[];
    foreach ($_POST as $key=>$value) if (str_starts_with($key,'spe_') && is_string($value) && trim($value)!=='') $overrides[substr($key,4)]=trim($value);
    $state['splitter_result']=$result; $state['splitter_pe_overrides']=$overrides;
    if ($path==='/splitter/download') {
        if (special_blocks($result,$overrides)) render_index($state+['splitter_error'=>'Select a location (PE code) for each special-prefix block (050 / 0521 / 0522 / 0524 / 0527 / 0598 / 0599) before downloading.']);
        $files=splitter_files($result,trim($pbx),$overrides);
        if (!$files) render_index($state+['splitter_error'=>'No CSV rows could be generated for download. Check PE code resolution.']);
        download(zip_data($files),zip_filename($files),'application/zip');
    }
    $state['splitter_sources']=$sourcesText; $state['splitter_removes']=$removesText; $state['splitter_pbx_id']=trim($pbx);
    render_index($state);
}
if ($_SERVER['REQUEST_METHOD']==='POST' && $path==='/') {
    $numbers_raw=form('numbers'); $operation=strtoupper(form('operation','ADD'));
    $pbx_id_from=form('pbx_id_from'); $pbx_id_to=form('pbx_id_to');
    $required=[];
    if (in_array($operation,['DELETE','MOVE'],true)) $required['Delete from PBX-ID']=$pbx_id_from;
    if (in_array($operation,['ADD','MOVE'],true)) $required['Add to PBX-ID']=$pbx_id_to;
    foreach ($required as $name=>$value) if (!preg_match('/^[0-9]{7,}$/D',trim($value))) render_index(['provisioning_error'=>"$name must contain at least 7 digits (numbers only)."],400);
    if ($operation==='MOVE' && trim($pbx_id_from)===trim($pbx_id_to)) render_index(['provisioning_error'=>'You cannot move to the same PBX-ID'],400);
    if (strtolower(form('output_format','csv'))==='xlsx') download(xlsx_data($numbers_raw),'bulk_number_blocks.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    $parsed=parse_numbers($numbers_raw);
    $numbers_050=array_values(array_filter($parsed,fn($n)=>$n['lookup_national'] && special_prefix($n['lookup_national'])));
    if (in_array($operation,['ADD','MOVE'],true) && $numbers_050 && !form('confirm_050')) {
        $locations_by_prefix=locations();
        $prefixes=array_unique(array_map(fn($n)=>special_prefix($n['lookup_national']),$numbers_050));
        $bulk_locations=count($prefixes)===1 ? $locations_by_prefix[reset($prefixes)] : null;
        require dirname(__DIR__).'/templates/select_050.php'; exit;
    }
    $overrides=[];
    if (form('confirm_050')) foreach ($_POST as $key=>$value) if (str_starts_with($key,'pe_') && is_string($value)) $overrides[substr($key,3)]=$value;
    $rows=provisioning_rows($parsed,$operation,$pbx_id_from,$pbx_id_to,$overrides);
    $filename=match($operation) { 'ADD'=>'add'.$pbx_id_to.'.csv', 'DELETE'=>'del'.$pbx_id_from.'.csv', 'MOVE'=>'move'.$pbx_id_from.'to'.$pbx_id_to.'.csv', default=>'bulkpnp.csv' };
    // Only digits/spaces have passed validation, but remove whitespace in download names.
    download(csv_data($rows),preg_replace('/\s/','',$filename),'text/csv; charset=utf-8');
}
http_response_code(404); echo 'Not found';
