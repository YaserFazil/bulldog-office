import pandas as pd

import json
import os
import numpy as np
from pymongo import ASCENDING, DESCENDING
from employee_manager import *
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

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
def compute_running_holiday_hours(df, holiday_dates, official_holidays, holiday_hours_count, initial_overtime="00:00"):
    # Ensure DataFrame is sorted by Date ascending.
    df_sorted = df.sort_values(by="Date").copy()
    
    # Initialize running_overtime based on initial_overtime
    if initial_overtime != "00:00":
        running_overtime = hhmm_to_decimal(initial_overtime)
    else:
        # For first row, use the Difference (Decimal) directly without additional processing
        first_row_diff = df_sorted["Difference (Decimal)"].iloc[0]
        running_overtime = float(first_row_diff) if first_row_diff not in ["", None] and pd.notna(first_row_diff) else 0
    
    overtime_list = []
    holiday_hours_list = []
    remaining_holiday_hours = holiday_hours_count if holiday_hours_count else 0  # Initialize holiday hours count
    remaining_holiday_hours_str = decimal_hours_to_hhmmss(remaining_holiday_hours)
    # Process each row in chronological order.
    for idx, row in df_sorted.iterrows():
        row_date = pd.to_datetime(row["Date"]).strftime("%Y-%m-%d")
        row_date_obj = pd.to_datetime(row["Date"]).date()
        
        # Skip overtime calculation for first row if initial_overtime is "00:00"
        if idx == 0 and initial_overtime == "00:00":
            running_overtime_str = decimal_hours_to_hhmmss(running_overtime)
        else:
            # Initialize overtime tracking from the first filled "Difference (Decimal)" if not set
            if running_overtime is None and row["Difference (Decimal)"] not in ["", None] and pd.notna(row["Difference (Decimal)"]):
                running_overtime = float(row["Difference (Decimal)"])
            
            if running_overtime is not None:
                running_overtime_str = decimal_hours_to_hhmmss(running_overtime)
            else:
                running_overtime_str = "00:00"
            
            # If this row is a holiday event date...
            if row_date in holiday_dates or row["Holiday"] == "sick" or row["Holiday"] == "Sick":
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
        
        # Decrease holiday hours count if the row's date is not in official_holidays and "Holiday" column is not empty
        if row_date_obj not in official_holidays and row["Holiday"] not in ["", "sick", "Sick", None] and is_valid_holiday(row["Holiday"]):
            # Convert standard work hours to decimal for holiday hours deduction
            standard_hours = hhmm_to_decimal(row["Standard Time"])
            remaining_holiday_hours = remaining_holiday_hours - standard_hours
            remaining_holiday_hours_str = decimal_hours_to_hhmmss(remaining_holiday_hours)
        
        holiday_hours_list.append(remaining_holiday_hours_str)
        overtime_list.append(running_overtime_str)
    
    df_sorted["Hours Overtime Left"] = overtime_list
    df_sorted["Holiday Hours"] = holiday_hours_list
    
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
    # Check if is_holiday is actually a holiday (non-empty string or non-null)
    has_holiday = is_holiday is not None and pd.notna(is_holiday) and str(is_holiday).strip() != ""
    
    # Check for empty or None values.
    if not work_time or not standard_time:
        if standard_time and not has_holiday:
            return "-" + standard_time if default else -hhmm_to_decimal(standard_time)
        elif standard_time and has_holiday:
            return "00:00" if default else hhmm_to_decimal("00:00")
        elif not standard_time and has_holiday:
            return work_time if default else hhmm_to_decimal(work_time)
        elif not work_time and has_holiday:
            return "00:00" if default else hhmm_to_decimal("00:00")
        else:
            return None
    if has_holiday and default is True:
        return work_time
    elif has_holiday and default is False:
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

def fetch_employee_work_history(employee_id, start_date=None, end_date=None, fill_missing_days=False):
    try:
        """Fetch work history for the selected employee within a date range, 
        also retrieves 'Hours Holiday' from the record before start_date if available."""
        query = {"employee_id": str(employee_id)}
        
        # Fetch the record before the start_date
        previous_hours_overtime = None
        previous_holiday_hours = None
        if start_date:
            prev_query = {"employee_id": str(employee_id), "Date": {"$lt": datetime.combine(start_date, datetime.min.time())}}
            prev_record = work_history_collection.find(prev_query).sort("Date", DESCENDING).limit(1)
            prev_record = list(prev_record)
            if prev_record and "Hours Overtime Left" in prev_record[0] and prev_record[0]["Hours Overtime Left"]:
                previous_hours_overtime = prev_record[0]["Hours Overtime Left"]
            elif not prev_record:
                previous_hours_overtime = "00:00"
                
            if prev_record and "Holiday Hours" in prev_record[0] and prev_record[0]["Holiday Hours"]:
                previous_holiday_hours = prev_record[0]["Holiday Hours"]
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
            
            # Fill missing days if requested and date range is specified
            if fill_missing_days and start_date and end_date:
                work_history = fill_missing_days_in_work_history(
                    work_history, 
                    start_date=start_date, 
                    end_date=end_date,
                    employee_id=employee_id
                )
            
            return work_history, previous_hours_overtime, previous_holiday_hours
        
        return pd.DataFrame(), previous_hours_overtime, previous_holiday_hours
    except Exception as e:
        st.error(f"Something went wrong while fetching work history: {e}")
        return None, None, None
    
def delete_employee_temp_work_history(employee_id):
    try:
        """Delete temp work history for the selected employee."""
        query = {"employee_id": str(employee_id)}
        result = temp_work_history_collection.delete_many(query)
        if result.deleted_count > 0:
            st.success(f"Deleted {result.deleted_count} records from temp work history.")
        else:
            st.warning("No records found to delete in temp work history.")
    except Exception as e:
        st.error(f"Something went wrong while deleting temp work history: {e}")


def fetch_employee_temp_work_history(employee_id):
    try:
        """Fetch temp work history for the selected employee, 
        also retrieves 'Hours Holiday' from the record before start_date if available."""
        query = {"employee_id": str(employee_id)}
        
        first_date = None
        last_date = None
        
        work_history = list(temp_work_history_collection.find(query).sort("Date", ASCENDING))
        
        if work_history:
            df = pd.DataFrame(work_history)
            df['Date'] = pd.to_datetime(df['Date']).dt.date
            df["IN"] = df["IN"].replace({np.nan: None}).astype("object").values
            df["OUT"] = df["OUT"].replace({np.nan: None}).astype("object").values

            # --- REORDER COLUMNS ---
            desired_order = ["Day", "Date", "IN", "OUT", "Work Time", " Daily Total", " Note", "Break", "Standard Time", "Difference (Decimal)", "Multiplication", "Hours Overtime Left", "Holiday", "Holiday Hours"]  # Existing columns
            for col in desired_order:
                if col == " Note":
                    df[col] = df["Note"]
                elif col == "Multiplication":
                    df[col] = 1.0
                elif col not in df.columns:
                    df[col] = None  # Fill in if missing from DB
            df = df[desired_order]

            return df, df['Date'].iloc[0], df['Date'].iloc[-1]

        return pd.DataFrame(), first_date, last_date

    except Exception as e:
        st.error(f"Something went wrong while fetching temp work history: {e}")
        return None, None, None


def send_email_with_attachment(email, pdf_buffer, file_name, mime_type):
    """Send an email with the PDF attachment."""
    try:
        # Create a multipart email message
        msg = MIMEMultipart()
        msg['From'] = "frfvipbl@gmail.com"
        msg['To'] = email
        msg['Subject'] = "Your Work History PDF"
        msg.attach(MIMEText("Please find attached your work history PDF.", 'plain'))
        # Attach the PDF file
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(pdf_buffer.getvalue())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={file_name}')
        msg.attach(part)
        # Send the email
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            # server.starttls()
            server.login("frfvipbl@gmail.com", "vwks blct zpbr qqbm")
            server.sendmail("frfvipbl@gmail.com", email, msg.as_string())
        st.success("Email sent successfully.")
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        raise e


def send_the_pdf_created_in_history_page_to_email(employee_id, pdf_buffer, file_name, mime_type):
    try:
        """Send the PDF created in the history page to the employee's email."""
        # Fetch employee email from the database
        query = {"_id": ObjectId(employee_id)}
        employee = employees_collection.find_one(query)
        
        if employee and "email" in employee:
            email = employee["email"]
            if email:
                # Send the email with the PDF attachment
                send_email_with_attachment(email, pdf_buffer, file_name, mime_type)
            else:
                st.warning("employee email not found.")
        else:
            st.warning("employee not found.")
    except Exception as e:
        st.error(f"Something went wrong while sending the PDF: {e}")


def fill_missing_days_in_work_history(work_history_df, start_date=None, end_date=None, employee_id=None):
    """
    Fill missing days in work history with placeholder entries.
    This allows users to add absence types (vacation, sick leave, etc.) for days without work records.
    
    Args:
        work_history_df: DataFrame with existing work history
        start_date: Start date for the range (if None, uses first work record)
        end_date: End date for the range (if None, uses today or last work record)
        employee_id: Employee ID for the records
    
    Returns:
        DataFrame with filled missing days
    """
    try:
        from datetime import date, timedelta
        import calendar
        
        if work_history_df.empty:
            st.warning("No work history data available to fill missing days.")
            return work_history_df
        
        # Determine date range
        if start_date is None:
            if not work_history_df.empty and 'Date' in work_history_df.columns:
                start_date = work_history_df['Date'].min()
            else:
                st.error("Cannot determine start date. Please load work history first.")
                return work_history_df
        
        if end_date is None:
            if not work_history_df.empty and 'Date' in work_history_df.columns:
                end_date = max(work_history_df['Date'].max(), date.today())
            else:
                end_date = date.today()
        
        # Ensure dates are date objects
        if isinstance(start_date, str):
            start_date = pd.to_datetime(start_date).date()
        if isinstance(end_date, str):
            end_date = pd.to_datetime(end_date).date()
        
        # Create complete date range
        date_range = []
        current_date = start_date
        while current_date <= end_date:
            date_range.append(current_date)
            current_date += timedelta(days=1)
        
        # Create a complete DataFrame with all dates
        complete_df = pd.DataFrame({'Date': date_range})
        
        # Add day of week (abbreviated format: MON, TUE, WED, etc.)
        complete_df['Day'] = complete_df['Date'].apply(lambda x: calendar.day_abbr[x.weekday()].upper())
        
        # Merge with existing work history
        if not work_history_df.empty:
            # Ensure Date column is datetime for merging
            work_history_df_copy = work_history_df.copy()
            work_history_df_copy['Date'] = pd.to_datetime(work_history_df_copy['Date'])
            complete_df['Date'] = pd.to_datetime(complete_df['Date'])
            
            # Remove the Day column from work_history_df_copy to avoid conflicts
            # We'll use the Day column from complete_df which has all days
            if 'Day' in work_history_df_copy.columns:
                work_history_df_copy = work_history_df_copy.drop('Day', axis=1)
            
            # Merge existing data with complete date range
            merged_df = pd.merge(complete_df, work_history_df_copy, on='Date', how='left')
            
            # For any missing columns from the original data, add them with default values
            for col in work_history_df_copy.columns:
                if col not in merged_df.columns and col != 'Date':
                    merged_df[col] = None
        else:
            merged_df = complete_df
        
        # Ensure Day column is properly filled for all rows
        if 'Day' in merged_df.columns:
            # Recalculate day names for all dates to ensure they're correct (abbreviated format)
            merged_df['Day'] = merged_df['Date'].apply(lambda x: calendar.day_abbr[x.weekday()].upper())
        else:
            st.error("Day column is missing from merged data")
        
        # Fill missing values for required columns
        if employee_id:
            merged_df['employee_id'] = employee_id
        
        # Ensure all required columns exist
        required_columns = ['IN', 'OUT', 'Work Time', ' Daily Total', ' Note', 'Break', 
                           'Standard Time', 'Difference', 'Difference (Decimal)', 
                           'Multiplication', 'Holiday', 'Holiday Hours', 'Hours Overtime Left']
        
        for col in required_columns:
            if col not in merged_df.columns:
                merged_df[col] = None
        
        # Add a marker to distinguish between existing DB records and new placeholder records
        merged_df['is_new_record'] = merged_df['_id'].isna()
        
        # Apply calendar events (holidays/weekends) to the Holiday column
        try:
            calendar_events = load_calendar_events()
            if calendar_events:
                # Convert the keys from string to date objects
                calendar_events_date = {
                    pd.to_datetime(date_str, format="%Y-%m-%d").date(): event 
                    for date_str, event in calendar_events.items()
                }
                
                # Apply calendar events to all dates, but only for new records or if Holiday is empty
                for idx, row in merged_df.iterrows():
                    date_val = row['Date']
                    if isinstance(date_val, str):
                        date_val = pd.to_datetime(date_val).date()
                    
                    # Apply calendar event if:
                    # 1. It's a new record, OR
                    # 2. The Holiday field is empty/null for existing records
                    is_new = row.get('is_new_record', False)
                    holiday_empty = pd.isna(row.get('Holiday')) or str(row.get('Holiday', '')).strip() == ''
                    
                    if date_val in calendar_events_date and (is_new or holiday_empty):
                        merged_df.at[idx, 'Holiday'] = calendar_events_date[date_val]
        except Exception as e:
            st.warning(f"Could not load calendar events: {e}")
        
        # Set default values for missing entries - use the same approach as the original code
        merged_df['IN'] = merged_df['IN'].replace({np.nan: None}).astype("object").values
        merged_df['OUT'] = merged_df['OUT'].replace({np.nan: None}).astype("object").values
        merged_df['Work Time'] = merged_df['Work Time'].fillna('00:00')
        merged_df[' Daily Total'] = merged_df[' Daily Total'].fillna('00:00')
        merged_df[' Note'] = merged_df[' Note'].fillna('')
        merged_df['Break'] = merged_df['Break'].fillna('00:00')
        merged_df['Standard Time'] = merged_df['Standard Time'].fillna('08:00')
        merged_df['Difference'] = merged_df['Difference'].fillna('00:00')
        merged_df['Difference (Decimal)'] = merged_df['Difference (Decimal)'].fillna(0.0)
        merged_df['Multiplication'] = merged_df['Multiplication'].fillna(1.0)
        merged_df['Holiday'] = merged_df['Holiday'].fillna('')
        merged_df['Holiday Hours'] = merged_df['Holiday Hours'].fillna('')
        merged_df['Hours Overtime Left'] = merged_df['Hours Overtime Left'].fillna('')
        
        # Calculate Difference and Difference (Decimal) for all records (especially new ones)
        for idx, row in merged_df.iterrows():
            work_time = str(row['Work Time']) if pd.notna(row['Work Time']) else '00:00'
            standard_time = str(row['Standard Time']) if pd.notna(row['Standard Time']) else '08:00'
            holiday = row.get('Holiday', '')
            
            # Calculate time difference using the existing function
            try:
                diff_str = compute_time_difference(work_time, standard_time, holiday, default=True)
                diff_decimal = compute_time_difference(work_time, standard_time, holiday, default=False)
                
                if diff_str is not None:
                    merged_df.at[idx, 'Difference'] = diff_str
                if diff_decimal is not None:
                    merged_df.at[idx, 'Difference (Decimal)'] = diff_decimal
            except Exception as e:
                # If calculation fails, use defaults
                merged_df.at[idx, 'Difference'] = '00:00'
                merged_df.at[idx, 'Difference (Decimal)'] = 0.0
        
        # Convert Date back to date type
        merged_df['Date'] = pd.to_datetime(merged_df['Date']).dt.date
        
        # Sort by date
        merged_df = merged_df.sort_values('Date').reset_index(drop=True)
        
        return merged_df
        
    except Exception as e:
        st.error(f"Error filling missing days: {str(e)}")
        print(f"Error filling missing days: {str(e)}")

        import traceback
        st.error(f"Full error: {traceback.format_exc()}")
        print(f"Full error: {traceback.format_exc()}")
        return work_history_df

def calculate_absence_hours(absence_type, standard_hours="08:00"):
    """
    Calculate hours for different absence types.
    
    Args:
        absence_type: Type of absence (vacation, sick, personal, etc.)
        standard_hours: Standard work hours per day
    
    Returns:
        Tuple of (work_time, note) for the absence
    """
    absence_mappings = {
        'vacation': (standard_hours, 'Vacation'),
        'sick': (standard_hours, 'Sick Leave'),
        'personal': (standard_hours, 'Personal Leave'),
        'unpaid': ('00:00', 'Unpaid Leave'),
        'holiday': (standard_hours, 'Holiday'),
        'weekend': ('00:00', 'Weekend'),
        'other': (standard_hours, 'Other Leave')
    }
    
    return absence_mappings.get(absence_type.lower(), (standard_hours, 'Leave'))

