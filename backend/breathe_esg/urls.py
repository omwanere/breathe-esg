"""
URL configuration for breathe_esg project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from esg_platform.views import (
    CustomTokenObtainPairView, DataSourceViewSet, IngestionJobViewSet,
    UploadSAPView, UploadUtilityView, UploadTravelView,
    RawActivityRowViewSet, ApproveRowView, RejectRowView,
    BulkApproveRowsView, ReviewSummaryView, ExportAuditView
)

router = DefaultRouter()
router.register('ingestion/sources', DataSourceViewSet, basename='datasource')
router.register('ingestion/jobs', IngestionJobViewSet, basename='ingestionjob')
router.register('review/rows', RawActivityRowViewSet, basename='rawactivityrow')

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Auth Endpoints
    path('api/auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Ingestion Uploads
    path('api/ingestion/upload/sap/', UploadSAPView.as_view(), name='upload_sap'),
    path('api/ingestion/upload/utility/', UploadUtilityView.as_view(), name='upload_utility'),
    path('api/ingestion/upload/travel/', UploadTravelView.as_view(), name='upload_travel'),
    
    # Review Actions
    path('api/review/rows/<uuid:pk>/approve/', ApproveRowView.as_view(), name='approve_row'),
    path('api/review/rows/<uuid:pk>/reject/', RejectRowView.as_view(), name='reject_row'),
    path('api/review/bulk-approve/', BulkApproveRowsView.as_view(), name='bulk_approve'),
    path('api/review/summary/', ReviewSummaryView.as_view(), name='review_summary'),
    
    # Include Router (which includes sources, jobs, and rows list/detail/patch)
    path('api/', include(router.urls)),
    
    # Export Audit
    path('api/export/audit-ready/', ExportAuditView.as_view(), name='export_audit_ready'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

