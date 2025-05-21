import streamlit as st
import json
import os
from datetime import date, datetime
import pandas as pd
from streamlit_calendar import calendar
import requests

# --- File for storing events ---
EVENTS_FILE = "calendar_events.json"

# --- Functions to load and save events ---
def load_events():
    """Load events from the JSON file if it exists; otherwise, return an empty dict."""
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE, "r") as f:
            return json.load(f)
    else:
        return {}

def save_events(events):
    """Save the events dictionary to a JSON file."""
    with open(EVENTS_FILE, "w") as f:
        json.dump(events, f, indent=4)

# --- Function to generate weekend events for a given year ---
def get_weekend_events(year):
    """
    Return a dictionary with keys as date strings (YYYY-MM-DD) for every Saturday and Sunday
    of the given year, with a default value (e.g. "Weekend/Holiday").
    """
    start_date = pd.Timestamp(year=year, month=1, day=1)
    end_date = pd.Timestamp(year=year, month=12, day=31)
    weekend_events = {}
    for dt in pd.date_range(start_date, end_date):
        if dt.weekday() in [5, 6]:  # Saturday or Sunday
            date_str = dt.strftime("%Y-%m-%d")
            weekend_events[date_str] = "Weekend/Holiday"
    return weekend_events


def get_weekend_and_holiday_events(year):
    """
    Return a dictionary with keys as date strings (YYYY-MM-DD) for every Saturday, Sunday,
    and public holiday in Austria for the given year. If a date is both a weekend and a holiday,
    the value will indicate both.
    """
    # Fetch Austrian public holidays
    url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/AT"
    response = requests.get(url)
    holidays = response.json() if response.status_code == 200 else []
    
    # Convert holiday list to dictionary with date as key
    holiday_events = {h["date"]: {"localName": h["localName"], "name": h["name"]} for h in holidays}
    
    start_date = pd.Timestamp(year=year, month=1, day=1)
    end_date = pd.Timestamp(year=year, month=12, day=31)
    events = {}
    
    for dt in pd.date_range(start_date, end_date):
        date_str = dt.strftime("%Y-%m-%d")
        is_weekend = dt.weekday() in [5, 6]  # Saturday or Sunday
        is_holiday = date_str in holiday_events
        
        if is_weekend and is_holiday:
            events[date_str] = f"Weekend/Holiday {holiday_events[date_str]["localName"]} ({holiday_events[date_str]["name"]})"
        elif is_weekend:
            events[date_str] = "Weekend"
        elif is_holiday:
            events[date_str] = f"Holiday {holiday_events[date_str]["localName"]} ({holiday_events[date_str]["name"]})"
    
    return events


# --- Convert our stored events (dict) to a list of event objects for the calendar ---
def events_dict_to_list(events_dict):
    """
    Convert events stored as a dict {date_str: event_detail or [detail, ...]} 
    into a list of event objects.
    For simplicity, each event is created as a full-day event (start and end on the same day).
    """
    event_list = []
    for event_date, details in events_dict.items():
        if isinstance(details, list):
            for title in details:
                event_list.append({
                    "title": title,
                    "start": event_date,
                    "end": event_date
                })
        else:
            title = details
            event_list.append({
                "title": title,
                "start": event_date,
                "end": event_date
            })
    return event_list

# --- Convert list of event objects from the calendar back to our stored dictionary format ---
def events_list_to_dict(event_list):
    """
    Convert a list of event objects (with keys "title" and "start")
    into our stored format: { date_str: event_detail or [detail, ...] }.
    """
    events_dict = {}
    for ev in event_list:
        date_str = ev.get("start")
        title = ev.get("title")
        if date_str in events_dict:
            if isinstance(events_dict[date_str], list):
                events_dict[date_str].append(title)
            else:
                events_dict[date_str] = [events_dict[date_str], title]
        else:
            events_dict[date_str] = title
    return events_dict

def main():
    st.title("Interactive Calendar")

    # Load stored events from JSON.
    events = load_events()

    # Merge in all weekend events for the current year.
    current_year = date.today().year
    holiday_events = get_weekend_and_holiday_events(current_year)
    
    for d, default_text in holiday_events.items():
        if d not in events:
            events[d] = default_text

    # Convert our dictionary to a list of event objects.
    event_list = events_dict_to_list(events)

    # --- Calendar Options and Custom CSS (as per documentation) ---
    calendar_options = {
        "editable": True,
        "selectable": True,
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "dayGridMonth",
        },
        "timeZone": 'UTC',
        "locale": 'en',
        "initialView": "dayGridMonth",
    }
 
    # --- Render the Calendar Component ---
    # The calendar component returns a dict containing state from callbacks such as eventsSet.
    returned_state = calendar(
        events=event_list,
        options=calendar_options,
        callbacks=['dateClick', 'eventClick', 'eventChange', 'eventsSet', 'select'],
        license_key='CC-Attribution-NonCommercial-NoDerivatives',
        key="my_calendar"
    )
    # --- Handle an eventClick callback (for update/delete) ---
    if returned_state.get("eventClick"):
        clicked_event = returned_state["eventClick"]["event"]
        selected_date = clicked_event["start"]
        details = clicked_event["title"]
        # Convert to date-only string.
        date_str = pd.to_datetime(selected_date).strftime("%Y-%m-%d")
        st.subheader(f"Edit Event for {date_str}")
        new_date = st.date_input("Select a date", value=pd.to_datetime(selected_date), key="edit_date", disabled=True)
        new_details = st.text_area("Update Event Details", value=details, height=100, key="edit_text")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Update Event"):
                new_date_str = new_date.strftime("%Y-%m-%d")
                # Update (unique event per date): override existing event.
                events[new_date_str] = new_details
                # If the date has changed, remove the old event.
                if new_date_str != date_str and date_str in events:
                    del events[date_str]
                save_events(events)
                st.success("Event updated!")
                # st.rerun()
        with col2:
            if st.button("Delete Event"):
                if date_str in events:
                    del events[date_str]
                    save_events(events)
                    st.success("Event deleted!")
                    # st.rerun()
    # If the employee clicks on a date (dateClick callback)...
    if returned_state.get("dateClick"):
        clicked_date = returned_state["dateClick"]["date"]
        date_str = pd.to_datetime(clicked_date).strftime("%Y-%m-%d")
        # Check if an event already exists on this date.
        if date_str in events:
            st.subheader(f"Edit Event for {date_str}")
            current_details = events[date_str]
            new_details = st.text_area("Update Event Details", value=current_details, height=100, key="edit_text_dateclick")
            col3, col4 = st.columns(2)
            with col3:
                if st.button("Update Existing Event"):
                    events[date_str] = new_details
                    save_events(events)
                    st.success("Event updated!")
                    # st.rerun()
            with col4:
                if st.button("Delete Existing Event"):
                    del events[date_str]
                    save_events(events)
                    st.success("Event deleted!")
                    # st.rerun()
        else:
            st.subheader(f"Add a New Event to {date_str}")
            # Disable date_input here to fix the date.
            new_date = st.date_input("Select a date", value=pd.to_datetime(clicked_date), key="add_date", disabled=True)
            event_text = st.text_area("Event Details", value="", height=100, key="add_text_dateclick")
            if st.button("Add Event (from dateClick)"):
                events[new_date.strftime("%Y-%m-%d")] = event_text
                save_events(events)
                st.success("Event added!")
                # st.rerun()
    # If the calendar returns an updated list of events, convert it back to our dictionary format.
    # if returned_state.get("eventsSet"):
    #     calendar_events = returned_state.get("eventsSet").get("events")
    #     calendar_events = calendar_events if calendar_events else event_list
    #     events = events_list_to_dict(calendar_events)

    st.markdown("---")
    if os.path.exists("calendar_events.json"):
        with open("calendar_events.json", "r") as f:
            file_contents = f.read()
        st.download_button(
            label="Download Calendar Events",
            data=file_contents,
            file_name="calendar_events.json",
            mime="application/json"
        )
    else:
        st.error("No events file found!")

    if st.button("Set/Reset Events for the current year"):
        save_events(holiday_events)

if __name__ == "__main__":
    main()
