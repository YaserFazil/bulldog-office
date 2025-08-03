# Bulldog Office - User Guide

## Table of Contents
1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Login System](#login-system)
4. [Home Page - Timecard Upload](#home-page---timecard-upload)
5. [Bulk Timecard Processing](#bulk-timecard-processing)
6. [Work History Management](#work-history-management)
7. [Temporary Work History](#temporary-work-history)
8. [Calendar Management](#calendar-management)
9. [Employee Management](#employee-management)
10. [Troubleshooting](#troubleshooting)
11. [Glossary](#glossary)

---

## Introduction

**Bulldog Office** is a comprehensive timecard management system designed to help businesses track employee work hours, manage overtime, and generate detailed reports. This system is particularly useful for companies that need to:

- Track employee check-in and check-out times
- Calculate work hours and overtime
- Manage holiday and vacation time
- Generate PDF reports for payroll
- Handle bulk timecard data from multiple employees

### Key Features
- **Simple Web Interface**: Easy-to-use web application
- **Employee Management**: Add, edit, and manage employee profiles
- **Time Tracking**: Record daily work hours with automatic calculations
- **Overtime Management**: Track and calculate overtime hours
- **Holiday Integration**: Automatic Austrian holiday detection
- **PDF Reports**: Generate detailed timecard reports
- **Email Integration**: Send reports directly to employees
- **Bulk Processing**: Handle multiple employee timecards at once

---

## Getting Started

### System Requirements
- Modern web browser (Chrome, Firefox, Safari, Edge)
- Internet connection
- Valid login credentials

### Accessing the System
1. Open your web browser
2. Navigate to the Bulldog Office application URL
3. You'll see the login page
4. Enter your username/email and password
5. Click "Login"

---

## Login System

### First Time Login
If this is your first time using the system, you'll need to:
1. Contact your system administrator to get your login credentials
2. Your username can be either your email address or a specific username
3. Enter your password (case-sensitive)

### Login Process
1. **Username/Email Field**: Enter your username or email address
2. **Password Field**: Enter your password
3. **Login Button**: Click to access the system

### Troubleshooting Login Issues
- **"Invalid username/email or password"**: Double-check your credentials
- **Forgotten password**: Contact your system administrator
- **Account locked**: Contact your system administrator

---

## Home Page - Timecard Upload

The Home page is your main workspace for uploading and managing timecard data.

### File Upload Options

#### Option 1: Single CSV Upload
**When to use**: Uploading timecard data for a single employee

**Steps**:
1. Select "Single CSV Upload" from the dropdown
2. Click "Browse files" or drag and drop your CSV file
3. The system will automatically process your file
4. Review the data in the interactive table
5. Make any necessary edits
6. Click "Save Changes" to store the data

**CSV File Format Requirements**:
- Must be a CSV (Comma Separated Values) file
- Should include columns: Day, Date, IN, OUT, Note
- Date format: YYYY-MM-DD or MM/DD/YYYY
- Time format: HH:MM (24-hour format)

#### Option 2: From Bulk Timecard
**When to use**: Selecting data that was previously uploaded via bulk processing

**Steps**:
1. Select "From Bulk Timecard" from the dropdown
2. Choose the employee from the dropdown list
3. The system will load their temporary work data
4. Review and edit the data as needed
5. Click "Save Changes" to make it permanent

### Data Editing Interface

The interactive table allows you to:
- **Edit any cell**: Click on any cell to modify its content
- **Add new rows**: Use the "Add row" button
- **Delete rows**: Select rows and use the delete function
- **Sort data**: Click column headers to sort
- **Filter data**: Use the search/filter options

### Important Fields Explained

#### Time Fields
- **IN**: Employee check-in time (format: HH:MM)
- **OUT**: Employee check-out time (format: HH:MM)
- **Work Time**: Automatically calculated work duration
- **Break**: Break time taken during the day
- **Standard Time**: Expected work hours (usually 8:00)

#### Calculation Fields
- **Difference**: Overtime or undertime compared to standard hours
- **Multiplication**: Pay rate multiplier for overtime
- **Hours Overtime Left**: Running balance of overtime hours
- **Holiday Hours**: Remaining holiday hours

#### Special Fields
- **Holiday**: Type of holiday (sick, vacation, etc.)
- **Note**: Additional comments or notes

### Saving Your Work

**Before saving**:
1. Review all data for accuracy
2. Check that all required fields are filled
3. Verify time formats are correct

**After saving**:
1. You'll see a success message
2. Data is now stored in the permanent database
3. You can generate PDF reports

### PDF Report Generation

**To generate a PDF report**:
1. Click the "Generate PDF Report" button
2. The system will create a detailed report
3. You can download the PDF or email it to the employee

**Report includes**:
- Employee information
- Date range summary
- Daily breakdown
- Overtime calculations
- Holiday hours used
- Total hours worked 