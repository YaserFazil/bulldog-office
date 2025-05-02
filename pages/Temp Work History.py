from employee_manager import *
from utils import *
import streamlit as st


st.title("Temp Work History")
def reset_file():
    if "temp_work_data" in st.session_state:
        st.session_state.pop("temp_work_data")
        st.session_state.pop("temp_employee_name")
        if "selected_temp_user" in st.session_state:
            st.session_state.pop("selected_temp_user")
all_usernames = get_users()
selected_username = st.selectbox("Select Employee", all_usernames)
if "selected_temp_user" in st.session_state and st.session_state["selected_temp_user"] != selected_username:
    user_id, full_name = get_user_id(selected_username)
    work_history_asked, first_date, last_date = fetch_employee_temp_work_history(user_id)
    if work_history_asked.empty == False:
        st.session_state["temp_work_data"] = work_history_asked
    else:
        reset_file()
        st.warning("No temp work history found for the selected employee.")
    st.session_state["temp_employee_name"] = full_name
    st.session_state["temp_user_id"] = user_id
    st.session_state["selected_temp_user"] = selected_username
elif "selected_temp_user" not in st.session_state:
    user_id, full_name = get_user_id(selected_username)
    work_history_asked, first_date, last_date = fetch_employee_temp_work_history(user_id)
    if work_history_asked.empty == False:
        st.session_state["temp_work_data"] = work_history_asked
    else:
        reset_file()
        st.warning("No temp work history found for the selected employee.")
    st.session_state["temp_employee_name"] = full_name
    st.session_state["temp_user_id"] = user_id
    st.session_state["selected_temp_user"] = selected_username


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
        delete_employee_temp_work_history(st.session_state["temp_user_id"])
        st.success("Temp work history reset successfully.")
        st.rerun()