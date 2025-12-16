import os
import json
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

import requests
import pandas as pd


class FrappeClientError(Exception):
    """Custom exception for Frappe client errors."""


def _get_base_config() -> Tuple[str, str, str]:
    """
    Read base configuration for Frappe API from environment variables.

    Expected env vars:
      - FRAPPE_BASE_URL   (e.g. https://your-site.com)
      - FRAPPE_API_KEY
      - FRAPPE_API_SECRET
    """
    base_url = os.getenv("FRAPPE_BASE_URL")
    api_key = os.getenv("FRAPPE_API_KEY")
    api_secret = os.getenv("FRAPPE_API_SECRET")

    if not base_url or not api_key or not api_secret:
        raise FrappeClientError(
            "Missing Frappe configuration. Please set FRAPPE_BASE_URL, "
            "FRAPPE_API_KEY and FRAPPE_API_SECRET environment variables."
        )
        

    # Ensure no trailing slash to avoid '//' in URLs
    base_url = base_url.rstrip("/")
    return base_url, api_key, api_secret


def _build_auth_headers() -> Dict[str, str]:
    """
    Build Authorization header for token based auth:
    Authorization: token api_key:api_secret
    """
    _, api_key, api_secret = _get_base_config()
    return {
        "Authorization": f"token {api_key}:{api_secret}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def fetch_frappe_employees(limit: int = 1000) -> List[Dict]:
    """
    Fetch a list of Employee records from Frappe for selection in the UI.

    Returns a list of dicts with at least:
      - name          (Employee ID/code)
      - employee_name (Human-readable name)
    """
    base_url, _, _ = _get_base_config()
    url = f"{base_url}/api/resource/Employee"

    params = {
        "fields": '["name", "employee_name", "status"]',
        "limit_page_length": limit,
        "order_by": "employee_name asc",
    }

    headers = _build_auth_headers()
    resp = requests.get(url, headers=headers, params=params, timeout=30)

    if resp.status_code != 200:
        raise FrappeClientError(
            f"Frappe API error {resp.status_code}: {resp.text}"
        )

    data = resp.json()
    if not isinstance(data, dict) or "data" not in data:
        raise FrappeClientError(f"Unexpected response format from Frappe: {data}")

    return data["data"]


def _add_hhmm_times(time1: str, time2: str) -> str:
    """
    Add two HH:MM time values (handles negative values like "-15:32").
    
    Args:
        time1: First time in HH:MM format (e.g., "15:32", "-15:32", "00:00")
        time2: Second time in HH:MM format (e.g., "08:15", "-02:30", "00:00")
    
    Returns:
        Sum of the two times in HH:MM format (e.g., "23:47", "-17:02", "05:45")
    """
    from utils import hhmm_to_decimal, decimal_hours_to_hhmmss
    
    try:
        # Convert both times to decimal hours
        decimal1 = hhmm_to_decimal(time1) if time1 else 0.0
        decimal2 = hhmm_to_decimal(time2) if time2 else 0.0
        
        # Add them
        total_decimal = decimal1 + decimal2
        
        # Convert back to HH:MM format
        return decimal_hours_to_hhmmss(total_decimal)
    except Exception as e:
        # If conversion fails, return "00:00" as fallback
        print(f"Error adding HH:MM times '{time1}' + '{time2}': {e}")
        return "00:00"


def _float_hours_to_hhmm(hours_float: float) -> str:
    """
    Convert float hours (e.g., 8.0, 8.5, 7.75) to HH:MM format.
    
    Args:
        hours_float: Hours as float (e.g., 8.0 for 8 hours, 8.5 for 8 hours 30 minutes)
    
    Returns:
        Hours in HH:MM format (e.g., "08:00", "08:30", "07:45")
    """
    try:
        hours = int(hours_float)
        minutes = int(round((hours_float - hours) * 60))
        
        # Handle rounding up to next hour
        if minutes == 60:
            minutes = 0
            hours += 1
        
        return f"{hours:02d}:{minutes:02d}"
    except (ValueError, TypeError):
        return "08:00"  # Default fallback


def _calculate_hours_from_time_range(start_time: str, end_time: str) -> Optional[str]:
    """
    Calculate hours difference between start_time and end_time.
    Handles night shifts that cross midnight.
    
    Args:
        start_time: Time string in HH:MM:SS format
        end_time: Time string in HH:MM:SS format
    
    Returns:
        Hours in HH:MM format, or None if calculation fails
    """
    try:
        # Parse times (assuming HH:MM:SS or HH:MM format)
        start_parts = start_time.split(":")
        end_parts = end_time.split(":")
        
        start_hour = int(start_parts[0])
        start_min = int(start_parts[1]) if len(start_parts) > 1 else 0
        
        end_hour = int(end_parts[0])
        end_min = int(end_parts[1]) if len(end_parts) > 1 else 0
        
        # Convert to minutes for easier calculation
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        
        # Handle night shift (end < start means it crosses midnight)
        if end_minutes < start_minutes:
            end_minutes += 24 * 60  # Add 24 hours
        
        diff_minutes = end_minutes - start_minutes
        hours = diff_minutes // 60
        minutes = diff_minutes % 60
        
        return f"{hours:02d}:{minutes:02d}"
    except Exception:
        return None


def fetch_employee_time_config(employee_code: str, report_start_date: Optional[date] = None) -> Dict[str, Optional[str]]:
    """
    Fetch per-employee configuration from Frappe for:
      - standard work hours per day (from Employee's default_shift -> Shift Type's "Standard Work Hours" field)
      - initial overtime balance
      - initial holiday hours

    Standard hours are fetched from the "Standard Work Hours" custom field in the Shift Type 
    associated with the employee's default_shift.
    Field names for overtime and holiday hours can be configured via environment variables:
      - FRAPPE_INIT_OVERTIME_FIELD  (default: "initial_overtime_balance")
      - FRAPPE_INIT_HOLIDAY_FIELD   (default: "initial_holiday_hours")
    """
    base_url, _, _ = _get_base_config()

    overtime_field = os.getenv("FRAPPE_INIT_OVERTIME_FIELD", "initial_overtime_balance")
    holiday_field = os.getenv("FRAPPE_INIT_HOLIDAY_FIELD", "initial_holiday_hours")

    # First, fetch employee - don't specify fields to ensure custom fields are included
    url = f"{base_url}/api/resource/Employee/{employee_code}"
    # Note: Not specifying fields parameter to get all fields including custom fields
    params = {}

    headers = _build_auth_headers()
    resp = requests.get(url, headers=headers, params=params, timeout=30)

    if resp.status_code != 200:
        raise FrappeClientError(
            f"Frappe API error {resp.status_code}: {resp.text}"
        )

    data = resp.json()
    if not isinstance(data, dict) or "data" not in data:
        raise FrappeClientError(f"Unexpected response format from Frappe: {data}")

    doc = data["data"]
    default_shift = doc.get("default_shift")
    # Fetch standard hours from Shift Type if default_shift exists
    # Uses the custom field "Standard Work Hours" from Shift Type DocType
    standard_work_hours = None
    if default_shift:
        try:
            # Fetch Shift Type - don't specify fields to ensure custom fields are included
            shift_url = f"{base_url}/api/resource/Shift Type/{default_shift}"
            # Note: Not specifying fields parameter to get all fields including custom fields
            shift_resp = requests.get(shift_url, headers=headers, timeout=30)
            if shift_resp.status_code == 200:
                shift_data = shift_resp.json()
                if isinstance(shift_data, dict) and "data" in shift_data:
                    shift_doc = shift_data["data"]
                    # Try multiple possible field name variations
                    # Frappe API may return custom fields with spaces, underscores, or different casing
                    std_hours_raw = shift_doc.get("custom_standard_work_hours")
                    
                    # Convert float to HH:MM format if it's a number
                    if std_hours_raw is not None:
                        try:
                            # Handle numeric values (int or float)
                            if isinstance(std_hours_raw, (int, float)):
                                standard_work_hours = _float_hours_to_hhmm(float(std_hours_raw))
                            # Handle string values - try to parse as float first
                            elif isinstance(std_hours_raw, str) and std_hours_raw.strip():
                                # Try parsing as float
                                try:
                                    float_val = float(std_hours_raw)
                                    standard_work_hours = _float_hours_to_hhmm(float_val)
                                except ValueError:
                                    # If it's not a number, assume it's already in HH:MM format
                                    standard_work_hours = std_hours_raw.strip()
                            else:
                                standard_work_hours = str(std_hours_raw) if std_hours_raw else None
                        except Exception as conv_error:
                            # If conversion fails, use None (will fallback in UI)
                            standard_work_hours = None
            else:
                # Log the error but don't fail completely
                pass
        except Exception as e:
            # If shift fetch fails, continue without standard hours
            # This is expected if shift doesn't exist or field is missing
            pass

    # Get custom_initial_overtimeundertime_hours from Employee DocType (primary base value)
    # This field can be: a value (e.g., "15:32" or "-15:32"), "00:00", or null/empty
    custom_initial_overtime = doc.get("custom_initial_overtimeundertime_hours")
    
    # Normalize the custom_initial_overtime value
    base_overtime_hours = None
    if custom_initial_overtime is not None:
        # Convert to string and strip whitespace
        custom_initial_overtime_str = str(custom_initial_overtime).strip()
        # Check if it's not empty and is a valid HH:MM format (including negative)
        if custom_initial_overtime_str and custom_initial_overtime_str not in ["", "None", "null"]:
            # Validate it looks like HH:MM format (with optional negative sign)
            if ":" in custom_initial_overtime_str:
                base_overtime_hours = custom_initial_overtime_str
    
    # Calculate initial overtime from historical Employee Checkin data BEFORE report_start_date
    historical_overtime = "00:00"
    if standard_work_hours and report_start_date:
        try:
            historical_overtime = calculate_historical_overtime_balance(
                employee_code=employee_code,
                standard_work_hours_hhmm=standard_work_hours,
                start_date=report_start_date,
            )
        except Exception as e:
            # If calculation fails, use "00:00"
            print(f"Error calculating historical overtime balance: {e}")
            historical_overtime = "00:00"
    
    # Combine base value with historical calculation based on the 3 scenarios:
    # Scenario 1: base_overtime_hours has a value (e.g., "15:32" or "-15:32") → base + historical
    # Scenario 2: base_overtime_hours is "00:00" → "00:00" + historical = historical
    # Scenario 3: base_overtime_hours is None/empty → only historical (no base)
    if base_overtime_hours is not None:
        # Scenarios 1 & 2: Add base value to historical calculation
        calculated_initial_overtime = _add_hhmm_times(base_overtime_hours, historical_overtime)
    else:
        # Scenario 3: Use only historical calculation (no base value from custom field)
        calculated_initial_overtime = historical_overtime
    
    # Get initial holiday hours from Employee DocType (custom_initial_holiday_hours table)
    # This is now a table (child table) with records containing "year" and "holiday_hours" fields
    holiday_hours_table = doc.get("custom_initial_holiday_hours")
    
    # Handle both table format (list) and old single value format (fallback)
    calculated_initial_holiday_hours = None
    
    if holiday_hours_table and isinstance(holiday_hours_table, list) and len(holiday_hours_table) > 0:
        # New table format: calculate from table
        if report_start_date:
            try:
                calculated_initial_holiday_hours = calculate_holiday_hours_balance_from_table(
                    employee_code=employee_code,
                    holiday_hours_table=holiday_hours_table,
                    standard_work_hours_hhmm=standard_work_hours or "08:00",
                    before_date=report_start_date,
                )
                
                # Update the custom_holiday_hours_balance field in Employee DocType
                try:
                    from utils import hhmm_to_decimal
                    balance_decimal = hhmm_to_decimal(calculated_initial_holiday_hours)
                    update_employee_holiday_hours_balance(
                        employee_code=employee_code,
                        balance_hours=balance_decimal,
                    )
                except Exception as update_error:
                    print(f"Warning: Could not update holiday hours balance field: {update_error}")
            except Exception as e:
                print(f"Error calculating holiday hours balance from table: {e}")
                calculated_initial_holiday_hours = "00:00"
        else:
            # No report_start_date, sum all allocations
            try:
                from utils import decimal_hours_to_hhmmss
                total_allocated = 0.0
                for record in holiday_hours_table:
                    holiday_hours = record.get("holiday_hours")
                    if holiday_hours is not None:
                        try:
                            total_allocated += float(holiday_hours)
                        except (ValueError, TypeError):
                            continue
                calculated_initial_holiday_hours = decimal_hours_to_hhmmss(total_allocated) if total_allocated > 0 else "00:00"
            except Exception:
                calculated_initial_holiday_hours = "00:00"
    else:
        # Fallback to old field format (single value)
        initial_holiday_hours_per_year = doc.get(holiday_field)
        if initial_holiday_hours_per_year is not None:
            try:
                from utils import decimal_hours_to_hhmmss
                if isinstance(initial_holiday_hours_per_year, str):
                    initial_holiday_hours_per_year = float(initial_holiday_hours_per_year)
                else:
                    initial_holiday_hours_per_year = float(initial_holiday_hours_per_year)
                calculated_initial_holiday_hours = decimal_hours_to_hhmmss(initial_holiday_hours_per_year)
            except (ValueError, TypeError):
                calculated_initial_holiday_hours = None
    
    # Final fallback
    if calculated_initial_holiday_hours is None:
        calculated_initial_holiday_hours = "00:00"
    
    return {
        "name": doc.get("name"),
        "employee_name": doc.get("employee_name"),
        "standard_work_hours": standard_work_hours,
        "initial_overtime": calculated_initial_overtime,
        "initial_holiday_hours": calculated_initial_holiday_hours,
    }


def fetch_employee_attendance(
    employee_code: str,
    start_date: date,
    end_date: date,
    limit: int = 10000,
) -> List[Dict]:
    """
    Fetch Attendance records for a single employee in a date range.

    Args:
        employee_code: Frappe Employee name/code (e.g. EMP-0001 or username2).
        start_date: Start date (inclusive).
        end_date: End date (inclusive).
        limit: Max number of records to fetch.

    Returns:
        List of raw Attendance documents from Frappe.
    """
    base_url, _, _ = _get_base_config()
    url = f"{base_url}/api/resource/Attendance"

    # Frappe filters are passed as JSON string
    filters = [
        ["Attendance", "employee", "=", employee_code],
        ["Attendance", "attendance_date", ">=", start_date.strftime("%Y-%m-%d")],
        ["Attendance", "attendance_date", "<=", end_date.strftime("%Y-%m-%d")],
    ]

    params = {
        "fields": '["name", "employee", "attendance_date", "status", "leave_type"]',
        # Frappe expects JSON string in `filters`
        "filters": json.dumps(filters),
        "limit_page_length": limit,
        "order_by": "attendance_date asc",
    }

    headers = _build_auth_headers()
    resp = requests.get(url, headers=headers, params=params, timeout=30)

    if resp.status_code != 200:
        raise FrappeClientError(
            f"Frappe API error {resp.status_code}: {resp.text}"
        )

    data = resp.json()
    if not isinstance(data, dict) or "data" not in data:
        raise FrappeClientError(f"Unexpected response format from Frappe: {data}")

    return data["data"]


def build_daily_rows_from_attendance_and_checkins(
    attendance_records: List[Dict],
    checkins_by_date: Dict[str, Dict[str, Optional[str]]],
) -> List[Dict]:
    """
    Build daily rows from Attendance records, filling in IN/OUT times from Employee Checkin data.
    
    Args:
        attendance_records: List of Attendance records from Frappe
        checkins_by_date: Dict mapping date (YYYY-MM-DD) -> {"IN": "HH:MM", "OUT": "HH:MM"}
    
    Returns:
        List of daily row dictionaries with Date, Day, IN, OUT, Status, Leave Type
    """
    daily_rows: List[Dict] = []
    
    for record in attendance_records:
        try:
            attendance_date_str = record.get("attendance_date")
            if not attendance_date_str:
                continue
            
            # Parse date (Frappe format: YYYY-MM-DD or DD-MM-YYYY)
            try:
                date_obj = datetime.strptime(attendance_date_str, "%Y-%m-%d").date()
            except:
                try:
                    date_obj = datetime.strptime(attendance_date_str, "%d-%m-%Y").date()
                except:
                    continue
            
            day_name = date_obj.strftime("%a").upper()
            date_key = date_obj.isoformat()
            
            # Get IN/OUT times from checkins if available
            checkin_data = checkins_by_date.get(date_key, {})
            in_time = checkin_data.get("IN")
            out_time = checkin_data.get("OUT")
            
            # Get attendance status and leave type
            status = record.get("status", "")
            leave_type = record.get("leave_type", "")
            
            daily_rows.append(
                {
                    "Day": day_name,
                    "Date": date_obj,
                    "IN": in_time,
                    "OUT": out_time,
                    "Status": status,
                    "Leave Type": leave_type,
                }
            )
        except Exception as e:
            continue
    
    return daily_rows


def fetch_employee_checkins(
    employee_code: str,
    start: datetime,
    end: datetime,
    limit: int = 5000,
) -> List[Dict]:
    """
    Fetch Employee Checkin records for a single employee in a date range.

    Args:
        employee_code: Frappe Employee name/code (e.g. EMP-0001 or username2).
        start: Start datetime (inclusive).
        end: End datetime (inclusive).
        limit: Max number of records to fetch.

    Returns:
        List of raw Employee Checkin documents from Frappe.
    """
    base_url, _, _ = _get_base_config()
    url = f"{base_url}/api/resource/Employee Checkin"

    # Frappe filters are passed as JSON string
    filters = [
        ["Employee Checkin", "employee", "=", employee_code],
        ["Employee Checkin", "time", ">=", start.strftime("%Y-%m-%d 00:00:00")],
        ["Employee Checkin", "time", "<=", end.strftime("%Y-%m-%d 23:59:59")],
    ]

    params = {
        "fields": '["name", "employee", "time", "log_type", "skip_auto_attendance"]',
        # Frappe expects JSON string in `filters`
        "filters": json.dumps(filters),
        "limit_page_length": limit,
        "order_by": "time asc",
    }

    headers = _build_auth_headers()
    resp = requests.get(url, headers=headers, params=params, timeout=30)

    if resp.status_code != 200:
        raise FrappeClientError(
            f"Frappe API error {resp.status_code}: {resp.text}"
        )

    data = resp.json()
    if not isinstance(data, dict) or "data" not in data:
        raise FrappeClientError(f"Unexpected response format from Frappe: {data}")

    return data["data"]


def build_daily_checkins_from_employee_checkins(
    checkins: List[Dict],
) -> List[Dict]:
    """
    Transform raw Employee Checkin entries into daily IN/OUT rows.

    Strategy:
      - Group by date (based on 'time')
      - For each date:
          * Earliest IN as IN
          * Latest OUT as OUT
      - If only IN or only OUT exists, keep the one we have and leave the other empty.
    """
    by_date: Dict[str, Dict[str, Optional[datetime]]] = {}

    for row in checkins:
        time_str = row.get("time")
        log_type = row.get("log_type")
        if not time_str or not log_type:
            continue

        try:
            ts = datetime.fromisoformat(time_str)
        except ValueError:
            # Fallback: try common Frappe datetime format
            try:
                ts = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S.%f")
            except Exception:
                continue

        date_key = ts.date().isoformat()
        if date_key not in by_date:
            by_date[date_key] = {"in": None, "out": None}

        if log_type.upper() == "IN":
            current_in = by_date[date_key]["in"]
            if current_in is None or ts < current_in:
                by_date[date_key]["in"] = ts
        elif log_type.upper() == "OUT":
            current_out = by_date[date_key]["out"]
            if current_out is None or ts > current_out:
                by_date[date_key]["out"] = ts

    daily_rows: List[Dict] = []
    for date_key, times in sorted(by_date.items()):
        dt = datetime.fromisoformat(date_key)
        day_name = dt.strftime("%a").upper()
        in_time = times["in"].strftime("%H:%M") if times["in"] else None
        out_time = times["out"].strftime("%H:%M") if times["out"] else None

        daily_rows.append(
            {
                "Day": day_name,
                "Date": dt.date(),
                "IN": in_time,
                "OUT": out_time,
            }
        )

    return daily_rows


def calculate_historical_overtime_balance(
    employee_code: str,
    standard_work_hours_hhmm: str = "08:00",
    start_date: Optional[date] = None,
) -> str:
    """
    Calculate cumulative overtime/undertime balance from Employee Checkin data BEFORE the start_date.
    
    Scenarios:
    1. If start_date is None or there's no data before start_date → return "00:00"
    2. If there's data before start_date → calculate balance from all records before start_date
    
    This function:
    1. Fetches Employee Checkin records BEFORE the start_date (if provided)
    2. Groups data by year
    3. For each year, calculates daily work hours vs standard hours
    4. Accumulates overtime balance year by year
    5. Returns the final balance as HH:MM string (e.g., "04:30" or "-02:15")
    
    Args:
        employee_code: Frappe Employee name/code
        standard_work_hours_hhmm: Standard work hours per day in HH:MM format (default: "08:00")
        start_date: Only calculate from records BEFORE this date. If None, returns "00:00"
    
    Returns:
        Final overtime balance in HH:MM format (positive = overtime, negative = undertime)
    """
    # Import utils functions for time calculations
    from utils import (
        compute_work_duration,
        adjust_work_time_and_break,
        compute_time_difference,
        hhmm_to_decimal,
        decimal_hours_to_hhmmss,
    )
    
    # If no start_date provided, return zero balance
    if start_date is None:
        return "00:00"
    
    base_url, _, _ = _get_base_config()
    
    # Fetch checkins BEFORE the start_date only
    url = f"{base_url}/api/resource/Employee Checkin"
    filters = [
        ["Employee Checkin", "employee", "=", employee_code],
        ["Employee Checkin", "time", "<", start_date.strftime("%Y-%m-%d 00:00:00")],
    ]
    
    params = {
        "fields": '["name", "employee", "time", "log_type", "skip_auto_attendance"]',
        "filters": json.dumps(filters),
        "limit_page_length": 50000,  # Large limit to get all historical data
        "order_by": "time asc",
    }
    
    headers = _build_auth_headers()
    resp = requests.get(url, headers=headers, params=params, timeout=60)
    
    if resp.status_code != 200:
        raise FrappeClientError(
            f"Frappe API error {resp.status_code}: {resp.text}"
        )
    
    data = resp.json()
    if not isinstance(data, dict) or "data" not in data:
        raise FrappeClientError(f"Unexpected response format from Frappe: {data}")
    
    all_checkins = data["data"]
    
    if not all_checkins:
        return "00:00"  # No data before start_date, return zero balance
    
    # Build daily checkins from all records
    daily_rows = build_daily_checkins_from_employee_checkins(all_checkins)
    
    if not daily_rows:
        return "00:00"
    
    # Convert to DataFrame for easier processing
    df = pd.DataFrame(daily_rows)
    df['Date'] = pd.to_datetime(df['Date'])
    
    # Group by year
    df['Year'] = df['Date'].dt.year
    years = sorted(df['Year'].unique())
    
    # Initialize running balance
    running_overtime_balance = 0.0  # In decimal hours
    
    # Process year by year
    for year in years:
        year_data = df[df['Year'] == year].copy()
        year_data = year_data.sort_values('Date')
        
        # Calculate work duration for each day
        year_data[" Daily Total"] = year_data.apply(
            lambda row: compute_work_duration(row.get("IN", ""), row.get("OUT", "")), axis=1
        )
        
        # Adjust work time and break (using default break rules)
        year_data["Work Time"], year_data["Break"] = zip(
            *year_data.apply(
                lambda row: adjust_work_time_and_break(
                    row[" Daily Total"],
                    row.get("Break"),
                    "06:00",  # break_rule_hours
                    "00:30",  # break_hours
                ),
                axis=1,
            )
        )
        
        # Set standard time for all days
        year_data["Standard Time"] = standard_work_hours_hhmm
        
        # Calculate difference (work time - standard time) for each day
        year_data["Difference (Decimal)"] = year_data.apply(
            lambda row: compute_time_difference(
                row.get("Work Time", ""),
                row.get("Standard Time", ""),
                None,  # No holiday info in historical calculation
                False,  # Return decimal
            ),
            axis=1,
        )
        
        # Accumulate overtime balance for this year
        for _, row in year_data.iterrows():
            diff_decimal = row.get("Difference (Decimal)")
            if diff_decimal is not None and pd.notna(diff_decimal):
                try:
                    diff_val = float(diff_decimal)
                    running_overtime_balance += diff_val
                except (ValueError, TypeError):
                    pass
    
    # Convert final balance to HH:MM format
    return decimal_hours_to_hhmmss(running_overtime_balance)


def calculate_holiday_hours_balance_from_table(
    employee_code: str,
    holiday_hours_table: List[Dict],
    standard_work_hours_hhmm: str = "08:00",
    before_date: Optional[date] = None,
) -> str:
    """
    Calculate holiday hours balance from the custom_initial_holiday_hours table.
    
    The table contains child records with:
    - year: select field (e.g., "2024", "2025")
    - holiday_hours: float field (allocated hours for that year)
    
    Args:
        employee_code: Frappe Employee name/code
        holiday_hours_table: List of dicts from custom_initial_holiday_hours table
        standard_work_hours_hhmm: Standard work hours per day
        before_date: Calculate balance up to (but not including) this date
    
    Returns:
        Total remaining holiday hours balance in HH:MM format
    """
    from utils import hhmm_to_decimal, decimal_hours_to_hhmmss
    
    # Parse holiday hours allocations from table
    allocations_by_year: Dict[int, float] = {}
    for record in holiday_hours_table:
        try:
            year_str = record.get("year")
            holiday_hours = record.get("holiday_hours")
            
            if year_str and holiday_hours is not None:
                # Convert year to int (handle string like "2024" or int)
                try:
                    year = int(year_str) if isinstance(year_str, str) else int(year_str)
                    hours = float(holiday_hours)
                    allocations_by_year[year] = hours
                except (ValueError, TypeError):
                    continue
        except Exception:
            continue
    
    # If no allocations found, return "00:00"
    if not allocations_by_year:
        return "00:00"
    
    # Fetch Attendance records with "Paid Holiday" leave type before the date
    base_url, _, _ = _get_base_config()
    url = f"{base_url}/api/resource/Attendance"
    filters = [
        ["Attendance", "employee", "=", employee_code],
        ["Attendance", "leave_type", "=", "Paid Holiday"],
    ]
    
    if before_date:
        filters.append(["Attendance", "attendance_date", "<", before_date.strftime("%Y-%m-%d")])
    
    params = {
        "fields": '["name", "employee", "attendance_date", "status", "leave_type"]',
        "filters": json.dumps(filters),
        "limit_page_length": 10000,
        "order_by": "attendance_date asc",
    }
    
    headers = _build_auth_headers()
    resp = requests.get(url, headers=headers, params=params, timeout=60)
    
    if resp.status_code != 200:
        raise FrappeClientError(
            f"Frappe API error {resp.status_code}: {resp.text}"
        )
    
    data = resp.json()
    if not isinstance(data, dict) or "data" not in data:
        raise FrappeClientError(f"Unexpected response format from Frappe: {data}")
    
    attendance_records = data["data"]
    
    # Scenario 5: If no data before date range, get allocation for the year of start date
    if not attendance_records and before_date:
        start_year = before_date.year
        if start_year in allocations_by_year:
            return decimal_hours_to_hhmmss(allocations_by_year[start_year])
        else:
            return "00:00"  # No allocation for that year
    
    # Group attendance by year and calculate used hours per year
    standard_hours_decimal = hhmm_to_decimal(standard_work_hours_hhmm)
    used_hours_by_year: Dict[int, float] = {}
    
    for record in attendance_records:
        try:
            attendance_date_str = record.get("attendance_date")
            if not attendance_date_str:
                continue
            
            # Parse date (Frappe format: YYYY-MM-DD or DD-MM-YYYY)
            try:
                date_obj = datetime.strptime(attendance_date_str, "%Y-%m-%d").date()
            except:
                try:
                    date_obj = datetime.strptime(attendance_date_str, "%d-%m-%Y").date()
                except:
                    continue
            
            year = date_obj.year
            leave_type = record.get("leave_type", "")
            
            # Only count "Paid Holiday" leave type
            if leave_type and "Paid Holiday" in str(leave_type):
                if year not in used_hours_by_year:
                    used_hours_by_year[year] = 0.0
                used_hours_by_year[year] += standard_hours_decimal
        except Exception as e:
            continue
    
    # Calculate balance per year (initial - used) for all years with allocations
    total_balance = 0.0
    for year, initial_hours in allocations_by_year.items():
        used_hours = used_hours_by_year.get(year, 0.0)
        balance = initial_hours - used_hours
        total_balance += balance
    
    # Convert to HH:MM format
    return decimal_hours_to_hhmmss(total_balance)


def calculate_holiday_hours_balance_per_year(
    employee_code: str,
    initial_holiday_hours_per_year: float,
    standard_work_hours_hhmm: str = "08:00",
    before_date: Optional[date] = None,
) -> Dict[int, float]:
    """
    Calculate holiday hours balance per year for an employee.
    
    Args:
        employee_code: Frappe Employee name/code
        initial_holiday_hours_per_year: Initial holiday hours allocated per year (float)
        standard_work_hours_hhmm: Standard work hours per day
        before_date: Calculate balance up to (but not including) this date. If None, calculates for all years.
    
    Returns:
        Dict mapping year -> remaining holiday hours balance (float)
    """
    from utils import hhmm_to_decimal
    
    base_url, _, _ = _get_base_config()
    
    # Fetch all Attendance records with "On Leave" status
    url = f"{base_url}/api/resource/Attendance"
    filters = [
        ["Attendance", "employee", "=", employee_code],
        ["Attendance", "status", "=", "On Leave"],
    ]
    
    if before_date:
        filters.append(["Attendance", "attendance_date", "<", before_date.strftime("%Y-%m-%d")])
    
    params = {
        "fields": '["name", "employee", "attendance_date", "status", "leave_type"]',
        "filters": json.dumps(filters),
        "limit_page_length": 10000,
        "order_by": "attendance_date asc",
    }
    
    headers = _build_auth_headers()
    resp = requests.get(url, headers=headers, params=params, timeout=60)
    
    if resp.status_code != 200:
        raise FrappeClientError(
            f"Frappe API error {resp.status_code}: {resp.text}"
        )
    
    data = resp.json()
    if not isinstance(data, dict) or "data" not in data:
        raise FrappeClientError(f"Unexpected response format from Frappe: {data}")
    
    attendance_records = data["data"]
    
    # Group attendance by year and calculate used hours per year
    standard_hours_decimal = hhmm_to_decimal(standard_work_hours_hhmm)
    used_hours_by_year: Dict[int, float] = {}
    
    for record in attendance_records:
        try:
            attendance_date_str = record.get("attendance_date")
            if not attendance_date_str:
                continue
            
            # Parse date (Frappe format: YYYY-MM-DD or DD-MM-YYYY)
            try:
                date_obj = datetime.strptime(attendance_date_str, "%Y-%m-%d").date()
            except:
                try:
                    date_obj = datetime.strptime(attendance_date_str, "%d-%m-%Y").date()
                except:
                    continue
            
            year = date_obj.year
            leave_type = record.get("leave_type", "")
            
            # Count as holiday hours if it's a paid leave type (exclude unpaid)
            if leave_type and "unpaid" not in str(leave_type).lower():
                if year not in used_hours_by_year:
                    used_hours_by_year[year] = 0.0
                used_hours_by_year[year] += standard_hours_decimal
        except Exception as e:
            continue
    
    # Calculate balance per year (initial - used)
    balance_by_year: Dict[int, float] = {}
    for year, used_hours in used_hours_by_year.items():
        balance_by_year[year] = initial_holiday_hours_per_year - used_hours
    
    # If no records found, return empty dict (will be handled by caller)
    return balance_by_year


def update_employee_holiday_hours_balance(
    employee_code: str,
    balance_hours: float,
) -> bool:
    """
    Update the custom_holiday_hours_balance field in Employee DocType.
    
    Args:
        employee_code: Frappe Employee name/code
        balance_hours: Holiday hours balance to set (float)
    
    Returns:
        True if update successful, False otherwise
    """
    base_url, _, _ = _get_base_config()
    headers = _build_auth_headers()
    
    url = f"{base_url}/api/resource/Employee/{employee_code}"
    data = {
        "custom_holiday_hours_balance": balance_hours,
    }
    
    resp = requests.put(url, headers=headers, json=data, timeout=30)
    
    if resp.status_code in [200, 201]:
        return True
    else:
        raise FrappeClientError(
            f"Failed to update holiday hours balance: {resp.status_code} - {resp.text}"
        )


def calculate_holiday_hours_used_before_date(
    employee_code: str,
    before_date: date,
    standard_work_hours_hhmm: str = "08:00",
) -> str:
    """
    Calculate total holiday hours used (from Attendance records) before the specified date.
    
    Args:
        employee_code: Frappe Employee name/code
        before_date: Calculate holiday hours used before this date
        standard_work_hours_hhmm: Standard work hours per day (for calculating full day = 8 hours)
    
    Returns:
        Total holiday hours used in HH:MM format
    """
    from utils import hhmm_to_decimal, decimal_hours_to_hhmmss
    
    base_url, _, _ = _get_base_config()
    
    # Fetch Attendance records with "On Leave" status before the date
    url = f"{base_url}/api/resource/Attendance"
    filters = [
        ["Attendance", "employee", "=", employee_code],
        ["Attendance", "attendance_date", "<", before_date.strftime("%Y-%m-%d")],
        ["Attendance", "status", "=", "On Leave"],
    ]
    
    params = {
        "fields": '["name", "employee", "attendance_date", "status", "leave_type"]',
        "filters": json.dumps(filters),
        "limit_page_length": 10000,
        "order_by": "attendance_date asc",
    }
    
    headers = _build_auth_headers()
    resp = requests.get(url, headers=headers, params=params, timeout=60)
    
    if resp.status_code != 200:
        raise FrappeClientError(
            f"Frappe API error {resp.status_code}: {resp.text}"
        )
    
    data = resp.json()
    if not isinstance(data, dict) or "data" not in data:
        raise FrappeClientError(f"Unexpected response format from Frappe: {data}")
    
    attendance_records = data["data"]
    
    if not attendance_records:
        return "00:00"  # No holiday records found
    
    # Calculate total holiday hours used
    # Count days marked as "On Leave" with leave types that consume holiday hours
    # (Sick, Paid Holiday, Vacation, etc. - but exclude unpaid leave)
    total_holiday_hours = 0.0
    standard_hours_decimal = hhmm_to_decimal(standard_work_hours_hhmm)
    
    for record in attendance_records:
        leave_type = record.get("leave_type", "")
        # Count as holiday hours if it's a paid leave type
        # Exclude "Leave Without Pay" or similar unpaid types
        if leave_type and "unpaid" not in str(leave_type).lower():
            total_holiday_hours += standard_hours_decimal
    
    return decimal_hours_to_hhmmss(total_holiday_hours)


