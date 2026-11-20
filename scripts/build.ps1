param([switch]$LocalSnapshot, [string]$SnapshotPath)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$html = [IO.File]::ReadAllText("$root/index.html")
$leafletDir = "$root/vendor/leaflet"
$leafletCss = [IO.File]::ReadAllText("$leafletDir/leaflet.css")
foreach ($name in 'layers.png', 'layers-2x.png', 'marker-icon.png') {
    $image = [Convert]::ToBase64String([IO.File]::ReadAllBytes("$leafletDir/images/$name"))
    $leafletCss = $leafletCss.Replace("url(images/$name)", "url(data:image/png;base64,$image)")
}
$leafletJs = [IO.File]::ReadAllText("$leafletDir/leaflet.js") -replace '(?m)^//# sourceMappingURL=.*$', ''
$leafletLicense = [IO.File]::ReadAllText("$leafletDir/LICENSE")
$html = $html.Replace('<link rel="stylesheet" href="vendor/leaflet/leaflet.css">', "<style>`n$leafletCss`n</style>")
$html = $html.Replace('<script src="vendor/leaflet/leaflet.js"></script>', "<script>`n/*`n$leafletLicense`n*/`n$leafletJs`n</script>")
$css = [IO.File]::ReadAllText("$root/css/style.css")
$html = $html.Replace('<link rel="stylesheet" href="css/style.css">', "<style>`n$css</style>")
foreach ($module in 'parser', 'filters', 'route', 'map', 'app') {
    $source = [IO.File]::ReadAllText("$root/js/$module.js")
    $html = $html.Replace(('<script src="js/{0}.js"></script>' -f $module), "<script>`n$source</script>")
}
[void][IO.Directory]::CreateDirectory("$root/dist")
[IO.File]::WriteAllText("$root/dist/index.html", $html, [Text.UTF8Encoding]::new($false))
if ($LocalSnapshot) {
    if (-not $SnapshotPath) { $SnapshotPath = "$root/quests.json" }
    $snapshot = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $SnapshotPath).ProviderPath)
    $snapshot = $snapshot.Replace('<', '\u003c')
    $tag = '<script id="quest-snapshot" type="application/json">' + $snapshot + '</script>'
    $localHtml = $html.Replace('<script>' + "`n" + '(() => {', $tag + "`n<script>`n(() => {")
    if ($localHtml -eq $html) { throw 'Could not embed the snapshot before the application script' }
    [IO.File]::WriteAllText("$root/dist/local.html", $localHtml, [Text.UTF8Encoding]::new($false))
}

