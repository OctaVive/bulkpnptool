<?php
declare(strict_types=1);
require dirname(__DIR__).'/lib.php';
set_error_handler(function($severity,$message,$file,$line) { throw new ErrorException($message,0,$severity,$file,$line); });
$cases=json_decode(file_get_contents(__DIR__.'/fixtures.json'),true,512,JSON_THROW_ON_ERROR);
$failures=0;
foreach ($cases as $i=>$case) {
    $actual=$case['function'](...$case['args']);
    if ($actual != $case['expected']) {
        $failures++;
        echo "FAIL $i {$case['function']} ".json_encode($case['args'],JSON_UNESCAPED_UNICODE)."\n";
        echo 'Expected: '.json_encode($case['expected'],JSON_UNESCAPED_UNICODE)."\nActual: ".json_encode($actual,JSON_UNESCAPED_UNICODE)."\n";
    }
}
echo count($cases)." reference cases; $failures failures\n";
exit($failures ? 1 : 0);
