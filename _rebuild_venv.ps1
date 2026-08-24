# ============================================================================
# 重建 .venv 脚本
# 用法: 右键 → "用 PowerShell 运行" (需要当前用户对系统 Python 有读权限)
# 或者以管理员身份运行 PowerShell 后再执行
# ============================================================================
$ErrorActionPreference = 'Stop'

Write-Host "[1/4] 备份损坏的 .venv ..."
if (Test-Path 'D:\my-projects\agent-monitor\.venv') {
    Rename-Item 'D:\my-projects\agent-monitor\.venv' 'D:\my-projects\agent-monitor\.venv.broken' -Force
}

Write-Host "[2/4] 用系统 Python 创建新 .venv ..."
# 这要求你对 C:\Users\Ed\AppData\Local\Python\pythoncore-3.14-64\python.exe 有读+执行权限
$sysPy = 'C:\Users\Ed\AppData\Local\Python\pythoncore-3.14-64\python.exe'
& $sysPy -m venv 'D:\my-projects\agent-monitor\.venv'

Write-Host "[3/4] 验证新 python.exe ..."
& 'D:\my-projects\agent-monitor\.venv\Scripts\python.exe' --version

Write-Host "[4/4] 重新安装依赖 ..."
& 'D:\my-projects\agent-monitor\.venv\Scripts\python.exe' -m pip install `
    streamlit streamlit-autorefresh `
    openinference-instrumentation-langchain `
    openinference-instrumentation-openai `
    opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc

Write-Host "`n[OK] .venv 已重建。现在重跑："
Write-Host "  `$env:TRACE_FILE = 'D:\agent\complex-agent-langchain\latest_traces.jsonl'"
Write-Host "  cd D:\my-projects\agent-monitor"
Write-Host "  .venv\Scripts\streamlit.exe run viewer.py"
