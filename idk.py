import pandas as pd
import streamlit as st
from fpdf import FPDF
import datetime

# --------------------
# Helper Functions for Time/Duration Parsing & Formatting
# --------------------

def parse_time_str(time_str):
    """Parse a time string (e.g. '9:00:00 AM' or '09:00:00') and return a time object."""
    time_str = time_str.strip()
    for fmt in ("%I:%M:%S %p", "%H:%M:%S"):
        try:
            dt = datetime.datetime.strptime(time_str, fmt)
            return dt.time()
        except ValueError:
            continue
    return None

def format_time_value(value):
    """Format a check-in/out time value to HH:MM. Returns '-' if missing."""
    if pd.isnull(value):
        return "-"
    if isinstance(value, (pd.Timestamp, datetime.datetime)):
        return value.strftime("%H:%M")
    t = parse_time_str(value)
    return t.strftime("%H:%M") if t else str(value)

def parse_duration_str(time_str):
    """Parse a duration string (ignoring AM/PM) into a timedelta."""
    time_str = time_str.strip()
    # Remove any AM/PM markers (durations don’t use them)
    for suffix in (" AM", " PM"):
        if time_str.endswith(suffix):
            time_str = time_str.replace(suffix, "")
            break
    try:
        dt = datetime.datetime.strptime(time_str, "%H:%M:%S")
        return datetime.timedelta(hours=dt.hour, minutes=dt.minute, seconds=dt.second)
    except ValueError:
        try:
            return pd.to_timedelta(time_str)
        except Exception:
            return datetime.timedelta(0)

def format_duration(td):
    """Format a timedelta as H:MM. If the timedelta comes from Excel (with a huge day offset), subtract it."""
    if pd.isnull(td):
        return "-"
    if not isinstance(td, datetime.timedelta):
        try:
            td = pd.to_timedelta(td)
        except Exception:
            return str(td)
    # Remove Excel epoch offset if detected (e.g. 25569 days)
    if td.days >= 25569:
        td = td - datetime.timedelta(days=25569)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours}:{minutes:02d}"

def get_duration(value):
    """Return a timedelta from a value (string, pd.Timedelta, or Timestamp)."""
    if pd.isnull(value):
        return datetime.timedelta(0)
    if isinstance(value, datetime.timedelta):
        return value
    if isinstance(value, pd.Timedelta):
        return value.to_pytimedelta()
    if isinstance(value, (pd.Timestamp, datetime.datetime)):
        return datetime.timedelta(hours=value.hour, minutes=value.minute, seconds=value.second)
    return parse_duration_str(value)

def adjust_work_hours(work_hours_val, break_val):
    """Apply the rule: if there is break, deduct 30 minutes."""
    wh = get_duration(work_hours_val)
    br = None
    if pd.notnull(break_val) and str(break_val).strip() not in ["", "-"]:
        br = get_duration(break_val)
    
    # if wh > datetime.timedelta(hours=6):
    return wh - datetime.timedelta(minutes=30) if br else wh
    # return wh

def get_time_from_val(val):
    """Return a time object from a value (Timestamp, time, or string)."""
    if pd.isnull(val):
        return None
    if isinstance(val, (datetime.datetime, pd.Timestamp)):
        return val.time()
    if isinstance(val, datetime.time):
        return val
    return parse_time_str(val)

def average_time(time_list):
    """Calculate the average time (as HH:MM) from a list of time objects."""
    if not time_list:
        return "-"
    total_minutes = sum(t.hour * 60 + t.minute + t.second/60 for t in time_list)
    avg_minutes = total_minutes / len(time_list)
    hours = int(avg_minutes // 60)
    minutes = int(avg_minutes % 60)
    return f"{hours:02d}:{minutes:02d}"

# --------------------
# Dynamic Column Computation Functions
# --------------------

def compute_difference(standard_time_val, work_time_minus_break_val):
    """
    Compute Difference = |Standard Time - (Work Time - Break)|.
    If either value cannot be converted to a duration, return None.
    """
    try:
        st_duration = get_duration(standard_time_val)
        wtb_duration = get_duration(work_time_minus_break_val)
        if st_duration > wtb_duration:
            diff = st_duration - wtb_duration
        else:
            diff = wtb_duration - st_duration
        return diff
    except Exception:
        return None

def compute_hours_holiday(standard_time_val, work_time_minus_break_val, current_hours_holiday_val):
    """
    Compute Hours Holiday dynamically using the formula:
      If Work Time - Break is empty, return current Hours Holiday.
      Else if Work Time - Break equals "ATTENTION", then 
            Hours Holiday = current Hours Holiday - Standard Time.
      Else if Standard Time > Work Time - Break, then 
            Hours Holiday = current Hours Holiday - Difference,
      Else 
            Hours Holiday = current Hours Holiday + Difference.
    """
    try:
        wtb_str = "" if pd.isnull(work_time_minus_break_val) else str(work_time_minus_break_val).strip().upper()
        if wtb_str == "" or wtb_str == "-":
            return get_duration(current_hours_holiday_val)
        if wtb_str == "ATTENTION":
            return get_duration(current_hours_holiday_val) # - get_duration(standard_time_val)
        diff = compute_difference(standard_time_val, work_time_minus_break_val)
        st_duration = get_duration(standard_time_val)
        wtb_duration = get_duration(work_time_minus_break_val)
        if st_duration > wtb_duration:
            return get_duration(current_hours_holiday_val) - diff
        else:
            return get_duration(current_hours_holiday_val) + diff
    except Exception:
        return None

# --------------------
# Data Loading & Filtering
# --------------------

def load_all_data(excel_file):
    df = pd.read_excel(excel_file, sheet_name='AllData')
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    return df

def filter_month_data(df, month, year):
    df = df.dropna(subset=['Date'])
    mask = (df['Date'].dt.month == month) & (df['Date'].dt.year == year)
    return df.loc[mask].copy()

# --------------------
# PDF Generation Function (with extra columns & additional summary)
# --------------------

def generate_pdf(data, summary, month, year, filename, extra_cols=[]):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Report Title
    month_name = datetime.date(year, month, 1).strftime("%B %Y")
    pdf.cell(0, 10, f"Monthly Timecard Report - {month_name}", ln=1, align='C')
    pdf.ln(5)
    
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    # Compute summary info:
    check_in_list = []
    check_out_list = []
    work_count = 0
    break_count = 0
    total_work_duration = datetime.timedelta(0)
    total_break_duration = datetime.timedelta(0)
    for idx, row in data.iterrows():
        ci = get_time_from_val(row['Check In'])
        co = get_time_from_val(row['Check Out'])
        if ci:
            check_in_list.append(ci)
        if co:
            check_out_list.append(co)
        br_val = row['Break']
        if pd.notnull(br_val) and str(br_val).strip() not in ["", "-"] and ci and co:
            break_count += 1
            total_break_duration += get_duration(br_val)

        work_hours_val = row['Work Hours']
        if pd.notnull(work_hours_val) and str(work_hours_val).strip() not in ["", "-"]:
            work_count += 1
            total_work_duration += get_duration(work_hours_val)

    avg_ci = average_time(check_in_list)
    avg_co = average_time(check_out_list)
    total_work_duration = total_work_duration - total_break_duration
    formatted_total_break = format_duration(total_break_duration)
    formatted_total_work = format_duration(total_work_duration)
    
    rem_vac = format_duration(get_duration(summary.get('Remaining Vacation', 0)))
    
    # Print summary block.
    pdf.cell(0, 10, f"Remaining Vacation Hours: {rem_vac}", ln=1)
    pdf.cell(0, 10, f"Average Check-In: {avg_ci}   Average Check-Out: {avg_co}", ln=1)
    pdf.cell(0, 10, f"Break Summary: {break_count} days with breaks, Total Break Duration: {formatted_total_break}", ln=1)
    pdf.cell(0, 10, f"Work Summary: {work_count} days worked, Total Work Duration: {formatted_total_work}", ln=1)

    # Define base table headers and widths.
    headers = ["Date", "Day", "Check In", "Check Out", "Work Hours", "Break"]
    col_widths = [20, 15, 20, 20, 20, 20]
    
    # Append extra columns.
    for col in extra_cols:
        headers.append(col)
        col_widths.append(40)
    
    # Print table header.
    pdf.set_font("Arial", "B", 10)
    for header, width in zip(headers, col_widths):
        pdf.cell(width, 10, header, border=1, align='C')
    pdf.ln(10)
    
    # Print table rows.
    pdf.set_font("Arial", size=10)
    for idx, row in data.iterrows():
        date_str = row['Date'].strftime("%Y-%m-%d")
        day_str = row.get('Day', '')
        check_in = format_time_value(row['Check In']) if pd.notnull(row['Check In']) else "-"
        check_out = format_time_value(row['Check Out']) if pd.notnull(row['Check Out']) else "-"
        # Here, "Work Hours" is our adjusted value (already computed via adjust_work_hours).
        raw_work = row.get('Work Hours', None)
        raw_break = row.get('Break', None)
        adjusted_wh = adjust_work_hours(raw_work, raw_break) if pd.notnull(raw_work) else datetime.timedelta(0)
        work_hours_str = format_duration(adjusted_wh)
        break_str = format_time_value(row['Break']) if pd.notnull(row['Break']) else "-"
        
        row_values = [date_str, day_str, check_in, check_out, work_hours_str, break_str]
        
        # Process extra columns.
        for col in extra_cols:
            # For dynamic columns, recalc using our formulas.
            if col == "Difference":
                computed = compute_difference(row.get("Standard Time"), row.get("Work Time - Break"))
                value = format_duration(computed) if computed is not None else "-"
            elif col == "Hours Holiday":
                computed = compute_hours_holiday(row.get("Standard Time"), row.get("Work Time - Break"), row.get("Hours Holiday"))
                value = format_duration(computed) if computed is not None else "-"
            else:
                # Otherwise, get the value from the row.
                val = row.get(col, "-")
                if isinstance(val, (datetime.timedelta, pd.Timedelta)):
                    value = format_duration(val)
                else:
                    value = str(val) if pd.notnull(val) else "-"
            row_values.append(value)
        
        # Write the row.
        for value, width in zip(row_values, col_widths):
            pdf.cell(width, 10, value, border=1)
        pdf.ln(10)
    

    
    pdf.output(filename)

# --------------------
# Streamlit Interface with Manual Editing & Customization Options
# --------------------

st.title("Employee Monthly PDF Report Generator")

# File uploader.
excel_file = st.file_uploader("Upload the Excel (.xlsm) file", type=["xlsm", "xlsx"])

# Month and year selection.
col1, col2 = st.columns(2)
with col1:
    month = st.selectbox("Select Month", list(range(1, 13)), index=0)
with col2:
    year = st.number_input("Year", value=2025, step=1)

# Option to include extra columns (e.g. "Note", "Standard Time", "Difference", "Hours Holiday", etc.).
all_possible_cols = ["Note", "Standard Time", "Difference", "Hours Holiday", "Work Time - Break"]
extra_cols = st.multiselect("Select extra columns to include in PDF", options=all_possible_cols)

if st.button("Load Data"):
    if excel_file is not None:
        df_all = load_all_data(excel_file)
        monthly_data = filter_month_data(df_all, month, year)
        if monthly_data.empty:
            st.error("No data found for the selected month and year.")
        else:
            st.success(f"Loaded {len(monthly_data)} records for {month}/{year}.")
            st.write("### Edit the Data (if necessary):")
            edited_data = st.data_editor(monthly_data, num_rows="dynamic", key="editor")
            st.session_state["edited_data"] = edited_data
    else:
        st.error("Please upload the Excel file.")

if st.button("Generate PDF Report"):
    if "edited_data" in st.session_state:
        data_to_use = st.session_state["edited_data"]
        # Compute remaining vacation hours (if available).
        hh_series = data_to_use['Hours Holiday'].dropna() if "Hours Holiday" in data_to_use.columns else None
        remaining_vac = hh_series.iloc[-1] if hh_series is not None and not hh_series.empty else 0
        summary = {"Remaining Vacation": remaining_vac}
        
        filename = f"Monthly_Report_{year}_{month:02d}.pdf"
        generate_pdf(data_to_use, summary, month, year, filename, extra_cols=extra_cols)
        with open(filename, "rb") as pdf_file:
            st.download_button("Download PDF", data=pdf_file, file_name=filename)
    else:
        st.error("No data available. Please load and edit data first.")
