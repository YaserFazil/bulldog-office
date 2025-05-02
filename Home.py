from datetime import date, datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
import streamlit as st
import io
from io import BytesIO
from utils import *
# ----------------------
# 10. The main Streamlit app
# ----------------------
def main():
    st.title("Timecard Report Uploader")
    
    def reset_file():
        if "edited_data" in st.session_state:
            st.session_state.pop("edited_data")
            st.session_state.pop("pay_period_from")
            st.session_state.pop("pay_period_to")
            st.session_state.pop("employee_name")
            if "selected_user" in st.session_state:
                st.session_state.pop("selected_user")

    file_type_choice = st.selectbox(
        "Select the type of file you want to upload",
        ("Select", "Single CSV Upload", "From Bulk Timecard")
    )
    if file_type_choice == "Single CSV Upload":
        uploaded_file = st.file_uploader("Upload your timecard CSV", type=["csv"], on_change=reset_file)
    elif file_type_choice == "From Bulk Timecard":
        all_usernames = get_users()
        selected_username = st.selectbox("Select Employee", all_usernames)
        if "selected_user" in st.session_state and st.session_state["selected_user"] != selected_username:
            user_id, full_name = get_user_id(selected_username)
            work_history_asked, first_date, last_date = fetch_employee_temp_work_history(user_id)
            if work_history_asked.empty == False:
                st.session_state["edited_data"] = work_history_asked
                st.session_state["pay_period_from"] = first_date
                st.session_state["pay_period_to"] = last_date
            else:
                reset_file()
                st.warning("No temp work history found for the selected employee.")
            st.session_state["employee_name"] = full_name
            st.session_state["selected_user"] = selected_username
        elif "selected_user" not in st.session_state:
            user_id, full_name = get_user_id(selected_username)
            work_history_asked, first_date, last_date = fetch_employee_temp_work_history(user_id)
            if work_history_asked.empty == False:
                st.session_state["edited_data"] = work_history_asked
                st.session_state["pay_period_from"] = first_date
                st.session_state["pay_period_to"] = last_date
            else:
                reset_file()
                st.warning("No temp work history found for the selected employee.")
            st.session_state["employee_name"] = full_name
            st.session_state["selected_user"] = selected_username

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
            all_usernames = get_users(employee_name)
            selected_username = st.selectbox("Selected Employee", all_usernames)
        user_id, full_name = get_user_id(selected_username)
        old_work_history, previous_hours_overtime, previous_holiday_days = fetch_employee_work_history(user_id)
        latest_holiday_day = previous_holiday_days if previous_holiday_days else int(old_work_history["Holiday Days"].iloc[-1]) if "Holiday Days" in old_work_history and old_work_history["Holiday Days"].iloc[-1] else int(0)
        latest_hours_overtime = previous_hours_overtime if previous_hours_overtime else old_work_history["Hours Overtime Left"].iloc[-1] if "Hours Overtime Left" in old_work_history and old_work_history["Hours Overtime Left"].iloc[-1] else "00:00"
        col3, col4, colstnhr = st.columns(3)
        with col3:
            holiday_days = st.number_input("**Holiday Days**", value=latest_holiday_day)

        with col4:
            hours_overtime = st.text_input("**Hours Overtime**", value=latest_hours_overtime)
            hours_overtime_str = hours_overtime
            hours_overtime = int(hhmm_to_decimal(hours_overtime))
                        

        with colstnhr:
            standard_work_hours = st.text_input("**Standard Work Hours**", value="08:00")
            standard_work_hours = int(hhmm_to_decimal(standard_work_hours))

        colu1, colu2, colu3 = st.columns(3)
        with colu1:
            break_rule_hours = st.text_input("**Break Rule Hour(s)**", value="06:30")
        with colu2:
            break_hours = st.text_input("**Break Hour(s)**", value="00:30")
        with colu3:
            multiplication_input = st.number_input("**Multiplication**", value=1.0)

    
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
        data_df['Holiday Days'] = None

        # Load holiday events from the JSON file.
        calendar_events = load_calendar_events()  # keys are like "2025-01-04", values like "Weekend/Holiday"

        # Convert the keys from string to date objects.
        calendar_events_date = {
            pd.to_datetime(date_str, format="%Y-%m-%d").date(): event 
            for date_str, event in calendar_events.items()
        }

        # Map the holiday events onto the DataFrame using the converted keys.
        data_df['Holiday'] = data_df['Date'].map(calendar_events_date)

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
                df = compute_running_holiday_hours(df, holiday_event_dates, calendar_events_date, holiday_days, hours_overtime_str)
                
                st.session_state["edited_data"] = df
                st.success("Holiday hours calculated and updated!")
                st.rerun()
        
        with col12:
            if st.button("Save Data to DB", use_container_width=True):
                updated_df = safe_convert_to_df(edited_data).copy()
                work_history_created = upsert_employee_work_history(updated_df, user_id)
                if work_history_created["success"] == True:
                    st.success("Successfully Saved Data!")
                    if "selected_user" in st.session_state:
                        delete_employee_temp_work_history(user_id)
                    reset_file()

                else:
                    st.error(f"Couldn't save work history: {work_history_created}")

        pay_period = f"{pay_period_from_selected} - {pay_period_to_selected}"

        col7, col8, col9 = st.columns(3, vertical_alignment="bottom", gap="small")
        with col7:
            # Create date inputs for the user to select a date range.
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

        # --- Build the PDF File ---

        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=landscape(A4),
                                leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()

        # Create custom styles for the summary page.
        summary_title_style = ParagraphStyle(
            'SummaryTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=30,
            textColor=colors.darkblue,
            alignment=1,  # center alignment
            spaceAfter=20
        )

        summary_text_style = ParagraphStyle(
            'SummaryText',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=14,
            textColor=colors.black,
            leading=18,
            spaceAfter=12
        )
        elements = []

        # -- First Page: Summary --

        # -- First Page: Customized Summary --

        # Add a logo
        elements.append(Image("https://bulldogsliving.com/img/brand_logo/logo.png"))
        elements.append(Spacer(1, 20))


        # Add a title with the custom style.
        elements.append(Paragraph("Work Hours Summary", summary_title_style))
        elements.append(Spacer(1, 20))
        updated_df_pdf = safe_convert_to_df(edited_data).copy()
        
        # Build a summary table with two columns: Metric and Value.
        summary_data = [
            ["Metric", "Value"],
            ["Employee", employee_name],
            ["Pay Period", pay_period],
            ["Hours worked", hours_worked],
            ["Hours expected to work", hours_expected],
            ["Hours Overtime", updated_df_pdf["Hours Overtime Left"].iloc[-1]],
            ["Holiday Days Left", updated_df_pdf["Holiday Days"].iloc[-1]],
            ["Number of breaks", str(breaks_count)],
            ["Duration of breaks", breaks_duration],
            ["Total hours availability", total_hours_availability]
        ]

        summary_table = Table(summary_data, colWidths=[220, 150])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 16),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        elements.append(summary_table)
        elements.append(PageBreak())

        # -- Next Pages: Full Data Table --

        # Convert DataFrame to a list-of-lists.
        # (Converting all values to string for display purposes.)
        table_data = [df_to_download.columns.tolist()] + df_to_download.astype(str).values.tolist()

        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.50, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        elements.append(table)

        doc.build(elements)
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
