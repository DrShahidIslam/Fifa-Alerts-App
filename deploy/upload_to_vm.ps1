# FIFA News Agent — Upload to Oracle Cloud VM
# Edit the two variables below, then right-click this file → "Run with PowerShell"

$KEY_PATH = "C:\path\to\your-oracle-key.key"   # ← Change this
$VM_IP    = "YOUR_PUBLIC_IP"                     # ← Change this

Write-Host "Uploading FIFA News Agent to Oracle Cloud VM..." -ForegroundColor Green

# Upload Python files
scp -i $KEY_PATH "G:\Fifa Alerts App\main.py" "ubuntu@${VM_IP}:/opt/fifa-agent/"
scp -i $KEY_PATH "G:\Fifa Alerts App\config.py" "ubuntu@${VM_IP}:/opt/fifa-agent/"
scp -i $KEY_PATH "G:\Fifa Alerts App\.env" "ubuntu@${VM_IP}:/opt/fifa-agent/"
scp -i $KEY_PATH "G:\Fifa Alerts App\requirements.txt" "ubuntu@${VM_IP}:/opt/fifa-agent/"

# Upload modules
scp -i $KEY_PATH -r "G:\Fifa Alerts App\sources" "ubuntu@${VM_IP}:/opt/fifa-agent/"
scp -i $KEY_PATH -r "G:\Fifa Alerts App\detection" "ubuntu@${VM_IP}:/opt/fifa-agent/"
scp -i $KEY_PATH -r "G:\Fifa Alerts App\notifications" "ubuntu@${VM_IP}:/opt/fifa-agent/"
scp -i $KEY_PATH -r "G:\Fifa Alerts App\writer" "ubuntu@${VM_IP}:/opt/fifa-agent/"
scp -i $KEY_PATH -r "G:\Fifa Alerts App\publisher" "ubuntu@${VM_IP}:/opt/fifa-agent/"
scp -i $KEY_PATH -r "G:\Fifa Alerts App\database" "ubuntu@${VM_IP}:/opt/fifa-agent/"

# Upload service file
scp -i $KEY_PATH "G:\Fifa Alerts App\deploy\fifa-agent.service" "ubuntu@${VM_IP}:/opt/fifa-agent/"

Write-Host ""
Write-Host "Upload complete!" -ForegroundColor Green
Write-Host "Now SSH in and restart: sudo systemctl restart fifa-agent" -ForegroundColor Yellow
Read-Host "Press Enter to close"
