import pandas as pd

import json
import os
import numpy as np
from pymongo import ASCENDING, DESCENDING
from employee_manager import *


# ----------------------
# 1. Helper: decimal hours to HH:MM:SS
# ----------------------
def decimal_hours_to_hhmmss(decimal_hours):
    negative = decimal_hours < 0
    decimal_hours = abs(decimal_hours)

    hours = int(decimal_hours)
    mins = int(round((decimal_hours - hours) * 60))

    if mins == 60:  # Handle rounding up to next hour
        mins = 0
        hours += 1

    formatted_time = f"{hours:02d}:{mins:02d}"
    return f"-{formatted_time}" if negative else formatted_time

# ----------------------
# 2. Compute work duration from check-in and check-out strings
# ----------------------
def compute_work_duration(check_in, check_out):
    in_time_str = str(check_in).strip()
    out_time_str = str(check_out).strip()
    if in_time_str and out_time_str:
        try:
            t_in = pd.to_datetime(in_time_str, format="%H:%M")
            t_out = pd.to_datetime(out_time_str, format="%H:%M")
            delta = t_out - t_in
            if delta.total_seconds() < 0:
                delta += pd.Timedelta(days=1)
            total_seconds = int(delta.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours:02d}:{minutes:02d}"
        except Exception as e:
            return None
    return None

# ----------------------
# 3. Helper function to adjust work time and break values
# ----------------------
def adjust_work_time_and_break(daily_total_str, break_str, break_hour_rule, break_hours):
    if not daily_total_str:
        return None, break_str
    daily_total_td = pd.to_timedelta(daily_total_str + ":00")
    break_hour_rule_td = pd.to_timedelta(break_hour_rule + ":00")
    break_hours_td = pd.to_timedelta(break_hours + ":00")
    # if break_str and break_str != "00:00":
    if break_str and break_str not in ["00:00", "0:00", "0", "00", "0000", "00:00:00", "0:00:00"]:
        break_hours_td = pd.to_timedelta(break_str + ":00")

    # try:
    #     current_break_td = pd.to_timedelta(break_str)
    # except Exception:
    #     current_break_td = pd.Timedelta(0)
    current_break_td = pd.Timedelta(0)
    if daily_total_td >= pd.Timedelta(value=break_hour_rule_td):
        new_work_time_td = daily_total_td - pd.Timedelta(break_hours_td)
        new_break_td = current_break_td + pd.Timedelta(break_hours_td)
    else:
        new_work_time_td = daily_total_td
        new_break_td = current_break_td
    new_work_time_str = f"{int(new_work_time_td.total_seconds()//3600):02d}:{int((new_work_time_td.total_seconds()%3600)//60):02d}"
    new_break_str = f"{int(new_break_td.total_seconds()//3600):02d}:{int((new_break_td.total_seconds()%3600)//60):02d}"
    return new_work_time_str, new_break_str

# ----------------------
# 4. Helper: Convert a time string (HH:MM or HH:MM:SS) to decimal hours
# ----------------------
def hhmm_to_decimal(time_str):
    if not time_str:
        return 0

    negative = time_str.startswith("-")  # Check for a negative sign
    time_str = time_str.lstrip("-")  # Remove the negative sign for processing

    parts = time_str.split(":")
    
    if len(parts) == 3:
        hours, minutes, seconds = map(int, parts)
        decimal = hours + minutes / 60 + seconds / 3600
    elif len(parts) == 2:
        hours, minutes = map(int, parts)
        decimal = hours + minutes / 60
    else:
        return 0

    return -decimal if negative else decimal

# ----------------------
# 5. Helper: Convert a dict (from st.data_editor) safely to a DataFrame
# ----------------------
def safe_convert_to_df(data):
    if isinstance(data, pd.DataFrame):
        return data.copy()
    if isinstance(data, dict):
        new_data = {}
        for k, v in data.items():
            if isinstance(v, pd.Series):
                new_data[k] = v.tolist()
            elif not isinstance(v, list):
                new_data[k] = [v]
            else:
                new_data[k] = v
        return pd.DataFrame(new_data)
    return pd.DataFrame(data)

# ----------------------
# 6. Helper: Load calendar events (holiday dates) from JSON file
# ----------------------
def load_calendar_events():
    filename = "calendar_events.json"
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {}

# Helper function to ensure the passed column has a valid, non-empty value.
def is_valid_holiday(value):
    return pd.notnull(value) and str(value).strip() != ''

# ----------------------
# 7. New Helper: Compute a running holiday balance row-by-row
# ----------------------
def compute_running_holiday_hours(df, holiday_dates, official_holidays, holiday_days_count, initial_overtime="00:00"):
    # Ensure DataFrame is sorted by Date ascending.
    df_sorted = df.sort_values(by="Date").copy()
    running_overtime = hhmm_to_decimal(initial_overtime) if initial_overtime != "00:00" else df_sorted["Difference (Decimal)"].iloc[0]
    overtime_list = []
    holiday_days = []
    remaining_holiday_days = holiday_days_count if holiday_days_count else 0  # Initialize holiday days count
    
    # Process each row in chronological order.
    for idx, row in df_sorted.iterrows():
        row_date = pd.to_datetime(row["Date"]).strftime("%Y-%m-%d")
        row_date_obj = pd.to_datetime(row["Date"]).date()
        
        # Initialize overtime tracking from the first filled "Difference (Decimal)" if not set
        if running_overtime is None and row["Difference (Decimal)"] not in ["", None] and pd.notna(row["Difference (Decimal)"]):
            running_overtime = float(row["Difference (Decimal)"])
        
        if running_overtime is not None:
            running_overtime_str = decimal_hours_to_hhmmss(running_overtime)
        else:
            running_overtime_str = "00:00"
        
        # If this row is a holiday event date...
        if row_date in holiday_dates:
            work_str = row["Work Time"]
            worked = hhmm_to_decimal(work_str) if work_str and work_str not in ["00:00", "00:00:00"] else 0
            
            # Reward only if employee worked.
            if worked > 0:
                multiplication = float(row["Multiplication"])
                worked = worked * multiplication
                # Sum extra hours to overtime balance
                if running_overtime is not None and idx > 0 or initial_overtime != "00:00":
                    running_overtime = running_overtime + worked
                    running_overtime_str = decimal_hours_to_hhmmss(running_overtime)
        else:
            work_str = row["Work Time"]
            worked = hhmm_to_decimal(work_str) if work_str and work_str not in ["00:00", "00:00:00"] else 0
            standard_work_hours = hhmm_to_decimal(row["Standard Time"])
            
            if worked < standard_work_hours:
                not_worked_hours = standard_work_hours - worked
                #  Unsum not worked hours from overtime balance
                if running_overtime is not None:
                    running_overtime = running_overtime - not_worked_hours
                    running_overtime_str = decimal_hours_to_hhmmss(running_overtime)
            elif worked > standard_work_hours:
                extra_hours = float(row["Difference (Decimal)"]) * float(row["Multiplication"])
                
                # Sum extra hours to overtime balance
                if running_overtime is not None:
                    running_overtime = running_overtime + extra_hours
                    running_overtime_str = decimal_hours_to_hhmmss(running_overtime)
        
        # Decrease holiday days count if the row's date is not in official_holidays and "Holiday" column is not empty
        if row_date_obj not in official_holidays and row["Holiday"] not in ["", None] and is_valid_holiday(row["Holiday"]):
            remaining_holiday_days = max(0, remaining_holiday_days - 1)
        
        holiday_days.append(remaining_holiday_days)
        overtime_list.append(running_overtime_str)
    
    df_sorted["Hours Overtime Left"] = overtime_list
    df_sorted["Holiday Days"] = holiday_days
    
    return df_sorted


# ----------------------
# 8. Compute the difference between work_time and standard_time,
# both provided as strings in "hh:mm" format.
# Returns a string in "hh:mm" format, with a "-" sign if negative.
# If either input is missing or invalid, returns an empty string.
# ----------------------
def compute_time_difference(work_time, standard_time, is_holiday=None, default=True):
    """
    Compute the difference between work_time and standard_time,
    both provided as strings in "hh:mm" format.
    Returns a string in "hh:mm" format, with a "-" sign if negative.
    If either input is missing or invalid, returns an empty string.
    """
    # Check for empty or None values.
    if not work_time or not standard_time:
        if standard_time and not pd.notna(is_holiday):
            return "-" + standard_time if default else -hhmm_to_decimal(standard_time)
        elif standard_time and pd.notna(is_holiday):
            return "00:00" if default else hhmm_to_decimal("00:00")
        elif not standard_time and pd.notna(is_holiday):
            return work_time if default else hhmm_to_decimal(work_time)
        elif not work_time and pd.notna(is_holiday):
            return "00:00" if default else hhmm_to_decimal("00:00")
        else:
            return None
    if pd.notna(is_holiday) and default is True:
        return work_time
    elif pd.notna(is_holiday) and default is False:
        return hhmm_to_decimal(work_time)
    try:
        work_hours, work_minutes = map(int, work_time.split(':'))
        std_hours, std_minutes = map(int, standard_time.split(':'))
    except Exception:
        return None
    
    # Convert both times to total minutes.
    work_total = work_hours * 60 + work_minutes
    std_total = std_hours * 60 + std_minutes
    
    # Calculate the difference.
    diff = work_total - std_total
    sign = "-" if diff < 0 else ""
    diff = abs(diff)
    
    # Convert minutes back to hours and minutes.
    diff_hours = diff // 60
    diff_minutes = diff % 60
    if default:
        return f"{sign}{diff_hours:02d}:{diff_minutes:02d}"
    else:
        return diff / 60 if not sign else -diff / 60

def fetch_employee_work_history(user_id, start_date=None, end_date=None):
    try:
        """Fetch work history for the selected user within a date range, 
        also retrieves 'Hours Holiday' from the record before start_date if available."""
        query = {"employee_id": str(user_id)}
        
        # Fetch the record before the start_date
        previous_hours_overtime = None
        previous_holiday_days = None
        if start_date:
            prev_query = {"employee_id": str(user_id), "Date": {"$lt": datetime.combine(start_date, datetime.min.time())}}
            prev_record = work_history_collection.find(prev_query).sort("Date", DESCENDING).limit(1)
            prev_record = list(prev_record)
            if prev_record and "Hours Overtime Left" in prev_record[0] and prev_record[0]["Hours Overtime Left"]:
                previous_hours_overtime = prev_record[0]["Hours Overtime Left"]
            elif not prev_record:
                previous_hours_overtime = "00:00"
                
            if prev_record and "Holiday Days" in prev_record[0] and prev_record[0]["Holiday Days"]:
                previous_holiday_days = prev_record[0]["Holiday Days"]
        # Add date filtering if start_date and end_date are provided
        if start_date and end_date:
            query["Date"] = {"$gte": datetime.combine(start_date, datetime.min.time()), 
                            "$lte": datetime.combine(end_date, datetime.max.time())}
        
        work_history = list(work_history_collection.find(query).sort("Date", ASCENDING))
        
        if work_history:
            work_history = pd.DataFrame(work_history) 
            work_history['Date'] = pd.to_datetime(work_history['Date']).dt.date
            work_history["IN"] = work_history["IN"].replace({np.nan: None}).astype("object").values
            work_history["OUT"] = work_history["OUT"].replace({np.nan: None}).astype("object").values
            return work_history, previous_hours_overtime, previous_holiday_days
        
        return pd.DataFrame(), previous_hours_overtime, previous_holiday_days
    except Exception as e:
        st.error(f"Something went wrong while fetching work history: {e}")
        return None, None, None
    
def delete_employee_temp_work_history(user_id):
    try:
        """Delete temp work history for the selected user."""
        query = {"employee_id": str(user_id)}
        result = temp_work_history_collection.delete_many(query)
        if result.deleted_count > 0:
            st.success(f"Deleted {result.deleted_count} records from temp work history.")
        else:
            st.warning("No records found to delete in temp work history.")
    except Exception as e:
        st.error(f"Something went wrong while deleting temp work history: {e}")


def fetch_employee_temp_work_history(user_id):
    try:
        """Fetch temp work history for the selected user, 
        also retrieves 'Hours Holiday' from the record before start_date if available."""
        query = {"employee_id": str(user_id)}
        
        first_date = None
        last_date = None
        
        work_history = list(temp_work_history_collection.find(query).sort("Date", ASCENDING))
        
        if work_history:
            df = pd.DataFrame(work_history)
            df['Date'] = pd.to_datetime(df['Date']).dt.date
            df["IN"] = df["IN"].replace({np.nan: None}).astype("object").values
            df["OUT"] = df["OUT"].replace({np.nan: None}).astype("object").values

            # --- REORDER COLUMNS ---
            desired_order = ["Day", "Date", "IN", "OUT", " Note"]  # Existing columns
            for col in desired_order:
                if col == " Note":
                    df[col] = df["Note"]
                elif col not in df.columns:
                    df[col] = None  # Fill in if missing from DB
            
            # --- ADD EXTRA EMPTY COLUMNS ---
            additional_columns = ["Work Time", " Daily Total", "Break", "Standard Time", "Difference (Decimal)", "Multiplication", "Hours Overtime Left", "Holiday", "Holiday Days"]
            for col in additional_columns:
                df[col] = None  # Add empty columns
                if col == "Multiplication":
                    df[col] = 1.0

            # Final column order: existing desired + additional
            final_columns = desired_order + additional_columns
            df = df[final_columns]

            return df, df['Date'].iloc[0], df['Date'].iloc[-1]

        return pd.DataFrame(), first_date, last_date

    except Exception as e:
        st.error(f"Something went wrong while fetching temp work history: {e}")
        return None, None, None
