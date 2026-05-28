#!/usr/bin/env pwsh
Set-Location "C:\code\web\herbaflow\.claude\worktrees\audit-session-3\backend"

Write-Host "Running target dedup tests..." -ForegroundColor Green
uv run pytest tests/unit/test_target_dedup.py -v

Write-Host "`nRunning all unit tests (summary)..." -ForegroundColor Green
uv run pytest tests/unit/ -q 2>&1 | Tail -3

Write-Host "`nTest run complete." -ForegroundColor Green
