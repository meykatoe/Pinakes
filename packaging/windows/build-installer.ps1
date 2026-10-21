# 產生安裝程式：powershell -ExecutionPolicy Bypass -File packaging\windows\build-installer.ps1
param(
    [switch]$SkipPackage
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).ProviderPath
$Out = Join-Path $Root 'packaging\out'
$Pkg = Join-Path $Out 'Pinakes-win'
$Tmp = Join-Path $env:TEMP 'pinakes-build'
$Inno = Join-Path $Tmp 'inno'
$InnoUrl = 'https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe'

if (-not $SkipPackage -or -not (Test-Path (Join-Path $Pkg 'tray.py'))) {
    & (Join-Path $PSScriptRoot 'build.ps1')
    if ($LASTEXITCODE) { throw '打包失敗' }
}

$iscc = Join-Path $Inno 'ISCC.exe'
if (-not (Test-Path $iscc)) {
    New-Item -ItemType Directory -Path $Tmp -Force | Out-Null
    $setup = Join-Path $Tmp 'innosetup.exe'
    Write-Host '下載 Inno Setup'
    Invoke-WebRequest -Uri $InnoUrl -OutFile $setup
    if ((Get-Item $setup).Length -lt 1MB) { throw '下載 Inno Setup 失敗' }
    Start-Process $setup -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CURRENTUSER', "/DIR=$Inno" -Wait
    if (-not (Test-Path $iscc)) { throw '安裝 Inno Setup 失敗' }
}

Write-Host '產生圖示'
$python = Join-Path $Pkg 'python\python.exe'
$ico = Join-Path $Pkg 'pinakes.ico'
$code = "import sys; sys.path.insert(0, r'$Pkg'); import tray; tray.make_icon().save(r'$ico', sizes=[(16,16),(32,32),(48,48),(64,64)])"
& $python -c $code
if ($LASTEXITCODE -or -not (Test-Path $ico)) { throw '產生圖示失敗' }

$version = (Select-String -Path (Join-Path $Root 'backend\pyproject.toml') -Pattern '^version\s*=\s*"(.+)"').Matches[0].Groups[1].Value
Write-Host "編譯安裝程式 $version"
$build = Join-Path $Tmp 'installer-out'
if (Test-Path $build) { Remove-Item $build -Recurse -Force }
& $iscc "/DAppVersion=$version" "/DSourceDir=$Pkg" "/DOutputDir=$build" (Join-Path $PSScriptRoot 'Pinakes.iss')
if ($LASTEXITCODE) { throw '編譯安裝程式失敗' }
$final = Join-Path $Out 'Pinakes-Setup.exe'
Copy-Item (Join-Path $build 'Pinakes-Setup.exe') $final -Force
Write-Host "完成：$final"
