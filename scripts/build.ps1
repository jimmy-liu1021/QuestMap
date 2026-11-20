param([switch]$LocalSnapshot)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$html = [IO.File]::ReadAllText("$root/index.html")
$css = [IO.File]::ReadAllText("$root/css/style.css")
$html = $html.Replace('<link rel="stylesheet" href="css/style.css">', "<style>`n$css</style>")
foreach ($module in 'parser', 'filters', 'map', 'app') {
    $source = [IO.File]::ReadAllText("$root/js/$module.js")
    $html = $html.Replace(('<script src="js/{0}.js"></script>' -f $module), "<script>`n$source</script>")
}
[void][IO.Directory]::CreateDirectory("$root/dist")
[IO.File]::WriteAllText("$root/dist/index.html", $html, [Text.UTF8Encoding]::new($false))
if ($LocalSnapshot) {
    $snapshot = [IO.File]::ReadAllText("$root/quests.json")
    $snapshot = $snapshot.Replace('<', '\u003c')
    $tag = '<script id="quest-snapshot" type="application/json">' + $snapshot + '</script>'
    $localHtml = $html.Replace('<script>' + "`n" + '(() => {', $tag + "`n<script>`n(() => {")
    if ($localHtml -eq $html) { throw 'Could not embed the snapshot before the application script' }
    [IO.File]::WriteAllText("$root/dist/local.html", $localHtml, [Text.UTF8Encoding]::new($false))
}

