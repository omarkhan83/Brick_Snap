Add-Type -AssemblyName System.Drawing
$out = "$PSScriptRoot\..\sample-photos"
New-Item -ItemType Directory -Force $out | Out-Null
function Col($r,$g,$b){ [System.Drawing.Color]::FromArgb($r,$g,$b) }
function Br($r,$g,$b){ New-Object System.Drawing.SolidBrush (Col $r $g $b) }
$body = Br 48 50 58; $dark = Br 28 29 34; $mid = Br 72 75 86

# Game controller, about 144 mm wide, 108 mm deep, 55 mm tall
function Img($w,$h,$name,[scriptblock]$paint){
  $bmp = New-Object System.Drawing.Bitmap $w,$h
  $g = [System.Drawing.Graphics]::FromImage($bmp); $g.SmoothingMode='AntiAlias'
  # table-top background, lighter at the top like room light
  $bg = New-Object System.Drawing.Drawing2D.LinearGradientBrush (New-Object System.Drawing.Rectangle 0,0,$w,$h), (Col 238 236 230), (Col 222 219 212), 90
  $g.FillRectangle($bg,0,0,$w,$h)
  & $paint $g
  $bmp.Save("$out\$name",[System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()
}
function RRect($g,$brush,$x,$y,$w,$h,$r){
  $p = New-Object System.Drawing.Drawing2D.GraphicsPath
  $p.AddArc($x,$y,2*$r,2*$r,180,90); $p.AddArc($x+$w-2*$r,$y,2*$r,2*$r,270,90)
  $p.AddArc($x+$w-2*$r,$y+$h-2*$r,2*$r,2*$r,0,90); $p.AddArc($x,$y+$h-2*$r,2*$r,2*$r,90,90); $p.CloseFigure()
  $g.FillPath($brush,$p)
}
function Ell($g,$brush,$cx,$cy,$rx,$ry,$deg){
  $g.TranslateTransform($cx,$cy); $g.RotateTransform($deg); $g.FillEllipse($brush,-$rx,-$ry,2*$rx,2*$ry); $g.ResetTransform()
}
function Ruler($g,$x0,$y,$s,$cmCount){
  $len = $cmCount*10*$s
  $g.FillRectangle((Br 250 215 60),$x0-12,$y,$len+24,13*$s)
  $g.DrawRectangle((New-Object System.Drawing.Pen (Col 30 30 30),2),$x0-12,$y,$len+24,13*$s)
  $pen = New-Object System.Drawing.Pen (Col 30 30 30),1; $font = New-Object System.Drawing.Font "Arial",9
  for($mm=0;$mm -le $cmCount*10;$mm++){
    $x=$x0+$mm*$s; $l= if($mm%10 -eq 0){4.5*$s}elseif($mm%5 -eq 0){3*$s}else{1.6*$s}
    $g.DrawLine($pen,$x,$y,$x,$y+$l)
    if($mm%10 -eq 0){$g.DrawString("$($mm/10)",$font,[System.Drawing.Brushes]::Black,$x-4,$y+5*$s)}
  }
}

# TOP at 3 px/mm, player side (grips) at the bottom
Img 640 480 "controller-3-top.png" {
  param($g); $s=3; $X={param([double]$v)320+$v*$s}; $Y={param([double]$v)225+$v*$s}
  RRect $g $dark (& $X -62) (& $Y -52) (34*$s) (14*$s) 12          # shoulder buttons
  RRect $g $dark (& $X 28) (& $Y -52) (34*$s) (14*$s) 12
  RRect $g $body (& $X -62) (& $Y -45) (124*$s) (57*$s) 60         # main body
  Ell $g $body (& $X -50) (& $Y 25) (21*$s) (32*$s) 20             # grips
  Ell $g $body (& $X 50) (& $Y 25) (21*$s) (32*$s) -20
  foreach($c in @(@(-36,-14),@(18,12))){                            # thumbsticks
    Ell $g $dark (& $X $c[0]) (& $Y $c[1]) (11*$s) (11*$s) 0; Ell $g $mid (& $X $c[0]) (& $Y $c[1]) (7*$s) (7*$s) 0 }
  $g.FillRectangle($mid,(& $X -27),(& $Y 9),18*$s,6*$s); $g.FillRectangle($mid,(& $X -21),(& $Y 3),6*$s,18*$s)   # d-pad
  $btn=@(@(0,-8,0,166,80),@(8,0,227,0,11),@(0,8,0,108,183),@(-8,0,255,207,0))
  foreach($b in $btn){ Ell $g (Br $b[2] $b[3] $b[4]) (& $X (38+$b[0])) (& $Y (-14+$b[1])) (4*$s) (4*$s) 0 }
  Ell $g $mid (& $X 0) (& $Y -22) (4*$s) (4*$s) 0                  # home button
}

# FRONT (from the player) at 4 px/mm, with a 15 cm ruler
Img 720 460 "controller-1-front.png" {
  param($g); $s=4; $X={param([double]$v)360+$v*$s}; $Z={param([double]$v)290-$v*$s}
  RRect $g $dark (& $X -60) (& $Z 52) (30*$s) (16*$s) 14            # shoulder buttons behind
  RRect $g $dark (& $X 30) (& $Z 52) (30*$s) (16*$s) 14
  foreach($c in @(-36,18)){ $g.FillRectangle($dark,(& $X ($c-4)),(& $Z 54),8*$s,14*$s); RRect $g $mid (& $X ($c-7)) (& $Z 55) (14*$s) (4*$s) 6 }  # sticks
  RRect $g $body (& $X -62) (& $Z 42) (124*$s) (28*$s) 36           # body
  Ell $g $body (& $X -50) (& $Z 18) (22*$s) (18*$s) 0               # grips
  Ell $g $body (& $X 50) (& $Z 18) (22*$s) (18*$s) 0
  Ruler $g 60 340 $s 15
}

# RIGHT SIDE at 3.5 px/mm, player side on the left
Img 560 420 "controller-2-side.png" {
  param($g); $s=3.5; $U={param([double]$y)70+(56-$y)*$s}; $Z={param([double]$v)320-$v*$s}
  RRect $g $dark (& $U -38) (& $Z 52) (14*$s) (16*$s) 14            # shoulder button
  foreach($c in @(-14,12)){ $g.FillRectangle($dark,(& $U ($c+4)),(& $Z 54),8*$s,14*$s); RRect $g $mid (& $U ($c+7)) (& $Z 55) (14*$s) (4*$s) 6 }
  RRect $g $body (& $U 12) (& $Z 42) (57*$s) (28*$s) 36             # body
  Ell $g $body (& $U 30) (& $Z 16) (30*$s) (16*$s) -15              # grip
}
Get-ChildItem $out -Filter controller* | Select-Object Name,Length

