import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import gspread

# ---------------------------------------------------------
# 1. CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(page_title="AII Project Tracker V5", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
        [data-testid="stMetricValue"] { font-size: 1.8rem; color: #1f77b4; }
        .stTabs [data-baseweb="tab"] { border-radius: 5px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("🌌 AII Project Management System V5")

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
    expected_logs = ['Employee', 'Project', 'Main_Task', 'Sub_Task', 'Start_Date', 'End_Date', 'Progress', 'Issue', 'Status']
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
            save_df['Start_Date'] = save_df['Start_Date'].dt.strftime('%Y-%m-%d')
            save_df['End_Date'] = save_df['End_Date'].dt.strftime('%Y-%m-%d')
            ws_logs.clear()
            ws_logs.update(range_name="A1", values=[save_df.columns.values.tolist()] + save_df.values.tolist())
            return True
        except: return False

if 'data' not in st.session_state:
    load_data()

# ==========================================
# 3. INTERACTIVE DIALOGS
# ==========================================
@st.dialog("📝 อัปเดตงาน (Sub-task)")
def update_task_dialog(index, row_data):
    df = st.session_state['data']
    task, main, proj = row_data['Sub_Task'], row_data['Main_Task'], row_data['Project']
    st.markdown(f"🏢 **{proj}** > 📑 **{main}**")
    st.subheader(f"📌 {task}")
    new_prog = st.slider("ความคืบหน้า (%)", 0, 100, int(row_data['Progress']))
    new_issue = st.text_area("Issue / Note", value=str(row_data['Issue']))
    sync_all = st.checkbox("🔄 อัปเดตทุกคนในงานย่อยนี้พร้อมกัน", value=True)
    if st.button("💾 บันทึก", type="primary", use_container_width=True):
        if sync_all:
            mask = (df['Project'] == proj) & (df['Main_Task'] == main) & (df['Sub_Task'] == task)
            df.loc[mask, ['Progress', 'Issue']] = [new_prog, new_issue]
        else:
            df.at[index, 'Progress'] = new_prog
            df.at[index, 'Issue'] = new_issue
        if save_data(df):
            st.toast("✅ อัปเดตสำเร็จ!"); st.rerun()

# ==========================================
# 4. SIDEBAR
# ==========================================
with st.sidebar:
    st.header("⚙️ ระบบ AII")
    if st.button("🔄 รีเฟรชข้อมูลล่าสุด", use_container_width=True):
        st.cache_data.clear()
        load_data()
        st.rerun()
    st.divider()
    with st.expander("👤 เพิ่มรายชื่อพนักงาน"):
        n_emp = st.text_input("ชื่อเล่น")
        if st.button("เพิ่มคน"):
            sh = connect_gsheet(); sh.worksheet('Employees').append_row([n_emp]); st.rerun()
    with st.expander("📂 สร้างโปรเจกต์ (Baseline)"):
        n_p = st.text_input("ชื่อโปรเจกต์")
        c1, c2 = st.columns(2)
        ps = c1.date_input("เริ่ม"); pe = c2.date_input("จบ")
        if st.button("เพิ่มโปรเจกต์"):
            sh = connect_gsheet(); sh.worksheet('Projects').append_row([n_p, ps.strftime('%Y-%m-%d'), pe.strftime('%Y-%m-%d')]); st.rerun()

# ==========================================
# 5. MAIN TABS
# ==========================================
tabs = st.tabs(["📝 ลงทะเบียน", "📊 แผนผังงาน", "🛠️ อัปเดตงาน", "🏆 อันดับผลงาน", "📑 รายงานสรุป"])

# --- TAB 0: ลงทะเบียน ---
with tabs[0]:
    st.subheader("📝 มอบหมายงาน (1 Task : N Sub-tasks)")
    df_curr = st.session_state.get('data', pd.DataFrame())
    with st.form("reg_form_v5", clear_on_submit=True):
        p = st.selectbox("📁 1. เลือกโปรเจกต์", st.session_state.get('projects_list', []))
        existing_mt = ["-- สร้างงานรองใหม่ --"]
        if not df_curr.empty and p:
            mt_list = df_curr[df_curr['Project'] == p]['Main_Task'].unique().tolist()
            existing_mt.extend(mt_list)
        sel_mt = st.selectbox("📑 2. เลือกงานรองที่มีอยู่ (หรือพิมพ์ใหม่ด้านล่าง)", existing_mt)
        new_mt = st.text_input("✨ กรณีสร้างงานรองใหม่ พิมพ์ที่นี่")
        final_mt = new_mt if sel_mt == "-- สร้างงานรองใหม่ --" else sel_mt
        stk = st.text_input("📌 3. ชื่องานย่อย (Sub-task)")
        ems = st.multiselect("👥 4. ผู้รับผิดชอบ", st.session_state.get('employees', []))
        c1, c2 = st.columns(2)
        ds, de = c1.date_input("วันเริ่ม"), c2.date_input("วันจบ")
        if st.form_submit_button("💾 บันทึกลงระบบ", use_container_width=True):
            if final_mt and stk and ems:
                latest = st.session_state['data']
                new_data = [{'Employee': e, 'Project': p, 'Main_Task': final_mt, 'Sub_Task': stk, 'Start_Date': pd.to_datetime(ds), 'End_Date': pd.to_datetime(de), 'Progress': 0} for e in ems]
                updated = pd.concat([latest, pd.DataFrame(new_data)], ignore_index=True)
                if save_data(updated):
                    st.toast("✅ บันทึกสำเร็จ"); st.rerun()

# --- TAB 1: แผนผังงาน (The Ultimate Gantt) ---
with tabs[1]:
    df_all = st.session_state.get('data', pd.DataFrame())
    if not df_all.empty:
        available_p = df_all['Project'].unique().tolist()
        sel_p = st.selectbox("📂 ดูแผนผังรายโปรเจกต์:", available_p, key="p_gantt_v5")
        df_proj = df_all[df_all['Project'] == sel_p].copy()
        master = st.session_state.get('projects_master', pd.DataFrame())
        if not master.empty and sel_p in master['Project'].values:
            p_info = master[master['Project'] == sel_p].iloc[0]
            p_s, p_e = pd.to_datetime(p_info['Start_Date']), pd.to_datetime(p_info['End_Date']) + pd.Timedelta(days=1)
        else:
            p_s, p_e = df_proj['Start_Date'].min(), df_proj['End_Date'].max() + pd.Timedelta(days=1)
        p_pct = df_proj['Progress'].mean()
        st.metric(f"📊 Overall Progress: {sel_p}", f"{p_pct:.1f}%")
        plot_data = []
        plot_data.append({'Task': f"🏢 {sel_p}", 'Start': p_s, 'End': p_e, 'Type': 'P_Plan', 'Label': '', 'Width': 0.8, 'Color': '#E5E7E9', 'Pos': 'inside'})
        plot_data.append({'Task': f"🏢 {sel_p}", 'Start': p_s, 'End': p_s+(p_e-p_s)*(p_pct/100), 'Type': 'P_Act', 'Label': f"{int(p_pct)}%", 'Width': 0.8, 'Color': '#2C3E50', 'Pos': 'inside'})
        main_tasks = df_proj['Main_Task'].unique()
        colors = px.colors.qualitative.Prism
        for idx, mt in enumerate(main_tasks):
            df_mt_group = df_proj[df_proj['Main_Task'] == mt]
            group_col = colors[idx % len(colors)]
            mt_s, mt_e, mt_pct = df_mt_group['Start_Date'].min(), df_mt_group['End_Date'].max()+pd.Timedelta(days=1), df_mt_group['Progress'].mean()
            mt_lab = f"📑 {mt}"
            plot_data.append({'Task': mt_lab, 'Start': mt_s, 'End': mt_e, 'Type': f'M_Plan_{idx}', 'Label': '', 'Width': 0.55, 'Color': '#F4F6F6', 'Pos': 'outside'})
            plot_data.append({'Task': mt_lab, 'Start': mt_s, 'End': mt_s+(mt_e-mt_s)*(mt_pct/100), 'Type': f'M_Act_{idx}', 'Label': f"{int(mt_pct)}%", 'Width': 0.55, 'Color': group_col, 'Pos': 'outside'})
            df_stk_list = df_mt_group.groupby('Sub_Task').agg({'Start_Date': 'min', 'End_Date': 'max', 'Progress': 'mean'}).reset_index().sort_values('Start_Date')
            for s_idx, srow in df_stk_list.iterrows():
                ss, se, st_pct = srow['Start_Date'], srow['End_Date']+pd.Timedelta(days=1), srow['Progress']
                st_lab = f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;└ {srow['Sub_Task']}"
                plot_data.append({'Task': st_lab, 'Start': ss, 'End': se, 'Type': f'S_Plan_{idx}_{s_idx}', 'Label': '', 'Width': 0.3, 'Color': '#FBFCFC', 'Pos': 'outside'})
                plot_data.append({'Task': st_lab, 'Start': ss, 'End': ss+(se-ss)*(st_pct/100), 'Type': f'S_Act_{idx}_{s_idx}', 'Label': f"{int(st_pct)}%", 'Width': 0.3, 'Color': group_col, 'Pos': 'outside'})
        df_p = pd.DataFrame(plot_data)
        fig = px.timeline(df_p, x_start="Start", x_end="End", y="Task", color="Type", text="Label", height=len(df_p)*25+180)
        for i, row in df_p.iterrows():
            f_col = "white" if row['Pos'] == 'inside' else "black"
            fig.update_traces(marker_color=row['Color'], selector={'name': row['Type']}, patch={"width": row['Width'], "textposition": row['Pos'], "textfont": {"size": 13, "family": "Arial Black", "color": f_col}})
        fig.update_yaxes(categoryorder="array", categoryarray=df_p['Task'].unique()[::-1], title="")
        fig.update_layout(showlegend=False, margin=dict(r=120))
        fig.add_vline(x=datetime.now().timestamp()*1000, line_dash="dot", line_color="red", annotation_text="Today")
        st.plotly_chart(fig, use_container_width=True)

# --- TAB 2: อัปเดตงาน ---
with tabs[2]:
    st.subheader("🛠️ ค้นหาและแก้ไขงาน")
    df_u = st.session_state['data']
    if not df_u.empty:
        search = st.text_input("🔍 ค้นหา (ชื่อคน/งาน):")
        df_f = df_u[df_u.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
        ev = st.dataframe(df_f[['Sub_Task', 'Main_Task', 'Project', 'Employee', 'Progress']], use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        if ev.selection.rows:
            idx = df_f.index[ev.selection.rows[0]]
            if st.button(f"✏️ แก้ไข: {df_u.iloc[idx]['Sub_Task']}", type="primary"): update_task_dialog(idx, df_u.iloc[idx])

# --- TAB 3: อันดับผลงาน ---
with tabs[3]:
    st.subheader("🏆 Leaderboard")
    if not df_all.empty:
        ld = df_all.groupby('Employee')['Progress'].mean().reset_index().sort_values('Progress', ascending=False)
        st.plotly_chart(px.bar(ld, x='Employee', y='Progress', color='Progress', text_auto='.1f', title="Success Rate (%)"), use_container_width=True)
        st.table(ld)

# --- TAB 4: สรุปรายงาน ---
with tabs[4]:
    st.subheader("📑 Project Summary")
    if not df_all.empty:
        rpt = df_all.groupby(['Project', 'Main_Task']).agg({'Progress': 'mean', 'Employee': lambda x: ', '.join(x.unique())}).reset_index()
        st.dataframe(rpt, use_container_width=True)
        csv = df_all.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Download Report (CSV)", data=csv, file_name=f"AII_Report_{date.today()}.csv")