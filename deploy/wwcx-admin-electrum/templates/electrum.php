<?php
declare(strict_types=1);

require_once __DIR__ . '/bootstrap.php';
wwcx_require_user('admin');

header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');

$pageTitle = 'Electrum Console';
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title><?= htmlspecialchars($pageTitle, ENT_QUOTES, 'UTF-8') ?> | WW.CX Admin</title>
  <style>
    :root { color-scheme: light dark; font-family: system-ui, sans-serif; }
    body { margin: 0; background: #10151c; color: #eef3f8; }
    main { max-width: 1100px; margin: 0 auto; padding: 24px; }
    .header { display: flex; gap: 16px; align-items: center; justify-content: space-between; flex-wrap: wrap; }
    .grid { display: grid; grid-template