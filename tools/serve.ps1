# Tiny local web server for testing: serves the app folder at http://localhost:8765/
$root = Split-Path $PSScriptRoot
$l = New-Object System.Net.HttpListener; $l.Prefixes.Add("http://localhost:8765/"); $l.Start()
while ($l.IsListening) {
  $c = $l.GetContext(); $p = [Uri]::UnescapeDataString($c.Request.Url.AbsolutePath.TrimStart('/'))
  if ($p -eq '') { $p = 'index.html' }
  $f = Join-Path $root $p
  try {
    $b = [IO.File]::ReadAllBytes($f)
    $c.Response.ContentType = @{'.html'='text/html';'.png'='image/png';'.jpg'='image/jpeg'}[[IO.Path]::GetExtension($f)]
    $c.Response.OutputStream.Write($b, 0, $b.Length)
  } catch { $c.Response.StatusCode = 404 }
  $c.Response.Close()
}
