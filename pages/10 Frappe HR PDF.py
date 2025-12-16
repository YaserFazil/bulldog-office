import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Dict, Optional

from streamlit_extras.switch_page_button import switch_page

from frappe_client import (
    fetch_employee_checkins,
    build_daily_checkins_from_employee_checkins,
    fetch_frappe_employees,
    fetch_employee_time_config,
    fetch_employee_attendance,
    build_daily_rows_from_attendance_and_checkins,
)
from utils import (
    decimal_hours_to_hhmmss,
    hhmm_to_decimal,
    compute_work_duration,
    adjust_work_time_and_break,
    compute_time_difference,
    compute_running_holiday_hours,
    load_calendar_events,
    safe_convert_to_df,
)

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image


def main():
    if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
        st.error("You need to log in first.")
        st.session_state["logged_in"] = False
        st.session_state["user_id"] = None
        switch_page("Login")
        return

    st.title("Frappe HR – Employee PDF Report")

    st.markdown(
        """
        Use this page to generate the same style of work-hours PDF report,
        but **directly from Frappe HR (Attendance)** instead of uploaded CSV data.
        
        The report is primarily based on **Attendance** records, with **Employee Checkin** 
        records used only to determine work hours (IN/OUT times) for days when the employee was present.
        """
    )

    # --- Load employees from Frappe (cached in session) ---
    if "frappe_employees" not in st.session_state:
        try:
            with st.spinner("Loading employees from Frappe HR..."):
                st.session_state["frappe_employees"] = fetch_frappe_employees()
        except Exception as e:
            st.error(f"Failed to load employees from Frappe HR: {e}")
            st.session_state["frappe_employees"] = []

    employees = st.session_state.get("frappe_employees", [])
    employee_options = []
    code_by_label = {}
    name_by_code = {}
    for emp in employees:
        code = emp.get("name")
        full_name = emp.get("employee_name") or code
        label = f"{full_name} ({code})"
        employee_options.append(label)
        code_by_label[label] = code
        name_by_code[code] = full_name

    col1, col2 = st.columns(2)
    with col1:
        if employee_options:
            selected_label = st.selectbox("Frappe Employee", employee_options)
            employee_code = code_by_label[selected_label]
            employee_display_name = name_by_code.get(employee_code, employee_code)
        else:
            employee_code = None
            employee_display_name = ""
            st.warning("No employees available from Frappe HR.")
    with col2:
        today = date.today()
        date_input_value = st.date_input(
            "Select date range",
            value=[date(today.year, today.month, 1), today],
        )
        # `date_input` may return a single date or a list/tuple of dates
        if isinstance(date_input_value, (list, tuple)) and len(date_input_value) == 2:
            start_date, end_date = date_input_value
        else:
            # Fallback: treat the single selected date as both start and end
            single = date_input_value if not isinstance(date_input_value, (list, tuple)) else date_input_value[0]
            start_date, end_date = single, single

    # --- Load per-employee time config from Frappe ---
    def normalize_time_value(value: object, fallback: str) -> str:
        if value is None or value == "":
            return fallback
        try:
            # Numeric value interpreted as decimal hours
            if isinstance(value, (int, float)):
                return decimal_hours_to_hhmmss(float(value))
            # Already a time-like string
            return str(value)
        except Exception:
            return fallback

    frappe_config = {}
    if employee_code:
        # Always fetch fresh data (no caching) to ensure latest data from Frappe HR
        try:
            # Try calling with report_start_date parameter
            import inspect
            sig = inspect.signature(fetch_employee_time_config)
            if 'report_start_date' in sig.parameters:
                frappe_config = fetch_employee_time_config(employee_code, report_start_date=start_date)
            else:
                # Fallback for cached old version - call without the parameter
                frappe_config = fetch_employee_time_config(employee_code)
                # Manually calculate overtime if needed
                if start_date and frappe_config.get("standard_work_hours"):
                    from frappe_client import calculate_historical_overtime_balance
                    try:
                        calculated_overtime = calculate_historical_overtime_balance(
                            employee_code=employee_code,
                            standard_work_hours_hhmm=frappe_config.get("standard_work_hours"),
                            start_date=start_date,
                        )
                        frappe_config["initial_overtime"] = calculated_overtime
                    except Exception:
                        pass
        except Exception as e:
            st.warning(f"Could not load time configuration from Frappe for {employee_code}: {e}")
            frappe_config = {}

    std_default = normalize_time_value(frappe_config.get("standard_work_hours"), "08:00")
    overtime_default = normalize_time_value(frappe_config.get("initial_overtime"), "00:00")
    holiday_default = normalize_time_value(frappe_config.get("initial_holiday_hours"), "00:00")

    col3, col4, col5 = st.columns(3)
    with col3:
        standard_work_hours_str = st.text_input(
            "Standard Work Hours per Day",
            value=std_default,
        )
        standard_work_hours = hhmm_to_decimal(standard_work_hours_str)
    with col4:
        initial_overtime_str = st.text_input(
            "Initial Overtime Balance",
            value=overtime_default,
        )
    with col5:
        holiday_hours_str = st.text_input(
            "Initial Holiday Hours",
            value=holiday_default,
        )
        holiday_hours = hhmm_to_decimal(holiday_hours_str)

    if st.button("Generate PDF from Frappe HR", use_container_width=True):
        if not employee_code:
            st.error("Please select a Frappe employee.")
            return

        try:
            with st.spinner("Fetching Attendance data from Frappe HR..."):
                # Fetch Attendance records as primary source
                attendance_records = fetch_employee_attendance(
                    employee_code=employee_code,
                    start_date=start_date,
                    end_date=end_date,
                )

            if not attendance_records:
                st.warning("No Attendance data found for the selected period.")
                return

            # Fetch Employee Checkin records to get IN/OUT times for days when employee was present
            with st.spinner("Fetching Employee Checkin data for work hours..."):
                raw_checkins = fetch_employee_checkins(
                    employee_code=employee_code,
                    start=datetime.combine(start_date, datetime.min.time()),
                    end=datetime.combine(end_date, datetime.max.time()),
                )
            
            # Build checkins by date dictionary for quick lookup
            checkins_by_date: Dict[str, Dict[str, Optional[str]]] = {}
            if raw_checkins:
                daily_checkins = build_daily_checkins_from_employee_checkins(raw_checkins)
                for checkin_row in daily_checkins:
                    date_key = checkin_row["Date"].isoformat() if isinstance(checkin_row["Date"], date) else str(checkin_row["Date"])
                    checkins_by_date[date_key] = {
                        "IN": checkin_row.get("IN"),
                        "OUT": checkin_row.get("OUT"),
                    }
            
            # Build daily rows from Attendance records, filling in IN/OUT from checkins
            daily_rows = build_daily_rows_from_attendance_and_checkins(
                attendance_records=attendance_records,
                checkins_by_date=checkins_by_date,
            )
            
            # Load calendar events for holidays
            calendar_events = load_calendar_events()
            calendar_events_date = {
                pd.to_datetime(date_str, format="%Y-%m-%d").date(): event
                for date_str, event in calendar_events.items()
            }
            
            # Get all dates in the selected range
            all_dates_in_range = set()
            current_date = start_date
            while current_date <= end_date:
                all_dates_in_range.add(current_date)
                current_date += timedelta(days=1)
            
            # Get dates that already have Attendance records
            existing_dates = {row["Date"] for row in daily_rows if "Date" in row}
            
            # Find missing dates (weekends and holidays without Attendance records)
            missing_weekends_holidays = []
            for date_obj in all_dates_in_range:
                if date_obj not in existing_dates:
                    # Check if it's a weekend (Saturday=5, Sunday=6)
                    is_weekend = date_obj.weekday() >= 5
                    # Check if it's in calendar events (could be weekend or public holiday)
                    holiday_label_from_calendar = calendar_events_date.get(date_obj)
                    is_in_calendar = holiday_label_from_calendar is not None
                    
                    # Determine if it's a public holiday:
                    # - If it's in calendar events AND NOT a weekend, it's a public holiday
                    # - If it's in calendar events AND is a weekend, check the label
                    is_public_holiday = False
                    if is_in_calendar:
                        if not is_weekend:
                            # Not a weekend but in calendar = public holiday
                            is_public_holiday = True
                        else:
                            # It's a weekend, check if calendar label indicates it's also a holiday
                            holiday_str = str(holiday_label_from_calendar).lower()
                            # If label contains "holiday" (and not just "weekend"), it's a public holiday on weekend
                            if "holiday" in holiday_str and holiday_str != "weekend":
                                is_public_holiday = True
                    
                    # Include weekends OR public holidays
                    if is_weekend or is_public_holiday:
                        # Determine holiday label and leave type
                        if is_weekend and is_public_holiday:
                            # Weekend that is also a public holiday
                            holiday_label = holiday_label_from_calendar or "Weekend/Holiday"
                            leave_type = "Public Holiday"  # It's a public holiday, so mark as Paid Holiday
                        elif is_weekend:
                            # Just a weekend (not a public holiday)
                            holiday_label = "Weekend"
                            leave_type = None  # Weekends are NOT paid holidays
                        else:
                            # Public holiday that is NOT a weekend
                            holiday_label = holiday_label_from_calendar or "Holiday"
                            leave_type = "Public Holiday"  # Public holidays are paid holidays
                        
                        # Create a row for this missing weekend/holiday
                        day_name = date_obj.strftime("%a").upper()
                        missing_weekends_holidays.append({
                            "Day": day_name,
                            "Date": date_obj,
                            "IN": None,
                            "OUT": None,
                            "Status": "On Leave",
                            "Leave Type": leave_type,
                            "Holiday": holiday_label,
                        })
            
            # Combine Attendance records with missing weekends/holidays
            if missing_weekends_holidays:
                daily_rows.extend(missing_weekends_holidays)
            
            if not daily_rows:
                st.warning("No daily rows generated from Attendance data.")
                return
            
            df = pd.DataFrame(daily_rows)

            # First, populate Holiday column from calendar events (only for rows where Holiday is not already set)
            # This preserves the Holiday values we set for missing weekends/holidays
            df["Holiday"] = df.apply(
                lambda row: row.get("Holiday") if pd.notnull(row.get("Holiday")) and str(row.get("Holiday")).strip() != "" 
                else calendar_events_date.get(row["Date"]), 
                axis=1
            )
            
            # Then, mark "Paid Holiday" leave types as holidays (only if Holiday is not already set to a specific value)
            # This ensures "On Leave" with "Paid Holiday" leave type is considered as holiday
            # But don't override if Holiday already has a meaningful value (like holiday name)
            paid_holiday_mask = (
                (df["Status"] == "On Leave") & 
                (df["Leave Type"] == "Paid Holiday") &
                (df["Holiday"].isna() | (df["Holiday"] == "") | (df["Holiday"].astype(str).str.strip() == ""))
            )
            df.loc[paid_holiday_mask, "Holiday"] = "Paid Holiday"
            
            # Mark "Sick" leave types in the Holiday column
            # This ensures "On Leave" with "Sick" leave type is marked as "sick" in Holiday column
            sick_leave_mask = (
                (df["Status"] == "On Leave") & 
                (df["Leave Type"] == "Sick")
            )
            df.loc[sick_leave_mask, "Holiday"] = "sick"
            df["Break"] = None
            df["Standard Time"] = decimal_hours_to_hhmmss(standard_work_hours)
            df["Difference"] = None
            df["Difference (Decimal)"] = None
            # Initialize Multiplication to 1.0 for all rows first
            df["Multiplication"] = 1.0
            df["Hours Overtime Left"] = None
            df["Holiday Hours"] = None
            
            # Set Multiplication to 2.0 for Sundays and Public Holidays
            # Sunday is weekday() == 6
            # Public Holidays are in calendar_events_date
            # Use vectorized operations for better performance and reliability
            def get_date_obj(date_val):
                """Convert various date formats to date object"""
                if isinstance(date_val, date):
                    return date_val
                elif isinstance(date_val, pd.Timestamp):
                    return date_val.date()
                elif isinstance(date_val, str):
                    return pd.to_datetime(date_val).date()
                else:
                    # Try to convert using pd.to_datetime
                    return pd.to_datetime(date_val).date()
            
            # Convert all dates to date objects for comparison
            df_dates = df["Date"].apply(get_date_obj)
            
            # Check for Sundays (weekday == 6)
            is_sunday = df_dates.apply(lambda d: d.weekday() == 6)
            
            # Check for Public Holidays
            is_public_holiday = df_dates.apply(lambda d: d in calendar_events_date)
            
            # Set Multiplication to 2.0 for Sundays or Public Holidays
            # Use .copy() to ensure we're working with a proper boolean Series
            mask = (is_sunday | is_public_holiday).copy()
            df.loc[mask, "Multiplication"] = 2.0
            
            # Ensure Multiplication is explicitly set (defensive check)
            # This ensures no row has Multiplication > 2.0 or < 1.0
            df["Multiplication"] = df["Multiplication"].clip(lower=1.0, upper=2.0)

            # Only calculate work duration for days when employee was present or half day
            df[" Daily Total"] = df.apply(
                lambda row: compute_work_duration(row.get("IN", ""), row.get("OUT", "")) 
                if row.get("Status") in ["Present", "Half Day"] else "", 
                axis=1
            )
            df["Work Time"], df["Break"] = zip(
                *df.apply(
                    lambda row: adjust_work_time_and_break(
                        row[" Daily Total"],
                        row.get("Break"),
                        "06:00",
                        "00:30",
                    ) if row.get("Status") in ["Present", "Half Day"] else ("", row.get("Break")),
                    axis=1,
                )
            )

            df["Difference"] = df.apply(
                lambda row: compute_time_difference(
                    row.get("Work Time", ""),
                    row.get("Standard Time", ""),
                    row.get("Holiday", ""),
                    True,
                ),
                axis=1,
            )
            df["Difference (Decimal)"] = df.apply(
                lambda row: compute_time_difference(
                    row.get("Work Time", ""),
                    row.get("Standard Time", ""),
                    row.get("Holiday", ""),
                    False,
                ),
                axis=1,
            )

            # Include all dates with non-empty Holiday column (including "Paid Holiday")
            valid_holiday_mask = df["Holiday"].apply(lambda v: pd.notnull(v) and str(v).strip() != "")
            holiday_event_dates = set(
                df.loc[valid_holiday_mask, "Date"].apply(lambda d: d.strftime("%Y-%m-%d"))
            )

            df = compute_running_holiday_hours(
                df,
                holiday_event_dates,
                calendar_events_date,
                holiday_hours,
                initial_overtime_str,
            )

            # Re-verify and fix Multiplication after compute_running_holiday_hours
            # This ensures Multiplication is always correct, even if something went wrong
            def get_date_obj_safe(date_val):
                """Convert various date formats to date object"""
                if isinstance(date_val, date):
                    return date_val
                elif isinstance(date_val, pd.Timestamp):
                    return date_val.date()
                elif isinstance(date_val, str):
                    return pd.to_datetime(date_val).date()
                else:
                    return pd.to_datetime(date_val).date()
            
            # Re-check and set Multiplication correctly
            df_dates_after = df["Date"].apply(get_date_obj_safe)
            is_sunday_after = df_dates_after.apply(lambda d: d.weekday() == 6)
            is_public_holiday_after = df_dates_after.apply(lambda d: d in calendar_events_date)
            
            # Reset Multiplication to 1.0 first, then set to 2.0 for Sundays and Public Holidays
            df["Multiplication"] = 1.0
            df.loc[is_sunday_after | is_public_holiday_after, "Multiplication"] = 2.0
            
            # Final safeguard: clip to ensure no value is outside 1.0-2.0 range
            df["Multiplication"] = df["Multiplication"].clip(lower=1.0, upper=2.0)

            df = df.sort_values("Date").reset_index(drop=True)

            # Metrics for PDF summary
            hours_expected_total = 0.0
            for _, row in df.iterrows():
                std = row.get("Standard Time")
                is_holiday = row.get("Holiday")
                if std and str(std).strip() != "" and (not is_holiday or str(is_holiday).strip() == ""):
                    try:
                        hours_expected_total += hhmm_to_decimal(str(std))
                    except Exception:
                        pass
            hours_expected_str = decimal_hours_to_hhmmss(hours_expected_total)

            total_work = 0.0
            for t in df["Work Time"]:
                if t and str(t).strip() != "":
                    try:
                        total_work += hhmm_to_decimal(str(t))
                    except Exception:
                        pass
            hours_worked_str = decimal_hours_to_hhmmss(total_work)

            # Build PDF (simplified version based on Home page)
            employee_name = employee_display_name or employee_code
            pay_period = f"{start_date} - {end_date}"

            pdf_buffer = BytesIO()
            doc = SimpleDocTemplate(
                pdf_buffer,
                pagesize=landscape(A4),
                leftMargin=30,
                rightMargin=30,
                topMargin=60,
                bottomMargin=40,
            )

            styles = getSampleStyleSheet()

            header_style = ParagraphStyle(
                "Header",
                parent=styles["Heading1"],
                fontName="Helvetica-Bold",
                fontSize=24,
                textColor=colors.HexColor("#2c3e50"),
                alignment=1,
                spaceAfter=20,
            )

            def add_header_footer(canvas, doc_):
                canvas.saveState()
                canvas.setFont("Helvetica-Bold", 16)
                canvas.setFillColor(colors.HexColor("#2c3e50"))
                canvas.drawString(40, doc_.pagesize[1] - 40, "Bulldog Office - Work Hours Report (Frappe HR)")
                canvas.setFont("Helvetica", 10)
                canvas.setFillColor(colors.HexColor("#7f8c8d"))
                canvas.drawRightString(doc_.pagesize[0] - 40, 30, f"Page {doc_.page}")
                canvas.restoreState()

            elements = []

            # -- First Page: Enhanced Summary --
            # Resize logo
            logo = Image("https://bulldogsliving.com/img/brand_logo/logo.png", width=200, height=60)
            elements.append(logo)
            elements.append(Spacer(1, 30))

            # Summary page
            elements.append(Paragraph("WORK HOURS SUMMARY (Frappe HR)", header_style))
            elements.append(Spacer(1, 30))

            last_row = df.iloc[-1]
            
            # Calculate Total Sick Days
            sick_days_count = 0
            for _, row in df.iterrows():
                holiday_val = row.get("Holiday", "")
                leave_type = row.get("Leave Type", "")
                if (holiday_val and str(holiday_val).strip().lower() == "sick") or \
                   (leave_type and str(leave_type).strip() == "Sick"):
                    sick_days_count += 1
            
            # Calculate Total Available Time Off (HH:MM)
            # Combine holiday hours + overtime balance (only if overtime is positive)
            holiday_hours_str = last_row.get("Holiday Hours", "00:00") or "00:00"
            overtime_balance_str = last_row.get("Hours Overtime Left", "00:00") or "00:00"
            
            holiday_hours_decimal = hhmm_to_decimal(holiday_hours_str)
            overtime_balance_decimal = hhmm_to_decimal(overtime_balance_str)
            
            # Only add overtime if it's positive (overtime, not undertime)
            total_available_time_off_decimal = holiday_hours_decimal
            if overtime_balance_decimal > 0:
                total_available_time_off_decimal += overtime_balance_decimal
            
            total_available_time_off_hhmm = decimal_hours_to_hhmmss(total_available_time_off_decimal)
            
            # Calculate Total Available Time Off (Days)
            # Convert HH:MM to days based on standard work hours per day
            total_available_time_off_days = total_available_time_off_decimal / standard_work_hours
            total_available_time_off_days_str = f"{total_available_time_off_days:.2f}"
            
            summary_data = [
                ["Metric", "Value", "What This Means"],
                ["Employee", employee_name, "Your name as recorded in the system"],
                ["Pay Period", pay_period, "The date range this report covers"],
                ["Hours worked", hours_worked_str, "Total hours you actually worked (sum of all 'Work Time' entries)"],
                ["Hours expected", hours_expected_str, "Total hours you were expected to work (sum of all 'Standard Time' entries, excluding holidays)"],
                ["Overtime/Undertime Balance", overtime_balance_str, "Your current overtime balance. Positive = overtime earned, Negative = undertime owed"],
                ["Remaining Holiday Hours", holiday_hours_str, "Your remaining paid holiday hours that you can use"],
                ["Total Sick Days", str(sick_days_count), "Number of days marked as sick leave in this period"],
                ["Total Available Time Off (HH:MM)", total_available_time_off_hhmm, "Combined hours of holiday time + overtime that you can use for time off"],
                ["Total Available Time Off (Days)", total_available_time_off_days_str, "Your total available time off converted to full work days (assuming 8-hour workday)"],
            ]

            summary_table = Table(summary_data, colWidths=[150, 150, 420])
            summary_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3498db")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#bdc3c7")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f6fa")]),
                    ]
                )
            )
            elements.append(summary_table)
            elements.append(PageBreak())

            # Detailed table
            elements.append(Paragraph("DETAILED WORK LOG (Frappe HR)", header_style))
            elements.append(Spacer(1, 20))

            desired_columns = [
                "Date",
                " Daily Total",
                "Break",
                "Day",
                "Holiday",
                "Holiday Hours",
                "Hours Overtime Left",
                "IN",
                "OUT",
                "Standard Time",
                "Multiplication",
                "Work Time",
            ]
            df_table = df[desired_columns].copy()

            table_data = [df_table.columns.tolist()] + df_table.astype(str).values.tolist()
            data_table = Table(table_data, repeatRows=1)
            data_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2ecc71")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f6fa")]),
                    ]
                )
            )
            elements.append(data_table)
            elements.append(PageBreak())

            # -- Detailed Explanation Pages --
            elements.append(Paragraph("📋 COMPLETE REPORT EXPLANATION", header_style))
            elements.append(Spacer(1, 20))

            # Create explanation styles
            explanation_style = ParagraphStyle(
                'Explanation',
                parent=styles['Normal'],
                fontName='Helvetica',
                fontSize=11,
                textColor=colors.HexColor("#2c3e50"),
                alignment=0,
                spaceAfter=8,
                leftIndent=0
            )

            section_style = ParagraphStyle(
                'Section',
                parent=styles['Heading2'],
                fontName='Helvetica-Bold',
                fontSize=14,
                textColor=colors.HexColor("#2c3e50"),
                alignment=0,
                spaceAfter=10,
                spaceBefore=15
            )

            # Page 1: Summary Metrics Explanation
            elements.append(Paragraph("📊 SUMMARY METRICS EXPLANATION", section_style))
            
            summary_explanations = [
                "🏢 <b>Employee & Pay Period:</b> Basic identification information showing your name and the time period covered by this report.",
                "",
                "⏰ <b>Hours Worked:</b> The total number of hours you actually worked during this period. This is calculated by adding up all your 'Work Time' entries from each day.",
                "",
                "📅 <b>Hours Expected:</b> The total number of hours you were supposed to work during this period. This is calculated by adding up all your 'Standard Time' entries (usually 8 hours per day), excluding holidays and weekends.",
                "",
                "💰 <b>Overtime or Undertime Balance:</b> This shows your current overtime balance. A positive number means you've worked extra hours that you can use as time off. A negative number means you owe hours to the company.",
                "",
                "🏖️ <b>Remaining Holiday Hours:</b> Your remaining paid holiday hours that you can use for vacation or other time off.",
                "",
                "🏥 <b>Total Sick Days:</b> The number of days in this period that were marked as sick leave.",
                "",
                "📈 <b>Total Available Time Off (HH:MM):</b> The combined total of your holiday hours plus overtime balance (if positive) - this is the total time you can take off in hours and minutes.",
                "",
                "📊 <b>Total Available Time Off (Days):</b> Your available time off converted to full work days (based on your standard work hours per day)."
            ]
            
            for explanation in summary_explanations:
                if explanation.strip():
                    elements.append(Paragraph(explanation, explanation_style))
                else:
                    elements.append(Spacer(1, 5))

            elements.append(Spacer(1, 15))

            # Page 2: Detailed Work Log Explanation
            elements.append(Paragraph("📋 DETAILED WORK LOG EXPLANATION", section_style))
            
            work_log_explanations = [
                "📅 <b>Date:</b> The specific date of the work entry.",
                "",
                "⏰ <b>Daily Total:</b> The total time you were present at work (from check-in to check-out).",
                "",
                "☕ <b>Break:</b> The total break time taken during your work day.",
                "",
                "📆 <b>Day:</b> The day of the week (MON, TUE, WED, etc.).",
                "",
                "🎉 <b>Holiday:</b> Any holiday or special event on this date (Weekend, Holiday, Vacation, Sick, etc.).",
                "",
                "🏖️ <b>Holiday Hours:</b> Your running balance of remaining holiday hours after this date.",
                "",
                "💰 <b>Hours Overtime Left:</b> Your running balance of overtime hours after this date.",
                "",
                "🕐 <b>IN:</b> Your check-in time for the day.",
                "",
                "🕕 <b>OUT:</b> Your check-out time for the day.",
                "",
                "⏱️ <b>Standard Time:</b> The number of hours you were expected to work on this day (usually 8 hours).",
                "",
                "📊 <b>Multiplication:</b> Any multiplier applied to your hours (e.g., 2.0 for Sunday or public holiday work).",
                "",
                "💼 <b>Work Time:</b> The actual hours you worked after subtracting break time."
            ]
            
            for explanation in work_log_explanations:
                if explanation.strip():
                    elements.append(Paragraph(explanation, explanation_style))
                else:
                    elements.append(Spacer(1, 5))

            elements.append(Spacer(1, 15))

            # Page 3: How Calculations Work
            elements.append(Paragraph("🧮 HOW CALCULATIONS WORK", section_style))
            
            calculation_explanations = [
                "📊 <b>Work Time Calculation:</b>",
                "   Work Time = Daily Total - Break Time",
                "   Example: If you were at work for 9 hours and took 1 hour break, your Work Time = 8 hours",
                "",
                "💰 <b>Overtime Calculation:</b>",
                "   Overtime = Work Time - Standard Time",
                "   Example: If you worked 9 hours and standard time is 8 hours, overtime = 1 hour",
                "",
                "📊 <b>Multiplication for Sundays and Public Holidays:</b>",
                "   • Work hours on Sundays are multiplied by 2.0",
                "   • Work hours on public holidays are multiplied by 2.0",
                "   • This multiplied time is added to your overtime balance",
                "",
                "🏖️ <b>Holiday Hours:</b>",
                "   • You start with a certain number of holiday hours per year",
                "   • Each day you take vacation (Paid Holiday) deducts hours from your balance",
                "   • Sick days do NOT deduct from holiday hours",
                "   • Weekends and public holidays are free and do NOT deduct from holiday hours",
                "   • The remaining balance is shown in the 'Holiday Hours' column",
                "",
                "💰 <b>Overtime Balance:</b>",
                "   • Positive overtime hours accumulate when you work more than standard time",
                "   • Work on Sundays and public holidays is multiplied by 2.0 and added to overtime",
                "   • These can be used for time off or paid out",
                "   • The running balance is shown in the 'Hours Overtime Left' column",
                "",
                "📈 <b>Available Time Off:</b>",
                "   Total Available = Holiday Hours + Overtime Balance (if positive)",
                "   This is the total time you can take off."
            ]
            
            for explanation in calculation_explanations:
                if explanation.strip():
                    elements.append(Paragraph(explanation, explanation_style))
                else:
                    elements.append(Spacer(1, 5))

            elements.append(Spacer(1, 15))

            # Page 4: Understanding the Data
            elements.append(Paragraph("🔍 UNDERSTANDING YOUR DATA", section_style))
            
            understanding_explanations = [
                "📊 <b>Reading the Summary:</b>",
                "   • Compare 'Hours Worked' vs 'Hours Expected' to see if you met your work requirements",
                "   • Check 'Overtime Balance' to see if you have extra time available",
                "   • Review 'Holiday Hours' to know how much vacation time you have left",
                "   • Check 'Total Available Time Off' to see your combined time off balance",
                "",
                "📅 <b>Understanding Patterns:</b>",
                "   • Look for consistent work patterns",
                "   • Identify days with high overtime",
                "   • Check your break time usage",
                "   • Note Sundays and public holidays with 2.0 multiplication",
                "",
                "⚠️ <b>What to Watch For:</b>",
                "   • Negative overtime balance (means you owe hours)",
                "   • Low holiday hours remaining",
                "   • Inconsistent check-in/check-out times",
                "   • Missing break times on long work days",
                "",
                "📋 <b>Data Source:</b>",
                "   This report is generated from Frappe HR Attendance and Employee Checkin records.",
                "   All data is automatically synchronized from your Frappe HR system."
            ]
            
            for explanation in understanding_explanations:
                if explanation.strip():
                    elements.append(Paragraph(explanation, explanation_style))
                else:
                    elements.append(Spacer(1, 5))

            elements.append(Spacer(1, 15))

            # Page 5: Contact Information
            elements.append(Paragraph("📞 NEED HELP?", section_style))
            
            help_explanations = [
                "If you have questions about this report or need clarification on any of the data:",
                "",
                "📧 <b>Contact your supervisor or HR department</b>",
                "📱 <b>Check the documentation in the Bulldog Office system</b>",
                "📋 <b>Review your attendance records in Frappe HR for accuracy</b>",
                "",
                "This report is generated automatically based on your Frappe HR Attendance and Employee Checkin data. If you notice any discrepancies, please contact your supervisor immediately."
            ]
            
            for explanation in help_explanations:
                if explanation.strip():
                    elements.append(Paragraph(explanation, explanation_style))
                else:
                    elements.append(Spacer(1, 5))

            doc.build(elements, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
            pdf_data = pdf_buffer.getvalue()

            st.download_button(
                label="Download Frappe HR PDF",
                data=pdf_data,
                file_name=f"{employee_name}_pay_period_{pay_period}_frappe_hr.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

        except Exception as e:
            st.error(f"Failed to generate PDF from Frappe HR: {e}")


if __name__ == "__main__":
    main()


