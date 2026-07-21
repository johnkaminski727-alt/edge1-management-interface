<?php
declare(strict_types=1);

require_once dirname(__DIR__) . '/bootstrap.php';
wwcx_require_user('admin');

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');

function respond(int $status, array $payload): never
{
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
    exit;
}

function read_secret_file(string $path): array
{
    if ($path === '' || !is_readable($path)) {
        throw new RuntimeException('Electrum integration is not configured');
    }

    $values = [];
    foreach (file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: [] as $line) {
        $line = trim($line);
        if ($line === '' || str_starts_with($line, '#') || !str_contains($line, '=')) {
            continue;
        }
        [$key, $value] = explode('=', $line, 2);
        $values[trim($key)] = trim($value);
    }
    return $values;
}

function fetch_json(string $baseUrl, string $path, string $token): array
{
    $url = rtrim($baseUrl, '/') . $path;
    $parts = parse_url($url);
    if (!is_array($parts) || ($parts['scheme'] ?? '') !== 'https' || empty($parts['host'])) {
        throw new RuntimeException('Electrum API must use HTTPS');
    }

    $context = stream_context_create([
        'http' => [
            'method' => 'GET',
            'timeout' => 8,
            'ignore_errors' => true,
            'follow_location' => 0,
            'max_redirects' => 0,
            'header' => "Authorization: Bearer {$token}\r\nAccept: application/json\r\nUser-Agent: WWCX-Admin-Electrum/1.0\r\n",
        ],
        'ssl' => [
            'verify_peer' => true,
            'verify_peer_name' => true,
        ],
    ]);

    $body = @file_get_contents($url, false, $context, 0, 1048576);
    if ($body === false) {
        throw new RuntimeException('Electrum API is unavailable');
    }

    $status = 0;
    foreach ($http_response_header ?? [] as $header) {
        if (preg_match('/^HTTP\/\S+\s+(\d{3})/', $header, $match)) {
            $status = (int) $match[1];
        }
    }
    if ($status !== 200) {
        throw new RuntimeException('Electrum API returned an error');
    }

    $payload = json_decode($body, true, 32, JSON_THROW_ON_ERROR);
    if (!is_array($payload) || ($payload['ok'] ?? false) !== true || !array_key_exists('result', $payload)) {
        throw new RuntimeException('Electrum API response is invalid');
    }

    return is_array($payload['result']) ? $payload['result'] : ['value' => $payload['result']];
}

if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'GET') {
    header('Allow: GET');
    respond(405, ['ok' => false, 'error' => 'Method not allowed']);
}

try {
    $secretPath = getenv('WWCX_ELECTRUM_ENV') ?: dirname(__DIR__, 3) . '/private/electrum.env';
    $config = read_secret_file($secretPath);
    $baseUrl = $config['ELECTRUM_API_BASE_URL'] ?? '';
    $token = $config['ELECTRUM_API_TOKEN'] ?? '';
    if ($baseUrl === '' || strlen($token) < 32) {
        throw new RuntimeException('Electrum integration is not configured');
    }

    $info = fetch_json($baseUrl, '/v1/wallet/info', $token);
    $balance = fetch_json($baseUrl, '/v1/wallet/balance', $token);
    respond(200, [
        'ok' => true,
        'generated_at' => gmdate('c'),
        'info' => $info,
        'balance' => $balance,
    ]);
} catch (Throwable $error) {
    error_log('WW.CX Electrum admin proxy: ' . $error->getMessage());
    respond(502, ['ok' => false, 'error' => 'Electrum status is unavailable']);
}
