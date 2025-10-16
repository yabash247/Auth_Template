<#
======================================================
🔧  Auth_Template Setup Script (Enhanced Version)
Author: yabash247
Purpose:
 - Initialize only submodules the user has access to.
 - Auto-create stub folders for missing modules so Django won't crash.
======================================================
#>

function Write-Color($Text, $Color="White") {
    Write-Host $Text -ForegroundColor $Color
}

Write-Color "🔄 Starting developer environment setup..." "Cyan"

# Ensure we are inside a Git repo
if (-not (Test-Path ".git")) {
    Write-Color "❌ Error: This folder is not a Git repository." "Red"
    Write-Color "Please run this script from the main project root (BACKEND)." "Yellow"
    exit
}

# Pull latest updates
Write-Color "`n📦 Updating main repository..." "Cyan"
git pull | Out-Null

# Detect all submodules from .gitmodules
$submodules = git config --file .gitmodules --get-regexp path | ForEach-Object { $_.Split(" ")[1] }

if (-not $submodules) {
    Write-Color "⚠️ No submodules found. Please check your .gitmodules file." "Yellow"
    exit
}

Write-Color "`n🧱 Detected submodules:" "Green"
$submodules | ForEach-Object { Write-Color "   • $_" "Gray" }

# Initialize submodules
$initialized = @()
$missing = @()

foreach ($module in $submodules) {
    Write-Color "`n▶ Initializing submodule: $module ..." "Cyan"
    try {
        git submodule update --init --recursive $module 2>$null
        if (Test-Path $module) {
            Write-Color "✅ Loaded: $module" "Green"
            $initialized += $module
        } else {
            Write-Color "⚠️ Skipped: $module (no permission or missing repo)" "Yellow"
            $missing += $module
        }
    } catch {
        Write-Color "⚠️ Skipped: $module (access denied or not available)" "Yellow"
        $missing += $module
    }
}

# 🧩 Stub generator function
function New-StubApp($appPath) {
    if (-not (Test-Path $appPath)) {
        Write-Color "🧱 Creating stub folder for missing app: $appPath" "Yellow"
        New-Item -ItemType Directory -Force -Path $appPath | Out-Null

        $initFile = Join-Path $appPath "__init__.py"
        $appsFile = Join-Path $appPath "apps.py"

        Set-Content -Path $initFile -Value "# Stub for restricted app '$appPath'"

        $appName = Split-Path $appPath -Leaf
        $appsContent = @"
from django.apps import AppConfig

class ${appName}Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = '$appName'
"@
        Set-Content -Path $appsFile -Value $appsContent
    }
}

# Generate stubs for all missing submodules
if ($missing.Count -gt 0) {
    Write-Color "`n🧩 Generating stubs for missing modules..." "Cyan"
    foreach ($m in $missing) {
        New-StubApp $m
    }
} else {
    Write-Color "`n✅ No missing modules detected. All submodules initialized successfully." "Green"
}

Write-Color "`n✨ Setup complete!" "Green"
Write-Color "Initialized: $($initialized -join ', ')" "Green"
Write-Color "Stubbed: $($missing -join ', ')" "Yellow"
Write-Color "`nYou can now run:  python manage.py runserver" "Gray"
