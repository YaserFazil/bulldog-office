from employee_manager import *
from utils import *
import streamlit as st
from streamlit_extras.switch_page_button import switch_page

st.title("Temp Work History")
if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
    st.error("You need to log in first.")
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = None
    switch_page("Login")  # Name of your Home.py page (no .py)
def reset_file():
    if "temp_work_data" in st.session_state:
        st.session_state.pop("temp_work_data")
        st.session_state.pop("temp_employee_name")
        if "selected_temp_employee" in st.session_state:
            st.session_state.pop("selected_temp_employee")
all_usernames = get_employees()
selected_username = st.selectbox("Select Employee", all_usernames)
if "selected_temp_employee" in st.session_state and st.session_state["selected_temp_employee"] != selected_username:
    employee_id, full_name = get_employee_id(selected_username)
    work_history_asked, first_date, last_date = fetch_employee_temp_work_history(employee_id)
    if work_history_asked.empty == False:
        st.session_state["temp_work_data"] = work_history_asked
    else:
        reset_file()
        st.warning("No temp work history found for the selected employee.")
    st.session_state["temp_employee_name"] = full_name
    st.session_state["temp_employee_id"] = employee_id
    st.session_state["selected_temp_employee"] = selected_username
elif "selected_temp_employee" not in st.session_state:
    employee_id, full_name = get_employee_id(selected_username)
    work_history_asked, first_date, last_date = fetch_employee_temp_work_history(employee_id)
    if work_history_asked.empty == False:
        st.session_state["temp_work_data"] = work_history_asked
    else:
        reset_file()
        st.warning("No temp work history found for the selected employee.")
    st.session_state["temp_employee_name"] = full_name
    st.session_state["temp_employee_id"] = employee_id
    st.session_state["selected_temp_employee"] = selected_username


if "temp_work_data" in st.session_state:
    work_history_asked = st.session_state["temp_work_data"]
    first_date = work_history_asked["Date"].min()
    last_date = work_history_asked["Date"].max()
    st.write(f"Temp work history for {st.session_state['temp_employee_name']}")
    st.write(f"From {first_date} to {last_date}")
    st.dataframe(work_history_asked)
    st.write("Click the button below to reset the temp work history.")
    if st.button(f"Reset Temp Work History for {st.session_state['temp_employee_name']}"):
        reset_file()
        delete_employee_temp_work_history(st.session_state["temp_employee_id"])
        st.success("Temp work history reset successfully.")
        st.rerun()