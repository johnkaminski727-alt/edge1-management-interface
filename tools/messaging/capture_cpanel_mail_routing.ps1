[CmdletBinding()]
param(
    [string] $CpanelHost = 'business159.web-hosting.com',
    [string] $CpanelUser = 'wwcxjywl',

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string[]] $Domain,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $OutputDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Test-InGitWorkTree {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    $FullPath = [IO.Path]::GetFullPath($Path)
    $Current = New-Object IO.DirectoryInfo($FullPath)

    if (-not $Current.Exists) {
        $Current = $Current.Parent
    }

    while ($null -ne $Current) {
        if (Test-Path -LiteralPath (Join-Path $Current.FullName '.git')) {
            return $true
        }

        $Current = $Current.Parent
    }

    return $false
}

function New-QueryString {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable] $Parameters
    )

    $Pairs = foreach ($Entry in ($Parameters.GetEnumerator() | Sort-Object Key)) {
        '{0}={1}' -f `
            [Uri]::EscapeDataString([string] $Entry.Key),
            [Uri]::EscapeDataString([string] $Entry.Value)
    }

    return ($Pairs -join '&')
}

function Invoke-GetMxCheck {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ExpectedDomain,

        [Parameter(Mandatory = $true)]
        [hashtable] $Headers,

        [Parameter(Mandatory = $true)]
        [string] $BaseUri
    )

    $Query = New-QueryString -Parameters @{
        cpanel_jsonapi_user       = $CpanelUser
        cpanel_jsonapi_apiversion = '2'
        cpanel_jsonapi_module     = 'Email'
        cpanel_jsonapi_func       = 'getmxcheck'
        domain                    = $ExpectedDomain
    }

    $Uri = $BaseUri + '?' + $Query

    try {
        $Response = Invoke-WebRequest `
            -Uri $Uri `
            -Method Get `
            -Headers $Headers `
            -UseBasicParsing `
            -TimeoutSec 60
    }
    catch {
        throw "cPanel API 2 getmxcheck failed for ${ExpectedDomain}: $($_.Exception.Message)"
    }

    if ($Response.StatusCode -ne 200) {
        throw "HTTP $($Response.StatusCode) returned for ${ExpectedDomain}."
    }

    try {
        $Parsed = $Response.Content | ConvertFrom-Json
    }
    catch {
        throw "Invalid JSON returned for ${ExpectedDomain}."
    }

    if (-not ($Parsed.PSObject.Properties.Name -contains 'cpanelresult')) {
        throw "Missing cpanelresult object for ${ExpectedDomain}."
    }

    $Result = $Parsed.cpanelresult

    if (
        -not ($Result.PSObject.Properties.Name -contains 'event') -or
        -not ($Result.event.PSObject.Properties.Name -contains 'result') -or
        [int] $Result.event.result -ne 1
    ) {
        throw "cPanel API 2 did not report success for ${ExpectedDomain}."
    }

    $Rows = @($Result.data)

    if ($Rows.Count -ne 1) {
        throw "Expected exactly one getmxcheck row for ${ExpectedDomain}."
    }

    $ReturnedDomain = ([string] $Rows[0].domain).Trim().ToLowerInvariant()
    $Mode = ([string] $Rows[0].mxcheck).Trim().ToLowerInvariant()

    if ($ReturnedDomain -ne $ExpectedDomain) {
        throw "getmxcheck returned domain '${ReturnedDomain}' while '${ExpectedDomain}' was requested."
    }

    if ($Mode -notin @('auto', 'local', 'remote', 'secondary')) {
        throw "Unsupported getmxcheck mode '${Mode}' for ${ExpectedDomain}."
    }

    return [string] $Response.Content
}

$NormalizedDomains = @(
    $Domain |
        ForEach-Object { $_.Trim().ToLowerInvariant() } |
        Where-Object { $_ -ne '' } |
        Sort-Object -Unique
)

if ($NormalizedDomains.Count -eq 0) {
    throw 'At least one domain is required.'
}

foreach ($Item in $NormalizedDomains) {
    if ($Item -notmatch '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$') {
        throw "Invalid domain: $Item"
    }
}

$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)

if (Test-InGitWorkTree -Path $OutputDirectory) {
    throw 'Refusing to store provider routing evidence inside a Git working tree.'
}

if (Test-Path -LiteralPath $OutputDirectory) {
    throw "Output directory already exists: $OutputDirectory"
}

$ParentDirectory = Split-Path -Parent $OutputDirectory
New-Item -ItemType Directory -Path $ParentDirectory -Force | Out-Null

$BaseUri = "https://${CpanelHost}:2083/json-api/cpanel"
$SecureToken = $null
$ApiToken = $null
$TokenPointer = [IntPtr]::Zero
$Headers = $null
$StagingDirectory = $OutputDirectory + '.partial-' + [Guid]::NewGuid().ToString('N')
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

try {
    $SecureToken = Read-Host 'Paste the temporary cPanel API token' -AsSecureString
    $TokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureToken)
    $ApiToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($TokenPointer)

    if ([string]::IsNullOrWhiteSpace($ApiToken)) {
        throw 'No API token was entered.'
    }

    $Headers = @{
        Authorization = ('cpanel {0}:{1}' -f $CpanelUser, $ApiToken)
        Accept        = 'application/json'
    }

    Write-Host 'Testing cPanel API-token authentication with read-only getmxcheck...'

    $null = Invoke-GetMxCheck `
        -ExpectedDomain $NormalizedDomains[0] `
        -Headers $Headers `
        -BaseUri $BaseUri

    Write-Host 'Authentication and read-only probe succeeded.'

    New-Item -ItemType Directory -Path $StagingDirectory -Force | Out-Null

    foreach ($Item in $NormalizedDomains) {
        Write-Host "Capturing mail-routing mode for $Item..."

        $RawJson = Invoke-GetMxCheck `
            -ExpectedDomain $Item `
            -Headers $Headers `
            -BaseUri $BaseUri

        $SafeDomain = $Item.Replace('.', '_')
        $FinalFile = Join-Path $StagingDirectory "getmxcheck-${SafeDomain}.json"
        $TemporaryFile = $FinalFile + '.tmp'

        [IO.File]::WriteAllText(
            $TemporaryFile,
            $RawJson + [Environment]::NewLine,
            $Utf8NoBom
        )

        Move-Item -LiteralPath $TemporaryFile -Destination $FinalFile
    }

    $Sha256 = [Security.Cryptography.SHA256]::Create()

    try {
        $UserHashBytes = $Sha256.ComputeHash(
            [Text.Encoding]::UTF8.GetBytes($CpanelUser)
        )
    }
    finally {
        $Sha256.Dispose()
    }

    $UserHash = (
        $UserHashBytes |
            ForEach-Object { $_.ToString('x2') }
    ) -join ''

    $Metadata = [ordered]@{
        contract           = 'wwcx.cpanel-mail-routing-evidence.v1'
        captured_at        = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        read_only          = $true
        cpanel_host        = $CpanelHost
        cpanel_user_sha256 = $UserHash
        domains            = $NormalizedDomains
        transport          = 'https-cpanel-api-token'
        api_family         = 'cpanel-api-2'
        function           = 'Email::getmxcheck'
        sensitivity        = 'restricted-operational-metadata'
    }

    [IO.File]::WriteAllText(
        (Join-Path $StagingDirectory 'metadata.json'),
        ($Metadata | ConvertTo-Json -Depth 10) + [Environment]::NewLine,
        $Utf8NoBom
    )

    $ManifestLines = Get-ChildItem -LiteralPath $StagingDirectory -Filter '*.json' |
        Sort-Object Name |
        ForEach-Object {
            $Hash = (
                Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
            ).Hash.ToLowerInvariant()

            '{0}  {1}' -f $Hash, $_.Name
        }

    [IO.File]::WriteAllLines(
        (Join-Path $StagingDirectory 'SHA256SUMS'),
        [string[]] $ManifestLines,
        [Text.Encoding]::ASCII
    )

    Move-Item -LiteralPath $StagingDirectory -Destination $OutputDirectory

    Write-Host
    Write-Host 'Mail-routing capture completed successfully.'
    Write-Host "Evidence directory: $OutputDirectory"
    Write-Host

    Get-ChildItem -LiteralPath $OutputDirectory |
        Sort-Object Name |
        Select-Object Name, Length
}
finally {
    $Headers = $null
    $ApiToken = $null
    $SecureToken = $null

    if ($TokenPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($TokenPointer)
    }

    if (Test-Path -LiteralPath $StagingDirectory) {
        Remove-Item -LiteralPath $StagingDirectory -Recurse -Force
    }

    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
