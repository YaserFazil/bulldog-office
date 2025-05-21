import streamlit as st
import pandas as pd
from io import BytesIO
from utils import get_employees, get_employee_id, fetch_employee_work_history, safe_convert_to_df, upsert_employee_work_history, hhmm_to_decimal, compute_work_duration, adjust_work_time_and_break, compute_time_difference, compute_running_holiday_hours, decimal_hours_to_hhmmss, load_calendar_events, send_the_pdf_created_in_history_page_to_email
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
def main_work():
    st.title("Work History Records")
    
    all_usernames = get_employees()
    selected_username = st.selectbox("Select Employee", all_usernames)
    
    if selected_username:
        employee_id, full_name = get_employee_id(selected_username)
        work_history, previous_hours_overtime, previous_holiday_days = fetch_employee_work_history(employee_id)
        if work_history.empty:
            st.warning("No work history found for this employee.")
            return

        # --- Display Header Info in Widgets ---
        st.subheader("Timecard Report")
        employee_name = full_name
        col1, col2, col13 = st.columns(3,vertical_alignment="bottom")
        default_pay_period_from = st.session_state["edited_work_history_data"]["Date"][0] if "edited_work_history_data" in st.session_state and "Date" in st.session_state["edited_work_history_data"] else work_history["Date"][0]
        default_pay_period_to = st.session_state["edited_work_history_data"]["Date"].iloc[-1] if "edited_work_history_data" in st.session_state and "Date" in st.session_state["edited_work_history_data"] else work_history["Date"].iloc[-1]
        with col1:
            pay_period_from_selected = st.date_input("**Pay Period From:**", value=default_pay_period_from)
        with col2:
            pay_period_to_selected = st.date_input("**Pay Period To:**", value=default_pay_period_to, min_value=pay_period_from_selected)
        with col13:
            period_loaded = st.button("Load selected period")
        if period_loaded:
            # # Fetch filtered data based on employee selection
            work_history, previous_hours_overtime, previous_holiday_days = fetch_employee_work_history(employee_id, pay_period_from_selected, pay_period_to_selected)
            latest_holiday_day = previous_holiday_days if previous_holiday_days else int(work_history["Holiday Days"].iloc[0]) if "Holiday Days" in work_history and work_history["Holiday Days"].iloc[0] else int(0)
            latest_hours_overtime_left = (
                previous_hours_overtime
                if previous_hours_overtime is not None
                else work_history["Hours Overtime Left"].iloc[0]
                if "Hours Overtime Left" in work_history and work_history["Hours Overtime Left"].iloc[0] is not None
                else "00:00"
            )

            st.session_state["latest_holiday_days_left"] = latest_holiday_day
            st.session_state["latest_hours_overtime_left"] = latest_hours_overtime_left
            st.session_state["edited_work_history_data"] = work_history
            st.rerun()
        if "edited_work_history_data" in st.session_state and not st.session_state.get("edited_work_history_data").empty:
            employee_name = st.text_input("**Employee Name:**", value=employee_name, disabled=True)
            holiday_day_col, hours_overtime_col = st.columns(2)
            col4, col5, col6 = st.columns(3)
            with holiday_day_col:
                holiday_days = st.number_input("**Holiday Days Left:**", value=st.session_state["latest_holiday_days_left"])
            with hours_overtime_col:
                hours_overtime = st.text_input("**Hours Overtime:**", value=st.session_state["latest_hours_overtime_left"])
                hours_overtime_str = hours_overtime
                hours_overtime = int(hhmm_to_decimal(hours_overtime))
                       
            with col4:
                standard_work_hours = st.text_input("**Standard Work Hours**", value="08:00")
                standard_work_hours_str = standard_work_hours
                standard_work_hours = int(hhmm_to_decimal(standard_work_hours))
            with col5:
                break_rule_hours = st.text_input("**Break Rule Hour(s)**", value="06:30")
            with col6:
                break_hours = st.text_input("**Break Hour(s)**", value="00:30")



            # Define column configurations
            column_configuration = {
                "Day": st.column_config.TextColumn(
                    "Day",
                    required=True,
                ),
                "Date": st.column_config.DateColumn(
                    "Date",
                    required=True,
                ),
                "Standard Time": st.column_config.TextColumn(
                    "Standard Time",
                    required=True,
                    default=standard_work_hours_str
                ),
            }
            edited_work_history_data = st.data_editor(
                data=st.session_state["edited_work_history_data"],
                num_rows="dynamic",
                column_config=column_configuration,
                column_order=[
                    "Day", 
                    "Date", 
                    "IN", 
                    "OUT", 
                    "Work Time", 
                    " Daily Total", 
                    " Note",
                    "Break",
                    "Standard Time",
                    "Difference",
                    "Difference (Decimal)",
                    "Multiplication",
                    "Holiday",
                    "Holiday Days",
                    "Hours Overtime Left",
                    "employee_id",
                    "_id"
                ],
                disabled=["_id", "employee_id"],
                key="edited_work_history_data_editor"
            )
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("Calculate Work Duration", use_container_width=True):
                    updated_df = safe_convert_to_df(edited_work_history_data).copy()
                    updated_df[" Daily Total"] = updated_df.apply(
                        lambda row: compute_work_duration(row.get("IN", ""), row.get("OUT", "")), axis=1
                    )
                    updated_df["Work Time"], updated_df["Break"] = zip(*updated_df.apply(
                        lambda row: adjust_work_time_and_break(row[" Daily Total"], row.get("Break"), break_rule_hours, break_hours), axis=1
                    ))

                    # Calculate the difference between "Work Time" and "Standard Time"
                    # Both columns are in "hh:mm" string format.
                    updated_df["Difference"] = updated_df.apply(
                        lambda row: compute_time_difference(row.get("Work Time", ""), row.get("Standard Time", ""), row.get("Holiday", ""), True),
                        axis=1
                    )
                    updated_df["Difference (Decimal)"] = updated_df.apply(
                        lambda row: compute_time_difference(row.get("Work Time", ""), row.get("Standard Time", ""), row.get("Holiday", ""), False),
                        axis=1
                    )
                    st.session_state["edited_work_history_data"] = updated_df
                    st.rerun()
            
            with col2:
                # --- New: Calculate Holiday Hours Running Balance ---
                if st.button("Calculate Holiday", use_container_width=True):
                    # Load holiday events from the JSON file.
                    calendar_events = load_calendar_events()  # keys are like "2025-01-04", values like "Weekend/Holiday"

                    # Convert the keys from string to date objects.
                    calendar_events_date = {
                        pd.to_datetime(date_str, format="%Y-%m-%d").date(): event 
                        for date_str, event in calendar_events.items()
                    }
                    df = safe_convert_to_df(edited_work_history_data).copy()
                    
                    # Helper function to ensure the 'Holiday' column has a valid, non-empty value.
                    def is_valid_holiday(value):
                        return pd.notnull(value) and str(value).strip() != ''
                    
                    valid_holiday_mask = df['Holiday'].apply(is_valid_holiday)
                    
                    # Convert the date objects to strings in "YYYY-MM-DD" format.
                    holiday_event_dates = set(
                        df.loc[valid_holiday_mask, 'Date'].apply(lambda d: d.strftime('%Y-%m-%d'))
                    )
                    
                    # Compute running holiday hours using the extracted holiday dates.
                    df = compute_running_holiday_hours(df, holiday_event_dates, calendar_events_date, holiday_days, hours_overtime_str)
                    
                    st.session_state["edited_work_history_data"] = df
                    st.success("Holiday hours calculated and updated!")
                    st.rerun()
            
            with col3:
                # Implement actual save logic here
                if st.button("Save Changes", use_container_width=True):
                    # employee_id, full_name = get_employee_id(selected_username)
                    updated_df = safe_convert_to_df(edited_work_history_data).copy()
                    work_history_created = upsert_employee_work_history(updated_df, employee_id)
                    if work_history_created["success"] == True:
                        st.success("Successfully Saved Data!")
                        
                        st.session_state["edited_work_history_data"], previous_hours_overtime, previous_holiday_days = fetch_employee_work_history(employee_id)
                        st.rerun()
                    else:
                        st.error(f"Couldn't save work history: {work_history_created}")

            # ------------------------
            # Export Options
            # ------------------------
            st.subheader("Export Records")
            pay_period = f"{pay_period_from_selected} - {pay_period_to_selected}"

            col8, col9, col_send_email_btn = st.columns(3, vertical_alignment="bottom", gap="small")
            start_date = edited_work_history_data["Date"].min()
            end_date = edited_work_history_data["Date"].max()
            # Filter the DataFrame based on the selected date range
            df_to_download = edited_work_history_data[
                (edited_work_history_data["Date"] >= start_date) &
                (edited_work_history_data["Date"] <= end_date)
            ]

            if "_id" in df_to_download:
                df_to_download.pop("_id")

            if "employee_id" in df_to_download:
                df_to_download.pop("employee_id")

            # Prepare the Excel file in memory
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_to_download.to_excel(writer, index=False, sheet_name='Sheet1')

            excel_data = output.getvalue()
            with col8:
                st.download_button(
                    label="Download Excel",
                    data=excel_data,
                    file_name=f"{employee_name}_pay_period_{pay_period}_bulldog_office.xlsx",
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    use_container_width=True
                )

            # --- Calculate Summary Metrics ---
            df_to_download = df_to_download.fillna('')

            # Hours expected to work: sum of "Standard Time"
            total_standard = 0.0
            for index, row in df_to_download.iterrows():
                standard_time = row["Standard Time"]
                is_holiday = row["Holiday"]

                if standard_time and standard_time.strip() != "" and (not is_holiday or str(is_holiday).strip() == ""):
                    try:
                        total_standard += hhmm_to_decimal(standard_time)
                    except Exception:
                        pass
                    
            hours_expected = decimal_hours_to_hhmmss(total_standard)

            # Hours worked: sum of "Work Time"
            total_work = 0.0
            for t in df_to_download["Work Time"]:
                if t and t.strip() != "":
                    try:
                        total_work += hhmm_to_decimal(t)
                    except Exception:
                        pass
            hours_worked = decimal_hours_to_hhmmss(total_work)

            consumed_deficit = 0.0

            # Loop over each row in the DataFrame
            for _, row in df_to_download.iterrows():
                # Check if this is a non-holiday row
                if not row["Holiday"] or str(row["Holiday"]).strip() == "":
                    standard_time = hhmm_to_decimal(row["Standard Time"])
                    worked_time = hhmm_to_decimal(row["Work Time"])
                    # Only if the employee worked less than standard time, add the deficit
                    if worked_time < standard_time:
                        consumed_deficit += (standard_time - worked_time)
            # Number of breaks: count of rows where "Break" is not empty and not "00:00"
            breaks_count = df_to_download["Break"].apply(
                lambda x: bool(x and x.strip() != "" and x != "00:00")
            ).sum()

            # Duration of breaks: sum of all valid "Break" values
            total_breaks = 0.0
            for t in df_to_download["Break"]:
                if t and t.strip() != "" and t != "00:00":
                    try:
                        total_breaks += hhmm_to_decimal(t)
                    except Exception:
                        pass
            breaks_duration = decimal_hours_to_hhmmss(total_breaks)

            # Total hours availability: sum of "Daily Total"
            total_daily = 0.0
            for t in df_to_download[" Daily Total"]:
                if t and t.strip() != "":
                    try:
                        total_daily += hhmm_to_decimal(t)
                    except Exception:
                        pass
            total_hours_availability = decimal_hours_to_hhmmss(total_daily)

            # Update column selection and ordering
            desired_columns = ["Date", " Daily Total", "Break", "Day", "Holiday", "Holiday Days", 
                            "Hours Overtime Left", "IN", "OUT", "Standard Time", "Multiplication", "Work Time"]
            df_to_download = df_to_download[desired_columns]

            # --- Build the PDF File with Enhanced Styling ---
            pdf_buffer = BytesIO()
            doc = SimpleDocTemplate(pdf_buffer, pagesize=landscape(A4),
                                    leftMargin=30, rightMargin=30, 
                                    topMargin=60, bottomMargin=40)  # Increased top margin for header

            styles = getSampleStyleSheet()

            # Custom Styles
            header_style = ParagraphStyle(
                'Header',
                parent=styles['Heading1'],
                fontName='Helvetica-Bold',
                fontSize=24,
                textColor=colors.HexColor("#2c3e50"),
                alignment=1,
                spaceAfter=20
            )

            footer_style = ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontName='Helvetica-Oblique',
                fontSize=10,
                textColor=colors.HexColor("#7f8c8d"),
                alignment=2
            )

            # Create header and footer templates
            def add_header_footer(canvas, doc):
                # Header
                canvas.saveState()
                canvas.setFont('Helvetica-Bold', 16)
                canvas.setFillColor(colors.HexColor("#2c3e50"))
                canvas.drawString(40, doc.pagesize[1] - 40, "Bulldog Office - Work Hours Report")
                
                # Footer
                canvas.setFont('Helvetica', 10)
                canvas.setFillColor(colors.HexColor("#7f8c8d"))
                canvas.drawRightString(doc.pagesize[0] - 40, 30, f"Page {doc.page}")
                canvas.restoreState()

            elements = []

            # -- First Page: Enhanced Summary --
            # Resize logo
            logo = Image("https://bulldogsliving.com/img/brand_logo/logo.png", width=200, height=60)
            elements.append(logo)
            elements.append(Spacer(1, 30))

            # Summary Title
            elements.append(Paragraph("WORK HOURS SUMMARY", header_style))
            elements.append(Spacer(1, 30))
            # Summary Table with modern styling
            summary_data = [
                ["Metric", "Value"],
                ["Employee", employee_name],
                ["Pay Period", pay_period],
                ["Hours worked", hours_worked],
                ["Hours expected", hours_expected],
                ["Overtime Balance", df_to_download["Hours Overtime Left"].iloc[-1]],
                ["Remaining Holidays", df_to_download["Holiday Days"].iloc[-1]],
                ["Breaks Taken", f"{breaks_count} (Total: {breaks_duration})"],
                ["Availability", total_hours_availability]
            ]

            summary_table = Table(summary_data, colWidths=[180, 180])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#3498db")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 14),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('BOTTOMPADDING', (0,0), (-1,0), 15),
                ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#ecf0f1")),
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor("#bdc3c7")),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f5f6fa")])
            ]))
            elements.append(summary_table)
            elements.append(PageBreak())

            # -- Data Table Page --
            # Header for data table
            elements.append(Paragraph("DETAILED WORK LOG", header_style))
            elements.append(Spacer(1, 20))

            # Create styled data table
            table_data = [df_to_download.columns.tolist()] + df_to_download.astype(str).values.tolist()
            # Adjust the column widths based on the longest value between the column name and its data
            max_column_widths = [
                max(
                    len(str(col)),  # Length of the column header
                    max(len(str(item)) for item in df_to_download[col].astype(str).values)  # Length of longest value
                ) * 5.3  # Width multiplier (adjust as needed for your font)
                for col in df_to_download.columns
            ]

            # Ensure a minimum width of 40
            max_column_widths = [max(40, width) for width in max_column_widths]

            # Create the table with calculated column widths
            data_table = Table(table_data, repeatRows=1, colWidths=max_column_widths)

            data_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2ecc71")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 9),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#bdc3c7")),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f5f6fa")]),
                ('LEFTPADDING', (0,0), (-1,-1), 5),
                ('RIGHTPADDING', (0,0), (-1,-1), 5),
            ]))
            elements.append(data_table)

            # Build document with header/footer
            doc.build(elements, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
            pdf_data = pdf_buffer.getvalue()
            with col9:
                st.download_button(
                    label="Download PDF",
                    data=pdf_data,
                    file_name=f"{employee_name}_pay_period_{pay_period}_bulldog_office.pdf",
                    mime='application/pdf',
                    use_container_width=True
                )
    
            with col_send_email_btn:
                # Email sending logic
                if st.button("Send Email", use_container_width=True):
                    st.write("Email functionality is not implemented yet.")
                    send_the_pdf_created_in_history_page_to_email(employee_id, pdf_buffer, f"{employee_name}_pay_period_{pay_period}_bulldog_office.pdf", "application/pdf")
                    st.write(employee_id)
if __name__ == "__main__":
    main_work()
