import streamlit as st
from datetime import datetime
import pandas as pd
import os
from dotenv import load_dotenv
from employee_manager import create_employee_account, update_employee_account, delete_employee_account
from pymongo import MongoClient
import time

load_dotenv()

# MongoDB Setup
client = MongoClient(os.getenv("MONGODB_CLIENT"))
db = client["bulldog_office"]
employees_collection = db["employees"]

def get_profile_dataset(pd_output=True):
    items = list(employees_collection.find({}))  # Retrieve all employees, excluding MongoDB ID field
    if not pd_output:
        return items
    else:
        df = pd.DataFrame(items) if items else pd.DataFrame()
        if "date_joined" in df.columns:
            df["date_joined"] = pd.to_datetime(df["date_joined"], errors="coerce")
        return df

def emp_manage_main():
    st.title("Employee Management Panel")
    
    # Define column configurations
    column_configuration = {
        "username": st.column_config.TextColumn(
            "Username", help="The username", max_chars=100, required=True
        ),
        "full_name": st.column_config.TextColumn(
            "Full Name", help="The Full name of employee in the CSV input file", max_chars=100, required=True
        ),
        "date_joined": st.column_config.DateColumn("Date Joined", help="employee Join Date"),
        "_id": st.column_config.TextColumn("employee ID", disabled=True),
        "email": st.column_config.TextColumn("Email", help="The employee's email address", required=True),
        "hours_overtime": st.column_config.TextColumn(
            "Hours Overtime", help="The employee's overtime hours", max_chars=100, required=False, default="00:00"
        ),
    }
    
    all_data = get_profile_dataset()
    if not all_data.empty:
        st.data_editor(
            all_data,
            key="employees_manager",
            column_order=("full_name", "username", "email", "hours_overtime", "date_joined", "_id"),
            disabled=("_id",),
            column_config=column_configuration,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
        )
    else:
        st.warning("No registered employees found!")
        st.subheader("**Create an employee record**")
        with st.form("employee_create"):
            form_full_name = st.text_input("Full name")
            form_username = st.text_input("Username")
            form_email = st.text_input("Email")
            if st.form_submit_button():
                st.session_state["employees_manager"] = {}
                st.session_state["employees_manager"]["added_rows"] = [{
                    "username": form_username, "email": form_email, "full_name": form_full_name
                }]
    
    employees_manager = st.session_state.get("employees_manager", {})
    added_employees = employees_manager.get("added_rows")
    edited_employees = employees_manager.get("edited_rows")
    deleted_employees = employees_manager.get("deleted_rows")
    
    if added_employees:
        for employee in added_employees:
            account_is_created = create_employee_account(**employee)
            with st.status("Loading employee creation process...", expanded=True) as status:
                if account_is_created["success"]:
                    del st.session_state["employees_manager"]
                    status.update(label="employee Account Creation Completed!", state="complete", expanded=True)
                    st.switch_page("./pages/Employee Management.py")
                else:
                    st.error(account_is_created["message"])
                    status.update(label="employee Account Creation Failed!", state="error", expanded=True)
    
    elif edited_employees:
        updated_employee_data = edited_employees
        employee_index = list(updated_employee_data.keys())[0]
        if "date_joined" in updated_employee_data[employee_index]:
            updated_employee_data[employee_index]["date_joined"] = pd.to_datetime(
                updated_employee_data[employee_index]["date_joined"], format="%Y-%m-%d", errors="coerce"
            )
        all_employees = get_profile_dataset(pd_output=False)
        old_employee_data = all_employees[employee_index]
        account_is_updated = update_employee_account(old_employee_data["_id"], **updated_employee_data[employee_index])
        with st.status("Loading employee management process...", expanded=True) as status:
            st.write("Searching for exact employee with username or email...")
            if account_is_updated["success"]:
                del st.session_state["employees_manager"]
                st.write("Updating employee Account...")
                st.success("employee Updated!")
                status.update(label="employee Account Update Completed!", state="complete", expanded=True)
                time.sleep(3)
                st.switch_page("./pages/Employee Management.py")
            else:
                st.error(account_is_updated["message"])
                status.update(label="employee Account Update Failed!", state="error", expanded=True)
    
    elif deleted_employees:
        all_employees = get_profile_dataset(pd_output=False)
        for employee in deleted_employees:
            old_employee_data = all_employees[employee]
            employee_deleted = delete_employee_account(old_employee_data["_id"])
            with st.status("Loading employee management process...", expanded=True) as status:
                if employee_deleted["success"]:
                    st.write("Deleting employee Account...")
                    st.success("employee Deleted!")
                    status.update(label="employee Account Deletion Completed!", state="complete", expanded=True)
                else:
                    st.error(employee_deleted["message"])
                    status.update(label="employee Account Deletion Failed!", state="error", expanded=True)

if __name__ == "__main__":
    emp_manage_main()