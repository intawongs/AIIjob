import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import gspread

# ---------------------------------------------------------
# 1. CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(page_title="AII Project Tracker - Full 5 Tabs", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
        [data-testid="stMetricValue"] { font-size: 1.8rem; color: #1f77b4; }
        .stTabs [data-baseweb="tab"] { border-radius: 5px; padding: 10px 20px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("🌌 AII Project Management System (Full 5 Tabs)")

# ==========================================
# 2. DATA ENGINE (Google Sheets)
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
    expected_logs = ['Employee', 'Project', 'Main_Task', 'Sub_Task', 'Start_Date', 'End_Date', 'Progress', 'Issue', 'Score', 'Status']
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            ws_emps = sh.worksheet('Employees')
            ws_projs = sh.worksheet('Projects')

            df_logs = pd.DataFrame(ws_logs.get_all_records())
            df_projs = pd.DataFrame(ws_projs.get_all_records())
            df_emps = pd.DataFrame(ws_emps.get_all_records())

            # Check & Create missing columns
            for col in expected_logs:
                if col not in df_logs.columns: df_logs[col] = ""
            
            if not df_logs.empty:
                df_logs['Start_Date'] = pd.to_datetime(df_logs['Start_Date'], errors='coerce')
                df_logs['End_Date'] = pd.to_datetime(df_logs['End_Date'], errors='coerce')
                df_logs['Progress'] = pd.to_numeric(df_logs['Progress'], errors='coerce').fillna(0)
                df_logs['Score'] = pd.to_numeric(df_logs['Score'], errors='coerce').fillna(0)

            # Store in state
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
            save_df['Start_Date'] = save_df['Start_Date'].dt.strftime('%Y-%m-%d')
            save_df['End_Date'] = save_df['End_Date'].dt.strftime('%Y-%m-%d')
            ws_logs.clear()
            ws_logs.update(range_name="A1", values=[save_df.columns.values.tolist()] + save_df.values.tolist())
            return True
        except: return False

# Initialize
if 'projects_list' not in st.session_state:
    load_data()

# ==========================================
# 3. INTERACTIVE DIALOGS
# ==========================================
@st.dialog("📝 อัปเดตงานย่อย (Sub-task)")
def update_task_dialog(index, row_data):
    df = st.session_state['data']
    task, main, proj = row_data['Sub_Task'], row_data['Main_Task'], row_data['Project']
    
    st.markdown(f"🏢 **Project:** {proj}  \n📑 **Task:** {main}")
    st.subheader(f"📌 {task}")
    
    new_prog = st.slider("Progress (%)", 0, 100, int(row_data['Progress']))
    new_issue = st.text_area("Issue/Note", value=str(row_data['Issue']))
    new_status = st.selectbox("Status", ["⏳ กำลังทำ", "✅ เสร็จแล้ว", "⚠️ ติดปัญหา"], index=0)
    
    sync_all = st.checkbox("🔄 อัปเดตทุกคนที่รับผิดชอบงานย่อยนี้พร้อมกัน", value=True)
    
    if st.button("💾 บันทึกข้อมูล", type="primary", use_container_width=True):
        if sync_all:
            mask = (df['Project'] == proj) & (df['Main_Task'] == main) & (df['Sub_Task'] == task)
            df.loc[mask, ['Progress', 'Issue', 'Status']] = [new_prog, new_issue, new_status]
        else:
            df.at[index, 'Progress'] = new_prog
            df.at[index, 'Issue'] = new_issue
            df.at[index, 'Status'] = new_status
        
        if save_data(df):
            st.toast("✅ อัปเดตสำเร็จ!"); st.rerun()

# ==========================================
# 4. SIDEBAR
# ==========================================
with st.sidebar:
    st.header("⚙️ ระบบจัดการ")
    if st.button("🔄 ดึงข้อมูลล่าสุด", use_container_width=True):
        st.cache_data.clear()
        load_data()
        st.rerun()
    
    st.divider()
    with st.expander("👤 รายชื่อพนักงาน"):
        st.write(st.session_state['employees'])
        new_name = st.text_input("ชื่อเล่น/ชื่อจริง")
        if st.button("เพิ่มพนักงาน"):
            sh = connect_gsheet()
            sh.worksheet('Employees').append_row([new_name])
            st.rerun()

    with st.expander("📂 สร้างโปรเจกต์ (Baseline)"):
        p_name = st.text_input("Project Name")
        c1, c2 = st.columns(2)
        ps = c1.date_input("Start Date")
        pe = c2.date_input("End Date", value=date.today()+timedelta(days=30))
        if st.button("เพิ่มโปรเจกต์"):
            sh = connect_gsheet()
            sh.worksheet('Projects').append_row([p_name, ps.strftime('%Y-%m-%d'), pe.strftime('%Y-%m-%d')])
            st.rerun()

# ==========================================
# 5. MAIN TABS (The Full 5)
# ==========================================
tabs = st.tabs(["📝 ลงทะเบียน", "📊 แผนผังงาน", "🛠️ อัปเดตงาน", "🏆 อันดับผลงาน", "📑 สรุปรายงาน"])

# --- TAB 0: ลงทะเบียน ---
with tabs[0]:
    st.subheader("📝 บันทึกมอบหมายงานใหม่")
    with st.form("reg_form", clear_on_submit=True):
        p = st.selectbox("1. เลือกโปรเจกต์", st.session_state['projects_list'])
        mt = st.text_input("2. งานรอง / เฟส (Main Task)")
        stk = st.text_input("3. งานย่อย (Sub-task)")
        ems = st.multiselect("4. ผู้รับผิดชอบ", st.session_state['employees'])
        c1, c2 = st.columns(2)
        ds, de = c1.date_input("วันเริ่ม"), c2.date_input("วันสิ้นสุด")
        if st.form_submit_button("💾 บันทึกงานสู่ระบบ", use_container_width=True):
            if p and mt and stk and ems:
                latest = st.session_state['data']
                new_rows = [{'Employee': e, 'Project': p, 'Main_Task': mt, 'Sub_Task': stk, 
                             'Start_Date': pd.to_datetime(ds), 'End_Date': pd.to_datetime(de), 
                             'Progress': 0, 'Status': '⏳ กำลังทำ'} for e in ems]
                updated = pd.concat([latest, pd.DataFrame(new_rows)], ignore_index=True)
                if save_data(updated):
                    st.toast("✅ บันทึกสำเร็จ"); st.rerun()

# --- TAB 1: แผนผังงาน (Gantt 3 Levels) ---
with tabs[1]:
    df_all = st.session_state.get('data', pd.DataFrame())
    if not df_all.empty:
        available_p = df_all['Project'].unique().tolist()
        sel_p = st.selectbox("📂 ดูแผนผังรายโปรเจกต์:", available_p, key="p_gantt_v3")
        
        df_proj = df_all[df_all['Project'] == sel_p].copy()
        
        # --- Logic จัดการ Baseline (เหมือนเดิม) ---
        master = st.session_state.get('projects_master', pd.DataFrame())
        if not master.empty and sel_p in master['Project'].values:
            p_info = master[master['Project'] == sel_p].iloc[0]
            p_s, p_e = pd.to_datetime(p_info['Start_Date']), pd.to_datetime(p_info['End_Date']) + pd.Timedelta(days=1)
        else:
            p_s, p_e = df_proj['Start_Date'].min(), df_proj['End_Date'].max() + pd.Timedelta(days=1)

        p_pct = df_proj['Progress'].mean()
        st.metric(f"📊 {sel_p}", f"{p_pct:.1f}%")

        plot_data = []
        
        # 1. Project Layer (บนสุด)
        plot_data.append({'Task': f"🏢 {sel_p}", 'Start': p_s, 'End': p_e, 'Color_Group': 'PROJECT', 'Width': 0.8, 'Label': f"TOTAL: {int(p_pct)}%"})

        # 2. Main Task & Sub Task (เรียงกลุ่ม)
        # สร้าง Palette สีให้แต่ละ Main Task (เพื่อให้ Sub-task มีสีเดียวกับแม่)
        main_tasks = df_proj['Main_Task'].unique()
        
        for idx, mt in enumerate(main_tasks):
            df_mt_group = df_proj[df_proj['Main_Task'] == mt]
            mt_s, mt_e = df_mt_group['Start_Date'].min(), df_mt_group['End_Date'].max() + pd.Timedelta(days=1)
            mt_pct = df_mt_group['Progress'].mean()
            
            group_key = f"GROUP_{idx}" # ใช้ ID กลุ่มในการคุมสี
            
            # เพิ่มแถว Main Task (หนาปานกลาง)
            mt_label = f"📑 {mt}"
            plot_data.append({'Task': mt_label, 'Start': mt_s, 'End': mt_e, 'Color_Group': group_key, 'Width': 0.5, 'Label': f"{int(mt_pct)}%"})
            
            # เพิ่ม Sub-tasks (บาง)
            df_stk = df_mt_group.groupby('Sub_Task').agg({'Start_Date': 'min', 'End_Date': 'max', 'Progress': 'mean'}).reset_index()
            for _, srow in df_stk.iterrows():
                # เพิ่มช่องว่าง (Indent) หน้าชื่อให้เยอะขึ้น
                st_label = f"&nbsp;&nbsp;&nbsp;&nbsp;└ {srow['Sub_Task']}" 
                plot_data.append({
                    'Task': st_label, 
                    'Start': srow['Start_Date'], 
                    'End': srow['End_Date'] + pd.Timedelta(days=1), 
                    'Color_Group': group_key, # 🎨 ใช้สีกลุ่มเดียวกับ Main Task
                    'Width': 0.25, 
                    'Label': f"{int(srow['Progress'])}%"
                })

        df_p = pd.DataFrame(plot_data)
        
        # วาดกราฟโดยแยกสีตาม Color_Group
        fig = px.timeline(
            df_p, x_start="Start", x_end="End", y="Task", 
            color="Color_Group", # แยกสีตามกลุ่มงาน
            text="Label", 
            height=len(df_p) * 40 + 100, # ปรับความสูงตามจำนวนงาน
            color_discrete_sequence=px.colors.qualitative.Pastel # ใช้โทนสีพาสเทลแยกง่าย
        )

        fig.update_yaxes(categoryorder="array", categoryarray=df_p['Task'].unique()[::-1], title="")
        
        # ปรับความหนาแบบ Dynamic ตามที่ตั้งไว้ใน df_p
        for i, task in enumerate(df_p['Task'].unique()):
            w = df_p[df_p['Task'] == task]['Width'].iloc[0]
            fig.update_traces(patch={"width": w}, selector={"name": df_p[df_p['Task'] == task]['Color_Group'].iloc[0]})

        fig.update_layout(showlegend=False) # ซ่อน Legend เพื่อลดความรก
        fig.update_traces(textfont=dict(size=12, family="Arial Black"))
        
        st.plotly_chart(fig, use_container_width=True)

# --- TAB 2: อัปเดตงาน (Quick Edit) ---
with tabs[2]:
    st.subheader("🛠️ ค้นหาและอัปเดตงานย่อย")
    df_u = st.session_state['data']
    if not df_u.empty:
        search = st.text_input("🔍 ค้นหางาน/ชื่อคน:", placeholder="พิมพ์ชื่อคน หรือชื่องาน...")
        df_filtered = df_u[df_u.apply(lambda row: search.lower() in str(row).lower(), axis=1)]
        
        ev = st.dataframe(df_filtered[['Sub_Task', 'Main_Task', 'Project', 'Employee', 'Progress', 'Status']], 
                         use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        
        if ev.selection.rows:
            idx = df_filtered.index[ev.selection.rows[0]]
            if st.button(f"✏️ เปิดหน้าแก้ไข: {df_u.iloc[idx]['Sub_Task']}", type="primary"):
                update_task_dialog(idx, df_u.iloc[idx])

# --- TAB 3: อันดับผลงาน (Leaderboard) ---
with tabs[3]:
    st.subheader("🏆 Leaderboard - ความสำเร็จรายบุคคล")
    df_l = st.session_state['data']
    if not df_l.empty:
        # คำนวณ Score จาก Progress เฉลี่ย
        leader = df_l.groupby('Employee').agg({'Progress': 'mean', 'Sub_Task': 'count'}).reset_index()
        leader.columns = ['พนักงาน', 'ความคืบหน้าเฉลี่ย (%)', 'จำนวนงานที่ถือ']
        leader = leader.sort_values('ความคืบหน้าเฉลี่ย (%)', ascending=False)
        
        c1, c2 = st.columns([2, 1])
        with c1:
            fig_l = px.bar(leader, x='พนักงาน', y='ความคืบหน้าเฉลี่ย (%)', color='ความคืบหน้าเฉลี่ย (%)', 
                           text_auto='.1f', title="อันดับพนักงานตาม Progress")
            st.plotly_chart(fig_l, use_container_width=True)
        with c2:
            st.table(leader)

# --- TAB 4: สรุปรายงาน (Summary Report) ---
with tabs[4]:
    st.subheader("📑 รายงานสรุปสถานะโครงการ")
    df_r = st.session_state['data']
    if not df_r.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("จำนวนงานทั้งหมด", len(df_r))
        c2.metric("งานที่เสร็จแล้ว", len(df_r[df_r['Progress'] == 100]))
        c3.metric("เฉลี่ยทุกโปรเจกต์", f"{df_r['Progress'].mean():.1f}%")
        
        st.divider()
        st.markdown("### 📊 ตารางสรุปรายโปรเจกต์")
        rpt = df_r.groupby(['Project', 'Main_Task']).agg({
            'Progress': 'mean',
            'Employee': lambda x: ', '.join(x.unique()),
            'Status': 'first'
        }).reset_index()
        st.dataframe(rpt, use_container_width=True)
        
        # Download Button
        csv = df_r.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 ดาวน์โหลดรายงาน (CSV)", data=csv, file_name=f"AII_Report_{date.today()}.csv", mime='text/csv')