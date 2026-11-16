Add-Type -AssemblyName System.Drawing
$out = "$PSScriptRoot\..\sample-photos"
function Col($r,$g,$b){ [System.Drawing.Color]::FromArgb($r,$g,$b) }
function Br($r,$g,$b){ New-Object System.Drawing.SolidBrush (Col $r $g $b) }
function Img($w,$h,$name,[scriptblock]$paint){
  $bmp = New-Object System.Drawing.Bitmap $w,$h
  $g = [System.Drawing.Graphics]::FromImage($bmp); $g.SmoothingMode='AntiAlias'
  $bg = New-Object System.Drawing.Drawing2D.LinearGradientBrush (New-Object System.Drawing.Rectangle 0,0,$w,$h), (Col 238 236 230), (Col 222 219 212), 90
  $g.FillRectangle($bg,0,0,$w,$h); & $paint $g
  $bmp.Save("$out\$name",[System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()
}
function RRect($g,$brush,$x,$y,$w,$h,$r){
  $p = New-Object System.Drawing.Drawing2D.GraphicsPath
  $p.AddArc($x,$y,2*$r,2*$r,180,90); $p.AddArc($x+$w-2*$r,$y,2*$r,2*$r,270,90)
  $p.AddArc($x+$w-2*$r,$y+$h-2*$r,2*$r,2*$r,0,90); $p.AddArc($x,$y+$h-2*$r,2*$r,2*$r,90,90); $p.CloseFigure(); $g.FillPath($brush,$p)
}
function Ell($g,$brush,$cx,$cy,$rx,$ry,$deg){ $g.TranslateTransform($cx,$cy); $g.RotateTransform($deg); $g.FillEllipse($brush,-$rx,-$ry,2*$rx,2*$ry); $g.ResetTransform() }
function Ruler($g,$x0,$y,$s,$cmCount){
  $len=$cmCount*10*$s
  $g.FillRectangle((Br 250 215 60),$x0-12,$y,$len+24,13*$s); $g.DrawRectangle((New-Object System.Drawing.Pen (Col 30 30 30),2),$x0-12,$y,$len+24,13*$s)
  $pen=New-Object System.Drawing.Pen (Col 30 30 30),1; $font=New-Object System.Drawing.Font "Arial",9
  for($mm=0;$mm -le $cmCount*10;$mm++){ $x=$x0+$mm*$s; $l= if($mm%10 -eq 0){4.5*$s}elseif($mm%5 -eq 0){3*$s}else{1.6*$s}
    $g.DrawLine($pen,$x,$y,$x,$y+$l); if($mm%10 -eq 0){$g.DrawString("$($mm/10)",$font,[System.Drawing.Brushes]::Black,$x-4,$y+5*$s)} }
}
$body=Br 48 50 58; $dark=Br 28 29 34; $mid=Br 72 75 86

# ----- controller BACK (from behind) and BOTTOM (flipped over sideways, front still at the bottom) -----
Img 720 400 "controller-4-back.png" {
  param($g); $s=4; $X={param([double]$v)360+$v*$s}; $Z={param([double]$v)300-$v*$s}
  RRect $g $mid (& $X -60) (& $Z 54) (30*$s) (18*$s) 14; RRect $g $mid (& $X 30) (& $Z 54) (30*$s) (18*$s) 14   # triggers, big from behind
  RRect $g $body (& $X -62) (& $Z 42) (124*$s) (28*$s) 36
  Ell $g $body (& $X -50) (& $Z 18) (22*$s) (18*$s) 0; Ell $g $body (& $X 50) (& $Z 18) (22*$s) (18*$s) 0
  $g.FillRectangle((Br 200 200 205),(& $X -14),(& $Z 34),28*$s,4*$s)          # light bar
}
Img 640 480 "controller-5-bottom.png" {
  param($g); $s=3; $X={param([double]$v)320+$v*$s}; $Y={param([double]$v)225+$v*$s}
  RRect $g $dark (& $X -62) (& $Y -52) (34*$s) (14*$s) 12; RRect $g $dark (& $X 28) (& $Y -52) (34*$s) (14*$s) 12
  RRect $g $body (& $X -62) (& $Y -45) (124*$s) (57*$s) 60
  Ell $g $body (& $X -50) (& $Y 25) (21*$s) (32*$s) 20; Ell $g $body (& $X 50) (& $Y 25) (21*$s) (32*$s) -20
  RRect $g $mid (& $X -25) (& $Y -20) (50*$s) (16*$s) 8                         # battery cover
}

# ----- rubber duck: 70 mm wide, 95 mm long (beak at the front), 90 mm tall -----
$yel=Br 245 205 48; $org=Br 230 120 30; $blk=Br 25 25 25
Img 600 560 "duck-1-front.png" {
  param($g); $s=4; $X={param([double]$v)300+$v*$s}; $Z={param([double]$v)440-$v*$s}
  Ell $g $yel (& $X 0) (& $Z 25) (35*$s) (25*$s) 0
  Ell $g $yel (& $X 0) (& $Z 67.5) (22.5*$s) (22.5*$s) 0
  Ell $g $org (& $X 0) (& $Z 63) (11*$s) (5*$s) 0
  Ell $g $blk (& $X -10) (& $Z 74) (3*$s) (3*$s) 0; Ell $g $blk (& $X 10) (& $Z 74) (3*$s) (3*$s) 0
  Ruler $g 100 470 $s 10
}
Img 520 420 "duck-2-side.png" {
  param($g); $s=3.5; $U={param([double]$u)80+$u*$s}; $Z={param([double]$v)360-$v*$s}
  Ell $g $yel (& $U 88) (& $Z 42) (8*$s) (14*$s) 30                           # tail
  Ell $g $yel (& $U 55) (& $Z 25) (40*$s) (25*$s) 0                           # body
  Ell $g $yel (& $U 32) (& $Z 67.5) (22.5*$s) (22.5*$s) 0                     # head
  Ell $g $org (& $U 9) (& $Z 64) (9*$s) (4.5*$s) 0                            # beak
  Ell $g $blk (& $U 24) (& $Z 74) (3*$s) (3*$s) 0                             # eye
  Ell $g (Br 230 185 30) (& $U 60) (& $Z 30) (18*$s) (9*$s) -10               # wing
}
Img 480 420 "duck-3-top.png" {
  param($g); $s=3; $X={param([double]$v)240+$v*$s}; $Y={param([double]$v)380-$v*$s}
  Ell $g $yel (& $X 0) (& $Y 55) (35*$s) (40*$s) 0
  Ell $g $yel (& $X 0) (& $Y 32) (22.5*$s) (22.5*$s) 0
  Ell $g $org (& $X 0) (& $Y 7) (11*$s) (7*$s) 0
}
Get-ChildItem $out -File | Select-Object Name
