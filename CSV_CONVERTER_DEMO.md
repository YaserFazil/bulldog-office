# CSV to Frappe HR Converter - Visual Demo

## 🖥️ User Interface Walkthrough

### Step 1: Access the Page

**Navigation**: Sidebar → "CSV to Frappe HR"

```
┌─────────────────────────────────────────────────────┐
│  📄 CSV to Frappe HR Converter                      │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ℹ️ About This Tool                                 │
│  Upload timecard CSV files in NGTecoTime format     │
│  and convert them to Frappe HR compatible Excel/    │
│  CSV files. The tool automatically extracts         │
│  employee information, formats dates and times,     │
│  and generates the proper output format.            │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

### Step 2: Upload CSV File

```
┌─────────────────────────────────────────────────────┐
│  📁 Upload CSV File                                  │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Choose a CSV file in NGTecoTime format             │
│  ┌─────────────────────────────────────────┐       │
│  │  📎 Browse files                         │       │
│  │  Drag and drop file here                 │       │
│  │  Limit 200MB per file • CSV              │       │
│  └─────────────────────────────────────────┘       │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

### Step 3: Review Extracted Information

After uploading `NGTecoTime report-20250825-20250831-1127(in).csv`:

```
┌─────────────────────────────────────────────────────┐
│  📊 Extracted Information                            │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌────────────────────────┐  ┌──────────────────┐  │
│  │ Employee:               │  │ Pay Period:      │  │
│  │ Patricia Bruckner (3)   │  │ 20250825-20250831│  │
│  └────────────────────────┘  └──────────────────┘  │
│                                                      │
│  ✅ Found 3 working day records                     │
│                                                      │
│  ▼ 🔍 View Original Data Preview                    │
│  ┌─────────────────────────────────────────┐       │
│  │ Day    Date      IN      OUT             │       │
│  ├─────────────────────────────────────────┤       │
│  │ MON    20250825  17:40   -               │       │
│  │ TUE    20250826  8:37    17:19           │       │
│  │ FRI    20250829  8:30    18:25           │       │
│  └─────────────────────────────────────────┘       │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

### Step 4: Configure Options

```
┌─────────────────────────────────────────────────────┐
│  ⚙️ Conversion Options                               │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌────────────────────────┐  ┌──────────────────┐  │
│  │ ☑ Include Unique IDs    │  │ Output Format:   │  │
│  │                         │  │ ○ Excel (.xlsx)  │  │
│  │ Generate unique IDs in  │  │ ○ CSV (.csv)     │  │
│  │ format: EMP-CKIN-       │  │ ● Both           │  │
│  │ {month}-{year}-{seq}    │  │                  │  │
│  └────────────────────────┘  └──────────────────┘  │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

### Step 5: Convert Data

```
┌─────────────────────────────────────────────────────┐
│  ┌───────────────────────────────────────────────┐ │
│  │   🔄 Convert to Frappe HR Format              │ │
│  └───────────────────────────────────────────────┘ │
│                                                      │
│  ✅ Successfully converted 5 records!                │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

### Step 6: Preview Converted Data

```
┌─────────────────────────────────────────────────────┐
│  📋 Converted Data Preview                           │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ID                        Employee          Time           Log Type │
│  ───────────────────────────────────────────────────────────────────│
│  EMP-CKIN-08-2025-000001  Patricia Bruckner  25-08-2025 17:40:00  IN │
│  EMP-CKIN-08-2025-000002  Patricia Bruckner  26-08-2025 08:37:00  IN │
│  EMP-CKIN-08-2025-000003  Patricia Bruckner  26-08-2025 17:19:00  OUT│
│  EMP-CKIN-08-2025-000004  Patricia Bruckner  29-08-2025 08:30:00  IN │
│  EMP-CKIN-08-2025-000005  Patricia Bruckner  29-08-2025 18:25:00  OUT│
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

### Step 7: Download Files

```
┌─────────────────────────────────────────────────────┐
│  💾 Download Files                                   │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌────────────────────────┐  ┌──────────────────┐  │
│  │ 📥 Download Excel File  │  │ 📥 Download CSV  │  │
│  │                         │  │      File         │  │
│  └────────────────────────┘  └──────────────────┘  │
│                                                      │
│  Files:                                              │
│  • frappe_hr_patricia_bruckner_20251017_143052.xlsx │
│  • frappe_hr_patricia_bruckner_20251017_143052.csv  │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

### Step 8: View Summary Statistics

```
┌─────────────────────────────────────────────────────┐
│  📈 Conversion Summary                               │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │  IN      │  │  OUT     │  │  Total Records   │  │
│  │  Records │  │  Records │  │                  │  │
│  │    3     │  │    2     │  │        5         │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## 🎯 Example Workflow

### Scenario: Converting Patricia Bruckner's Timecard

**Input File**: `NGTecoTime report-20250825-20250831-1127(in).csv`

**Input Data**:
```
MON, 20250825, 17:40, -      (Missing OUT)
TUE, 20250826, 8:37, 17:19
FRI, 20250829, 8:30, 18:25
SAT, 20250830, -, -          (Weekend - skipped)
SUN, 20250831, -, -          (Weekend - skipped)
```

**Output Records**: 5 total
- 3 IN records (MON, TUE, FRI)
- 2 OUT records (TUE, FRI)
- MON missing OUT is handled gracefully

**Output File**: `frappe_hr_patricia_bruckner_20251017_143052.xlsx`

**Result**:
```csv
ID,Employee,Time,Log Type
EMP-CKIN-08-2025-000001,Patricia Bruckner,25-08-2025 17:40:00,IN
EMP-CKIN-08-2025-000002,Patricia Bruckner,26-08-2025 08:37:00,IN
EMP-CKIN-08-2025-000003,Patricia Bruckner,26-08-2025 17:19:00,OUT
EMP-CKIN-08-2025-000004,Patricia Bruckner,29-08-2025 08:30:00,IN
EMP-CKIN-08-2025-000005,Patricia Bruckner,29-08-2025 18:25:00,OUT
```

---

## 🎨 Color Scheme & Icons

### Status Indicators:
- ✅ **Green**: Success, completed actions
- ℹ️ **Blue**: Information, helpful tips
- ⚠️ **Yellow**: Warnings, data issues
- ❌ **Red**: Errors, critical issues

### Section Icons:
- 📄 **File/Document**: CSV converter, files
- 📊 **Chart**: Data, statistics, summaries
- 📁 **Folder**: Upload, file management
- 🔄 **Arrows**: Convert, process, transform
- 💾 **Disk**: Download, save
- ⚙️ **Gear**: Settings, options
- 🔍 **Magnifier**: Preview, view details
- 📈 **Chart Up**: Metrics, statistics
- 📋 **Clipboard**: Results, data tables

---

## 📱 Responsive Layout

The interface adapts to different screen sizes:

**Desktop View**:
```
┌─────────────────────────────────────┐
│ ┌────────┐  ┌────────┐             │
│ │ Col 1  │  │ Col 2  │             │
│ └────────┘  └────────┘             │
└─────────────────────────────────────┘
```

**Mobile View**:
```
┌───────────────┐
│ ┌───────────┐ │
│ │  Col 1    │ │
│ └───────────┘ │
│ ┌───────────┐ │
│ │  Col 2    │ │
│ └───────────┘ │
└───────────────┘
```

---

## 🚀 Quick Start Guide

1. **Navigate**: Sidebar → CSV to Frappe HR
2. **Upload**: Click "Browse files" → Select your CSV
3. **Review**: Check extracted employee and pay period
4. **Options**: Toggle IDs on/off, select format
5. **Convert**: Click "Convert to Frappe HR Format"
6. **Download**: Click download button(s)
7. **Import**: Upload to Frappe HR

**Time Required**: ~30 seconds per file

---

## ✨ What Happens Behind the Scenes

```
1. File Upload
   ↓
2. Parse CSV Structure
   • Extract Pay Period: "20250825-20250831"
   • Extract Employee: "Patricia Bruckner (3)"
   • Find data rows (skip headers)
   ↓
3. Process Each Row
   • Parse date: 20250825 → 2025-08-25
   • Parse IN time: 17:40 → 17:40:00
   • Parse OUT time: 17:19 → 17:19:00
   • Skip empty weekend rows
   ↓
4. Generate Records
   • Create IN record with formatted datetime
   • Create OUT record with formatted datetime
   • Generate unique ID (if enabled)
   • Clean employee name
   ↓
5. Create DataFrame
   • Columns: [ID], Employee, Time, Log Type
   • Sort by time (chronological)
   ↓
6. Export Files
   • Excel: .xlsx with openpyxl engine
   • CSV: UTF-8 encoded
   • Filename: auto-generated with timestamp
   ↓
7. Display Results
   • Preview table
   • Summary statistics
   • Download buttons
```

---

## 💡 Pro Tips

1. **Preview First**: Always expand "View Original Data Preview" to verify upload
2. **Check Summary**: Look at IN/OUT counts to spot missing records
3. **Use Both Formats**: Download both Excel and CSV for flexibility
4. **Batch Process**: Process multiple employees back-to-back (files auto-named)
5. **Verify Dates**: Check that date range in filename matches pay period

---

**Ready to try it?** Upload your first CSV file and see the magic happen! ✨

