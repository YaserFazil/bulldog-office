"""
Test script to check for duplicate dates in Attendance records.
Checks if there are multiple Attendance records for the same date.
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

from frappe_client import fetch_employee_attendance


def check_attendance_duplicates(employee_code: str, start_date: date = None, end_date: date = None):
    """
    Check for duplicate dates in Attendance records.
    
    Args:
        employee_code: Frappe Employee code (e.g., 'HR-EMP-00005')
        start_date: Start date (default: 2020-01-01)
        end_date: End date (default: today)
    """
    if start_date is None:
        start_date = date(2020, 1, 1)
    if end_date is None:
        end_date = date.today()
    
    print(f'🔍 Checking Attendance records for: {employee_code}')
    print(f'📅 Date range: {start_date} to {end_date}')
    print()
    
    # Fetch all attendance records
    try:
        attendance_records = fetch_employee_attendance(employee_code, start_date, end_date, limit=10000)
        print(f'✅ Found {len(attendance_records)} total attendance records')
        
        if not attendance_records:
            print('ℹ️ No attendance records found for this employee')
            return
        
        # Group by attendance_date
        by_date = defaultdict(list)
        
        for record in attendance_records:
            attendance_date_str = record.get('attendance_date', '')
            name = record.get('name', '')
            status = record.get('status', '')
            leave_type = record.get('leave_type', '')
            
            if attendance_date_str:
                try:
                    # Parse date - handle different formats
                    try:
                        date_obj = datetime.strptime(attendance_date_str, '%Y-%m-%d').date()
                    except:
                        try:
                            date_obj = datetime.strptime(attendance_date_str, '%d-%m-%Y').date()
                        except:
                            continue
                    
                    by_date[date_obj].append({
                        'name': name,
                        'attendance_date': attendance_date_str,
                        'status': status,
                        'leave_type': leave_type
                    })
                except Exception as e:
                    pass  # Skip parsing errors
        
        # Check for duplicates
        duplicate_dates = []
        for check_date, records in sorted(by_date.items()):
            if len(records) > 1:
                duplicate_dates.append({
                    'date': check_date,
                    'count': len(records),
                    'records': records
                })
        
        if duplicate_dates:
            print(f'❌ Found {len(duplicate_dates)} dates with duplicate Attendance records:')
            print()
            for dup in duplicate_dates[:20]:  # Show first 20
                print(f'📅 Date: {dup["date"]} ({dup["count"]} records)')
                for rec in dup['records']:
                    print(f'     - {rec["name"]}: Status={rec["status"]}, Leave Type={rec.get("leave_type", "N/A")}')
                print()
            
            if len(duplicate_dates) > 20:
                print(f'... and {len(duplicate_dates) - 20} more dates with duplicates')
        else:
            print('✅ SUCCESS! No duplicate dates found! All dates have at most 1 Attendance record.')
        
        # Summary statistics
        print()
        print('📊 Summary:')
        print(f'   Total dates with attendance: {len(by_date)}')
        print(f'   Dates with duplicate records: {len(duplicate_dates)}')
        
        # Show breakdown by status
        if duplicate_dates:
            print()
            print('📋 Breakdown by Status:')
            status_counts = defaultdict(int)
            for dup in duplicate_dates:
                for rec in dup['records']:
                    status_counts[rec['status']] += 1
            for status, count in sorted(status_counts.items()):
                print(f'   {status}: {count} records')
        
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
    
    check_attendance_duplicates(employee_code)

