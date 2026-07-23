# activate_venv_EN.ps1 - Pure English Version

# Temporarily set Execution Policy to RemoteSigned for this process
Write-Host "--- Checking and setting execution policy ---"
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force

# Check if the virtual environment exists
if (-Not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "Error: Activation script not found at .venv\Scripts\Activate.ps1." -ForegroundColor Red
    Write-Host "Please run 'python -m venv .venv' first." -ForegroundColor Yellow
    exit 1
}

# Execute the virtual environment activation script
Write-Host "--- Activating virtual environment (.venv) ---"
. .venv\Scripts\Activate.ps1

# Verify if activation was successful
if ($env:VIRTUAL_ENV) {
    Write-Host "--- Activation successful: Current environment is $($env:VIRTUAL_ENV) ---" -ForegroundColor Green
} else {
    Write-Host "Warning: The activate script ran, but the environment variable was not set. Check your PowerShell version or permissions." -ForegroundColor Yellow
}