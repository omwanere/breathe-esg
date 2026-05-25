from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.authentication.views import CustomTokenObtainPairView
from apps.ingestion.views import (
    DataSourceViewSet, IngestionJobViewSet,
    UploadSAPView, UploadUtilityView, UploadTravelView
)
from apps.review.views import (
    RawActivityRowViewSet, ApproveRowView, RejectRowView,
    BulkApproveRowsView, ReviewSummaryView
)
from apps.export.views import ExportAuditView

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
