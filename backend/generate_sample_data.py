import csv
import os
import random
from datetime import datetime, timedelta

def generate_sap_data(filepath):
    # Columns: Buchungsdatum, Werk, Material, Materialkurztext, Bewegungsart, Menge, Basismengeneinheit, Buchungsjahr, Buchungsperiode, Kostenstelle
    headers = [
        'Buchungsdatum', 'Werk', 'Material', 'Materialkurztext', 'Bewegungsart', 
        'Menge', 'Basismengeneinheit', 'Buchungsjahr', 'Buchungsperiode', 'Kostenstelle'
    ]
    
    rows = []
    start_date = datetime(2024, 1, 1)
    
    # Mix of fuels (Diesel, Petrol) and procurement (Steel, Concrete)
    materials = [
        ('MAT-DI-01', 'Diesel fuel extra', '261', 'L'),
        ('MAT-DI-01', 'Diesel kraftstoff', '201', 'GAL'),
        ('MAT-PET-02', 'Benzin super 95', '261', 'L'),
        ('MAT-ST-03', 'Structural Steel plates', '261', 'KG'),
        ('MAT-CO-04', 'Concrete Mix C30', '101', 'STK'),
    ]

    plants = ['1001', '1002', '1003']
    
    # 44 normal valid rows
    for i in range(44):
        p_date = start_date + timedelta(days=random.randint(0, 89))
        date_str = p_date.strftime('%d.%m.%Y')
        plant = random.choice(plants)
        mat_code, mat_desc, mvt, unit = random.choice(materials)
        
        # Menge using German decimal format: e.g. 1.234,56 or 123,45
        qty_val = round(random.uniform(50, 2500), 2)
        if qty_val >= 1000:
            qty_str = f"{int(qty_val // 1000)}.{int(qty_val % 1000):03d},{int(round((qty_val - int(qty_val)) * 100)):02d}"
        else:
            qty_str = f"{int(qty_val)},{int(round((qty_val - int(qty_val)) * 100)):02d}"
            
        rows.append([
            date_str, plant, mat_code, mat_desc, mvt, 
            qty_str, unit, '2024', f"{p_date.month:02d}", f"KST-{random.choice([5001, 5002])}"
        ])
        
    # Dirty rows:
    # 1. 3 rows with unknown units
    for i in range(3):
        p_date = start_date + timedelta(days=random.randint(0, 89))
        date_str = p_date.strftime('%d.%m.%Y')
        plant = random.choice(plants)
        rows.append([
            date_str, plant, 'MAT-DI-01', 'Diesel fuel dirty unit', '261', 
            '500,00', 'XYZ', '2024', f"{p_date.month:02d}", 'KST-5001'
        ])
        
    # 2. 2 rows with negative quantities
    for i in range(2):
        p_date = start_date + timedelta(days=random.randint(0, 89))
        date_str = p_date.strftime('%d.%m.%Y')
        plant = random.choice(plants)
        rows.append([
            date_str, plant, 'MAT-PET-02', 'Benzin negative qty', '261', 
            '-150,00', 'L', '2024', f"{p_date.month:02d}", 'KST-5002'
        ])
        
    # 3. One with a missing Werk
    p_date = start_date + timedelta(days=random.randint(0, 89))
    date_str = p_date.strftime('%d.%m.%Y')
    rows.append([
        date_str, '', 'MAT-DI-01', 'Diesel missing plant', '261', 
        '750,00', 'L', '2024', f"{p_date.month:02d}", 'KST-5001'
    ])
    
    # 4. Add 5 rows with non-matching movement types (e.g. 311, which will be filtered out by the parser)
    for i in range(5):
        p_date = start_date + timedelta(days=random.randint(0, 89))
        date_str = p_date.strftime('%d.%m.%Y')
        plant = random.choice(plants)
        rows.append([
            date_str, plant, 'MAT-ST-03', 'Steel ignored mvt', '311', 
            '1.000,00', 'KG', '2024', f"{p_date.month:02d}", 'KST-5001'
        ])

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

def generate_utility_data(filepath):
    # Columns: account_number, meter_id, site_name, site_address, billing_period_start, billing_period_end, consumption_kwh, consumption_unit, demand_kw, tariff_code, supplier_name, invoice_number, invoice_date
    headers = [
        'account_number', 'meter_id', 'site_name', 'site_address', 
        'billing_period_start', 'billing_period_end', 'consumption_kwh', 'consumption_unit', 
        'demand_kw', 'tariff_code', 'supplier_name', 'invoice_number', 'invoice_date'
    ]
    
    rows = []
    
    # Meter 1: UK region (supplier UK Power Network) - 12 months in 2023
    start_date_uk = datetime(2022, 12, 14)
    for month in range(12):
        bp_start = start_date_uk + timedelta(days=month * 30)
        bp_end = bp_start + timedelta(days=30)
        inv_date = bp_end + timedelta(days=5)
        
        qty = round(random.uniform(1500, 3500), 2)
        unit = 'kWh' if month % 4 != 0 else 'MWh'  # Mix units
        if unit == 'MWh':
            qty = round(qty / 1000, 3)
            
        rows.append([
            'AC-UK-99281', 'METER-UK-01', 'London Plant', '100 Green Rd, London, UK',
            bp_start.strftime('%Y-%m-%d'), bp_end.strftime('%Y-%m-%d'),
            qty, unit, '25', 'UK-BUS-01', 'UK Power Network',
            f'INV-UK-{1000 + month}', inv_date.strftime('%Y-%m-%d')
        ])

    # Meter 2: US region (WECC Energy) - 12 months in 2023
    start_date_us = datetime(2022, 12, 15)
    for month in range(12):
        bp_start = start_date_us + timedelta(days=month * 30)
        bp_end = bp_start + timedelta(days=30)
        inv_date = bp_end + timedelta(days=4)
        
        # Override to create the 2 dirty rows
        qty = round(random.uniform(5000, 9000), 2)
        unit = 'kWh'
        
        # Row 10 of US Meter: consumption = 0 (Flagged)
        if month == 5:
            qty = 0.0
            
        # Row 11 of US Meter: billing period 38 days (Flagged)
        if month == 9:
            bp_end = bp_start + timedelta(days=38)
            
        rows.append([
            'AC-US-77112', 'METER-US-WECC', 'Denver Warehouse', '500 Rockies Blvd, Denver, US',
            bp_start.strftime('%Y-%m-%d'), bp_end.strftime('%Y-%m-%d'),
            qty, unit, '', 'US-COMM-WECC', 'WECC Energy',
            f'INV-US-{5000 + month}', inv_date.strftime('%Y-%m-%d')
        ])

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

def generate_travel_data(filepath):
    # Columns: report_id, employee_id, employee_name, department, expense_type, transaction_date, origin, destination, distance_km, amount_usd, currency, vendor_name, booking_class, trip_purpose, nights
    headers = [
        'report_id', 'employee_id', 'employee_name', 'department', 
        'expense_type', 'transaction_date', 'origin', 'destination', 
        'distance_km', 'amount_usd', 'currency', 'vendor_name', 
        'booking_class', 'trip_purpose', 'nights'
    ]
    
    rows = []
    employees = [
        ('EMP001', 'Alice Smith', 'Engineering'),
        ('EMP002', 'Bob Jones', 'Sales'),
        ('EMP003', 'Charlie Brown', 'Marketing'),
    ]
    
    expense_types = ['Airfare', 'Hotel', 'Car Rental', 'Rail', 'Taxi/Rideshare']
    start_date = datetime(2024, 1, 1)

    # We need 40 rows.
    # We will generate a mix of all expense types.
    # Include major international flights (LHR-JFK, BOM-DXB, SIN-SYD)
    flights = [
        ('LHR', 'JFK', 'British Airways', 'Y', 5576), # Econ
        ('LHR', 'JFK', 'Virgin Atlantic', 'C', 5576), # Business
        ('BOM', 'DXB', 'Emirates', 'F', 1930),        # First
        ('SIN', 'SYD', 'Singapore Air', 'W', 6298),   # Premium Econ
        ('JFK', 'LAX', 'Delta Air', 'Y', 3982),
        ('CDG', 'HND', 'Air France', 'C', 9713),
    ]

    for i in range(35):
        emp_id, emp_name, dept = random.choice(employees)
        tx_date = start_date + timedelta(days=random.randint(0, 89))
        tx_date_str = tx_date.strftime('%m/%d/%Y')
        exp_type = random.choice(expense_types)
        
        amount = round(random.uniform(50, 1500), 2)
        origin, dest, dist_km, booking_class, nights = '', '', '', '', ''
        vendor = 'Concur Travel'

        if exp_type == 'Airfare':
            fl = random.choice(flights)
            origin, dest, vendor, booking_class, act_dist = fl
            # Blank out distance for some rows to exercise the IATA lookup
            dist_km = act_dist if i % 2 == 0 else ''
            amount = round(act_dist * 0.15 * (1 + (ord(booking_class) % 3) * 0.5), 2)
            
        elif exp_type == 'Hotel':
            origin = ''
            dest = random.choice(['JFK', 'LHR', 'SIN', 'BOM'])
            nights = random.randint(1, 7)
            vendor = 'Hilton'
            amount = round(nights * random.uniform(150, 400), 2)
            
        elif exp_type == 'Car Rental':
            origin = 'JFK'
            vendor = 'Hertz'
            dist_km = random.randint(50, 300)
            amount = round(random.uniform(100, 400), 2)
            
        elif exp_type == 'Rail':
            origin = 'LHR'
            vendor = 'Eurostar'
            dist_km = random.randint(30, 200)
            amount = round(random.uniform(40, 150), 2)
            
        else: # Taxi
            origin = 'BOM'
            vendor = 'Uber'
            dist_km = random.randint(5, 40)
            amount = round(random.uniform(10, 60), 2)
            
        rows.append([
            f'REP-{10000+i}', emp_id, emp_name, dept, 
            exp_type, tx_date_str, origin, dest, 
            dist_km, amount, 'USD', vendor, 
            booking_class, 'Business', nights
        ])
        
    # Add some specific international flights to meet prompt guidelines
    # 1. Flight LHR-JFK with blank distance
    rows.append([
        'REP-10036', 'EMP001', 'Alice Smith', 'Engineering',
        'Airfare', '02/15/2024', 'LHR', 'JFK',
        '', '850.00', 'USD', 'British Airways',
        'Y', 'Client Visit', ''
    ])
    # 2. Flight BOM-DXB with blank distance
    rows.append([
        'REP-10037', 'EMP002', 'Bob Jones', 'Sales',
        'Airfare', '02/20/2024', 'BOM', 'DXB',
        '', '450.00', 'USD', 'Emirates',
        'C', 'Business', ''
    ])

    # Dirty rows:
    # 1. One with origin == destination
    rows.append([
        'REP-10038', 'EMP003', 'Charlie Brown', 'Marketing',
        'Airfare', '03/01/2024', 'LHR', 'LHR',
        '0', '150.00', 'USD', 'British Airways',
        'Y', 'Internal Meeting', ''
    ])
    # 2. One with amount_usd > 10000 ($15,000)
    rows.append([
        'REP-10039', 'EMP002', 'Bob Jones', 'Sales',
        'Airfare', '03/05/2024', 'SIN', 'SYD',
        '6298', '15000.00', 'USD', 'Singapore Air',
        'F', 'Client Visit', ''
    ])
    # 3. Ground travel missing distance
    rows.append([
        'REP-10040', 'EMP001', 'Alice Smith', 'Engineering',
        'Car Rental', '03/10/2024', 'LHR', '',
        '', '250.00', 'USD', 'Enterprise',
        '', 'Business', ''
    ])

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

if __name__ == '__main__':
    os.makedirs('sample_data', exist_ok=True)
    generate_sap_data('sample_data/sap_mb51_export.csv')
    generate_utility_data('sample_data/utility_electricity.csv')
    generate_travel_data('sample_data/concur_travel_export.csv')
    print("Successfully generated all sample datasets in the sample_data/ directory.")
