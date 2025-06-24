from datetime import date, datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
import streamlit as st
import io
from io import BytesIO
from utils import *
from streamlit_extras.switch_page_button import switch_page

# ----------------------
# 10. The main Streamlit app
# ----------------------
def main():
    if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
        st.error("You need to log in first.")
        st.session_state["logged_in"] = False
        st.session_state["user_id"] = None
        switch_page("Login")  # Name of your Home.py page (no .py)
        return
    st.title("Timecard Report Uploader")
    
    def reset_file():
        if "edited_data" in st.session_state:
            st.session_state.pop("edited_data")
            st.session_state.pop("pay_period_from")
            st.session_state.pop("pay_period_to")
            st.session_state.pop("employee_name")
            if "selected_employee" in st.session_state:
                st.session_state.pop("selected_employee")

    file_type_choice = st.selectbox(
        "Select the type of file you want to upload",
        ("Select", "Single CSV Upload", "From Bulk Timecard")
    )
    if file_type_choice == "Single CSV Upload":
        uploaded_file = st.file_uploader("Upload your timecard CSV", type=["csv"], on_change=reset_file)
    elif file_type_choice == "From Bulk Timecard":
        all_usernames = get_employees()
        selected_username = st.selectbox("Select Employee", all_usernames)
        if "selected_employee" in st.session_state and st.session_state["selected_employee"] != selected_username:
            employee_id, full_name = get_employee_id(selected_username)
            work_history_asked, first_date, last_date = fetch_employee_temp_work_history(employee_id)
            if work_history_asked.empty == False:
                # Load holiday events from the JSON file.
                calendar_events_for_bulk = load_calendar_events()  # keys are like "2025-01-04", values like "Weekend/Holiday"

                # Convert the keys from string to date objects.
                calendar_events_date_for_bulk = {
                    pd.to_datetime(date_str, format="%Y-%m-%d").date(): event 
                    for date_str, event in calendar_events_for_bulk.items()
                }

                # Map the holiday events onto the DataFrame using the converted keys.
                work_history_asked['Holiday'] = work_history_asked['Date'].map(calendar_events_date_for_bulk)
                st.session_state["edited_data"] = work_history_asked
                st.session_state["pay_period_from"] = first_date
                st.session_state["pay_period_to"] = last_date
            else:
                reset_file()
                st.warning("No temp work history found for the selected employee.")
            st.session_state["employee_name"] = full_name
            st.session_state["selected_employee"] = selected_username
        elif "selected_employee" not in st.session_state:
            employee_id, full_name = get_employee_id(selected_username)
            work_history_asked, first_date, last_date = fetch_employee_temp_work_history(employee_id)
            if work_history_asked.empty == False:
                st.session_state["edited_data"] = work_history_asked
                st.session_state["pay_period_from"] = first_date
                st.session_state["pay_period_to"] = last_date
            else:
                reset_file()
                st.warning("No temp work history found for the selected employee.")
            st.session_state["employee_name"] = full_name
            st.session_state["selected_employee"] = selected_username

        uploaded_file = None
    else:
        uploaded_file = None
    
    if uploaded_file or "edited_data" in st.session_state:
        if not uploaded_file:
            uploaded_df = pd.DataFrame(st.session_state["edited_data"])

            # Convert all columns to string to avoid float-related errors
            uploaded_df = uploaded_df.astype(str)  

            # Create an in-memory file buffer
            file_buffer = io.StringIO()
            uploaded_df.to_csv(file_buffer, index=False)
            pay_period_from = st.session_state["pay_period_from"]
            pay_period_to = st.session_state["pay_period_to"]
            employee_name = st.session_state["employee_name"]
        else:
            file_contents = uploaded_file.getvalue().decode("utf-8")
            file_buffer = io.StringIO(file_contents)
    
            # --- First Read: Extract Header Information ---
            header_df = pd.read_csv(file_buffer, header=None, nrows=3)
            pay_period_str = header_df.iloc[1, 3]  # e.g., "20250101-20250131"
            pay_period_from_str, pay_period_to_str = pay_period_str.split("-")
            pay_period_from = pd.to_datetime(pay_period_from_str, format="%Y%m%d", errors="coerce").date()
            st.session_state["pay_period_from"] = pay_period_from
            pay_period_to = pd.to_datetime(pay_period_to_str, format="%Y%m%d", errors="coerce").date()
            st.session_state["pay_period_to"] = pay_period_to
            employee_name = header_df.iloc[2, 3]  # e.g., "Osman Kocabal (4)"
            st.session_state["employee_name"] = employee_name
    
        # --- Display Header Info in Widgets ---
        st.subheader("Timecard Report")
        col1, col2 = st.columns(2)
        with col1:
            pay_period_from_selected = st.date_input("**Pay Period From:**", value=pay_period_from, disabled=True)
        with col2:
            pay_period_to_selected = st.date_input("**Pay Period To:**", value=pay_period_to, min_value=pay_period_from_selected, disabled=True)
        col13, col14 = st.columns(2)
        with col13:
            employee_name = st.text_input("**Employee Name:**", value=employee_name, disabled=True)
        with col14:
            all_usernames = get_employees(employee_name)
            selected_username = st.selectbox("Selected Employee", all_usernames)
        employee_id, full_name = get_employee_id(selected_username)
        old_work_history, previous_hours_overtime, previous_holiday_hours = fetch_employee_work_history(employee_id)
        latest_hours_overtime = previous_hours_overtime if previous_hours_overtime else old_work_history["Hours Overtime Left"].iloc[-1] if "Hours Overtime Left" in old_work_history and old_work_history["Hours Overtime Left"].iloc[-1] else "00:00"
        col3, col4, colstnhr = st.columns(3)
        with col3:
            holiday_hours = st.text_input("**Holiday Hours**", value="00:00")
            holiday_hours_str = holiday_hours
            holiday_hours = float(hhmm_to_decimal(holiday_hours))

        with col4:
            hours_overtime = st.text_input("**Hours Overtime**", value=latest_hours_overtime)
            hours_overtime_str = hours_overtime
            hours_overtime = int(hhmm_to_decimal(hours_overtime))
                        

        with colstnhr:
            standard_work_hours = st.text_input("**Standard Work Hours**", value="08:00")
            standard_work_hours = int(hhmm_to_decimal(standard_work_hours))

        # colu1, colu2, colu3 = st.columns(3)
        # with colu1:
        #     break_rule_hours = st.text_input("**Break Rule Hour(s)**", value="06:00")
        # with colu2:
        #     break_hours = st.text_input("**Break Hour(s)**", value="00:30")
        # with colu3:
        #     multiplication_input = st.number_input("**Multiplication**", value=1.0)
        break_rule_hours = "06:00"
        break_hours = "00:30"
        multiplication_input = 1.0
    
        # --- Second Read: Extract the Main Data ---
        file_buffer.seek(0)
        data_df = pd.read_csv(file_buffer, skiprows=3, skipfooter=1, engine='python')
        new_cols = list(data_df.columns)
        new_cols[0] = "Day"
        new_cols[1] = "Date"
        data_df.columns = new_cols
        data_df['Date'] = pd.to_datetime(data_df['Date'], format="%Y%m%d", errors="coerce").dt.date
        data_df['Break'] = None
        data_df['Standard Time'] = decimal_hours_to_hhmmss(standard_work_hours)
        data_df['Difference'] = None
        data_df['Difference (Decimal)'] = None
        data_df['Multiplication'] = multiplication_input
        data_df['Hours Overtime Left'] = None 
        data_df['Holiday'] = None
        data_df['Holiday Hours'] = None

        # Load holiday events from the JSON file.
        calendar_events = load_calendar_events()  # keys are like "2025-01-04", values like "Weekend/Holiday"

        # Convert the keys from string to date objects.
        calendar_events_date = {
            pd.to_datetime(date_str, format="%Y-%m-%d").date(): event 
            for date_str, event in calendar_events.items()
        }

        # Map the holiday events onto the DataFrame using the converted keys.
        data_df['Holiday'] = data_df['Date'].map(calendar_events_date)

        # Set multiplication to 2 for Sundays and holidays (but not Saturdays)
        data_df['Multiplication'] = data_df.apply(
            lambda row: 2.0 if (
                (row['Date'] in calendar_events_date and row['Date'].weekday() != 5)  # Holiday but not Saturday
            ) else multiplication_input, 
            axis=1
        )

        # Compute work duration (Daily Total) and adjust Work Time and Break.
        data_df[" Daily Total"] = data_df.apply(
            lambda row: compute_work_duration(row.get("IN", ""), row.get("OUT", "")), axis=1
        )
        data_df["Work Time"], data_df["Break"] = zip(*data_df.apply(
            lambda row: adjust_work_time_and_break(row[" Daily Total"], row.get("Break"), break_rule_hours, break_hours), axis=1
        ))
    
        if "edited_data" not in st.session_state:
            st.session_state["edited_data"] = data_df
    
        edited_data = st.data_editor(
            data=st.session_state["edited_data"],
            num_rows="dynamic",
            key="edited_data_editor"
        )
        col10, col11, col12 = st.columns(3)
        with col10:
            if st.button("Calculate Work Duration", use_container_width=True):
                updated_df = safe_convert_to_df(edited_data).copy()
                updated_df["Standard Time"] = decimal_hours_to_hhmmss(standard_work_hours)
                
                # Set multiplication to 2 for Sundays and holidays (but not Saturdays)
                updated_df['Multiplication'] = updated_df.apply(
                    lambda row: 2.0 if (
                        (row['Date'] in calendar_events_date and row['Date'].weekday() != 5)  # Holiday but not Saturday
                    ) else multiplication_input, 
                    axis=1
                )
                
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

                st.session_state["edited_data"] = updated_df
                st.rerun()

        with col11:
            # --- New: Calculate Holiday Hours Running Balance ---
            if st.button("Calculate Holiday", use_container_width=True):
                df = safe_convert_to_df(edited_data).copy()
                
                # Helper function to ensure the 'Holiday' column has a valid, non-empty value.
                def is_valid_holiday(value):
                    return pd.notnull(value) and str(value).strip() != ''
                
                valid_holiday_mask = df['Holiday'].apply(is_valid_holiday)
                
                # Convert the date objects to strings in "YYYY-MM-DD" format.
                holiday_event_dates = set(
                    df.loc[valid_holiday_mask, 'Date'].apply(lambda d: d.strftime('%Y-%m-%d'))
                )
                
                # Compute running holiday hours using the extracted holiday dates.
                df = compute_running_holiday_hours(df, holiday_event_dates, calendar_events_date, holiday_hours, hours_overtime_str)
                
                st.session_state["edited_data"] = df
                st.success("Holiday hours calculated and updated!")
                st.rerun()
        
        with col12:
            if st.button("Save Data to DB", use_container_width=True):
                updated_df = safe_convert_to_df(edited_data).copy()
                work_history_created = upsert_employee_work_history(updated_df, employee_id)
                if work_history_created["success"] == True:
                    st.success("Successfully Saved Data!")
                    if "selected_employee" in st.session_state:
                        delete_employee_temp_work_history(employee_id)
                    reset_file()

                else:
                    st.error(f"Couldn't save work history: {work_history_created}")

        pay_period = f"{pay_period_from_selected} - {pay_period_to_selected}"

        col7, col8, col9 = st.columns(3, vertical_alignment="bottom", gap="small")
        with col7:
            # Create date inputs for the employee to select a date range.
            # Default values are set to the minimum and maximum dates in the DataFrame.
            start_date, end_date = st.date_input(
                "Select date range:",
                value=[edited_data["Date"].min(), edited_data["Date"].max()]
            )

        # Filter the DataFrame based on the selected date range
        df_to_download = edited_data[
            (edited_data["Date"] >= start_date) &
            (edited_data["Date"] <= end_date)
        ]

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
        desired_columns = ["Date", " Daily Total", "Break", "Day", "Holiday", "Holiday Hours", 
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
        updated_df_pdf = safe_convert_to_df(edited_data).copy()
        # Summary Table with modern styling
        summary_data = [
            ["Metric", "Value"],
            ["Employee", employee_name],
            ["Pay Period", pay_period],
            ["Hours worked", hours_worked],
            ["Hours expected", hours_expected],
            ["Overtime or Undertime Balance", updated_df_pdf["Hours Overtime Left"].iloc[-1]],
            ["Remaining Holiday Hours", updated_df_pdf["Holiday Hours"].iloc[-1]],
            ["Total Sick Days", updated_df_pdf["Holiday"].apply(lambda x: 1 if x == "sick" or x == "Sick" else 0).sum()],
            ["Total Available Time Off", decimal_hours_to_hhmmss(hhmm_to_decimal(updated_df_pdf["Holiday Hours"].iloc[-1]) + hhmm_to_decimal(updated_df_pdf["Hours Overtime Left"].iloc[-1]))]
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
            ) * 4.9  # Width multiplier (adjust as needed for your font)
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
    
if __name__ == "__main__":
    main()
