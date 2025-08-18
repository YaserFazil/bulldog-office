import streamlit as st
import pandas as pd
from io import BytesIO
from utils import get_employees, get_employee_id, fetch_employee_work_history, safe_convert_to_df, upsert_employee_work_history, hhmm_to_decimal, compute_work_duration, adjust_work_time_and_break, compute_time_difference, compute_running_holiday_hours, decimal_hours_to_hhmmss, load_calendar_events, send_the_pdf_created_in_history_page_to_email, fill_missing_days_in_work_history, calculate_absence_hours
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
    
    # Add documentation link
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("""
        <div style="background-color: #e3f2fd; padding: 10px; border-radius: 5px; border-left: 4px solid #2196f3; margin-bottom: 20px;">
            <strong>📚 Need help?</strong> Check out our Documentation & User Guides for detailed instructions on work history and absence tracking.
        </div>
        """, unsafe_allow_html=True)
    with col2:
        if st.button("📚 View Documentation", use_container_width=True):
            switch_page("documentation")
    
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
        
        # Add Fill Missing Days functionality
        st.markdown("---")
        st.markdown("### 📅 Absence Tracking Tools")
        st.info("💡 **Tip**: Use these tools to add missing days and track employee absences like vacation, sick leave, etc.")
        
        col_fill1, col_fill2, col_fill3, col_debug = st.columns(4)
        with col_fill1:
            fill_missing_days = st.button("🔧 Fill Missing Days", help="Add placeholder entries for days without work records to enable absence tracking")
        with col_fill2:
            absence_type = st.selectbox(
                "Absence Type for Empty Days",
                ["", "vacation", "sick", "personal", "unpaid", "holiday", "other"],
                help="Select the type of absence to apply to empty days"
            )
        with col_fill3:
            apply_absence = st.button("✅ Apply Absence Type", help="Apply the selected absence type to all empty days")
        with col_debug:
            debug_info = st.button("🐛 Debug Info", help="Show debug information to help troubleshoot issues")
        
        # Debug information
        if debug_info:
            st.markdown("### 🐛 Debug Information")
            if "edited_work_history_data" in st.session_state:
                data = st.session_state["edited_work_history_data"]
                st.write(f"**Data shape:** {data.shape}")
                st.write(f"**Columns:** {list(data.columns)}")
                if not data.empty and 'Date' in data.columns:
                    st.write(f"**Date range:** {data['Date'].min()} to {data['Date'].max()}")
                    st.write(f"**Total days:** {len(data)}")
                else:
                    st.write("**No date data available**")
            else:
                st.write("**No work history data in session**")
        
        # Absence type explanations
        if absence_type:
            absence_explanations = {
                "vacation": "🏖️ **Vacation**: Paid time off, counts toward holiday hours",
                "sick": "🏥 **Sick Leave**: Illness-related absence, may have different pay rules",
                "personal": "👤 **Personal Leave**: Personal time off, may be paid or unpaid",
                "unpaid": "❌ **Unpaid Leave**: No pay, no hours counted",
                "holiday": "🎉 **Holiday**: Company or public holiday",
                "other": "📝 **Other**: Miscellaneous absence type"
            }
            if absence_type in absence_explanations:
                st.info(absence_explanations[absence_type])
        
        if period_loaded:
            # # Fetch filtered data based on employee selection
            work_history, previous_hours_overtime, previous_holiday_hours = fetch_employee_work_history(
                employee_id, 
                pay_period_from_selected, 
                pay_period_to_selected,
                fill_missing_days=True  # Automatically fill missing days when loading a period
            )
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
            # Store the selected date range for use by other functions
            st.session_state["selected_start_date"] = pay_period_from_selected
            st.session_state["selected_end_date"] = pay_period_to_selected
            # Reset original data for new period
            if "original_work_history_data" in st.session_state:
                st.session_state.pop("original_work_history_data")
            st.rerun()
        
        # Handle Fill Missing Days functionality
        if fill_missing_days and "edited_work_history_data" in st.session_state:
            try:
                with st.spinner("Filling missing days..."):
                    current_data = st.session_state["edited_work_history_data"]
                    
                    # Debug: Show current data info
                    st.write(f"Current data shape: {current_data.shape}")
                    st.write(f"Current data columns: {list(current_data.columns)}")
                    
                    # Use the selected date range from session state
                    if "selected_start_date" in st.session_state and "selected_end_date" in st.session_state:
                        start_date = st.session_state["selected_start_date"]
                        end_date = st.session_state["selected_end_date"]
                        st.write(f"Using selected date range: {start_date} to {end_date}")
                    elif not current_data.empty and 'Date' in current_data.columns:
                        start_date = current_data['Date'].min()
                        end_date = current_data['Date'].max()
                        st.write(f"Using existing data range: {start_date} to {end_date}")
                    else:
                        st.error("No date range available. Please select a date range first.")
                        return
                    
                    st.info(f"Filling missing days from {start_date} to {end_date}")
                    
                    # Test the function with the full selected date range
                    test_result = fill_missing_days_in_work_history(
                        current_data, 
                        start_date=start_date, 
                        end_date=end_date,
                        employee_id=employee_id
                    )
                    
                    st.write(f"Test result shape: {test_result.shape if test_result is not None else 'None'}")
                    if test_result is not None:
                        st.write(f"Test result columns: {list(test_result.columns)}")
                        st.write(f"Holiday column exists: {'Holiday' in test_result.columns}")
                    
                    if test_result is not None and not test_result.empty:
                        st.session_state["edited_work_history_data"] = test_result
                        added_days = len(test_result) - len(current_data)
                        st.success(f"✅ Added {added_days} missing days to the work history!")
                        st.rerun()
                    else:
                        st.error("Failed to fill missing days. Please try again.")
            except Exception as e:
                st.error(f"Error filling missing days: {str(e)}")
                import traceback
                st.error(f"Full traceback: {traceback.format_exc()}")
                st.info("Please ensure you have loaded a work history period first.")
        
        # Handle Apply Absence Type functionality
        if apply_absence and absence_type and "edited_work_history_data" in st.session_state:
            with st.spinner("Applying absence type..."):
                current_data = st.session_state["edited_work_history_data"].copy()
                standard_hours = standard_work_hours_str if 'standard_work_hours_str' in locals() else "08:00"
                
                # Apply absence type only to new records (not existing DB records)
                modified_count = 0
                for idx, row in current_data.iterrows():
                    # Only modify if it's a new record (not from DB) and has no IN/OUT times
                    is_new = row.get('is_new_record', False)
                    has_no_times = pd.isna(row['IN']) or row['IN'] is None or str(row['IN']).strip() == ''
                    
                    if is_new and has_no_times:
                        work_time, note = calculate_absence_hours(absence_type, standard_hours)
                        current_data.at[idx, 'Work Time'] = work_time
                        current_data.at[idx, ' Note'] = note
                        current_data.at[idx, 'Holiday'] = absence_type
                        
                        # Recalculate Difference and Difference (Decimal) based on new work time
                        standard_time = str(current_data.at[idx, 'Standard Time'])
                        
                        try:
                            diff_str = compute_time_difference(work_time, standard_time, absence_type, default=True)
                            diff_decimal = compute_time_difference(work_time, standard_time, absence_type, default=False)
                            
                            if diff_str is not None:
                                current_data.at[idx, 'Difference'] = diff_str
                            if diff_decimal is not None:
                                current_data.at[idx, 'Difference (Decimal)'] = diff_decimal
                        except Exception:
                            current_data.at[idx, 'Difference'] = '00:00'
                            current_data.at[idx, 'Difference (Decimal)'] = 0.0
                        
                        modified_count += 1
                
                st.session_state["edited_work_history_data"] = current_data
                if modified_count > 0:
                    st.success(f"✅ Applied '{absence_type}' absence type to {modified_count} new days!")
                else:
                    st.info(f"ℹ️ No new days found to apply '{absence_type}' absence type. Existing database records were not modified.")
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
                "Holiday": st.column_config.TextColumn(
                    "Holiday",
                    help="Holiday/absence type for this day (auto-filled from calendar or manually entered)"
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
                disabled=["_id", "employee_id", "is_new_record"],
                hide_index=True,
                use_container_width=True,
                key="edited_work_history_data_editor"
            )
            
            # Display absence summary
            if not edited_work_history_data.empty:
                st.markdown("---")
                st.markdown("### 📊 Absence Summary")
                
                # Count absence types
                absence_counts = edited_work_history_data['Holiday'].value_counts()
                total_days = len(edited_work_history_data)
                work_days = len(edited_work_history_data[edited_work_history_data['IN'].notna() & (edited_work_history_data['IN'] != '')])
                absence_days = total_days - work_days
                
                col_sum1, col_sum2, col_sum3 = st.columns(3)
                with col_sum1:
                    st.metric("Total Days", total_days)
                with col_sum2:
                    st.metric("Work Days", work_days)
                with col_sum3:
                    st.metric("Absence Days", absence_days)
                
                # Show absence breakdown
                if not absence_counts.empty:
                    st.markdown("**Absence Breakdown:**")
                    for absence_type, count in absence_counts.items():
                        if absence_type and str(absence_type).strip() != '':
                            absence_icons = {
                                "vacation": "🏖️",
                                "sick": "🏥", 
                                "personal": "👤",
                                "unpaid": "❌",
                                "holiday": "🎉",
                                "weekend": "📅",
                                "other": "📝"
                            }
                            icon = absence_icons.get(absence_type, "📋")
                            st.write(f"{icon} {absence_type.title()}: {count} days")
            
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
                    try:
                        # Use the data from the editor, not session state
                        # Load holiday events from the JSON file.
                        calendar_events = load_calendar_events()  # keys are like "2025-01-04", values like "Weekend/Holiday"

                        # Convert the keys from string to date objects.
                        calendar_events_date = {
                            pd.to_datetime(date_str, format="%Y-%m-%d").date(): event 
                            for date_str, event in calendar_events.items()
                        }
                        df = safe_convert_to_df(edited_work_history_data).copy()
                        
                        # Clean the data for calculation - ensure all required fields exist and have proper values
                        required_fields = ['Work Time', 'Standard Time', 'Difference (Decimal)', 'Multiplication', 'Difference']
                        for field in required_fields:
                            if field not in df.columns:
                                if field == 'Work Time':
                                    df[field] = '00:00'
                                elif field == 'Standard Time':
                                    df[field] = '08:00'
                                elif field == 'Difference (Decimal)':
                                    df[field] = 0.0
                                elif field == 'Multiplication':
                                    df[field] = 1.0
                                elif field == 'Difference':
                                    df[field] = '00:00'
                        
                        # Fill missing values for calculation
                        df['Work Time'] = df['Work Time'].fillna('00:00')
                        df['Standard Time'] = df['Standard Time'].fillna('08:00')
                        df['Difference (Decimal)'] = df['Difference (Decimal)'].fillna(0.0)
                        df['Multiplication'] = df['Multiplication'].fillna(1.0)
                        df['Difference'] = df['Difference'].fillna('00:00')
                        
                        # Recalculate time differences and decimal values for new records
                        for idx, row in df.iterrows():
                            work_time = str(row['Work Time'])
                            standard_time = str(row['Standard Time'])
                            holiday = row.get('Holiday', '')
                            
                            # Only recalculate for records that need it (empty or invalid values)
                            if (pd.isna(row.get('Difference (Decimal)')) or 
                                row.get('Difference (Decimal)') == 0.0 or 
                                pd.isna(row.get('Difference')) or 
                                str(row.get('Difference', '')).strip() == ''):
                                
                                # Calculate time difference
                                diff_str = compute_time_difference(work_time, standard_time, holiday, default=True)
                                diff_decimal = compute_time_difference(work_time, standard_time, holiday, default=False)
                                
                                if diff_str is not None:
                                    df.at[idx, 'Difference'] = diff_str
                                if diff_decimal is not None:
                                    df.at[idx, 'Difference (Decimal)'] = diff_decimal
                        
                        st.write(f"Debug: Data shape before calculation: {df.shape}")
                        st.write(f"Debug: Sample Work Time values: {df['Work Time'].head(3).tolist()}")
                        st.write(f"Debug: Sample Difference (Decimal) values: {df['Difference (Decimal)'].head(3).tolist()}")
                        
                        # Helper function to ensure the 'Holiday' column has a valid, non-empty value.
                        def is_valid_holiday(value):
                            return pd.notnull(value) and str(value).strip() != ''
                        
                        valid_holiday_mask = df['Holiday'].apply(is_valid_holiday)
                        
                        # Convert the date objects to strings in "YYYY-MM-DD" format.
                        holiday_event_dates = set(
                            df.loc[valid_holiday_mask, 'Date'].apply(lambda d: d.strftime('%Y-%m-%d'))
                        )
                        
                        st.write(f"Debug: Found {len(holiday_event_dates)} holiday dates for calculation")
                        st.write(f"Debug: Holiday event dates: {list(holiday_event_dates)[:5]}")  # Show first 5
                        st.write(f"Debug: Starting holiday hours: {holiday_hours}")
                        st.write(f"Debug: Starting overtime: {hours_overtime_str}")
                        
                        # Compute running holiday hours using the extracted holiday dates.
                        df_before_calc = df.copy()
                        df = compute_running_holiday_hours(df, holiday_event_dates, calendar_events_date, holiday_hours, hours_overtime_str)
                        
                        # Debug: Check if calculation worked
                        if 'Holiday Hours' in df.columns:
                            st.write(f"Debug: Holiday Hours after calculation: {df['Holiday Hours'].head(3).tolist()}")
                        if 'Hours Overtime Left' in df.columns:
                            st.write(f"Debug: Hours Overtime Left after calculation: {df['Hours Overtime Left'].head(3).tolist()}")
                        
                        # Check if values actually changed
                        if 'Holiday Hours' in df_before_calc.columns and 'Holiday Hours' in df.columns:
                            changed = not df_before_calc['Holiday Hours'].equals(df['Holiday Hours'])
                            st.write(f"Debug: Holiday Hours values changed: {changed}")
                        if 'Hours Overtime Left' in df_before_calc.columns and 'Hours Overtime Left' in df.columns:
                            changed = not df_before_calc['Hours Overtime Left'].equals(df['Hours Overtime Left'])
                            st.write(f"Debug: Overtime values changed: {changed}")
                        
                        # Preserve manual_modifications field from the editor data
                        if 'manual_modifications' in edited_work_history_data.columns:
                            df['manual_modifications'] = edited_work_history_data['manual_modifications']
                        
                        # Preserve is_new_record field if it exists
                        if 'is_new_record' in edited_work_history_data.columns:
                            df['is_new_record'] = edited_work_history_data['is_new_record']
                        
                        # Now update session state
                        st.session_state["edited_work_history_data"] = df
                        st.success("Holiday hours calculated and updated!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error calculating holiday hours: {str(e)}")
                        import traceback
                        st.error(f"Full error: {traceback.format_exc()}")
            
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
            # Summary Table with modern styling and explanations
            summary_data = [
                ["Metric", "Value", "What This Means"],
                ["Employee", employee_name, "Your name as recorded in the system"],
                ["Pay Period", pay_period, "The date range this report covers"],
                ["Hours worked", hours_worked, "Total hours you actually worked (sum of all 'Work Time' entries)"],
                ["Hours expected", hours_expected, "Total hours you were expected to work (sum of all 'Standard Time' entries, excluding holidays)"],
                ["Overtime or Undertime Balance", df_to_download["Hours Overtime Left"].iloc[-1], "Your current overtime balance. Positive = overtime earned, Negative = undertime owed"],
                ["Remaining Holiday Hours", df_to_download["Holiday Hours"].iloc[-1], "Your remaining paid holiday hours that you can use"],
                ["Total Sick Days", df_to_download["Holiday"].apply(lambda x: 1 if x == "sick" or x == "Sick" else 0).sum(), "Number of days marked as sick leave in this period"],
                ["Total Available Time Off", decimal_hours_to_hhmmss(hhmm_to_decimal(df_to_download["Holiday Hours"].iloc[-1]) + hhmm_to_decimal(df_to_download["Hours Overtime Left"].iloc[-1])), "Combined hours of holiday time + overtime that you can use for time off"]
            ]

            # Calculate Total Available Time Off in Days
            total_available_hours = hhmm_to_decimal(df_to_download["Holiday Hours"].iloc[-1]) + hhmm_to_decimal(df_to_download["Hours Overtime Left"].iloc[-1])
            standard_work_hours_per_day = hhmm_to_decimal(standard_work_hours_str)  # Convert "08:00" to decimal hours
            total_available_days = total_available_hours / standard_work_hours_per_day if standard_work_hours_per_day > 0 else 0
            
            # Add the days calculation to the summary
            summary_data.append(["Total Available Time Off (Days)", f"{total_available_days:.1f} days", "Your total available time off converted to full work days (assuming 8-hour workday)"])

            summary_table = Table(summary_data, colWidths=[150, 150, 420])
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
            elements.append(PageBreak())

            # -- Detailed Explanation Page --
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
                "📈 <b>Total Available Time Off:</b> The combined total of your holiday hours plus overtime balance - this is the total time you can take off.",
                "",
                "📊 <b>Total Available Time Off (Days):</b> Your available time off converted to full work days (assuming an 8-hour workday)."
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
                "📊 <b>Multiplication:</b> Any multiplier applied to your hours (e.g., 2x for holiday work).",
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
                "🏖️ <b>Holiday Hours:</b>",
                "   • You start with a certain number of holiday hours per year",
                "   • Each day you take vacation, sick leave, or personal time, hours are deducted",
                "   • The remaining balance is shown in the 'Holiday Hours' column",
                "",
                "💰 <b>Overtime Balance:</b>",
                "   • Positive overtime hours accumulate when you work more than standard time",
                "   • These can be used for time off or paid out",
                "   • The running balance is shown in the 'Hours Overtime Left' column",
                "",
                "📈 <b>Available Time Off:</b>",
                "   Total Available = Holiday Hours + Overtime Balance",
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
                "🟡 <b>Yellow Highlighted Cells:</b>",
                "   These indicate data that was manually modified from the original upload. This helps you see what changes were made to your timecard data.",
                "",
                "📊 <b>Reading the Summary:</b>",
                "   • Compare 'Hours Worked' vs 'Hours Expected' to see if you met your work requirements",
                "   • Check 'Overtime Balance' to see if you have extra time available",
                "   • Review 'Holiday Hours' to know how much vacation time you have left",
                "",
                "📅 <b>Understanding Patterns:</b>",
                "   • Look for consistent work patterns",
                "   • Identify days with high overtime",
                "   • Check your break time usage",
                "",
                "⚠️ <b>What to Watch For:</b>",
                "   • Negative overtime balance (means you owe hours)",
                "   • Low holiday hours remaining",
                "   • Inconsistent check-in/check-out times",
                "   • Missing break times on long work days"
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
                "📋 <b>Review your timecard entries for accuracy</b>",
                "",
                "This report is generated automatically based on your timecard data. If you notice any discrepancies, please contact your supervisor immediately."
            ]
            
            for explanation in help_explanations:
                if explanation.strip():
                    elements.append(Paragraph(explanation, explanation_style))
                else:
                    elements.append(Spacer(1, 5))

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
