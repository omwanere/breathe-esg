from django.test import TestCase
from decimal import Decimal
from datetime import date
import io
from esg_platform.models import Tenant, User, DataSource, IngestionJob, RawActivityRow, UnitConversion, EmissionFactor
from esg_platform.parsers import ingest_travel_file, calculate_emissions

class TravelParserTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Demo Tenant", slug="demo")
        self.user = User.objects.create_user(username="analyst@demo.com", password="password", tenant=self.tenant)
        self.ds = DataSource.objects.create(
            tenant=self.tenant,
            source_type="TRAVEL_FLIGHT",
            ingestion_mode="FILE_UPLOAD"
        )
        self.job = IngestionJob.objects.create(data_source=self.ds, status="PENDING", triggered_by=self.user)
        
        # Seed conversions and factors
        UnitConversion.objects.get_or_create(from_unit="miles", to_unit="km", defaults={"factor": Decimal("1.60934")})
        
        EmissionFactor.objects.get_or_create(
            activity_type="Short-haul flight",
            region="Global",
            unit="km",
            defaults={"factor_kg_co2e_per_unit": Decimal("0.255"), "source": "DEFRA", "valid_year": 2023}
        )
        EmissionFactor.objects.get_or_create(
            activity_type="Long-haul flight",
            region="Global",
            unit="km",
            defaults={"factor_kg_co2e_per_unit": Decimal("0.195"), "source": "DEFRA", "valid_year": 2023}
        )
        EmissionFactor.objects.get_or_create(
            activity_type="Hotel stay",
            region="Global",
            unit="room-night",
            defaults={"factor_kg_co2e_per_unit": Decimal("31.9"), "source": "DEFRA", "valid_year": 2023}
        )
        EmissionFactor.objects.get_or_create(
            activity_type="Car Rental",
            region="Global",
            unit="km",
            defaults={"factor_kg_co2e_per_unit": Decimal("0.192"), "source": "DEFRA", "valid_year": 2023}
        )
        EmissionFactor.objects.get_or_create(
            activity_type="Rail",
            region="Global",
            unit="km",
            defaults={"factor_kg_co2e_per_unit": Decimal("0.035"), "source": "DEFRA", "valid_year": 2023}
        )
        EmissionFactor.objects.get_or_create(
            activity_type="Taxi",
            region="Global",
            unit="km",
            defaults={"factor_kg_co2e_per_unit": Decimal("0.149"), "source": "DEFRA", "valid_year": 2023}
        )

    def test_4_1_happy_path(self):
        csv_content = (
            "report_id,employee_id,employee_name,department,expense_type,transaction_date,origin,destination,distance_km,amount_usd,currency,vendor_name,booking_class,trip_purpose,nights\n"
            "REP-01,EMP01,John Doe,Sales,Airfare,02/15/2024,LHR,JFK,5576,850.00,USD,BA,Y,Client,0\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        
        ingest_travel_file(self.job.id, file_obj, "travel.csv")
        
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "COMPLETED")
        self.assertEqual(self.job.row_count, 1)
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        self.assertEqual(row.scope, "SCOPE_3")
        self.assertEqual(row.source_type, "TRAVEL_FLIGHT")

    def test_4_2_iata_distance_calculation(self):
        csv_content = (
            "report_id,employee_id,employee_name,department,expense_type,transaction_date,origin,destination,distance_km,amount_usd,currency,vendor_name,booking_class,trip_purpose,nights\n"
            "REP-01,EMP01,John Doe,Sales,Airfare,02/15/2024,LHR,JFK,,850.00,USD,BA,Y,Client,0\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        ingest_travel_file(self.job.id, file_obj, "travel.csv")
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        # distance should be computed around 5576 km (LHR-JFK), and within 5% of 5540 km
        diff = abs(row.parsed_quantity - Decimal("5540"))
        pct_diff = (diff / Decimal("5540")) * 100
        self.assertTrue(pct_diff < 5)
        
        # Calculate emissions
        kwh, co2e, ef, src, flags = calculate_emissions(row)
        # Long-haul flight: 5576 * 0.195 = ~1087 kg CO2e
        self.assertAlmostEqual(ef, Decimal("0.195"))

    def test_4_3_cabin_class_multiplier(self):
        classes = [
            ("Y", Decimal("1.0")),
            ("W", Decimal("1.6")),
            ("C", Decimal("2.0")),
            ("F", Decimal("2.4"))
        ]
        
        co2e_values = []
        for booking_class, mult in classes:
            row = RawActivityRow.objects.create(
                tenant=self.tenant,
                ingestion_job=self.job,
                source_type="TRAVEL_FLIGHT",
                scope="SCOPE_3",
                parsed_quantity=Decimal("1000"),
                parsed_unit="km",
                activity_date=date(2024, 1, 1),
                raw_data={"booking_class": booking_class}
            )
            kwh, co2e, ef, src, flags = calculate_emissions(row)
            co2e_values.append(co2e)
            
        # Ratios should be: Y: 1000 * 0.255 = 255. W: 255 * 1.6 = 408. C: 255 * 2.0 = 510. F: 255 * 2.4 = 612.
        self.assertAlmostEqual(co2e_values[0], Decimal("255.0"))
        self.assertAlmostEqual(co2e_values[1], Decimal("408.0"))
        self.assertAlmostEqual(co2e_values[2], Decimal("510.0"))
        self.assertAlmostEqual(co2e_values[3], Decimal("612.0"))

    def test_4_4_hotel_emission_calculation(self):
        row = RawActivityRow.objects.create(
            tenant=self.tenant,
            ingestion_job=self.job,
            source_type="TRAVEL_HOTEL",
            scope="SCOPE_3",
            parsed_quantity=Decimal("3"),
            parsed_unit="room-night",
            activity_date=date(2024, 1, 1),
            description="Hotel stay"
        )
        kwh, co2e, ef, src, flags = calculate_emissions(row)
        self.assertAlmostEqual(co2e, Decimal("95.7")) # 3 * 31.9 = 95.7

    def test_4_5_ground_transport_factors(self):
        # Car Rental
        row_car = RawActivityRow.objects.create(
            tenant=self.tenant,
            ingestion_job=self.job,
            source_type="TRAVEL_GROUND",
            scope="SCOPE_3",
            parsed_quantity=Decimal("100"),
            parsed_unit="km",
            activity_date=date(2024, 1, 1),
            raw_data={"expense_type": "Car Rental"}
        )
        kwh, co2e_car, ef, src, flags = calculate_emissions(row_car)
        self.assertAlmostEqual(co2e_car, Decimal("19.2")) # 100 * 0.192 = 19.2
        
        # Rail
        row_rail = RawActivityRow.objects.create(
            tenant=self.tenant,
            ingestion_job=self.job,
            source_type="TRAVEL_GROUND",
            scope="SCOPE_3",
            parsed_quantity=Decimal("100"),
            parsed_unit="km",
            activity_date=date(2024, 1, 1),
            raw_data={"expense_type": "Rail"}
        )
        kwh, co2e_rail, ef, src, flags = calculate_emissions(row_rail)
        self.assertAlmostEqual(co2e_rail, Decimal("3.5")) # 100 * 0.035 = 3.5
        
        # Taxi
        row_taxi = RawActivityRow.objects.create(
            tenant=self.tenant,
            ingestion_job=self.job,
            source_type="TRAVEL_GROUND",
            scope="SCOPE_3",
            parsed_quantity=Decimal("100"),
            parsed_unit="km",
            activity_date=date(2024, 1, 1),
            raw_data={"expense_type": "Taxi"}
        )
        kwh, co2e_taxi, ef, src, flags = calculate_emissions(row_taxi)
        self.assertAlmostEqual(co2e_taxi, Decimal("14.9")) # 100 * 0.149 = 14.9

    def test_4_6_origin_equals_destination(self):
        csv_content = (
            "report_id,employee_id,employee_name,department,expense_type,transaction_date,origin,destination,distance_km,amount_usd,currency,vendor_name,booking_class,trip_purpose,nights\n"
            "REP-01,EMP01,John Doe,Sales,Airfare,02/15/2024,LHR,LHR,0,850.00,USD,BA,Y,Client,0\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        ingest_travel_file(self.job.id, file_obj, "travel.csv")
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        self.assertEqual(row.status, "FLAGGED")
        self.assertTrue(any("origin and destination are identical" in r for r in row.flag_reasons))

    def test_4_7_high_amount_flag(self):
        csv_content = (
            "report_id,employee_id,employee_name,department,expense_type,transaction_date,origin,destination,distance_km,amount_usd,currency,vendor_name,booking_class,trip_purpose,nights\n"
            "REP-01,EMP01,John Doe,Sales,Airfare,02/15/2024,LHR,JFK,5576,15000.00,USD,BA,Y,Client,0\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        ingest_travel_file(self.job.id, file_obj, "travel.csv")
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        self.assertEqual(row.status, "FLAGGED")
        self.assertTrue(any("Expense amount is high" in r for r in row.flag_reasons))

    def test_4_8_concur_date_format(self):
        csv_content = (
            "report_id,employee_id,employee_name,department,expense_type,transaction_date,origin,destination,distance_km,amount_usd,currency,vendor_name,booking_class,trip_purpose,nights\n"
            "REP-01,EMP01,John Doe,Sales,Airfare,03/15/2024,LHR,JFK,5576,850.00,USD,BA,Y,Client,0\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        ingest_travel_file(self.job.id, file_obj, "travel.csv")
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        self.assertEqual(row.activity_date, date(2024, 3, 15))

    def test_4_9_unknown_iata_code(self):
        csv_content = (
            "report_id,employee_id,employee_name,department,expense_type,transaction_date,origin,destination,distance_km,amount_usd,currency,vendor_name,booking_class,trip_purpose,nights\n"
            "REP-01,EMP01,John Doe,Sales,Airfare,02/15/2024,ZZZ,JFK,,850.00,USD,BA,Y,Client,0\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        ingest_travel_file(self.job.id, file_obj, "travel.csv")
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        self.assertEqual(row.status, "FLAGGED")
        self.assertTrue(any("unrecognized in system database" in r for r in row.flag_reasons))

    def test_4_10_missing_expense_type(self):
        csv_content = (
            "report_id,employee_id,employee_name,department,expense_type,transaction_date,origin,destination,distance_km,amount_usd,currency,vendor_name,booking_class,trip_purpose,nights\n"
            "REP-01,EMP01,John Doe,Sales,,02/15/2024,LHR,JFK,100,850.00,USD,BA,Y,Client,0\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        ingest_travel_file(self.job.id, file_obj, "travel.csv")
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        self.assertEqual(row.status, "FLAGGED")
        self.assertTrue(any("Missing expense type" in r for r in row.flag_reasons))
