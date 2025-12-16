import streamlit as st
import pandas as pd
from datetime import date, datetime
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
            
            if not daily_rows:
                st.warning("No daily rows generated from Attendance data.")
                return
            
            df = pd.DataFrame(daily_rows)

            calendar_events = load_calendar_events()
            calendar_events_date = {
                pd.to_datetime(date_str, format="%Y-%m-%d").date(): event
                for date_str, event in calendar_events.items()
            }

            df["Holiday"] = df["Date"].map(calendar_events_date)
            df["Break"] = None
            df["Standard Time"] = decimal_hours_to_hhmmss(standard_work_hours)
            df["Difference"] = None
            df["Difference (Decimal)"] = None
            df["Multiplication"] = 1.0
            df["Hours Overtime Left"] = None
            df["Holiday Hours"] = None

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

            # Summary page
            elements.append(Paragraph("WORK HOURS SUMMARY (Frappe HR)", header_style))
            elements.append(Spacer(1, 30))

            last_row = df.iloc[-1]
            summary_data = [
                ["Metric", "Value"],
                ["Employee", employee_name],
                ["Pay Period", pay_period],
                ["Hours worked", hours_worked_str],
                ["Hours expected", hours_expected_str],
                ["Overtime/Undertime Balance", last_row.get("Hours Overtime Left", "00:00") or "00:00"],
                ["Remaining Holiday Hours", last_row.get("Holiday Hours", "00:00") or "00:00"],
            ]

            summary_table = Table(summary_data, colWidths=[200, 200])
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
                "Day",
                "Status",
                "Leave Type",
                "IN",
                "OUT",
                " Daily Total",
                "Break",
                "Work Time",
                "Standard Time",
                "Holiday",
                "Holiday Hours",
                "Hours Overtime Left",
                "Multiplication",
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


