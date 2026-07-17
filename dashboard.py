from io import StringIO

import requests
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import json
import os

# ===== PAGE CONFIG =====
st.set_page_config(
    page_title="Feed Status Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ===== LOAD CSS =====
def load_css():
    # Load Font Awesome and Google Fonts
    st.markdown("""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    """, unsafe_allow_html=True)

    # Load custom CSS from file
    try:
        with open('style.css', 'r') as f:
            css = f.read()
        st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)
        return True
    except FileNotFoundError:
        st.warning("style.css file not found. Using default styling.")
        return False


load_css()

# ===== CONFIGURATION =====
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1SJrK568FXninzicEE6iG2Jr3Ns4Z-hH_DN2aEAVa8go/edit?gid=0#gid=0"

SHEET1_COLUMNS = [
    'Feed_frequency', 'Feed_Name', 'Platform_Type',
    'Platform name', 'Active', 'Developers_name', 'system IP', 'Available on Path', 'Mail', 'Google Sheet',
    'Dropbox', 'Master_status'
]

SHEET2_COLUMNS = [
    'Platform_Type', 'Feed_Name', 'Category',
    'Developers_name', 'Available on Path', 'Mail','Master_status'
]

SHEET5_COLUMNS = [
    'Platform_Type', 'Feed_Name', 'Category',
    'Developers_name', 'Available on Path', 'Mail','Master_status'
]

STATUS_COLUMNS = ['Available on Path', 'Mail', 'Google Sheet', 'Dropbox']


# ===== GOOGLE SHEETS DATA CLASS =====
import requests
import io
import pandas as pd


# ===== GOOGLE SHEETS DATA CLASS - URL METHOD =====
class GoogleSheetData:
    def __init__(self):
        self.cached_data = None
        self.cache_time = None
        self.cache_duration = 120
        self.last_updated = None
        self.connection_error = None

    def fetch_data(self, force_refresh=False):
        if self.connection_error:
            return None

        if not force_refresh and self.cached_data is not None:
            if self.cache_time and (datetime.now() - self.cache_time).seconds < self.cache_duration:
                return self.cached_data

        try:
            # Sheet 1 URL (gid=0 is the first sheet)
            sheet1_url = "https://docs.google.com/spreadsheets/d/1SJrK568FXninzicEE6iG2Jr3Ns4Z-hH_DN2aEAVa8go/export?format=csv&id=1SJrK568FXninzicEE6iG2Jr3Ns4Z-hH_DN2aEAVa8go&gid=0"

            # Sheet 2 PM URL - you need to find the correct gid
            # To find gid: Open sheet in browser, look at URL after gid=
            sheet2pm_url = "https://docs.google.com/spreadsheets/d/1SJrK568FXninzicEE6iG2Jr3Ns4Z-hH_DN2aEAVa8go/export?format=csv&id=1SJrK568FXninzicEE6iG2Jr3Ns4Z-hH_DN2aEAVa8go&gid=602178604"  # Replace with actual gid

            # Sheet 5 PM URL - you need to find the correct gid
            sheet5pm_url = "https://docs.google.com/spreadsheets/d/1SJrK568FXninzicEE6iG2Jr3Ns4Z-hH_DN2aEAVa8go/export?format=csv&id=1SJrK568FXninzicEE6iG2Jr3Ns4Z-hH_DN2aEAVa8go&gid=1068112179"  # Replace with actual gid

            # Fetch data
            response1 = requests.get(sheet1_url, timeout=30)
            response1.raise_for_status()
            df_sheet1 = pd.read_csv(io.StringIO(response1.text))

            response2 = requests.get(sheet2pm_url, timeout=30)
            response2.raise_for_status()
            df_2pm = pd.read_csv(io.StringIO(response2.text))

            response3 = requests.get(sheet5pm_url, timeout=30)
            response3.raise_for_status()
            df_5pm = pd.read_csv(io.StringIO(response3.text))

            df_sheet1 = self.filter_columns(df_sheet1, SHEET1_COLUMNS)
            df_2pm = self.filter_columns(df_2pm, SHEET2_COLUMNS)
            df_5pm = self.filter_columns(df_5pm, SHEET5_COLUMNS)

            if 'Master_status' in df_sheet1.columns:
                df_sheet1['Master_status'] = df_sheet1['Master_status'].apply(
                    lambda x: 'Done' if str(x).strip().lower() == 'done' else 'Pending'
                )

            self.last_updated = datetime.now()

            self.cached_data = {
                'sheet1': df_sheet1,
                'sheet2pm': df_2pm,
                'sheet5pm': df_5pm,
                'last_updated': self.last_updated
            }
            self.cache_time = datetime.now()

            return self.cached_data

        except Exception as e:
            self.connection_error = f"Connection Error: {str(e)}"
            if self.cached_data is not None:
                return self.cached_data
            return None

    def filter_columns(self, df, required_columns):
        existing_columns = [col for col in required_columns if col in df.columns]
        if existing_columns:
            return df[existing_columns]
        return pd.DataFrame(columns=required_columns)


# ===== UI FUNCTIONS =====
def status_badge(status, is_master=False):
    if pd.isna(status) or status is None:
        status = 'Pending'
    status_lower = str(status).strip().lower().replace(' ', '-')

    if is_master:
        badge_class = 'master-done' if status_lower == 'done' else 'master-pending'
    else:
        badge_class = status_lower

    return f'<span class="status-badge {badge_class}">{status}</span>'


def metric_card_html(icon_class, value, label, subtext="", card_class="total"):
    return f'''
    <div class="metric-card {card_class}">
        <div class="metric-top">
            <span class="metric-label">{label}</span>
            <span class="metric-icon"><i class="{icon_class}"></i></span>
        </div>
        <div class="metric-value">{value}</div>
        {f'<div class="metric-sub">{subtext}</div>' if subtext else ''}
    </div>
    '''


def apply_filters(df, status_filter, frequency_filter, master_status_filter):
    """Apply status, frequency and master status filters to dataframe"""
    if df.empty:
        return df

    # Apply status filter (Active/Inactive)
    if status_filter == "Active":
        if 'Active' in df.columns:
            df = df[df['Active'].astype(str).str.lower().str.strip() == 'active']
    elif status_filter == "Inactive":
        if 'Active' in df.columns:
            df = df[df['Active'].astype(str).str.lower().str.strip() != 'active']
    # "All" - no filter

    # Apply frequency filter
    if frequency_filter != "All":
        if 'Feed_frequency' in df.columns:
            # Clean the frequency values
            df['Feed_frequency_clean'] = df['Feed_frequency'].astype(str).str.strip().str.lower()

            if frequency_filter == "Daily":
                df = df[df['Feed_frequency_clean'].str.contains('daily', na=False) & ~df[
                    'Feed_frequency_clean'].str.contains('daily/weekly', na=False)]
            elif frequency_filter == "Daily/Weekly":
                df = df[df['Feed_frequency_clean'].str.contains('daily/weekly', na=False)]
            elif frequency_filter == "Weekly":
                df = df[df['Feed_frequency_clean'].str.contains('weekly', na=False) & ~df[
                    'Feed_frequency_clean'].str.contains('daily', na=False)]

            # Drop the temporary column
            df = df.drop(columns=['Feed_frequency_clean'])

    # Apply Master Status filter (Done/Pending) - NEW
    if master_status_filter != "All":
        if 'Master_status' in df.columns:
            if master_status_filter == "Done":
                df = df[df['Master_status'].astype(str).str.strip() == 'Done']
            elif master_status_filter == "Pending":
                df = df[df['Master_status'].astype(str).str.strip() == 'Pending']

    return df


def get_filter_info_html(status_filter, frequency_filter, master_status_filter):
    """Get HTML for filter info badges"""
    badges = []

    # Status badge
    if status_filter == "All":
        badges.append('<span class="badge-all"><i class="fas fa-list"></i> All Status</span>')
    elif status_filter == "Active":
        badges.append('<span class="badge-active"><i class="fas fa-check-circle"></i> Active</span>')
    elif status_filter == "Inactive":
        badges.append('<span class="badge-inactive"><i class="fas fa-times-circle"></i> Inactive</span>')

    # Frequency badge
    if frequency_filter == "All":
        badges.append('<span class="badge-all"><i class="fas fa-clock"></i> All Frequency</span>')
    elif frequency_filter == "Daily":
        badges.append('<span class="badge-daily"><i class="fas fa-calendar-day"></i> Daily</span>')
    elif frequency_filter == "Daily/Weekly":
        badges.append('<span class="badge-dailyweekly"><i class="fas fa-calendar-alt"></i> Daily/Weekly</span>')
    elif frequency_filter == "Weekly":
        badges.append('<span class="badge-weekly"><i class="fas fa-calendar-week"></i> Weekly</span>')

    # Master Status badge - NEW
    if master_status_filter == "All":
        badges.append('<span class="badge-all"><i class="fas fa-tasks"></i> All Master</span>')
    elif master_status_filter == "Done":
        badges.append('<span class="badge-done-master"><i class="fas fa-check"></i> Done</span>')
    elif master_status_filter == "Pending":
        badges.append('<span class="badge-pending-master"><i class="fas fa-clock"></i> Pending</span>')

    return ' '.join(badges)

# ===== MAIN APP =====
def main():
    # Initialize filter states
    if 'status_filter' not in st.session_state:
        st.session_state.status_filter = "All"
    if 'frequency_filter' not in st.session_state:
        st.session_state.frequency_filter = "All"
    if 'master_status_filter' not in st.session_state:  # NEW
        st.session_state.master_status_filter = "All"

    # Header
    st.markdown('''
    <div class="main-header">
        <div>
            <h1>
                <i class="fas fa-chart-bar" style="color: #60a5fa; font-size: 32px;"></i>
                Feed Status Dashboard
            </h1>
            <div class="subtitle">
                <i class="fas fa-sync-alt"></i>
                Real-time feed delivery monitoring and status tracking
            </div>
        </div>
    </div>
    ''', unsafe_allow_html=True)

    # Initialize data fetcher
    if 'data_fetcher' not in st.session_state:
        st.session_state.data_fetcher = GoogleSheetData()
        st.session_state.last_fetch_time = None

    data_fetcher = st.session_state.data_fetcher

    # ===== SIDEBAR =====
    with st.sidebar:
        # Navigation Title
        st.markdown('''
        <div class="sidebar-nav-title">
            <i class="fas fa-compass"></i>
            Navigation
        </div>
        ''', unsafe_allow_html=True)

        # Selectbox for navigation
        page = st.selectbox(
            "Navigation",
            [
                "Dashboard",
                "Sheet 1",
                "2 PM Sheet",
                "5 PM Sheet"
            ],
            index=0,
            label_visibility="collapsed"
        )

        st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)

        # ===== STATUS FILTER =====
        st.markdown('''
        <div class="filter-section-title">
            <i class="fas fa-filter"></i>
            Filter by Status
        </div>
        ''', unsafe_allow_html=True)

        # Status filter buttons
        col1, col2, col3 = st.columns(3)

        status_filter = st.session_state.status_filter

        with col1:
            if st.button("All", key="status_all", use_container_width=True):
                st.session_state.status_filter = "All"
                st.rerun()

        with col2:
            if st.button("Active", key="status_active", use_container_width=True):
                st.session_state.status_filter = "Active"
                st.rerun()

        with col3:
            if st.button("Inactive", key="status_inactive", use_container_width=True):
                st.session_state.status_filter = "Inactive"
                st.rerun()

        st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)

        # ===== FREQUENCY FILTER =====
        st.markdown('''
        <div class="filter-section-title">
            <i class="fas fa-calendar-alt"></i>
            Filter by Frequency
        </div>
        ''', unsafe_allow_html=True)

        # Frequency filter buttons
        col1, col2, col3, col4 = st.columns(4)

        frequency_filter = st.session_state.frequency_filter

        with col1:
            if st.button("All", key="freq_all", use_container_width=True):
                st.session_state.frequency_filter = "All"
                st.rerun()

        with col2:
            if st.button("Daily", key="freq_daily", use_container_width=True):
                st.session_state.frequency_filter = "Daily"
                st.rerun()

        with col3:
            if st.button("D/W", key="freq_dailyweekly", use_container_width=True):
                st.session_state.frequency_filter = "Daily/Weekly"
                st.rerun()

        with col4:
            if st.button("Weekly", key="freq_weekly", use_container_width=True):
                st.session_state.frequency_filter = "Weekly"
                st.rerun()

        st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)

        # ===== MASTER STATUS FILTER =====
        st.markdown('''
        <div class="filter-section-title">
            <i class="fas fa-tasks"></i>
            Filter by Master Status
        </div>
        ''', unsafe_allow_html=True)

        # Master Status filter buttons
        col1, col2, col3 = st.columns(3)

        master_status_filter = st.session_state.master_status_filter

        with col1:
            if st.button("All", key="master_all", use_container_width=True):
                st.session_state.master_status_filter = "All"
                st.rerun()

        with col2:
            if st.button("Done", key="master_done", use_container_width=True):
                st.session_state.master_status_filter = "Done"
                st.rerun()

        with col3:
            if st.button("Pending", key="master_pending", use_container_width=True):
                st.session_state.master_status_filter = "Pending"
                st.rerun()

        # Show active filters
        st.markdown(f'''
        <div class="filter-info-badge">
            {get_filter_info_html(status_filter, frequency_filter, master_status_filter)}
        </div>
        ''', unsafe_allow_html=True)

        st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)

        # ===== REFRESH BUTTON =====
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.session_state.data_fetcher = GoogleSheetData()
            st.session_state.last_fetch_time = None
            st.rerun()

        st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)

        # Status Section
        st.markdown('''
        <div style="margin: 10px 0;">
            <div style="color: #94a3b8; font-family: 'Inter', sans-serif; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 8px;">
                <i class="fas fa-bolt" style="color: #60a5fa;"></i>
                Status
            </div>
        </div>
        ''', unsafe_allow_html=True)

        # Fetch data
        force_refresh = st.session_state.last_fetch_time is None or \
                        (datetime.now() - st.session_state.last_fetch_time).seconds > 120

        if force_refresh:
            with st.spinner('Fetching latest data...'):
                data = data_fetcher.fetch_data(force_refresh=True)
                st.session_state.last_fetch_time = datetime.now()
        else:
            data = data_fetcher.fetch_data(force_refresh=False)

        if data is None:
            st.error("Failed to fetch data. Please check connection.")
            return

        df_sheet1 = data['sheet1']
        df_2pm = data['sheet2pm']
        df_5pm = data['sheet5pm']

        # Apply filters
        df_sheet1_filtered = apply_filters(df_sheet1, status_filter, frequency_filter, master_status_filter)

        # For 2pm and 5pm sheets, filter based on Feed_Name from filtered sheet1
        if not df_sheet1_filtered.empty and 'Feed_Name' in df_sheet1_filtered.columns:
            active_feeds = set(df_sheet1_filtered['Feed_Name'].dropna())
            if not df_2pm.empty and 'Feed_Name' in df_2pm.columns:
                df_2pm_filtered = df_2pm[df_2pm['Feed_Name'].isin(active_feeds)]
            else:
                df_2pm_filtered = df_2pm
            if not df_5pm.empty and 'Feed_Name' in df_5pm.columns:
                df_5pm_filtered = df_5pm[df_5pm['Feed_Name'].isin(active_feeds)]
            else:
                df_5pm_filtered = df_5pm
        else:
            df_2pm_filtered = df_2pm
            df_5pm_filtered = df_5pm

        # Last Updated
        if data_fetcher.last_updated:
            st.markdown(f'''
            <div class="sidebar-status-box">
                <div class="label">
                    <i class="fas fa-clock"></i>
                    Last Updated
                </div>
                <div class="value">{data_fetcher.last_updated.strftime('%Y-%m-%d %H:%M:%S')}</div>
            </div>
            ''', unsafe_allow_html=True)

        if data_fetcher.connection_error:
            st.error(data_fetcher.connection_error)

        # Summary
        if not df_sheet1_filtered.empty:
            st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)

            st.markdown('''
            <div class="sidebar-summary-title">
                <i class="fas fa-chart-pie"></i>
                Summary
            </div>
            ''', unsafe_allow_html=True)

            st.markdown(f'''
            <div class="sidebar-metric-box">
                <div class="label">
                    <i class="fas fa-database"></i>
                    Total Feeds
                </div>
                <div class="value">{len(df_sheet1_filtered)}</div>
            </div>
            <div class="sidebar-metric-box">
                <div class="label">
                    <i class="fas fa-clock"></i>
                    2 PM Records
                </div>
                <div class="value">{len(df_2pm_filtered)}</div>
            </div>
            <div class="sidebar-metric-box">
                <div class="label">
                    <i class="fas fa-clock"></i>
                    5 PM Records
                </div>
                <div class="value">{len(df_5pm_filtered)}</div>
            </div>
            ''', unsafe_allow_html=True)

    # ===== PAGE CONTENT =====
    # Map page names
    page_display = {
        "Dashboard": "📊 Dashboard",
        "Sheet 1": "📄 Sheet 1",
        "2 PM Sheet": "📄 2 PM Sheet",
        "5 PM Sheet": "📄 5 PM Sheet"
    }[page]

    if page_display == "📊 Dashboard":
        if df_sheet1_filtered.empty:
            st.warning("No data found in Sheet1")
            return

        # # Show filter info
        # st.markdown(f'<div style="margin-bottom: 15px;">{get_filter_info_html(status_filter, frequency_filter)}</div>',
        #             unsafe_allow_html=True)
        # Show filter info with proper class - Left aligned
        # Show filter info with proper class - Left aligned
        filter_html = '''
        <div class="main-filter-badges">
            <div class="filter-badge-title">
                <i class="fas fa-filter" style="color: #60a5fa; font-size: 14px;"></i>
                Active Filters:
            </div>
            <div class="filter-info-badge">
                {badges}
            </div>
        </div>
        '''.format(badges=get_filter_info_html(status_filter, frequency_filter, master_status_filter))

        st.markdown(filter_html, unsafe_allow_html=True)

        # ===== METRIC CARDS =====
        total = len(df_sheet1_filtered)

        # Count Done/Pending for each column
        col_counts = {}
        for col in STATUS_COLUMNS:
            if col in df_sheet1_filtered.columns:
                done_count = len(
                    df_sheet1_filtered[df_sheet1_filtered[col].astype(str).str.lower().str.strip() == 'done'])
                col_counts[col] = {'done': done_count, 'total': len(df_sheet1_filtered)}
            else:
                col_counts[col] = {'done': 0, 'total': 0}

        # Master Status counts
        if 'Master_status' in df_sheet1_filtered.columns:
            master_done = len(df_sheet1_filtered[df_sheet1_filtered['Master_status'] == 'Done'])
            master_pending = len(df_sheet1_filtered[df_sheet1_filtered['Master_status'] == 'Pending'])
        else:
            master_done = 0
            master_pending = total

        # Row 1: Main Metrics
        st.markdown('<div class="metric-grid">', unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(metric_card_html("fas fa-database", total, "Total Feeds", "", "total"), unsafe_allow_html=True)

        with col2:
            st.markdown(
                metric_card_html("fas fa-check-circle", master_done, "Master Done", f"{master_done}/{total}", "done"),
                unsafe_allow_html=True)

        with col3:
            st.markdown(
                metric_card_html("fas fa-hourglass-half", master_pending, "Master Pending", f"{master_pending}/{total}",
                                 "pending"), unsafe_allow_html=True)

        with col4:
            # Show frequency distribution
            if 'Feed_frequency' in df_sheet1_filtered.columns:
                freq_counts = df_sheet1_filtered['Feed_frequency'].value_counts()
                freq_text = ", ".join([f"{k}: {v}" for k, v in freq_counts.items()])
                st.markdown(
                    metric_card_html("fas fa-calendar-alt", len(freq_counts), "Frequency Types", freq_text, "total"),
                    unsafe_allow_html=True)
            else:
                st.markdown(
                    metric_card_html("fas fa-calendar-alt", 0, "Frequency Types", "No data", "total"),
                    unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

        # Row 2: Individual Status Counts
        st.markdown('<div class="section-title"><i class="fas fa-list-ul"></i>Individual Status Counts</div>',
                    unsafe_allow_html=True)

        st.markdown('<div class="metric-grid">', unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)

        cols_with_icons = {
            'Available on Path': ('fas fa-folder-open', 'path'),
            'Mail': ('fas fa-envelope', 'mail'),
            'Google Sheet': ('fas fa-table', 'sheet'),
            'Dropbox': ('fas fa-cloud', 'dropbox')
        }

        for idx, col_name in enumerate(STATUS_COLUMNS):
            col_obj = [col1, col2, col3, col4][idx]
            count = col_counts.get(col_name, {})
            done = count.get('done', 0)
            total_count = count.get('total', 0)
            icon, card_class = cols_with_icons.get(col_name, ('fas fa-file', 'total'))

            with col_obj:
                st.markdown(
                    metric_card_html(icon, f"{done}/{total_count}", col_name, "", card_class),
                    unsafe_allow_html=True
                )

        st.markdown('</div>', unsafe_allow_html=True)

        # ===== DETAILED TABLE =====
        st.markdown('<div class="section-title"><i class="fas fa-table"></i>Detailed Status</div>',
                    unsafe_allow_html=True)

        display_df = df_sheet1_filtered.copy()

        if 'Master_status' in display_df.columns:
            display_df['Master_status'] = display_df['Master_status'].apply(
                lambda x: status_badge(x, is_master=True)
            )

        display_cols = ['Feed_Name', 'Platform_Type', 'Category', 'Developers_name',
                        'Master_status']
        if 'Feed_frequency' in display_df.columns:
            display_cols.insert(1, 'Feed_frequency')

        available_cols = [col for col in display_cols if col in display_df.columns]

        if available_cols:
            st.write(
                display_df[available_cols].to_html(escape=False, index=False),
                unsafe_allow_html=True
            )

    elif page_display == "📄 Sheet 1":
        st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h3 style="font-family: 'Inter', sans-serif; font-weight: 600; color: #ffffff; margin: 0;">
                <i class="fas fa-file-alt" style="margin-right: 10px; color: #3b82f6;"></i>
                Sheet 1 - Complete Data
            </h3>
            <div class="filter-info-badge">
                {get_filter_info_html(status_filter, frequency_filter, master_status_filter)}
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.dataframe(df_sheet1_filtered, use_container_width=True, hide_index=True)

        csv = df_sheet1_filtered.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"sheet1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

    elif page_display == "📄 2 PM Sheet":
        st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h3 style="font-family: 'Inter', sans-serif; font-weight: 600; color: #ffffff; margin: 0;">
                <i class="fas fa-clock" style="margin-right: 10px; color: #f59e0b;"></i>
                2 PM Sheet Data
            </h3>
            <div class="filter-info-badge">
                {get_filter_info_html(status_filter, frequency_filter, master_status_filter)}
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.dataframe(df_2pm_filtered, use_container_width=True, hide_index=True)

        csv = df_2pm_filtered.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"2pm_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

    elif page_display == "📄 5 PM Sheet":
        st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h3 style="font-family: 'Inter', sans-serif; font-weight: 600; color: #ffffff; margin: 0;">
                <i class="fas fa-clock" style="margin-right: 10px; color: #10b981;"></i>
                5 PM Sheet Data
            </h3>
            <div class="filter-info-badge">
                {get_filter_info_html(status_filter, frequency_filter, master_status_filter)}
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.dataframe(df_5pm_filtered, use_container_width=True, hide_index=True)

        csv = df_5pm_filtered.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"5pm_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )


if __name__ == "__main__":
    main()