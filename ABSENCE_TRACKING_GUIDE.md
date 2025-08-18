# Absence Tracking Guide

## Overview

The Absence Tracking feature allows you to manage employee absences like vacation, sick leave, and other types of time off. This feature automatically fills missing days in the work history, making it easy to track and manage employee absences.

## Problem Solved

**Before**: When employees were on vacation or sick leave for multiple weeks, the system only showed days with actual clock-in/out data, making it impossible to record absences.

**After**: The system now automatically fills missing days with placeholder entries, allowing you to add absence types for any day in the selected period.

## How It Works

### 1. Automatic Missing Days Detection

When you load a work history period, the system automatically:
- **Detects gaps** in the work history
- **Fills missing days** with placeholder entries
- **Shows all days** in the selected date range
- **Preserves existing data** while adding missing days

### 2. Absence Type Management

You can assign different absence types to days:

| Absence Type | Description | Pay Status | Hours Counted |
|--------------|-------------|------------|---------------|
| **Vacation** | Paid time off | Paid | Standard hours |
| **Sick** | Illness-related absence | Usually paid | Standard hours |
| **Personal** | Personal time off | May be paid/unpaid | Standard hours |
| **Unpaid** | Unpaid leave | Unpaid | 0 hours |
| **Holiday** | Company/public holiday | Paid | Standard hours |
| **Weekend** | Weekend days | Unpaid | 0 hours |
| **Other** | Miscellaneous absence | Varies | Standard hours |

## Using the Feature

### Step 1: Load Work History

1. **Go to "Work History"** page
2. **Select an employee** from the dropdown
3. **Choose date range** (Pay Period From/To)
4. **Click "Load selected period"**

The system will automatically fill missing days and show all days in the range.

### Step 2: Apply Absence Types

#### Option A: Bulk Apply Absence Type

1. **Select absence type** from the dropdown
2. **Click "Apply Absence Type"**
3. **System applies** the selected type to all empty days

#### Option B: Manual Entry

1. **Edit the "Absence Type" column** in the data table
2. **Select appropriate absence type** for each day
3. **Save changes** when finished

### Step 3: Review and Save

1. **Check the absence summary** at the bottom
2. **Verify all absences** are correctly marked
3. **Click "Save Changes"** to update the database

## Absence Summary

The system provides a real-time summary showing:

- **Total Days**: All days in the selected period
- **Work Days**: Days with actual clock-in/out times
- **Absence Days**: Days marked as various absence types
- **Absence Breakdown**: Count of each absence type

## Best Practices

### For HR Managers

1. **Review absences monthly** to ensure accuracy
2. **Update absence types** when employees return
3. **Document absence reasons** in the Notes column
4. **Verify holiday hours** are correctly deducted

### For Administrators

1. **Set up absence policies** for your organization
2. **Train employees** on absence reporting procedures
3. **Regularly audit** absence records for compliance
4. **Generate absence reports** for management

### For Employees

1. **Report absences** promptly when returning
2. **Provide documentation** for extended absences
3. **Check absence balances** regularly
4. **Update absence types** if circumstances change

## Common Scenarios

### Extended Vacation

1. **Load work history** for the vacation period
2. **Apply "vacation"** absence type to all days
3. **Verify holiday hours** are deducted correctly
4. **Save changes** to update records

### Sick Leave

1. **Load work history** for the sick period
2. **Apply "sick"** absence type to all days
3. **Add notes** with illness details if needed
4. **Save changes** to update records

### Personal Leave

1. **Load work history** for the leave period
2. **Apply "personal"** absence type to all days
3. **Add notes** with reason for leave
4. **Save changes** to update records

### Unpaid Leave

1. **Load work history** for the leave period
2. **Apply "unpaid"** absence type to all days
3. **Note**: These days count 0 hours toward overtime
4. **Save changes** to update records

## Troubleshooting

### Issue: Missing days not filled

**Solution**:
- Check that you've selected a date range
- Click "Load selected period" again
- Use "Fill Missing Days" button if needed

### Issue: Wrong absence type applied

**Solution**:
- Edit the "Absence Type" column manually
- Use "Apply Absence Type" to bulk update
- Save changes to update the database

### Issue: Absence not showing in reports

**Solution**:
- Ensure absence type is selected (not empty)
- Check that changes are saved
- Verify the date range includes the absence period

### Issue: Holiday hours not updating

**Solution**:
- Check that vacation/sick leave is marked correctly
- Verify holiday hours calculation settings
- Contact administrator if issues persist

## Advanced Features

### Custom Absence Types

You can add custom absence types by:
1. **Editing the code** to add new absence types
2. **Updating absence mappings** in the system
3. **Testing with sample data** before production use

### Absence Reporting

Generate absence reports by:
1. **Loading work history** for the reporting period
2. **Reviewing absence summary** at the bottom
3. **Exporting data** for further analysis
4. **Generating PDF reports** with absence details

### Integration with Payroll

Absence data integrates with:
- **Overtime calculations** (affects running balances)
- **Holiday hour tracking** (deducts from available hours)
- **Payroll reports** (includes absence information)
- **Compliance reporting** (tracks required absence types)

## Tips and Tricks

### Quick Absence Entry

1. **Use bulk operations** for extended absences
2. **Copy absence patterns** from previous periods
3. **Use keyboard shortcuts** for faster data entry
4. **Save frequently** to avoid data loss

### Data Validation

1. **Check absence totals** match expected days
2. **Verify holiday hours** are correctly deducted
3. **Review overtime calculations** for accuracy
4. **Validate absence types** against company policy

### Reporting

1. **Generate monthly absence reports**
2. **Track absence trends** over time
3. **Monitor compliance** with absence policies
4. **Export data** for external analysis

---

*This guide covers the absence tracking feature. For general system help, refer to the main User Guide.* 