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
    hours = int(decimal_hours)
    mins = int(round((decimal_hours - hours) * 60))
    return f"{hours:02d}:{mins:02d}"

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
    parts = time_str.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) + int(minutes)/60 + int(seconds)/3600
    elif len(parts) == 2:
        hours, minutes = parts
        return int(hours) + int(minutes)/60
    else:
        return 0

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

# ----------------------
# 7. New Helper: Compute a running holiday balance row-by-row
# ----------------------
def compute_running_holiday_hours(df, initial_holiday, holiday_dates):
    # Ensure DataFrame is sorted by Date ascending.
    df_sorted = df.sort_values(by="Date").copy()
    running_balance = initial_holiday
    balance_list = []
    # Process each row in chronological order.
    for idx, row in df_sorted.iterrows():
        row_date = pd.to_datetime(row["Date"]).strftime("%Y-%m-%d")
        running_balance_str = decimal_hours_to_hhmmss(running_balance)
        # If this row is a holiday event date...
        if row_date in holiday_dates:
            work_str = row["Work Time"]
            # Convert work time to decimal hours.
            worked = hhmm_to_decimal(work_str) if work_str and work_str not in ["00:00", "00:00:00"] else 0
            # Reward only if employee worked.
            if worked > 0:
                running_balance = max(0, running_balance + worked)
                running_balance_str = decimal_hours_to_hhmmss(running_balance)
        else:
            work_str = row["Work Time"]
            # Convert work time to decimal hours.
            worked = hhmm_to_decimal(work_str) if work_str and work_str not in ["00:00", "00:00:00"] else 0
            # Deduct if employee not worked enough
            standard_work_hours = hhmm_to_decimal(row["Standard Time"])
            if worked < standard_work_hours:
                not_worked_hours = standard_work_hours - worked
                running_balance = max(0, running_balance - not_worked_hours)
                running_balance_str = decimal_hours_to_hhmmss(running_balance)

        balance_list.append(running_balance_str)
    df_sorted["Hours Holiday"] = balance_list
    return df_sorted

# ----------------------
# 8. Compute the difference between work_time and standard_time,
# both provided as strings in "hh:mm" format.
# Returns a string in "hh:mm" format, with a "-" sign if negative.
# If either input is missing or invalid, returns an empty string.
# ----------------------
def compute_time_difference(work_time, standard_time):
    """
    Compute the difference between work_time and standard_time,
    both provided as strings in "hh:mm" format.
    Returns a string in "hh:mm" format, with a "-" sign if negative.
    If either input is missing or invalid, returns an empty string.
    """
    # Check for empty or None values.
    if not work_time or not standard_time:
        return None
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
    return f"{sign}{diff_hours:02d}:{diff_minutes:02d}"

def fetch_employee_work_history(user_id, start_date=None, end_date=None):
    """Fetch work history for the selected user within a date range, 
    also retrieves 'Hours Holiday' from the record before start_date if available."""
    query = {"employee_id": str(user_id)}
    
    # Fetch the record before the start_date
    previous_hours_holiday = None
    if start_date:
        prev_query = {"employee_id": str(user_id), "Date": {"$lt": datetime.combine(start_date, datetime.min.time())}}
        prev_record = work_history_collection.find(prev_query).sort("Date", DESCENDING).limit(1)
        prev_record = list(prev_record)
        if prev_record and "Hours Holiday" in prev_record[0] and prev_record[0]["Hours Holiday"]:
            previous_hours_holiday = prev_record[0]["Hours Holiday"]
    
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
        return work_history, previous_hours_holiday
    
    return pd.DataFrame(), previous_hours_holiday

def fetch_employee_work_history_old(user_id, start_date=None, end_date=None):
    """Fetch work history for the selected user within a date range."""
    query = {"employee_id": str(user_id)}
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
        return work_history
    return pd.DataFrame()