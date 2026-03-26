# e:\image_classify\auto_push.ps1
cd E:\image_classify
git add -A
if (-not (git diff --cached --quiet)) {
  git commit -m "Auto update: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
  git push origin main
}