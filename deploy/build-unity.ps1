[CmdletBinding()]
param(
    [string]$SourceDir,
    [string]$UnityEditor,
    [switch]$AllowCompatibleEditor
)
$ErrorActionPreference = 'Stop'
if (-not $SourceDir) { $SourceDir = Split-Path $PSScriptRoot -Parent }
$SourceDir = (Resolve-Path -LiteralPath $SourceDir).Path
$original = Join-Path $SourceDir 'unity\TEP-DigitalTwin-Unity'
$expected = ((Get-Content (Join-Path $original 'ProjectSettings\ProjectVersion.txt') | Select-String '^m_EditorVersion:').Line -split ':',2)[1].Trim()
if (-not $UnityEditor) {
    $UnityEditor = $env:TEP_UNITY_EDITOR
    if (-not $UnityEditor) { $UnityEditor = Join-Path $env:ProgramFiles "Unity\Hub\Editor\$expected\Editor\Unity.exe" }
}
if (-not (Test-Path -LiteralPath $UnityEditor)) { throw "Unity editor not found. Set TEP_UNITY_EDITOR or pass -UnityEditor." }
$version = (Get-Item -LiteralPath $UnityEditor).VersionInfo.ProductVersion
$compatible = -not $version.StartsWith($expected)
if ($compatible -and -not $AllowCompatibleEditor) { throw "Expected Unity $expected. A compatible isolated build requires -AllowCompatibleEditor." }
$output = Join-Path $SourceDir 'web\public\unity'
$logDir = Join-Path $SourceDir 'logs\unity-build'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$hashInputs = @(Get-ChildItem (Join-Path $original 'Assets\TEP') -Recurse -File)
$hashInputs += @(Get-ChildItem (Join-Path $original 'ProjectSettings') -File)
$hashInputs += @(Get-ChildItem (Join-Path $original 'Packages') -File)
$hashText = ($hashInputs | Sort-Object FullName | ForEach-Object { $_.FullName.Substring($original.Length) + ':' + (Get-FileHash $_.FullName -Algorithm SHA256).Hash }) -join "`n"
$hashText += "`n$version`n$compatible`nrecipe:" + (Get-FileHash $PSCommandPath -Algorithm SHA256).Hash
$fixture = Join-Path $SourceDir 'reports\06-final-model\sample_prediction.json'
$hashText += "`nfixture:" + (Get-FileHash $fixture -Algorithm SHA256).Hash
$sha = [Security.Cryptography.SHA256]::Create()
$sourceHash = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($hashText))).Replace('-','').ToLowerInvariant()
$manifestPath = Join-Path $output 'build-info.json'
if (Test-Path -LiteralPath $manifestPath) {
    $prior = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
    $valid = $prior.source_sha256 -eq $sourceHash
    foreach ($item in $prior.files) {
        $file = Join-Path $output $item.name
        if (-not (Test-Path -LiteralPath $file) -or (Get-FileHash $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.sha256) { $valid = $false }
    }
    if ($valid -and @($prior.files).Count -ge 4) { Write-Host "[UNITY] Verified cached WebGL build ($version)."; exit 0 }
}
$project = $original
if ($compatible) {
    # Keep the source project's version, packages and renderer untouched.
    $project = Join-Path $logDir 'compatible-project'
    $runtimeDir = Join-Path $project 'Assets\TEP\Scripts\Runtime'
    $editorDir = Join-Path $project 'Assets\TEP\Scripts\Editor'
    $resourceDir = Join-Path $project 'Assets\TEP\Resources'
    $pluginDir = Join-Path $project 'Assets\TEP\Plugins\WebGL'
    foreach ($dir in @($runtimeDir,$editorDir,$resourceDir,$pluginDir,(Join-Path $project 'Packages'),(Join-Path $project 'ProjectSettings'))) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    foreach ($name in @('DigitalTwinController','PredictionModels','PredictionSource','WebPredictionBridge','ProcessOverview','KoreanUi','DashboardPanel','EquipmentView','StatusPalette')) {
        foreach ($extension in @('.cs','.cs.meta')) { Copy-Item -LiteralPath (Join-Path $original "Assets\TEP\Scripts\Runtime\$name$extension") -Destination (Join-Path $runtimeDir "$name$extension") }
    }
    Copy-Item -LiteralPath (Join-Path $original 'Assets\TEP\Scripts\Editor\ProcessOverviewSetup.cs') -Destination $editorDir
    foreach ($name in @('NanumGothic-Regular.ttf','NanumGothic-Regular.ttf.meta','NanumGothic-OFL.txt','NanumGothic-OFL.txt.meta')) { Copy-Item -LiteralPath (Join-Path $original "Assets\TEP\Resources\$name") -Destination $resourceDir }
    Copy-Item -LiteralPath (Join-Path $original 'Assets\TEP\Plugins\WebGL\PredictionBridge.jslib') -Destination $pluginDir
    $packages = @{dependencies=@{'com.unity.ugui'='2.0.0';'com.unity.modules.audio'='1.0.0';'com.unity.modules.imageconversion'='1.0.0';'com.unity.modules.imgui'='1.0.0';'com.unity.modules.jsonserialize'='1.0.0';'com.unity.modules.physics'='1.0.0';'com.unity.modules.screencapture'='1.0.0';'com.unity.modules.ui'='1.0.0';'com.unity.modules.uielements'='1.0.0'}}
    [IO.File]::WriteAllText((Join-Path $project 'Packages\manifest.json'), ($packages | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
    $folderVersion = Split-Path (Split-Path (Split-Path $UnityEditor -Parent) -Parent) -Leaf
    [IO.File]::WriteAllText((Join-Path $project 'ProjectSettings\ProjectVersion.txt'), "m_EditorVersion: $folderVersion`n", [Text.UTF8Encoding]::new($false))
    Write-Host "[UNITY] Explicit compatible build: installed $version, source expects $expected; built-in renderer."
}
$log = Join-Path $logDir 'webgl.log'
$arguments = @('-batchmode','-quit','-buildTarget','WebGL','-projectPath',('"'+$project+'"'),'-executeMethod','TEP.Editor.ProcessOverviewSetup.BuildWebGL','-tepWebOutput',('"'+$output+'"'),'-tepFixture',('"'+$fixture+'"'),'-logFile',('"'+$log+'"'))
$build = Start-Process -FilePath $UnityEditor -ArgumentList $arguments -WindowStyle Hidden -PassThru
$build.WaitForExit()
if ($build.ExitCode -ne 0) { Get-Content $log -Tail 25; throw "Unity build failed ($($build.ExitCode))." }
$files = foreach ($name in @('unity.loader.js','unity.data','unity.framework.js','unity.wasm')) {
    $file = Join-Path $output "Build\$name"
    if (-not (Test-Path -LiteralPath $file)) { throw "Missing WebGL output: $name" }
    @{name="Build/$name";sha256=(Get-FileHash $file -Algorithm SHA256).Hash.ToLowerInvariant();bytes=(Get-Item $file).Length}
}
$manifest = @{time=(Get-Date).ToUniversalTime().ToString('o');source_sha256=$sourceHash;unity_version=$version;expected_unity_version=$expected;compatible_isolated_build=$compatible;renderer=$(if($compatible){'built-in'}else{'source-project'});files=@($files)}
[IO.File]::WriteAllText($manifestPath, ($manifest|ConvertTo-Json -Depth 6), [Text.UTF8Encoding]::new($false))
Write-Host "[UNITY] WebGL build and file hashes verified."
