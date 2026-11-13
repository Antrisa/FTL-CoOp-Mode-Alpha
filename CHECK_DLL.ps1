param([string]$GameFolder = "C:\Program Files (x86)\Steam\steamapps\common\FTL Faster Than Light")
$expected = "AE852427EA8A73D390EE5700A33A7D93436EFADFC4432FCB80A2F7BB58F22E1F"
$actual = Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $GameFolder "Hyperspace.dll")
$actual | Format-List
if ($actual.Hash -eq $expected) { Write-Host "MATCH: Fleet Co-op v0.28.16 DLL" -ForegroundColor Green }
else { Write-Host "MISMATCH: close FTL/Manager, use this package's Start_FTL_Coop.bat" -ForegroundColor Red }
