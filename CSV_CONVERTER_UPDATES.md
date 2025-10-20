# CSV to Frappe HR Converter - Updates

## 🎉 New Features Implemented

Two important features have been added to the CSV to Frappe HR Converter tool as requested.

---

## ✅ Feature 1: MongoDB Username Lookup

### What It Does
Instead of using the full name from the CSV file in the output, the tool now:
1. Extracts the full name from the uploaded CSV
2. Searches the MongoDB `employees` collection by matching the `full_name` field
3. Retrieves the `username2` field (or falls back to `username` if username2 doesn't exist)
4. Uses the username in the Employee column of the output file

### How It Works

**Before:**
```csv
ID,Employee,Time,Log Type
EMP-CKIN-08-2025-000001,Patricia Bruckner,25-08-2025 17:40:00,IN
```

**After:**
```csv
ID,Employee,Time,Log Type
EMP-CKIN-08-2025-000001,patricia.bruckner,25-08-2025 17:40:00,IN
```

### Technical Details
- **Database**: Connects to MongoDB `bulldog_office` database
- **Collection**: Searches in `employees` collection
- **Fields Used**: `full_name` (search), `username2` (preferred), `username` (fallback)
- **Matching**: Exact match first, then case-insensitive
- **Fallback**: If no match found, uses cleaned name from CSV with a warning

### Code Implementation
```python
def get_username_by_full_name(full_name):
    # Clean the name (remove ID in parentheses)
    clean_name = full_name.split('(')[0].strip() if '(' in full_name else full_name
    
    # Search in MongoDB
    employee = employees_collection.find_one(
        {"full_name": clean_name},
        {"username2": 1, "username": 1}
    )
    
    # Return username2 or username
    if employee:
        return employee.get("username2") or employee.get("username")
    
    # Fallback to name with warning
    return clean_name
```

---

## ✅ Feature 2: Missing Time Warning & Confirmation

### What It Does
When the uploaded CSV contains missing IN or OUT times, the tool now:
1. **Detects** all records with missing check-in or check-out times
2. **Displays** a warning message with the count of missing times
3. **Shows** a detailed table of which dates/days have missing times
4. **Requires** user confirmation via checkbox before allowing conversion
5. **Disables** the convert button until the user confirms

### User Interface

#### Warning Display
```
⚠️ Missing Time Records Detected
Warning: Found 1 missing check-in or check-out time(s).

📋 View Missing Records (Expanded)
┌─────────────┬─────┬─────────────┬────────────────────────────┐
│ Date        │ Day │ Type        │ Note                       │
├─────────────┼─────┼─────────────┼────────────────────────────┤
│ 25-08-2025  │ MON │ Missing OUT │ No check-out time recorded │
└─────────────┴─────┴─────────────┴────────────────────────────┘

ℹ️ These records will only have the available time (IN or OUT) in the output. 
   The missing time will be skipped.
```

#### Confirmation Required
```
✅ Confirmation Required
☐ I understand there are missing times and want to proceed with conversion

👆 Please confirm above to proceed with conversion.

[🔄 Convert to Frappe HR Format] (DISABLED)
```

#### After Confirmation
```
✅ Confirmation Required
☑ I understand there are missing times and want to proceed with conversion

[🔄 Convert to Frappe HR Format] (ENABLED)
```

### How It Works

1. **Detection Phase**
   - Parses all records from CSV
   - Checks each record for missing IN or OUT times
   - Identifies records where time is empty, None, or "Missing OUT"

2. **Warning Phase**
   - Displays count of issues found
   - Shows expandable table with details
   - Explains what will happen (missing times skipped)

3. **Confirmation Phase**
   - Shows checkbox only if missing times detected
   - Convert button disabled until checkbox is checked
   - User must explicitly acknowledge before proceeding

4. **Conversion Phase**
   - Only available times are included in output
   - Missing IN/OUT times are gracefully skipped
   - No errors thrown for missing data

### Technical Details

```python
def check_for_missing_times(parsed_data):
    missing_details = []
    
    for record in parsed_data['records']:
        # Check for missing IN
        if not in_time or in_time == 'Missing OUT':
            missing_details.append({
                'date': date_display,
                'day': day,
                'type': 'Missing IN',
                'note': 'No check-in time recorded'
            })
        
        # Check for missing OUT
        if not out_time or out_time == 'Missing OUT':
            missing_details.append({
                'date': date_display,
                'day': day,
                'type': 'Missing OUT',
                'note': 'No check-out time recorded'
            })
    
    return {
        'has_missing': len(missing_details) > 0,
        'missing_details': missing_details
    }
```

### User Flow with Missing Times

```
1. Upload CSV
   ↓
2. Parse Data
   ↓
3. Check for Missing Times
   ↓
   ┌─ No Missing Times ─→ Show Options → Convert Button (Enabled)
   │
   └─ Has Missing Times ─→ Show Warning → Show Table → Show Checkbox → Convert Button (Disabled until checked)
```

---

## 📊 Example Scenario

### Input CSV
```csv
Pay Period,,,20250825-20250831,,,
Employee,,,Patricia Bruckner (3),,,
Date,,IN,OUT,Work Time, Daily Total, Note
MON,20250825,17:40,,,,Missing OUT
TUE,20250826,8:37,17:19,8.7,8.7,
FRI,20250829,8:30,18:25,9.92,9.92,
```

### What Happens

1. **Upload**: CSV is uploaded
2. **Parse**: System extracts "Patricia Bruckner (3)"
3. **Lookup**: Searches MongoDB for full_name="Patricia Bruckner"
4. **Find**: Gets username2="patricia.bruckner"
5. **Detect**: Finds MON missing OUT time
6. **Warn**: Shows warning with 1 missing record
7. **Display**: Table shows "25-08-2025, MON, Missing OUT"
8. **Block**: Convert button is disabled
9. **User**: Checks confirmation checkbox
10. **Enable**: Convert button becomes enabled
11. **Convert**: Generates 5 records (3 IN + 2 OUT, MON OUT skipped)
12. **Output**: Employee column shows "patricia.bruckner" not "Patricia Bruckner"

### Output File
```csv
ID,Employee,Time,Log Type
EMP-CKIN-08-2025-000001,patricia.bruckner,25-08-2025 17:40:00,IN
EMP-CKIN-08-2025-000002,patricia.bruckner,26-08-2025 08:37:00,IN
EMP-CKIN-08-2025-000003,patricia.bruckner,26-08-2025 17:19:00,OUT
EMP-CKIN-08-2025-000004,patricia.bruckner,29-08-2025 08:30:00,IN
EMP-CKIN-08-2025-000005,patricia.bruckner,29-08-2025 18:25:00,OUT
```

**Note**: MON OUT is missing, so only the MON IN time is included.

---

## 🔧 Files Modified

### 1. Main Application File
**`pages/9 CSV to Frappe HR.py`**

**Changes:**
- Added MongoDB connection imports and setup
- Added `get_username_by_full_name()` function
- Added `check_for_missing_times()` function
- Updated `convert_to_frappe_format()` to use username lookup
- Added missing time warning display in UI
- Added missing records table display
- Added confirmation checkbox for missing times
- Modified convert button to be disabled until confirmation
- Updated example output to show username format

**New Dependencies:**
```python
from pymongo import MongoClient
from dotenv import load_dotenv
```

### 2. Documentation
**`documentation/CSV_TO_FRAPPE_GUIDE.md`**

**Changes:**
- Added missing time warning to Step 2
- Added new Step 5 for confirmation process
- Updated step numbers (Step 6 → Step 7)
- Added Database Integration feature section
- Updated output format tables (username instead of full name)
- Added "Important" note about username lookup
- Added troubleshooting for "Employee not found"
- Added troubleshooting for "Can't convert due to missing times"
- Updated all examples to show usernames

---

## 🎯 Benefits

### For Users
1. **Accurate Employee Identification**: Uses database usernames, not CSV names
2. **Data Consistency**: Frappe HR gets standardized usernames
3. **Error Prevention**: Can't accidentally convert files with data issues
4. **Transparency**: See exactly what's missing before converting
5. **Informed Decisions**: Understand what will be in the output

### For Admins
1. **Data Quality**: Ensures username consistency across systems
2. **Audit Trail**: Users must acknowledge missing data
3. **Error Reduction**: Less manual correction needed
4. **Database Linkage**: Properly connects to existing employee records

---

## 🧪 Testing

### Test Case 1: Normal Employee with Complete Data
- ✅ Full name lookup works
- ✅ Username correctly retrieved
- ✅ No warnings shown
- ✅ Convert button enabled immediately
- ✅ Output uses username

### Test Case 2: Employee Not in Database
- ✅ Warning displayed
- ✅ Falls back to cleaned name
- ✅ Conversion still works
- ✅ User informed of issue

### Test Case 3: Missing OUT Time
- ✅ Missing time detected
- ✅ Warning table shows details
- ✅ Convert button disabled
- ✅ Checkbox required
- ✅ Only IN time in output

### Test Case 4: Missing IN Time
- ✅ Missing IN detected correctly
- ✅ Only OUT time in output

### Test Case 5: Multiple Missing Times
- ✅ All missing times listed
- ✅ Count accurate
- ✅ Table shows all issues

---

## 📝 Important Notes

### Database Field Priority
1. **First Choice**: `username2` field
2. **Fallback**: `username` field
3. **Last Resort**: Cleaned name from CSV (with warning)

### Matching Logic
1. **Exact Match**: Searches for exact `full_name` match
2. **Case Insensitive**: Falls back to case-insensitive regex search
3. **Clean Name**: Removes ID in parentheses before searching

### Missing Time Handling
- **Empty strings**: Treated as missing
- **None values**: Treated as missing
- **"Missing OUT" text**: Treated as missing
- **Valid times**: Processed normally

---

## 🚀 How to Use

### For Normal Files (No Issues)
1. Upload CSV
2. Review extracted info
3. Configure options
4. Click Convert
5. Download files

### For Files with Missing Times
1. Upload CSV
2. Review extracted info
3. **See warning** about missing times
4. **Expand table** to see which records
5. **Read the note** about what will happen
6. **Check the confirmation box**
7. Click Convert (now enabled)
8. Download files

### If Employee Not Found
1. Tool shows warning: "⚠️ Employee 'Name' not found in database"
2. Check the employee's full_name in MongoDB
3. Either:
   - Fix the name in CSV to match database
   - Add/update employee in database
   - Proceed with name from CSV (output will use name, not username)

---

## 🎓 For Developers

### Adding to Codebase
The changes are modular and don't break existing functionality:
- MongoDB connection is optional (won't crash if not available)
- Username lookup has fallback behavior
- Missing time check can be disabled by removing UI elements
- All existing parameters and functions still work

### Database Schema Required
```javascript
// employees collection
{
  _id: ObjectId,
  full_name: String,        // Used for matching
  username: String,          // Fallback field
  username2: String,         // Preferred field (optional)
  // ... other fields
}
```

---

## ✅ Status

**Implementation**: Complete  
**Testing**: Passed  
**Documentation**: Updated  
**Linting**: Clean (no errors)  
**Ready**: Production Ready

---

**Date**: October 17, 2025  
**Version**: 1.1  
**Previous Version**: 1.0

