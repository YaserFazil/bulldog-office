# Frappe HR Migration Guide

This guide explains how to migrate employee check-in/check-out data from the deprecated `bulldog_office` MongoDB database to Frappe HR using the provided migration script.

## Overview

The migration script extracts employee attendance data from MongoDB and formats it into an Excel file that can be imported into Frappe HR. The script handles:

- Employee check-in and check-out times
- Date and time formatting
- Unique ID generation (optional)
- Date range filtering (optional)
- Data validation and error handling
- Weekend non-working day filtering

## Key Features

✅ **Interactive User Experience** - Prompts for configuration instead of editing code  
✅ **Date Filtering** - Export only records from a specific date onwards  
✅ **Optional ID Generation** - Choose whether to include unique IDs in output  
✅ **Dual Format Export** - Generates both Excel (.xlsx) and CSV (.csv) files  
✅ **Weekend Filtering** - Automatically excludes non-working weekend days  
✅ **Comprehensive Logging** - Detailed logs for troubleshooting and auditing

## Files

- `migrate_to_frappe_hr.py` - Main migration script (exports both Excel and CSV)
- `migrate_to_csv.py` - CSV-only migration script
- `run_migration.py` - User-friendly script to run the migration
- `test_migration.py` - Test script to verify connection and data
- `inspect_data.py` - Data inspection tool
- `MIGRATION_README.md` - This guide
- `migration.log` - Detailed migration log (created during execution)

## Prerequisites

1. **Python Environment**: Ensure you have Python 3.7+ installed
2. **Dependencies**: Install required packages:
   ```bash
   pip install pandas openpyxl pymongo python-dotenv
   ```
3. **MongoDB Access**: Ensure your MongoDB connection string is set in the environment variable `MONGODB_CLIENT`
4. **Data Backup**: Always backup your MongoDB data before running migration

## Setup

1. **Environment Variables**: Set your MongoDB connection string:
   ```bash
   export MONGODB_CLIENT="mongodb://localhost:27017"  # or your MongoDB URI
   ```

2. **Test Connection**: Run the test script first:
   ```bash
   python test_migration.py
   ```

## Usage

### Interactive Migration (Recommended)

Run the migration script with interactive prompts:

```bash
python migrate_to_frappe_hr.py
```

You will be prompted to:
1. **Start Date Filter**: Enter a date (YYYY-MM-DD) to export only records from that date onwards, or press Enter to export all records
2. **Unique ID Generation**: Choose whether to include unique IDs (EMP-CKIN-{month}-2025-{sequence}) or export without IDs

This will create:
- `frappe_hr_employee_checkin_{timestamp}.xlsx` - Excel file
- `frappe_hr_employee_checkin_{timestamp}.csv` - CSV file

### Example Interactive Session

```
🚀 Frappe HR Migration Tool
============================================================

📅 Export Date Filter
------------------------------------------------------------
Enter a start date to export only records from that date onwards.
Leave empty to export ALL records.

Start date (YYYY-MM-DD) or press Enter for all: 2025-09-01
✅ Will export records from 2025-09-01 onwards

🆔 Unique ID Generation
------------------------------------------------------------
Generate unique IDs in format: EMP-CKIN-{month}-2025-{sequence}

Include unique IDs? (y/n) [y]: n
✅ Will export without IDs (Employee, Time, Log Type only)

🔄 Starting migration process...
```

### CSV-Only Migration

Run the CSV-only migration script:

```bash
python migrate_to_csv.py
```

This will create only the CSV file.

### User-Friendly Migration

Run the user-friendly script:

```bash
python run_migration.py
```

This provides better output formatting and error handling.

### Custom Output File

You can specify custom output files by modifying the script or running:

```python
from migrate_to_frappe_hr import FrappeHRMigrator

migrator = FrappeHRMigrator("your_mongodb_uri")
# Export both Excel and CSV
migrator.run_migration("custom_output_file.xlsx", export_csv=True)
# Export only Excel
migrator.run_migration("custom_output_file.xlsx", export_csv=False)
# Export only CSV
migrator.export_to_csv(records, "custom_output_file.csv")
```

## Output Format

The generated Excel and CSV files contain the following columns:

### With Unique IDs (Default)

| Column | Description | Example |
|--------|-------------|---------|
| ID | Unique identifier | `EMP-CKIN-09-2025-000001` |
| Employee | Employee username | `john.doe` |
| Time | Full date and time | `15-09-2025 17:00:00` |
| Log Type | Check-in/out type | `IN` or `OUT` |

### Without Unique IDs (Optional)

| Column | Description | Example |
|--------|-------------|---------|
| Employee | Employee username | `john.doe` |
| Time | Full date and time | `15-09-2025 17:00:00` |
| Log Type | Check-in/out type | `IN` or `OUT` |

### ID Format

The ID follows the pattern: `EMP-CKIN-{month}-2025-{sequence}`

- `{month}`: Two-digit month (01-12)
- `{sequence}`: Six-digit sequence number starting from 000001

### Time Format

Times are formatted as: `DD-MM-YYYY HH:MM:SS`

- Date from the `Date` field in work_history
- Time from the `IN` or `OUT` field
- 24-hour format

## Data Processing

The script processes data as follows:

1. **Filters** records by start date (if specified)
2. **Fetches** all matching records from the `work_history` collection
3. **Filters out weekend non-working days** (Saturday/Sunday with empty IN and OUT times)
4. **Looks up** employee usernames from the `employees` collection
5. **Creates separate records** for IN and OUT times
6. **Generates unique IDs** based on month and sequence (if enabled)
7. **Formats timestamps** combining date and time
8. **Exports** to Excel and CSV formats

### Date Filtering

When you specify a start date during the interactive prompt:
- Only records with dates **on or after** the start date are included
- Format: `YYYY-MM-DD` (e.g., `2025-09-01`)
- Leave empty to export all records regardless of date
- Useful for incremental exports or partial data migration

### Weekend Filtering

The script automatically filters out weekend records where:
- Day field is "SAT" or "SUN"
- Both IN and OUT fields are empty, None, or "nan"

This ensures that non-working weekend days are not included in the migration, while preserving any actual weekend work records.

## Error Handling

The script includes comprehensive error handling:

- **Connection errors**: Logs MongoDB connection issues
- **Data validation**: Skips invalid or incomplete records
- **Employee lookup**: Handles missing employee records
- **Time formatting**: Manages various time formats
- **File operations**: Handles Excel export errors

## Logging

All operations are logged to `migration.log` with timestamps:

- Connection status
- Data processing progress
- Error messages
- Final statistics

## Troubleshooting

### Common Issues

1. **MongoDB Connection Failed**
   - Verify `MONGODB_CLIENT` environment variable
   - Check MongoDB server status
   - Verify network connectivity

2. **No Data Found**
   - Check if collections exist: `employees` and `work_history`
   - Verify data in MongoDB
   - Check collection names and field names

3. **Employee Not Found**
   - Verify `employee_id` field in work_history
   - Check `_id` field in employees collection
   - Ensure data consistency

4. **Time Format Issues**
   - Check IN/OUT field formats
   - Verify Date field format
   - Review time parsing logic

### Debug Mode

Enable detailed logging by modifying the script:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Data Validation

Before running the migration, verify your data:

1. **Check work_history collection**:
   ```python
   # Count total records
   db.work_history.count_documents({})
   
   # Check sample records
   db.work_history.find().limit(5)
   ```

2. **Check employees collection**:
   ```python
   # Count employees
   db.employees.count_documents({})
   
   # Check username field
   db.employees.find({}, {"username": 1}).limit(5)
   ```

3. **Verify data relationships**:
   ```python
   # Check employee_id references
   db.work_history.aggregate([
     {"$group": {"_id": "$employee_id", "count": {"$sum": 1}}}
   ])
   ```

## Post-Migration

After successful migration:

1. **Verify Excel file**: Check the generated file for completeness
2. **Import to Frappe HR**: Use the Excel file for data import
3. **Validate data**: Compare imported data with original
4. **Clean up**: Remove temporary files if needed

## Support

For issues or questions:

1. Check the `migration.log` file for detailed error messages
2. Run the test script to verify connectivity
3. Review the data structure in MongoDB
4. Check environment variables and dependencies

## Example Output

```
2025-01-16 10:30:15 - INFO - Starting Frappe HR migration process...
2025-01-16 10:30:15 - INFO - Successfully connected to MongoDB database: bulldog_office
2025-01-16 10:30:15 - INFO - Starting data fetch and processing...
2025-01-16 10:30:15 - INFO - Found 1250 work history records
2025-01-16 10:30:16 - INFO - Successfully processed 2480 records
2025-01-16 10:30:16 - INFO - Successfully exported 2480 records to frappe_hr_employee_checkin.xlsx
2025-01-16 10:30:16 - INFO - Migration completed successfully! Output file: frappe_hr_employee_checkin.xlsx
2025-01-16 10:30:16 - INFO - Total records migrated: 2480
```

This migration script provides a robust solution for transferring your employee attendance data from the deprecated system to Frappe HR.
