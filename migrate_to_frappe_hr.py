#!/usr/bin/env python3
"""
MongoDB to Frappe HR Migration Script
=====================================

This script migrates employee check-in/check-out data from the deprecated 
bulldog_office MongoDB database to an Excel format that can be uploaded to Frappe HR.

Author: Senior Python Developer
Date: 2025
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class FrappeHRMigrator:
    """Handles migration of employee data from MongoDB to Frappe HR Excel format."""
    
    def __init__(self, mongodb_uri: str, database_name: str = "bulldog_office"):
        """
        Initialize the migrator with MongoDB connection details.
        
        Args:
            mongodb_uri: MongoDB connection string
            database_name: Name of the MongoDB database
        """
        self.mongodb_uri = mongodb_uri
        self.database_name = database_name
        self.client = None
        self.db = None
        self.employees_collection = None
        self.work_history_collection = None
        
    def connect_to_mongodb(self) -> bool:
        """Establish connection to MongoDB."""
        try:
            self.client = MongoClient(self.mongodb_uri)
            self.db = self.client[self.database_name]
            self.employees_collection = self.db["employees"]
            self.work_history_collection = self.db["work_history"]
            
            # Test connection
            self.client.admin.command('ping')
            logger.info(f"Successfully connected to MongoDB database: {self.database_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            return False
    
    def get_employee_username(self, employee_id: str) -> Optional[str]:
        """
        Get username for a given employee ID.
        
        Args:
            employee_id: Employee ID to look up
            
        Returns:
            Username if found, None otherwise
        """
        try:
            # Try to find by _id first (ObjectId)
            if ObjectId.is_valid(employee_id):
                employee = self.employees_collection.find_one(
                    {"_id": ObjectId(employee_id)}, 
                    {"username": 1}
                )
                if employee:
                    return employee.get("username")
            
            # Try to find by employee_id field
            employee = self.employees_collection.find_one(
                {"_id": employee_id}, 
                {"username": 1}
            )
            if employee:
                return employee.get("username")
                
            logger.warning(f"Employee not found for ID: {employee_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error looking up employee {employee_id}: {str(e)}")
            return None
    
    def format_time_string(self, time_str: str) -> str:
        """
        Format time string to ensure it's in HH:MM format.
        
        Args:
            time_str: Time string in various formats
            
        Returns:
            Formatted time string in HH:MM format
        """
        if not time_str or pd.isna(time_str):
            return ""
            
        time_str = str(time_str).strip()
        
        # Handle different time formats
        if ":" in time_str:
            parts = time_str.split(":")
            if len(parts) >= 2:
                hours = parts[0].zfill(2)
                minutes = parts[1].zfill(2)
                return f"{hours}:{minutes}"
        
        # Handle formats like "900" -> "09:00"
        if time_str.isdigit() and len(time_str) <= 4:
            time_str = time_str.zfill(4)
            return f"{time_str[:2]}:{time_str[2:]}"
        
        return time_str
    
    def create_datetime_string(self, date_obj: datetime, time_str: str) -> str:
        """
        Combine date and time into a full datetime string.
        
        Args:
            date_obj: Date object
            time_str: Time string in HH:MM format
            
        Returns:
            Combined datetime string in DD-MM-YYYY HH:MM:SS format
        """
        try:
            if not time_str or time_str.strip() == "":
                return ""
                
            # Format time string
            formatted_time = self.format_time_string(time_str)
            if not formatted_time:
                return ""
            
            # Parse time
            time_parts = formatted_time.split(":")
            hours = int(time_parts[0])
            minutes = int(time_parts[1])
            
            # Create datetime object
            combined_datetime = datetime.combine(
                date_obj.date() if hasattr(date_obj, 'date') else date_obj,
                datetime.min.time().replace(hour=hours, minute=minutes)
            )
            
            # Format as DD-MM-YYYY HH:MM:SS
            return combined_datetime.strftime("%d-%m-%Y %H:%M:%S")
            
        except Exception as e:
            logger.error(f"Error creating datetime string for {date_obj}, {time_str}: {str(e)}")
            return ""
    
    def generate_record_id(self, month: int, sequence: int) -> str:
        """
        Generate unique record ID in the format EMP-CKIN-{month}-2025-{sequence}.
        
        Args:
            month: Month number (1-12)
            sequence: Sequence number starting from 1
            
        Returns:
            Formatted record ID
        """
        return f"EMP-CKIN-{month:02d}-2025-{sequence:06d}"
    
    def is_weekend_non_working_day(self, record: Dict[str, Any]) -> bool:
        """
        Check if a record represents a weekend non-working day.
        
        Args:
            record: Work history record from MongoDB
            
        Returns:
            True if it's a weekend day with no work (both IN and OUT are empty/None)
        """
        day = record.get("Day", "").upper()
        in_time = record.get("IN")
        out_time = record.get("OUT")
        
        # Check if it's a weekend day
        is_weekend = day in ["SAT", "SUN"]
        
        if not is_weekend:
            return False
        
        # Check if both IN and OUT are empty/None
        in_empty = (in_time is None or 
                   str(in_time).strip() == "" or 
                   str(in_time).strip().lower() == "nan")
        
        out_empty = (out_time is None or 
                    str(out_time).strip() == "" or 
                    str(out_time).strip().lower() == "nan")
        
        # Return True if it's weekend AND both times are empty
        return in_empty and out_empty

    def fetch_and_process_data(self, start_date: Optional[datetime] = None, include_ids: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch data from MongoDB and process it for Frappe HR format.
        
        Args:
            start_date: Optional start date to filter records (only records from this date onwards)
            include_ids: Whether to include unique ID generation in output
        
        Returns:
            List of processed records ready for Excel export
        """
        logger.info("Starting data fetch and processing...")
        
        if start_date:
            logger.info(f"Filtering records from {start_date.strftime('%Y-%m-%d')} onwards")
        
        try:
            # Build query filter
            query_filter = {}
            if start_date:
                query_filter["Date"] = {"$gte": start_date}
            
            # Fetch work history records
            work_history_cursor = self.work_history_collection.find(query_filter)
            work_history_data = list(work_history_cursor)
            
            logger.info(f"Found {len(work_history_data)} work history records")
            
            processed_records = []
            sequence_counter = 1
            skipped_weekend_records = 0
            
            # Process each work history record
            for record in work_history_data:
                try:
                    employee_id = record.get("employee_id")
                    if not employee_id:
                        logger.warning(f"Skipping record without employee_id: {record.get('_id')}")
                        continue
                    
                    # Check if this is a weekend non-working day (skip it)
                    if self.is_weekend_non_working_day(record):
                        skipped_weekend_records += 1
                        logger.debug(f"Skipping weekend non-working day: {record.get('_id')} - {record.get('Day')}")
                        continue
                    
                    # Get employee username
                    username = self.get_employee_username(employee_id)
                    if not username:
                        logger.warning(f"Skipping record for unknown employee: {employee_id}")
                        continue
                    
                    # Get date
                    date_field = record.get("Date")
                    if not date_field:
                        logger.warning(f"Skipping record without date: {record.get('_id')}")
                        continue
                    
                    # Convert date to datetime if needed
                    if isinstance(date_field, str):
                        date_obj = pd.to_datetime(date_field)
                    elif hasattr(date_field, 'date'):
                        date_obj = date_field
                    else:
                        date_obj = pd.to_datetime(date_field)
                    
                    # Get month for ID generation
                    month = date_obj.month if hasattr(date_obj, 'month') else pd.to_datetime(date_field).month
                    
                    # Process IN time
                    in_time = record.get("IN")
                    if in_time and str(in_time).strip() and str(in_time).strip() != "nan":
                        datetime_str = self.create_datetime_string(date_obj, str(in_time))
                        if datetime_str:
                            record_data = {
                                "Employee": username,
                                "Time": datetime_str,
                                "Log Type": "IN"
                            }
                            if include_ids:
                                record_data["ID"] = self.generate_record_id(month, sequence_counter)
                            processed_records.append(record_data)
                            sequence_counter += 1
                    
                    # Process OUT time
                    out_time = record.get("OUT")
                    if out_time and str(out_time).strip() and str(out_time).strip() != "nan":
                        datetime_str = self.create_datetime_string(date_obj, str(out_time))
                        if datetime_str:
                            record_data = {
                                "Employee": username,
                                "Time": datetime_str,
                                "Log Type": "OUT"
                            }
                            if include_ids:
                                record_data["ID"] = self.generate_record_id(month, sequence_counter)
                            processed_records.append(record_data)
                            sequence_counter += 1
                    
                except Exception as e:
                    logger.error(f"Error processing record {record.get('_id')}: {str(e)}")
                    continue
            
            # Sort records by time for better organization
            processed_records.sort(key=lambda x: x["Time"])
            
            logger.info(f"Successfully processed {len(processed_records)} records")
            logger.info(f"Skipped {skipped_weekend_records} weekend non-working day records")
            return processed_records
            
        except Exception as e:
            logger.error(f"Error fetching and processing data: {str(e)}")
            return []
    
    def export_to_excel(self, records: List[Dict[str, Any]], output_file: str = "frappe_hr_employee_checkin.xlsx", include_ids: bool = True) -> bool:
        """
        Export processed records to Excel file.
        
        Args:
            records: List of processed records
            output_file: Output Excel file path
            include_ids: Whether IDs are included in the records
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not records:
                logger.warning("No records to export")
                return False
            
            # Create DataFrame
            df = pd.DataFrame(records)
            
            # Ensure proper column order based on whether IDs are included
            if include_ids:
                column_order = ["ID", "Employee", "Time", "Log Type"]
            else:
                column_order = ["Employee", "Time", "Log Type"]
            df = df[column_order]
            
            # Export to Excel
            df.to_excel(output_file, index=False, engine='openpyxl')
            
            logger.info(f"Successfully exported {len(records)} records to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to Excel: {str(e)}")
            return False
    
    def export_to_csv(self, records: List[Dict[str, Any]], output_file: str = "frappe_hr_employee_checkin.csv", include_ids: bool = True) -> bool:
        """
        Export processed records to CSV file.
        
        Args:
            records: List of processed records
            output_file: Output CSV file path
            include_ids: Whether IDs are included in the records
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not records:
                logger.warning("No records to export")
                return False
            
            # Create DataFrame
            df = pd.DataFrame(records)
            
            # Ensure proper column order based on whether IDs are included
            if include_ids:
                column_order = ["ID", "Employee", "Time", "Log Type"]
            else:
                column_order = ["Employee", "Time", "Log Type"]
            df = df[column_order]
            
            # Export to CSV
            df.to_csv(output_file, index=False, encoding='utf-8')
            
            logger.info(f"Successfully exported {len(records)} records to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to CSV: {str(e)}")
            return False
    
    def run_migration(self, output_file: str = "frappe_hr_employee_checkin.xlsx", export_csv: bool = True, 
                     start_date: Optional[datetime] = None, include_ids: bool = True) -> bool:
        """
        Run the complete migration process.
        
        Args:
            output_file: Output Excel file path
            export_csv: Whether to also export CSV format
            start_date: Optional start date to filter records
            include_ids: Whether to include unique ID generation
            
        Returns:
            True if successful, False otherwise
        """
        logger.info("Starting Frappe HR migration process...")
        
        # Connect to MongoDB
        if not self.connect_to_mongodb():
            return False
        
        try:
            # Fetch and process data
            records = self.fetch_and_process_data(start_date=start_date, include_ids=include_ids)
            
            if not records:
                logger.warning("No data to migrate")
                return False
            
            # Export to Excel
            excel_success = self.export_to_excel(records, output_file, include_ids=include_ids)
            
            # Export to CSV if requested
            csv_success = True
            if export_csv:
                csv_file = output_file.replace('.xlsx', '.csv').replace('.xls', '.csv')
                csv_success = self.export_to_csv(records, csv_file, include_ids=include_ids)
            
            if excel_success and csv_success:
                logger.info(f"Migration completed successfully!")
                logger.info(f"Excel file: {output_file}")
                if export_csv:
                    csv_file = output_file.replace('.xlsx', '.csv').replace('.xls', '.csv')
                    logger.info(f"CSV file: {csv_file}")
                logger.info(f"Total records migrated: {len(records)}")
                return True
            else:
                logger.error("Failed to export data")
                return False
                
        except Exception as e:
            logger.error(f"Migration failed: {str(e)}")
            return False
        
        finally:
            # Close MongoDB connection
            if self.client:
                self.client.close()
                logger.info("MongoDB connection closed")

def main():
    """Main function to run the migration with interactive prompts."""
    print("🚀 Frappe HR Migration Tool")
    print("=" * 60)
    print()
    
    # Get MongoDB URI from environment variable
    mongodb_uri = os.getenv("MONGODB_CLIENT")
    
    if not mongodb_uri:
        logger.error("MONGODB_CLIENT environment variable not set")
        print("❌ Please set the MONGODB_CLIENT environment variable with your MongoDB connection string")
        return False
    
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
    
    if success:
        print(f"\n✅ Migration completed successfully!")
        print(f"📁 Excel file: {output_file}")
        csv_file = output_file.replace('.xlsx', '.csv')
        print(f"📁 CSV file: {csv_file}")
        if start_date:
            print(f"📅 Filtered from: {start_date.strftime('%Y-%m-%d')}")
        print(f"🆔 IDs included: {'Yes' if include_ids else 'No'}")
        print(f"📊 Check the migration.log file for detailed information")
    else:
        print("\n❌ Migration failed!")
        print("📋 Check the migration.log file for error details")
    
    return success

if __name__ == "__main__":
    main()
