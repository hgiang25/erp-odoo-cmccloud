# Script don dep toan bo tai nguyen Odoo tren Kubernetes Local
Write-Host "Dang go bo toan bo he thong Odoo tren Kubernetes..." -ForegroundColor Yellow
kubectl delete -k .
Write-Host "Da don dep hoan tat namespace odoo-system!" -ForegroundColor Green
