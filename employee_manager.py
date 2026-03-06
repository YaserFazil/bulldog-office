import uuid
from datetime import datetime
import pandas as pd
from pymongo import MongoClient, UpdateOne
from bson import ObjectId
import os
from dotenv import load_dotenv
import streamlit as st
load_dotenv()

# MongoDB setup
client = MongoClient(os.getenv("MONGODB_CLIENT"))  # Change if using a cloud DB
db = client["bulldog_office"]  # Replace with actual database name
work_history_collection = db["work_history"]  # Collection name
temp_work_history_collection = db["temp_work_history"]  # Collection name
employees_collection = db["employees"]
users_collection = db["users"]
overtime_payouts_collection = db["overtime_payouts"]

def get_employees(full_name=None):
    employees = list(employees_collection.find({}, {"username": 1, "full_name": 1}))
    usernames = []
    if full_name:
        selected_employee = next((employee for employee in employees if employee["full_name"] == full_name), None)
        if selected_employee:
            usernames.append(selected_employee["username"])
        usernames.extend(employee["username"] for employee in employees if not selected_employee or employee["username"] != selected_employee.get("username"))
    else:
        usernames = [employee["username"] for employee in employees]
    return usernames

def check_employee(email):
    return employees_collection.find_one({"email": email}) is not None

def validate_employee(username):
    return employees_collection.find_one({"username": username}) is not None

def validate_employee_full_name(full_name):
    employee = employees_collection.find_one({"full_name": full_name}, {"username": 1})
    return employee["username"] if employee else None

def get_employee_id(username):
    employee = employees_collection.find_one({"username": username}, {"_id": 1, "full_name": 1})
    if employee:
        return str(employee["_id"]), employee["full_name"]
    else:
        employee = employees_collection.find_one({"full_name": username}, {"_id": 1, "username": 1})
        if employee:
            return str(employee["_id"]), employee["username"]
        return None, None

def delete_employee_account(employee_id):
    result = employees_collection.delete_one({"_id": employee_id})
    if result.deleted_count:
        return {"success": True, "message": "employee Account Deleted!"}
    return {"success": False, "message": "employee not found!"}

def update_employee_account(employee_id, **kwargs):
    result = employees_collection.update_one({"_id": employee_id}, {"$set": kwargs})
    if result.modified_count:
        return {"success": True, "message": "employee Updated!"}
    return {"success": False, "message": "No changes made or employee not found!"}

def upsert_employee_work_history(df: pd.DataFrame, employee_id=None):
    try:
        df["Date"] = pd.to_datetime(df["Date"])  # Ensure "Date" is a datetime object
        records = df.to_dict(orient="records")

        bulk_updates = []
        for record in records:
            if employee_id:
                record["employee_id"] = str(employee_id)  # Ensure employee_id is a string

            record_id = record.pop("_id", None)  # Extract _id from the record

            if record_id:  
                # Update existing record using _id
                bulk_updates.append(
                    UpdateOne({"_id": ObjectId(record_id)}, {"$set": record}, upsert=True)
                )
            else:
                # Create or update based on "Date" and "employee_id"
                filter_query = {"employee_id": record["employee_id"], "Date": record["Date"]}
                bulk_updates.append(
                    UpdateOne(filter_query, {"$set": record}, upsert=True)
                )

        if bulk_updates:
            work_history_collection.bulk_write(bulk_updates)  # Perform bulk update

        return {"success": True, "message": "Work History upserted successfully"}

    except Exception as e:
        return {"success": False, "message": f"Bad request when upserting work history: {str(e)}"}

def create_employee_account(**kwargs):
    try:
        timestamp = str(datetime.now().isoformat(sep=" ")).split(".")[0]
        if check_employee(kwargs["email"]):
            return {"success": False, "message": f"employee with the {kwargs['email']} email already exists!"}
        if validate_employee(kwargs["username"]):
            return {"success": False, "message": f"employee with the {kwargs['username']} username already exists!"}
        employee_data = {"date_joined": timestamp, **kwargs}
        employees_collection.insert_one(employee_data)
        return {"success": True, "message": "employee created successfully"}
    except Exception as e:
        return {"success": False, "message": f"Bad request: {str(e)}"}


def upsert_employee_temp_work_history(source_record, employee_id=None, employee_username=None):
    try:
        source_record["Date"] = pd.to_datetime(source_record["Date"])  # Ensure "Date" is a datetime object

        bulk_updates = []
        if employee_id:
            source_record["employee_username"] = str(employee_username)
            source_record["employee_id"] = str(employee_id)  # Ensure employee_id is a string
            

        record_id = source_record.pop("_id", None)  # Extract _id from the record

        if record_id:  
            # Update existing record using _id
            bulk_updates.append(
                UpdateOne({"_id": ObjectId(record_id)}, {"$set": source_record}, upsert=True)
            )
        else:
            # Create or update based on "Date" and "employee_id"
            filter_query = {"employee_id": source_record["employee_id"], "Date": source_record["Date"]}
            bulk_updates.append(
                UpdateOne(filter_query, {"$set": source_record}, upsert=True)
            )

        if bulk_updates:
            temp_work_history_collection.bulk_write(bulk_updates)  # Perform bulk update

        return {"success": True, "message": "Temp Work History upserted successfully"}

    except Exception as e:
        return {"success": False, "message": f"Bad request when upserting temp work history: {str(e)}"}


def create_overtime_payout(employee_code, employee_name, payout_date, payout_hours, note=None):
    try:
        payout_date_value = pd.to_datetime(payout_date).normalize().to_pydatetime()
        timestamp = datetime.now()
        payout_record = {
            "employee_code": str(employee_code).strip(),
            "employee_name": str(employee_name).strip(),
            "payout_date": payout_date_value,
            "payout_hours": str(payout_hours).strip(),
            "note": str(note).strip() if note else "",
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        overtime_payouts_collection.insert_one(payout_record)
        return {"success": True, "message": "Overtime payout recorded successfully"}
    except Exception as e:
        return {"success": False, "message": f"Bad request when creating overtime payout: {str(e)}"}


def fetch_overtime_payouts(employee_code=None, start_date=None, end_date=None):
    try:
        query = {}
        if employee_code:
            query["employee_code"] = str(employee_code).strip()

        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = pd.to_datetime(start_date).normalize().to_pydatetime()
            if end_date:
                date_query["$lte"] = pd.to_datetime(end_date).normalize().to_pydatetime()
            query["payout_date"] = date_query

        records = list(overtime_payouts_collection.find(query).sort("payout_date", 1))
        for record in records:
            record["_id"] = str(record["_id"])
            payout_date_value = record.get("payout_date")
            if isinstance(payout_date_value, datetime):
                record["payout_date"] = payout_date_value.date()
        return records
    except Exception:
        return []


def delete_overtime_payout(payout_id):
    try:
        result = overtime_payouts_collection.delete_one({"_id": ObjectId(payout_id)})
        if result.deleted_count:
            return {"success": True, "message": "Overtime payout deleted successfully"}
        return {"success": False, "message": "Overtime payout not found"}
    except Exception as e:
        return {"success": False, "message": f"Bad request when deleting overtime payout: {str(e)}"}