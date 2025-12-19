"""
Streamlit page for data quality testing tools.
Allows users to check for duplicates and compare CSV files with Frappe HR data.
"""

import streamlit as st
from datetime import datetime, date
import pandas as pd
from io import BytesIO

from streamlit_extras.switch_page_button import switch_page
from frappe_client import fetch_frappe_employees, fetch_employee_checkins, fetch_employee_attendance
from collections import defaultdict


def main():
    if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
        st.error("You need to log in first.")
        st.session_state["logged_in"] = False
        st.session_state["user_id"] = None
        switch_page("Login")
        return

    st.title("🔍 Data Quality Tests")
    
    st.markdown("""
    <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; border-left: 4px solid #2196f3; margin-bottom: 20px;">
        <strong>ℹ️ About This Tool</strong><br>
        Test and validate data quality in Frappe HR. Check for duplicate records and compare CSV files with existing data.
    </div>
    """, unsafe_allow_html=True)
    
    # Get list of employees
    try:
        employees = fetch_frappe_employees(limit=1000)
        employee_dict = {emp.get('employee_name', ''): emp.get('name') for emp in employees}
        employee_names = sorted([name for name in employee_dict.keys() if name])
    except Exception as e:
        st.error(f"Error fetching employees: {e}")
        employee_dict = {}
        employee_names = []
    
    # Tabs for different test types
    tab1, tab2, tab3 = st.tabs([
        "🔍 Check Employee Checkin Duplicates",
        "📋 Check Attendance Duplicates",
        "📄 Compare CSV with Checkin Records"
    ])
    
    # Tab 1: Employee Checkin Duplicates
    with tab1:
        st.markdown("### 🔍 Check for Duplicate Dates in Employee Checkin Records")
        st.info("This tool checks if there are multiple IN or OUT records for the same date.")
        
        if employee_names:
            selected_employee_name = st.selectbox(
                "Select Employee",
                employee_names,
                key="checkin_employee_select"
            )
            employee_code = employee_dict.get(selected_employee_name)
            
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input(
                    "Start Date",
                    value=date(2020, 1, 1),
                    key="checkin_start_date"
                )
            with col2:
                end_date = st.date_input(
                    "End Date",
                    value=date.today(),
                    key="checkin_end_date"
                )
            
            if st.button("🔍 Check for Duplicates", type="primary", use_container_width=True, key="checkin_check_btn"):
                with st.spinner("Checking for duplicate dates..."):
                    try:
                        from datetime import datetime
                        start_datetime = datetime.combine(start_date, datetime.min.time())
                        end_datetime = datetime.combine(end_date, datetime.max.time())
                        
                        checkins = fetch_employee_checkins(employee_code, start_datetime, end_datetime, limit=50000)
                        
                        # Group by date and log_type
                        by_date = defaultdict(lambda: {'IN': [], 'OUT': []})
                        
                        for checkin in checkins:
                            time_str = checkin.get('time', '')
                            log_type = checkin.get('log_type', '')
                            name = checkin.get('name', '')
                            
                            if time_str:
                                try:
                                    if '.' in time_str:
                                        dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S.%f')
                                    else:
                                        dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                                    date_key = dt.date()
                                    
                                    if log_type in ['IN', 'OUT']:
                                        by_date[date_key][log_type].append({
                                            'name': name,
                                            'time': time_str,
                                            'log_type': log_type
                                        })
                                except:
                                    pass
                        
                        # Check for duplicates
                        duplicate_dates = []
                        for check_date, records in sorted(by_date.items()):
                            in_count = len(records['IN'])
                            out_count = len(records['OUT'])
                            
                            if in_count > 1 or out_count > 1:
                                duplicate_dates.append({
                                    'date': check_date,
                                    'IN_count': in_count,
                                    'OUT_count': out_count,
                                    'IN_records': records['IN'],
                                    'OUT_records': records['OUT']
                                })
                        
                        st.success(f"✅ Found {len(checkins)} total checkin records")
                        
                        if duplicate_dates:
                            st.error(f"❌ Found {len(duplicate_dates)} dates with duplicate IN/OUT records")
                            
                            # Display duplicates in a table
                            dup_data = []
                            for dup in duplicate_dates:
                                in_times = ', '.join([r['time'] for r in dup['IN_records']])
                                out_times = ', '.join([r['time'] for r in dup['OUT_records']])
                                dup_data.append({
                                    'Date': dup['date'],
                                    'IN Count': dup['IN_count'],
                                    'OUT Count': dup['OUT_count'],
                                    'IN Times': in_times,
                                    'OUT Times': out_times
                                })
                            
                            dup_df = pd.DataFrame(dup_data)
                            st.dataframe(dup_df, use_container_width=True, hide_index=True)
                            
                            # Download option
                            csv_buffer = BytesIO()
                            dup_df.to_csv(csv_buffer, index=False)
                            st.download_button(
                                label="📥 Download Duplicates Report",
                                data=csv_buffer.getvalue(),
                                file_name=f"checkin_duplicates_{employee_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv",
                            )
                        else:
                            st.success("✅ No duplicate dates found! All dates have at most 1 IN and 1 OUT record.")
                        
                        # Summary
                        st.markdown("### 📊 Summary")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Dates", len(by_date))
                        with col2:
                            st.metric("Duplicate Dates", len(duplicate_dates))
                        with col3:
                            st.metric("Dates with Duplicate IN", sum(1 for d in duplicate_dates if d['IN_count'] > 1))
                        with col4:
                            st.metric("Dates with Duplicate OUT", sum(1 for d in duplicate_dates if d['OUT_count'] > 1))
                            
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
                        st.exception(e)
        else:
            st.warning("⚠️ Could not load employee list. Please check your Frappe HR connection.")
    
    # Tab 2: Attendance Duplicates
    with tab2:
        st.markdown("### 📋 Check for Duplicate Dates in Attendance Records")
        st.info("This tool checks if there are multiple Attendance records for the same date.")
        
        if employee_names:
            selected_employee_name = st.selectbox(
                "Select Employee",
                employee_names,
                key="attendance_employee_select"
            )
            employee_code = employee_dict.get(selected_employee_name)
            
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input(
                    "Start Date",
                    value=date(2020, 1, 1),
                    key="attendance_start_date"
                )
            with col2:
                end_date = st.date_input(
                    "End Date",
                    value=date.today(),
                    key="attendance_end_date"
                )
            
            if st.button("🔍 Check for Duplicates", type="primary", use_container_width=True, key="attendance_check_btn"):
                with st.spinner("Checking for duplicate dates..."):
                    try:
                        attendance_records = fetch_employee_attendance(employee_code, start_date, end_date, limit=10000)
                        
                        # Group by attendance_date
                        by_date = defaultdict(list)
                        
                        for record in attendance_records:
                            attendance_date_str = record.get('attendance_date', '')
                            name = record.get('name', '')
                            status = record.get('status', '')
                            leave_type = record.get('leave_type', '')
                            
                            if attendance_date_str:
                                try:
                                    try:
                                        date_obj = datetime.strptime(attendance_date_str, '%Y-%m-%d').date()
                                    except:
                                        date_obj = datetime.strptime(attendance_date_str, '%d-%m-%Y').date()
                                    
                                    by_date[date_obj].append({
                                        'name': name,
                                        'attendance_date': attendance_date_str,
                                        'status': status,
                                        'leave_type': leave_type
                                    })
                                except:
                                    pass
                        
                        # Check for duplicates
                        duplicate_dates = []
                        for check_date, records in sorted(by_date.items()):
                            if len(records) > 1:
                                duplicate_dates.append({
                                    'date': check_date,
                                    'count': len(records),
                                    'records': records
                                })
                        
                        st.success(f"✅ Found {len(attendance_records)} total attendance records")
                        
                        if duplicate_dates:
                            st.error(f"❌ Found {len(duplicate_dates)} dates with duplicate Attendance records")
                            
                            # Display duplicates in a table
                            dup_data = []
                            for dup in duplicate_dates:
                                records_info = '; '.join([f"{r['name']} ({r['status']}, {r.get('leave_type', 'N/A')})" for r in dup['records']])
                                dup_data.append({
                                    'Date': dup['date'],
                                    'Record Count': dup['count'],
                                    'Records': records_info
                                })
                            
                            dup_df = pd.DataFrame(dup_data)
                            st.dataframe(dup_df, use_container_width=True, hide_index=True)
                            
                            # Download option
                            csv_buffer = BytesIO()
                            dup_df.to_csv(csv_buffer, index=False)
                            st.download_button(
                                label="📥 Download Duplicates Report",
                                data=csv_buffer.getvalue(),
                                file_name=f"attendance_duplicates_{employee_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv",
                            )
                        else:
                            st.success("✅ No duplicate dates found! All dates have at most 1 Attendance record.")
                        
                        # Summary
                        st.markdown("### 📊 Summary")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Total Dates", len(by_date))
                        with col2:
                            st.metric("Duplicate Dates", len(duplicate_dates))
                            
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
                        st.exception(e)
        else:
            st.warning("⚠️ Could not load employee list. Please check your Frappe HR connection.")
    
    # Tab 3: CSV Comparison
    with tab3:
        st.markdown("### 📄 Compare ngTeco CSV with Employee Checkin Records")
        st.info("Upload a ngTeco CSV file and compare it with existing Employee Checkin records in Frappe HR.")
        
        uploaded_file = st.file_uploader(
            "Upload ngTeco CSV File",
            type=['csv'],
            key="csv_comparison_file"
        )
        
        if uploaded_file is not None:
            try:
                import csv
                from io import StringIO
                
                # Read CSV
                content = uploaded_file.read().decode('utf-8')
                reader = csv.reader(StringIO(content))
                
                csv_data = []
                employee_name = None
                pay_period = None
                
                for i, row in enumerate(reader):
                    if i == 0:  # Timecard Report line
                        continue
                    elif i == 1:  # Pay Period line
                        if len(row) > 3 and row[3]:
                            pay_period = row[3]
                    elif i == 2:  # Employee line
                        if len(row) > 3 and row[3]:
                            employee_name = row[3]
                    elif i == 3:  # Header line
                        continue
                    else:
                        if len(row) >= 4:
                            date_str = row[1].strip() if row[1] else ''
                            in_time = row[2].strip() if row[2] else ''
                            out_time = row[3].strip() if row[3] else ''
                            
                            if date_str and (in_time or out_time):
                                try:
                                    date_obj = datetime.strptime(date_str, '%Y%m%d').date()
                                    csv_data.append({
                                        'date': date_obj,
                                        'in_time': in_time,
                                        'out_time': out_time
                                    })
                                except:
                                    pass
                
                if employee_name and csv_data:
                    st.success(f"✅ CSV loaded: {len(csv_data)} records for {employee_name}")
                    
                    # Find employee code
                    employee_code = None
                    def normalize_name(name):
                        return ' '.join(name.split()).lower() if name else ''
                    
                    csv_name_normalized = normalize_name(employee_name)
                    for emp_name, emp_code in employee_dict.items():
                        if normalize_name(emp_name) == csv_name_normalized:
                            employee_code = emp_code
                            break
                    
                    if not employee_code:
                        st.error(f"❌ Could not find employee code for: {employee_name}")
                    else:
                        st.info(f"📋 Employee Code: {employee_code}")
                        
                        if st.button("🔍 Compare with Frappe HR", type="primary", use_container_width=True, key="csv_compare_btn"):
                            with st.spinner("Comparing CSV with Frappe HR records..."):
                                try:
                                    min_date = min(r['date'] for r in csv_data)
                                    max_date = max(r['date'] for r in csv_data)
                                    start_datetime = datetime.combine(min_date, datetime.min.time())
                                    end_datetime = datetime.combine(max_date, datetime.max.time())
                                    
                                    # Fetch checkins
                                    checkins = fetch_employee_checkins(employee_code, start_datetime, end_datetime, limit=50000)
                                    
                                    # Build checkins by date from Frappe
                                    frappe_by_date = defaultdict(lambda: {'IN': [], 'OUT': []})
                                    
                                    for checkin in checkins:
                                        time_str = checkin.get('time', '')
                                        log_type = checkin.get('log_type', '')
                                        
                                        if time_str:
                                            try:
                                                if '.' in time_str:
                                                    dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S.%f')
                                                else:
                                                    dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                                                date_key = dt.date()
                                                time_only = dt.strftime('%H:%M')
                                                
                                                if log_type in ['IN', 'OUT']:
                                                    frappe_by_date[date_key][log_type].append({
                                                        'time': time_only,
                                                        'datetime': dt
                                                    })
                                            except:
                                                pass
                                    
                                    # Get earliest IN and latest OUT for each date
                                    frappe_daily = {}
                                    for date_key, records in frappe_by_date.items():
                                        in_times = sorted(records['IN'], key=lambda x: x['datetime'])
                                        out_times = sorted(records['OUT'], key=lambda x: x['datetime'], reverse=True)
                                        
                                        frappe_daily[date_key] = {
                                            'IN': in_times[0]['time'] if in_times else None,
                                            'OUT': out_times[0]['time'] if out_times else None
                                        }
                                    
                                    # Build CSV daily data
                                    csv_daily = {}
                                    for record in csv_data:
                                        csv_daily[record['date']] = {
                                            'IN': record['in_time'] if record['in_time'] else None,
                                            'OUT': record['out_time'] if record['out_time'] else None
                                        }
                                    
                                    # Compare
                                    all_dates = sorted(set(list(csv_daily.keys()) + list(frappe_daily.keys())))
                                    
                                    correct_matches = []
                                    mismatches = []
                                    csv_extra = []
                                    frappe_extra = []
                                    
                                    for check_date in all_dates:
                                        csv_record = csv_daily.get(check_date)
                                        frappe_record = frappe_daily.get(check_date)
                                        
                                        if csv_record and frappe_record:
                                            if csv_record['IN'] == frappe_record['IN'] and csv_record['OUT'] == frappe_record['OUT']:
                                                correct_matches.append(check_date)
                                            else:
                                                mismatches.append({
                                                    'date': check_date,
                                                    'csv_IN': csv_record['IN'],
                                                    'csv_OUT': csv_record['OUT'],
                                                    'frappe_IN': frappe_record['IN'],
                                                    'frappe_OUT': frappe_record['OUT']
                                                })
                                        elif csv_record and not frappe_record:
                                            csv_extra.append({
                                                'date': check_date,
                                                'IN': csv_record['IN'],
                                                'OUT': csv_record['OUT']
                                            })
                                        elif frappe_record and not csv_record:
                                            frappe_extra.append({
                                                'date': check_date,
                                                'IN': frappe_record['IN'],
                                                'OUT': frappe_record['OUT']
                                            })
                                    
                                    # Display results
                                    st.markdown("### 📊 Comparison Results")
                                    
                                    col1, col2, col3, col4 = st.columns(4)
                                    with col1:
                                        st.metric("✅ Perfect Matches", len(correct_matches), f"{len(correct_matches)/len(all_dates)*100:.1f}%")
                                    with col2:
                                        st.metric("❌ Mismatches", len(mismatches), f"{len(mismatches)/len(all_dates)*100:.1f}%")
                                    with col3:
                                        st.metric("📄 CSV Only", len(csv_extra), f"{len(csv_extra)/len(all_dates)*100:.1f}%")
                                    with col4:
                                        st.metric("🔵 Frappe Only", len(frappe_extra), f"{len(frappe_extra)/len(all_dates)*100:.1f}%")
                                    
                                    # Show mismatches
                                    if mismatches:
                                        st.markdown("#### ❌ Mismatches")
                                        mismatch_df = pd.DataFrame(mismatches)
                                        st.dataframe(mismatch_df, use_container_width=True, hide_index=True)
                                    
                                    # Show CSV extra
                                    if csv_extra:
                                        st.markdown("#### 📄 CSV Extra (In CSV but not in Frappe)")
                                        csv_extra_df = pd.DataFrame(csv_extra)
                                        st.dataframe(csv_extra_df, use_container_width=True, hide_index=True)
                                    
                                    # Show Frappe extra
                                    if frappe_extra:
                                        st.markdown("#### 🔵 Frappe Extra (In Frappe but not in CSV)")
                                        frappe_extra_df = pd.DataFrame(frappe_extra)
                                        st.dataframe(frappe_extra_df, use_container_width=True, hide_index=True)
                                    
                                except Exception as e:
                                    st.error(f"❌ Error: {e}")
                                    st.exception(e)
                else:
                    st.warning("⚠️ Could not parse CSV file. Please make sure it's in ngTeco format.")
                    
            except Exception as e:
                st.error(f"❌ Error reading CSV file: {e}")
                st.exception(e)
        else:
            st.info("👆 Please upload a ngTeco CSV file to compare.")


if __name__ == "__main__":
    main()

