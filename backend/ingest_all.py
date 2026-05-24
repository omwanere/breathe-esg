import os
import sys
import django

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'breathe_esg.settings')
django.setup()

from django.core.management import call_command
from esg_platform.models import User, DataSource, IngestionJob
from esg_platform.parsers import ingest_sap_file, ingest_utility_file, ingest_travel_file

def main():
    # 1. Run seed commands
    print("Running database migrations...")
    call_command('migrate')
    
    print("Seeding conversions, factors, and tenant...")
    call_command('seed_unit_conversions')
    call_command('seed_emission_factors')
    call_command('seed_demo_tenant')

    # 2. Get demo user
    user = User.objects.get(username='analyst@demo.com')

    # Paths to sample data files
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 3. Generate sample data files if they do not exist
    sample_data_dir = os.path.join(base_dir, 'sample_data')
    if not os.path.exists(sample_data_dir) or not os.listdir(sample_data_dir):
        print("Generating sample data files...")
        sys.path.append(base_dir)
        import generate_sample_data
        os.makedirs(sample_data_dir, exist_ok=True)
        generate_sample_data.generate_sap_data(os.path.join(sample_data_dir, 'sap_mb51_export.csv'))
        generate_sample_data.generate_utility_data(os.path.join(sample_data_dir, 'utility_electricity.csv'))
        generate_sample_data.generate_travel_data(os.path.join(sample_data_dir, 'concur_travel_export.csv'))
        print("Sample data files generated.")

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
            print(f"File {filepath} not found! Skipping ingestion for {f['source_type']}.")
            continue
        
        print(f"Ingesting {os.path.basename(filepath)}...")
        ds = DataSource.objects.filter(tenant=user.tenant, source_type=f['source_type']).first()
        if not ds:
            ds = DataSource.objects.create(tenant=user.tenant, source_type=f['source_type'], ingestion_mode='FILE_UPLOAD')
        
        # Create IngestionJob
        job = IngestionJob.objects.create(
            data_source=ds,
            status='PENDING',
            triggered_by=user
        )
        
        with open(filepath, 'rb') as file_obj:
            f['parser'](job.id, file_obj, os.path.basename(filepath))
        
        print(f"Successfully ingested {os.path.basename(filepath)} for {f['source_type']}")

    print("All sample data successfully ingested into the database!")

if __name__ == '__main__':
    main()
