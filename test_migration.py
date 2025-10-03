#!/usr/bin/env python3
"""
Test script for Frappe HR migration
===================================

This script tests the migration functionality with sample data.
"""

import os
import sys
from datetime import datetime
from migrate_to_frappe_hr import FrappeHRMigrator

def test_migration():
    """Test the migration process."""
    print("🧪 Testing Frappe HR Migration...")
    
    # Get MongoDB URI from environment variable
    mongodb_uri = os.getenv("MONGODB_CLIENT")
    
    if not mongodb_uri:
        print("❌ MONGODB_CLIENT environment variable not set")
        return False
    
    # Initialize migrator
    migrator = FrappeHRMigrator(mongodb_uri)
    
    # Test connection
    if not migrator.connect_to_mongodb():
        print("❌ Failed to connect to MongoDB")
        return False
    
    print("✅ Successfully connected to MongoDB")
    
    # Test data fetching
    try:
        # Get sample data count
        work_history_count = migrator.work_history_collection.count_documents({})
        employees_count = migrator.employees_collection.count_documents({})
        
        print(f"📊 Found {work_history_count} work history records")
        print(f"👥 Found {employees_count} employee records")
        
        # Test processing a small sample
        sample_records = list(migrator.work_history_collection.find().limit(5))
        print(f"🔍 Sample work history records: {len(sample_records)}")
        
        for i, record in enumerate(sample_records):
            print(f"  Record {i+1}:")
            print(f"    Employee ID: {record.get('employee_id')}")
            print(f"    Date: {record.get('Date')}")
            print(f"    IN: {record.get('IN')}")
            print(f"    OUT: {record.get('OUT')}")
            
            # Test username lookup
            username = migrator.get_employee_username(record.get('employee_id'))
            print(f"    Username: {username}")
            print()
        
        # Close connection
        migrator.client.close()
        print("✅ Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_migration()
