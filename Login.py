import streamlit as st
import hashlib
import time
import streamlit.components.v1 as components
from employee_manager import users_collection  # Import the MongoDB collection for users
from streamlit_extras.switch_page_button import switch_page

# Hash password using SHA-256
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Authenticate user
def authenticate_user(username_or_email, password):
    # hashed_pw = hash_password(password)
    user = users_collection.find_one({
        "$or": [{"email": username_or_email}, {"username": username_or_email}],
        "password": password
    })
    return user

# Main login logic
def main():
    st.set_page_config(page_title="Login", page_icon="🔐", initial_sidebar_state="collapsed")
    hide_sidebar = """
        <style>
            [data-testid="stSidebar"] {
                display: none;
            }
            [data-testid="collapsedControl"] {
                display: none;
            }
        </style>
    """
    st.markdown(hide_sidebar, unsafe_allow_html=True)
    # If already logged in, redirect to Home
    if st.session_state.get("logged_in"):
        switch_page("Home")  # Name of your Home.py page (no .py)
        return

    st.title("🔐 Login Page")

    with st.form("login_form"):
        username_or_email = st.text_input("Email or Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            user = authenticate_user(username_or_email, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.user_id = str(user["_id"])
                st.success("Logged in successfully!")
                time.sleep(1)
                switch_page("Home")  # Name of your Home.py page (no .py)
            else:
                st.error("Invalid username/email or password")

if __name__ == "__main__":
    main()
