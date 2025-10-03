#!/usr/bin/env python3
"""
Simple script to run the Frappe HR migration
============================================

This is a user-friendly script to run the migration with proper error handling.
"""

import os
import sys
from datetime import datetime

def main():
    """Main function to run the migration with user-friendly output and interactive prompts."""
    
    print("🚀 Frappe HR Migration Tool")
    print("=" * 60)
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
    
    # Import and run migration
    try:
        from migrate_to_frappe_hr import FrappeHRMigrator
        
        # Prompt for start date
        print("📅 Export Date Filter")
        print("-" * 60)
        print("Enter a start date to export only records from that date onwards.")
        print("Leave empty to export ALL records.")
        print()
        
        start_date = None
        while True:
            date_input = input("Start date (YYYY-MM-DD) or press Enter for all: ").strip()
            
            if not date_input:
                print("✅ Exporting all records (no date filter)")
                break
            
            try:
                start_date = datetime.strptime(date_input, "%Y-%m-%d")
                print(f"✅ Will export records from {start_date.strftime('%Y-%m-%d')} onwards")
                break
            except ValueError:
                print("❌ Invalid date format. Please use YYYY-MM-DD (e.g., 2025-01-01)")
        
        print()
        
        # Prompt for ID generation
        print("🆔 Unique ID Generation")
        print("-" * 60)
        print("Generate unique IDs in format: EMP-CKIN-{month}-2025-{sequence}")
        print()
        
        while True:
            id_input = input("Include unique IDs? (y/n) [y]: ").strip().lower()
            
            if id_input in ['', 'y', 'yes']:
                include_ids = True
                print("✅ Will generate unique IDs for each record")
                break
            elif id_input in ['n', 'no']:
                include_ids = False
                print("✅ Will export without IDs (Employee, Time, Log Type only)")
                break
            else:
                print("❌ Please enter 'y' or 'n'")
        
        print()
        print("🔄 Starting migration process...")
        print()
        
        # Initialize migrator
        migrator = FrappeHRMigrator(mongodb_uri)
        
        # Generate output filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"frappe_hr_employee_checkin_{timestamp}.xlsx"
        
        # Run migration with user preferences
        success = migrator.run_migration(
            output_file=output_file,
            export_csv=True,
            start_date=start_date,
            include_ids=include_ids
        )
        
        print()
        if success:
            print("🎉 Migration completed successfully!")
            print(f"📁 Excel file: {output_file}")
            csv_file = output_file.replace('.xlsx', '.csv')
            print(f"📁 CSV file: {csv_file}")
            if start_date:
                print(f"📅 Filtered from: {start_date.strftime('%Y-%m-%d')}")
            print(f"🆔 IDs included: {'Yes' if include_ids else 'No'}")
            print(f"📊 Check migration.log for detailed information")
            print()
            print("Next steps:")
            print("1. Review the generated Excel and CSV files")
            print("2. Import the data into Frappe HR")
            print("3. Verify the imported data")
        else:
            print("❌ Migration failed!")
            print("📋 Check migration.log for error details")
            print()
            print("Troubleshooting:")
            print("1. Verify MongoDB connection")
            print("2. Check data structure in collections")
            print("3. Run test_migration.py for diagnostics")
        
        return success
        
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
