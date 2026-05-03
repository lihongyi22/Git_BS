Set-Location "$PSScriptRoot\backend"
Write-Host "Installing dependencies..."
pip install -r requirements.txt
Write-Host "Starting FastAPI on 127.0.0.1:8000"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

