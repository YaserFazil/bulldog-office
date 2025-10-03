#!/usr/bin/env python3
"""
CSV-only Migration Script
=========================

This script migrates employee check-in/check-out data from MongoDB to CSV format only.
"""

import os
import sys
from datetime import datetime
from migrate_to_frappe_hr import FrappeHRMigrator

def main():
    """Main function to run CSV-only migration."""
    
    print("📄 Frappe HR CSV Migration Tool")
    print("=" * 50)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check if MongoDB URI is set
    mongodb_uri = os.getenv("MONGODB_CLIENT")
    if not mongodb_uri:
        print("❌ Error: MONGODB_CLIENT environment variable not set")
        print()
        print("Please set your MongoDB connection string:")
        print("  export MONGODB_CLIENT='mongodb://localhost:27017'")
        print("  # or")
        print("  export MONGODB_CLIENT='mongodb://username:password@host:port/database'")
        print()
        return False
    
    print("✅ MongoDB URI found")
    print()
    
    try:
        from migrate_to_frappe_hr import FrappeHRMigrator
        
        print("🔄 Starting CSV migration process...")
        print()
        
        # Initialize migrator
        migrator = FrappeHRMigrator(mongodb_uri)
        
        # Connect to MongoDB
        if not migrator.connect_to_mongodb():
            print("❌ Failed to connect to MongoDB")
            return False
        
        try:
            # Fetch and process data
            records = migrator.fetch_and_process_data()
            
            if not records:
                print("⚠️  No data to migrate")
                return False
            
            # Export to CSV only
            csv_file = f"frappe_hr_employee_checkin_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            success = migrator.export_to_csv(records, csv_file)
            
            print()
            if success:
                print("🎉 CSV migration completed successfully!")
                print(f"📁 CSV file: {csv_file}")
                print(f"📊 Total records: {len(records)}")
                print(f"📋 Check migration.log for detailed information")
                print()
                print("Next steps:")
                print("1. Review the generated CSV file")
                print("2. Import the data into Frappe HR")
                print("3. Verify the imported data")
            else:
                print("❌ CSV migration failed!")
                print("📋 Check migration.log for error details")
            
            return success
            
        finally:
            # Close MongoDB connection
            if migrator.client:
                migrator.client.close()
        
    except ImportError as e:
        print(f"❌ Import error: {str(e)}")
        print("Make sure all required packages are installed:")
        print("  pip install pandas openpyxl pymongo python-dotenv")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        print("Check migration.log for detailed error information")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
