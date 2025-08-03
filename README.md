# Bulldog Office - Timecard Management System

## Overview

Bulldog Office is a comprehensive web-based timecard management system designed for businesses that need to track employee work hours, manage overtime, and generate detailed reports. Built with Streamlit and MongoDB, it provides an intuitive interface for managing employee time tracking with Austrian holiday integration.

## Features

### 🕒 Time Tracking
- **Check-in/out recording** with automatic duration calculation
- **Break time management** with configurable rules
- **Overtime tracking** with running balances
- **Holiday hours management** with Austrian holiday integration

### 👥 Employee Management
- **Employee profiles** with contact information
- **Overtime balance tracking** per employee
- **User authentication** with secure login
- **Bulk employee operations**

### 📊 Reporting & Analytics
- **PDF report generation** with professional formatting
- **Email integration** for automatic report delivery
- **Date range filtering** for custom reports
- **Overtime and holiday summaries**

### 📅 Calendar Management
- **Austrian public holiday integration**
- **Custom event management**
- **Weekend detection and tracking**
- **Holiday hours calculation**

### 📁 Data Processing
- **CSV file upload** for single employees
- **Bulk timecard processing** for multiple employees
- **Data validation** and error checking
- **Interactive data editing**

## Documentation

### 📖 User Guides

| Guide | Description | Audience |
|-------|-------------|----------|
| **[Quick Start Guide](QUICK_START_GUIDE.md)** | Get up and running in 5 minutes | New users |
| **[User Guide](USER_GUIDE.md)** | Comprehensive system documentation | All users |
| **[Bulk Timecard Guide](BULK_TIMECARD_GUIDE.md)** | Processing multiple employee timecards | Data processors |
| **[Employee Management Guide](EMPLOYEE_MANAGEMENT_GUIDE.md)** | Managing employee profiles and data | Administrators |
| **[Calendar Guide](CALENDAR_GUIDE.md)** | Holiday and event management | HR managers |

### 🚀 Getting Started

1. **Read the [Quick Start Guide](QUICK_START_GUIDE.md)** for immediate setup
2. **Review the [User Guide](USER_GUIDE.md)** for comprehensive instructions
3. **Explore specific guides** based on your role and needs

## System Requirements

### Technical Requirements
- **Python 3.12.5** or higher
- **Modern web browser** (Chrome, Firefox, Safari, Edge)
- **Internet connection** for web access
- **MongoDB database** for data storage

### Dependencies
```
pandas==2.2.3
openpyxl==3.1.5
fpdf==1.7.2
streamlit==1.42.0
streamlit-calendar==1.2.1
reportlab==4.3.1
python-dotenv==1.0.1
pymongo==4.11.2
streamlit-extras==0.7.1
```

## Installation & Setup

### Prerequisites
1. **Python environment** with required version
2. **MongoDB instance** (local or cloud)
3. **Environment variables** configured

### Installation Steps
1. **Clone the repository**
2. **Install dependencies**: `pip install -r requirements.txt`
3. **Configure environment variables**:
   - `MONGODB_CLIENT`: MongoDB connection string
   - Email settings for report delivery
4. **Run the application**: `streamlit run Login.py`

## Usage

### For End Users
1. **Login** with your credentials
2. **Upload timecard data** via CSV files
3. **Review and edit** data as needed
4. **Generate reports** for payroll
5. **Email reports** to employees

### For Administrators
1. **Manage employee profiles** in Employee Management
2. **Configure holiday calendar** with company events
3. **Process bulk timecard data** for multiple employees
4. **Generate comprehensive reports** for management

### For HR Managers
1. **Track holiday hours** and usage
2. **Manage overtime balances** per employee
3. **Configure holiday rules** and pay rates
4. **Generate compliance reports**

## File Formats

### Single Employee CSV
```csv
Day,Date,IN,OUT,Note
Monday,2025-01-01,09:00,17:00,Regular day
Tuesday,2025-01-02,08:30,17:30,Overtime
```

### Bulk CSV Format
```csv
Pay Period,,,2025-01-01 to 2025-01-15
Employee,,,John Doe
Day,Date,IN,OUT,Total,Note
Monday,2025-01-01,09:00,17:00,8:00,Regular day
```

## Key Features Explained

### Time Calculation
- **Work Duration**: OUT - IN - Break
- **Overtime**: Work Time - Standard Time (8 hours)
- **Holiday Work**: Special rates for holiday hours
- **Weekend Work**: Separate tracking and rates

### Holiday Management
- **Austrian Holidays**: Automatic detection and marking
- **Custom Events**: Company-specific holidays and events
- **Holiday Hours**: Tracking used vs. available time
- **Pay Rates**: Different rates for holiday work

### Data Processing
- **Validation**: Automatic format and logic checking
- **Editing**: Interactive data tables for corrections
- **Bulk Operations**: Process multiple employees efficiently
- **Backup**: Temporary and permanent data storage

## Support & Troubleshooting

### Common Issues
- **Login problems**: Check credentials and contact admin
- **Upload errors**: Verify file format and size
- **Calculation issues**: Check time format (HH:MM)
- **Report generation**: Ensure all required data is present

### Getting Help
1. **Check the documentation** for your specific issue
2. **Review troubleshooting sections** in relevant guides
3. **Contact your system administrator** for technical issues
4. **Provide detailed information** about the problem

## Development

### Project Structure
```
bulldog_office/
├── Login.py                 # Authentication system
├── employee_manager.py      # Database operations
├── utils.py                 # Utility functions
├── pages/                   # Streamlit pages
│   ├── 1 Home.py           # Main timecard upload
│   ├── 2 Bulk Timecard.py  # Bulk processing
│   ├── 3 Work History.py   # Permanent records
│   ├── 4 Temp Work History.py # Temporary data
│   ├── 5 Calendar.py       # Holiday management
│   └── 6 Employee Management.py # Employee profiles
├── calendar_events.json     # Holiday data
├── requirements.txt         # Python dependencies
└── documentation/           # User guides
```

### Database Schema
- **employees**: Employee profiles and information
- **users**: Authentication data
- **work_history**: Permanent timecard records
- **temp_work_history**: Temporary timecard data

## Contributing

### For Users
- **Report bugs** with detailed information
- **Suggest features** through your administrator
- **Share feedback** on usability and functionality

### For Developers
- **Follow Python coding standards**
- **Add tests** for new features
- **Update documentation** for changes
- **Maintain backward compatibility**

## License

This project is proprietary software. All rights reserved.

## Contact

For technical support or questions:
- **System Administrator**: Contact your IT department
- **Feature Requests**: Submit through your administrator
- **Bug Reports**: Include detailed steps and error messages

---

**Ready to get started?** Begin with the [Quick Start Guide](QUICK_START_GUIDE.md) for immediate setup instructions.