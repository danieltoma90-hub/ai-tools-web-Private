param(
    [Parameter(Mandatory=$true)]
    [string]$RenderApiKey,

    [Parameter(Mandatory=$true)]
    [string]$SupabaseUrl,

    [Parameter(Mandatory=$true)]
    [string]$SupabaseServiceKey,

    [Parameter(Mandatory=$true)]
    [string]$AnthropicApiKey,

    [Parameter(Mandatory=$false)]
    [string]$FrontendUrl = "https://placeholder.vercel.app"
)

$headers = @{
    Authorization  = "Bearer $RenderApiKey"
    "Content-Type" = "application/json"
    Accept         = "application/json"
}

Write-Host "Verific conectivitate Render API..." -ForegroundColor Cyan
$me = Invoke-RestMethod -Uri "https://api.render.com/v1/owners?limit=1" -Headers $headers
Write-Host "Conectat ca: $($me[0].owner.name)" -ForegroundColor Green

$ownerId = $me[0].owner.id

Write-Host "Creez serviciu backend pe Render..." -ForegroundColor Cyan

$serviceBody = @{
    type       = "web_service"
    name       = "ai-tools-backend"
    ownerId    = $ownerId
    autoDeploy = "yes"
    branch     = "master"
    rootDir    = "backend"
    repo       = "https://github.com/danieltoma90-hub/ai-tools-web-Private"
    envVars    = @(
        @{ key = "SUPABASE_URL";         value = $SupabaseUrl }
        @{ key = "SUPABASE_SERVICE_KEY"; value = $SupabaseServiceKey }
        @{ key = "ANTHROPIC_API_KEY";    value = $AnthropicApiKey }
        @{ key = "FRONTEND_URL";         value = $FrontendUrl }
        @{ key = "PYTHON_VERSION";       value = "3.11.0" }
    )
    serviceDetails = @{
        env          = "python"
        buildCommand = "pip install -r requirements.txt"
        startCommand = 'uvicorn main:app --host 0.0.0.0 --port $PORT'
        plan         = "free"
        region       = "oregon"
        pullRequestPreviewsEnabled = "no"
    }
} | ConvertTo-Json -Depth 10

try {
    $svc = Invoke-RestMethod -Uri "https://api.render.com/v1/services" `
        -Method POST -Headers $headers -Body $serviceBody
    $serviceId  = $svc.service.id
    $serviceUrl = "https://$($svc.service.serviceDetails.url)"
    Write-Host "Serviciu creat! ID: $serviceId" -ForegroundColor Green
    Write-Host ""
    Write-Host "URL Render: $serviceUrl" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Da URL-ul de mai sus lui Claude pentru pasul urmator." -ForegroundColor Cyan
    return $serviceUrl
} catch {
    $err = $_.ErrorDetails.Message | ConvertFrom-Json -ErrorAction SilentlyContinue
    Write-Host "Eroare: $($_.Exception.Message)" -ForegroundColor Red
    if ($err) { Write-Host ($err | ConvertTo-Json) -ForegroundColor Red }
}
