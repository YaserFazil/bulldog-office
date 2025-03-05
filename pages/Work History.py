import streamlit as st
import pandas as pd
from io import BytesIO
from utils import get_users, get_user_id, fetch_employee_work_history, safe_convert_to_df, upsert_employee_work_history, hhmm_to_decimal, compute_work_duration, adjust_work_time_and_break, compute_time_difference, compute_running_holiday_hours, decimal_hours_to_hhmmss
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
def main_work():
    st.title("Work History Records")
    
    all_usernames = get_users()
    selected_username = st.selectbox("Select Employee", all_usernames)
    
    if selected_username:
        user_id, full_name = get_user_id(selected_username)
        work_history, prev_holiday_hour = fetch_employee_work_history(user_id)
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
            # # Fetch filtered data based on user selection
            work_history, prev_holiday_hour = fetch_employee_work_history(user_id, pay_period_from_selected, pay_period_to_selected)
            st.session_state["prev_holiday_hour"] = prev_holiday_hour
            st.session_state["edited_work_history_data"] = work_history
            st.rerun()
        if "edited_work_history_data" in st.session_state and not st.session_state.get("edited_work_history_data").empty:
            employee_name = st.text_input("**Employee Name:**", value=employee_name, disabled=True)
            col3, col4, col5, col6 = st.columns(4)
            with col3:
                if "Hours Holiday" in st.session_state["edited_work_history_data"]:
                    first_row_holiday = st.session_state["edited_work_history_data"]["Holiday"][0] if "Holiday" in st.session_state["edited_work_history_data"] and st.session_state["edited_work_history_data"]["Holiday"][0] else ""
                    if first_row_holiday == "" or not first_row_holiday or pd.isna(first_row_holiday):  # Check if "Holiday" column is empty
                        first_row_work_time = st.session_state["edited_work_history_data"]["Work Time"][0] if "Work Time" in st.session_state["edited_work_history_data"] and not pd.isna(st.session_state["edited_work_history_data"]["Work Time"][0]) else "00:00"
                        first_row_standard_time = st.session_state["edited_work_history_data"]["Standard Time"][0] if "Standard Time" in st.session_state["edited_work_history_data"] else "00:00"
                        
                        work_time_decimal = hhmm_to_decimal(first_row_work_time)
                        standard_time_decimal = hhmm_to_decimal(first_row_standard_time)
                        if work_time_decimal < standard_time_decimal:
                            # Calculate the difference and add it to "Holiday Hours"
                            st.write(f"Work time: {work_time_decimal}")
                            st.write(f"Standard time: {standard_time_decimal}")
                            diff = standard_time_decimal - work_time_decimal
                            st.write(f"Diff: {diff}")
                            holiday_hours_value = st.session_state["edited_work_history_data"]["Hours Holiday"][0] if "Hours Holiday" in st.session_state["edited_work_history_data"] else "00:00"
                            holiday_hours_decimal = hhmm_to_decimal(holiday_hours_value)
                            st.write(f"First holiday hour: {holiday_hours_value}")

                            holiday_hours_value = holiday_hours_decimal + diff
                            st.write(f"Here is after diff {holiday_hours_value}")
                            holiday_hours = decimal_hours_to_hhmmss(holiday_hours_value)
                        # elif work_time_decimal < standard_time_decimal and st.session_state.get("prev_holiday_hour") is None:
                        #     diff = standard_time_decimal
                        #     holiday_hours_value = st.session_state["edited_work_history_data"]["Hours Holiday"][0] if "Hours Holiday" in st.session_state["edited_work_history_data"] else "00:00"
                        #     holiday_hours_decimal = hhmm_to_decimal(holiday_hours_value)
                        #     holiday_hours_value = holiday_hours_decimal + diff
                        #     holiday_hours = f"{int(holiday_hours_value)}:{int((holiday_hours_value - int(holiday_hours_value)) * 60):02d}"
                        else:
                            holiday_hours = st.session_state["edited_work_history_data"]["Hours Holiday"][0] if "Hours Holiday" in st.session_state["edited_work_history_data"] else "00:00"
                    else:
                        holiday_hours = st.session_state["edited_work_history_data"]["Hours Holiday"][0] if "Hours Holiday" in st.session_state["edited_work_history_data"] else "00:00"
                else:
                    holiday_hours = work_history["Hours Holiday"][0] if "Hours Holiday" in work_history else "00:00"
                # Holiday Hours: initial total holiday entitlement for the year.
                holiday_hours = st.text_input("**Holiday Hours**", value=holiday_hours)
                holiday_hours_str = holiday_hours
                holiday_hours = int(hhmm_to_decimal(holiday_hours))
            with col4:
                standard_work_hours = st.text_input("**Standard Work Hours**", value="04:00")
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
                    "Holiday",
                    "Hours Holiday",
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
                        lambda row: compute_time_difference(row.get("Work Time", ""), row.get("Standard Time", "")),
                        axis=1
                    )

                    st.session_state["edited_work_history_data"] = updated_df
                    st.rerun()
            
            with col2:
                # --- New: Calculate Holiday Hours Running Balance ---
                if st.button("Calculate Holiday Hours", use_container_width=True):
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
                    df = compute_running_holiday_hours(df, holiday_hours, holiday_event_dates)
                    
                    st.session_state["edited_work_history_data"] = df
                    st.success("Holiday hours calculated and updated!")
                    st.rerun()
            
            with col3:
                # Implement actual save logic here
                if st.button("Save Changes", use_container_width=True):
                    # user_id, full_name = get_user_id(selected_username)
                    updated_df = safe_convert_to_df(edited_work_history_data).copy()
                    work_history_created = upsert_employee_work_history(updated_df, user_id)
                    if work_history_created["success"] == True:
                        st.success("Successfully Saved Data!")
                        
                        st.session_state["edited_work_history_data"], prev_holiday_hour = fetch_employee_work_history(user_id)
                        st.rerun()
                    else:
                        st.error(f"Couldn't save work history: {work_history_created}")

            # ------------------------
            # Export Options
            # ------------------------
            st.subheader("Export Records")
            pay_period = f"{pay_period_from_selected} - {pay_period_to_selected}"

            col8, col9 = st.columns(2, vertical_alignment="bottom", gap="small")
            # with col7:
            #     # Create date inputs for the user to select a date range.
            #     # Default values are set to the minimum and maximum dates in the DataFrame.
            #     start_date, end_date = st.date_input(
            #         "Select date range:",
            #         value=[edited_work_history_data["Date"].min(), edited_work_history_data["Date"].max()]
            #     )
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

            # Consumed holiday hours (in decimal) are simply the sum of deficits on non-holiday days.
            holiday_consumed = decimal_hours_to_hhmmss(consumed_deficit)

            # The last row's "Hours Holiday" column already gives you the holiday balance on the holiday day.
            if not df_to_download.empty and not df_to_download["Hours Holiday"].empty:
                holiday_hours_left_str = str(df_to_download["Hours Holiday"].iloc[-1]).strip()
            else:
                holiday_hours_left_str = "00:00"
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
            
            # Build a summary table with two columns: Metric and Value.
            summary_data = [
                ["Metric", "Value"],
                ["Employee", employee_name],
                ["Pay Period", pay_period],
                ["Hours worked", hours_worked],
                ["Hours expected to work", hours_expected],
                ["Holiday hours consumed", f"{holiday_consumed} / {holiday_hours_str}"],
                ["Holiday hours left", holiday_hours_left_str],
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
    main_work()
