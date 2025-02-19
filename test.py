import pandas as pd
from fpdf import FPDF
import os
from datetime import datetime, timedelta


# File paths
csv_file_path = "NGTecoTime report-20250101-20250131-January.csv"
xlsm_file_path = "25_Working_Hours_Osman_Kocabel_original.xlsm"
output_pdf_folder = "Monthly_PDF_Reports"

# Load CSV data
csv_data = pd.read_csv(csv_file_path)
csv_data.columns = csv_data.columns.str.strip()

# Load Excel data
xlsm_data = pd.ExcelFile(xlsm_file_path)
all_data_df = xlsm_data.parse("AllData")

# Merge CSV data into AllData sheet
# csv_data = csv_data.rename(columns={
#     'Date': 'Day',
#     'Unnamed: 1': 'Date',
#     'IN': 'Check In',
#     'OUT': 'Check Out',
#     'Work Time': 'Work Hours'
# })
csv_data['Date'] = pd.to_datetime(csv_data['Date'], format='%Y%m%d')

all_data_df = all_data_df.merge(csv_data, on=['Date', 'Day'], how='left', suffixes=('', '_new'))
all_data_df['Check In'] = all_data_df['Check In_new'].combine_first(all_data_df['Check In'])
all_data_df['Check Out'] = all_data_df['Check Out_new'].combine_first(all_data_df['Check Out'])
all_data_df['Work Hours'] = all_data_df['Work Hours_new'].combine_first(all_data_df['Work Hours'])
all_data_df = all_data_df.drop(columns=['Check In_new', 'Check Out_new', 'Work Hours_new'])

# Ensure output folder exists
os.makedirs(output_pdf_folder, exist_ok=True)
def timestamp_to_hms(timestamp_str):
    # Convert timestamp string to datetime
    dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

    # Convert to timedelta relative to midnight of the same day
    delta = timedelta(hours=dt.hour, minutes=dt.minute, seconds=dt.second)

    # Extract hours, minutes, and seconds
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    return hours, minutes, seconds

# Function to apply break rules
def calculate_breaks(work_time):
    if pd.isna(work_time) or work_time == '00:00:00':
        return '00:00:00'
    hours, minutes, seconds = timestamp_to_hms(str(work_time))
    work_time = f"{hours}:{minutes}:{seconds}"
    work_time = pd.to_timedelta(work_time)
    if work_time > pd.Timedelta(hours=6):
        work_time -= pd.Timedelta(minutes=30)
    return str(work_time)

# Apply break adjustments
all_data_df['Adjusted Work Hours'] = all_data_df['Work Hours'].apply(calculate_breaks)

# Generate PDFs
def generate_employee_pdf(employee_name, employee_data):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", style='B', size=16)
    pdf.cell(200, 10, f"Work Report - {employee_name}", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, f"Remaining Vacation Hours: {employee_data.iloc[-1]['Remaining Vacation']}", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", style='B', size=12)
    pdf.cell(40, 10, "Date", 1)
    pdf.cell(40, 10, "Check In", 1)
    pdf.cell(40, 10, "Check Out", 1)
    pdf.cell(40, 10, "Work Hours", 1)
    pdf.cell(40, 10, "Breaks", 1)
    pdf.ln()
    
    pdf.set_font("Arial", size=10)
    for _, row in employee_data.iterrows():
        pdf.cell(40, 10, str(row['Date']), 1)
        pdf.cell(40, 10, str(row['Check In']), 1)
        pdf.cell(40, 10, str(row['Check Out']), 1)
        pdf.cell(40, 10, str(row['Adjusted Work Hours']), 1)
        pdf.cell(40, 10, "00:30:00" if row['Work Hours'] > '06:00:00' else "00:00:00", 1)
        pdf.ln()
    
    pdf_file_path = os.path.join(output_pdf_folder, f"{employee_name}_Work_Report.pdf")
    pdf.output(pdf_file_path)
    print(f"Generated PDF: {pdf_file_path}")

# Generate reports for each employee
for employee in all_data_df['Employee'].unique():
    employee_data = all_data_df[all_data_df['Employee'] == employee]
    generate_employee_pdf(employee, employee_data)
