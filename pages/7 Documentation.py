import streamlit as st
import os
from pathlib import Path

def load_markdown_file(file_path):
    """Load and return the content of a markdown file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        return f"Error loading file: {str(e)}"

def main():
    st.title("📚 Documentation & User Guides")
    st.markdown("---")
    
    # Check if user is logged in
    if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
        st.error("You need to log in first.")
        st.session_state["logged_in"] = False
        st.session_state["user_id"] = None
        return
    
    # Documentation files with their descriptions
    docs = {
        "QUICK_START_GUIDE.md": {
            "title": "🚀 Quick Start Guide",
            "description": "Get up and running with Bulldog Office in just a few minutes",
            "icon": "⚡"
        },
        "USER_GUIDE.md": {
            "title": "📖 User Guide",
            "description": "Comprehensive guide for all users of the system",
            "icon": "👤"
        },
        "EMPLOYEE_MANAGEMENT_GUIDE.md": {
            "title": "👥 Employee Management Guide",
            "description": "How to add, edit, and manage employee information",
            "icon": "👥"
        },
        "BULK_TIMECARD_GUIDE.md": {
            "title": "📊 Bulk Timecard Guide",
            "description": "Process multiple employee timecards efficiently",
            "icon": "📊"
        },
        "CALENDAR_GUIDE.md": {
            "title": "📅 Calendar & Holiday Management",
            "description": "Manage holidays, events, and calendar features",
            "icon": "📅"
        },
        "ABSENCE_TRACKING_GUIDE.md": {
            "title": "🏖️ Absence Tracking Guide",
            "description": "Track and manage employee absences and time off",
            "icon": "🏖️"
        },
        "ANALYTICS_DASHBOARD_GUIDE.md": {
            "title": "📊 Analytics Dashboard Guide",
            "description": "Comprehensive analytics and business intelligence insights",
            "icon": "📊"
        }
    }
    
    # Create tabs for each documentation section
    tab_names = [docs[file]["title"] for file in docs.keys()]
    tabs = st.tabs(tab_names)
    
    # Documentation directory path
    docs_dir = Path("documentation")
    
    # Populate each tab with the corresponding documentation
    for i, (filename, doc_info) in enumerate(docs.items()):
        with tabs[i]:
            st.markdown(f"## {doc_info['icon']} {doc_info['title']}")
            st.markdown(f"*{doc_info['description']}*")
            st.markdown("---")
            
            # Load and display the markdown content
            file_path = docs_dir / filename
            if file_path.exists():
                content = load_markdown_file(file_path)
                
                # Custom CSS for better markdown rendering
                st.markdown("""
                <style>
                .stMarkdown {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                }
                .stMarkdown h1 {
                    color: #1f77b4;
                    border-bottom: 2px solid #1f77b4;
                    padding-bottom: 10px;
                }
                .stMarkdown h2 {
                    color: #2e7d32;
                    margin-top: 30px;
                }
                .stMarkdown h3 {
                    color: #1976d2;
                }
                .stMarkdown code {
                    background-color: #f5f5f5;
                    padding: 2px 4px;
                    border-radius: 3px;
                    font-family: 'Courier New', monospace;
                }
                .stMarkdown pre {
                    background-color: #f8f9fa;
                    padding: 15px;
                    border-radius: 5px;
                    border-left: 4px solid #007bff;
                }
                .stMarkdown table {
                    border-collapse: collapse;
                    width: 100%;
                    margin: 20px 0;
                }
                .stMarkdown th, .stMarkdown td {
                    border: 1px solid #ddd;
                    padding: 8px 12px;
                    text-align: left;
                }
                .stMarkdown th {
                    background-color: #f2f2f2;
                    font-weight: bold;
                }
                .stMarkdown tr:nth-child(even) {
                    background-color: #f9f9f9;
                }
                .stMarkdown blockquote {
                    border-left: 4px solid #007bff;
                    margin: 0;
                    padding-left: 15px;
                    color: #666;
                }
                </style>
                """, unsafe_allow_html=True)
                
                # Display the markdown content
                st.markdown(content)
                
                # Add a download button for the markdown file
                st.markdown("---")
                col1, col2 = st.columns([3, 1])
                with col2:
                    st.download_button(
                        label="📥 Download Guide",
                        data=content,
                        file_name=filename,
                        mime="text/markdown",
                        use_container_width=True
                    )
            else:
                st.error(f"Documentation file '{filename}' not found.")
    
    # Add a helpful section at the bottom
    st.markdown("---")
    st.markdown("## 💡 Need Help?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("""
        **Quick Tips:**
        - Start with the Quick Start Guide if you're new
        - Use the User Guide for detailed instructions
        - Check specific guides for specialized tasks
        """)
    
    with col2:
        st.success("""
        **Getting Started:**
        1. Read the Quick Start Guide
        2. Set up your first employee
        3. Upload your first timecard
        4. Explore other features
        """)

if __name__ == "__main__":
    main()
