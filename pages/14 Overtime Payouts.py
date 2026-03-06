import pandas as pd
import streamlit as st
from datetime import date

from streamlit_extras.switch_page_button import switch_page

from employee_manager import (
    create_overtime_payout,
    delete_overtime_payout,
    fetch_overtime_payouts,
)
from frappe_client import fetch_employee_time_config, fetch_frappe_employees
from utils import decimal_hours_to_hhmmss, hhmm_to_decimal


def _sum_payout_hours(payout_records):
    total_hours = 0.0
    for payout in payout_records:
        payout_hours = payout.get("payout_hours")
        if payout_hours:
            total_hours += hhmm_to_decimal(str(payout_hours))
    return total_hours


def _build_employee_options(employees):
    employee_options = []
    code_by_label = {}
    name_by_code = {}

    for employee in employees:
        employee_code = employee.get("name")
        employee_name = employee.get("employee_name") or employee_code
        label = f"{employee_name} ({employee_code})"
        employee_options.append(label)
        code_by_label[label] = employee_code
        name_by_code[employee_code] = employee_name

    return employee_options, code_by_label, name_by_code


def main():
    if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
        st.error("You need to log in first.")
        st.session_state["logged_in"] = False
        st.session_state["user_id"] = None
        switch_page("Login")
        return

    st.title("Frappe HR - Overtime Payouts")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(
            """
            <div style="background-color: #e3f2fd; padding: 10px; border-radius: 5px; border-left: 4px solid #2196f3; margin-bottom: 20px;">
                <strong>Track overtime payouts</strong><br>
                Record paid-out overtime hours in MongoDB. These payouts are deducted from overtime balances starting on the payout date and are shown in Frappe HR PDF reports for the selected period.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        if st.button("📚 View Documentation", use_container_width=True):
            switch_page("documentation")

    if "frappe_employees" not in st.session_state:
        try:
            with st.spinner("Loading employees from Frappe HR..."):
                st.session_state["frappe_employees"] = fetch_frappe_employees()
        except Exception as e:
            st.error(f"Failed to load employees from Frappe HR: {e}")
            st.session_state["frappe_employees"] = []

    employees = st.session_state.get("frappe_employees", [])
    employee_options, code_by_label, name_by_code = _build_employee_options(employees)

    if not employee_options:
        st.warning("No employees available from Frappe HR.")
        return

    selected_label = st.selectbox("Frappe Employee", employee_options)
    employee_code = code_by_label[selected_label]
    employee_name = name_by_code.get(employee_code, employee_code)

    today = date.today()
    employee_payouts = fetch_overtime_payouts(employee_code=employee_code)
    paid_out_through_today_decimal = _sum_payout_hours(
        [payout for payout in employee_payouts if payout.get("payout_date") and payout["payout_date"] <= today]
    )

    frappe_balance_before_payouts = "00:00"
    adjusted_balance_after_payouts = "00:00"
    try:
        time_config = fetch_employee_time_config(employee_code, report_start_date=today)
        frappe_balance_before_payouts = time_config.get("initial_overtime") or "00:00"
        adjusted_balance_after_payouts = decimal_hours_to_hhmmss(
            hhmm_to_decimal(frappe_balance_before_payouts) - paid_out_through_today_decimal
        )
    except Exception as e:
        st.warning(f"Could not load current overtime balance from Frappe HR: {e}")

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    with metric_col1:
        st.metric("Frappe Balance Before Payouts", frappe_balance_before_payouts)
    with metric_col2:
        st.metric("Paid Out Through Today", decimal_hours_to_hhmmss(paid_out_through_today_decimal))
    with metric_col3:
        st.metric("Estimated Balance After Payouts", adjusted_balance_after_payouts)

    st.markdown("### Record New Payout")
    with st.form("create_overtime_payout_form", clear_on_submit=True):
        form_col1, form_col2 = st.columns(2)
        with form_col1:
            payout_date = st.date_input("Payout Date", value=today)
        with form_col2:
            payout_hours = st.text_input("Paid-Out Overtime Hours", value="00:00")
        note = st.text_input("Note (optional)", placeholder="Optional payroll note")
        submit_payout = st.form_submit_button("Save Overtime Payout", use_container_width=True)

        if submit_payout:
            try:
                paid_out_decimal = hhmm_to_decimal(payout_hours.strip())
            except Exception:
                st.error("Paid-out overtime hours must use HH:MM format, for example 02:30.")
                paid_out_decimal = None

            if paid_out_decimal is None:
                pass
            elif paid_out_decimal <= 0:
                st.error("Paid-out overtime hours must be greater than 00:00.")
            else:
                result = create_overtime_payout(
                    employee_code=employee_code,
                    employee_name=employee_name,
                    payout_date=payout_date,
                    payout_hours=decimal_hours_to_hhmmss(paid_out_decimal),
                    note=note,
                )
                if result["success"]:
                    st.success(result["message"])
                    st.rerun()
                else:
                    st.error(result["message"])

    st.markdown("### Existing Payouts")
    if not employee_payouts:
        st.info("No overtime payouts recorded for this employee yet.")
        return

    payouts_df = pd.DataFrame(employee_payouts)
    payouts_df["payout_date"] = pd.to_datetime(payouts_df["payout_date"]).dt.date
    payouts_df = payouts_df.sort_values("payout_date", ascending=False).reset_index(drop=True)

    st.dataframe(
        payouts_df[["payout_date", "payout_hours", "note"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "payout_date": st.column_config.DateColumn("Payout Date"),
            "payout_hours": st.column_config.TextColumn("Paid-Out Hours"),
            "note": st.column_config.TextColumn("Note"),
        },
    )

    delete_options = {}
    for idx, row in payouts_df.iterrows():
        label = f"{idx + 1}. {row['payout_date']} - {row['payout_hours']}"
        if row.get("note"):
            label += f" - {row['note']}"
        delete_options[label] = row["_id"]
    selected_delete_label = st.selectbox(
        "Select a payout to delete",
        options=list(delete_options.keys()),
        key="overtime_payout_delete_selector",
    )

    if st.button("Delete Selected Payout", type="secondary", use_container_width=True):
        delete_result = delete_overtime_payout(delete_options[selected_delete_label])
        if delete_result["success"]:
            st.success(delete_result["message"])
            st.rerun()
        else:
            st.error(delete_result["message"])


if __name__ == "__main__":
    main()
