Set-Location "$PSScriptRoot\backend"
Write-Host "Installing dependencies..."
pip install -r requirements.txt
Write-Host "Starting WEB3 FastAPI on 127.0.0.1:8003"
uvicorn app.main:app --host 127.0.0.1 --port 8003 --reload

