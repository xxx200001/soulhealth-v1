# SoulHealth V1 - 打包脚本（给另一个 AI 看代码用）
# 只保留源代码 + 配置 + 样本数据，排除所有二进制/运行时/大文件

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$OutputZip = Join-Path (Split-Path -Parent $ProjectRoot) "soulhealth-v1-source.zip"

# 如果已存在旧包，先删除
if (Test-Path $OutputZip) { Remove-Item $OutputZip -Force }

# 创建临时目录
$TmpDir = Join-Path $env:TEMP "soulhealth_pack_$(Get-Random)"
$TmpProject = Join-Path $TmpDir "soulhealth-v1"
New-Item -ItemType Directory -Path $TmpProject -Force | Out-Null

Write-Host "正在收集源代码文件..." -ForegroundColor Cyan

# ===================== 要包含的文件列表 =====================

# 1. 根目录配置文件
$rootFiles = @(
    ".env.example",
    ".gitignore",
    "README.md",
    "requirements.txt",
    "run.py",
    "start.bat",
    "start.sh",
    "start_tunnel.py",
    "export_code_dump.py"
)

foreach ($f in $rootFiles) {
    $src = Join-Path $ProjectRoot $f
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $TmpProject $f) -Force
    }
}

# 2. configs/ 目录
$configsDest = Join-Path $TmpProject "configs"
New-Item -ItemType Directory -Path $configsDest -Force | Out-Null
Copy-Item (Join-Path $ProjectRoot "configs\indicators.yaml") $configsDest -Force

# 3. app/ 目录（全部 .py 文件，排除 __pycache__）
$appSrc = Join-Path $ProjectRoot "app"
$appDest = Join-Path $TmpProject "app"

Get-ChildItem -Path $appSrc -Recurse -File -Include "*.py" |
    Where-Object { $_.FullName -notlike "*__pycache__*" } |
    ForEach-Object {
        $rel = $_.FullName.Substring($appSrc.Length)
        $dest = Join-Path $appDest $rel
        $destDir = Split-Path -Parent $dest
        if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
        Copy-Item $_.FullName $dest -Force
    }

# 4. web/ 目录（源代码，排除 node_modules 和 dist）
$webSrc = Join-Path $ProjectRoot "web"
$webDest = Join-Path $TmpProject "web"

# web 根目录配置文件
$webRootFiles = @("index.html", "package.json", "vite.config.js")
New-Item -ItemType Directory -Path $webDest -Force | Out-Null
foreach ($f in $webRootFiles) {
    $src = Join-Path $webSrc $f
    if (Test-Path $src) { Copy-Item $src (Join-Path $webDest $f) -Force }
}

# web/src/ 所有文件
$webSrcDir = Join-Path $webSrc "src"
$webSrcDest = Join-Path $webDest "src"
if (Test-Path $webSrcDir) {
    Get-ChildItem -Path $webSrcDir -Recurse -File |
        ForEach-Object {
            $rel = $_.FullName.Substring($webSrcDir.Length)
            $dest = Join-Path $webSrcDest $rel
            $destDir = Split-Path -Parent $dest
            if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
            Copy-Item $_.FullName $dest -Force
        }
}

# 5. data/samples/ 目录（小 JSON 样本文件）
$samplesSrc = Join-Path $ProjectRoot "data\samples"
$samplesDest = Join-Path $TmpProject "data\samples"
if (Test-Path $samplesSrc) {
    New-Item -ItemType Directory -Path $samplesDest -Force | Out-Null
    Get-ChildItem -Path $samplesSrc -File -Include "*.json" | ForEach-Object {
        Copy-Item $_.FullName $samplesDest -Force
    }
}

# data/uploads/.gitkeep (保持目录结构)
$uploadsKeep = Join-Path $TmpProject "data\uploads"
New-Item -ItemType Directory -Path $uploadsKeep -Force | Out-Null
Set-Content -Path (Join-Path $uploadsKeep ".gitkeep") -Value "placeholder"

# 6. tests/ 目录（排除 __pycache__）
$testsSrc = Join-Path $ProjectRoot "tests"
$testsDest = Join-Path $TmpProject "tests"
if (Test-Path $testsSrc) {
    Get-ChildItem -Path $testsSrc -Recurse -File -Include "*.py" |
        Where-Object { $_.FullName -notlike "*__pycache__*" } |
        ForEach-Object {
            $rel = $_.FullName.Substring($testsSrc.Length)
            $dest = Join-Path $testsDest $rel
            $destDir = Split-Path -Parent $dest
            if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
            Copy-Item $_.FullName $dest -Force
        }
}

# ===================== 打包 =====================
Write-Host "正在压缩..." -ForegroundColor Cyan
Compress-Archive -Path $TmpProject -DestinationPath $OutputZip -Force

# 清理临时目录
Remove-Item -Path $TmpDir -Recurse -Force

# 统计
$zipSize = (Get-Item $OutputZip).Length
$zipSizeMB = [math]::Round($zipSize / 1MB, 2)
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " 打包完成！" -ForegroundColor Green
Write-Host " 输出: $OutputZip" -ForegroundColor Green
Write-Host " 大小: ${zipSizeMB} MB" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
