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

from frappe_client import _get_base_config, _build_auth_headers, FrappeClientError, fetch_employee_time_config
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
    holiday_type: Optional[str] = None,
    note: Optional[str] = None,
    user_selected_sick_dates: Optional[set] = None,
    user_selected_holiday_dates: Optional[set] = None,
    user_selected_absent_dates: Optional[set] = None,
    current_date: Optional[date] = None,
) -> Tuple[str, Optional[str]]:
    """
    Determine attendance status and leave type based on check-in data and user selections.
    
    Args:
        user_selected_sick_dates: Set of dates (date objects) that user marked as sick
        user_selected_holiday_dates: Set of dates (date objects) that user marked as paid holiday
        user_selected_absent_dates: Set of dates (date objects) that user marked as absent
        current_date: Current date being processed (to check against user selections)
    
    Returns:
        (attendance_status, leave_type)
        attendance_status: "Present", "Half Day", "On Leave", "Absent"
        leave_type: "Sick", "Paid Holiday", "Leave Without Pay", None
    """
    # Check user selections first (takes priority)
    # "Is Absent" has highest priority - if marked, always return "Absent"
    if current_date:
        if user_selected_absent_dates and current_date in user_selected_absent_dates:
            return "Absent", None
        
        if user_selected_sick_dates and current_date in user_selected_sick_dates:
            return "On Leave", "Sick"
        
        if user_selected_holiday_dates and current_date in user_selected_holiday_dates:
            return "On Leave", "Paid Holiday"
    
    # Check note for sick/holiday indicators (fallback if no user selection)
    note_lower = (note or "").lower()
    
    # Sick day - no check-in needed
    if "sick" in note_lower or note == "Sick":
        return "On Leave", "Sick"
    
    # Holiday from note - no check-in needed
    if "holiday" in note_lower or "vacation" in note_lower:
        return "On Leave", "Paid Holiday"
    
    # Weekends and public holidays - handle differently
    if is_weekend_or_holiday:
        # If employee worked on weekend/holiday (has IN/OUT times), treat as Present
        if in_time or out_time:
            # Calculate work hours if both times present
            if in_time and out_time:
                if work_hours is None:
                    work_duration = compute_work_duration(in_time, out_time)
                    if work_duration:
                        work_hours = hhmm_to_decimal(work_duration)
                
                # Half day if work hours < 75% of standard
                if work_hours and work_hours < (standard_hours * 0.75):
                    return "Half Day", None
                
                return "Present", None
            else:
                # Only IN or only OUT on weekend/holiday
                return "Present", None
        else:
            # Weekend/holiday with no work times
            # Weekends: Mark as "On Leave" with no leave_type (only if user selected "Is Paid Holiday")
            # Public holidays: Mark as "On Leave" with "Paid Holiday" leave_type
            if holiday_type == "Holiday":
                # Public holiday - mark as "Paid Holiday"
                return "On Leave", "Paid Holiday"
            else:
                # Weekend - mark as "On Leave" with no leave_type
                # Leave type will only be set if user explicitly marked it as "Is Paid Holiday"
                return "On Leave", None
    
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
        if work_hours and work_hours < (standard_hours * 0.75):
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


def validate_business_days_have_times(
    dates_df: pd.DataFrame,
    calendar_events: Optional[Dict] = None,
) -> Tuple[bool, List[Dict]]:
    """
    Validate that all business working days have valid IN and OUT times.
    
    Validation rules:
    - Business working days (weekdays, not holidays): Always require valid IN/OUT times
    - Weekends/Public holidays/Sick days/Paid holidays/Absent days:
      * If IN or OUT time is filled → Include in validation (employee worked that day)
      * If both IN and OUT are empty → Exclude from validation (employee didn't work)
    
    This allows employees who work on weekends/holidays to have their times validated,
    while skipping validation for days when they didn't work.
    
    Args:
        dates_df: DataFrame with columns: Date, IN, OUT, Is Sick, Is Paid Holiday, Is Absent
        calendar_events: Optional dict of calendar events (date_str -> event_name)
    
    Returns:
        (is_valid, missing_days_list)
        is_valid: True if all days that require validation have valid times
        missing_days_list: List of dicts with date and reason for missing times
    """
    if calendar_events is None:
        calendar_events = load_calendar_events()
    
    missing_days = []
    
    for _, row in dates_df.iterrows():
        date_val = row.get('Date')
        
        # Convert date to date object if needed
        try:
            if isinstance(date_val, str):
                try:
                    date_obj = datetime.strptime(date_val, '%Y-%m-%d').date()
                except:
                    date_obj = pd.to_datetime(date_val).date()
            elif isinstance(date_val, date):
                date_obj = date_val
            elif hasattr(date_val, 'date'):
                date_obj = date_val.date()
            elif pd.isna(date_val):
                continue
            else:
                # Try pandas to_datetime for other types (Timestamp, etc.)
                date_obj = pd.to_datetime(date_val).date()
        except Exception:
            # Skip rows with invalid dates
            continue
        
        # Check if it's a weekend (Saturday=5, Sunday=6)
        is_weekend = date_obj.weekday() >= 5
        
        # Check if it's a public holiday
        date_str = date_obj.strftime("%Y-%m-%d")
        is_public_holiday = False
        if date_str in calendar_events:
            event = calendar_events[date_str]
            event_str = str(event).lower()
            # Check if it's a holiday (not just a weekend marker)
            if "holiday" in event_str and "weekend" not in event_str:
                is_public_holiday = True
            # Also check if it's a weekend that's marked as holiday
            elif is_weekend and "holiday" in event_str:
                is_public_holiday = True
        
        # Check if marked as sick, paid holiday, or absent
        is_sick = row.get('Is Sick', False)
        is_paid_holiday = row.get('Is Paid Holiday', False)
        is_absent = row.get('Is Absent', False)
        
        # Get IN and OUT times first
        in_time = str(row.get('IN', '') or '').strip()
        out_time = str(row.get('OUT', '') or '').strip()
        
        # Check if employee worked on this day (has at least IN or OUT time)
        has_work_time = bool(in_time or out_time)
        
        # Skip validation ONLY if:
        # - It's a weekend/public holiday/sick/paid holiday/absent AND
        # - Employee did NOT work that day (no IN or OUT times)
        # If employee worked on a weekend/holiday/sick/paid holiday/absent day, we should validate it
        if (is_weekend or is_public_holiday or is_sick or is_paid_holiday or is_absent) and not has_work_time:
            continue
        
        # For all other days (business days OR days where employee worked), validate IN and OUT times
        
        # Check if times are missing or invalid
        missing_fields = []
        in_time_valid = False
        out_time_valid = False
        in_time_obj = None
        out_time_obj = None
        
        if not in_time:
            missing_fields.append("IN")
        else:
            # Validate IN time format (HH:MM)
            try:
                parts = in_time.split(':')
                if len(parts) != 2:
                    missing_fields.append("IN (invalid format)")
                else:
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
                        missing_fields.append("IN (invalid time)")
                    else:
                        in_time_valid = True
                        # Create a time object for comparison
                        in_time_obj = datetime.strptime(in_time, '%H:%M').time()
            except:
                missing_fields.append("IN (invalid format)")
        
        if not out_time:
            missing_fields.append("OUT")
        else:
            # Validate OUT time format (HH:MM)
            try:
                parts = out_time.split(':')
                if len(parts) != 2:
                    missing_fields.append("OUT (invalid format)")
                else:
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
                        missing_fields.append("OUT (invalid time)")
                    else:
                        out_time_valid = True
                        # Create a time object for comparison
                        out_time_obj = datetime.strptime(out_time, '%H:%M').time()
            except:
                missing_fields.append("OUT (invalid format)")
        
        # If both times are valid, check if OUT is after IN
        if in_time_valid and out_time_valid and in_time_obj and out_time_obj:
            if out_time_obj <= in_time_obj:
                missing_fields.append("OUT must be after IN")
        
        if missing_fields:
            missing_days.append({
                'date': date_obj,
                'date_str': date_obj.strftime('%Y-%m-%d'),
                'day_name': date_obj.strftime('%A'),
                'missing_fields': missing_fields,
            })
    
    is_valid = len(missing_days) == 0
    return is_valid, missing_days


def fetch_employee_standard_work_hours(employee_code: str) -> float:
    """
    Fetch standard work hours for an employee from Frappe HR.
    
    Path: Employee > Default Shift > Shift Type > custom_standard_work_hours
    
    Args:
        employee_code: Frappe Employee code/name
    
    Returns:
        Standard work hours as float (e.g., 8.0). Defaults to 8.0 if not found.
    """
    try:
        time_config = fetch_employee_time_config(employee_code)
        standard_work_hours_str = time_config.get('standard_work_hours')
        print(f"Standard work hours: {standard_work_hours_str}")
        if standard_work_hours_str:
            # Convert HH:MM format to float
            return hhmm_to_decimal(standard_work_hours_str)
        else:
            # Default to 8.0 if not found
            return 8.0
    except Exception as e:
        print(f"Error fetching standard work hours for {employee_code}: {e}")
        # Default to 8.0 on error
        return 8.0


def generate_frappe_records_from_ngtecho_csv(
    csv_file_path: str,
    standard_work_hours: Optional[float] = None,
    auto_detect_weekends_holidays: bool = False,
    multiply_sunday_hours: bool = False,
    user_selected_sick_dates: Optional[set] = None,
    user_selected_holiday_dates: Optional[set] = None,
    edited_dates_df: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate both Employee Check-in and Attendance records from ngTecho CSV.
    
    Args:
        csv_file_path: Path to ngTecho CSV file
        standard_work_hours: Standard work hours per day (float). If None, will fetch from Frappe HR.
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
    
    # Fetch standard work hours from Frappe HR if not provided
    if standard_work_hours is None:
        standard_work_hours = fetch_employee_standard_work_hours(employee_username)
    
    # Load calendar events for holiday detection
    calendar_events = load_calendar_events()
    
    # Track dates we've processed
    processed_dates = set()
    
    # Lists to store records
    checkin_records = []
    attendance_records = []
    
    # Create a mapping of edited dates if provided
    edited_dates_map = {}
    user_selected_absent_dates = set()
    if edited_dates_df is not None and not edited_dates_df.empty:
        for _, row in edited_dates_df.iterrows():
            date_val = row.get('Date')
            if isinstance(date_val, date):
                date_key = date_val
            elif isinstance(date_val, str):
                try:
                    date_key = datetime.strptime(date_val, '%Y-%m-%d').date()
                except:
                    continue
            else:
                continue
            
            edited_dates_map[date_key] = {
                'IN': row.get('IN', ''),
                'OUT': row.get('OUT', ''),
                'Is Edited': row.get('Is Edited', False),
                'Is Sick': row.get('Is Sick', False),
                'Is Paid Holiday': row.get('Is Paid Holiday', False),
                'Is Absent': row.get('Is Absent', False),
            }
            
            # Collect absent dates for determine_attendance_status
            if edited_dates_map[date_key].get('Is Absent', False):
                user_selected_absent_dates.add(date_key)
    
    # Process each record from CSV
    for record in parsed_data['records']:
        date_str = record['date']
        
        try:
            date_obj = datetime.strptime(date_str, '%Y%m%d').date()
        except:
            continue
        
        processed_dates.add(date_obj)
        
        # Check if "Is Absent" is marked - if so, clear IN/OUT times
        is_absent = False
        if date_obj in edited_dates_map:
            is_absent = edited_dates_map[date_obj].get('Is Absent', False)
        
        # Use edited IN/OUT times if available, otherwise use CSV times
        # BUT: If "Is Absent" is marked, always clear IN/OUT times
        if date_obj in edited_dates_map:
            edited_data = edited_dates_map[date_obj]
            if is_absent:
                # Clear times when marked as absent (use empty strings for consistency)
                in_time = ''
                out_time = ''
            else:
                edited_in = edited_data.get('IN', '')
                edited_out = edited_data.get('OUT', '')
                # Use edited times if they're not empty, otherwise fall back to CSV
                in_time = edited_in if edited_in and str(edited_in).strip() else record.get('in_time')
                out_time = edited_out if edited_out and str(edited_out).strip() else record.get('out_time')
            is_date_edited = edited_data.get('Is Edited', False)
        else:
            in_time = record.get('in_time')
            out_time = record.get('out_time')
            is_date_edited = False
        
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
            is_weekend_holiday, holiday_type, note,
            user_selected_sick_dates=user_selected_sick_dates,
            user_selected_holiday_dates=user_selected_holiday_dates,
            user_selected_absent_dates=user_selected_absent_dates,
            current_date=date_obj,
        )
        
        # Generate Employee Check-in records (only if Present/Half Day with IN/OUT)
        # NEVER create checkin records if marked as "Absent"
        if attendance_status in ["Present", "Half Day"] and in_time and not is_absent:
            # IN record
            try:
                time_parts = in_time.split(':')
                hours = int(time_parts[0])
                minutes = int(time_parts[1])
                # Use YYYY-MM-DD HH:MM:SS format for Frappe HR
                datetime_str = date_obj.strftime('%Y-%m-%d') + f' {hours:02d}:{minutes:02d}:00'
                
                checkin_record = {
                    'Employee': employee_username,
                    'Time': datetime_str,
                    'Log Type': 'IN'
                }
                
                # Mark as edited if the date was edited
                if is_date_edited:
                    checkin_record['Is Edited'] = True
                
                checkin_records.append(checkin_record)
            except Exception as e:
                print(f"Error processing IN time for {date_str}: {e}")
        
        # NEVER create checkin records if marked as "Absent"
        if attendance_status in ["Present", "Half Day"] and out_time and not is_absent:
            # OUT record
            try:
                time_parts = out_time.split(':')
                hours = int(time_parts[0])
                minutes = int(time_parts[1])
                # Use YYYY-MM-DD HH:MM:SS format for Frappe HR
                datetime_str = date_obj.strftime('%Y-%m-%d') + f' {hours:02d}:{minutes:02d}:00'
                
                checkin_record = {
                    'Employee': employee_username,
                    'Time': datetime_str,
                    'Log Type': 'OUT'
                }
                
                # Mark as edited if the date was edited
                if is_date_edited:
                    checkin_record['Is Edited'] = True
                
                checkin_records.append(checkin_record)
            except Exception as e:
                print(f"Error processing OUT time for {date_str}: {e}")
        
        # Generate Attendance record only if:
        # 1. Employee worked (has IN/OUT times), OR
        # 2. It's a business day (not weekend/public holiday), OR
        # 3. User explicitly marked it as sick/paid holiday/absent
        should_create_attendance = False
        
        # Check if employee worked (has IN/OUT times)
        has_work_times = bool(in_time or out_time)
        
        # Check if user explicitly marked it (sick, paid holiday, or absent)
        is_user_marked = False
        if date_obj in edited_dates_map:
            edited_data = edited_dates_map[date_obj]
            if edited_data.get('Is Sick', False) or edited_data.get('Is Paid Holiday', False) or edited_data.get('Is Absent', False):
                is_user_marked = True
        # Also check user_selected sets (for backward compatibility)
        if user_selected_sick_dates and date_obj in user_selected_sick_dates:
            is_user_marked = True
        if user_selected_holiday_dates and date_obj in user_selected_holiday_dates:
            is_user_marked = True
        
        # Create attendance record if:
        # - Employee worked (has times), OR
        # - It's a business day (not weekend/holiday), OR
        # - User explicitly marked it
        if has_work_times or not is_weekend_holiday or is_user_marked:
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
    
    # Ensure Is Edited column exists (default to False if not set)
    if not checkin_df.empty and 'Is Edited' not in checkin_df.columns:
        checkin_df['Is Edited'] = False
    
    return checkin_df, attendance_df


def check_existing_records(
    checkin_df: pd.DataFrame,
    attendance_df: pd.DataFrame,
) -> Dict[str, any]:
    """
    Check if records already exist in Frappe HR.
    
    Args:
        checkin_df: DataFrame with Employee Check-in records
        attendance_df: DataFrame with Attendance records
    
    Returns:
        Dict with existing record information
    """
    base_url, _, _ = _get_base_config()
    headers = _build_auth_headers()
    
    existing = {
        'checkin_existing': [],
        'attendance_existing': [],
        'checkin_existing_count': 0,
        'attendance_existing_count': 0,
    }
    
    # Check Employee Check-in records
    if not checkin_df.empty:
        # Get unique employees and time ranges
        employees = checkin_df['Employee'].unique()
        time_min = checkin_df['Time'].min()
        time_max = checkin_df['Time'].max()
        
        for employee in employees:
            try:
                url = f"{base_url}/api/resource/Employee Checkin"
                filters = [
                    ["Employee Checkin", "employee", "=", employee],
                    ["Employee Checkin", "time", ">=", time_min],
                    ["Employee Checkin", "time", "<=", time_max],
                ]
                params = {
                    "fields": '["name", "employee", "time", "log_type"]',
                    "filters": json.dumps(filters),
                    "limit_page_length": 10000,
                }
                resp = requests.get(url, headers=headers, params=params, timeout=60)
                
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and "data" in data:
                        existing_checkins = data["data"]
                        # Create a set of (employee, time, log_type) tuples for quick lookup
                        existing_set = {
                            (c.get("employee"), c.get("time"), c.get("log_type"))
                            for c in existing_checkins
                        }
                        
                        # Check which records from our DataFrame already exist
                        for _, row in checkin_df[checkin_df['Employee'] == employee].iterrows():
                            key = (row['Employee'], row['Time'], row['Log Type'])
                            if key in existing_set:
                                existing['checkin_existing'].append(row.to_dict())
                                existing['checkin_existing_count'] += 1
            except Exception as e:
                print(f"Error checking existing check-ins: {e}")
    
    # Check Attendance records
    if not attendance_df.empty:
        # Get unique employees and date ranges
        employees = attendance_df['Employee'].unique()
        date_min = attendance_df['Attendance Date'].min()
        date_max = attendance_df['Attendance Date'].max()
        
        for employee in employees:
            try:
                url = f"{base_url}/api/resource/Attendance"
                filters = [
                    ["Attendance", "employee", "=", employee],
                    ["Attendance", "attendance_date", ">=", date_min],
                    ["Attendance", "attendance_date", "<=", date_max],
                ]
                params = {
                    "fields": '["name", "employee", "attendance_date", "status", "leave_type"]',
                    "filters": json.dumps(filters),
                    "limit_page_length": 10000,
                }
                resp = requests.get(url, headers=headers, params=params, timeout=60)
                
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and "data" in data:
                        existing_attendance = data["data"]
                        # Create a set of (employee, attendance_date) tuples for quick lookup
                        existing_set = {
                            (a.get("employee"), a.get("attendance_date"))
                            for a in existing_attendance
                        }
                        
                        # Check which records from our DataFrame already exist
                        for _, row in attendance_df[attendance_df['Employee'] == employee].iterrows():
                            key = (row['Employee'], row['Attendance Date'])
                            if key in existing_set:
                                existing['attendance_existing'].append(row.to_dict())
                                existing['attendance_existing_count'] += 1
            except Exception as e:
                print(f"Error checking existing attendance: {e}")
    
    return existing


def import_to_frappe_hr(
    checkin_df: pd.DataFrame,
    attendance_df: pd.DataFrame,
    dry_run: bool = True,
    overwrite_existing: bool = False,
    skip_existing: bool = False,
    existing_records: Optional[Dict] = None,
) -> Dict[str, any]:
    """
    Import Employee Check-in and Attendance records to Frappe HR via API.
    
    Args:
        checkin_df: DataFrame with Employee Check-in records
        attendance_df: DataFrame with Attendance records
        dry_run: If True, only validate without actually importing
        overwrite_existing: If True, delete existing records before importing (for Attendance only)
        skip_existing: If True, skip records that already exist (requires existing_records dict)
        existing_records: Dict with existing records info from check_existing_records()
    
    Returns:
        Dict with import results and statistics, including failed records DataFrames
    """
    base_url, _, _ = _get_base_config()
    headers = _build_auth_headers()
    
    results = {
        'checkin_imported': 0,
        'checkin_failed': 0,
        'attendance_imported': 0,
        'attendance_failed': 0,
        'errors': [],
        'failed_checkin_df': pd.DataFrame(),
        'failed_attendance_df': pd.DataFrame(),
    }
    
    # Filter out existing records if skip_existing is True
    if skip_existing and existing_records:
        # Filter check-in records
        if not checkin_df.empty and existing_records.get('checkin_existing'):
            existing_checkin_set = {
                (str(r.get('Employee', '')), str(r.get('Time', '')), str(r.get('Log Type', '')))
                for r in existing_records['checkin_existing']
            }
            checkin_df = checkin_df[
                ~checkin_df.apply(
                    lambda row: (str(row.get('Employee', '')), str(row.get('Time', '')), str(row.get('Log Type', ''))) in existing_checkin_set,
                    axis=1
                )
            ].copy()
        
        # Filter attendance records
        if not attendance_df.empty and existing_records.get('attendance_existing'):
            existing_attendance_set = {
                (str(r.get('Employee', '')), str(r.get('Attendance Date', '')))
                for r in existing_records['attendance_existing']
            }
            attendance_df = attendance_df[
                ~attendance_df.apply(
                    lambda row: (str(row.get('Employee', '')), str(row.get('Attendance Date', ''))) in existing_attendance_set,
                    axis=1
                )
            ].copy()
    
    if dry_run:
        return {
            **results,
            'dry_run': True,
            'checkin_count': len(checkin_df),
            'attendance_count': len(attendance_df),
        }
    
    # Track failed records
    failed_checkin_records = []
    failed_attendance_records = []
    
    # If overwrite_existing is True, delete existing Attendance records first
    if overwrite_existing and not attendance_df.empty:
        employees = attendance_df['Employee'].unique()
        date_min = attendance_df['Attendance Date'].min()
        date_max = attendance_df['Attendance Date'].max()
        
        for employee in employees:
            try:
                url = f"{base_url}/api/resource/Attendance"
                filters = [
                    ["Attendance", "employee", "=", employee],
                    ["Attendance", "attendance_date", ">=", date_min],
                    ["Attendance", "attendance_date", "<=", date_max],
                ]
                params = {
                    "fields": '["name"]',
                    "filters": json.dumps(filters),
                    "limit_page_length": 10000,
                }
                resp = requests.get(url, headers=headers, params=params, timeout=60)
                
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and "data" in data:
                        for record in data["data"]:
                            record_name = record.get("name")
                            if record_name:
                                delete_url = f"{base_url}/api/resource/Attendance/{record_name}"
                                delete_resp = requests.delete(delete_url, headers=headers, timeout=60)
                                if delete_resp.status_code not in [200, 202]:
                                    results['errors'].append(f"Failed to delete existing attendance {record_name}: {delete_resp.text}")
            except Exception as e:
                results['errors'].append(f"Error deleting existing attendance: {str(e)}")
    
    # Import Employee Check-in records
    for _, row in checkin_df.iterrows():
        try:
            checkin_data = {
                'employee': row['Employee'],
                'time': row['Time'],
                'log_type': row['Log Type'],
            }
            
            # Add custom_is_edited field if the record was manually edited
            # Check if 'Is Edited' column exists and is True
            is_edited = False
            if 'Is Edited' in row:
                is_edited_value = row.get('Is Edited')
                # Handle both boolean and numeric (0/1) values
                if pd.notna(is_edited_value):
                    if isinstance(is_edited_value, bool):
                        is_edited = is_edited_value
                    elif isinstance(is_edited_value, (int, float)):
                        is_edited = bool(is_edited_value)
                    elif str(is_edited_value).lower() in ['true', '1', 'yes']:
                        is_edited = True
            
            if is_edited:
                checkin_data['custom_is_edited'] = 1  # Frappe uses 1 for True, 0 for False
            
            url = f"{base_url}/api/resource/Employee Checkin"
            resp = requests.post(url, headers=headers, json=checkin_data, timeout=60)
            
            if resp.status_code in [200, 201]:
                results['checkin_imported'] += 1
            else:
                results['checkin_failed'] += 1
                error_msg = resp.text
                results['errors'].append(f"Check-in failed: {error_msg}")
                # Store failed record for reimport
                failed_checkin_records.append(row.to_dict())
        except Exception as e:
            results['checkin_failed'] += 1
            error_msg = str(e)
            results['errors'].append(f"Check-in error: {error_msg}")
            # Store failed record for reimport
            failed_checkin_records.append(row.to_dict())
    
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
                error_msg = resp.text
                results['errors'].append(f"Attendance failed: {error_msg}")
                # Store failed record for reimport
                failed_attendance_records.append(row.to_dict())
        except Exception as e:
            results['attendance_failed'] += 1
            error_msg = str(e)
            results['errors'].append(f"Attendance error: {error_msg}")
            # Store failed record for reimport
            failed_attendance_records.append(row.to_dict())
    
    # Create DataFrames for failed records
    if failed_checkin_records:
        results['failed_checkin_df'] = pd.DataFrame(failed_checkin_records)
    if failed_attendance_records:
        results['failed_attendance_df'] = pd.DataFrame(failed_attendance_records)
    
    return results


if __name__ == "__main__":
    # Example usage
    csv_path = "path/to/ngtecho_file.csv"
    checkin_df, attendance_df = generate_frappe_records_from_ngtecho_csv(
        csv_path,
        standard_work_hours=8.0,
        auto_detect_weekends_holidays=False,
        multiply_sunday_hours=False,
    )
    
    print(f"Generated {len(checkin_df)} check-in records")
    print(f"Generated {len(attendance_df)} attendance records")
    
    # Export to Excel
    with pd.ExcelWriter('frappe_import.xlsx', engine='openpyxl') as writer:
        checkin_df.to_excel(writer, sheet_name='Employee Checkin', index=False)
        attendance_df.to_excel(writer, sheet_name='Attendance', index=False)
    
    print("Exported to frappe_import.xlsx")

