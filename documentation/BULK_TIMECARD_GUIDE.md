# Bulk Timecard Processing Guide

## Overview

The Bulk Timecard feature allows you to process timecard data for multiple employees from a single CSV file. This is particularly useful when you receive consolidated timecard reports from your payroll system or when multiple employees submit their timecards in a combined format.

## When to Use Bulk Processing

- **Multiple employees in one file**: When your timecard system exports data for all employees in a single file
- **Payroll system integration**: When importing data from external payroll or HR systems
- **Batch processing**: When you need to process timecards for an entire department or company at once
- **Data migration**: When moving data from legacy systems

## File Format Requirements

### Required Structure

Your bulk CSV file must follow this specific format:

```
Pay Period,,,2025-01-01 to 2025-01-15
Employee,,,John Doe
Day,Date,IN,OUT,Total,Note
Monday,2025-01-01,09:00,17:00,8:00,Regular day
Tuesday,2025-01-02,08:30,17:30,9:00,Overtime
Wednesday,2025-01-03,09:00,17:00,8:00,Regular day
...
Total Hours,,,25:00,

Pay Period,,,2025-01-01 to 2025-01-15
Employee,,,Jane Smith
Day,Date,IN,OUT,Total,Note
Monday,2025-01-01,08:00,16:00,8:00,Regular day
Tuesday,2025-01-02,08:00,16:00,8:00,Regular day
...
Total Hours,,,24:00,
```

### Field Descriptions

| Field | Description | Format | Required |
|-------|-------------|--------|----------|
| **Pay Period** | Date range for the timecard | YYYY-MM-DD to YYYY-MM-DD | Yes |
| **Employee** | Employee's full name | Text | Yes |
| **Day** | Day of the week | Monday, Tuesday, etc. | Yes |
| **Date** | Work date | YYYY-MM-DD | Yes |
| **IN** | Check-in time | HH:MM (24-hour) | Yes |
| **OUT** | Check-out time | HH:MM (24-hour) | Yes |
| **Total** | Total hours worked | HH:MM | Optional |
| **Note** | Additional comments | Text | Optional |

### Important Formatting Rules

1. **Date Format**: Use YYYY-MM-DD format (e.g., 2025-01-15)
2. **Time Format**: Use 24-hour format (e.g., 14:30 for 2:30 PM)
3. **Employee Names**: Must match exactly with names in the system
4. **Section Separation**: Each employee section must be clearly separated
5. **Total Hours**: Include a summary row for each employee

## Step-by-Step Process

### Step 1: Prepare Your File

1. **Export from your source system** (if applicable)
2. **Format the data** according to the requirements above
3. **Save as CSV** with UTF-8 encoding
4. **Verify employee names** match those in the system

### Step 2: Upload the File

1. Navigate to the **"Bulk Timecard"** page
2. Click **"Upload CSV file"**
3. Select your prepared CSV file
4. The system will automatically parse and display the data

### Step 3: Review and Edit

1. **Check the parsed data** in the interactive table
2. **Verify employee names** are correctly identified
3. **Review time entries** for accuracy
4. **Make any necessary corrections** using the data editor

### Step 4: Save to Database

1. Click **"Save Changes to Database"**
2. The system will process all employee data
3. You'll see a success message with the number of records saved
4. Data is now stored in **temporary work history**

## Processing Individual Employees

After bulk upload, you need to process each employee individually:

### Step 1: Go to Home Page

1. Navigate to the **"Home"** page
2. Select **"From Bulk Timecard"** from the dropdown
3. Choose the employee you want to process

### Step 2: Review Employee Data

1. The system loads the employee's temporary data
2. Review all entries for accuracy
3. Make any necessary edits
4. Verify overtime and holiday calculations

### Step 3: Make Permanent

1. Click **"Save Changes"**
2. The data moves from temporary to permanent storage
3. Repeat for each employee

## Common Issues and Solutions

### Issue: "Employee not found"

**Cause**: Employee name in CSV doesn't match system records
**Solution**: 
- Check spelling of employee names
- Verify names match exactly (including spaces)
- Add missing employees to the system first

### Issue: "Invalid time format"

**Cause**: Time entries don't follow HH:MM format
**Solution**:
- Convert all times to 24-hour format
- Ensure no extra spaces or characters
- Use leading zeros (e.g., 09:00 not 9:00)

### Issue: "Date format error"

**Cause**: Dates not in YYYY-MM-DD format
**Solution**:
- Convert all dates to YYYY-MM-DD format
- Check for extra spaces or characters
- Verify year, month, and day are correct

### Issue: "Missing required fields"

**Cause**: CSV file missing required columns
**Solution**:
- Ensure all required columns are present
- Check column headers match exactly
- Add missing columns if needed

## Best Practices

### File Preparation
- **Test with small files** first
- **Backup original data** before processing
- **Validate employee names** against system records
- **Check time formats** before upload

### Data Quality
- **Verify all times** are in 24-hour format
- **Ensure IN time** is before OUT time
- **Check for duplicate entries**
- **Validate date ranges** are correct

### Processing Workflow
- **Process one employee at a time** for better control
- **Review data thoroughly** before making permanent
- **Keep backup copies** of original files
- **Document any manual corrections** made

## Advanced Features

### Custom Date Ranges

You can process data for specific date ranges:
1. Upload the bulk file
2. Use date filters in the data editor
3. Process only the relevant time periods

### Data Validation

The system automatically validates:
- Time format consistency
- Date format accuracy
- Employee name matching
- Logical time sequences (IN before OUT)

### Error Reporting

The system provides detailed error messages for:
- Missing required fields
- Invalid time formats
- Unknown employee names
- Data inconsistencies

## Troubleshooting Checklist

Before contacting support, check:

- [ ] File is saved as CSV format
- [ ] UTF-8 encoding is used
- [ ] Employee names match system records
- [ ] Time format is HH:MM (24-hour)
- [ ] Date format is YYYY-MM-DD
- [ ] No extra spaces or special characters
- [ ] File size is under 10MB
- [ ] All required columns are present

## Support Information

If you encounter issues not covered in this guide:

1. **Save a copy** of your original file
2. **Note the exact error message**
3. **Document the steps** you followed
4. **Contact your system administrator** with:
   - Error message
   - File sample (first few rows)
   - Steps to reproduce the issue

---

*This guide covers the bulk timecard processing feature. For general system help, refer to the main User Guide.* 