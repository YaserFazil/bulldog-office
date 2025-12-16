"""
Frappe HR Import Script
Generates Employee Check-in and Attendance records from ngTecho CSV data.

This script:
1. Parses ngTecho CSV format
2. Generates Employee Check-in records (with custom IDs) for days with IN/OUT
3. Generates Attendance records (with custom IDs, synced with check-ins)
4. Handles scenarios: Present, Half Day, Sick, Holiday, Absent
5. Auto-detects weekends/public holidays and creates records
6. Multiplies Sunday work hours by 2.0
"""

import pandas as pd
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
import calendar
import requests
import json
import os
from dotenv import load_dotenv

from frappe_client import _get_base_config, _build_auth_headers, FrappeClientError
import importlib.util
import sys
import os

# Import from page with number in name using importlib.util
# frappe_import_script.py is in bulldog_office root, pages/ is in the same directory
script_dir = os.path.dirname(os.path.abspath(__file__))
pages_dir = os.path.join(script_dir, "pages")
csv_converter_path = os.path.join(pages_dir, "9 CSV to Frappe HR.py")
spec = importlib.util.spec_from_file_location("csv_converter", csv_converter_path)
csv_converter = importlib.util.module_from_spec(spec)
sys.modules["csv_converter"] = csv_converter
spec.loader.exec_module(csv_converter)
parse_ngtecotime_csv = csv_converter.parse_ngtecotime_csv
get_username_by_full_name = csv_converter.get_username_by_full_name

from utils import load_calendar_events, compute_work_duration, hhmm_to_decimal, decimal_hours_to_hhmmss

load_dotenv()


def generate_custom_id(prefix: str, date_obj: date, sequence: int) -> str:
    """
    Generate custom ID in format: {PREFIX}-{MONTH:02d}-{YEAR}-{SEQUENCE:06d}
    Example: EMP-CKIN-08-2025-000001 or EMP-ATT-08-2025-000001
    """
    return f"{prefix}-{date_obj.month:02d}-{date_obj.year}-{sequence:06d}"


def is_weekend_or_holiday(date_obj: date, calendar_events: Dict) -> Tuple[bool, Optional[str]]:
    """
    Check if a date is a weekend or holiday.
    
    Returns:
        (is_weekend_or_holiday, holiday_type)
        holiday_type can be: "Weekend", "Holiday", or None
    """
    # Check if weekend
    if date_obj.weekday() >= 5:  # Saturday (5) or Sunday (6)
        return True, "Weekend"
    
    # Check if holiday from calendar events
    date_str = date_obj.strftime("%Y-%m-%d")
    if date_str in calendar_events:
        event = calendar_events[date_str]
        if "holiday" in str(event).lower() or "weekend" in str(event).lower():
            return True, "Holiday"
    
    return False, None


def determine_attendance_status(
    in_time: Optional[str],
    out_time: Optional[str],
    work_hours: Optional[float],
    standard_hours: float = 8.0,
    is_weekend_or_holiday: bool = False,
    note: Optional[str] = None,
    user_selected_sick_dates: Optional[set] = None,
    user_selected_holiday_dates: Optional[set] = None,
    current_date: Optional[date] = None,
) -> Tuple[str, Optional[str]]:
    """
    Determine attendance status and leave type based on check-in data and user selections.
    
    Args:
        user_selected_sick_dates: Set of dates (date objects) that user marked as sick
        user_selected_holiday_dates: Set of dates (date objects) that user marked as paid holiday
        current_date: Current date being processed (to check against user selections)
    
    Returns:
        (attendance_status, leave_type)
        attendance_status: "Present", "Half Day", "On Leave", "Absent"
        leave_type: "Sick", "Paid Holiday", "Leave Without Pay", None
    """
    # Check user selections first (takes priority)
    if current_date:
        if user_selected_sick_dates and current_date in user_selected_sick_dates:
            return "On Leave", "Sick"
        
        if user_selected_holiday_dates and current_date in user_selected_holiday_dates:
            return "On Leave", "Paid Holiday"
    
    # Check note for sick/holiday indicators (fallback if no user selection)
    note_lower = (note or "").lower()
    
    # Sick day - no check-in needed
    if "sick" in note_lower or note == "Sick":
        return "On Leave", "Sick"
    
    # Holiday - no check-in needed
    if is_weekend_or_holiday or "holiday" in note_lower or "vacation" in note_lower:
        return "On Leave", "Paid Holiday"
    
    # Absent - no check-in and no note indicating leave
    if not in_time and not out_time and not note:
        return "Absent", None
    
    # Present with both IN and OUT
    if in_time and out_time:
        # Calculate work hours if not provided
        if work_hours is None:
            work_duration = compute_work_duration(in_time, out_time)
            if work_duration:
                work_hours = hhmm_to_decimal(work_duration)
        
        # Half day if work hours < 50% of standard
        if work_hours and work_hours < (standard_hours * 0.5):
            return "Half Day", None
        
        return "Present", None
    
    # Only IN or only OUT - treat as present but incomplete
    if in_time or out_time:
        return "Present", None
    
    # Default to absent
    return "Absent", None


def calculate_work_hours_with_sunday_multiplier(
    in_time: Optional[str],
    out_time: Optional[str],
    date_obj: date,
) -> Optional[float]:
    """
    Calculate work hours, multiplying by 2.0 if it's a Sunday.
    
    Returns:
        Work hours in decimal format (already multiplied for Sundays)
    """
    if not in_time or not out_time:
        return None
    
    work_duration = compute_work_duration(in_time, out_time)
    if not work_duration:
        return None
    
    work_hours = hhmm_to_decimal(work_duration)
    
    # Multiply by 2.0 if Sunday
    if date_obj.weekday() == 6:  # Sunday
        work_hours *= 2.0
    
    return work_hours


def fill_missing_weekends_holidays(
    start_date: date,
    end_date: date,
    existing_dates: set,
    calendar_events: Dict,
    employee_username: str,
) -> List[Dict]:
    """
    Generate Attendance records for weekends and holidays that are missing from the CSV.
    
    Returns:
        List of attendance records (dicts) for missing weekends/holidays
    """
    attendance_records = []
    current_date = start_date
    
    while current_date <= end_date:
        if current_date not in existing_dates:
            is_weekend_holiday, holiday_type = is_weekend_or_holiday(current_date, calendar_events)
            
            if is_weekend_holiday:
                # Create attendance record for weekend/holiday
                attendance_records.append({
                    "date": current_date,
                    "employee": employee_username,
                    "status": "On Leave",
                    "leave_type": "Paid Holiday" if holiday_type == "Holiday" else None,
                    "is_weekend_or_holiday": True,
                })
        
        current_date += timedelta(days=1)
    
    return attendance_records


def generate_frappe_records_from_ngtecho_csv(
    csv_file_path: str,
    standard_work_hours: float = 8.0,
    auto_detect_weekends_holidays: bool = True,
    multiply_sunday_hours: bool = True,
    user_selected_sick_dates: Optional[set] = None,
    user_selected_holiday_dates: Optional[set] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate both Employee Check-in and Attendance records from ngTecho CSV.
    
    Args:
        csv_file_path: Path to ngTecho CSV file
        standard_work_hours: Standard work hours per day (default: 8.0)
        auto_detect_weekends_holidays: Auto-create records for missing weekends/holidays
        multiply_sunday_hours: Multiply Sunday work hours by 2.0
    
    Returns:
        (checkin_df, attendance_df) - Two DataFrames ready for Frappe HR import
    """
    # Parse CSV
    with open(csv_file_path, 'rb') as f:
        file_content = f.read()
    
    parsed_data = parse_ngtecotime_csv(file_content)
    employee_full_name = parsed_data['employee']
    employee_username = get_username_by_full_name(employee_full_name)
    
    # Load calendar events for holiday detection
    calendar_events = load_calendar_events()
    
    # Track dates we've processed
    processed_dates = set()
    
    # Lists to store records
    checkin_records = []
    attendance_records = []
    
    # Process each record from CSV
    for record in parsed_data['records']:
        date_str = record['date']
        
        try:
            date_obj = datetime.strptime(date_str, '%Y%m%d').date()
        except:
            continue
        
        processed_dates.add(date_obj)
        in_time = record.get('in_time')
        out_time = record.get('out_time')
        note = record.get('note', '')
        
        # Check if weekend/holiday
        is_weekend_holiday, holiday_type = is_weekend_or_holiday(date_obj, calendar_events)
        
        # Determine attendance status
        work_hours = None
        if in_time and out_time:
            work_hours = calculate_work_hours_with_sunday_multiplier(
                in_time, out_time, date_obj
            ) if multiply_sunday_hours else hhmm_to_decimal(compute_work_duration(in_time, out_time))
        
        attendance_status, leave_type = determine_attendance_status(
            in_time, out_time, work_hours, standard_work_hours,
            is_weekend_holiday, note,
            user_selected_sick_dates=user_selected_sick_dates,
            user_selected_holiday_dates=user_selected_holiday_dates,
            current_date=date_obj,
        )
        
        # Generate Employee Check-in records (only if Present/Half Day with IN/OUT)
        if attendance_status in ["Present", "Half Day"] and in_time:
            # IN record
            try:
                time_parts = in_time.split(':')
                hours = int(time_parts[0])
                minutes = int(time_parts[1])
                # Use YYYY-MM-DD HH:MM:SS format for Frappe HR
                datetime_str = date_obj.strftime('%Y-%m-%d') + f' {hours:02d}:{minutes:02d}:00'
                
                checkin_records.append({
                    'Employee': employee_username,
                    'Time': datetime_str,
                    'Log Type': 'IN'
                })
            except Exception as e:
                print(f"Error processing IN time for {date_str}: {e}")
        
        if attendance_status in ["Present", "Half Day"] and out_time:
            # OUT record
            try:
                time_parts = out_time.split(':')
                hours = int(time_parts[0])
                minutes = int(time_parts[1])
                # Use YYYY-MM-DD HH:MM:SS format for Frappe HR
                datetime_str = date_obj.strftime('%Y-%m-%d') + f' {hours:02d}:{minutes:02d}:00'
                
                checkin_records.append({
                    'Employee': employee_username,
                    'Time': datetime_str,
                    'Log Type': 'OUT'
                })
            except Exception as e:
                print(f"Error processing OUT time for {date_str}: {e}")
        
        # Generate Attendance record for ALL days
        attendance_record = {
            'Employee': employee_username,
            'Attendance Date': date_obj.strftime('%Y-%m-%d'),  # Use YYYY-MM-DD format for Frappe HR
            'Status': attendance_status,
        }
        
        if leave_type:
            attendance_record['Leave Type'] = leave_type
        
        attendance_records.append(attendance_record)
    
    # Auto-detect and fill missing weekends/holidays
    if auto_detect_weekends_holidays and parsed_data.get('pay_period'):
        try:
            # Extract date range from pay period
            # Format: "20250825-20250831"
            period_parts = parsed_data['pay_period'].split('-')
            if len(period_parts) == 2:
                start_date = datetime.strptime(period_parts[0], '%Y%m%d').date()
                end_date = datetime.strptime(period_parts[1], '%Y%m%d').date()
                
                missing_records = fill_missing_weekends_holidays(
                    start_date, end_date, processed_dates, calendar_events, employee_username
                )
                
                for missing_rec in missing_records:
                    attendance_records.append({
                        'Employee': employee_username,
                        'Attendance Date': missing_rec['date'].strftime('%Y-%m-%d'),  # Use YYYY-MM-DD format for Frappe HR
                        'Status': missing_rec['status'],
                        'Leave Type': missing_rec.get('leave_type'),
                    })
        except Exception as e:
            print(f"Error filling missing weekends/holidays: {e}")
    
    # Create DataFrames
    checkin_df = pd.DataFrame(checkin_records) if checkin_records else pd.DataFrame()
    attendance_df = pd.DataFrame(attendance_records) if attendance_records else pd.DataFrame()
    
    return checkin_df, attendance_df


def import_to_frappe_hr(
    checkin_df: pd.DataFrame,
    attendance_df: pd.DataFrame,
    dry_run: bool = True,
) -> Dict[str, any]:
    """
    Import Employee Check-in and Attendance records to Frappe HR via API.
    
    Args:
        checkin_df: DataFrame with Employee Check-in records
        attendance_df: DataFrame with Attendance records
        dry_run: If True, only validate without actually importing
    
    Returns:
        Dict with import results and statistics
    """
    base_url, _, _ = _get_base_config()
    headers = _build_auth_headers()
    
    results = {
        'checkin_imported': 0,
        'checkin_failed': 0,
        'attendance_imported': 0,
        'attendance_failed': 0,
        'errors': [],
    }
    
    if dry_run:
        return {
            **results,
            'dry_run': True,
            'checkin_count': len(checkin_df),
            'attendance_count': len(attendance_df),
        }
    
    # Import Employee Check-in records
    for _, row in checkin_df.iterrows():
        try:
            checkin_data = {
                'employee': row['Employee'],
                'time': row['Time'],
                'log_type': row['Log Type'],
            }
            
            url = f"{base_url}/api/resource/Employee Checkin"
            resp = requests.post(url, headers=headers, json=checkin_data, timeout=60)
            
            if resp.status_code in [200, 201]:
                results['checkin_imported'] += 1
            else:
                results['checkin_failed'] += 1
                results['errors'].append(f"Check-in failed: {resp.text}")
        except Exception as e:
            results['checkin_failed'] += 1
            results['errors'].append(f"Check-in error: {str(e)}")
    
    # Import Attendance records
    for _, row in attendance_df.iterrows():
        try:
            attendance_data = {
                'employee': row['Employee'],
                'attendance_date': row['Attendance Date'],
                'status': row['Status'],
            }
            
            if 'Leave Type' in row and pd.notna(row['Leave Type']):
                attendance_data['leave_type'] = row['Leave Type']
            
            url = f"{base_url}/api/resource/Attendance"
            resp = requests.post(url, headers=headers, json=attendance_data, timeout=60)
            
            if resp.status_code in [200, 201]:
                results['attendance_imported'] += 1
            else:
                results['attendance_failed'] += 1
                results['errors'].append(f"Attendance failed: {resp.text}")
        except Exception as e:
            results['attendance_failed'] += 1
            results['errors'].append(f"Attendance error: {str(e)}")
    
    return results


if __name__ == "__main__":
    # Example usage
    csv_path = "path/to/ngtecho_file.csv"
    checkin_df, attendance_df = generate_frappe_records_from_ngtecho_csv(
        csv_path,
        standard_work_hours=8.0,
        auto_detect_weekends_holidays=True,
        multiply_sunday_hours=True,
    )
    
    print(f"Generated {len(checkin_df)} check-in records")
    print(f"Generated {len(attendance_df)} attendance records")
    
    # Export to Excel
    with pd.ExcelWriter('frappe_import.xlsx', engine='openpyxl') as writer:
        checkin_df.to_excel(writer, sheet_name='Employee Checkin', index=False)
        attendance_df.to_excel(writer, sheet_name='Attendance', index=False)
    
    print("Exported to frappe_import.xlsx")

