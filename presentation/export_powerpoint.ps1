$ErrorActionPreference = 'Stop'
$deckPath = Join-Path $PSScriptRoot 'PetrIUS_Interview_15min.pptx'
$powerpoint = New-Object -ComObject PowerPoint.Application
$wasEmpty = $powerpoint.Presentations.Count -eq 0
try {
  $deck = $powerpoint.Presentations.Open($deckPath, -1, 0, 0)
  $deck.SaveAs([System.IO.Path]::ChangeExtension($deckPath, '.pdf'), 32)
  $deck.Close()
} finally { if ($wasEmpty) { $powerpoint.Quit() } }
