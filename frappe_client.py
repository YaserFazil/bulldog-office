import os
import json
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple, Any
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


def normalize_employee_name_for_match(name: str) -> str:
    """
    Normalize a person name for comparing CSV / Mongo / Frappe employee_name fields.
    Strips parenthetical IDs (e.g. "Name (3)"), collapses whitespace, lowercases.
    """
    if not name or not str(name).strip():
        return ""
    base = str(name).split("(")[0].strip()
    return " ".join(base.split()).lower()


def resolve_frappe_employee_code(
    display_name: str,
    mongo_username: Optional[str] = None,
) -> str:
    """
    Map CSV header name and optional Mongo login to Frappe Employee.name (document ID).

    Frappe APIs use Employee.name in URLs and Link fields, not employee_name.
    Mongo often stores a short username (e.g. "Emmanuel") that is not a valid
    Employee.name, while the CSV has the full name that matches Frappe's employee_name.

    Resolution order:
      1. Employee whose employee_name matches display_name (normalized)
      2. Employee whose name equals mongo_username (when it is already a valid ID)
      3. mongo_username, else trimmed display_name (legacy / best-effort)
    """
    dn = normalize_employee_name_for_match(display_name)
    mongo = (mongo_username or "").strip() or None

    employees: List[Dict] = []
    try:
        employees = fetch_frappe_employees(limit=2000)
    except Exception:
        pass

    for emp in employees:
        if dn and normalize_employee_name_for_match(emp.get("employee_name") or "") == dn:
            code = emp.get("name")
            if code:
                return str(code)

    if mongo:
        for emp in employees:
            if emp.get("name") == mongo:
                return mongo

    if mongo:
        return mongo

    return (display_name or "").split("(")[0].strip()


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


def fetch_employee_shifts_by_period(employee_code: str) -> List[Dict]:
    """
    Fetch the custom_shifts_by_period child table from Employee doctype.
    
    Args:
        employee_code: Frappe Employee code/name
    
    Returns:
        List of shift period records with:
        - start_date: Start date of the period (YYYY-MM-DD format)
        - end_date: End date of the period (YYYY-MM-DD format)
        - shift_type: Shift Type name (Link to Shift Type doctype)
    """
    base_url, _, _ = _get_base_config()
    headers = _build_auth_headers()
    
    # Fetch employee - don't specify fields to ensure custom fields and child tables are included
    url = f"{base_url}/api/resource/Employee/{employee_code}"
    params = {}
    
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    
    if resp.status_code != 200:
        raise FrappeClientError(
            f"Frappe API error {resp.status_code}: {resp.text}"
        )
    
    data = resp.json()
    if not isinstance(data, dict) or "data" not in data:
        raise FrappeClientError(f"Unexpected response format from Frappe: {data}")
    
    doc = data["data"]
    shifts_by_period = doc.get("custom_shifts_by_period", [])
    
    # Handle both list format (child table) and None/empty
    if not shifts_by_period:
        return []
    
    if not isinstance(shifts_by_period, list):
        return []
    
    return shifts_by_period


def get_shift_type_for_date(employee_code: str, target_date: date) -> Optional[str]:
    """
    Determine which shift type applies for a specific date based on custom_shifts_by_period.
    
    Args:
        employee_code: Frappe Employee code/name
        target_date: The date to check
    
    Returns:
        Shift Type name if found, None otherwise (will fallback to default_shift)
    """
    try:
        shifts_by_period = fetch_employee_shifts_by_period(employee_code)
        
        if not shifts_by_period:
            return None
        
        # Find the shift period that contains the target_date
        target_date_str = target_date.strftime("%Y-%m-%d")
        
        for period in shifts_by_period:
            start_date_str = period.get("start_date")
            end_date_str = period.get("end_date")
            shift_type = period.get("shift_type")
            
            if not start_date_str or not end_date_str or not shift_type:
                continue
            
            try:
                # Parse dates - handle different formats
                try:
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                except:
                    try:
                        start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date()
                    except:
                        continue
                
                try:
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                except:
                    try:
                        end_date = datetime.strptime(end_date_str, "%d-%m-%Y").date()
                    except:
                        continue
                
                # Check if target_date falls within this period (inclusive)
                if start_date <= target_date <= end_date:
                    return shift_type
            except Exception:
                continue
        
        return None
    except Exception as e:
        print(f"Error getting shift type for date {target_date}: {e}")
        return None


def get_standard_work_hours_for_date(employee_code: str, target_date: date) -> Optional[str]:
    """
    Get standard work hours for a specific date, considering shift periods.
    
    Args:
        employee_code: Frappe Employee code/name
        target_date: The date to get standard work hours for
    
    Returns:
        Standard work hours in HH:MM format, or None if not found
    """
    base_url, _, _ = _get_base_config()
    headers = _build_auth_headers()
    
    # First, try to get shift type from custom_shifts_by_period
    shift_type = get_shift_type_for_date(employee_code, target_date)
    
    if shift_type:
        # Fetch Shift Type and get standard work hours
        try:
            shift_url = f"{base_url}/api/resource/Shift Type/{shift_type}"
            shift_resp = requests.get(shift_url, headers=headers, timeout=30)
            
            if shift_resp.status_code == 200:
                shift_data = shift_resp.json()
                if isinstance(shift_data, dict) and "data" in shift_data:
                    shift_doc = shift_data["data"]
                    std_hours_raw = shift_doc.get("custom_standard_work_hours")
                    
                    if std_hours_raw is not None:
                        try:
                            # Handle numeric values (int or float)
                            if isinstance(std_hours_raw, (int, float)):
                                return _float_hours_to_hhmm(float(std_hours_raw))
                            # Handle string values
                            elif isinstance(std_hours_raw, str) and std_hours_raw.strip():
                                try:
                                    float_val = float(std_hours_raw)
                                    return _float_hours_to_hhmm(float_val)
                                except ValueError:
                                    # Assume it's already in HH:MM format
                                    return std_hours_raw.strip()
                        except Exception:
                            pass
        except Exception as e:
            print(f"Error fetching shift type {shift_type}: {e}")
    
    # Fallback to default shift (existing logic)
    try:
        url = f"{base_url}/api/resource/Employee/{employee_code}"
        resp = requests.get(url, headers=headers, params={}, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "data" in data:
                doc = data["data"]
                default_shift = doc.get("default_shift")
                
                if default_shift:
                    shift_url = f"{base_url}/api/resource/Shift Type/{default_shift}"
                    shift_resp = requests.get(shift_url, headers=headers, timeout=30)
                    
                    if shift_resp.status_code == 200:
                        shift_data = shift_resp.json()
                        if isinstance(shift_data, dict) and "data" in shift_data:
                            shift_doc = shift_data["data"]
                            std_hours_raw = shift_doc.get("custom_standard_work_hours")
                            
                            if std_hours_raw is not None:
                                try:
                                    if isinstance(std_hours_raw, (int, float)):
                                        return _float_hours_to_hhmm(float(std_hours_raw))
                                    elif isinstance(std_hours_raw, str) and std_hours_raw.strip():
                                        try:
                                            float_val = float(std_hours_raw)
                                            return _float_hours_to_hhmm(float_val)
                                        except ValueError:
                                            return std_hours_raw.strip()
                                except Exception:
                                    pass
    except Exception as e:
        print(f"Error fetching default shift: {e}")
    
    return None


DEFAULT_HISTORICAL_BREAK_RULE_HHMM = "06:00"
DEFAULT_HISTORICAL_BREAK_DURATION_HHMM = "00:30"


def _historical_as_date(d) -> date:
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime):
        return d.date()
    return pd.Timestamp(d).date()


def _historical_shift_doc_to_params(shift_doc: dict) -> Dict[str, Any]:
    """Map Shift Type API doc to standard HH:MM, optional break HH:MMs, optional daily limit (hours)."""
    std = None
    std_raw = shift_doc.get("custom_standard_work_hours")
    if std_raw is not None:
        try:
            if isinstance(std_raw, (int, float)):
                std = _float_hours_to_hhmm(float(std_raw))
            elif isinstance(std_raw, str) and std_raw.strip():
                try:
                    std = _float_hours_to_hhmm(float(std_raw))
                except ValueError:
                    std = std_raw.strip()
        except Exception:
            pass

    def _nz_float_to_hhmm(raw) -> Optional[str]:
        if raw is None:
            return None
        try:
            if isinstance(raw, (int, float)):
                v = float(raw)
            elif isinstance(raw, str) and raw.strip():
                v = float(raw.strip())
            else:
                return None
            if v == 0:
                return None
            return _float_hours_to_hhmm(v)
        except (TypeError, ValueError):
            return None

    def _daily_limit(raw) -> Optional[float]:
        if raw is None:
            return None
        try:
            v = float(raw.strip()) if isinstance(raw, str) else float(raw)
            if v <= 0:
                return None
            return v
        except (TypeError, ValueError):
            return None

    return {
        "standard_hhmm": std,
        "break_rule_hhmm": _nz_float_to_hhmm(shift_doc.get("custom_break_rule")),
        "break_duration_hhmm": _nz_float_to_hhmm(shift_doc.get("custom_break_duration")),
        "daily_limit_hours": _daily_limit(shift_doc.get("custom_daily_limit")),
    }


def _historical_apply_daily_work_limit(work_time_str: object, limit_hours: Optional[float]) -> str:
    from utils import hhmm_to_decimal, decimal_hours_to_hhmmss

    if work_time_str is None:
        work_time_str = ""
    text = str(work_time_str).strip()
    if limit_hours is None or text == "":
        return text
    wt = hhmm_to_decimal(text)
    if wt <= limit_hours:
        return text
    return decimal_hours_to_hhmmss(limit_hours)


def _historical_resolve_shift_type_name(shifts_by_period: List[Dict], date_obj: date) -> Optional[str]:
    for period in shifts_by_period:
        start_date_str = period.get("start_date")
        end_date_str = period.get("end_date")
        period_shift_type = period.get("shift_type")
        if not start_date_str or not end_date_str or not period_shift_type:
            continue
        try:
            try:
                period_start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except Exception:
                period_start = datetime.strptime(start_date_str, "%d-%m-%Y").date()
            try:
                period_end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except Exception:
                period_end = datetime.strptime(end_date_str, "%d-%m-%Y").date()
            if period_start <= date_obj <= period_end:
                return period_shift_type
        except Exception:
            continue
    return None


def _historical_ensure_shift_cached(
    shift_type: str,
    shift_type_cache: Dict[str, Dict[str, Any]],
    base_url: str,
    headers: Dict[str, str],
) -> None:
    if shift_type in shift_type_cache:
        return
    placeholder = {
        "standard_hhmm": None,
        "break_rule_hhmm": None,
        "break_duration_hhmm": None,
        "daily_limit_hours": None,
    }
    shift_type_cache[shift_type] = dict(placeholder)
    try:
        shift_resp = requests.get(
            f"{base_url}/api/resource/Shift Type/{shift_type}",
            headers=headers,
            timeout=30,
        )
        if shift_resp.status_code != 200:
            return
        shift_data = shift_resp.json()
        if not isinstance(shift_data, dict) or "data" not in shift_data:
            return
        shift_type_cache[shift_type] = _historical_shift_doc_to_params(shift_data["data"])
    except Exception as e:
        print(f"Error fetching shift type {shift_type} for historical OT: {e}")


def fetch_employee_time_config(
    employee_code: str,
    report_start_date: Optional[date] = None,
    report_end_date: Optional[date] = None,
) -> Dict[str, Optional[str]]:
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

    Optional report_end_date: when set with report_start_date, holiday balance from
    custom_initial_holiday_hours includes every allocation year up to max(start year, end year),
    so cross-year PDF ranges include all relevant annual pots.
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
                    report_end_date=report_end_date,
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
            except FrappeClientError:
                raise
            except Exception as e:
                print(f"Error calculating holiday hours balance from table: {e}")
                calculated_initial_holiday_hours = "00:00"
        else:
            # No report_start_date, sum all allocations (still enforce non-overlapping windows)
            try:
                norm = _normalize_holiday_allocation_rows(holiday_hours_table)
                _validate_holiday_allocation_rows_no_overlap(norm)
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
            except FrappeClientError:
                raise
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
        "fields": '["name", "employee", "time", "log_type", "skip_auto_attendance", "custom_is_edited"]',
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
      - Track which IN/OUT times are edited (custom_is_edited = 1)
    """
    by_date: Dict[str, Dict[str, any]] = {}

    for row in checkins:
        time_str = row.get("time")
        log_type = row.get("log_type")
        custom_is_edited = row.get("custom_is_edited", 0)
        is_edited = bool(custom_is_edited == 1 or custom_is_edited is True)
        
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
            by_date[date_key] = {"in": None, "out": None, "in_edited": False, "out_edited": False}

        if log_type.upper() == "IN":
            current_in = by_date[date_key]["in"]
            if current_in is None or ts < current_in:
                by_date[date_key]["in"] = ts
                by_date[date_key]["in_edited"] = is_edited
        elif log_type.upper() == "OUT":
            current_out = by_date[date_key]["out"]
            if current_out is None or ts > current_out:
                by_date[date_key]["out"] = ts
                by_date[date_key]["out_edited"] = is_edited

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
                "IN_Edited": times.get("in_edited", False),
                "OUT_Edited": times.get("out_edited", False),
            }
        )

    return daily_rows


def calculate_historical_overtime_balance(
    employee_code: str,
    standard_work_hours_hhmm: str = "08:00",
    start_date: Optional[date] = None,
) -> str:
    """
    Cumulative overtime/undertime from Attendance + Checkins strictly BEFORE ``start_date``,
    using the same rules as the Frappe HR PDF: **Shifts by Period** (per-day Shift Type for
    standard hours, custom break rule/duration, daily limit), synthetic weekend/public-holiday
    rows for gaps in that window, and calendar multiplication (Sun / public hol ×2, not Sat).

    ``standard_work_hours_hhmm`` is only a fallback when a date has no matching shift period
    or Shift Type fetch fails (same role as default shift in the PDF UI).
    """
    from utils import (
        compute_work_duration,
        adjust_work_time_and_break,
        compute_time_difference,
        hhmm_to_decimal,
        decimal_hours_to_hhmmss,
        load_calendar_events,
    )

    if start_date is None:
        return "00:00"

    base_url, _, _ = _get_base_config()
    headers = _build_auth_headers()

    attendance_url = f"{base_url}/api/resource/Attendance"
    attendance_filters = [
        ["Attendance", "employee", "=", employee_code],
        ["Attendance", "attendance_date", "<", start_date.strftime("%Y-%m-%d")],
    ]

    attendance_params = {
        "fields": '["name", "employee", "attendance_date", "status", "leave_type"]',
        "filters": json.dumps(attendance_filters),
        "limit_page_length": 10000,
        "order_by": "attendance_date asc",
    }

    attendance_resp = requests.get(attendance_url, headers=headers, params=attendance_params, timeout=60)

    if attendance_resp.status_code != 200:
        raise FrappeClientError(
            f"Frappe API error {attendance_resp.status_code}: {attendance_resp.text}"
        )

    attendance_data = attendance_resp.json()
    if not isinstance(attendance_data, dict) or "data" not in attendance_data:
        raise FrappeClientError(f"Unexpected response format from Frappe: {attendance_data}")

    attendance_records = attendance_data["data"]

    if not attendance_records:
        return "00:00"

    checkin_url = f"{base_url}/api/resource/Employee Checkin"
    checkin_filters = [
        ["Employee Checkin", "employee", "=", employee_code],
        ["Employee Checkin", "time", "<", start_date.strftime("%Y-%m-%d 00:00:00")],
    ]

    checkin_params = {
        "fields": '["name", "employee", "time", "log_type", "skip_auto_attendance"]',
        "filters": json.dumps(checkin_filters),
        "limit_page_length": 50000,
        "order_by": "time asc",
    }

    checkin_resp = requests.get(checkin_url, headers=headers, params=checkin_params, timeout=60)

    all_checkins: List[Dict] = []
    if checkin_resp.status_code == 200:
        checkin_data = checkin_resp.json()
        if isinstance(checkin_data, dict) and "data" in checkin_data:
            all_checkins = checkin_data["data"]

    checkins_by_date: Dict[str, Dict[str, Optional[str]]] = {}
    if all_checkins:
        daily_checkins = build_daily_checkins_from_employee_checkins(all_checkins)
        for checkin_row in daily_checkins:
            date_key = (
                checkin_row["Date"].isoformat()
                if isinstance(checkin_row["Date"], date)
                else str(checkin_row["Date"])
            )
            checkins_by_date[date_key] = {
                "IN": checkin_row.get("IN"),
                "OUT": checkin_row.get("OUT"),
            }

    daily_rows = build_daily_rows_from_attendance_and_checkins(
        attendance_records=attendance_records,
        checkins_by_date=checkins_by_date,
    )

    if not daily_rows:
        return "00:00"

    calendar_events = load_calendar_events()
    calendar_events_date = {
        pd.to_datetime(date_str, format="%Y-%m-%d").date(): event
        for date_str, event in calendar_events.items()
    }

    existing_dates = {_historical_as_date(row["Date"]) for row in daily_rows if row.get("Date") is not None}
    range_start = min(existing_dates)
    range_end = start_date - timedelta(days=1)

    missing_weekends_holidays: List[Dict] = []
    cur = range_start
    while cur <= range_end:
        if cur not in existing_dates:
            is_weekend = cur.weekday() >= 5
            holiday_label_from_calendar = calendar_events_date.get(cur)
            is_in_calendar = holiday_label_from_calendar is not None
            is_public_holiday = False
            if is_in_calendar:
                if not is_weekend:
                    is_public_holiday = True
                else:
                    holiday_str = str(holiday_label_from_calendar).lower()
                    if "holiday" in holiday_str and holiday_str != "weekend":
                        is_public_holiday = True
            if is_weekend or is_public_holiday:
                if is_weekend and is_public_holiday:
                    holiday_label = holiday_label_from_calendar or "Weekend/Holiday"
                    leave_type = "Public Holiday"
                elif is_weekend:
                    holiday_label = "Weekend"
                    leave_type = None
                else:
                    holiday_label = holiday_label_from_calendar or "Holiday"
                    leave_type = "Public Holiday"
                missing_weekends_holidays.append(
                    {
                        "Day": cur.strftime("%a").upper(),
                        "Date": cur,
                        "IN": None,
                        "OUT": None,
                        "Status": "On Leave",
                        "Leave Type": leave_type,
                        "Holiday": holiday_label,
                    }
                )
        cur += timedelta(days=1)

    if missing_weekends_holidays:
        daily_rows.extend(missing_weekends_holidays)

    shifts_by_period: List[Dict] = []
    shift_type_cache: Dict[str, Dict[str, Any]] = {}
    try:
        shifts_by_period = fetch_employee_shifts_by_period(employee_code)
    except Exception as e:
        print(f"Warning: shifts_by_period unavailable for historical OT: {e}")

    def get_hist_shift_params(date_obj: date) -> Tuple[str, str, str, Optional[float]]:
        st_name = _historical_resolve_shift_type_name(shifts_by_period, date_obj)
        if st_name:
            _historical_ensure_shift_cached(st_name, shift_type_cache, base_url, headers)
            p = shift_type_cache.get(st_name) or {}
            std = p.get("standard_hhmm") or standard_work_hours_hhmm
            br = p.get("break_rule_hhmm") or DEFAULT_HISTORICAL_BREAK_RULE_HHMM
            bd = p.get("break_duration_hhmm") or DEFAULT_HISTORICAL_BREAK_DURATION_HHMM
            cap = p.get("daily_limit_hours")
            return std, br, bd, cap
        return (
            standard_work_hours_hhmm,
            DEFAULT_HISTORICAL_BREAK_RULE_HHMM,
            DEFAULT_HISTORICAL_BREAK_DURATION_HHMM,
            None,
        )

    df = pd.DataFrame(daily_rows)
    df["Date"] = pd.to_datetime(df["Date"])

    df["Holiday"] = df.apply(
        lambda row: row.get("Holiday")
        if pd.notnull(row.get("Holiday")) and str(row.get("Holiday")).strip() != ""
        else calendar_events_date.get(
            row["Date"].date() if hasattr(row["Date"], "date") else pd.to_datetime(row["Date"]).date()
        ),
        axis=1,
    )

    paid_holiday_mask = (
        (df["Status"] == "On Leave")
        & (df["Leave Type"] == "Paid Holiday")
        & (
            df["Holiday"].isna()
            | (df["Holiday"] == "")
            | (df["Holiday"].astype(str).str.strip() == "")
        )
    )
    df.loc[paid_holiday_mask, "Holiday"] = "Paid Holiday"

    sick_leave_mask = (df["Status"] == "On Leave") & (df["Leave Type"] == "Sick")
    df.loc[sick_leave_mask, "Holiday"] = "sick"
    df["Break"] = None

    df = df.sort_values("Date").reset_index(drop=True)

    df["Standard Time"] = df["Date"].apply(
        lambda ts: get_hist_shift_params(
            ts.date() if hasattr(ts, "date") else pd.to_datetime(ts).date()
        )[0]
    )

    df[" Daily Total"] = df.apply(
        lambda row: compute_work_duration(row.get("IN", ""), row.get("OUT", ""))
        if row.get("Status") in ["Present", "Half Day"]
        else "",
        axis=1,
    )

    def _work_time_break_row(row):
        if row.get("Status") not in ["Present", "Half Day"]:
            b = row.get("Break")
            return "", b if b is not None else ""
        ts = row["Date"]
        d_obj = ts.date() if hasattr(ts, "date") else pd.to_datetime(ts).date()
        _, br_rule, br_dur, cap = get_hist_shift_params(d_obj)
        wt, brk = adjust_work_time_and_break(
            row[" Daily Total"],
            row.get("Break"),
            br_rule,
            br_dur,
        )
        return _historical_apply_daily_work_limit(wt, cap), brk

    df["Work Time"], df["Break"] = zip(*df.apply(_work_time_break_row, axis=1))

    df["Difference (Decimal)"] = df.apply(
        lambda row: compute_time_difference(
            row.get("Work Time", ""),
            row.get("Standard Time", ""),
            row.get("Holiday", ""),
            False,
        ),
        axis=1,
    )

    df_dates = df["Date"].apply(
        lambda x: x.date() if hasattr(x, "date") else pd.to_datetime(x).date()
    )
    is_saturday = df_dates.apply(lambda d: d.weekday() == 5)
    is_sunday = df_dates.apply(lambda d: d.weekday() == 6)
    is_public_holiday_col = df_dates.apply(lambda d: d in calendar_events_date)
    df["Multiplication"] = 1.0
    df.loc[(is_sunday | is_public_holiday_col) & ~is_saturday, "Multiplication"] = 2.0
    df["Multiplication"] = df["Multiplication"].clip(lower=1.0, upper=2.0)

    valid_holiday_mask = df["Holiday"].apply(lambda v: pd.notnull(v) and str(v).strip() != "")
    holiday_dates = set(df.loc[valid_holiday_mask, "Date"].apply(lambda d: d.strftime("%Y-%m-%d")))

    running_overtime_balance = 0.0
    for _, row in df.iterrows():
        ts = row["Date"]
        date_obj = ts.date() if hasattr(ts, "date") else pd.to_datetime(ts).date()
        row_date = date_obj.strftime("%Y-%m-%d")

        work_time_str = row.get("Work Time", "")
        worked = (
            hhmm_to_decimal(work_time_str)
            if work_time_str and work_time_str not in ["00:00", "00:00:00"]
            else 0
        )
        standard_h = hhmm_to_decimal(str(row.get("Standard Time") or standard_work_hours_hhmm))
        multiplication = float(row.get("Multiplication", 1.0))

        is_holiday = (
            row_date in holiday_dates
            or row.get("Holiday") == "sick"
            or row.get("Holiday") == "Sick"
        )

        if is_holiday:
            if worked > 0:
                running_overtime_balance += worked * multiplication
        else:
            if worked < standard_h:
                running_overtime_balance -= standard_h - worked
            elif worked > standard_h:
                diff_decimal = row.get("Difference (Decimal)")
                if diff_decimal is not None and pd.notna(diff_decimal):
                    try:
                        running_overtime_balance += float(diff_decimal) * multiplication
                    except (ValueError, TypeError):
                        pass

    return decimal_hours_to_hhmmss(running_overtime_balance)


def _parse_holiday_table_date(val) -> Optional[date]:
    """Parse optional start_date / end_date from custom_initial_holiday_hours child rows."""
    if val is None or val == "":
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    s = str(val).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _merge_inclusive_date_intervals(
    intervals: List[Tuple[date, date]],
) -> List[Tuple[date, date]]:
    """Merge inclusive [start, end] date ranges (overlap or adjacent days)."""
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda x: (x[0], x[1]))
    merged: List[Tuple[date, date]] = [intervals[0]]
    for s, e in intervals[1:]:
        ps, pe = merged[-1]
        if s <= pe + timedelta(days=1):
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))
    return merged


def _gaps_in_inclusive_range(
    range_start: date,
    range_end: date,
    merged_blockers: List[Tuple[date, date]],
) -> List[Tuple[date, date]]:
    """
    Return maximal inclusive sub-ranges of [range_start, range_end] not covered by
    merged_blockers (each [bs, be] inclusive, already merged).
    """
    gaps: List[Tuple[date, date]] = []
    cur = range_start
    for bs, be in merged_blockers:
        if bs > range_end:
            break
        b0 = max(bs, range_start)
        b1 = min(be, range_end)
        if b0 > b1:
            continue
        if cur < b0:
            gaps.append((cur, b0 - timedelta(days=1)))
        cur = max(cur, b1 + timedelta(days=1))
        if cur > range_end:
            return gaps
    if cur <= range_end:
        gaps.append((cur, range_end))
    return gaps


def _explicit_holiday_intervals_from_table(
    holiday_hours_table: List[Dict],
) -> List[Tuple[date, date]]:
    """All inclusive windows from rows where both start and end are set (any row order)."""
    out: List[Tuple[date, date]] = []
    for record in holiday_hours_table:
        ws = _parse_holiday_table_date(record.get("start_date") or record.get("custom_start_date"))
        we = _parse_holiday_table_date(record.get("end_date") or record.get("custom_end_date"))
        if not ws or not we:
            continue
        if ws > we:
            ws, we = we, ws
        out.append((ws, we))
    return _merge_inclusive_date_intervals(out)


def _normalize_holiday_allocation_rows(
    holiday_hours_table: List[Dict],
) -> List[Dict[str, Any]]:
    """
    Build normalized allocation entries.

    - If both ``start_date`` and ``end_date`` are set, they define the window; ``canonical_year``
      is ``start_date.year``.
    - If only ``year`` is set (no dates), the default window is Jan 1–Dec 31 of that year, **minus**
      any dates covered by **other** rows that have explicit start/end (so a year-only row shares
      the year with dated rows without overlapping).
    """
    merged_explicit = _explicit_holiday_intervals_from_table(holiday_hours_table)
    rows: List[Dict[str, Any]] = []
    for record in holiday_hours_table:
        try:
            holiday_hours = record.get("holiday_hours")
            if holiday_hours is None:
                continue
            hours = float(holiday_hours)
        except (ValueError, TypeError):
            continue

        year_str = record.get("year")
        table_year: Optional[int] = None
        if year_str is not None and str(year_str).strip():
            try:
                table_year = int(year_str) if isinstance(year_str, str) else int(year_str)
            except (ValueError, TypeError):
                table_year = None

        ws = _parse_holiday_table_date(record.get("start_date") or record.get("custom_start_date"))
        we = _parse_holiday_table_date(record.get("end_date") or record.get("custom_end_date"))

        if ws and we:
            if ws > we:
                ws, we = we, ws
            eff_start, eff_end = ws, we
            canonical_year = ws.year
            rows.append(
                {
                    "hours": hours,
                    "eff_start": eff_start,
                    "eff_end": eff_end,
                    "canonical_year": canonical_year,
                }
            )
        elif table_year is not None:
            y0 = date(table_year, 1, 1)
            y1 = date(table_year, 12, 31)
            blockers_in_year: List[Tuple[date, date]] = []
            for bs, be in merged_explicit:
                s = max(bs, y0)
                e = min(be, y1)
                if s <= e:
                    blockers_in_year.append((s, e))
            blockers_in_year = _merge_inclusive_date_intervals(blockers_in_year)
            gaps = _gaps_in_inclusive_range(y0, y1, blockers_in_year)
            if not gaps:
                if hours > 0:
                    raise FrappeClientError(
                        f"Holiday allocation for calendar year {table_year} ({hours} h) has no "
                        "dates left: other `custom_initial_holiday_hours` rows with start_date and "
                        "end_date cover the entire year. Remove or narrow those date ranges, or "
                        "remove this year-only row."
                    )
                continue
            for eff_start, eff_end in gaps:
                rows.append(
                    {
                        "hours": hours,
                        "eff_start": eff_start,
                        "eff_end": eff_end,
                        "canonical_year": table_year,
                    }
                )
        else:
            continue

    return rows


def _validate_holiday_allocation_rows_no_overlap(norm_rows: List[Dict[str, Any]]) -> None:
    """Raise FrappeClientError if any two rows cover the same calendar day (inclusive windows)."""
    if len(norm_rows) < 2:
        return
    for i in range(len(norm_rows)):
        a = norm_rows[i]
        for j in range(i + 1, len(norm_rows)):
            b = norm_rows[j]
            if a["eff_start"] <= b["eff_end"] and b["eff_start"] <= a["eff_end"]:
                raise FrappeClientError(
                    "Overlapping holiday allocation rows in Employee "
                    "`custom_initial_holiday_hours`: "
                    f"row {i + 1} ({a['eff_start']} – {a['eff_end']}, {a['hours']} h) and "
                    f"row {j + 1} ({b['eff_start']} – {b['eff_end']}, {b['hours']} h) "
                    "share at least one day. Adjust start_date/end_date (or year-only ranges) "
                    "so windows do not overlap, then regenerate the report."
                )


def compute_holiday_balance_by_year_at_report_start(
    employee_code: str,
    holiday_hours_table: List[Dict],
    standard_work_hours_hhmm: str = "08:00",
    before_date: Optional[date] = None,
    report_end_date: Optional[date] = None,
) -> Tuple[Dict[int, float], Dict[int, float], List[Dict[str, Any]]]:
    """
    Per-year allocation and remaining holiday hours at report start (before before_date).

    Child rows may set optional ``start_date`` and ``end_date``. When both are set, they define
    the allocation window and override the calendar ``year`` for matching leave; leave on date D
    debits the first matching row in table order. If only ``year`` is used (dates blank), the
    window is that full calendar year **excluding** dates covered by rows that set both start and
    end dates (so a dated 0 h row can define April–December without overlapping a year-only row).

    Returns:
        (allocations_by_year_in_scope, balance_by_year_at_start, holiday_windows)
        ``holiday_windows`` is an ordered list of dicts with ``eff_start``, ``eff_end`` (dates),
        ``hours``, ``opening_balance`` (remaining hours for that window at report start) and
        ``canonical_year``. Used to reset the running holiday column when the active window changes (e.g. April 1 new row with
        0 h). Empty dicts / list if there are no usable rows.
    """
    from utils import hhmm_to_decimal

    norm_rows = _normalize_holiday_allocation_rows(holiday_hours_table)
    if not norm_rows:
        return {}, {}, []

    _validate_holiday_allocation_rows_no_overlap(norm_rows)

    if before_date and report_end_date:
        max_year = max(before_date.year, report_end_date.year)
    elif before_date:
        max_year = before_date.year
    elif report_end_date:
        max_year = report_end_date.year
    else:
        max_year = None

    def row_in_scope(r: Dict[str, Any]) -> bool:
        if max_year is None:
            return True
        return r["canonical_year"] <= max_year

    allocations_by_year: Dict[int, float] = defaultdict(float)
    for r in norm_rows:
        if not row_in_scope(r):
            continue
        allocations_by_year[r["canonical_year"]] += r["hours"]

    if not allocations_by_year:
        return {}, {}, []

    base_url, _, _ = _get_base_config()
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
    balance_by_year: Dict[int, float] = defaultdict(float)
    used_per_row: List[float] = [0.0] * len(norm_rows)

    if not attendance_records and before_date:
        for r in norm_rows:
            if not row_in_scope(r):
                continue
            balance_by_year[r["canonical_year"]] += r["hours"]
    else:
        standard_hours_decimal = hhmm_to_decimal(standard_work_hours_hhmm)

        for record in attendance_records:
            try:
                attendance_date_str = record.get("attendance_date")
                if not attendance_date_str:
                    continue

                try:
                    date_obj = datetime.strptime(attendance_date_str, "%Y-%m-%d").date()
                except Exception:
                    try:
                        date_obj = datetime.strptime(attendance_date_str, "%d-%m-%Y").date()
                    except Exception:
                        continue

                is_weekend = date_obj.weekday() >= 5
                leave_type = record.get("leave_type", "")
                leave_type_str = str(leave_type).strip() if leave_type else ""
                is_paid_holiday = leave_type_str == "Paid Holiday"
                is_sick = leave_type_str == "Sick"

                if is_paid_holiday and not is_sick and not is_weekend:
                    for i, r in enumerate(norm_rows):
                        if r["eff_start"] <= date_obj <= r["eff_end"]:
                            if r["hours"] > 0:
                                used_per_row[i] += standard_hours_decimal
                            break
            except Exception:
                continue

        for i, r in enumerate(norm_rows):
            if not row_in_scope(r):
                continue
            balance_by_year[r["canonical_year"]] += max(
                0.0, r["hours"] - used_per_row[i]
            )

    holiday_windows: List[Dict[str, Any]] = []
    for i, r in enumerate(norm_rows):
        if not row_in_scope(r):
            continue
        opening = max(0.0, r["hours"] - used_per_row[i])
        holiday_windows.append(
            {
                "eff_start": r["eff_start"],
                "eff_end": r["eff_end"],
                "hours": float(r["hours"]),
                "opening_balance": opening,
                "canonical_year": int(r["canonical_year"]),
            }
        )

    alloc_in_scope = {y: allocations_by_year[y] for y in balance_by_year if y in allocations_by_year}
    return alloc_in_scope, dict(balance_by_year), holiday_windows


def fetch_holiday_year_balances_for_report(
    employee_code: str,
    report_start_date: date,
    report_end_date: date,
    standard_work_hours_hhmm: str,
) -> Optional[Tuple[Dict[int, float], Dict[int, float], List[Dict[str, Any]]]]:
    """
    Load Employee holiday child table and return per-year allocation, balance at report start,
    and ordered ``holiday_windows`` for running-balance resets between date windows.
    Returns None if there is no custom_initial_holiday_hours table data.
    """
    base_url, _, _ = _get_base_config()
    headers = _build_auth_headers()
    emp_url = f"{base_url}/api/resource/Employee/{employee_code}"
    resp = requests.get(emp_url, headers=headers, params={}, timeout=30)
    if resp.status_code != 200:
        raise FrappeClientError(
            f"Frappe API error {resp.status_code}: {resp.text}"
        )
    payload = resp.json()
    if not isinstance(payload, dict) or "data" not in payload:
        raise FrappeClientError(f"Unexpected response format from Frappe: {payload}")
    table = payload["data"].get("custom_initial_holiday_hours")
    if not table or not isinstance(table, list) or len(table) == 0:
        return None
    return compute_holiday_balance_by_year_at_report_start(
        employee_code=employee_code,
        holiday_hours_table=table,
        standard_work_hours_hhmm=standard_work_hours_hhmm,
        before_date=report_start_date,
        report_end_date=report_end_date,
    )


def calculate_holiday_hours_balance_from_table(
    employee_code: str,
    holiday_hours_table: List[Dict],
    standard_work_hours_hhmm: str = "08:00",
    before_date: Optional[date] = None,
    report_end_date: Optional[date] = None,
) -> str:
    """
    Calculate holiday hours balance from the custom_initial_holiday_hours table.

    The table contains child records with:
    - year: when start_date/end_date are not both set, allocation applies to that calendar year
      minus any dates covered by other rows with explicit start_date and end_date
    - holiday_hours: float (allocated hours)
    - optional start_date, end_date: when both set, define the allocation window (override year
      for matching Paid Holiday leave); canonical bucket year is start_date.year

    Args:
        employee_code: Frappe Employee name/code
        holiday_hours_table: List of dicts from custom_initial_holiday_hours table
        standard_work_hours_hhmm: Standard work hours per day
        before_date: Calculate balance up to (but not including) this date
        report_end_date: If set with before_date, allocation years through
            max(before_date.year, report_end_date.year) are included in the total

    Returns:
        Total remaining holiday hours balance in HH:MM format
    """
    from utils import decimal_hours_to_hhmmss

    alloc_in_scope, balance_by_year, holiday_windows = (
        compute_holiday_balance_by_year_at_report_start(
            employee_code=employee_code,
            holiday_hours_table=holiday_hours_table,
            standard_work_hours_hhmm=standard_work_hours_hhmm,
            before_date=before_date,
            report_end_date=report_end_date,
        )
    )
    if not balance_by_year:
        return "00:00"
    from utils import holiday_opening_balance_combined_through_year

    if before_date:
        active_opening = None
        for w in holiday_windows:
            if w["eff_start"] <= before_date <= w["eff_end"]:
                active_opening = float(w["opening_balance"])
                break
        if active_opening is not None:
            return decimal_hours_to_hhmmss(active_opening)
        opening = holiday_opening_balance_combined_through_year(
            balance_by_year,
            alloc_in_scope,
            before_date.year,
        )
        return decimal_hours_to_hhmmss(opening)
    return decimal_hours_to_hhmmss(sum(balance_by_year.values()))


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


