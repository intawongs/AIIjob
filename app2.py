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
# 3. DATABASE LOGIC (SAFE LOAD & SAVE)
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
            
            # 🔥 บังคับ Format วันที่ให้ Plotly และ Logic คำนวณอ่านได้
            if not df_logs.empty:
                df_logs['Start_Date'] = pd.to_datetime(df_logs['Start_Date'], errors='coerce')
                df_logs['End_Date'] = pd.to_datetime(df_logs['End_Date'], errors='coerce')
                df_logs['Progress'] = pd.to_numeric(df_logs['Progress'], errors='coerce').fillna(0)
                df_logs['Issue'] = df_logs['Issue'].astype(str).replace('nan', '')

            st.session_state['projects_master'] = df_projs
            st.session_state['employees'] = df_emps['Name'].tolist() if not df_emps.empty else []
            st.session_state['projects'] = df_projs['Project'].dropna().unique().tolist() if not df_projs.empty else []

            return df_logs, st.session_state['employees'], st.session_state['projects']
        except Exception as e:
            return pd.DataFrame(columns=expected_cols), [], []
    return pd.DataFrame(), [], []

def save_data(df_to_save):
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            save_df = df_to_save.copy().fillna("")
            # แปลงกลับเป็น String ISO Format ก่อนลง Sheet
            save_df['Start_Date'] = save_df['Start_Date'].dt.strftime('%Y-%m-%d')
            save_df['End_Date'] = save_df['End_Date'].dt.strftime('%Y-%m-%d')
            
            cols = ['Employee', 'Main_Task', 'Sub_Task', 'Start_Date', 'End_Date', 'Output', 'Issue', 'Dependency', 'Progress', 'Score', 'Status']
            ws_logs.clear()
            ws_logs.update(range_name="A1", values=[cols] + save_df[cols].values.tolist())
            return True
        except: return False

# ==========================================
# 4. INITIALIZE & DIALOG (SYNC FEATURE)
# ==========================================
if 'data' not in st.session_state:
    logs, emps, projs = load_data()
    st.session_state.update({"data": logs, "employees": emps, "projects": projs})

@st.dialog("📝 อัปเดตงาน (Group Sync)")
def update_task_dialog(index, row_data):
    df = st.session_state['data']
    task_name = row_data['Sub_Task']
    project_name = row_data['Main_Task']
    
    # ดึงทีมงานที่เกี่ยวข้องมาโชว์
    team = df[(df['Main_Task'] == project_name) & (df['Sub_Task'] == task_name)]['Employee'].unique().tolist()
    
    st.markdown(f"📁 **โปรเจกต์:** {project_name}  \n📌 **งาน:** {task_name}  \n👥 **ทีมงาน:** {', '.join(team)}")
    
    new_prog = st.slider("ความคืบหน้า (%)", 0, 100, int(row_data['Progress']))
    new_issue = st.text_area("บันทึกเพิ่มเติม", value=str(row_data['Issue']))
    
    sync_all = st.checkbox("🔄 อัปเดตให้ทุกคนในงานนี้พร้อมกัน", value=True)
    
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
            st.toast(f"✅ อัปเดตงานให้ทีม {len(team) if sync_all else 1} คนเรียบร้อย", icon="🚀")
            st.rerun()
    if c2.button("ยกเลิก", use_container_width=True): st.rerun()

# ==========================================
# 5. SIDEBAR
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
        new_p_name = st.text_input("ชื่อโปรเจกต์หลัก", key="new_p_side")
        c1, c2 = st.columns(2)
        p_start = c1.date_input("วันเริ่ม")
        p_end = c2.date_input("วันจบ", value=date.today() + timedelta(days=30))
        if st.button("➕ บันทึกโปรเจกต์", use_container_width=True):
            if new_p_name:
                sh = connect_gsheet()
                sh.worksheet('Projects').append_row([new_p_name, p_start.strftime('%Y-%m-%d'), p_end.strftime('%Y-%m-%d')])
                st.toast(f"💾 บันทึกโปรเจกต์ {new_p_name} แล้ว", icon="✅")
                st.rerun()

# ==========================================
# 6. UI TABS
# ==========================================
tabs = st.tabs(["📝 ลงทะเบียน", "📊 แผนผัง & Dashboard", "🛠️ อัปเดต", "🏆 ผลงาน", "📑 รายงาน"])

with tabs[0]: # ลงทะเบียน (บันทึกแล้วล้างค่า)
    with st.form("reg_form", clear_on_submit=True):
        p_opt = st.session_state['projects']
        p = st.selectbox("เลือกโปรเจกต์", p_opt if p_opt else ["-- ไม่มีข้อมูล --"])
        sub = st.text_input("ชื่องานย่อย")
        emps_multi = st.multiselect("ผู้รับผิดชอบ", st.session_state['employees'])
        c1, c2 = st.columns(2)
        d_start, d_end = c1.date_input("เริ่ม"), c2.date_input("จบ")
        
        if st.form_submit_button("💾 บันทึกงานย่อย", use_container_width=True):
            if sub and emps_multi and p != "-- ไม่มีข้อมูล --":
                latest_logs, _, _ = load_data()
                new_rows = [{'Employee': e, 'Main_Task': p, 'Sub_Task': sub, 
                             'Start_Date': pd.to_datetime(d_start), 
                             'End_Date': pd.to_datetime(d_end), 
                             'Progress': 0, 'Status': '⏳ กำลังดำเนินการ'} for e in emps_multi]
                updated_df = pd.concat([latest_logs, pd.DataFrame(new_rows)], ignore_index=True)
                if save_data(updated_df):
                    st.session_state['data'] = updated_df
                    st.toast(f"✅ บันทึกงาน '{sub}' เรียบร้อย!", icon="💾")
                    st.rerun()
            else:
                st.warning("⚠️ กรุณากรอกข้อมูลให้ครบ")

with tabs[1]: # แผนผัง (Summary + Sub-tasks)
    df_all = st.session_state['data']
    if not df_all.empty and st.session_state['projects']:
        sel_p = st.selectbox("📂 เลือกโปรเจกต์:", st.session_state['projects'], key="p_dash_sel")
        
        master = st.session_state.get('projects_master', pd.DataFrame())
        if not master.empty and sel_p in master['Project'].values:
            p_info = master[master['Project'] == sel_p].iloc[0]
            p_s, p_e = pd.to_datetime(p_info['Start_Date']), pd.to_datetime(p_info['End_Date'])
            
            # Progress รวม
            actual_pct = df_all[df_all['Main_Task'] == sel_p]['Progress'].mean()
            st.metric(f"Progress รวม: {sel_p}", f"{actual_pct:.1f}%")
            st.progress(actual_pct/100)

            # Gantt Chart
            df_sub = df_all[(df_all['Main_Task'] == sel_p) & (df_all['Employee'].isin(sel_emps_filter))].copy()
            if not df_sub.empty:
                df_sub['Start'], df_sub['End_V'] = df_sub['Start_Date'], df_sub['End_Date'] + pd.Timedelta(days=1)
                df_sub['Type'] = "📌 งานย่อย"

                summary_row = pd.DataFrame([{
                    'Sub_Task': f"🎯 ภาพรวม: {sel_p}", 'Employee': 'OVERALL', 
                    'Start': p_s, 'End_V': p_e + pd.Timedelta(days=1), 'Progress': actual_pct, 'Type': "🏢 โปรเจกต์หลัก"
                }])

                df_plot = pd.concat([summary_row, df_sub], ignore_index=True)
                fig = px.timeline(df_plot, x_start="Start", x_end="End_V", y="Sub_Task", color="Type", text="Progress", height=450,
                                 color_discrete_map={"🏢 โปรเจกต์หลัก": "#333333", "📌 งานย่อย": "#636EFA"})
                fig.update_yaxes(autorange="reversed", title="")
                fig.add_vline(x=datetime.now().timestamp()*1000, line_dash="dot", line_color="red")
                st.plotly_chart(fig, use_container_width=True)

with tabs[2]: # อัปเดต (คลิกเลือกแล้วแก้)
    st.subheader("🛠️ คลิกเลือกแถวงานเพื่ออัปเดตยกทีม")
    df_upd = st.session_state['data'].copy()
    if not df_upd.empty:
        event = st.dataframe(
            df_upd[['Sub_Task', 'Main_Task', 'Employee', 'Progress', 'Issue']], 
            use_container_width=True, 
            hide_index=True,
            on_select="rerun", 
            selection_mode="single-row"
        )
        
        if event.selection.rows:
            idx = event.selection.rows[0]
            selected_row = df_upd.iloc[idx]
            if st.button(f"✏️ แก้ไขงานย่อย: {selected_row['Sub_Task']}", type="primary", use_container_width=True):
                update_task_dialog(idx, selected_row)
    else:
        st.info("📭 ยังไม่มีข้อมูลงานย่อย")

with tabs[3]: # ผลงาน
    df_perf = st.session_state['data']
    if not df_perf.empty:
        sum_df = df_perf.groupby('Employee')['Progress'].mean().reset_index().sort_values('Progress', ascending=False)
        for i, row in sum_df.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([1, 4])
                c1.title("🥇" if i==0 else "🥈" if i==1 else "🥉" if i==2 else f"#{i+1}")
                c2.metric(row['Employee'], f"{row['Progress']:.1f}% ความคืบหน้าเฉลี่ย")

with tabs[4]: # รายงาน
    st.subheader("📑 สรุปรายโปรเจกต์")
    if not st.session_state['data'].empty:
        st.table(st.session_state['data'].groupby('Main_Task')['Progress'].mean().reset_index())