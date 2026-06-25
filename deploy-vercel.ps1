param(
    [Parameter(Mandatory=$true)]
    [string]$BackendUrl
)

Set-Location D:\ai-tools-web\frontend

Write-Host "Setez variabilele de mediu pe Vercel..." -ForegroundColor Cyan

# Setare env vars productie
"https://zjmtqitymnrmmmsfoolp.supabase.co" | vercel env add NEXT_PUBLIC_SUPABASE_URL production --yes 2>&1
"sb_publishable_zGrZT3emlDbPD7L5dEs2YA_pdOMLAyp" | vercel env add NEXT_PUBLIC_SUPABASE_ANON_KEY production --yes 2>&1
$BackendUrl | vercel env add NEXT_PUBLIC_API_URL production --yes 2>&1

Write-Host "Rulez deploy productie Vercel..." -ForegroundColor Cyan
$output = vercel --prod --yes 2>&1
Write-Host $output

# Extrag URL-ul final
$vercelUrl = ($output | Select-String "https://[a-z0-9\-]+\.vercel\.app").Matches[0].Value
if ($vercelUrl) {
    Write-Host ""
    Write-Host "Frontend URL: $vercelUrl" -ForegroundColor Yellow
    Write-Host "FRONTEND_URL=$vercelUrl" -ForegroundColor Magenta
    Write-Host ""
    Write-Host "Copiaza URL-ul de mai sus si da-l lui Claude." -ForegroundColor Cyan
    return $vercelUrl
} else {
    Write-Host "Deploy terminat. Cauta URL-ul in output-ul de mai sus." -ForegroundColor Yellow
}
