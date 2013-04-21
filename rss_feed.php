<?php
// Rename this script before usage. Anybody can add items to it, so keep the address secret.
// TODO: Adjust this variable. It must not be accessible from web
$DATA_PATH = "../rss_feed.data"

function read_items() {
    $lines = split("\n", file_get_contents($DATA_PATH));
    $items = Array();
    while (!empty($lines)) {
        $title = array_shift($lines);
	if (trim($title) == "")
	    break;
	$url = array_shift($lines);
        $items[] = Array($title, $url);
    }
    return $items;
}

function send_security_headers() {
    header('Access-Control-Allow-Origin: *');
    header('Access-Control-Allow-Methods: POST, OPTIONS');
    header('Access-Control-Allow-Headers: X-Requested-With');
    header('Access-Control-Max-Age: 180');
}

function write_items($items) {
    $data = "";
    foreach ($items as $item) {
        $data .= $item[0] . "\n" . $item[1] . "\n";
    }
    file_put_contents($DATA_PATH, $data);
}

if ($_SERVER["REQUEST_METHOD"] == "POST") {
    $items = read_items();
    $items[] = Array($_POST["title"], $_POST["url"]);
    if (count($items) > 100) {
        array_shift($items);
    }
    write_items($items);
    header("Status: 201 Created");
    send_security_headers();
    echo "Record added";
} else if ($_SERVER["REQUEST_METHOD"] == "OPTIONS") {
    send_security_headers();
} else {
    $items = read_items();

    echo '<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
        <title>Хабрахабр</title>
	        <language>ru</language>
';
    foreach ($items as $item) {
        echo "<item>\n    <title><![CDATA[" . $item[0] . "]]></title>\n    <link>" . $item[1] . "</link>\n</item>\n";
    }
    echo '</channel></rss>';
}
