Add-Type -AssemblyName System.Drawing
$in = "$PSScriptRoot\..\sample-photos\bottle-original"; $out = "$PSScriptRoot\..\sample-photos"
function Col($r,$g,$b){ [System.Drawing.Color]::FromArgb($r,$g,$b) }
function Br($r,$g,$b){ New-Object System.Drawing.SolidBrush (Col $r $g $b) }
# a ruler drawn straight up the photo, $s pixels per mm
function VRuler($g,$x,$y0,$s,$cm){
  $len=$cm*10*$s
  $g.FillRectangle((Br 250 215 60),$x,$y0-14,13*$s,$len+28); $g.DrawRectangle((New-Object System.Drawing.Pen (Col 30 30 30),2),$x,$y0-14,13*$s,$len+28)
  $pen=New-Object System.Drawing.Pen (Col 30 30 30),1.5; $font=New-Object System.Drawing.Font "Arial",14
  for($mm=0;$mm -le $cm*10;$mm++){ $y=$y0+$len-$mm*$s; $l= if($mm%10 -eq 0){4.5*$s}elseif($mm%5 -eq 0){3*$s}else{1.6*$s}
    $g.DrawLine($pen,$x,$y,$x+$l,$y); if($mm%10 -eq 0){$g.DrawString("$($mm/10)",$font,[System.Drawing.Brushes]::Black,$x+5*$s,$y-10)} }
}
function WithRuler($src,$dst,$s,$x,$y0,$cm){
  $b=[System.Drawing.Bitmap]::FromFile($src); $o=New-Object System.Drawing.Bitmap $b.Width,$b.Height
  $g=[System.Drawing.Graphics]::FromImage($o); $g.SmoothingMode='AntiAlias'; $g.DrawImage($b,0,0,$b.Width,$b.Height)
  VRuler $g $x $y0 $s $cm
  $o.Save($dst,[System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $o.Dispose(); $b.Dispose()
}
function Top($dst,$rings){ # rings: diameter mm, r, g, b - drawn biggest first at 4 px/mm
  $o=New-Object System.Drawing.Bitmap 520,520; $g=[System.Drawing.Graphics]::FromImage($o); $g.SmoothingMode='AntiAlias'; $g.Clear((Col 240 238 234))
  foreach($r in $rings){ $d=$r[0]*4; $g.FillEllipse((Br $r[1] $r[2] $r[3]),260-$d/2,260-$d/2,$d,$d) }
  $o.Save($dst,[System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $o.Dispose()
}

# Black steel bottle: body 265-703 px wide = 70 mm (assumed) -> 6.26 px/mm. Ruler up the right side, 15 cm, ending at the table.
$s=438/70.0
WithRuler "$in\steel-bottle.jpg" "$out\bottle-black-1-front.png" $s 770 (1340-150*$s) 15
Copy-Item "$out\bottle-black-1-front.png" "$out\bottle-black-2-side.png"   # it's round, so the side looks the same
Top "$out\bottle-black-3-top.png" @(@(70,30,30,32),@(54,175,175,180),@(40,200,200,205))

# Red and grey bottle: body 322-640 px wide = 80 mm (assumed) -> 3.98 px/mm. Ruler up the left side, 25 cm.
$s=318/80.0
WithRuler "$in\red-grey-bottle.jpg" "$out\bottle-red-1-front.png" $s 120 (1190-250*$s) 25
Copy-Item "$out\bottle-red-1-front.png" "$out\bottle-red-2-side.png"
Top "$out\bottle-red-3-top.png" @(@(80,215,40,70),@(72,170,178,190),@(46,195,200,210))
"done"
