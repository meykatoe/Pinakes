# 產生 Windows 免安裝包：powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
param(
    [switch]$Rebuild
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).ProviderPath
$Out = Join-Path $Root 'packaging\out'
$Pkg = Join-Path $Out 'Pinakes-win'
$Tmp = Join-Path $env:TEMP 'pinakes-build'

$UvUrl = 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip'
$PyVersion = '3.14.8'
$PyUrl = "https://www.python.org/ftp/python/$PyVersion/python-$PyVersion-embed-amd64.zip"
$FfmpegUrl = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'

function Get-Zip($Url, $Name) {
    $zip = Join-Path $Tmp "$Name.zip"
    if (-not (Test-Path $zip)) {
        Write-Host "下載 $Name"
        Invoke-WebRequest -Uri $Url -OutFile $zip
    }
    $dir = Join-Path $Tmp $Name
    if (Test-Path $dir) { Remove-Item $dir -Recurse -Force }
    Expand-Archive -Path $zip -DestinationPath $dir
    return $dir
}

$dist = Join-Path $Root 'frontend\dist\index.html'
if ($Rebuild -or -not (Test-Path $dist)) {
    Write-Host '建置前端'
    Push-Location (Join-Path $Root 'frontend')
    try {
        npm ci
        if ($LASTEXITCODE) { throw 'npm ci 失敗' }
        npm run build
        if ($LASTEXITCODE) { throw '前端建置失敗' }
    } finally { Pop-Location }
}

if (Test-Path $Pkg) { Remove-Item $Pkg -Recurse -Force }
New-Item -ItemType Directory -Path $Pkg, $Tmp -Force | Out-Null

Write-Host '複製後端與前端'
$backend = Join-Path $Pkg 'backend'
robocopy (Join-Path $Root 'backend') $backend /E /XD .venv tests data __pycache__ .pytest_cache .ruff_cache /XF .env | Out-Null
if ($LASTEXITCODE -ge 8) { throw '複製後端失敗' }
robocopy (Join-Path $Root 'frontend\dist') (Join-Path $Pkg 'frontend\dist') /E | Out-Null
if ($LASTEXITCODE -ge 8) { throw '複製前端失敗' }

$uv = Get-Zip $UvUrl 'uv'
$uvExe = (Get-ChildItem $uv -Recurse -Filter uv.exe | Select-Object -First 1).FullName

Write-Host '安裝內嵌 Python 與套件'
$py = Get-Zip $PyUrl 'python'
Copy-Item $py (Join-Path $Pkg 'python') -Recurse
$site = Join-Path $Pkg 'python\Lib\site-packages'
New-Item -ItemType Directory -Path $site -Force | Out-Null
$pth = Get-ChildItem (Join-Path $Pkg 'python') -Filter 'python*._pth' | Select-Object -First 1
$lines = @("$($pth.BaseName).zip", '.', 'Lib\site-packages', '..\backend', 'import site')
Set-Content -Path $pth.FullName -Encoding ascii -Value $lines
$req = Join-Path $Tmp 'requirements.txt'
& $uvExe export --frozen --no-dev --no-hashes --no-emit-project --project $backend --output-file $req | Out-Null
if ($LASTEXITCODE) { throw '匯出相依套件失敗' }
Add-Content -Path $req -Value 'pystray', 'pillow'
& $uvExe pip install --target $site --python-version 3.14 --python-platform windows --only-binary ':all:' -r $req
if ($LASTEXITCODE) { throw '安裝套件失敗' }

$ff = Get-Zip $FfmpegUrl 'ffmpeg'
$bin = Get-ChildItem $ff -Recurse -Directory -Filter bin | Select-Object -First 1
New-Item -ItemType Directory -Path (Join-Path $Pkg 'ffmpeg\bin') -Force | Out-Null
foreach ($name in 'ffmpeg.exe', 'ffprobe.exe') {
    Copy-Item (Join-Path $bin.FullName $name) (Join-Path $Pkg 'ffmpeg\bin')
}

Copy-Item (Join-Path $PSScriptRoot 'start.bat') $Pkg
Copy-Item (Join-Path $PSScriptRoot 'tray.py') $Pkg
Copy-Item (Join-Path $PSScriptRoot 'README.txt') $Pkg

$zipPath = Join-Path $Out 'Pinakes-win.zip'
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path $Pkg -DestinationPath $zipPath
Write-Host "完成：$zipPath"
