param([string]$src,[string]$dst)
Add-Type -AssemblyName System.Drawing
$bmp = [System.Drawing.Bitmap]::FromFile($src)
# find the controller: dark pixels, sampled every 4 px
$x0=9999;$x1=0;$y0=9999;$y1=0
for($y=300;$y -lt $bmp.Height;$y+=4){for($x=0;$x -lt $bmp.Width-60;$x+=4){
  $c=$bmp.GetPixel($x,$y); if($c.R+$c.G+$c.B -lt 180){ if($x-lt$x0){$x0=$x};if($x-gt$x1){$x1=$x};if($y-lt$y0){$y0=$y};if($y-gt$y1){$y1=$y} } }}
"controller box: x $x0-$x1, y $y0-$y1"
# DualShock 4 is 162 mm wide (Sony spec), so this many pixels = 1 mm
$s = (1155-170)/162.0
"px per mm: $s"
$out = New-Object System.Drawing.Bitmap $bmp.Width,$bmp.Height
$g = [System.Drawing.Graphics]::FromImage($out); $g.SmoothingMode='AntiAlias'
$g.DrawImage($bmp,0,0,$bmp.Width,$bmp.Height)
$ry = $y1 + 50; $rx = [int](($bmp.Width - 150*$s)/2)
$g.FillRectangle((New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(250,215,60))),$rx-14,$ry,150*$s+28,13*$s)
$g.DrawRectangle((New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(30,30,30)),2),$rx-14,$ry,150*$s+28,13*$s)
$pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(30,30,30)),1.5; $font = New-Object System.Drawing.Font "Arial",13
for($mm=0;$mm -le 150;$mm++){ $x=$rx+$mm*$s; $l= if($mm%10 -eq 0){4.5*$s}elseif($mm%5 -eq 0){3*$s}else{1.6*$s}
  $g.DrawLine($pen,$x,$ry,$x,$ry+$l); if($mm%10 -eq 0){$g.DrawString("$($mm/10)",$font,[System.Drawing.Brushes]::Black,$x-6,$ry+5*$s)} }
$out.Save($dst,[System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $out.Dispose(); $bmp.Dispose()


