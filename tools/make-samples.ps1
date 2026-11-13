Add-Type -AssemblyName System.Drawing
$out = "$PSScriptRoot\..\sample-photos"
New-Item -ItemType Directory -Force $out | Out-Null
$C = { param($r,$g,$b) [System.Drawing.Color]::FromArgb($r,$g,$b) }
$wall  = New-Object System.Drawing.SolidBrush (& $C 200 40 40)
$roof  = New-Object System.Drawing.SolidBrush (& $C 130 30 30)
$roof2 = New-Object System.Drawing.SolidBrush (& $C 160 35 35)
$ink   = New-Object System.Drawing.Pen (& $C 30 30 30), 2
$P = { param($x,$y) New-Object System.Drawing.PointF $x,$y }

function Save($w,$h,$name,[scriptblock]$paint){
  $bmp = New-Object System.Drawing.Bitmap $w,$h
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode = 'AntiAlias'
  $g.Clear((& $C 245 243 238))
  & $paint $g
  $bmp.Save("$out\$name", [System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $bmp.Dispose()
}

# Object: a little house, 80 mm wide, 60 mm deep, 80 mm tall (50 mm walls + 30 mm roof)

# FRONT at 4 px/mm, with a 0-10 cm ruler underneath
Save 600 520 "1-front.png" {
  param($g)
  $g.FillRectangle($wall, 100, 200, 320, 200)
  $g.FillPolygon($roof, [System.Drawing.PointF[]]@((& $P 100 200), (& $P 420 200), (& $P 260 80)))
  $g.FillRectangle((New-Object System.Drawing.SolidBrush (& $C 90 60 30)), 230, 300, 60, 100)   # door
  # ruler
  $g.FillRectangle((New-Object System.Drawing.SolidBrush (& $C 250 215 60)), 90, 440, 420, 50)
  $g.DrawRectangle($ink, 90, 440, 420, 50)
  $font = New-Object System.Drawing.Font "Arial", 9
  for ($mm = 0; $mm -le 100; $mm++) {
    $x = 100 + $mm * 4
    $len = if ($mm % 10 -eq 0) { 18 } elseif ($mm % 5 -eq 0) { 12 } else { 6 }
    $g.DrawLine((New-Object System.Drawing.Pen (& $C 30 30 30), 1), $x, 440, $x, 440 + $len)
    if ($mm % 10 -eq 0) { $g.DrawString("$($mm/10)", $font, [System.Drawing.Brushes]::Black, $x - 4, 462) }
  }
  $g.DrawString("cm", $font, [System.Drawing.Brushes]::Black, 488, 474)
}

# RIGHT SIDE at 3 px/mm (front of house on the left)
Save 500 450 "2-side.png" {
  param($g)
  $g.FillRectangle($wall, 160, 210, 180, 150)
  $g.FillRectangle($roof, 160, 120, 180, 90)
  $g.FillRectangle((New-Object System.Drawing.SolidBrush (& $C 200 225 245)), 220, 250, 60, 50)  # window
}

# TOP at 3 px/mm (front of house at the bottom)
Save 500 450 "3-top.png" {
  param($g)
  $g.FillRectangle($roof, 130, 135, 120, 180)
  $g.FillRectangle($roof2, 250, 135, 120, 180)
}
Get-ChildItem $out | Select-Object Name, Length
