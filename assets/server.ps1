# Eevee Local HTTP Server - Pure PowerShell (No Dependencies)
# Usage: .\server.ps1
# Navigate to: http://localhost:8000

$port = 8000
$folder = Split-Path -Parent $PSScriptRoot

$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$port/")
$listener.Start()

Write-Host "🎉 Eevee Server Started!"
Write-Host "📍 Open browser: http://localhost:$port"
Write-Host "📁 Serving folder: $folder"
Write-Host "⏹️  Press Ctrl+C to stop"
Write-Host ""

$mimeTypes = @{
    ".html"  = "text/html"
    ".css"   = "text/css"
    ".js"    = "application/javascript"
    ".json"  = "application/json"
    ".png"   = "image/png"
    ".jpg"   = "image/jpeg"
    ".gif"   = "image/gif"
    ".svg"   = "image/svg+xml"
    ".woff"  = "font/woff"
    ".woff2" = "font/woff2"
    ".ttf"   = "font/ttf"
}

try {
    while ($true) {
        $context = $listener.GetContext()
        $request = $context.Request
        $response = $context.Response
        
        $path = $request.Url.LocalPath
        if ($path -eq "/") { $path = "/index.html" }
        
        $filePath = Join-Path $folder $path.TrimStart("/")
        
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $($request.HttpMethod) $($request.Url.LocalPath)" -ForegroundColor Cyan
        
        if (Test-Path $filePath -PathType Leaf) {
            $ext = [System.IO.Path]::GetExtension($filePath)
            $mimeType = $mimeTypes[$ext] -or "application/octet-stream"
            
            $response.ContentType = $mimeType
            $response.StatusCode = 200
            
            $fileBytes = [System.IO.File]::ReadAllBytes($filePath)
            $response.ContentLength64 = $fileBytes.Length
            $response.OutputStream.Write($fileBytes, 0, $fileBytes.Length)
            
            Write-Host "  → 200 OK ($mimeType)" -ForegroundColor Green
        }
        else {
            $response.StatusCode = 404
            $errorMsg = "404 - File Not Found: $path"
            $errorBytes = [System.Text.Encoding]::UTF8.GetBytes($errorMsg)
            $response.ContentLength64 = $errorBytes.Length
            $response.OutputStream.Write($errorBytes, 0, $errorBytes.Length)
            
            Write-Host "  → 404 Not Found" -ForegroundColor Red
        }
        
        $response.OutputStream.Close()
    }
}
finally {
    $listener.Stop()
    $listener.Close()
    Write-Host "Server stopped."
}
