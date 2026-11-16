# A chess pawn as an STL (mm, Z up), made by spinning a side profile around the Z axis
$dir = "$PSScriptRoot\..\sample-models"; New-Item -ItemType Directory -Force $dir | Out-Null
$prof = @(@(0,0),@(15,0),@(15,4),@(12,6),@(12,8),@(9,10),@(6,24),@(9,25),@(9,27),@(5,28))
for($a=-70;$a -le 90;$a+=10){ $r=[Math]::PI*$a/180; $prof += ,@([Math]::Max(0,7.5*[Math]::Cos($r)), (35+7.5*[Math]::Sin($r))) }
$N=48; $sb = New-Object System.Text.StringBuilder; [void]$sb.AppendLine("solid pawn")
function V($r,$z,$i){ $t=2*[Math]::PI*$i/$N; "{0:F4} {1:F4} {2:F4}" -f ($r*[Math]::Cos($t)),($r*[Math]::Sin($t)),$z }
function Tri($a,$b,$c){ [void]$sb.AppendLine("facet normal 0 0 0`n outer loop`n  vertex $a`n  vertex $b`n  vertex $c`n endloop`nendfacet") }
for($k=0;$k -lt $prof.Count-1;$k++){ $p=$prof[$k]; $q=$prof[$k+1]
  for($i=0;$i -lt $N;$i++){ $a=V $p[0] $p[1] $i; $b=V $p[0] $p[1] ($i+1); $c=V $q[0] $q[1] ($i+1); $d=V $q[0] $q[1] $i
    Tri $a $b $c; Tri $a $c $d } }
[void]$sb.AppendLine("endsolid pawn")
[IO.File]::WriteAllText("$dir\pawn.stl",$sb.ToString())
Get-Item "$dir\pawn.stl" | Select-Object Name,Length
