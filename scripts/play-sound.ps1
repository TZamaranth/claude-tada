# Plays one audio file and waits for it to finish. Called by play-sound.sh on Windows.
# Uses WPF's MediaPlayer (Media Foundation) rather than System.Media.SoundPlayer,
# because SoundPlayer only handles .wav and your own sounds may be .mp3 or .m4a.
param([Parameter(Mandatory = $true)][string]$SoundPath)

if (-not (Test-Path -LiteralPath $SoundPath)) {
  Write-Error "play-sound-windows.ps1: sound file not found: $SoundPath"
  exit 1
}

Add-Type -AssemblyName PresentationCore
$mediaPlayer = New-Object System.Windows.Media.MediaPlayer
$mediaPlayer.Open([uri]$SoundPath)

# The duration is only known once the file has loaded; give up after 3 seconds.
$waitedMilliseconds = 0
while (-not $mediaPlayer.NaturalDuration.HasTimeSpan -and $waitedMilliseconds -lt 3000) {
  Start-Sleep -Milliseconds 50
  $waitedMilliseconds += 50
}
if (-not $mediaPlayer.NaturalDuration.HasTimeSpan) {
  Write-Error "play-sound-windows.ps1: could not load $SoundPath within 3 seconds"
  exit 1
}

$mediaPlayer.Play()
Start-Sleep -Milliseconds ([int]$mediaPlayer.NaturalDuration.TimeSpan.TotalMilliseconds + 200)
$mediaPlayer.Close()
