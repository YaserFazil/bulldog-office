"""
Test script to check for duplicate dates in Employee Checkin records.
Checks if there are multiple IN or OUT records for the same date.
"""

import sys
import os
from datetime import datetime, date
from collections import defaultdict

# Load environment variables
try:
    with open('.env', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                value = value.strip().strip('"').strip("'")
                os.environ[key.strip()] = value
except FileNotFoundError:
    print('⚠️ .env file not found')

from frappe_client import fetch_employee_checkins


def check_employee_checkin_duplicates(employee_code: str, start_date: datetime = None, end_date: datetime = None):
    """
    Check for duplicate dates in Employee Checkin records.
    
    Args:
        employee_code: Frappe Employee code (e.g., 'HR-EMP-00005')
        start_date: Start datetime (default: 2020-01-01)
        end_date: End datetime (default: now)
    """
    if start_date is None:
        start_date = datetime(2020, 1, 1)
    if end_date is None:
        end_date = datetime.now()
    
    print(f'🔍 Checking Employee Checkin records for: {employee_code}')
    print(f'📅 Date range: {start_date.date()} to {end_date.date()}')
    print()
    
    # Fetch all checkins
    try:
        checkins = fetch_employee_checkins(employee_code, start_date, end_date, limit=50000)
        print(f'✅ Found {len(checkins)} total checkin records')
        
        if not checkins:
            print('ℹ️ No checkin records found for this employee')
            return
        
        # Group by date and log_type
        by_date = defaultdict(lambda: {'IN': [], 'OUT': []})
        
        for checkin in checkins:
            time_str = checkin.get('time', '')
            log_type = checkin.get('log_type', '')
            name = checkin.get('name', '')
            
            if time_str:
                try:
                    # Parse datetime - handle different formats
                    if '.' in time_str:
                        dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S.%f')
                    else:
                        dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                    date_key = dt.date()
                    
                    if log_type in ['IN', 'OUT']:
                        by_date[date_key][log_type].append({
                            'name': name,
                            'time': time_str,
                            'log_type': log_type
                        })
                except Exception as e:
                    pass  # Skip parsing errors
        
        # Check for duplicates
        duplicate_dates = []
        for check_date, records in sorted(by_date.items()):
            in_count = len(records['IN'])
            out_count = len(records['OUT'])
            
            if in_count > 1 or out_count > 1:
                duplicate_dates.append({
                    'date': check_date,
                    'IN_count': in_count,
                    'OUT_count': out_count,
                    'IN_records': records['IN'],
                    'OUT_records': records['OUT']
                })
        
        if duplicate_dates:
            print(f'❌ Found {len(duplicate_dates)} dates with duplicate IN/OUT records:')
            print()
            for dup in duplicate_dates[:20]:  # Show first 20
                print(f'📅 Date: {dup["date"]}')
                print(f'   IN records: {dup["IN_count"]}')
                for in_rec in dup['IN_records']:
                    print(f'     - {in_rec["time"]} ({in_rec["name"]})')
                print(f'   OUT records: {dup["OUT_count"]}')
                for out_rec in dup['OUT_records']:
                    print(f'     - {out_rec["time"]} ({out_rec["name"]})')
                print()
            
            if len(duplicate_dates) > 20:
                print(f'... and {len(duplicate_dates) - 20} more dates with duplicates')
        else:
            print('✅ SUCCESS! No duplicate dates found! All dates have at most 1 IN and 1 OUT record.')
        
        # Summary statistics
        print()
        print('📊 Summary:')
        print(f'   Total dates with checkins: {len(by_date)}')
        print(f'   Dates with duplicate IN: {sum(1 for d in duplicate_dates if d["IN_count"] > 1)}')
        print(f'   Dates with duplicate OUT: {sum(1 for d in duplicate_dates if d["OUT_count"] > 1)}')
        print(f'   Dates with both duplicate IN and OUT: {sum(1 for d in duplicate_dates if d["IN_count"] > 1 and d["OUT_count"] > 1)}')
        
        return duplicate_dates
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    if len(sys.argv) > 1:
        employee_code = sys.argv[1]
    else:
        employee_code = 'HR-EMP-00005'  # Default
    
    check_employee_checkin_duplicates(employee_code)

