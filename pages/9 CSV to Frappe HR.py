import streamlit as st
import pandas as pd
from datetime import datetime
import io
from streamlit_extras.switch_page_button import switch_page
import os
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables and setup MongoDB
load_dotenv()
client = MongoClient(os.getenv("MONGODB_CLIENT"))
db = client["bulldog_office"]
employees_collection = db["employees"]

def get_username_by_full_name(full_name):
    """
    Look up employee username2 (or username) by full name in MongoDB.
    
    Args:
        full_name: Employee full name to search for
        
    Returns:
        username2 if found, otherwise username, otherwise the original full_name
    """
    try:
        # Clean the full name (remove any ID in parentheses)
        clean_name = full_name
        if '(' in full_name and ')' in full_name:
            clean_name = full_name.split('(')[0].strip()
        
        # Try exact match first
        employee = employees_collection.find_one(
            {"full_name": clean_name},
            {"username2": 1, "username": 1}
        )
        
        if employee:
            # Prefer username2 if it exists, otherwise use username
            if "username2" in employee and employee["username2"]:
                return employee["username2"]
            elif "username" in employee and employee["username"]:
                return employee["username"]
        
        # Try case-insensitive match
        employee = employees_collection.find_one(
            {"full_name": {"$regex": f"^{clean_name}$", "$options": "i"}},
            {"username2": 1, "username": 1}
        )
        
        if employee:
            if "username2" in employee and employee["username2"]:
                return employee["username2"]
            elif "username" in employee and employee["username"]:
                return employee["username"]
        
        # If no match found, return the cleaned name
        st.warning(f"⚠️ Employee '{clean_name}' not found in database. Using name as-is.")
        return clean_name
        
    except Exception as e:
        st.error(f"❌ Error looking up employee: {str(e)}")
        return full_name

def check_for_missing_times(parsed_data):
    """
    Check if there are any missing IN or OUT times in the parsed data.
    
    Returns:
        dict with 'has_missing', 'missing_details' list
    """
    missing_details = []
    
    for record in parsed_data['records']:
        date_str = record['date']
        day = record['day']
        in_time = record['in_time']
        out_time = record['out_time']
        
        # Parse date for display
        try:
            date_obj = datetime.strptime(date_str, '%Y%m%d')
            date_display = date_obj.strftime('%d-%m-%Y')
        except:
            date_display = date_str
        
        # Check for missing IN
        if not in_time or in_time == 'Missing OUT':
            missing_details.append({
                'date': date_display,
                'day': day,
                'type': 'Missing IN',
                'note': 'No check-in time recorded'
            })
        
        # Check for missing OUT
        if not out_time or out_time == 'Missing OUT':
            missing_details.append({
                'date': date_display,
                'day': day,
                'type': 'Missing OUT',
                'note': 'No check-out time recorded'
            })
    
    return {
        'has_missing': len(missing_details) > 0,
        'missing_details': missing_details
    }

def parse_ngtecotime_csv(file_content):
    """
    Parse NGTecoTime CSV format and extract relevant information.
    
    Returns:
        dict with 'employee', 'pay_period', and 'records' (list of dicts)
    """
    lines = file_content.decode('utf-8').strip().split('\n')
    
    # Extract metadata
    employee_name = None
    pay_period = None
    
    for line in lines[:5]:  # Check first 5 lines for metadata
        if line.startswith('Pay Period'):
            parts = line.split(',')
            for part in parts:
                if part and part != 'Pay Period' and part.strip():
                    pay_period = part.strip()
                    break
        elif line.startswith('Employee'):
            parts = line.split(',')
            for part in parts:
                if part and part != 'Employee' and part.strip():
                    employee_name = part.strip()
                    # Extract employee ID from parentheses if present
                    # e.g., "Patricia Bruckner (3)" -> "Patricia Bruckner"
                    if '(' in employee_name and ')' in employee_name:
                        # Keep the full name with ID for now
                        pass
                    break
    
    # Find the data rows
    records = []
    data_started = False
    
    for line in lines:
        # Skip until we find the Date column header
        if 'Date' in line and 'IN' in line and 'OUT' in line:
            data_started = True
            continue
        
        if not data_started:
            continue
        
        # Stop at Total Hours or empty lines
        if line.startswith('Total Hours') or not line.strip():
            break
        
        parts = [p.strip() for p in line.split(',')]
        
        if len(parts) >= 4:
            day = parts[0] if parts[0] else None
            date_str = parts[1] if parts[1] else None
            in_time = parts[2] if parts[2] else None
            out_time = parts[3] if parts[3] else None
            
            # Skip rows without a date
            if not date_str or not date_str.isdigit():
                continue
            
            # Skip weekend/empty rows if both IN and OUT are empty
            if not in_time and not out_time:
                continue
            
            records.append({
                'day': day,
                'date': date_str,
                'in_time': in_time,
                'out_time': out_time
            })
    
    return {
        'employee': employee_name,
        'pay_period': pay_period,
        'records': records
    }

def convert_to_frappe_format(parsed_data, include_ids=True):
    """
    Convert parsed NGTecoTime data to Frappe HR format.
    
    Returns:
        pandas DataFrame with columns: [ID], Employee, Time, Log Type
    """
    frappe_records = []
    employee_full_name = parsed_data['employee']
    
    # Look up username2 (or username) from MongoDB by full name
    employee_username = get_username_by_full_name(employee_full_name)
    
    sequence = 1
    
    for record in parsed_data['records']:
        date_str = record['date']
        
        # Parse date from YYYYMMDD format
        try:
            date_obj = datetime.strptime(date_str, '%Y%m%d')
        except:
            continue
        
        # Process IN time
        if record['in_time'] and record['in_time'] != 'Missing OUT':
            try:
                # Parse time (can be H:MM or HH:MM)
                time_parts = record['in_time'].split(':')
                hours = int(time_parts[0])
                minutes = int(time_parts[1])
                
                # Create full datetime string in Frappe format: DD-MM-YYYY HH:MM:SS
                datetime_str = date_obj.strftime('%d-%m-%Y') + f' {hours:02d}:{minutes:02d}:00'
                
                frappe_record = {
                    'Employee': employee_username,
                    'Time': datetime_str,
                    'Log Type': 'IN'
                }
                
                if include_ids:
                    month = date_obj.month
                    record_id = f"EMP-CKIN-{month:02d}-{date_obj.year}-{sequence:06d}"
                    frappe_record['ID'] = record_id
                    sequence += 1
                
                frappe_records.append(frappe_record)
            except Exception as e:
                st.warning(f"Could not parse IN time '{record['in_time']}' for date {date_str}: {e}")
        
        # Process OUT time
        if record['out_time'] and record['out_time'] != 'Missing OUT':
            try:
                # Parse time (can be H:MM or HH:MM)
                time_parts = record['out_time'].split(':')
                hours = int(time_parts[0])
                minutes = int(time_parts[1])
                
                # Create full datetime string in Frappe format: DD-MM-YYYY HH:MM:SS
                datetime_str = date_obj.strftime('%d-%m-%Y') + f' {hours:02d}:{minutes:02d}:00'
                
                frappe_record = {
                    'Employee': employee_username,
                    'Time': datetime_str,
                    'Log Type': 'OUT'
                }
                
                if include_ids:
                    month = date_obj.month
                    record_id = f"EMP-CKIN-{month:02d}-{date_obj.year}-{sequence:06d}"
                    frappe_record['ID'] = record_id
                    sequence += 1
                
                frappe_records.append(frappe_record)
            except Exception as e:
                st.warning(f"Could not parse OUT time '{record['out_time']}' for date {date_str}: {e}")
    
    # Create DataFrame with proper column order
    if frappe_records:
        df = pd.DataFrame(frappe_records)
        if include_ids:
            df = df[['ID', 'Employee', 'Time', 'Log Type']]
        else:
            df = df[['Employee', 'Time', 'Log Type']]
        return df
    else:
        return pd.DataFrame()

def main():
    """Main Streamlit app for CSV to Frappe HR conversion."""
    
    # Check login
    if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
        st.error("You need to log in first.")
        st.session_state["logged_in"] = False
        st.session_state["user_id"] = None
        switch_page("Login")
        return
    
    st.title("📄 CSV to Frappe HR Converter")
    
    st.markdown("""
    <div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; border-left: 4px solid #4caf50; margin-bottom: 20px;">
        <strong>ℹ️ About This Tool</strong><br>
        Upload timecard CSV files in NGTecoTime format and convert them to Frappe HR compatible Excel/CSV files.
        The tool automatically extracts employee information, formats dates and times, and generates the proper output format.
    </div>
    """, unsafe_allow_html=True)
    
    # File upload section
    st.markdown("### 📁 Upload CSV File")
    uploaded_file = st.file_uploader(
        "Choose a CSV file in NGTecoTime format",
        type=['csv'],
        help="Upload a timecard CSV file with employee check-in/out data"
    )
    
    if uploaded_file is not None:
        try:
            # Read and parse the CSV
            file_content = uploaded_file.read()
            parsed_data = parse_ngtecotime_csv(file_content)
            
            # Display extracted information
            st.markdown("### 📊 Extracted Information")
            
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**Employee:** {parsed_data['employee']}")
            with col2:
                st.info(f"**Pay Period:** {parsed_data['pay_period']}")
            
            st.success(f"✅ Found {len(parsed_data['records'])} working day records")
            
            # Check for missing IN/OUT times
            missing_check = check_for_missing_times(parsed_data)
            
            if missing_check['has_missing']:
                st.markdown("### ⚠️ Missing Time Records Detected")
                st.warning(f"**Warning**: Found {len(missing_check['missing_details'])} missing check-in or check-out time(s).")
                
                # Show missing records in a table
                with st.expander("📋 View Missing Records", expanded=True):
                    missing_df = pd.DataFrame(missing_check['missing_details'])
                    st.dataframe(
                        missing_df[['date', 'day', 'type', 'note']], 
                        use_container_width=True,
                        hide_index=True
                    )
                    st.info("ℹ️ These records will only have the available time (IN or OUT) in the output. The missing time will be skipped.")
            
            # Show preview of original data
            with st.expander("🔍 View Original Data Preview", expanded=False):
                preview_data = []
                for record in parsed_data['records'][:10]:  # Show first 10
                    preview_data.append({
                        'Day': record['day'],
                        'Date': record['date'],
                        'IN': record['in_time'] if record['in_time'] else '-',
                        'OUT': record['out_time'] if record['out_time'] else '-'
                    })
                st.dataframe(pd.DataFrame(preview_data), use_container_width=True)
            
            # Conversion options
            st.markdown("### ⚙️ Conversion Options")
            
            col1, col2 = st.columns(2)
            with col1:
                include_ids = st.checkbox(
                    "Include Unique IDs",
                    value=True,
                    help="Generate unique IDs in format: EMP-CKIN-{month}-{year}-{sequence}"
                )
            with col2:
                export_format = st.radio(
                    "Output Format",
                    options=["Excel (.xlsx)", "CSV (.csv)", "Both"],
                    horizontal=True
                )
            
            # Confirmation checkbox for missing times
            proceed_with_conversion = True
            if missing_check['has_missing']:
                st.markdown("### ✅ Confirmation Required")
                proceed_with_conversion = st.checkbox(
                    "I understand there are missing times and want to proceed with conversion",
                    value=False,
                    help="Check this box to confirm you want to convert the data despite missing IN/OUT times"
                )
                
                if not proceed_with_conversion:
                    st.info("👆 Please confirm above to proceed with conversion.")
            
            # Convert button
            convert_button_disabled = missing_check['has_missing'] and not proceed_with_conversion
            if st.button(
                "🔄 Convert to Frappe HR Format", 
                type="primary", 
                use_container_width=True,
                disabled=convert_button_disabled
            ):
                with st.spinner("Converting data..."):
                    frappe_df = convert_to_frappe_format(parsed_data, include_ids=include_ids)
                    
                    if frappe_df.empty:
                        st.error("❌ No valid records found to convert!")
                    else:
                        st.success(f"✅ Successfully converted {len(frappe_df)} records!")
                        
                        # Show preview of converted data
                        st.markdown("### 📋 Converted Data Preview")
                        st.dataframe(frappe_df.head(20), use_container_width=True)
                        
                        # Prepare download files
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        employee_slug = parsed_data['employee'].split('(')[0].strip().replace(' ', '_').lower()
                        
                        st.markdown("### 💾 Download Files")
                        
                        download_col1, download_col2 = st.columns(2)
                        
                        # Excel download
                        if export_format in ["Excel (.xlsx)", "Both"]:
                            excel_buffer = io.BytesIO()
                            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                                frappe_df.to_excel(writer, index=False, sheet_name='Employee Checkin')
                            excel_buffer.seek(0)
                            
                            with download_col1:
                                st.download_button(
                                    label="📥 Download Excel File",
                                    data=excel_buffer,
                                    file_name=f"frappe_hr_{employee_slug}_{timestamp}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    use_container_width=True
                                )
                        
                        # CSV download
                        if export_format in ["CSV (.csv)", "Both"]:
                            csv_buffer = io.StringIO()
                            frappe_df.to_csv(csv_buffer, index=False)
                            csv_data = csv_buffer.getvalue()
                            
                            with download_col2:
                                st.download_button(
                                    label="📥 Download CSV File",
                                    data=csv_data,
                                    file_name=f"frappe_hr_{employee_slug}_{timestamp}.csv",
                                    mime="text/csv",
                                    use_container_width=True
                                )
                        
                        # Show summary statistics
                        st.markdown("### 📈 Conversion Summary")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            in_count = len(frappe_df[frappe_df['Log Type'] == 'IN'])
                            st.metric("IN Records", in_count)
                        with col2:
                            out_count = len(frappe_df[frappe_df['Log Type'] == 'OUT'])
                            st.metric("OUT Records", out_count)
                        with col3:
                            st.metric("Total Records", len(frappe_df))
        
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")
            st.exception(e)
    
    else:
        # Show usage instructions
        st.markdown("### 📖 How to Use")
        st.markdown("""
        1. **Upload** your CSV file using the file uploader above
        2. **Review** the extracted employee information and data preview
        3. **Configure** conversion options (IDs and output format)
        4. **Click Convert** to generate Frappe HR compatible files
        5. **Download** the Excel and/or CSV files
        
        #### Expected CSV Format:
        ```
        ,,,,Timecard Report,,
        Pay Period,,,20250825-20250831,,,
        Employee,,,Patricia Bruckner (3),,,
        Date,,IN,OUT,Work Time, Daily Total, Note
        MON,20250825,17:40,,,,
        TUE,20250826,8:37,17:19,8.7,8.7,
        ...
        ```
        
        #### Output Format:
        - **With IDs**: ID, Employee, Time, Log Type
        - **Without IDs**: Employee, Time, Log Type
        - **Time Format**: DD-MM-YYYY HH:MM:SS
        - **Log Type**: IN or OUT
        """)
        
        # Show example output
        st.markdown("### 📊 Example Output")
        example_df = pd.DataFrame([
            {'ID': 'EMP-CKIN-08-2025-000001', 'Employee': 'patricia.bruckner', 'Time': '25-08-2025 17:40:00', 'Log Type': 'IN'},
            {'ID': 'EMP-CKIN-08-2025-000002', 'Employee': 'patricia.bruckner', 'Time': '26-08-2025 08:37:00', 'Log Type': 'IN'},
            {'ID': 'EMP-CKIN-08-2025-000003', 'Employee': 'patricia.bruckner', 'Time': '26-08-2025 17:19:00', 'Log Type': 'OUT'},
            {'ID': 'EMP-CKIN-08-2025-000004', 'Employee': 'patricia.bruckner', 'Time': '29-08-2025 08:30:00', 'Log Type': 'IN'},
            {'ID': 'EMP-CKIN-08-2025-000005', 'Employee': 'patricia.bruckner', 'Time': '29-08-2025 18:25:00', 'Log Type': 'OUT'},
        ])
        st.dataframe(example_df, use_container_width=True)
        
        st.info("ℹ️ **Note**: Employee names in the output are looked up from the MongoDB database (username2 or username field) based on the full name in the CSV file.")

if __name__ == "__main__":
    main()

