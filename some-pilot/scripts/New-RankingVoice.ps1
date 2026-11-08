param(
    [Parameter(Mandatory = $true)][string]$PlanPath,
    [string]$VoiceDirectory = ("voice-" + (Get-Date -Format "yyyyMMddHHmmss"))
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
$root = Split-Path -Parent $PlanPath
$output = Join-Path $root $VoiceDirectory
New-Item -ItemType Directory -Path $output -Force | Out-Null
$plan = Get-Content -Raw -Encoding UTF8 $PlanPath | ConvertFrom-Json
$plan.voice_dir = $VoiceDirectory
$plan | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $PlanPath
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speaker.SelectVoice("Microsoft Zira Desktop")
$speaker.Rate = 1
$speaker.Volume = 100
$items = @(@{ Name = "hook"; Text = $plan.hook })
foreach ($scene in $plan.scenes) {
    $items += @{ Name = ("rank-{0:d2}" -f [int]$scene.rank); Text = $scene.narration }
}
foreach ($item in $items) {
    $target = Join-Path $output ($item.Name + ".wav")
    if (Test-Path $target) { Remove-Item -LiteralPath $target -Force }
    $speaker.SetOutputToWaveFile($target)
    $speaker.Speak($item.Text)
    Write-Output $target
}
$speaker.Dispose()
