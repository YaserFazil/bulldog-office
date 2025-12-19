"""
Streamlit page for importing ngTecho CSV data to Frappe HR
Allows users to select sick days and paid holiday days before generating records.
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
from io import BytesIO
import tempfile
import os

from streamlit_extras.switch_page_button import switch_page
import importlib.util
import sys
import os

# Import functions from frappe_import_script
from frappe_import_script import (
    generate_frappe_records_from_ngtecho_csv,
    import_to_frappe_hr,
    check_existing_records,
    fetch_employee_standard_work_hours,
    validate_business_days_have_times,
)

# Import from page with number in name using importlib.util
pages_dir = os.path.dirname(os.path.abspath(__file__))
csv_converter_path = os.path.join(pages_dir, "9 CSV to Frappe HR.py")
spec = importlib.util.spec_from_file_location("csv_converter", csv_converter_path)
csv_converter = importlib.util.module_from_spec(spec)
sys.modules["csv_converter"] = csv_converter
spec.loader.exec_module(csv_converter)
parse_ngtecotime_csv = csv_converter.parse_ngtecotime_csv


def main():
    if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
        st.error("You need to log in first.")
        st.session_state["logged_in"] = False
        st.session_state["user_id"] = None
        switch_page("Login")
        return

    st.title("📥 Frappe HR Import Tool")
    
    st.markdown("""
    <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; border-left: 4px solid #2196f3; margin-bottom: 20px;">
        <strong>ℹ️ About This Tool</strong><br>
        Upload ngTecho CSV files and generate Employee Check-in and Attendance records for Frappe HR.
        You can manually select which days were sick days and which were paid holiday days.
    </div>
    """, unsafe_allow_html=True)

    # File upload
    st.markdown("### 📁 Step 1: Upload CSV File")
    uploaded_file = st.file_uploader(
        "Choose a CSV file in NGTecoTime format",
        type=['csv'],
        help="Upload a timecard CSV file with employee check-in/out data"
    )

    if uploaded_file is not None:
        try:
            # Parse CSV
            file_content = uploaded_file.read()
            parsed_data = parse_ngtecotime_csv(file_content)
            
            st.success(f"✅ Successfully parsed CSV for {parsed_data['employee']}")
            
            # Display extracted information
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**Employee:** {parsed_data['employee']}")
            with col2:
                st.info(f"**Pay Period:** {parsed_data['pay_period']}")
            
            # Load calendar events to check for weekends and public holidays
            from utils import load_calendar_events
            calendar_events = load_calendar_events()
            
            # Create DataFrame for date selection
            # Filter out weekends and public holidays that don't have IN/OUT times
            date_records = []
            for record in parsed_data['records']:
                try:
                    date_obj = datetime.strptime(record['date'], '%Y%m%d').date()
                    in_time = record.get('in_time', '').strip()
                    out_time = record.get('out_time', '').strip()
                    has_times = bool(in_time or out_time)
                    
                    # Check if it's a weekend (Saturday=5, Sunday=6)
                    is_weekend = date_obj.weekday() >= 5
                    
                    # Check if it's a public holiday
                    date_str = date_obj.strftime("%Y-%m-%d")
                    is_public_holiday = False
                    if date_str in calendar_events:
                        event = calendar_events[date_str]
                        event_str = str(event).lower()
                        # Check if it's a holiday (not just a weekend marker)
                        if "holiday" in event_str and "weekend" not in event_str:
                            is_public_holiday = True
                        # Also check if it's a weekend that's marked as holiday
                        elif is_weekend and "holiday" in event_str:
                            is_public_holiday = True
                    
                    # Skip weekends and public holidays that don't have IN/OUT times
                    # Keep business days (even with empty IN/OUT) and weekends/holidays with times
                    if (is_weekend or is_public_holiday) and not has_times:
                        continue
                    
                    date_records.append({
                        'Date': date_obj,
                        'Day': record.get('day', ''),
                        'IN': in_time,
                        'OUT': out_time,
                        'Note': record.get('note', ''),
                    })
                except:
                    continue
            
            if not date_records:
                st.error("No valid date records found in CSV.")
                return
            
            df_dates = pd.DataFrame(date_records)
            df_dates = df_dates.sort_values('Date').reset_index(drop=True)
            
            # Store original for comparison (to detect edits)
            df_dates_original = df_dates.copy()
            st.session_state['df_dates_original'] = df_dates_original
            
            # Step 2: Combined editor for dates, times, sick/holiday selection
            st.markdown("### ✏️ Step 2: Review and Edit Daily Records")
            st.info("💡 You can edit IN/OUT times, select sick days, paid holiday days, and absent days. Days with empty IN/OUT times should be marked as 'Is Sick', 'Is Paid Holiday', or 'Is Absent' if applicable. Any edited times will be marked with 'Is Edited' flag in Frappe HR.")
            
            # Create columns for selection and editing
            df_dates['Is Sick'] = False
            df_dates['Is Paid Holiday'] = False
            df_dates['Is Absent'] = False
            df_dates['Is Edited'] = False
            
            # Display dates in a unified data editor
            edited_df = st.data_editor(
                df_dates[['Date', 'Day', 'IN', 'OUT', 'Note', 'Is Sick', 'Is Paid Holiday', 'Is Absent', 'Is Edited']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Date': st.column_config.DateColumn('Date', disabled=True),
                    'Day': st.column_config.TextColumn('Day', disabled=True),
                    'IN': st.column_config.TextColumn('IN', help="Format: HH:MM (e.g., 09:00). Edit to correct check-in time."),
                    'OUT': st.column_config.TextColumn('OUT', help="Format: HH:MM (e.g., 17:00). Edit to correct check-out time."),
                    'Note': st.column_config.TextColumn('Note', disabled=True),
                    'Is Sick': st.column_config.CheckboxColumn('Is Sick', help="Check if this day was a sick day"),
                    'Is Paid Holiday': st.column_config.CheckboxColumn('Is Paid Holiday', help="Check if this day was a paid holiday"),
                    'Is Absent': st.column_config.CheckboxColumn('Is Absent', help="Check if this day was an absent day (no IN/OUT times required)"),
                    'Is Edited': st.column_config.CheckboxColumn('Is Edited', disabled=True, help="Auto-marked if IN/OUT times were edited"),
                },
                key="unified_editor",
            )
            
            # Detect edits by comparing original vs edited IN/OUT times
            edited_df['Is Edited'] = False
            for i in range(min(len(edited_df), len(df_dates_original))):
                original_row = df_dates_original.iloc[i]
                edited_row = edited_df.iloc[i]
                
                # Check if IN or OUT time changed
                original_in = str(original_row.get('IN', '') or '')
                edited_in = str(edited_row.get('IN', '') or '')
                original_out = str(original_row.get('OUT', '') or '')
                edited_out = str(edited_row.get('OUT', '') or '')
                
                if (original_in.strip() != edited_in.strip() or original_out.strip() != edited_out.strip()):
                    edited_df.at[i, 'Is Edited'] = True
            
            # Store edited dataframe in session state
            st.session_state['df_dates_edited'] = edited_df
            
            # Show summary of edited records
            edited_count = edited_df['Is Edited'].sum()
            if edited_count > 0:
                st.success(f"✅ {int(edited_count)} day(s) have been manually edited and will be marked with 'Is Edited' flag in Frappe HR.")
            
            # Extract selected dates and edited times
            sick_dates = set(edited_df[edited_df['Is Sick'] == True]['Date'].tolist())
            holiday_dates = set(edited_df[edited_df['Is Paid Holiday'] == True]['Date'].tolist())
            
            # Step 3: Generate records
            st.markdown("### 🔄 Step 3: Generate Records")
            
            # Validate business days before allowing generation
            from utils import load_calendar_events
            calendar_events = load_calendar_events()
            is_valid, missing_days = validate_business_days_have_times(
                dates_df=edited_df,
                calendar_events=calendar_events,
            )
            
            if not is_valid:
                st.error("❌ **Validation Failed**: The following days are missing valid IN/OUT times:")
                missing_df = pd.DataFrame(missing_days)
                missing_df['Missing Fields'] = missing_df['missing_fields'].apply(lambda x: ', '.join(x))
                missing_df_display = missing_df[['date_str', 'day_name', 'Missing Fields']].copy()
                missing_df_display.columns = ['Date', 'Day', 'Missing Fields']
                st.dataframe(missing_df_display, use_container_width=True, hide_index=True)
                st.warning("⚠️ Please fill in the missing IN/OUT times before generating records.")
                st.info("💡 **Note**: Weekends, public holidays, sick days, paid holidays, and absent days are only excluded from validation if they have no IN/OUT times. If you worked on these days (have IN/OUT times filled), they will be validated and require both IN and OUT times.")
                st.stop()  # Stop execution to prevent generation
            else:
                st.success(f"✅ Validation passed! All days that require IN/OUT times have valid entries.")
            
            if st.button("Generate Frappe HR Records", type="primary", use_container_width=True):
                with st.spinner("Generating Employee Check-in and Attendance records..."):
                    # Save uploaded file temporarily
                    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.csv') as tmp_file:
                        tmp_file.write(file_content)
                        tmp_path = tmp_file.name
                    
                    try:
                        # Get edited dates from unified editor
                        edited_df = st.session_state.get('df_dates_edited', df_dates)
                        
                        # Get employee username to fetch and display standard work hours
                        employee_full_name = parsed_data['employee']
                        # Get username from the CSV converter module
                        get_username_by_full_name = csv_converter.get_username_by_full_name
                        employee_username = get_username_by_full_name(employee_full_name)
                        
                        # Fetch standard work hours from Frappe HR to show user
                        try:
                            fetched_standard_hours = fetch_employee_standard_work_hours(employee_username)
                            from utils import decimal_hours_to_hhmmss
                            standard_hours_str = decimal_hours_to_hhmmss(fetched_standard_hours)
                            st.info(f"ℹ️ Using standard work hours: **{standard_hours_str}** (fetched from Frappe HR: Employee > Default Shift > Shift Type > custom_standard_work_hours)")
                        except Exception as e:
                            st.warning(f"⚠️ Could not fetch standard work hours from Frappe HR: {str(e)}. Using default 8.0 hours.")
                            fetched_standard_hours = 8.0
                        
                        # Generate records using edited IN/OUT times
                        checkin_df, attendance_df = generate_frappe_records_from_ngtecho_csv(
                            csv_file_path=tmp_path,
                            standard_work_hours=fetched_standard_hours,  # Use fetched value from Frappe HR
                            auto_detect_weekends_holidays=False,  # Default: disabled
                            multiply_sunday_hours=False,  # Default: disabled
                            user_selected_sick_dates=sick_dates,
                            user_selected_holiday_dates=holiday_dates,
                            edited_dates_df=edited_df,  # Pass edited dates with IN/OUT times
                        )
                        
                        # Store in session state so they persist across reruns
                        st.session_state['frappe_checkin_df'] = checkin_df
                        st.session_state['frappe_attendance_df'] = attendance_df
                        st.session_state['frappe_employee_name'] = parsed_data['employee']
                        
                        st.success(f"✅ Generated {len(checkin_df)} check-in records and {len(attendance_df)} attendance records!")
                        
                        # Display previews
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("#### 📋 Employee Check-in Records Preview")
                            st.dataframe(checkin_df.head(10), use_container_width=True)
                        with col2:
                            st.markdown("#### 📋 Attendance Records Preview")
                            st.dataframe(attendance_df.head(10), use_container_width=True)
                        
                        # Show summary of edited records
                        edited_checkin_count = checkin_df['Is Edited'].sum() if 'Is Edited' in checkin_df.columns else 0
                        if edited_checkin_count > 0:
                            st.success(f"✅ {int(edited_checkin_count)} check-in record(s) from edited dates will be marked with 'Is Edited' flag in Frappe HR.")
                        
                        # Download options
                        st.markdown("### 💾 Download Generated Records")
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        employee_slug = parsed_data['employee'].split('(')[0].strip().replace(' ', '_').lower()
                        
                        excel_buffer = BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                            # Export edited checkin_df if available, otherwise use original
                            checkin_df_export = st.session_state.get('frappe_checkin_df', checkin_df)
                            checkin_df_export.to_excel(writer, sheet_name='Employee Checkin', index=False)
                            attendance_df.to_excel(writer, sheet_name='Attendance', index=False)
                        excel_buffer.seek(0)
                        
                        st.download_button(
                            label="📥 Download Excel File",
                            data=excel_buffer,
                            file_name=f"frappe_hr_import_{employee_slug}_{timestamp}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )
                        
                    finally:
                        # Clean up temp file
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
        
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")
            st.exception(e)
    
    else:
        st.info("👆 Please upload a CSV file to get started.")
    
    # Show import section if records are already generated (persisted in session state)
    if 'frappe_checkin_df' in st.session_state and 'frappe_attendance_df' in st.session_state:
        checkin_df_existing = st.session_state.get('frappe_checkin_df')
        attendance_df_existing = st.session_state.get('frappe_attendance_df')
        employee_name_existing = st.session_state.get('frappe_employee_name', 'Employee')
        
        if checkin_df_existing is not None and attendance_df_existing is not None and len(checkin_df_existing) > 0:
            st.markdown("---")
            st.markdown("### 🚀 Import Previously Generated Records")
            st.info(f"Found {len(checkin_df_existing)} check-in records and {len(attendance_df_existing)} attendance records for {employee_name_existing}")
            
            col_import1, col_import2 = st.columns(2)
            with col_import1:
                dry_run_existing = st.checkbox("Dry Run (Validate only, don't import)", value=True, key="dry_run_existing")
            
            # Check for existing records before import
            existing_records_existing = None
            if not dry_run_existing:
                if st.button("🔍 Check for Existing Records", use_container_width=True, key="check_existing_existing"):
                    with st.spinner("Checking for existing records in Frappe HR..."):
                        try:
                            existing_records_existing = check_existing_records(
                                checkin_df=checkin_df_existing,
                                attendance_df=attendance_df_existing,
                            )
                            st.session_state['existing_records_existing'] = existing_records_existing
                        except Exception as e:
                            st.error(f"Error checking existing records: {str(e)}")
            
            # Show existing records warning if found
            if 'existing_records_existing' in st.session_state:
                existing_records_existing = st.session_state['existing_records_existing']
                if existing_records_existing and (existing_records_existing.get('checkin_existing_count', 0) > 0 or existing_records_existing.get('attendance_existing_count', 0) > 0):
                    st.warning(
                        f"⚠️ Found {existing_records_existing.get('checkin_existing_count', 0)} existing check-in records "
                        f"and {existing_records_existing.get('attendance_existing_count', 0)} existing attendance records "
                        f"that match your import data."
                    )
                    overwrite_choice_existing = st.radio(
                        "How would you like to proceed?",
                        ["Skip existing records (recommended)", "Overwrite existing attendance records"],
                        key="overwrite_choice_existing"
                    )
                    overwrite_existing_existing = overwrite_choice_existing == "Overwrite existing attendance records"
                else:
                    overwrite_existing_existing = False
            else:
                overwrite_existing_existing = False
            
            with col_import2:
                if st.button("Import to Frappe HR", type="primary", use_container_width=True, key="import_existing"):
                    with st.spinner("Importing to Frappe HR..."):
                        # Get existing records info if available
                        existing_records_info_existing = st.session_state.get('existing_records_existing') if not overwrite_existing_existing else None
                        skip_existing_existing = not overwrite_existing_existing and existing_records_info_existing is not None
                        
                        results = import_to_frappe_hr(
                            checkin_df=checkin_df_existing,
                            attendance_df=attendance_df_existing,
                            dry_run=dry_run_existing,
                            overwrite_existing=overwrite_existing_existing if not dry_run_existing else False,
                            skip_existing=skip_existing_existing,
                            existing_records=existing_records_info_existing,
                        )
                        
                        if dry_run_existing:
                            st.info(f"Dry run completed: {results.get('checkin_count', 0)} check-ins, {results.get('attendance_count', 0)} attendance records would be imported.")
                        else:
                            st.success(f"✅ Import completed!")
                            st.metric("Check-ins Imported", results.get('checkin_imported', 0))
                            st.metric("Attendance Imported", results.get('attendance_imported', 0))
                            
                            # Store failed records in session state for reimport
                            if not results.get('failed_checkin_df', pd.DataFrame()).empty:
                                st.session_state['failed_checkin_df'] = results['failed_checkin_df']
                            if not results.get('failed_attendance_df', pd.DataFrame()).empty:
                                st.session_state['failed_attendance_df'] = results['failed_attendance_df']
                            
                            if results.get('checkin_failed', 0) > 0 or results.get('attendance_failed', 0) > 0:
                                st.warning(f"⚠️ {results.get('checkin_failed', 0)} check-ins and {results.get('attendance_failed', 0)} attendance records failed to import.")
                                st.info("💡 You can reimport failed records using the 'Reimport Failed Records' section below.")
                            if results.get('errors'):
                                st.error(f"❌ {len(results['errors'])} errors occurred")
                                with st.expander("View Errors"):
                                    for error in results['errors'][:20]:
                                        st.text(error)
            
            if st.button("Clear Generated Records", key="clear_records"):
                del st.session_state['frappe_checkin_df']
                del st.session_state['frappe_attendance_df']
                del st.session_state['frappe_employee_name']
                if 'existing_records' in st.session_state:
                    del st.session_state['existing_records']
                st.success("✅ Records cleared. Please generate new records.")
                st.rerun()
    
    # Show reimport failed records section
    if 'failed_checkin_df' in st.session_state or 'failed_attendance_df' in st.session_state:
        failed_checkin = st.session_state.get('failed_checkin_df', pd.DataFrame())
        failed_attendance = st.session_state.get('failed_attendance_df', pd.DataFrame())
        
        if not failed_checkin.empty or not failed_attendance.empty:
            st.markdown("---")
            st.markdown("### 🔄 Reimport Failed Records")
            
            failed_checkin_count = len(failed_checkin) if not failed_checkin.empty else 0
            failed_attendance_count = len(failed_attendance) if not failed_attendance.empty else 0
            
            st.warning(f"⚠️ You have {failed_checkin_count} failed check-in records and {failed_attendance_count} failed attendance records from a previous import.")
            
            col1, col2 = st.columns(2)
            with col1:
                if not failed_checkin.empty:
                    st.markdown(f"#### Failed Check-ins ({failed_checkin_count})")
                    st.dataframe(failed_checkin, use_container_width=True)
            with col2:
                if not failed_attendance.empty:
                    st.markdown(f"#### Failed Attendance ({failed_attendance_count})")
                    st.dataframe(failed_attendance, use_container_width=True)
            
            if st.button("🔄 Reimport Failed Records", type="primary", use_container_width=True, key="reimport_failed"):
                with st.spinner("Reimporting failed records..."):
                    results = import_to_frappe_hr(
                        checkin_df=failed_checkin if not failed_checkin.empty else pd.DataFrame(),
                        attendance_df=failed_attendance if not failed_attendance.empty else pd.DataFrame(),
                        dry_run=False,
                        overwrite_existing=False,
                    )
                    
                    st.success(f"✅ Reimport completed!")
                    st.metric("Check-ins Reimported", results.get('checkin_imported', 0))
                    st.metric("Attendance Reimported", results.get('attendance_imported', 0))
                    
                    # Update failed records with new failures
                    if not results.get('failed_checkin_df', pd.DataFrame()).empty:
                        st.session_state['failed_checkin_df'] = results['failed_checkin_df']
                    else:
                        if 'failed_checkin_df' in st.session_state:
                            del st.session_state['failed_checkin_df']
                    
                    if not results.get('failed_attendance_df', pd.DataFrame()).empty:
                        st.session_state['failed_attendance_df'] = results['failed_attendance_df']
                    else:
                        if 'failed_attendance_df' in st.session_state:
                            del st.session_state['failed_attendance_df']
                    
                    if results.get('checkin_failed', 0) > 0 or results.get('attendance_failed', 0) > 0:
                        st.warning(f"⚠️ {results.get('checkin_failed', 0)} check-ins and {results.get('attendance_failed', 0)} attendance records still failed.")
                    else:
                        st.success("🎉 All failed records have been successfully reimported!")
                        if 'failed_checkin_df' in st.session_state:
                            del st.session_state['failed_checkin_df']
                        if 'failed_attendance_df' in st.session_state:
                            del st.session_state['failed_attendance_df']
                    
                    if results.get('errors'):
                        st.error(f"❌ {len(results['errors'])} errors occurred")
                        with st.expander("View Errors"):
                            for error in results['errors'][:20]:
                                st.text(error)
            
            if st.button("🗑️ Clear Failed Records", key="clear_failed"):
                if 'failed_checkin_df' in st.session_state:
                    del st.session_state['failed_checkin_df']
                if 'failed_attendance_df' in st.session_state:
                    del st.session_state['failed_attendance_df']
                st.success("✅ Failed records cleared.")
                st.rerun()


if __name__ == "__main__":
    main()

