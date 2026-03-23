import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import gspread

# ---------------------------------------------------------
# 1. CONFIGURATION & STYLING
# ---------------------------------------------------------
st.set_page_config(page_title="AII Project Tracker V13", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
        .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #dee2e6; }
        [data-testid="stMetricValue"] { font-size: 1.8rem; color: #007bff; }
        .stTabs [data-baseweb="tab"] { font-weight: bold; font-size: 1.1rem; }
        .noti-box { background-color: #fff3cd; padding: 10px; border-radius: 5px; border-left: 5px solid #ffc107; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

st.title("🌌 AII Project Management System V13")

# ==========================================
# 2. DATA ENGINE
# ==========================================
def connect_gsheet():
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            if "\\n" in creds_dict["private_key"]:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            client = gspread.service_account_from_dict(creds_dict)
        else:
            client = gspread.service_account(filename='credentials.json')
        return client.open("Chronos_Data") 
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return None

def load_data():
    expected_logs = ['Employee', 'Project', 'Main_Task', 'Sub_Task', 'Dependency', 'Start_Date', 'End_Date', 'Progress', 'Issue', 'Status']
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            ws_emps = sh.worksheet('Employees')
            ws_projs = sh.worksheet('Projects')

            df_logs = pd.DataFrame(ws_logs.get_all_records())
            df_projs = pd.DataFrame(ws_projs.get_all_records())
            df_emps = pd.DataFrame(ws_emps.get_all_records())

            for col in expected_logs:
                if col not in df_logs.columns: df_logs[col] = "" 

            if not df_logs.empty:
                df_logs['Start_Date'] = pd.to_datetime(df_logs['Start_Date'], errors='coerce')
                df_logs['End_Date'] = pd.to_datetime(df_logs['End_Date'], errors='coerce')
                df_logs['Progress'] = pd.to_numeric(df_logs['Progress'], errors='coerce').fillna(0)

            st.session_state['data'] = df_logs
            st.session_state['employees'] = df_emps['Name'].tolist() if not df_emps.empty else []
            st.session_state['projects_master'] = df_projs
            st.session_state['projects_list'] = df_projs['Project'].dropna().unique().tolist() if not df_projs.empty else []
            return df_logs
        except Exception as e:
            st.error(f"Load Error: {e}")
            return pd.DataFrame(columns=expected_logs)
    return pd.DataFrame()

def save_data(df_to_save):
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            save_df = df_to_save.copy().fillna("")
            cols_to_keep = ['Employee', 'Project', 'Main_Task', 'Sub_Task', 'Dependency', 'Start_Date', 'End_Date', 'Progress', 'Issue', 'Status']
            save_df = save_df[cols_to_keep]
            save_df['Start_Date'] = save_df['Start_Date'].dt.strftime('%Y-%m-%d')
            save_df['End_Date'] = save_df['End_Date'].dt.strftime('%Y-%m-%d')
            ws_logs.clear()
            ws_logs.update(range_name="A1", values=[save_df.columns.values.tolist()] + save_df.values.tolist())
            return True
        except: return False

if 'data' not in st.session_state:
    load_data()

# ==========================================
# 3. SIDEBAR
# ==========================================
with st.sidebar:
    st.header("⚙️ ระบบ AII")
    if st.button("🔄 Sync ข้อมูลล่าสุด", use_container_width=True):
        st.cache_data.clear()
        load_data()
        st.rerun()
    st.divider()
    with st.expander("👤 เพิ่มรายชื่อพนักงาน"):
        n_emp = st.text_input("ชื่อเล่น")
        if st.button("บันทึกชื่อ"):
            sh = connect_gsheet(); sh.worksheet('Employees').append_row([n_emp]); st.rerun()

# ==========================================
# 4. MAIN INTERFACE
# ==========================================
tabs = st.tabs(["📝 ลงทะเบียน", "📊 แผนผังงาน (Gantt)", "🛠️ แก้ไข/ลบข้อมูล", "🏆 อันดับผลงาน", "📑 รายงาน"])

# --- TAB 0: ลงทะเบียน ---
with tabs[0]:
    st.subheader("📝 มอบหมายงาน (พร้อมระบบ Dependency)")
    df_curr = st.session_state.get('data', pd.DataFrame())
    with st.form("reg_form_v13", clear_on_submit=True):
        p = st.selectbox("📁 1. เลือกโปรเจกต์", st.session_state.get('projects_list', []))
        
        # Main Task
        existing_mt = ["-- สร้างงานรองใหม่ --"]
        if not df_curr.empty and p:
            mt_list = df_curr[df_curr['Project'] == p]['Main_Task'].unique().tolist()
            existing_mt.extend(mt_list)
        sel_mt = st.selectbox("📑 2. เลือกงานรอง", existing_mt)
        new_mt = st.text_input("✨ หรือพิมพ์ชื่อเฟสใหม่")
        final_mt = new_mt if sel_mt == "-- สร้างงานรองใหม่ --" else sel_mt
        
        stk = st.text_input("📌 3. ชื่องานย่อย (Sub-task)")
        
        # Dependency
        existing_stk = ["-- เริ่มได้ทันที --"]
        if not df_curr.empty and p:
            stk_list = df_curr[df_curr['Project'] == p]['Sub_Task'].unique().tolist()
            existing_stk.extend(stk_list)
        sel_dep = st.selectbox("🔗 4. งานที่ต้องรอให้เสร็จก่อน", existing_stk)
        final_dep = "" if sel_dep == "-- เริ่มได้ทันที --" else sel_dep

        ems = st.multiselect("👥 5. ผู้รับผิดชอบ", st.session_state.get('employees', []))
        c1, c2 = st.columns(2)
        ds, de = c1.date_input("📅 เริ่ม"), c2.date_input("🏁 จบ")
        
        if st.form_submit_button("💾 บันทึกงาน", use_container_width=True):
            if final_mt and stk and ems:
                latest = st.session_state['data']
                new_data = [{'Employee': e, 'Project': p, 'Main_Task': final_mt, 'Sub_Task': stk, 'Dependency': final_dep, 'Start_Date': pd.to_datetime(ds), 'End_Date': pd.to_datetime(de), 'Progress': 0, 'Status': '⏳ กำลังทำ'} for e in ems]
                updated = pd.concat([latest, pd.DataFrame(new_data)], ignore_index=True)
                if save_data(updated):
                    st.success("บันทึกเรียบร้อย!"); st.rerun()

# --- TAB 1: Gantt Chart & Daily Noti ---
with tabs[1]:
    df_all = st.session_state.get('data', pd.DataFrame())
    if not df_all.empty:
        # 🚩 Daily Notification Alert (งานที่ต้องอัปเดต)
        today = datetime.now().date()
        late_tasks = df_all[(df_all['Progress'] < 100) & (df_all['End_Date'].dt.date < today)]
        no_move_tasks = df_all[(df_all['Progress'] == 0) & (df_all['Start_Date'].dt.date <= today)]
        
        if not late_tasks.empty or not no_move_tasks.empty:
            with st.expander("🔔 แจ้งเตือนงานค้าง / งานยังไม่เริ่ม (Daily Alert)", expanded=True):
                if not late_tasks.empty:
                    st.error(f"⚠️ มี {len(late_tasks)} งานที่เลยกำหนดส่ง! (กรุณาอัปเดตด่วน)")
                if not no_move_tasks.empty:
                    st.warning(f"🕒 มี {len(no_move_tasks)} งานที่ต้องเริ่มแล้วแต่ Progress ยังเป็น 0%")

        sel_p = st.selectbox("📂 ดูแผนผังโปรเจกต์:", df_all['Project'].unique().tolist(), key="p_gantt_v13")
        df_proj = df_all[df_all['Project'] == sel_p].copy()
        
        # Gantt Logic (V12.1 Enhanced)
        master = st.session_state.get('projects_master', pd.DataFrame())
        if not master.empty and sel_p in master['Project'].values:
            p_info = master[master['Project'] == sel_p].iloc[0]
            p_s, p_e = pd.to_datetime(p_info['Start_Date']), pd.to_datetime(p_info['End_Date']) + pd.Timedelta(days=1)
        else:
            p_s, p_e = df_proj['Start_Date'].min(), df_proj['End_Date'].max() + pd.Timedelta(days=1)
        
        p_pct = df_proj['Progress'].mean()
        st.metric(f"🚀 Overall Progress: {sel_p}", f"{p_pct:.1f}%")

        plot_data = []
        # Project Layer
        p_lab = f"🏢 {sel_p}"
        plot_data.append({'Task': p_lab, 'Start': p_s, 'End': p_e, 'Type': 'P_Plan', 'Label': '', 'Width': 0.8, 'Color': '#E5E8E8', 'Pos': 'inside'})
        plot_data.append({'Task': p_lab, 'Start': p_s, 'End': p_s+((p_e-p_s)*(p_pct/100)), 'Type': 'P_Act', 'Label': f"{int(p_pct)}%", 'Width': 0.8, 'Color': '#2C3E50', 'Pos': 'inside'})
        
        main_tasks = df_proj['Main_Task'].unique()
        colors = px.colors.qualitative.Prism
        for idx, mt in enumerate(main_tasks):
            df_mt_group = df_proj[df_proj['Main_Task'] == mt]
            group_col = colors[idx % len(colors)]
            mt_s, mt_e, mt_pct = df_mt_group['Start_Date'].min(), df_mt_group['End_Date'].max()+pd.Timedelta(days=1), df_mt_group['Progress'].mean()
            mt_lab = f"📑 {mt}"
            plot_data.append({'Task': mt_lab, 'Start': mt_s, 'End': mt_e, 'Type': f'M_P_{idx}', 'Label': '', 'Width': 0.55, 'Color': '#F2F3F4', 'Pos': 'outside'})
            plot_data.append({'Task': mt_lab, 'Start': mt_s, 'End': mt_s+((mt_e-mt_s)*(mt_pct/100)), 'Type': f'M_A_{idx}', 'Label': f"{int(mt_pct)}%", 'Width': 0.55, 'Color': group_col, 'Pos': 'outside'})
            
            df_stk_list = df_mt_group.groupby(['Sub_Task', 'Dependency']).agg({'Start_Date': 'min', 'End_Date': 'max', 'Progress': 'mean'}).reset_index().sort_values('Start_Date')
            for s_idx, srow in df_stk_list.iterrows():
                ss, se, st_pct = srow['Start_Date'], srow['End_Date']+pd.Timedelta(days=1), srow['Progress']
                dep_info = f" (รอ: {srow['Dependency']})" if srow['Dependency'] else ""
                st_lab = f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;└ {srow['Sub_Task']}{dep_info}"
                plot_data.append({'Task': st_lab, 'Start': ss, 'End': se, 'Type': f'S_P_{idx}_{s_idx}', 'Label': '', 'Width': 0.35, 'Color': '#FDFEFE', 'Pos': 'outside'})
                plot_data.append({'Task': st_lab, 'Start': ss, 'End': ss+((se-ss)*(st_pct/100)), 'Type': f'S_A_{idx}_{s_idx}', 'Label': f"{int(st_pct)}%", 'Width': 0.35, 'Color': group_col, 'Pos': 'outside'})

        df_p = pd.DataFrame(plot_data)
        fig = px.timeline(df_p, x_start="Start", x_end="End", y="Task", color="Type", text="Label", height=len(df_p)*28 + 150)
        for i, row in df_p.iterrows():
            f_col = "white" if row['Pos'] == 'inside' else "black"
            fig.update_traces(marker_color=row['Color'], selector={'name': row['Type']}, patch={"width": row['Width'], "textposition": row['Pos'], "textfont": {"size": 15, "family": "Arial Black", "color": f_col}})
        
        fig.update_yaxes(categoryorder="array", categoryarray=df_p['Task'].unique()[::-1], tickfont=dict(size=16, family="Arial Black", color="black"), title="")
        fig.update_layout(showlegend=False, margin=dict(r=150, l=250), barmode='overlay')
        fig.add_vline(x=datetime.now().timestamp()*1000, line_dash="solid", line_color="red", line_width=2)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("🔍 รายละเอียดคนทำงาน")
        df_summary = df_proj.groupby(['Sub_Task', 'Main_Task', 'Dependency']).agg({'Progress': 'mean'}).reset_index()
        event = st.dataframe(df_summary, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        if event.selection.rows:
            idx = event.selection.rows[0]; sel_sub = df_summary.iloc[idx]['Sub_Task']
            team = df_proj[df_proj['Sub_Task'] == sel_sub]
            st.markdown(f"### 👥 ทีมงาน: {sel_sub}")
            for _, r in team.iterrows():
                c1, c2, c3 = st.columns([2, 5, 1])
                c1.markdown(f"**👤 {r['Employee']}**"); c2.progress(int(r['Progress'])/100); c3.write(f"{int(r['Progress'])}%")

# --- TAB 2: แก้ไข/ลบ ---
with tabs[2]:
    st.subheader("🛠️ การจัดการข้อมูล (แก้ไข / ลบ)")
    df_raw = st.session_state.get('data', pd.DataFrame()).copy()
    if not df_raw.empty:
        df_raw.insert(0, "Action", False)
        edited_df = st.data_editor(df_raw, column_config={"Action": st.column_config.CheckboxColumn("ลบ?", default=False), "Progress": st.column_config.NumberColumn("Progress (%)", min_value=0, max_value=100), "Status": st.column_config.SelectboxColumn("สถานะ", options=["⏳ กำลังทำ", "✅ เสร็จสมบูรณ์", "⚠️ ติดปัญหา"])}, hide_index=True, use_container_width=True, key="admin_editor_v13")
        
        c1, c2 = st.columns(2)
        if c1.button("💾 ยืนยันการบันทึกแก้ไข", use_container_width=True, type="primary"):
            edited_df.loc[edited_df['Progress'] == 100, 'Status'] = "✅ เสร็จสมบูรณ์"
            final_df = edited_df.drop(columns=["Action"])
            if save_data(final_df):
                st.success("บันทึกแล้ว!"); st.rerun()
        
        if c2.button("🗑️ ลบแถวที่ติ๊กเลือก", use_container_width=True):
            to_del = edited_df[edited_df["Action"] == True]
            if not to_del.empty and not any(to_del['Progress'] == 100):
                final_rem = edited_df[edited_df["Action"] == False].drop(columns=["Action"])
                if save_data(final_rem):
                    st.warning("ลบแล้ว!"); st.rerun()
            else:
                st.error("ห้ามลบงาน 100% หรือยังไม่ได้เลือกแถว")

# --- Ranking & Reports ---
with tabs[3]:
    st.subheader("🏆 Leaderboard")
    if not df_all.empty:
        ld = df_all.groupby('Employee')['Progress'].mean().reset_index().sort_values('Progress', ascending=False)
        st.plotly_chart(px.bar(ld, x='Employee', y='Progress', color='Progress', text_auto='.1f'), use_container_width=True)

with tabs[4]:
    st.subheader("📑 Project Summary")
    if not df_all.empty:
        st.dataframe(df_all.groupby(['Project', 'Main_Task'])['Progress'].mean().reset_index(), use_container_width=True)
        csv = df_all.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Download Report (CSV)", data=csv, file_name=f"AII_Report_{date.today()}.csv")