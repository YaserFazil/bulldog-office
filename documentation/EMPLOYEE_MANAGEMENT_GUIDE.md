# Employee Management Guide

## Overview

The Employee Management system allows you to add, edit, and manage employee profiles in the Bulldog Office system. This is where you maintain all employee information, including contact details, work schedules, and overtime balances.

## Accessing Employee Management

1. Navigate to the **"Employee Management"** page
2. You'll see a table with all current employees
3. Use the interactive interface to manage employee data

## Employee Information Fields

### Required Fields

| Field | Description | Format | Notes |
|-------|-------------|--------|-------|
| **Full Name** | Employee's complete name | Text | Must be unique |
| **Username** | Login username | Text | Must be unique, no spaces |
| **Email** | Contact email address | Email format | Must be unique |

### Optional Fields

| Field | Description | Format | Default |
|-------|-------------|--------|---------|
| **Hours Overtime** | Current overtime balance | HH:MM | 00:00 |
| **Date Joined** | When employee was added | Date | Current date |

## Adding New Employees

### Method 1: Using the Data Editor

1. **Click "Add Row"** in the employee table
2. **Fill in required fields**:
   - Full Name: Employee's complete name
   - Username: Unique login username
   - Email: Valid email address
3. **Add optional fields** if needed
4. **Click "Save Changes"**

### Method 2: Using the Form

1. **Scroll to the form section** (if no employees exist)
2. **Fill in the form fields**:
   - Full name
   - Username
   - Email
3. **Click "Submit"**

### Username Guidelines

- **Must be unique** across all employees
- **No spaces** allowed
- **Use lowercase** letters and numbers
- **Examples**: john.doe, jane_smith, employee123

### Email Guidelines

- **Must be unique** across all employees
- **Use valid email format**: user@domain.com
- **Check for typos** before saving
- **Consider using company email** addresses

## Editing Employee Information

### Making Changes

1. **Click on any cell** in the employee table
2. **Make your changes**
3. **Click "Save Changes"**
4. **Wait for confirmation** message

### Editable Fields

- **Full Name**: Update if employee's name changes
- **Username**: Change login username (must be unique)
- **Email**: Update contact email
- **Hours Overtime**: Adjust overtime balance
- **Date Joined**: Correct join date if needed

### Important Notes

- **Username changes** affect login credentials
- **Email changes** affect report delivery
- **Overtime adjustments** should be documented
- **Name changes** should be communicated to the employee

## Deleting Employees

### When to Delete

- **Employee has left** the company
- **Duplicate entries** need to be removed
- **Test accounts** need cleanup

### Deletion Process

1. **Select the employee row** to delete
2. **Click "Delete"** or use delete function
3. **Confirm the action**
4. **Wait for confirmation** message

### Important Warnings

⚠️ **Deletion is permanent** and cannot be undone
⚠️ **All work history** for the employee will be deleted
⚠️ **Associated data** will be permanently removed

### Alternative to Deletion

Consider **archiving** instead of deleting:
1. **Change username** to include "_ARCHIVED"
2. **Update email** to archive@company.com
3. **Add note** in Full Name field
4. **Keep data** for historical purposes

## Managing Overtime Balances

### Understanding Overtime

- **Positive balance**: Employee has earned overtime
- **Negative balance**: Employee owes time
- **Format**: HH:MM (e.g., 05:30 for 5.5 hours)

### Adjusting Overtime

1. **Click on Hours Overtime cell**
2. **Enter new balance** in HH:MM format
3. **Save changes**
4. **Document the reason** for adjustment

### Common Overtime Scenarios

| Scenario | Action | Example |
|----------|--------|---------|
| **Employee worked extra** | Add hours | 02:00 → 04:30 |
| **Employee took time off** | Subtract hours | 05:00 → 03:00 |
| **Correction needed** | Set correct balance | 08:00 → 00:00 |
| **New employee** | Set to zero | 00:00 |

### Best Practices

- **Document all changes** with reasons
- **Review overtime regularly** (monthly)
- **Communicate changes** to employees
- **Keep historical records** of adjustments

## Employee Data Validation

### System Checks

The system automatically validates:
- **Unique usernames** across all employees
- **Unique email addresses** across all employees
- **Valid email format**
- **Required field completion**

### Common Validation Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Username already exists" | Duplicate username | Choose different username |
| "Email already exists" | Duplicate email | Use different email address |
| "Invalid email format" | Incorrect email | Check email format |
| "Required field missing" | Empty required field | Fill in all required fields |

## Employee Search and Filtering

### Finding Employees

- **Scroll through the table** to find employees
- **Use browser search** (Ctrl+F) to find specific names
- **Sort by column** by clicking column headers

### Organizing Data

- **Sort by name**: Click "Full Name" header
- **Sort by join date**: Click "Date Joined" header
- **Sort by overtime**: Click "Hours Overtime" header

## Data Export and Backup

### Exporting Employee Data

1. **Select all employee data** in the table
2. **Copy to clipboard** (Ctrl+A, Ctrl+C)
3. **Paste into Excel** or other spreadsheet
4. **Save as backup** file

### Regular Backups

- **Export monthly** for backup purposes
- **Keep historical records** of employee changes
- **Document all modifications** with dates and reasons

## Security Considerations

### Access Control

- **Limit access** to authorized personnel only
- **Use strong passwords** for admin accounts
- **Log out** when finished
- **Don't share credentials**

### Data Privacy

- **Protect employee information** according to privacy laws
- **Secure email addresses** and personal data
- **Follow company policies** for data handling
- **Document data access** and modifications

## Troubleshooting

### Common Issues

#### Issue: "Cannot add employee"
**Possible causes**:
- Username or email already exists
- Required fields are missing
- System is temporarily unavailable

**Solutions**:
- Check for duplicate usernames/emails
- Fill in all required fields
- Try again in a few minutes

#### Issue: "Cannot edit employee"
**Possible causes**:
- Field is read-only
- System is processing changes
- Permission issues

**Solutions**:
- Check if field is editable
- Wait for processing to complete
- Contact administrator if needed

#### Issue: "Cannot delete employee"
**Possible causes**:
- Employee has active work records
- System is processing
- Permission restrictions

**Solutions**:
- Check for associated work history
- Wait for processing to complete
- Contact administrator if needed

### Getting Help

**When to contact support**:
- System errors or crashes
- Data corruption issues
- Permission problems
- Feature requests

**Information to provide**:
- Your username
- Detailed error message
- Steps to reproduce issue
- Screenshots if possible

## Best Practices Summary

### Daily Operations
- [ ] Review new employee additions
- [ ] Check for data accuracy
- [ ] Update information as needed
- [ ] Document any changes

### Weekly Tasks
- [ ] Review overtime balances
- [ ] Check for duplicate entries
- [ ] Verify email addresses
- [ ] Update join dates if needed

### Monthly Tasks
- [ ] Export employee data for backup
- [ ] Review inactive employees
- [ ] Clean up test accounts
- [ ] Update system documentation

### Quarterly Tasks
- [ ] Comprehensive data review
- [ ] Archive old employee records
- [ ] Update security practices
- [ ] Review access permissions

---

*This guide covers employee management features. For other system features, refer to the main User Guide.* 