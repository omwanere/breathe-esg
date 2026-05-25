import threading
import os
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.ingestion.models import DataSource, IngestionJob
from apps.ingestion.serializers import DataSourceSerializer, IngestionJobSerializer
from apps.ingestion.parsers import ingest_sap_file, ingest_utility_file, ingest_travel_file

def run_async_ingestion(parser_func, job_id, file_content, filename):
    try:
        import io
        file_obj = io.BytesIO(file_content)
        parser_func(job_id, file_obj, filename)
    except Exception as e:
        try:
            job = IngestionJob.objects.get(id=job_id)
            job.status = 'FAILED'
            job.error_log.append({'error': str(e), 'step': 'Background processing'})
            job.save()
        except:
            pass

class DataSourceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = DataSourceSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.tenant:
            return DataSource.objects.none()
        return DataSource.objects.filter(tenant=user.tenant)

class IngestionJobViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = IngestionJobSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.tenant:
            return IngestionJob.objects.none()
        return IngestionJob.objects.filter(data_source__tenant=user.tenant).order_by('-started_at')

class BaseUploadView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_data_source(self, source_type):
        user = self.request.user
        ds = DataSource.objects.filter(tenant=user.tenant, source_type=source_type).first()
        if not ds:
            ds = DataSource.objects.create(tenant=user.tenant, source_type=source_type, ingestion_mode='FILE_UPLOAD')
        return ds

    def handle_upload(self, request, source_type, parser_func):
        if 'file' not in request.FILES:
            return Response({'error': 'No file uploaded', 'detail': 'Key name should be "file"'}, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = request.FILES['file']
        
        if uploaded_file.size > 10 * 1024 * 1024:
            return Response({'error': 'File too large', 'detail': 'Maximum allowed file size is 10MB.'}, status=status.HTTP_400_BAD_REQUEST)
            
        filename = uploaded_file.name
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        if ext not in ('csv', 'xlsx'):
            return Response({'error': 'Invalid file type', 'detail': 'Only CSV and XLSX files are allowed.'}, status=status.HTTP_400_BAD_REQUEST)
            
        file_content = uploaded_file.read()
        
        if ext == 'csv':
            if b'\x00' in file_content or file_content.startswith(b'MZ'):
                return Response({'error': 'Malicious file detected', 'detail': 'Binary contents or executable headers are not allowed in CSV uploads.'}, status=status.HTTP_400_BAD_REQUEST)
                
        ds = self.get_data_source(source_type)
        
        duplicate_jobs = IngestionJob.objects.filter(
            data_source=ds,
            status='COMPLETED'
        )
        is_duplicate = False
        for dj in duplicate_jobs:
            if dj.raw_file and os.path.basename(dj.raw_file.name) == filename:
                is_duplicate = True
                break
                
        error_log = []
        if is_duplicate:
            error_log.append({'warning': 'This file has already been ingested. Ingesting again may create duplicate entries.'})
            
        job = IngestionJob.objects.create(
            data_source=ds,
            status='PENDING',
            raw_file=uploaded_file,
            triggered_by=request.user,
            error_log=error_log
        )

        threading.Thread(
            target=run_async_ingestion,
            args=(parser_func, job.id, file_content, filename)
        ).start()

        serializer = IngestionJobSerializer(job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class UploadSAPView(BaseUploadView):
    def post(self, request):
        return self.handle_upload(request, 'SAP_FUEL', ingest_sap_file)

class UploadUtilityView(BaseUploadView):
    def post(self, request):
        return self.handle_upload(request, 'UTILITY_ELECTRICITY', ingest_utility_file)

class UploadTravelView(BaseUploadView):
    def post(self, request):
        return self.handle_upload(request, 'TRAVEL_FLIGHT', ingest_travel_file)
