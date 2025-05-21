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

def get_users(full_name=None):
    users = list(employees_collection.find({}, {"username": 1, "full_name": 1}))
    usernames = []
    if full_name:
        selected_user = next((user for user in users if user["full_name"] == full_name), None)
        if selected_user:
            usernames.append(selected_user["username"])
        usernames.extend(user["username"] for user in users if not selected_user or user["username"] != selected_user.get("username"))
    else:
        usernames = [user["username"] for user in users]
    return usernames

def check_user(email):
    return employees_collection.find_one({"email": email}) is not None

def validate_user(username):
    return employees_collection.find_one({"username": username}) is not None

def validate_user_full_name(full_name):
    user = employees_collection.find_one({"full_name": full_name}, {"username": 1})
    return user["username"] if user else None

def get_user_id(username):
    user = employees_collection.find_one({"username": username}, {"_id": 1, "full_name": 1})
    if user:
        return str(user["_id"]), user["full_name"]
    else:
        user = employees_collection.find_one({"full_name": username}, {"_id": 1, "username": 1})
        if user:
            return str(user["_id"]), user["username"]
        return None, None

def delete_user_account(user_id):
    result = employees_collection.delete_one({"_id": user_id})
    if result.deleted_count:
        return {"success": True, "message": "User Account Deleted!"}
    return {"success": False, "message": "User not found!"}

def update_user_account(user_id, **kwargs):
    result = employees_collection.update_one({"_id": user_id}, {"$set": kwargs})
    if result.modified_count:
        return {"success": True, "message": "User Updated!"}
    return {"success": False, "message": "No changes made or user not found!"}

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

def create_user_account(**kwargs):
    try:
        timestamp = str(datetime.now().isoformat(sep=" ")).split(".")[0]
        if check_user(kwargs["email"]):
            return {"success": False, "message": f"User with the {kwargs['email']} email already exists!"}
        if validate_user(kwargs["username"]):
            return {"success": False, "message": f"User with the {kwargs['username']} username already exists!"}
        user_data = {"date_joined": timestamp, **kwargs}
        employees_collection.insert_one(user_data)
        return {"success": True, "message": "User created successfully"}
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