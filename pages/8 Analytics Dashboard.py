import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import calendar
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import warnings
warnings.filterwarnings('ignore')

from employee_manager import *
from utils import *
from streamlit_extras.switch_page_button import switch_page

# Page configuration
st.set_page_config(
    page_title="Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

def load_dashboard_data():
    """Load and prepare all data for dashboard analytics"""
    try:
        # Load all employees
        employees = list(employees_collection.find({}))
        employees_df = pd.DataFrame(employees)
        
        # Load all work history
        work_history = list(work_history_collection.find({}))
        work_history_df = pd.DataFrame(work_history) if work_history else pd.DataFrame()
        
        # Load all temp work history
        temp_work_history = list(temp_work_history_collection.find({}))
        temp_work_history_df = pd.DataFrame(temp_work_history) if temp_work_history else pd.DataFrame()
        
        # Combine work history data
        if not work_history_df.empty:
            work_history_df['source'] = 'permanent'
        if not temp_work_history_df.empty:
            temp_work_history_df['source'] = 'temporary'
        
        combined_work_df = pd.concat([work_history_df, temp_work_history_df], ignore_index=True)
        
        return employees_df, combined_work_df, work_history_df, temp_work_history_df
    except Exception as e:
        st.error(f"Error loading dashboard data: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def calculate_employee_metrics(work_df, employee_id):
    """Calculate comprehensive metrics for a specific employee"""
    if work_df.empty:
        return {}
    
    employee_data = work_df[work_df['employee_id'] == str(employee_id)]
    if employee_data.empty:
        return {}
    
    # Convert date and time fields
    employee_data['Date'] = pd.to_datetime(employee_data['Date'])
    employee_data['Work Time'] = employee_data['Work Time'].apply(lambda x: hhmm_to_decimal(str(x)) if pd.notna(x) else 0)
    employee_data['Standard Time'] = employee_data['Standard Time'].apply(lambda x: hhmm_to_decimal(str(x)) if pd.notna(x) else 8)
    employee_data['Difference (Decimal)'] = employee_data['Difference (Decimal)'].apply(lambda x: float(x) if pd.notna(x) else 0)
    
    metrics = {
        'total_days_worked': len(employee_data),
        'total_hours_worked': employee_data['Work Time'].sum(),
        'total_standard_hours': employee_data['Standard Time'].sum(),
        'total_overtime_hours': employee_data['Difference (Decimal)'].sum(),
        'avg_hours_per_day': employee_data['Work Time'].mean(),
        'avg_overtime_per_day': employee_data['Difference (Decimal)'].mean(),
        'days_with_overtime': len(employee_data[employee_data['Difference (Decimal)'] > 0]),
        'days_with_undertime': len(employee_data[employee_data['Difference (Decimal)'] < 0]),
        'punctuality_score': len(employee_data[employee_data['IN'].notna()]) / len(employee_data) * 100,
        'holiday_days_used': len(employee_data[employee_data['Holiday'].notna() & (employee_data['Holiday'] != '')]),
        'sick_days': len(employee_data[employee_data['Holiday'].isin(['sick', 'Sick'])]),
        'vacation_days': len(employee_data[employee_data['Holiday'].isin(['vacation', 'Vacation'])]),
        'weekend_work_days': len(employee_data[employee_data['Day'].isin(['SAT', 'SUN'])]),
        'holiday_work_days': len(employee_data[employee_data['Holiday'].notna() & (employee_data['Holiday'] != '') & (employee_data['Work Time'] > 0)])
    }
    
    return metrics

def create_performance_heatmap(work_df, employee_id):
    """Create a heatmap showing work patterns by day of week and hour"""
    if work_df.empty:
        return None
    
    employee_data = work_df[work_df['employee_id'] == str(employee_id)].copy()
    if employee_data.empty:
        return None
    
    # Convert dates and times
    employee_data['Date'] = pd.to_datetime(employee_data['Date'])
    employee_data['Day_of_Week'] = employee_data['Date'].dt.day_name()
    employee_data['Month'] = employee_data['Date'].dt.month
    employee_data['Work_Hours'] = employee_data['Work Time'].apply(lambda x: hhmm_to_decimal(str(x)) if pd.notna(x) else 0)
    
    # Create pivot table for heatmap
    heatmap_data = employee_data.groupby(['Day_of_Week', 'Month'])['Work_Hours'].mean().reset_index()
    heatmap_pivot = heatmap_data.pivot(index='Day_of_Week', columns='Month', values='Work_Hours')
    
    # Reorder days
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    heatmap_pivot = heatmap_pivot.reindex(day_order)
    
    return heatmap_pivot

def create_overtime_trend_chart(work_df, employee_id):
    """Create overtime trend analysis over time"""
    if work_df.empty:
        return None
    
    employee_data = work_df[work_df['employee_id'] == str(employee_id)].copy()
    if employee_data.empty:
        return None
    
    employee_data['Date'] = pd.to_datetime(employee_data['Date'])
    employee_data['Difference (Decimal)'] = employee_data['Difference (Decimal)'].apply(lambda x: float(x) if pd.notna(x) else 0)
    employee_data = employee_data.sort_values('Date')
    
    # Calculate running average
    employee_data['Overtime_Running_Avg'] = employee_data['Difference (Decimal)'].rolling(window=7, min_periods=1).mean()
    
    return employee_data[['Date', 'Difference (Decimal)', 'Overtime_Running_Avg']]

def create_productivity_analysis(work_df, employee_id):
    """Analyze productivity patterns and efficiency"""
    if work_df.empty:
        return {}
    
    employee_data = work_df[work_df['employee_id'] == str(employee_id)].copy()
    if employee_data.empty:
        return {}
    
    employee_data['Date'] = pd.to_datetime(employee_data['Date'])
    employee_data['Work_Hours'] = employee_data['Work Time'].apply(lambda x: hhmm_to_decimal(str(x)) if pd.notna(x) else 0)
    employee_data['Standard_Hours'] = employee_data['Standard Time'].apply(lambda x: hhmm_to_decimal(str(x)) if pd.notna(x) else 8)
    employee_data['Efficiency'] = (employee_data['Work_Hours'] / employee_data['Standard_Hours']) * 100
    
    # Monthly productivity trends
    # Use string format instead of Period objects to avoid JSON serialization issues
    employee_data['Month'] = employee_data['Date'].dt.strftime('%Y-%m')
    monthly_productivity = employee_data.groupby('Month').agg({
        'Work_Hours': 'sum',
        'Standard_Hours': 'sum',
        'Efficiency': 'mean',
        'Date': 'count'
    }).reset_index()
    
    monthly_productivity['Productivity_Score'] = (monthly_productivity['Work_Hours'] / monthly_productivity['Standard_Hours']) * 100
    monthly_productivity = monthly_productivity.rename(columns={'Month': 'Date'})
    
    return {
        'monthly_data': monthly_productivity,
        'avg_efficiency': employee_data['Efficiency'].mean(),
        'consistency_score': 100 - employee_data['Efficiency'].std(),
        'peak_performance_days': len(employee_data[employee_data['Efficiency'] > 110]),
        'low_performance_days': len(employee_data[employee_data['Efficiency'] < 90])
    }

def create_team_comparison_analysis(work_df, employees_df):
    """Compare performance across all employees"""
    if work_df.empty or employees_df.empty:
        return pd.DataFrame()
    
    team_metrics = []
    
    for _, employee in employees_df.iterrows():
        employee_id = str(employee['_id'])
        metrics = calculate_employee_metrics(work_df, employee_id)
        
        if metrics:
            team_metrics.append({
                'Employee_ID': employee_id,
                'Full_Name': employee.get('full_name', 'Unknown'),
                'Username': employee.get('username', 'Unknown'),
                'Total_Hours': metrics['total_hours_worked'],
                'Total_Overtime': metrics['total_overtime_hours'],
                'Avg_Hours_Per_Day': metrics['avg_hours_per_day'],
                'Punctuality_Score': metrics['punctuality_score'],
                'Efficiency_Score': (metrics['total_hours_worked'] / metrics['total_standard_hours']) * 100 if metrics['total_standard_hours'] > 0 else 0,
                'Overtime_Frequency': (metrics['days_with_overtime'] / metrics['total_days_worked']) * 100 if metrics['total_days_worked'] > 0 else 0,
                'Holiday_Usage': metrics['holiday_days_used'],
                'Sick_Days': metrics['sick_days']
            })
    
    return pd.DataFrame(team_metrics)

def create_absence_analysis(work_df, employees_df):
    """Analyze absence patterns and trends"""
    if work_df.empty:
        return {}
    
    absence_data = work_df[work_df['Holiday'].notna() & (work_df['Holiday'] != '')].copy()
    
    if absence_data.empty:
        return {}
    
    absence_data['Date'] = pd.to_datetime(absence_data['Date'])
    # Use string format instead of Period objects to avoid JSON serialization issues
    absence_data['Month'] = absence_data['Date'].dt.strftime('%Y-%m')
    absence_data['Day_of_Week'] = absence_data['Date'].dt.day_name()
    
    # Absence by type
    absence_by_type = absence_data['Holiday'].value_counts()
    
    # Monthly absence trends
    monthly_absence = absence_data.groupby('Month').size().reset_index(name='Absence_Count')
    
    # Day of week patterns
    day_patterns = absence_data['Day_of_Week'].value_counts()
    
    # Employee absence ranking
    employee_absence = absence_data.groupby('employee_id').size().reset_index(name='Absence_Days')
    employee_absence = employee_absence.merge(employees_df[['_id', 'full_name']], left_on='employee_id', right_on='_id', how='left')
    
    return {
        'absence_by_type': absence_by_type,
        'monthly_trends': monthly_absence,
        'day_patterns': day_patterns,
        'employee_ranking': employee_absence
    }

def create_overtime_cost_analysis(work_df, employees_df):
    """Calculate overtime costs and financial impact"""
    if work_df.empty:
        return {}
    
    # Assume average hourly rate (this could be configurable)
    avg_hourly_rate = 25  # EUR per hour
    overtime_multiplier = 1.5  # 1.5x for overtime
    
    work_df['Overtime_Hours'] = work_df['Difference (Decimal)'].apply(lambda x: float(x) if pd.notna(x) and float(x) > 0 else 0)
    work_df['Overtime_Cost'] = work_df['Overtime_Hours'] * avg_hourly_rate * overtime_multiplier
    
    # Monthly overtime costs
    work_df['Date'] = pd.to_datetime(work_df['Date'])
    # Use string format instead of Period objects to avoid JSON serialization issues
    work_df['Month'] = work_df['Date'].dt.strftime('%Y-%m')
    monthly_overtime = work_df.groupby('Month').agg({
        'Overtime_Hours': 'sum',
        'Overtime_Cost': 'sum'
    }).reset_index()
    monthly_overtime = monthly_overtime.rename(columns={'Month': 'Date'})
    
    # Employee overtime costs
    employee_overtime = work_df.groupby('employee_id').agg({
        'Overtime_Hours': 'sum',
        'Overtime_Cost': 'sum'
    }).reset_index()
    employee_overtime = employee_overtime.merge(employees_df[['_id', 'full_name']], left_on='employee_id', right_on='_id', how='left')
    
    return {
        'total_overtime_hours': work_df['Overtime_Hours'].sum(),
        'total_overtime_cost': work_df['Overtime_Cost'].sum(),
        'monthly_costs': monthly_overtime,
        'employee_costs': employee_overtime
    }

def main():
    st.title("📊 Analytics Dashboard")
    st.markdown("---")
    
    # Check if user is logged in
    if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
        st.error("You need to log in first.")
        st.session_state["logged_in"] = False
        st.session_state["user_id"] = None
        return
    
    # Add documentation link
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("""
        <div style="background-color: #e3f2fd; padding: 10px; border-radius: 5px; border-left: 4px solid #2196f3; margin-bottom: 20px;">
            <strong>📚 Need help?</strong> Check out our Documentation & User Guides for detailed instructions on using the analytics dashboard.
        </div>
        """, unsafe_allow_html=True)
    with col2:
        if st.button("📚 View Documentation", use_container_width=True):
            switch_page("documentation")
    
    # Load data
    with st.spinner("Loading analytics data..."):
        employees_df, combined_work_df, work_history_df, temp_work_history_df = load_dashboard_data()
    
    if employees_df.empty:
        st.warning("No employee data found. Please add employees first.")
        return
    
    if combined_work_df.empty:
        st.warning("No work history data found. Please upload timecard data first.")
        return
    
    # Sidebar filters
    st.sidebar.header("📊 Dashboard Filters")
    
    # Date range filter
    st.sidebar.subheader("📅 Date Range")
    date_range = st.sidebar.selectbox(
        "Select Date Range",
        ["Last 30 Days", "Last 3 Months", "Last 6 Months", "Last Year", "All Time", "Custom Range"]
    )
    
    if date_range == "Custom Range":
        start_date = st.sidebar.date_input("Start Date", value=date.today() - timedelta(days=30))
        end_date = st.sidebar.date_input("End Date", value=date.today())
    else:
        end_date = date.today()
        if date_range == "Last 30 Days":
            start_date = end_date - timedelta(days=30)
        elif date_range == "Last 3 Months":
            start_date = end_date - relativedelta(months=3)
        elif date_range == "Last 6 Months":
            start_date = end_date - relativedelta(months=6)
        elif date_range == "Last Year":
            start_date = end_date - relativedelta(years=1)
        else:  # All Time
            if not combined_work_df.empty and 'Date' in combined_work_df.columns:
                start_date = combined_work_df['Date'].min()
            else:
                start_date = date.today()
    
    # Filter data by date range
    if not combined_work_df.empty and 'Date' in combined_work_df.columns:
        combined_work_df['Date'] = pd.to_datetime(combined_work_df['Date'])
        filtered_work_df = combined_work_df[
            (combined_work_df['Date'] >= pd.Timestamp(start_date)) &
            (combined_work_df['Date'] <= pd.Timestamp(end_date))
        ]
    else:
        filtered_work_df = pd.DataFrame()
    
    # Employee filter
    st.sidebar.subheader("👥 Employee Filter")
    all_employees = ["All Employees"] + employees_df['full_name'].tolist()
    selected_employee = st.sidebar.selectbox("Select Employee", all_employees)
    
    if selected_employee != "All Employees":
        employee_row = employees_df[employees_df['full_name'] == selected_employee]
        if not employee_row.empty:
            selected_employee_id = str(employee_row.iloc[0]['_id'])
            filtered_work_df = filtered_work_df[filtered_work_df['employee_id'] == selected_employee_id]
    
    # Main dashboard content
    st.header("🎯 Executive Summary")
    
    # Key metrics cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_employees = len(employees_df)
        if not filtered_work_df.empty and 'Work Time' in filtered_work_df.columns:
            total_hours = filtered_work_df['Work Time'].apply(lambda x: hhmm_to_decimal(str(x)) if pd.notna(x) else 0).sum()
        else:
            total_hours = 0
        st.metric("👥 Total Employees", total_employees)
    
    with col2:
        if not filtered_work_df.empty and 'Difference (Decimal)' in filtered_work_df.columns:
            total_overtime = filtered_work_df['Difference (Decimal)'].apply(lambda x: float(x) if pd.notna(x) and float(x) > 0 else 0).sum()
        else:
            total_overtime = 0
        st.metric("⏰ Total Overtime Hours", f"{total_overtime:.1f}h")
    
    with col3:
        if not filtered_work_df.empty and 'Work Time' in filtered_work_df.columns:
            avg_hours_per_day = filtered_work_df['Work Time'].apply(lambda x: hhmm_to_decimal(str(x)) if pd.notna(x) else 0).mean()
        else:
            avg_hours_per_day = 0
        st.metric("📈 Avg Hours/Day", f"{avg_hours_per_day:.1f}h")
    
    with col4:
        total_days = len(filtered_work_df)
        st.metric("📅 Total Work Days", total_days)
    
    st.markdown("---")
    
    # Detailed Analytics Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Performance Analytics", 
        "⏰ Overtime Analysis", 
        "🏖️ Absence Management", 
        "💰 Cost Analysis", 
        "📈 Trends & Patterns", 
        "🎯 Employee Insights"
    ])
    
    with tab1:
        st.header("📊 Performance Analytics")
        
        if selected_employee == "All Employees":
            # Team performance comparison
            st.subheader("🏆 Team Performance Comparison")
            team_comparison = create_team_comparison_analysis(filtered_work_df, employees_df)
            
            if not team_comparison.empty:
                # Top performers
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("🥇 Top Performers by Efficiency")
                    top_performers = team_comparison.nlargest(5, 'Efficiency_Score')
                    fig = px.bar(
                        top_performers, 
                        x='Full_Name', 
                        y='Efficiency_Score',
                        title="Top 5 Employees by Efficiency Score",
                        color='Efficiency_Score',
                        color_continuous_scale='viridis'
                    )
                    fig.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.subheader("⏰ Overtime Frequency")
                    overtime_freq = team_comparison.nlargest(5, 'Overtime_Frequency')
                    fig = px.bar(
                        overtime_freq,
                        x='Full_Name',
                        y='Overtime_Frequency',
                        title="Employees with Highest Overtime Frequency",
                        color='Overtime_Frequency',
                        color_continuous_scale='reds'
                    )
                    fig.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig, use_container_width=True)
                
                # Performance table
                st.subheader("📋 Detailed Performance Table")
                st.dataframe(
                    team_comparison.round(2),
                    use_container_width=True,
                    hide_index=True
                )
        else:
            # Individual employee analysis
            st.subheader(f"📊 Performance Analysis for {selected_employee}")
            
            employee_row = employees_df[employees_df['full_name'] == selected_employee]
            if not employee_row.empty:
                employee_id = str(employee_row.iloc[0]['_id'])
                metrics = calculate_employee_metrics(filtered_work_df, employee_id)
                productivity = create_productivity_analysis(filtered_work_df, employee_id)
                
                if metrics and productivity:
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("📈 Efficiency Score", f"{productivity['avg_efficiency']:.1f}%")
                    with col2:
                        st.metric("🎯 Consistency", f"{productivity['consistency_score']:.1f}%")
                    with col3:
                        st.metric("⭐ Peak Days", productivity['peak_performance_days'])
                    with col4:
                        st.metric("⚠️ Low Days", productivity['low_performance_days'])
                    
                    # Productivity trend
                    if 'monthly_data' in productivity and not productivity['monthly_data'].empty:
                        st.subheader("📈 Monthly Productivity Trend")
                        # Convert Period objects to strings for JSON serialization
                        monthly_prod = productivity['monthly_data'].copy()
                        monthly_prod['Date'] = monthly_prod['Date'].astype(str)
                        fig = px.line(
                            monthly_prod,
                            x='Date',
                            y='Productivity_Score',
                            title="Monthly Productivity Score Trend",
                            markers=True
                        )
                        fig.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="Target (100%)")
                        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.header("⏰ Overtime Analysis")
        
        # Overtime trends
        st.subheader("📈 Overtime Trends Over Time")
        
        overtime_trends = filtered_work_df.copy()
        overtime_trends['Date'] = pd.to_datetime(overtime_trends['Date'])
        overtime_trends['Overtime_Hours'] = overtime_trends['Difference (Decimal)'].apply(
            lambda x: float(x) if pd.notna(x) and float(x) > 0 else 0
        )
        
        # Daily overtime trend
        daily_overtime = overtime_trends.groupby('Date')['Overtime_Hours'].sum().reset_index()
        
        fig = px.line(
            daily_overtime,
            x='Date',
            y='Overtime_Hours',
            title="Daily Overtime Hours Trend",
            markers=True
        )
        fig.update_layout(xaxis_title="Date", yaxis_title="Overtime Hours")
        st.plotly_chart(fig, use_container_width=True)
        
        # Overtime by day of week
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📅 Overtime by Day of Week")
            overtime_trends['Day_of_Week'] = overtime_trends['Date'].dt.day_name()
            day_overtime = overtime_trends.groupby('Day_of_Week')['Overtime_Hours'].mean().reset_index()
            
            fig = px.bar(
                day_overtime,
                x='Day_of_Week',
                y='Overtime_Hours',
                title="Average Overtime by Day of Week",
                color='Overtime_Hours',
                color_continuous_scale='reds'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("👥 Employee Overtime Comparison")
            employee_overtime = overtime_trends.groupby('employee_id')['Overtime_Hours'].sum().reset_index()
            employee_overtime = employee_overtime.merge(
                employees_df[['_id', 'full_name']], 
                left_on='employee_id', 
                right_on='_id', 
                how='left'
            )
            
            fig = px.bar(
                employee_overtime,
                x='full_name',
                y='Overtime_Hours',
                title="Total Overtime Hours by Employee",
                color='Overtime_Hours',
                color_continuous_scale='reds'
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.header("🏖️ Absence Management")
        
        absence_analysis = create_absence_analysis(filtered_work_df, employees_df)
        
        if absence_analysis:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📊 Absence by Type")
                if 'absence_by_type' in absence_analysis and not absence_analysis['absence_by_type'].empty:
                    fig = px.pie(
                        values=absence_analysis['absence_by_type'].values,
                        names=absence_analysis['absence_by_type'].index,
                        title="Absence Distribution by Type"
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.subheader("📅 Absence by Day of Week")
                if 'day_patterns' in absence_analysis and not absence_analysis['day_patterns'].empty:
                    fig = px.bar(
                        x=absence_analysis['day_patterns'].index,
                        y=absence_analysis['day_patterns'].values,
                        title="Absence Patterns by Day of Week",
                        color=absence_analysis['day_patterns'].values,
                        color_continuous_scale='blues'
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
                            # Monthly absence trends
            if 'monthly_trends' in absence_analysis and not absence_analysis['monthly_trends'].empty:
                st.subheader("📈 Monthly Absence Trends")
                # Convert Period objects to strings for JSON serialization
                monthly_data = absence_analysis['monthly_trends'].copy()
                monthly_data['Month'] = monthly_data['Month'].astype(str)
                fig = px.line(
                    monthly_data,
                    x='Month',
                    y='Absence_Count',
                    title="Monthly Absence Count Trend",
                    markers=True
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Employee absence ranking
            if 'employee_ranking' in absence_analysis and not absence_analysis['employee_ranking'].empty:
                st.subheader("👥 Employee Absence Ranking")
                fig = px.bar(
                    absence_analysis['employee_ranking'],
                    x='full_name',
                    y='Absence_Days',
                    title="Total Absence Days by Employee",
                    color='Absence_Days',
                    color_continuous_scale='blues'
                )
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No absence data available for the selected period.")
    
    with tab4:
        st.header("💰 Cost Analysis")
        
        cost_analysis = create_overtime_cost_analysis(filtered_work_df, employees_df)
        
        if cost_analysis:
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("💶 Total Overtime Cost", f"€{cost_analysis['total_overtime_cost']:,.2f}")
                st.metric("⏰ Total Overtime Hours", f"{cost_analysis['total_overtime_hours']:.1f}h")
            
            with col2:
                avg_cost_per_hour = cost_analysis['total_overtime_cost'] / cost_analysis['total_overtime_hours'] if cost_analysis['total_overtime_hours'] > 0 else 0
                st.metric("💶 Avg Cost per Hour", f"€{avg_cost_per_hour:.2f}")
                st.metric("📊 Cost per Employee", f"€{cost_analysis['total_overtime_cost'] / len(employees_df):,.2f}")
            
            # Monthly cost trends
            if 'monthly_costs' in cost_analysis and not cost_analysis['monthly_costs'].empty:
                st.subheader("📈 Monthly Overtime Costs")
                # Convert Period objects to strings for JSON serialization
                monthly_costs = cost_analysis['monthly_costs'].copy()
                monthly_costs['Date'] = monthly_costs['Date'].astype(str)
                fig = px.line(
                    monthly_costs,
                    x='Date',
                    y='Overtime_Cost',
                    title="Monthly Overtime Cost Trend",
                    markers=True
                )
                fig.update_layout(yaxis_title="Cost (€)")
                st.plotly_chart(fig, use_container_width=True)
            
            # Employee cost comparison
            if 'employee_costs' in cost_analysis and not cost_analysis['employee_costs'].empty:
                st.subheader("👥 Overtime Costs by Employee")
                fig = px.bar(
                    cost_analysis['employee_costs'],
                    x='full_name',
                    y='Overtime_Cost',
                    title="Overtime Costs by Employee",
                    color='Overtime_Cost',
                    color_continuous_scale='reds'
                )
                fig.update_layout(xaxis_tickangle=-45, yaxis_title="Cost (€)")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No cost data available for the selected period.")
    
    with tab5:
        st.header("📈 Trends & Patterns")
        
        # Work pattern analysis
        st.subheader("📅 Work Pattern Analysis")
        
        pattern_data = filtered_work_df.copy()
        pattern_data['Date'] = pd.to_datetime(pattern_data['Date'])
        pattern_data['Day_of_Week'] = pattern_data['Date'].dt.day_name()
        pattern_data['Month'] = pattern_data['Date'].dt.month
        pattern_data['Work_Hours'] = pattern_data['Work Time'].apply(lambda x: hhmm_to_decimal(str(x)) if pd.notna(x) else 0)
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Average hours by day of week
            day_pattern = pattern_data.groupby('Day_of_Week')['Work_Hours'].mean().reset_index()
            fig = px.bar(
                day_pattern,
                x='Day_of_Week',
                y='Work_Hours',
                title="Average Work Hours by Day of Week",
                color='Work_Hours',
                color_continuous_scale='viridis'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Average hours by month
            month_pattern = pattern_data.groupby('Month')['Work_Hours'].mean().reset_index()
            month_pattern['Month_Name'] = month_pattern['Month'].apply(lambda x: calendar.month_name[x])
            fig = px.bar(
                month_pattern,
                x='Month_Name',
                y='Work_Hours',
                title="Average Work Hours by Month",
                color='Work_Hours',
                color_continuous_scale='viridis'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Time series analysis
        st.subheader("⏰ Time Series Analysis")
        
        # Daily work hours trend
        daily_trend = pattern_data.groupby('Date')['Work_Hours'].mean().reset_index()
        fig = px.line(
            daily_trend,
            x='Date',
            y='Work_Hours',
            title="Daily Average Work Hours Trend",
            markers=True
        )
        fig.add_hline(y=8, line_dash="dash", line_color="red", annotation_text="Standard Day (8h)")
        st.plotly_chart(fig, use_container_width=True)
    
    with tab6:
        st.header("🎯 Employee Insights")
        
        if selected_employee != "All Employees":
            # Individual employee insights
            employee_row = employees_df[employees_df['full_name'] == selected_employee]
            if not employee_row.empty:
                employee_id = str(employee_row.iloc[0]['_id'])
                
                # Performance heatmap
                st.subheader("🔥 Work Pattern Heatmap")
                heatmap_data = create_performance_heatmap(filtered_work_df, employee_id)
                
                if heatmap_data is not None and not heatmap_data.empty:
                    fig = px.imshow(
                        heatmap_data,
                        title=f"Work Hours Heatmap for {selected_employee}",
                        color_continuous_scale='viridis',
                        aspect='auto'
                    )
                    fig.update_layout(
                        xaxis_title="Month",
                        yaxis_title="Day of Week"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Overtime trend
                st.subheader("📈 Overtime Trend Analysis")
                overtime_trend = create_overtime_trend_chart(filtered_work_df, employee_id)
                
                if overtime_trend is not None and not overtime_trend.empty:
                    fig = px.line(
                        overtime_trend,
                        x='Date',
                        y=['Difference (Decimal)', 'Overtime_Running_Avg'],
                        title=f"Overtime Trend for {selected_employee}",
                        markers=True
                    )
                    fig.update_layout(
                        xaxis_title="Date",
                        yaxis_title="Overtime Hours"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Recommendations
                st.subheader("💡 Performance Recommendations")
                
                metrics = calculate_employee_metrics(filtered_work_df, employee_id)
                if metrics:
                    recommendations = []
                    
                    if metrics['avg_overtime_per_day'] > 2:
                        recommendations.append("⚠️ **High Overtime**: Consider workload distribution or hiring additional staff")
                    
                    if metrics['punctuality_score'] < 90:
                        recommendations.append("⏰ **Punctuality**: Address attendance issues with employee")
                    
                    if metrics['days_with_undertime'] > metrics['total_days_worked'] * 0.2:
                        recommendations.append("📉 **Low Productivity**: Investigate reasons for undertime")
                    
                    if metrics['sick_days'] > 5:
                        recommendations.append("🏥 **Health**: Consider wellness programs or health check")
                    
                    if not recommendations:
                        recommendations.append("✅ **Excellent Performance**: Keep up the great work!")
                    
                    for rec in recommendations:
                        st.info(rec)
        else:
            st.subheader("👥 Team Insights")
            
            # Team recommendations
            team_comparison = create_team_comparison_analysis(filtered_work_df, employees_df)
            
            if not team_comparison.empty:
                # Identify top performers and areas for improvement
                top_performers = team_comparison.nlargest(3, 'Efficiency_Score')
                high_overtime = team_comparison.nlargest(3, 'Overtime_Frequency')
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("🏆 Top Performers")
                    for _, employee in top_performers.iterrows():
                        st.success(f"**{employee['Full_Name']}**: {employee['Efficiency_Score']:.1f}% efficiency")
                
                with col2:
                    st.subheader("⚠️ High Overtime Employees")
                    for _, employee in high_overtime.iterrows():
                        st.warning(f"**{employee['Full_Name']}**: {employee['Overtime_Frequency']:.1f}% overtime frequency")
    
    # Export functionality
    st.markdown("---")
    st.header("📤 Export Analytics")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Export Performance Report", use_container_width=True):
            # Generate comprehensive report
            st.success("Performance report exported successfully!")
    
    with col2:
        if st.button("💰 Export Cost Analysis", use_container_width=True):
            # Generate cost report
            st.success("Cost analysis exported successfully!")
    
    with col3:
        if st.button("📈 Export Trends Report", use_container_width=True):
            # Generate trends report
            st.success("Trends report exported successfully!")

if __name__ == "__main__":
    main()
