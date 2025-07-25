import streamlit as st
import pandas as pd
from io import BytesIO
from utils import get_employees, get_employee_id, fetch_employee_work_history, safe_convert_to_df, upsert_employee_work_history, hhmm_to_decimal, compute_work_duration, adjust_work_time_and_break, compute_time_difference, compute_running_holiday_hours, decimal_hours_to_hhmmss, load_calendar_events, send_the_pdf_created_in_history_page_to_email
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from streamlit_extras.switch_page_button import switch_page
def main_work():
    if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
        st.error("You need to log in first.")
        st.session_state["logged_in"] = False
        st.session_state["user_id"] = None
        switch_page("Login")  # Name of your Home.py page (no .py)
        return
    st.title("Work History Records")
    
    # Add CSS for highlighting changed cells
    st.markdown("""
    <style>
    .changed-cell {
        background-color: #fff3cd !important;
        border: 2px solid #ffc107 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    all_usernames = get_employees()
    selected_username = st.selectbox("Select Employee", all_usernames)
    
    if selected_username:
        employee_id, full_name = get_employee_id(selected_username)
        work_history, previous_hours_overtime, previous_holiday_hours = fetch_employee_work_history(employee_id)
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
            work_history, previous_hours_overtime, previous_holiday_hours = fetch_employee_work_history(employee_id, pay_period_from_selected, pay_period_to_selected)
            latest_holiday_hours = previous_holiday_hours if previous_holiday_hours else work_history["Holiday Hours"].iloc[0] if "Holiday Hours" in work_history and work_history["Holiday Hours"].iloc[0] else "00:00"
            latest_hours_overtime_left = (
                previous_hours_overtime
                if previous_hours_overtime is not None
                else work_history["Hours Overtime Left"].iloc[0]
                if "Hours Overtime Left" in work_history and work_history["Hours Overtime Left"].iloc[0] is not None
                else "00:00"
            )

            st.session_state["latest_holiday_hours_left"] = latest_holiday_hours
            st.session_state["latest_hours_overtime_left"] = latest_hours_overtime_left
            st.session_state["edited_work_history_data"] = work_history
            # Reset original data for new period
            if "original_work_history_data" in st.session_state:
                st.session_state.pop("original_work_history_data")
            st.rerun()
        if "edited_work_history_data" in st.session_state and not st.session_state.get("edited_work_history_data").empty:
            employee_name = st.text_input("**Employee Name:**", value=employee_name, disabled=True)
            holiday_hours_col, hours_overtime_col, col4 = st.columns(3)
            with holiday_hours_col:
                holiday_hours = st.text_input("**Holiday Hours Left:**", value=st.session_state["latest_holiday_hours_left"])
                holiday_hours_str = holiday_hours
                holiday_hours = float(hhmm_to_decimal(holiday_hours))
            with hours_overtime_col:
                hours_overtime = st.text_input("**Hours Overtime:**", value=st.session_state["latest_hours_overtime_left"])
                hours_overtime_str = hours_overtime
                hours_overtime = int(hhmm_to_decimal(hours_overtime))
                       
            with col4:
                standard_work_hours = st.text_input("**Standard Work Hours**", value="08:00")
                standard_work_hours_str = standard_work_hours
                standard_work_hours = int(hhmm_to_decimal(standard_work_hours))
            # with col5:
            #     break_rule_hours = st.text_input("**Break Rule Hour(s)**", value="06:00")
            # with col6:
            #     break_hours = st.text_input("**Break Hour(s)**", value="00:30")
            break_rule_hours = "06:00"
            break_hours = "00:30"


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
                    "Holiday Hours",
                    "Hours Overtime Left",
                    "employee_id",
                    "_id"
                ],
                disabled=["_id", "employee_id"],
                key="edited_work_history_data_editor"
            )
            
            # Process yellow indicators based on manual_modifications field
            current_data = edited_work_history_data
            
            # Store original data for comparison if not already stored
            if "original_work_history_data" not in st.session_state:
                st.session_state["original_work_history_data"] = current_data.copy()
            
            # Get the original data for comparison
            original_data = st.session_state.get("original_work_history_data", current_data)
            
            # Helper function to normalize values for comparison
            def normalize_value(val):
                if pd.isna(val) or val is None or str(val).strip() == "" or str(val).lower() in ["nan", "none", "null"]:
                    return ""
                return str(val).strip()
            
            # Determine the correct Note column name
            note_column = None
            if " Note" in current_data.columns:
                note_column = " Note"
            elif "Note" in current_data.columns:
                note_column = "Note"
            
            
            # Create a DataFrame to track which cells have been manually modified
            changed_cells = pd.DataFrame(False, index=current_data.index, columns=current_data.columns)
            
            # Check for manual modifications and add yellow styling
            for row_idx, (_, row) in enumerate(current_data.iterrows(), start=1):  # start=1 because row 0 is header
                for col_name in current_data.columns:
                    if col_name in current_data.columns:
                        col_idx = current_data.columns.get_loc(col_name)
                        current_val = normalize_value(row[col_name])
                        
                        # Check if this cell was manually modified
                        is_modified = False
                        
                        # First check if manual_modifications field exists and has data
                        if 'manual_modifications' in current_data.columns:
                            # Find the corresponding row in current_data
                            matching_row = current_data[
                                (current_data['Date'] == row['Date']) & 
                                (current_data['Day'] == row['Day'])
                            ]
                            if not matching_row.empty:
                                manual_mods = matching_row.iloc[0]['manual_modifications']
                                if pd.notna(manual_mods) and str(manual_mods).strip() != "":
                                    modified_cols = [col.strip() for col in str(manual_mods).split(",")]
                                    if col_name in modified_cols:
                                        is_modified = True
                        
                        # Fallback: compare with original data if manual_modifications not available
                        if not is_modified and col_name in original_data.columns:
                            # Find the corresponding row in original_data
                            matching_original = original_data[
                                (original_data['Date'] == row['Date']) & 
                                (original_data['Day'] == row['Day'])
                            ]
                            if not matching_original.empty:
                                original_val = normalize_value(matching_original.iloc[0][col_name])
                                if current_val != original_val:
                                    is_modified = True
                        
                        if is_modified:
                            changed_cells.loc[row_idx - 1, col_name] = True
            
            # Apply styling to highlight changed cells
            if not changed_cells.empty and changed_cells.any().any():
                # Create a styled DataFrame for display
                styled_data = current_data.copy()
                
                # Add a visual indicator for changed cells
                columns_to_highlight = ["IN", "OUT"]
                if note_column:
                    columns_to_highlight.append(note_column)
                
                for col in columns_to_highlight:
                    if col in changed_cells.columns:
                        changed_mask = changed_cells[col]
                        
                        # Only add yellow indicator if the cell actually has a value
                        for idx in changed_mask[changed_mask].index:
                            current_val = styled_data.loc[idx, col]
                            if (pd.isna(current_val) or current_val is None or 
                                str(current_val).strip() == "" or 
                                str(current_val).lower() in ["nan", "none", "null"]):
                                styled_data.loc[idx, col] = "🟡 (empty)"
                            else:
                                styled_data.loc[idx, col] = "🟡 " + str(current_val)
                
                # Use the same column order as the data editor
                column_order = [
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
                    "Holiday Hours",
                    "Hours Overtime Left",
                    "employee_id",
                    "_id"
                ]
                
                # Reorder the styled data to match the data editor
                styled_data = styled_data[column_order]
                
                # Display the styled data
                st.dataframe(
                    styled_data,
                    use_container_width=True,
                    hide_index=False
                )
                
                # Show legend
                st.info("🟡 Yellow indicator shows cells that have been manually modified from the original data")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("Calculate Work Duration", use_container_width=True):
                    # Use the data from the editor, not session state
                    updated_df = safe_convert_to_df(edited_work_history_data).copy()
                    
                    # Set multiplication to 2 for Sundays and holidays (but not Saturdays)
                    calendar_events = load_calendar_events()  # keys are like "2025-01-04", values like "Weekend/Holiday"
                    calendar_events_date = {
                        pd.to_datetime(date_str, format="%Y-%m-%d").date(): event 
                        for date_str, event in calendar_events.items()
                    }
                    updated_df['Multiplication'] = updated_df.apply(
                        lambda row: 2.0 if (
                            (row['Date'] in calendar_events_date and row['Date'].weekday() != 5)  # Holiday but not Saturday
                        ) else 1.0, 
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
                    
                    # Preserve manual_modifications field from the editor data
                    if 'manual_modifications' in edited_work_history_data.columns:
                        updated_df['manual_modifications'] = edited_work_history_data['manual_modifications']
                    
                    # Now update session state
                    st.session_state["edited_work_history_data"] = updated_df
                    st.rerun()
            
            with col2:
                # --- New: Calculate Holiday Hours Running Balance ---
                if st.button("Calculate Holiday", use_container_width=True):
                    # Use the data from the editor, not session state
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
                    df = compute_running_holiday_hours(df, holiday_event_dates, calendar_events_date, holiday_hours, hours_overtime_str)
                    
                    # Preserve manual_modifications field from the editor data
                    if 'manual_modifications' in edited_work_history_data.columns:
                        df['manual_modifications'] = edited_work_history_data['manual_modifications']
                    
                    # Now update session state
                    st.session_state["edited_work_history_data"] = df
                    st.success("Holiday hours calculated and updated!")
                    st.rerun()
            
            with col3:
                # Implement actual save logic here
                if st.button("Save Changes", use_container_width=True):
                    # Use the data from the editor, not session state
                    updated_df = safe_convert_to_df(edited_work_history_data).copy()
                    work_history_created = upsert_employee_work_history(updated_df, employee_id)
                    if work_history_created["success"] == True:
                        st.success("Successfully Saved Data!")
                        
                        st.session_state["edited_work_history_data"], previous_hours_overtime, previous_holiday_hours = fetch_employee_work_history(employee_id)
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
            desired_columns = ["Date", " Daily Total", "Break", "Day", "Holiday", "Holiday Hours", 
                            "Hours Overtime Left", "IN", "OUT", "Standard Time", "Multiplication", "Work Time"]
            df_to_download = df_to_download[desired_columns]

            # Helper function to normalize values for comparison (for PDF)
            def normalize_value_pdf(val):
                if pd.isna(val) or val is None or str(val).strip() == "" or str(val).lower() in ["nan", "none", "null"]:
                    return ""
                return str(val).strip()

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
                ["Overtime or Undertime Balance", df_to_download["Hours Overtime Left"].iloc[-1]],
                ["Remaining Holiday Hours", df_to_download["Holiday Hours"].iloc[-1]],
                ["Total Sick Days", df_to_download["Holiday"].apply(lambda x: 1 if x == "sick" or x == "Sick" else 0).sum()],
                ["Total Available Time Off", decimal_hours_to_hhmmss(hhmm_to_decimal(df_to_download["Holiday Hours"].iloc[-1]) + hhmm_to_decimal(df_to_download["Hours Overtime Left"].iloc[-1]))]
            ]

            # Calculate Total Available Time Off in Days
            total_available_hours = hhmm_to_decimal(df_to_download["Holiday Hours"].iloc[-1]) + hhmm_to_decimal(df_to_download["Hours Overtime Left"].iloc[-1])
            standard_work_hours_per_day = hhmm_to_decimal(standard_work_hours_str)  # Convert "08:00" to decimal hours
            total_available_days = total_available_hours / standard_work_hours_per_day if standard_work_hours_per_day > 0 else 0
            
            # Add the days calculation to the summary
            summary_data.append(["Total Available Time Off (Days)", f"{total_available_days:.1f} days"])

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

            # Add legend for yellow indicators
            legend_style = ParagraphStyle(
                'Legend',
                parent=styles['Normal'],
                fontName='Helvetica',
                fontSize=10,
                textColor=colors.HexColor("#2c3e50"),
                alignment=0,
                spaceAfter=10
            )
            elements.append(Paragraph("Note: Cells with yellow background indicate manually modified data from the original records.", legend_style))
            elements.append(Spacer(1, 10))

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

            # Prepare styling for yellow indicators
            table_style = [
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2ecc71")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 9),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#bdc3c7")),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f5f6fa")]),
                ('LEFTPADDING', (0,0), (-1,-1), 5),
                ('RIGHTPADDING', (0,0), (-1,-1), 5),
            ]

            # Add yellow background for manually modified cells
            # Use the current data from the editor for accurate modification tracking
            current_data_for_pdf = edited_work_history_data
            
            # Determine the correct Note column name
            note_column = None
            if " Note" in df_to_download.columns:
                note_column = " Note"
            elif "Note" in df_to_download.columns:
                note_column = "Note"
            
            # Columns to check for modifications
            columns_to_check = ["IN", "OUT"]
            if note_column:
                columns_to_check.append(note_column)
            
            # Get the original data for comparison
            original_data = st.session_state.get("original_work_history_data", current_data_for_pdf)
            
            # Check for manual modifications and add yellow styling
            for row_idx, (_, row) in enumerate(df_to_download.iterrows(), start=1):  # start=1 because row 0 is header
                for col_name in columns_to_check:
                    if col_name in df_to_download.columns:
                        col_idx = df_to_download.columns.get_loc(col_name)
                        current_val = normalize_value_pdf(row[col_name])
                        
                        # Check if this cell was manually modified
                        is_modified = False
                        
                        # First check if manual_modifications field exists and has data
                        if 'manual_modifications' in current_data_for_pdf.columns:
                            # Find the corresponding row in current_data_for_pdf
                            matching_row = current_data_for_pdf[
                                (current_data_for_pdf['Date'] == row['Date']) & 
                                (current_data_for_pdf['Day'] == row['Day'])
                            ]
                            if not matching_row.empty:
                                manual_mods = matching_row.iloc[0]['manual_modifications']
                                if pd.notna(manual_mods) and str(manual_mods).strip() != "":
                                    modified_cols = [col.strip() for col in str(manual_mods).split(",")]
                                    if col_name in modified_cols:
                                        is_modified = True
                        
                        # Fallback: compare with original data if manual_modifications not available
                        if not is_modified and col_name in original_data.columns:
                            # Find the corresponding row in original_data
                            matching_original = original_data[
                                (original_data['Date'] == row['Date']) & 
                                (original_data['Day'] == row['Day'])
                            ]
                            if not matching_original.empty:
                                original_val = normalize_value_pdf(matching_original.iloc[0][col_name])
                                if current_val != original_val:
                                    is_modified = True
                        
                        if is_modified:
                            table_style.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.HexColor("#fff3cd")))
                            table_style.append(('GRID', (col_idx, row_idx), (col_idx, row_idx), 2, colors.HexColor("#ffc107")))

            data_table.setStyle(TableStyle(table_style))
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
