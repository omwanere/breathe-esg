import os
import sys
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.authentication.models import User
from apps.ingestion.models import DataSource, IngestionJob
from apps.ingestion.parsers import ingest_sap_file, ingest_utility_file, ingest_travel_file

class Command(BaseCommand):
    help = 'Loads and ingests sample data files into Supabase/PostgreSQL'

    def handle(self, *args, **options):
        # 1. Get demo user
        try:
            user = User.objects.get(username='analyst@demo.com')
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR("User analyst@demo.com not found. Please run seed_demo_tenant first."))
            return

        # Paths to sample data files
        sample_data_dir = settings.BASE_DIR.parent / 'sample_data'
        
        # 2. Generate sample data files if they do not exist
        if not os.path.exists(sample_data_dir) or not os.listdir(sample_data_dir):
            self.stdout.write("Generating sample data files...")
            sys.path.append(str(settings.BASE_DIR.parent))
            try:
                import generate_sample_data
                os.makedirs(sample_data_dir, exist_ok=True)
                generate_sample_data.generate_sap_data(os.path.join(sample_data_dir, 'sap_mb51_export.csv'))
                generate_sample_data.generate_utility_data(os.path.join(sample_data_dir, 'utility_electricity.csv'))
                generate_sample_data.generate_travel_data(os.path.join(sample_data_dir, 'concur_travel_export.csv'))
                self.stdout.write(self.style.SUCCESS("Sample data files generated."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to generate sample data: {e}"))
                return
         
        files_to_ingest = [
            {
                'path': os.path.join(sample_data_dir, 'sap_mb51_export.csv'),
                'source_type': 'SAP_FUEL',
                'parser': ingest_sap_file,
            },
            {
                'path': os.path.join(sample_data_dir, 'utility_electricity.csv'),
                'source_type': 'UTILITY_ELECTRICITY',
                'parser': ingest_utility_file,
            },
            {
                'path': os.path.join(sample_data_dir, 'concur_travel_export.csv'),
                'source_type': 'TRAVEL_FLIGHT',
                'parser': ingest_travel_file,
            }
        ]

        for f in files_to_ingest:
            filepath = f['path']
            if not os.path.exists(filepath):
                self.stdout.write(self.style.WARNING(f"File {filepath} not found! Skipping ingestion for {f['source_type']}."))
                continue
            
            self.stdout.write(f"Ingesting {os.path.basename(filepath)}...")
            ds = DataSource.objects.filter(tenant=user.tenant, source_type=f['source_type']).first()
            if not ds:
                ds = DataSource.objects.create(tenant=user.tenant, source_type=f['source_type'], ingestion_mode='FILE_UPLOAD')
            
            # Create IngestionJob
            job = IngestionJob.objects.create(
                data_source=ds,
                status='PENDING',
                triggered_by=user
            )
            
            try:
                with open(filepath, 'rb') as file_obj:
                    f['parser'](job.id, file_obj, os.path.basename(filepath))
                self.stdout.write(self.style.SUCCESS(f"Successfully ingested {os.path.basename(filepath)} for {f['source_type']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to ingest {os.path.basename(filepath)}: {e}"))

        self.stdout.write(self.style.SUCCESS("All sample data successfully ingested into the database!"))
