import streamlit as st
from datetime import datetime
import pandas as pd
import os
from dotenv import load_dotenv
from employee_manager import create_user_account, update_user_account, delete_user_account
from pymongo import MongoClient
import time

load_dotenv()

# MongoDB Setup
client = MongoClient(os.getenv("MONGODB_CLIENT"))
db = client["bulldog_office"]
employees_collection = db["employees"]

def get_profile_dataset(pd_output=True):
    items = list(employees_collection.find({}))  # Retrieve all users, excluding MongoDB ID field
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
        "date_joined": st.column_config.DateColumn("Date Joined", help="User Join Date"),
        "_id": st.column_config.TextColumn("User ID", disabled=True),
        "email": st.column_config.TextColumn("Email", help="The user's email address", required=True),
        "hours_overtime": st.column_config.TextColumn(
            "Hours Overtime", help="The user's overtime hours", max_chars=100, required=False, default="00:00"
        ),
    }
    
    all_data = get_profile_dataset()
    if not all_data.empty:
        st.data_editor(
            all_data,
            key="users_manager",
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
                st.session_state["users_manager"] = {}
                st.session_state["users_manager"]["added_rows"] = [{
                    "username": form_username, "email": form_email, "full_name": form_full_name
                }]
    
    users_manager = st.session_state.get("users_manager", {})
    added_users = users_manager.get("added_rows")
    edited_users = users_manager.get("edited_rows")
    deleted_users = users_manager.get("deleted_rows")
    
    if added_users:
        for user in added_users:
            account_is_created = create_user_account(**user)
            with st.status("Loading user creation process...", expanded=True) as status:
                if account_is_created["success"]:
                    del st.session_state["users_manager"]
                    status.update(label="User Account Creation Completed!", state="complete", expanded=True)
                    st.switch_page("./pages/Employee Management.py")
                else:
                    st.error(account_is_created["message"])
                    status.update(label="User Account Creation Failed!", state="error", expanded=True)
    
    elif edited_users:
        updated_user_data = edited_users
        user_index = list(updated_user_data.keys())[0]
        if "date_joined" in updated_user_data[user_index]:
            updated_user_data[user_index]["date_joined"] = pd.to_datetime(
                updated_user_data[user_index]["date_joined"], format="%Y-%m-%d", errors="coerce"
            )
        all_users = get_profile_dataset(pd_output=False)
        old_user_data = all_users[user_index]
        account_is_updated = update_user_account(old_user_data["_id"], **updated_user_data[user_index])
        with st.status("Loading user management process...", expanded=True) as status:
            st.write("Searching for exact user with username or email...")
            if account_is_updated["success"]:
                del st.session_state["users_manager"]
                st.write("Updating User Account...")
                st.success("User Updated!")
                status.update(label="User Account Update Completed!", state="complete", expanded=True)
                time.sleep(3)
                st.switch_page("./pages/Employee Management.py")
            else:
                st.error(account_is_updated["message"])
                status.update(label="User Account Update Failed!", state="error", expanded=True)
    
    elif deleted_users:
        all_users = get_profile_dataset(pd_output=False)
        for user in deleted_users:
            old_user_data = all_users[user]
            user_deleted = delete_user_account(old_user_data["_id"])
            with st.status("Loading user management process...", expanded=True) as status:
                if user_deleted["success"]:
                    st.write("Deleting User Account...")
                    st.success("User Deleted!")
                    status.update(label="User Account Deletion Completed!", state="complete", expanded=True)
                else:
                    st.error(user_deleted["message"])
                    status.update(label="User Account Deletion Failed!", state="error", expanded=True)

if __name__ == "__main__":
    emp_manage_main()