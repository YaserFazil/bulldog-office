import streamlit as st
import pandas as pd
import io
from employee_manager import *
from streamlit_extras.switch_page_button import switch_page
def parse_bulk_timecard(input_data):
    try:
        if isinstance(input_data, pd.DataFrame):
            lines = [','.join(map(str, row)) for row in input_data.values.tolist()]
        elif isinstance(input_data, str):
            # Treat as raw CSV content
            f = io.StringIO(input_data)
            lines = [line.strip() for line in f if line.strip()]
        else:
            raise ValueError("Input must be a file path, raw CSV string, or a DataFrame")

        employees = []
        i = 0
        while i < len(lines):
            if lines[i].startswith('Pay Period,,,'):
                pay_period = lines[i].split(',')[3]
                i += 1
                employee_name = lines[i].split(',')[3]
                i += 2  # Skip to header line
                
                entries = []
                while i < len(lines) and not lines[i].startswith('Total Hours'):
                    if lines[i]:
                        cols = lines[i].split(',')
                        entry = {
                            'Day': cols[0] if len(cols) > 0 else '',
                            'Date': pd.to_datetime(cols[1], format="%Y%m%d", errors="coerce").date() if len(cols) > 1 else '',
                            'IN': cols[2] if len(cols) > 2 else '',
                            'OUT': cols[3] if len(cols) > 3 else '',
                            'Note': ','.join(cols[6:]).strip() if len(cols) > 6 else ''
                        }
                        entries.append(entry)
                    i += 1
                employees.append({
                    'Employee': employee_name,
                    'Entries': entries
                })

            else:
                i += 1

        # Create flat list for DataFrame
        flat_data = []
        for emp in employees:
            for entry in emp['Entries']:
                flat_data.append({
                    'Employee': emp['Employee'],
                    **entry
                })
        
        df = pd.DataFrame(flat_data)
        return df, employees
    except Exception as e:
        st.error(f"Error parsing timecard: {e}")
        return pd.DataFrame(), []

# Streamlit App
if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
    st.error("You need to log in first.")
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = None
    switch_page("Login")  # Name of your Home.py page (no .py)
    
st.title("🕒 Bulk Timecard CSV Parser")

uploaded_filee = st.file_uploader("Upload CSV file", type=["csv"], key="file_uploaderh")

if uploaded_filee is not None:
    stringio = uploaded_filee.getvalue().decode("utf-8")
    df_parsed, employees_data = parse_bulk_timecard(stringio)


    st.subheader("📋 Structured Timesheet Table")
    edited_df = st.data_editor(df_parsed, num_rows="dynamic", use_container_width=True)
    if st.button("💾 Save Changes to Database"):
        with st.spinner("Saving..."):
            for _, row in edited_df.iterrows():
                employee_id, username = get_employee_id(row['Employee'])
                data = {
                    'Day': row['Day'],
                    'Date': row['Date'],
                    'IN': row['IN'],
                    'OUT': row['OUT'],
                    'Note': row['Note']
                }
                upsert_employee_temp_work_history(data, employee_id, username)
        st.success("Changes saved to database successfully.")