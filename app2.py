import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import gspread

# ---------------------------------------------------------
# 1. CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(page_title="ระบบติดตามงาน AII", layout="wide", initial_sidebar_state="auto")

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
        button[data-baseweb="tab"] { border-radius: 5px; margin: 0 2px; }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

st.title("🌌 Project Tracker (AII)")

# ==========================================
# 2. CONNECT GOOGLE SHEETS
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
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่ได้: {e}")
        return None

# ==========================================
# 3. DATABASE LOGIC
# ==========================================
def load_data():
    expected_cols = ['Employee', 'Main_Task', 'Sub_Task', 'Start_Date', 'End_Date', 'Output', 'Issue', 'Dependency', 'Progress', 'Score', 'Status']
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            ws_emps = sh.worksheet('Employees')
            ws_projs = sh.worksheet('Projects')

            df_logs = pd.DataFrame(ws_logs.get_all_records())
            df_projs = pd.DataFrame(ws_projs.get_all_records())
            df_emps = pd.DataFrame(ws_emps.get_all_records())

            if df_logs.empty: 
                df_logs = pd.DataFrame(columns=expected_cols)
            else:
                for col in expected_cols:
                    if col not in df_logs.columns: df_logs[col] = None
            
            if not df_logs.empty:
                df_logs['Start_Date'] = pd.to_datetime(df_logs['Start_Date'], errors='coerce')
                df_logs['End_Date'] = pd.to_datetime(df_logs['End_Date'], errors='coerce')
                df_logs['Progress'] = pd.to_numeric(df_logs['Progress'], errors='coerce').fillna(0)
                df_logs['Issue'] = df_logs['Issue'].astype(str).replace('nan', '')

            st.session_state['projects_master'] = df_projs
            st.session_state['employees'] = df_emps['Name'].tolist() if not df_emps.empty else []
            st.session_state['projects'] = df_projs['Project'].dropna().unique().tolist() if not df_projs.empty else []

            return df_logs, st.session_state['employees'], st.session_state['projects']
        except:
            return pd.DataFrame(columns=expected_cols), [], []
    return pd.DataFrame(), [], []

def save_data(df_to_save):
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            save_df = df_to_save.copy().fillna("")
            save_df['Start_Date'] = save_df['Start_Date'].dt.strftime('%Y-%m-%d')
            save_df['End_Date'] = save_df['End_Date'].dt.strftime('%Y-%m-%d')
            cols = ['Employee', 'Main_Task', 'Sub_Task', 'Start_Date', 'End_Date', 'Output', 'Issue', 'Dependency', 'Progress', 'Score', 'Status']
            ws_logs.clear()
            ws_logs.update(range_name="A1", values=[cols] + save_df[cols].values.tolist())
            return True
        except: return False

# ==========================================
# 4. DIALOGS
# ==========================================
@st.dialog("👤 รายละเอียดผู้รับผิดชอบ")
def show_task_info(task_name, project_name):
    df = st.session_state['data']
    team = df[(df['Main_Task'] == project_name) & (df['Sub_Task'] == task_name)]
    st.subheader(f"📌 {task_name}")
    st.divider()
    for _, row in team.iterrows():
        with st.container(border=True):
            c1, c2 = st.columns([1, 4])
            c1.markdown("### 👤")
            c2.markdown(f"**{row['Employee']}**")
            c2.progress(int(row['Progress'])/100)
            c2.caption(f"ความคืบหน้า: {int(row['Progress'])}%")
            if row['Issue']: st.info(f"📝 {row['Issue']}")

@st.dialog("📝 อัปเดตงาน (Group Sync)")
def update_task_dialog(index, row_data):
    df = st.session_state['data']
    task_name, project_name = row_data['Sub_Task'], row_data['Main_Task']
    team = df[(df['Main_Task'] == project_name) & (df['Sub_Task'] == task_name)]['Employee'].unique().tolist()
    
    st.markdown(f"📁 **โปรเจกต์:** {project_name}  \n📌 **งาน:** {task_name}  \n👥 **ทีมงาน:** {', '.join(team)}")
    new_prog = st.slider("ความคืบหน้า (%)", 0, 100, int(row_data['Progress']))
    new_issue = st.text_area("บันทึกเพิ่มเติม", value=str(row_data['Issue']))
    sync_all = st.checkbox("🔄 อัปเดตให้ทุกคนพร้อมกัน", value=True)
    
    c1, c2 = st.columns(2)
    if c1.button("💾 บันทึก", type="primary", use_container_width=True):
        if sync_all:
            mask = (df['Main_Task'] == project_name) & (df['Sub_Task'] == task_name)
            df.loc[mask, 'Progress'] = new_prog
            df.loc[mask, 'Issue'] = new_issue
        else:
            df.at[index, 'Progress'] = new_prog
            df.at[index, 'Issue'] = new_issue
        if save_data(df):
            st.toast("✅ อัปเดตเรียบร้อย!", icon="🚀")
            st.rerun()
    if c2.button("ยกเลิก", use_container_width=True): st.rerun()

# ==========================================
# 5. INITIALIZE
# ==========================================
if 'data' not in st.session_state:
    logs, emps, projs = load_data()
    st.session_state.update({"data": logs, "employees": emps, "projects": projs})

# ==========================================
# 6. SIDEBAR
# ==========================================
with st.sidebar:
    st.header("⚙️ ตั้งค่า")
    if st.button("🔄 รีเฟรชข้อมูล", use_container_width=True):
        st.cache_data.clear()
        logs, emps, projs = load_data()
        st.session_state.update({"data": logs, "employees": emps, "projects": projs})
        st.rerun()

    sel_emps_filter = st.multiselect("กรองพนักงาน (แผนผัง):", st.session_state['employees'], default=st.session_state['employees'])

    with st.expander("📂 จัดการโปรเจกต์ (Baseline)"):
        new_p_name = st.text_input("ชื่อโปรเจกต์ใหม่")
        c1, c2 = st.columns(2)
        p_start, p_end = c1.date_input("เริ่ม"), c2.date_input("จบ", value=date.today() + timedelta(days=30))
        if st.button("➕ บันทึกโปรเจกต์", use_container_width=True):
            if new_p_name:
                sh = connect_gsheet()
                sh.worksheet('Projects').append_row([new_p_name, p_start.strftime('%Y-%m-%d'), p_end.strftime('%Y-%m-%d')])
                st.toast(f"💾 บันทึก {new_p_name} แล้ว"); st.rerun()

# ==========================================
# 7. MAIN UI (5 TABS)
# ==========================================
tabs = st.tabs(["📝 ลงทะเบียน", "📊 แผนผัง & รายละเอียด", "🛠️ อัปเดต", "🏆 ผลงาน", "📑 รายงาน"])

with tabs[0]: # ลงทะเบียน
    with st.form("task_reg", clear_on_submit=True):
        p = st.selectbox("โปรเจกต์", st.session_state['projects'])
        sub = st.text_input("ชื่องานย่อย")
        emps_multi = st.multiselect("ผู้รับผิดชอบ", st.session_state['employees'])
        c1, c2 = st.columns(2)
        d_s, d_e = c1.date_input("เริ่ม", value=date.today()), c2.date_input("จบ", value=date.today()+timedelta(days=7))
        if st.form_submit_button("💾 บันทึกงาน", use_container_width=True):
            latest_logs, _, _ = load_data()
            new_rows = [{'Employee': e, 'Main_Task': p, 'Sub_Task': sub, 'Start_Date': pd.to_datetime(d_s), 'End_Date': pd.to_datetime(d_e), 'Progress': 0} for e in emps_multi]
            updated = pd.concat([latest_logs, pd.DataFrame(new_rows)], ignore_index=True)
            if save_data(updated):
                st.session_state['data'] = updated
                st.toast(f"✅ บันทึกงานสำเร็จ!"); st.rerun()

with tabs[1]: # แผนผัง & รายละเอียด (Overlay Progress Bar)
    df_all = st.session_state['data']
    if not df_all.empty and st.session_state['projects']:
        sel_p = st.selectbox("📂 เลือกโปรเจกต์:", st.session_state['projects'], key="dash_p")
        master = st.session_state.get('projects_master', pd.DataFrame())
        
        if not master.empty and sel_p in master['Project'].values:
            p_info = master[master['Project'] == sel_p].iloc[0]
            p_start_dt = pd.to_datetime(p_info['Start_Date'])
            p_end_dt = pd.to_datetime(p_info['End_Date']) + pd.Timedelta(days=1)
            actual_pct = df_all[df_all['Main_Task'] == sel_p]['Progress'].mean()
            
            st.metric(f"Progress รวม: {sel_p}", f"{actual_pct:.1f}%")

            # --- Gantt Chart Logic: Double Layer ---
            df_sub = df_all[(df_all['Main_Task'] == sel_p) & (df_all['Employee'].isin(sel_emps_filter))].copy()
            if not df_sub.empty:
                plot_data_list = []
                
                # 1. สร้างแถบ Baseline (ชั้นหลัง) และ Actual (ชั้นหน้า) ของโปรเจกต์หลัก
                plot_data_list.append({'Task': f"🏢 {sel_p}", 'Start': p_start_dt, 'End': p_end_dt, 'Type': 'Planned', 'Label': ''})
                p_actual_end = p_start_dt + ((p_end_dt - p_start_dt) * (actual_pct / 100))
                plot_data_list.append({'Task': f"🏢 {sel_p}", 'Start': p_start_dt, 'End': p_actual_end, 'Type': 'Actual', 'Label': f"{int(actual_pct)}%"})

                # 2. สร้างแถบของงานย่อยแต่ละงาน
                # รวมกลุ่มตามงานย่อย (โชว์ความคืบหน้าเฉลี่ยของงานนั้น)
                df_grouped = df_sub.groupby('Sub_Task').agg({'Start_Date': 'min', 'End_Date': 'max', 'Progress': 'mean'}).reset_index()
                
                for _, row in df_grouped.iterrows():
                    s, e = row['Start_Date'], row['End_Date'] + pd.Timedelta(days=1)
                    # แถบหลัง (Planned Frame)
                    plot_data_list.append({'Task': row['Sub_Task'], 'Start': s, 'End': e, 'Type': 'Planned_Sub', 'Label': ''})
                    # แถบหน้า (Actual Progress)
                    progress_dur = (e - s) * (row['Progress'] / 100)
                    plot_data_list.append({'Task': row['Sub_Task'], 'Start': s, 'End': s + progress_dur, 'Type': 'Actual_Sub', 'Label': f"{int(row['Progress'])}%"})

                df_plot = pd.DataFrame(plot_data_list)
                
                fig = px.timeline(
                    df_plot, x_start="Start", x_end="End", y="Task", color="Type", text="Label", height=450,
                    color_discrete_map={
                        "Planned": "#E5E7E9",      # เทาอ่อน (หลังโปรเจกต์)
                        "Actual": "#2C3E50",       # ดำ/น้ำเงินเข้ม (หน้าโปรเจกต์)
                        "Planned_Sub": "#EBF5FB",  # ฟ้าจางมาก (หลังงานย่อย)
                        "Actual_Sub": "#3498DB"    # ฟ้าสดใส (หน้างานย่อย)
                    }
                )
                
                # ปรับแต่งให้แท่ง Actual ทับ Planned สวยๆ
                fig.update_traces(textposition='inside', insidetextanchor='start')
                fig.update_traces(patch={"width": 0.7}, selector={"name": "Planned"})
                fig.update_traces(patch={"width": 0.7}, selector={"name": "Actual"})
                fig.update_traces(patch={"width": 0.4}, selector={"name": "Planned_Sub"})
                fig.update_traces(patch={"width": 0.4}, selector={"name": "Actual_Sub"})
                
                fig.update_yaxes(autorange="reversed", title="")
                fig.add_vline(x=datetime.now().timestamp()*1000, line_dash="dot", line_color="red", annotation_text="วันนี้")
                st.plotly_chart(fig, use_container_width=True)

                # 🔍 ตารางรายละเอียด (Popup)
                st.markdown("---")
                st.markdown("🔍 **เลือกงานเพื่อดูรายชื่อผู้รับผิดชอบและบันทึก**")
                task_list_df = df_grouped[['Sub_Task', 'Progress']]
                event_info = st.dataframe(task_list_df, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
                
                if event_info.selection.rows:
                    selected_task = task_list_df.iloc[event_info.selection.rows[0]]['Sub_Task']
                    show_task_info(selected_task, sel_p)

with tabs[2]: # อัปเดต
    st.subheader("🛠️ คลิกเลือกงานจากตารางเพื่ออัปเดตยกทีม")
    df_upd = st.session_state['data'].copy()
    if not df_upd.empty:
        event = st.dataframe(df_upd[['Sub_Task', 'Main_Task', 'Employee', 'Progress', 'Issue']], 
                            use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        if event.selection.rows:
            idx = event.selection.rows[0]
            if st.button(f"✏️ อัปเดตงาน: {df_upd.iloc[idx]['Sub_Task']}", type="primary", use_container_width=True):
                update_task_dialog(idx, df_upd.iloc[idx])

with tabs[3]: # ผลงาน
    if not df_all.empty:
        sum_df = df_all.groupby('Employee')['Progress'].mean().reset_index().sort_values('Progress', ascending=False)
        for i, row in sum_df.iterrows():
            st.metric(f"#{i+1} {row['Employee']}", f"{row['Progress']:.1f}%")

with tabs[4]: # รายงาน
    if not df_all.empty:
        st.subheader("📊 สรุปภาพรวมโปรเจกต์")
        st.table(df_all.groupby('Main_Task')['Progress'].mean().reset_index())