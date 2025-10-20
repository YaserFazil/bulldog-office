# CSV to Frappe HR Converter Guide

## Overview

The **CSV to Frappe HR Converter** is a web-based tool that allows you to convert timecard CSV files from NGTecoTime format into Frappe HR compatible Excel/CSV files. This tool simplifies the process of migrating employee attendance data between different systems.

## When to Use This Tool

Use this tool when you:
- Have timecard data in NGTecoTime CSV format
- Need to import employee check-in/out data into Frappe HR
- Want to convert individual employee timecard files quickly
- Need both Excel and CSV output formats

## Accessing the Tool

1. **Login** to the Bulldog Office system
2. Navigate to **"CSV to Frappe HR"** from the sidebar menu
3. The converter page will open with upload options

## Step-by-Step Guide

### Step 1: Upload Your CSV File

1. Click the **"Browse files"** button in the upload section
2. Select your NGTecoTime format CSV file
3. The file will be automatically processed

### Step 2: Review Extracted Information

Once uploaded, the tool displays:
- **Employee Name**: Extracted from the CSV file
- **Pay Period**: The date range covered in the timecard
- **Record Count**: Number of working day records found
- **Missing Time Warning**: If any IN or OUT times are missing (if applicable)

**Example:**
```
Employee: Patricia Bruckner (3)
Pay Period: 20250825-20250831
✅ Found 3 working day records
```

**If Missing Times Detected:**
```
⚠️ Missing Time Records Detected
Warning: Found 1 missing check-in or check-out time(s).

📋 View Missing Records
Date         Day   Type         Note
25-08-2025   MON   Missing OUT  No check-out time recorded
```

### Step 3: View Original Data Preview

Click the **"View Original Data Preview"** expander to see:
- Original data from your CSV file
- Day of week, dates, IN times, and OUT times
- First 10 records for verification

### Step 4: Configure Conversion Options

**Option 1: Include Unique IDs**
- ✅ **Checked (Default)**: Generates unique IDs in format `EMP-CKIN-{month}-{year}-{sequence}`
- ⬜ **Unchecked**: Exports without IDs (Employee, Time, Log Type only)

**Option 2: Output Format**
- **Excel (.xlsx)**: Download Excel file only
- **CSV (.csv)**: Download CSV file only
- **Both**: Download both Excel and CSV files

### Step 5: Confirm Missing Times (If Applicable)

If the tool detects missing IN or OUT times, you must confirm before converting:

1. Review the **Missing Records** table showing which dates have issues
2. Check the **confirmation checkbox**: "I understand there are missing times and want to proceed with conversion"
3. The convert button will be **disabled** until you confirm

**Note**: Only available times will be included in the output. Missing times are skipped.

### Step 6: Convert the Data

1. Click the **"Convert to Frappe HR Format"** button
2. Wait for the conversion to complete
3. Review the converted data preview

### Step 7: Download Your Files

Click the download button(s) to save:
- **Excel file**: `frappe_hr_{employee}_{timestamp}.xlsx`
- **CSV file**: `frappe_hr_{employee}_{timestamp}.csv`

Files are automatically named with timestamp to prevent overwrites.

## Input File Format

### Expected CSV Structure

```csv
,,,,Timecard Report,,
Pay Period,,,20250825-20250831,,,
Employee,,,Patricia Bruckner (3),,,
Date,,IN,OUT,Work Time, Daily Total, Note
MON,20250825,17:40,,,,Missing OUT
TUE,20250826,8:37,17:19,8.7,8.7,
WED,20250827,,,,,
THU,20250828,,,,,
FRI,20250829,8:30,18:25,9.92,9.92,
SAT,20250830,,,,,
SUN,20250831,,,,,
Total Hours,,,,,18.62,
```

### Required Elements

1. **Pay Period Line**: Must contain "Pay Period" and date range
2. **Employee Line**: Must contain "Employee" and employee name
3. **Data Header**: Must have columns: Date, IN, OUT (minimum)
4. **Data Rows**: Day, Date (YYYYMMDD), IN time, OUT time

### Supported Time Formats

- **H:MM** (e.g., `8:30`, `9:15`)
- **HH:MM** (e.g., `08:30`, `17:19`)

### Data Handling

- ✅ **Empty weekend rows**: Automatically skipped
- ✅ **Missing IN/OUT times**: Only valid times are converted
- ✅ **Notes and special markers**: Handled appropriately (e.g., "Missing OUT")

## Output Format

### With Unique IDs (Default)

| Column | Description | Example |
|--------|-------------|---------|
| ID | Unique identifier | `EMP-CKIN-08-2025-000001` |
| Employee | Employee username (from database) | `patricia.bruckner` |
| Time | Full date and time | `25-08-2025 17:40:00` |
| Log Type | IN or OUT | `IN` |

**Example Output:**
```csv
ID,Employee,Time,Log Type
EMP-CKIN-08-2025-000001,patricia.bruckner,25-08-2025 17:40:00,IN
EMP-CKIN-08-2025-000002,patricia.bruckner,26-08-2025 08:37:00,IN
EMP-CKIN-08-2025-000003,patricia.bruckner,26-08-2025 17:19:00,OUT
EMP-CKIN-08-2025-000004,patricia.bruckner,29-08-2025 08:30:00,IN
EMP-CKIN-08-2025-000005,patricia.bruckner,29-08-2025 18:25:00,OUT
```

**Important**: The Employee column contains the **username** (username2 or username field) looked up from the MongoDB `employees` collection by matching the full name from the CSV file.

### Without Unique IDs

| Column | Description | Example |
|--------|-------------|---------|
| Employee | Employee username (from database) | `patricia.bruckner` |
| Time | Full date and time | `25-08-2025 17:40:00` |
| Log Type | IN or OUT | `IN` |

## Conversion Summary

After conversion, the tool displays:
- **IN Records**: Count of check-in records
- **OUT Records**: Count of check-out records
- **Total Records**: Total records generated

**Example:**
```
IN Records:    3
OUT Records:   2
Total Records: 5
```

## Features

### ✅ Automatic Data Extraction
- Parses employee name and ID from CSV
- Extracts pay period information
- Identifies working days automatically
- **Looks up employee username from MongoDB database**

### ✅ Smart Data Processing
- Skips empty weekend rows
- **Detects and warns about missing IN or OUT times**
- Validates date and time formats
- **Converts full names to usernames via database lookup**

### ✅ Flexible Output Options
- Choose to include or exclude unique IDs
- Export to Excel, CSV, or both formats
- Timestamped filenames prevent overwrites
- Employee name in filename for easy identification

### ✅ Data Validation
- Shows preview of original data
- Displays converted data before download
- Provides summary statistics
- Error handling with clear messages
- **Requires confirmation for missing time records**

### ✅ Database Integration
- **Automatic employee username lookup** from MongoDB
- Searches by full name in the `employees` collection
- Uses `username2` field if available, falls back to `username`
- Case-insensitive matching for flexibility
- Warning shown if employee not found in database

## Use Cases

### Use Case 1: Single Employee Migration
**Scenario**: You have one employee's timecard and need to import it to Frappe HR.

**Steps:**
1. Upload the employee's CSV file
2. Keep "Include Unique IDs" checked
3. Select "Excel (.xlsx)" format
4. Convert and download
5. Import the Excel file into Frappe HR

### Use Case 2: Batch Processing Multiple Employees
**Scenario**: You have CSV files for multiple employees.

**Steps:**
1. Upload first employee's CSV
2. Convert and download (files are auto-named with employee name)
3. Upload second employee's CSV
4. Repeat for all employees
5. Import all generated files into Frappe HR

### Use Case 3: Data Review Before Import
**Scenario**: You want to verify data before importing.

**Steps:**
1. Upload CSV file
2. Review the "Original Data Preview"
3. Check the "Converted Data Preview"
4. Verify the summary statistics
5. Download only if data looks correct

## Troubleshooting

### Issue: "No valid records found to convert"

**Possible Causes:**
- CSV file is empty or improperly formatted
- No IN/OUT times in the data rows
- All rows are weekends with no work

**Solution:**
- Check the CSV file format matches the expected structure
- Ensure there are data rows with IN or OUT times
- Verify the file uploaded is not corrupted

### Issue: "Could not parse time"

**Possible Causes:**
- Time format is not H:MM or HH:MM
- Invalid characters in time field
- Time field contains text instead of numbers

**Solution:**
- Check the time format in your CSV
- Ensure times use colon (:) separator
- Remove any non-numeric characters

### Issue: Employee name has extra characters

**Possible Causes:**
- CSV format has unusual employee name formatting

**Solution:**
- The tool automatically looks up usernames from the database
- Check that the employee's full name in CSV matches the `full_name` in MongoDB
- If the warning appears, verify the employee exists in the database

### Issue: "Employee not found in database"

**Possible Causes:**
- Employee full name in CSV doesn't match `full_name` in MongoDB
- Employee not yet added to the database
- Name has different capitalization or spacing

**Solution:**
- Check the exact spelling in both CSV and database
- Verify employee exists in `employees` collection
- The tool will use the CSV name if no match found
- Consider updating the database with the correct full name

### Issue: Can't convert due to missing times

**Possible Causes:**
- File has missing IN or OUT times
- Confirmation checkbox not checked

**Solution:**
- Review the missing records table
- Check the confirmation checkbox to proceed
- The output will only include available times
- Missing times will be skipped automatically

### Issue: Missing some records in output

**Possible Causes:**
- Empty IN and OUT times are skipped
- Weekend rows without work are excluded
- Invalid date formats

**Solution:**
- Review the original data preview
- Check for any error messages during conversion
- Ensure dates are in YYYYMMDD format

## Best Practices

### 1. File Preparation
✅ **Do:**
- Verify CSV format before upload
- Ensure employee name is clearly stated
- Check that dates are in YYYYMMDD format
- Confirm IN/OUT times use colon separators

❌ **Don't:**
- Modify the CSV structure significantly
- Remove the employee or pay period lines
- Use unsupported date/time formats

### 2. Data Verification
✅ **Do:**
- Always review the original data preview
- Check the converted data preview
- Verify the summary statistics
- Download a test file before batch processing

❌ **Don't:**
- Skip the preview steps
- Ignore warning messages
- Upload without checking the file first

### 3. Output Management
✅ **Do:**
- Use descriptive employee names
- Keep both Excel and CSV copies
- Organize files by pay period
- Verify downloads before deleting source files

❌ **Don't:**
- Overwrite existing files
- Delete source CSV files immediately
- Mix different pay periods

## Tips for Efficient Use

1. **Batch Processing**: Process multiple employee files in sequence
2. **Naming Convention**: Files auto-include employee name and timestamp
3. **Quick Verification**: Use the preview features to catch errors early
4. **Format Consistency**: Use the same ID option for all employees in a batch
5. **Regular Backups**: Keep original CSV files as backup

## Integration with Frappe HR

After generating the files:

1. **Login to Frappe HR**
2. **Navigate to Employee Checkin** module
3. **Use the Import feature**
4. **Upload the generated Excel file**
5. **Map columns** if needed:
   - ID → ID (if included)
   - Employee → Employee
   - Time → Time
   - Log Type → Log Type
6. **Validate and submit** the import

## Frequently Asked Questions

**Q: Can I upload multiple files at once?**  
A: Currently, you need to upload and convert files one at a time. However, the process is quick and files are automatically named to prevent conflicts.

**Q: What happens to weekend days?**  
A: Weekend days (SAT, SUN) with no IN or OUT times are automatically skipped. If there's actual work on weekends, those records are included.

**Q: Can I edit the data after conversion?**  
A: The tool shows a preview but doesn't allow editing. Download the file and edit in Excel if needed before importing to Frappe HR.

**Q: Is there a file size limit?**  
A: The tool can handle typical monthly timecard files. Very large files (>10MB) may take longer to process.

**Q: Can I convert files without logging in?**  
A: No, you must be logged into the Bulldog Office system to use this tool.

**Q: What if the employee name has special characters?**  
A: The tool handles most special characters. Employee IDs in parentheses are automatically removed from the output.

## Support

If you encounter issues:
1. Check this documentation for troubleshooting steps
2. Verify your CSV file format
3. Contact your system administrator with:
   - Description of the issue
   - Sample CSV file (if possible)
   - Error messages displayed

---

**Ready to convert?** Navigate to the CSV to Frappe HR page and upload your first file! 🚀

