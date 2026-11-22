# 一键跑 demo：生成一份示例报告
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "1/3 检查依赖..." -ForegroundColor Cyan
python -m pip install -q -r requirements.txt

Write-Host "2/3 生成报告（离线引擎，不需要 API key）..." -ForegroundColor Cyan
python scripts\generate.py --answers inbox\demo.json --id DEMO --mbti ISTJ --birth 1992-03-10 --engine offline

Write-Host "3/3 完成，产物在 out\DEMO\" -ForegroundColor Green
Get-ChildItem out\DEMO | Select-Object Name, Length | Format-Table -AutoSize
