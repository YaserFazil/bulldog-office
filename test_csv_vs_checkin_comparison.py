"""
Test script to compare ngTeco CSV file with Employee Checkin records from Frappe HR.
Shows what's extra, what's missing, and what matches correctly.
"""

import sys
import os
import csv
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

from frappe_client import fetch_employee_checkins, fetch_frappe_employees


def normalize_name(name):
    """Normalize name for comparison (remove extra spaces, case insensitive)."""
    return ' '.join(name.split()).lower() if name else ''


def compare_csv_with_checkin(csv_file: str, employee_code: str = None):
    """
    Compare ngTeco CSV file with Employee Checkin records from Frappe HR.
    
    Args:
        csv_file: Path to ngTeco CSV file
        employee_code: Optional employee code. If not provided, will try to find from CSV employee name.
    """
    print('📄 Reading ngTeco CSV file...')
    print()
    
    # Parse CSV
    csv_data = []
    employee_name = None
    pay_period = None
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i == 0:  # Timecard Report line
                continue
            elif i == 1:  # Pay Period line
                if len(row) > 3 and row[3]:
                    pay_period = row[3]
            elif i == 2:  # Employee line
                if len(row) > 3 and row[3]:
                    employee_name = row[3]
            elif i == 3:  # Header line
                continue
            else:
                if len(row) >= 4:
                    day = row[0].strip() if row[0] else ''
                    date_str = row[1].strip() if row[1] else ''
                    in_time = row[2].strip() if row[2] else ''
                    out_time = row[3].strip() if row[3] else ''
                    
                    if date_str and (in_time or out_time):
                        try:
                            # Parse date from YYYYMMDD format
                            date_obj = datetime.strptime(date_str, '%Y%m%d').date()
                            csv_data.append({
                                'date': date_obj,
                                'date_str': date_str,
                                'day': day,
                                'in_time': in_time,
                                'out_time': out_time
                            })
                        except:
                            pass
    
    print(f'✅ CSV File Info:')
    print(f'   Employee: {employee_name}')
    print(f'   Pay Period: {pay_period}')
    print(f'   Total records in CSV: {len(csv_data)}')
    print()
    
    # Get employee code if not provided
    if not employee_code:
        employees = fetch_frappe_employees(limit=1000)
        employee_code = None
        
        csv_name_normalized = normalize_name(employee_name)
        
        for emp in employees:
            emp_name_normalized = normalize_name(emp.get('employee_name', ''))
            if emp_name_normalized == csv_name_normalized:
                employee_code = emp.get('name')
                break
        
        if not employee_code:
            print(f'❌ Could not find employee code for: {employee_name}')
            print('Available employees:')
            for emp in employees[:10]:
                print(f'   - {emp.get("name")}: {emp.get("employee_name")}')
            return None
    
    print(f'✅ Found employee code: {employee_code}')
    print()
    
    # Get date range from CSV
    if not csv_data:
        print('❌ No data found in CSV file')
        return None
    
    min_date = min(r['date'] for r in csv_data)
    max_date = max(r['date'] for r in csv_data)
    start_datetime = datetime.combine(min_date, datetime.min.time())
    end_datetime = datetime.combine(max_date, datetime.max.time())
    
    print(f'📅 Date range: {min_date} to {max_date}')
    print()
    
    # Fetch Employee Checkin records from Frappe
    print('🔍 Fetching Employee Checkin records from Frappe HR...')
    checkins = fetch_employee_checkins(employee_code, start_datetime, end_datetime, limit=50000)
    print(f'✅ Found {len(checkins)} checkin records in Frappe HR')
    print()
    
    # Build checkins by date from Frappe
    frappe_by_date = defaultdict(lambda: {'IN': [], 'OUT': []})
    
    for checkin in checkins:
        time_str = checkin.get('time', '')
        log_type = checkin.get('log_type', '')
        name = checkin.get('name', '')
        
        if time_str:
            try:
                # Parse datetime
                if '.' in time_str:
                    dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S.%f')
                else:
                    dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                date_key = dt.date()
                time_only = dt.strftime('%H:%M')
                
                if log_type in ['IN', 'OUT']:
                    frappe_by_date[date_key][log_type].append({
                        'time': time_only,
                        'datetime': dt,
                        'name': name
                    })
            except Exception as e:
                pass
    
    # For each date, get earliest IN and latest OUT
    frappe_daily = {}
    for date_key, records in frappe_by_date.items():
        in_times = sorted(records['IN'], key=lambda x: x['datetime'])
        out_times = sorted(records['OUT'], key=lambda x: x['datetime'], reverse=True)
        
        frappe_daily[date_key] = {
            'IN': in_times[0]['time'] if in_times else None,
            'OUT': out_times[0]['time'] if out_times else None,
            'IN_count': len(in_times),
            'OUT_count': len(out_times)
        }
    
    # Build CSV daily data
    csv_daily = {}
    for record in csv_data:
        csv_daily[record['date']] = {
            'IN': record['in_time'] if record['in_time'] else None,
            'OUT': record['out_time'] if record['out_time'] else None
        }
    
    # Compare
    print('=' * 80)
    print('📊 COMPARISON RESULTS')
    print('=' * 80)
    print()
    
    all_dates = sorted(set(list(csv_daily.keys()) + list(frappe_daily.keys())))
    
    correct_matches = []
    csv_extra = []  # In CSV but not in Frappe or different
    frappe_extra = []  # In Frappe but not in CSV
    mismatches = []  # Same date but different times
    
    for check_date in all_dates:
        csv_record = csv_daily.get(check_date)
        frappe_record = frappe_daily.get(check_date)
        
        if csv_record and frappe_record:
            # Both exist, compare times
            csv_in = csv_record['IN']
            csv_out = csv_record['OUT']
            frappe_in = frappe_record['IN']
            frappe_out = frappe_record['OUT']
            
            if csv_in == frappe_in and csv_out == frappe_out:
                correct_matches.append({
                    'date': check_date,
                    'IN': csv_in,
                    'OUT': csv_out
                })
            else:
                mismatches.append({
                    'date': check_date,
                    'csv_IN': csv_in,
                    'csv_OUT': csv_out,
                    'frappe_IN': frappe_in,
                    'frappe_OUT': frappe_out,
                    'frappe_IN_count': frappe_record['IN_count'],
                    'frappe_OUT_count': frappe_record['OUT_count']
                })
        elif csv_record and not frappe_record:
            # Only in CSV
            csv_extra.append({
                'date': check_date,
                'IN': csv_record['IN'],
                'OUT': csv_record['OUT']
            })
        elif frappe_record and not csv_record:
            # Only in Frappe
            frappe_extra.append({
                'date': check_date,
                'IN': frappe_record['IN'],
                'OUT': frappe_record['OUT'],
                'IN_count': frappe_record['IN_count'],
                'OUT_count': frappe_record['OUT_count']
            })
    
    # Print summary
    print(f'✅ CORRECT MATCHES: {len(correct_matches)}')
    print(f'❌ MISMATCHES: {len(mismatches)}')
    print(f'📄 CSV EXTRA (in CSV but not in Frappe): {len(csv_extra)}')
    print(f'🔵 FRAPPE EXTRA (in Frappe but not in CSV): {len(frappe_extra)}')
    print()
    
    # Show mismatches
    if mismatches:
        print('=' * 80)
        print('❌ MISMATCHES (Same date but different times):')
        print('=' * 80)
        for mismatch in mismatches[:50]:  # Show first 50
            print(f"📅 {mismatch['date']} ({mismatch['date'].strftime('%A')})")
            print(f"   CSV:     IN={mismatch['csv_IN'] or 'N/A':>5}  OUT={mismatch['csv_OUT'] or 'N/A':>5}")
            print(f"   Frappe:  IN={mismatch['frappe_IN'] or 'N/A':>5}  OUT={mismatch['frappe_OUT'] or 'N/A':>5}  (IN count: {mismatch['frappe_IN_count']}, OUT count: {mismatch['frappe_OUT_count']})")
            print()
        if len(mismatches) > 50:
            print(f'... and {len(mismatches) - 50} more mismatches')
        print()
    
    # Show CSV extra
    if csv_extra:
        print('=' * 80)
        print('📄 CSV EXTRA (In CSV but not in Frappe HR):')
        print('=' * 80)
        for extra in csv_extra[:50]:  # Show first 50
            print(f"📅 {extra['date']} ({extra['date'].strftime('%A')}): IN={extra['IN'] or 'N/A':>5}  OUT={extra['OUT'] or 'N/A':>5}")
        if len(csv_extra) > 50:
            print(f'... and {len(csv_extra) - 50} more')
        print()
    
    # Show Frappe extra
    if frappe_extra:
        print('=' * 80)
        print('🔵 FRAPPE EXTRA (In Frappe HR but not in CSV):')
        print('=' * 80)
        for extra in frappe_extra[:50]:  # Show first 50
            print(f"📅 {extra['date']} ({extra['date'].strftime('%A')}): IN={extra['IN'] or 'N/A':>5}  OUT={extra['OUT'] or 'N/A':>5}  (IN count: {extra['IN_count']}, OUT count: {extra['OUT_count']})")
        if len(frappe_extra) > 50:
            print(f'... and {len(frappe_extra) - 50} more')
        print()
    
    # Show some correct matches as confirmation
    if correct_matches:
        print('=' * 80)
        print(f'✅ SAMPLE CORRECT MATCHES (showing first 10 of {len(correct_matches)}):')
        print('=' * 80)
        for match in correct_matches[:10]:
            print(f"📅 {match['date']} ({match['date'].strftime('%A')}): IN={match['IN'] or 'N/A':>5}  OUT={match['OUT'] or 'N/A':>5}")
        print()
    
    # Final summary
    print('=' * 80)
    print('📊 FINAL SUMMARY')
    print('=' * 80)
    print(f'Total dates in CSV: {len(csv_daily)}')
    print(f'Total dates in Frappe: {len(frappe_daily)}')
    print(f'Total unique dates: {len(all_dates)}')
    print()
    if len(all_dates) > 0:
        print(f'✅ Perfect matches: {len(correct_matches)} ({len(correct_matches)/len(all_dates)*100:.1f}%)')
        print(f'❌ Mismatches: {len(mismatches)} ({len(mismatches)/len(all_dates)*100:.1f}%)')
        print(f'📄 CSV only: {len(csv_extra)} ({len(csv_extra)/len(all_dates)*100:.1f}%)')
        print(f'🔵 Frappe only: {len(frappe_extra)} ({len(frappe_extra)/len(all_dates)*100:.1f}%)')
    
    return {
        'correct_matches': correct_matches,
        'mismatches': mismatches,
        'csv_extra': csv_extra,
        'frappe_extra': frappe_extra
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
        employee_code = sys.argv[2] if len(sys.argv) > 2 else None
    else:
        csv_file = 'output/ngteco_csv_20251219_095919.csv'  # Default
        employee_code = None
    
    compare_csv_with_checkin(csv_file, employee_code)

