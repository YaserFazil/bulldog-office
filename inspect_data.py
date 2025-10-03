#!/usr/bin/env python3
"""
Data Inspection Script
======================

This script helps you inspect your MongoDB data structure before running the migration.
"""

import os
import sys
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
import pandas as pd

def inspect_database():
    """Inspect the MongoDB database structure and sample data."""
    
    print("🔍 MongoDB Data Inspector")
    print("=" * 50)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Get MongoDB URI
    mongodb_uri = os.getenv("MONGODB_CLIENT")
    if not mongodb_uri:
        print("❌ Error: MONGODB_CLIENT environment variable not set")
        return False
    
    try:
        # Connect to MongoDB
        client = MongoClient(mongodb_uri)
        db = client["bulldog_office"]
        
        print("✅ Connected to MongoDB")
        print()
        
        # Inspect employees collection
        print("👥 EMPLOYEES COLLECTION")
        print("-" * 30)
        employees_collection = db["employees"]
        employees_count = employees_collection.count_documents({})
        print(f"Total employees: {employees_count}")
        
        if employees_count > 0:
            sample_employee = employees_collection.find_one()
            print(f"Sample employee fields: {list(sample_employee.keys())}")
            print(f"Sample employee data:")
            for key, value in sample_employee.items():
                if key != "_id":
                    print(f"  {key}: {value}")
        print()
        
        # Inspect work_history collection
        print("📅 WORK_HISTORY COLLECTION")
        print("-" * 30)
        work_history_collection = db["work_history"]
        work_history_count = work_history_collection.count_documents({})
        print(f"Total work history records: {work_history_count}")
        
        if work_history_count > 0:
            sample_work = work_history_collection.find_one()
            print(f"Sample work history fields: {list(sample_work.keys())}")
            print(f"Sample work history data:")
            for key, value in sample_work.items():
                if key != "_id":
                    print(f"  {key}: {value}")
        print()
        
        # Check data relationships
        print("🔗 DATA RELATIONSHIPS")
        print("-" * 30)
        
        # Get unique employee IDs from work_history
        work_employee_ids = work_history_collection.distinct("employee_id")
        print(f"Unique employee IDs in work_history: {len(work_employee_ids)}")
        
        # Check if employee IDs match
        employee_ids = []
        for emp in employees_collection.find({}, {"_id": 1}):
            employee_ids.append(str(emp["_id"]))
        
        print(f"Employee IDs in employees collection: {len(employee_ids)}")
        
        # Find matching employee IDs
        matching_ids = set(work_employee_ids) & set(employee_ids)
        print(f"Matching employee IDs: {len(matching_ids)}")
        
        if len(matching_ids) < len(work_employee_ids):
            missing_ids = set(work_employee_ids) - set(employee_ids)
            print(f"⚠️  Missing employee IDs: {len(missing_ids)}")
            print(f"   Sample missing IDs: {list(missing_ids)[:5]}")
        
        print()
        
        # Check date ranges
        print("📊 DATE RANGES")
        print("-" * 30)
        
        if work_history_count > 0:
            # Get date range
            pipeline = [
                {"$group": {
                    "_id": None,
                    "min_date": {"$min": "$Date"},
                    "max_date": {"$max": "$Date"}
                }}
            ]
            date_range = list(work_history_collection.aggregate(pipeline))
            
            if date_range:
                min_date = date_range[0]["min_date"]
                max_date = date_range[0]["max_date"]
                print(f"Date range: {min_date} to {max_date}")
            
        # Count records with IN/OUT times
        with_in = work_history_collection.count_documents({"IN": {"$exists": True, "$ne": None, "$ne": ""}})
        with_out = work_history_collection.count_documents({"OUT": {"$exists": True, "$ne": None, "$ne": ""}})
        
        print(f"Records with IN time: {with_in}")
        print(f"Records with OUT time: {with_out}")
        
        # Check weekend records
        weekend_records = work_history_collection.count_documents({"Day": {"$in": ["SAT", "SUN"]}})
        weekend_with_work = work_history_collection.count_documents({
            "Day": {"$in": ["SAT", "SUN"]},
            "$or": [
                {"IN": {"$exists": True, "$ne": None, "$ne": ""}},
                {"OUT": {"$exists": True, "$ne": None, "$ne": ""}}
            ]
        })
        weekend_non_working = weekend_records - weekend_with_work
        
        print(f"Weekend records (SAT/SUN): {weekend_records}")
        print(f"Weekend records with work: {weekend_with_work}")
        print(f"Weekend non-working records (will be skipped): {weekend_non_working}")
        
        print()
        
        # Sample data for migration preview
        print("🔍 MIGRATION PREVIEW")
        print("-" * 30)
        
        if work_history_count > 0:
            print("Sample records that will be migrated:")
            sample_records = list(work_history_collection.find().limit(3))
            
            for i, record in enumerate(sample_records, 1):
                print(f"\nRecord {i}:")
                employee_id = record.get("employee_id")
                date = record.get("Date")
                in_time = record.get("IN")
                out_time = record.get("OUT")
                
                print(f"  Employee ID: {employee_id}")
                print(f"  Date: {date}")
                print(f"  IN: {in_time}")
                print(f"  OUT: {out_time}")
                
                # Try to find employee username
                try:
                    if ObjectId.is_valid(employee_id):
                        employee = employees_collection.find_one({"_id": ObjectId(employee_id)})
                    else:
                        employee = employees_collection.find_one({"_id": employee_id})
                    
                    if employee:
                        username = employee.get("username", "Not found")
                        print(f"  Username: {username}")
                    else:
                        print(f"  Username: Employee not found")
                except:
                    print(f"  Username: Error looking up employee")
        
        print()
        print("✅ Data inspection completed!")
        print()
        print("Next steps:")
        print("1. Review the data structure above")
        print("2. Fix any data issues if needed")
        print("3. Run the migration script")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Error during inspection: {str(e)}")
        return False

if __name__ == "__main__":
    success = inspect_database()
    sys.exit(0 if success else 1)
