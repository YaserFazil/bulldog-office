# Migration Tool - Enhanced UX Demo

## What's New? 🎉

The migration tool now includes an **interactive user experience** that asks you for your preferences instead of requiring code modifications.

## New Interactive Features

### 1. 📅 Date Filtering
- **What it does**: Export only records from a specific date onwards
- **Use case**: Incremental migrations, partial data exports
- **How it works**: Enter a date in `YYYY-MM-DD` format, or press Enter to export all records

### 2. 🆔 Optional ID Generation
- **What it does**: Choose whether to include unique IDs in the output
- **Use case**: 
  - With IDs: When Frappe HR requires unique identifiers
  - Without IDs: When you want a simpler format or will generate IDs in Frappe HR
- **How it works**: Answer `y` or `n` when prompted

## Example Usage

### Scenario 1: Export All Records with IDs (Default)

```bash
$ python migrate_to_frappe_hr.py

🚀 Frappe HR Migration Tool
============================================================

📅 Export Date Filter
------------------------------------------------------------
Enter a start date to export only records from that date onwards.
Leave empty to export ALL records.

Start date (YYYY-MM-DD) or press Enter for all: [Press Enter]
✅ Exporting all records (no date filter)

🆔 Unique ID Generation
------------------------------------------------------------
Generate unique IDs in format: EMP-CKIN-{month}-2025-{sequence}

Include unique IDs? (y/n) [y]: [Press Enter]
✅ Will generate unique IDs for each record

🔄 Starting migration process...
```

**Output columns**: ID, Employee, Time, Log Type

---

### Scenario 2: Export Records from Sept 2025 Onwards, No IDs

```bash
$ python migrate_to_frappe_hr.py

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

**Output columns**: Employee, Time, Log Type

---

### Scenario 3: Recent Records Only (Last Month)

```bash
$ python run_migration.py

Start date (YYYY-MM-DD) or press Enter for all: 2025-09-16
✅ Will export records from 2025-09-16 onwards

Include unique IDs? (y/n) [y]: y
✅ Will generate unique IDs for each record
```

**Result**: Only records from Sept 16, 2025 onwards with IDs

---

## Output File Formats

### With IDs Enabled:
```csv
ID,Employee,Time,Log Type
EMP-CKIN-09-2025-000001,john.doe,15-09-2025 09:00:00,IN
EMP-CKIN-09-2025-000002,john.doe,15-09-2025 17:00:00,OUT
EMP-CKIN-09-2025-000003,jane.smith,15-09-2025 08:30:00,IN
```

### With IDs Disabled:
```csv
Employee,Time,Log Type
john.doe,15-09-2025 09:00:00,IN
john.doe,15-09-2025 17:00:00,OUT
jane.smith,15-09-2025 08:30:00,IN
```

## Benefits

✅ **No Code Editing** - Just run and answer prompts  
✅ **Flexible Exports** - Choose exactly what you need  
✅ **User-Friendly** - Clear instructions and validation  
✅ **Error Prevention** - Validates date format automatically  
✅ **Timestamped Files** - Output files include timestamp to prevent overwrites

## Scripts Available

1. **`python migrate_to_frappe_hr.py`** - Main interactive migration
2. **`python run_migration.py`** - Same features with extra user guidance
3. **`python migrate_to_csv.py`** - CSV-only export (also updated with new features)

## Quick Reference

| Feature | Default | Options |
|---------|---------|---------|
| Date Filter | All records | Any date in YYYY-MM-DD format |
| ID Generation | Enabled (y) | y = with IDs, n = without IDs |
| Output Format | Excel + CSV | Both formats always generated |
| File Naming | Auto-timestamped | `frappe_hr_employee_checkin_{timestamp}` |

---

**Ready to use?** Just run `python migrate_to_frappe_hr.py` and follow the prompts! 🚀


