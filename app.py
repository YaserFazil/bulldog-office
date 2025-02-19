import pandas as pd
import os

# File paths
csv_file_path = "NGTecoTime report-20250101-20250131-January.csv"
xlsm_file_path = "25_Working_Hours_Osman_Kocabel_original.xlsm"
output_file_path = "Updated_Working_Hours.xlsx"

# Load CSV data
csv_data = pd.read_csv(csv_file_path)
csv_data.columns = csv_data.columns.str.strip()

# Load Excel data
xlsm_data = pd.ExcelFile(xlsm_file_path)
import_data_df = xlsm_data.parse("ImportData")
calendar_df = xlsm_data.parse("Calendar")
all_data_df = xlsm_data.parse("AllData")

# # Cleaning and structuring the CSV data
# csv_data = csv_data.rename(columns={
#     'Date': 'Day',
#     'Unnamed: 1': 'Date',
#     'IN': 'Check In',
#     'OUT': 'Check Out',
#     'Work Time': 'Work Hours'
# })
csv_data = csv_data[['Day', 'Date', 'Check In', 'Check Out', 'Work Hours']]
csv_data['Date'] = pd.to_datetime(csv_data['Date'], format='%Y%m%d')

# Merge CSV data into ImportData
import_data_df = import_data_df[['Date', 'Day', 'Check In', 'Check Out', 'Work Hours']]
import_data_df = import_data_df.merge(csv_data, on=['Date', 'Day'], how='left', suffixes=('', '_new'))

# Updating check-in, check-out, and work hours
import_data_df['Check In'] = import_data_df['Check In_new'].combine_first(import_data_df['Check In'])
import_data_df['Check Out'] = import_data_df['Check Out_new'].combine_first(import_data_df['Check Out'])
import_data_df['Work Hours'] = import_data_df['Work Hours_new'].combine_first(import_data_df['Work Hours'])
import_data_df = import_data_df.drop(columns=['Check In_new', 'Check Out_new', 'Work Hours_new'])

# Applying business rules
def adjust_work_hours(row):
    if pd.isna(row['Work Hours']) or row['Work Hours'] == '00:00:00':
        return '00:00:00'
    work_time = pd.to_timedelta(row['Work Hours'])
    if work_time >= pd.Timedelta(hours=6):
        work_time -= pd.Timedelta(minutes=30)
    return str(work_time)

import_data_df['Work Hours'] = import_data_df.apply(adjust_work_hours, axis=1)

# Save updated Excel file
with pd.ExcelWriter(output_file_path, engine='xlsxwriter') as writer:
    import_data_df.to_excel(writer, sheet_name='ImportData', index=False)
    calendar_df.to_excel(writer, sheet_name='Calendar', index=False)
    all_data_df.to_excel(writer, sheet_name='AllData', index=False)

print(f"Updated file saved as {output_file_path}")
