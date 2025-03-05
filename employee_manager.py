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
users_collection = db["users"]

def get_users(full_name=None):
    users = list(users_collection.find({}, {"username": 1, "full_name": 1}))
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
    return users_collection.find_one({"email": email}) is not None

def validate_user(username):
    return users_collection.find_one({"username": username}) is not None

def validate_user_full_name(full_name):
    user = users_collection.find_one({"full_name": full_name}, {"username": 1})
    return user["username"] if user else None

def get_user_id(username):
    user = users_collection.find_one({"username": username}, {"_id": 1, "full_name": 1})
    if user:
        return str(user["_id"]), user["full_name"]
    else:
        return None, None

def delete_user_account(user_id):
    result = users_collection.delete_one({"_id": user_id})
    if result.deleted_count:
        return {"success": True, "message": "User Account Deleted!"}
    return {"success": False, "message": "User not found!"}

def update_user_account(user_id, **kwargs):
    result = users_collection.update_one({"_id": user_id}, {"$set": kwargs})
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

def update_employee_work_history(df: pd.DataFrame):
    try:
        df["Date"] = pd.to_datetime(df["Date"])  # Ensures "Date" is a datetime object
        records = df.to_dict(orient="records")

        bulk_updates = []
        for record in records:
            record_id = record.pop("_id", None)  # Extract _id from the record
            
            if record_id:  # Only update if _id exists
                bulk_updates.append(
                    UpdateOne({"_id": ObjectId(record_id)}, {"$set": record}, upsert=True)
                )

        if bulk_updates:
            work_history_collection.bulk_write(bulk_updates)  # Perform bulk update
        
        return {"success": True, "message": "Work History updated successfully"}    
    except Exception as e:
        return {"success": False, "message": f"Bad request when updating work history: {str(e)}"}

def create_employee_work_history(employee_id, df: pd.DataFrame):
    try:
        df["Date"] = pd.to_datetime(df["Date"])  # Ensures "Date" is a datetime object
        records = df.to_dict(orient="records")

        bulk_updates = []
        for record in records:
            record["employee_id"] = str(employee_id)  # Convert employee_id to string
            
            # Create a unique filter using "Date" and "employee_id"
            filter_query = {"employee_id": record["employee_id"], "Date": record["Date"]}

            # Use $set to update or insert the record
            bulk_updates.append(
                UpdateOne(filter_query, {"$set": record}, upsert=True)
            )

        if bulk_updates:
            work_history_collection.bulk_write(bulk_updates)  # Perform bulk operation

        return {"success": True, "message": "Work History created/updated successfully"}

    except Exception as e:
        return {"success": False, "message": f"Bad request when creating work history: {str(e)}"}

def create_user_account(**kwargs):
    try:
        timestamp = str(datetime.now().isoformat(sep=" ")).split(".")[0]
        if check_user(kwargs["email"]):
            return {"success": False, "message": f"User with the {kwargs['email']} email already exists!"}
        if validate_user(kwargs["username"]):
            return {"success": False, "message": f"User with the {kwargs['username']} username already exists!"}
        user_data = {"date_joined": timestamp, **kwargs}
        users_collection.insert_one(user_data)
        return {"success": True, "message": "User created successfully"}
    except Exception as e:
        return {"success": False, "message": f"Bad request: {str(e)}"}
