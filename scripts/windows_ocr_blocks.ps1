# Windows PowerShell 5.1. Reads only supplied image bands. No screen/input APIs.
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrResult,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null
[Windows.Globalization.Language,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and
    $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1
if ($null -eq $asTask) { throw 'winrt_async_adapter_unavailable' }
function Await-Operation($operation, [Type]$resultType) {
    $task = $asTask.MakeGenericMethod($resultType).Invoke($null, @($operation))
    return $task.GetAwaiter().GetResult()
}
$inputData = [Console]::In.ReadToEnd() | ConvertFrom-Json
$available = @([Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages | ForEach-Object LanguageTag)
$languages = @($available | Where-Object { $_ -like 'zh-*' }) + @($available | Where-Object { $_ -eq 'en-US' })
if ($languages.Count -eq 0) { throw 'ocr_languages_unavailable' }
$engines = @{}
foreach ($language in $languages) {
    $engines[$language] = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new($language))
}
$lines = @(); $watch = [Diagnostics.Stopwatch]::StartNew()
foreach ($region in $inputData.regions) {
    $bytes = [Convert]::FromBase64String([string]$region.image)
    if ($bytes.Length -gt 20000000) { throw 'ocr_image_too_large' }
    $stream = $null; $random = $null; $bitmap = $null
    try {
        $stream = New-Object IO.MemoryStream(,$bytes)
        $random = [IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($stream)
        $decoder = Await-Operation ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($random)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await-Operation ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        if ($bitmap.PixelWidth -gt [Windows.Media.Ocr.OcrEngine]::MaxImageDimension -or
            $bitmap.PixelHeight -gt [Windows.Media.Ocr.OcrEngine]::MaxImageDimension) { throw 'ocr_dimensions_too_large' }
        $scale = [double]$region.scale; $ox = [double]$region.offset[0]; $oy = [double]$region.offset[1]
        if ($scale -le 0) { throw 'ocr_invalid_scale' }
        foreach ($language in $languages) {
            $engine = $engines[$language]
            if ($null -eq $engine) { continue }
            $result = Await-Operation ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
            $angle = 0.0; if ($null -ne $result.TextAngle) { $angle = [double]$result.TextAngle }
            foreach ($line in $result.Lines) {
                $words = @($line.Words)
                if ($words.Count -eq 0) { continue }
                $x0 = ($words | ForEach-Object { $_.BoundingRect.X } | Measure-Object -Minimum).Minimum
                $y0 = ($words | ForEach-Object { $_.BoundingRect.Y } | Measure-Object -Minimum).Minimum
                $x1 = ($words | ForEach-Object { $_.BoundingRect.X + $_.BoundingRect.Width } | Measure-Object -Maximum).Maximum
                $y1 = ($words | ForEach-Object { $_.BoundingRect.Y + $_.BoundingRect.Height } | Measure-Object -Maximum).Maximum
                $lines += @{ text=[string]$line.Text; box=@($x0,$y0,$x1,$y1); angle=$angle; region_size=@($bitmap.PixelWidth,$bitmap.PixelHeight); scale=$scale; offset=@($ox,$oy); language=$language }
            }
        }
    } finally {
        if ($null -ne $bitmap) { $bitmap.Dispose() }
        if ($null -ne $random) { $random.Dispose() }
        if ($null -ne $stream) { $stream.Dispose() }
    }
}
$watch.Stop()
@{ engine='Windows.Media.Ocr'; pipeline_version=3; languages=$languages; windows_version=[Environment]::OSVersion.VersionString;
   image_size=$inputData.image_size; ocr_seconds=$watch.Elapsed.TotalSeconds; lines=$lines } | ConvertTo-Json -Depth 8 -Compress
