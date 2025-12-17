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
            
            # Create DataFrame for date selection
            date_records = []
            for record in parsed_data['records']:
                try:
                    date_obj = datetime.strptime(record['date'], '%Y%m%d').date()
                    date_records.append({
                        'Date': date_obj,
                        'Day': record.get('day', ''),
                        'IN': record.get('in_time', ''),
                        'OUT': record.get('out_time', ''),
                        'Note': record.get('note', ''),
                    })
                except:
                    continue
            
            if not date_records:
                st.error("No valid date records found in CSV.")
                return
            
            df_dates = pd.DataFrame(date_records)
            df_dates = df_dates.sort_values('Date').reset_index(drop=True)
            
            # Step 2: User selection for sick/holiday days
            st.markdown("### 🏥 Step 2: Select Sick Days and Paid Holiday Days")
            st.markdown("Select which days were **sick days** and which were **paid holiday days**.")
            
            # Create columns for selection
            df_dates['Is Sick'] = False
            df_dates['Is Paid Holiday'] = False
            
            # Display dates in a data editor for selection
            edited_df = st.data_editor(
                df_dates[['Date', 'Day', 'IN', 'OUT', 'Is Sick', 'Is Paid Holiday']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Date': st.column_config.DateColumn('Date', disabled=True),
                    'Day': st.column_config.TextColumn('Day', disabled=True),
                    'IN': st.column_config.TextColumn('IN', disabled=True),
                    'OUT': st.column_config.TextColumn('OUT', disabled=True),
                    'Is Sick': st.column_config.CheckboxColumn('Is Sick'),
                    'Is Paid Holiday': st.column_config.CheckboxColumn('Is Paid Holiday'),
                }
            )
            
            # Extract selected dates
            sick_dates = set(edited_df[edited_df['Is Sick'] == True]['Date'].tolist())
            holiday_dates = set(edited_df[edited_df['Is Paid Holiday'] == True]['Date'].tolist())
            
            # Step 3: Configuration
            st.markdown("### ⚙️ Step 3: Configuration")
            col1, col2, col3 = st.columns(3)
            with col1:
                standard_hours = st.number_input(
                    "Standard Work Hours per Day",
                    min_value=0.0,
                    max_value=24.0,
                    value=8.0,
                    step=0.5,
                )
            with col2:
                auto_detect = st.checkbox(
                    "Auto-detect weekends/holidays",
                    value=True,
                    help="Automatically create records for missing weekends and public holidays"
                )
            with col3:
                multiply_sunday = st.checkbox(
                    "Multiply Sunday hours by 2.0",
                    value=True,
                    help="Multiply work hours for Sundays by 2.0"
                )
            
            # Step 4: Generate records
            st.markdown("### 🔄 Step 4: Generate Records")
            
            if st.button("Generate Frappe HR Records", type="primary", use_container_width=True):
                with st.spinner("Generating Employee Check-in and Attendance records..."):
                    # Save uploaded file temporarily
                    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.csv') as tmp_file:
                        tmp_file.write(file_content)
                        tmp_path = tmp_file.name
                    
                    try:
                        # Generate records
                        checkin_df, attendance_df = generate_frappe_records_from_ngtecho_csv(
                            csv_file_path=tmp_path,
                            standard_work_hours=standard_hours,
                            auto_detect_weekends_holidays=auto_detect,
                            multiply_sunday_hours=multiply_sunday,
                            user_selected_sick_dates=sick_dates,
                            user_selected_holiday_dates=holiday_dates,
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
                        
                        # Download options
                        st.markdown("### 💾 Download Generated Records")
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        employee_slug = parsed_data['employee'].split('(')[0].strip().replace(' ', '_').lower()
                        
                        excel_buffer = BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                            checkin_df.to_excel(writer, sheet_name='Employee Checkin', index=False)
                            attendance_df.to_excel(writer, sheet_name='Attendance', index=False)
                        excel_buffer.seek(0)
                        
                        st.download_button(
                            label="📥 Download Excel File",
                            data=excel_buffer,
                            file_name=f"frappe_hr_import_{employee_slug}_{timestamp}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )
                        
                        # Import to Frappe HR option
                        st.markdown("### 🚀 Import to Frappe HR")
                        st.warning("⚠️ This will create records in your Frappe HR system. Make sure the data is correct before proceeding.")
                        
                        col_import1, col_import2 = st.columns(2)
                        with col_import1:
                            dry_run = st.checkbox("Dry Run (Validate only, don't import)", value=True)
                        
                        # Check for existing records before import
                        checkin_df_import = st.session_state.get('frappe_checkin_df')
                        attendance_df_import = st.session_state.get('frappe_attendance_df')
                        
                        existing_records = None
                        if not dry_run and checkin_df_import is not None and attendance_df_import is not None:
                            if st.button("🔍 Check for Existing Records", use_container_width=True, key="check_existing"):
                                with st.spinner("Checking for existing records in Frappe HR..."):
                                    try:
                                        existing_records = check_existing_records(
                                            checkin_df=checkin_df_import,
                                            attendance_df=attendance_df_import,
                                        )
                                        st.session_state['existing_records'] = existing_records
                                    except Exception as e:
                                        st.error(f"Error checking existing records: {str(e)}")
                        
                        # Show existing records warning if found
                        if 'existing_records' in st.session_state:
                            existing_records = st.session_state['existing_records']
                            if existing_records and (existing_records.get('checkin_existing_count', 0) > 0 or existing_records.get('attendance_existing_count', 0) > 0):
                                st.warning(
                                    f"⚠️ Found {existing_records.get('checkin_existing_count', 0)} existing check-in records "
                                    f"and {existing_records.get('attendance_existing_count', 0)} existing attendance records "
                                    f"that match your import data."
                                )
                                overwrite_choice = st.radio(
                                    "How would you like to proceed?",
                                    ["Skip existing records (recommended)", "Overwrite existing attendance records"],
                                    key="overwrite_choice"
                                )
                                overwrite_existing = overwrite_choice == "Overwrite existing attendance records"
                            else:
                                overwrite_existing = False
                        else:
                            overwrite_existing = False
                        
                        with col_import2:
                            if st.button("Import to Frappe HR", type="primary", use_container_width=True):
                                with st.spinner("Importing to Frappe HR..."):
                                    # Get dataframes from session state
                                    checkin_df_import = st.session_state.get('frappe_checkin_df')
                                    attendance_df_import = st.session_state.get('frappe_attendance_df')
                                    
                                    if checkin_df_import is None or attendance_df_import is None:
                                        st.error("❌ Records not found. Please generate records first.")
                                    else:
                                        # Get existing records info if available
                                        existing_records_info = st.session_state.get('existing_records') if not overwrite_existing else None
                                        skip_existing = not overwrite_existing and existing_records_info is not None
                                        
                                        results = import_to_frappe_hr(
                                            checkin_df=checkin_df_import,
                                            attendance_df=attendance_df_import,
                                            dry_run=dry_run,
                                            overwrite_existing=overwrite_existing if not dry_run else False,
                                            skip_existing=skip_existing,
                                            existing_records=existing_records_info,
                                        )
                                        
                                        if dry_run:
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

