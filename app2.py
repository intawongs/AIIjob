import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import gspread

# ---------------------------------------------------------
# 1. CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(page_title="AII Project Tracker V17.4", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
        .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #dee2e6; }
        .stTabs [data-baseweb="tab"] { font-weight: bold; font-size: 1.1rem; }
    </style>
""", unsafe_allow_html=True)

st.title("🌌 AII Project Management System V17.4")

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
    expected_cols = ['Employee', 'Project', 'Main_Task', 'Sub_Task', 'Dependency', 'Start_Date', 'End_Date', 'Revised_End', 'Progress', 'Issue', 'Status']
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            ws_emps = sh.worksheet('Employees')
            ws_projs = sh.worksheet('Projects')
            
            df_logs = pd.DataFrame(ws_logs.get_all_records())
            df_projs = pd.DataFrame(ws_projs.get_all_records())
            df_emps = pd.DataFrame(ws_emps.get_all_records())
            
            for col in expected_cols:
                if col not in df_logs.columns: df_logs[col] = ""
            
            if not df_logs.empty:
                df_logs['Start_Date'] = pd.to_datetime(df_logs['Start_Date'], errors='coerce')
                df_logs['End_Date'] = pd.to_datetime(df_logs['End_Date'], errors='coerce')
                df_logs['Revised_End'] = pd.to_datetime(df_logs['Revised_End'], errors='coerce')
                df_logs['Progress'] = pd.to_numeric(df_logs['Progress'], errors='coerce').fillna(0)
            
            st.session_state['data'] = df_logs
            st.session_state['employees'] = df_emps['Name'].tolist() if not df_emps.empty else []
            st.session_state['projects_master'] = df_projs
            
            p_m = df_projs['Project'].dropna().unique().tolist() if not df_projs.empty else []
            p_l = df_logs['Project'].dropna().unique().tolist() if not df_logs.empty else []
            st.session_state['projects_list'] = sorted(list(set(p_m + p_l)))
            return df_logs
        except Exception as e:
            st.error(f"Load Error: {e}")
            return pd.DataFrame(columns=expected_cols)
    return pd.DataFrame()

def save_data(df_to_save):
    if df_to_save.empty:
        st.error("⚠️ ระงับการบันทึก: ตรวจพบข้อมูลว่างเปล่า")
        return False
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            save_df = df_to_save.copy().fillna("")
            for col in ['Start_Date', 'End_Date', 'Revised_End']:
                if col in save_df.columns:
                    save_df[col] = pd.to_datetime(save_df[col], errors='coerce').dt.strftime('%Y-%m-%d').replace('NaT', '')
            ws_logs.clear()
            ws_logs.update(range_name="A1", values=[save_df.columns.values.tolist()] + save_df.values.tolist())
            return True
        except: return False
    return False

if 'data' not in st.session_state: load_data()

# ==========================================
# 3. SIDEBAR (Fix: เพิ่มแล้วไม่หาย)
# ==========================================
with st.sidebar:
    st.header("⚙️ AII Control Panel")
    if st.button("🔄 Sync & Refresh", use_container_width=True):
        st.cache_data.clear(); load_data(); st.rerun()
    st.divider()
    
    with st.expander("👤 รายชื่อทีมงาน"):
        n_emp = st.text_input("เพิ่มชื่อพนักงาน", key="add_e_v17_4")
        if st.button("➕ บันทึกพนักงาน", use_container_width=True):
            if n_emp:
                sh = connect_gsheet(); sh.worksheet('Employees').append_row([n_emp])
                st.success(f"เพิ่ม {n_emp} แล้ว"); load_data(); st.rerun()

    with st.expander("📂 Baseline โปรเจกต์ (Fixed)"):
        # 🔥 แก้ไข: ใช้ st.form เพื่อให้ปุ่มกดแล้วทำงานแน่นอน
        with st.form("add_project_form"):
            n_p = st.text_input("ชื่อโปรเจกต์ใหม่")
            c1, c2 = st.columns(2); ps = c1.date_input("เริ่ม"); pe = c2.date_input("จบ")
            if st.form_submit_button("➕ บันทึก Baseline", use_container_width=True):
                if n_p:
                    sh = connect_gsheet()
                    # ใช้ append_row เพื่อ "ต่อท้าย" ของเดิม ไม่ใช่เขียนทับ
                    sh.worksheet('Projects').append_row([n_p, ps.strftime('%Y-%m-%d'), pe.strftime('%Y-%m-%d')])
                    st.success(f"บันทึก {n_p} แล้ว")
                    load_data(); st.rerun()

# ==========================================
# 4. MAIN INTERFACE
# ==========================================
tabs = st.tabs(["📝 ลงทะเบียน", "📊 แผนผังงาน (Gantt)", "🛠️ แก้ไข/ลบข้อมูล", "🏆 Leaderboard", "📑 รายงาน"])

with tabs[0]: # ลงทะเบียน
    st.subheader("📝 มอบหมายงานใหม่")
    df_curr = st.session_state.get('data', pd.DataFrame())
    p_list = st.session_state.get('projects_list', [])
    sel_p_reg = st.selectbox("📁 1. เลือกโปรเจกต์", p_list)
    f_mt = df_curr[df_curr['Project'] == sel_p_reg]['Main_Task'].unique().tolist() if not df_curr.empty else []
    
    with st.form("reg_form_v17_4", clear_on_submit=True):
        sel_mt = st.selectbox("📑 2. เลือกงานรอง", ["-- สร้างงานรองใหม่ --"] + f_mt)
        new_mt = st.text_input("✨ หรือพิมพ์ชื่อเฟสใหม่")
        final_mt = new_mt if sel_mt == "-- สร้างงานรองใหม่ --" else sel_mt
        stk = st.text_input("📌 3. ชื่องานย่อย")
        f_stk = df_curr[df_curr['Project'] == sel_p_reg]['Sub_Task'].unique().tolist() if not df_curr.empty else []
        sel_dep = st.selectbox("🔗 4. งานย่อยที่ต้องรอ", ["-- เริ่มได้ทันที --"] + f_stk)
        ems = st.multiselect("👥 5. ผู้รับผิดชอบ", st.session_state.get('employees', []))
        c1, c2 = st.columns(2); ds, de = c1.date_input("วันเริ่ม"), c2.date_input("วันจบ")
        if st.form_submit_button("💾 บันทึกงาน"):
            if final_mt and stk and ems:
                current_full = load_data()
                new_rows = [{'Employee': e, 'Project': sel_p_reg, 'Main_Task': final_mt, 'Sub_Task': stk, 'Dependency': ("" if sel_dep == "-- เริ่มได้ทันที --" else sel_dep), 'Start_Date': pd.to_datetime(ds), 'End_Date': pd.to_datetime(de), 'Progress': 0, 'Status': '⏳ กำลังทำ'} for e in ems]
                updated = pd.concat([current_full, pd.DataFrame(new_rows)], ignore_index=True)
                if save_data(updated): load_data(); st.rerun()

with tabs[1]: # Gantt
    df_all = st.session_state.get('data', pd.DataFrame())
    if not df_all.empty:
        today = datetime.now().date()
        df_all['Actual_End'] = df_all['Revised_End'].fillna(df_all['End_Date'])
        sel_p = st.selectbox("📂 ดูภาพรวมโปรเจกต์:", st.session_state.get('projects_list', []))
        df_proj = df_all[df_all['Project'] == sel_p].copy().sort_values('Start_Date')
        if not df_proj.empty:
            p_pct = df_proj['Progress'].mean(); st.metric(f"🚀 {sel_p} Overall", f"{p_pct:.1f}%")
            master = st.session_state.get('projects_master', pd.DataFrame())
            p_s, p_e = (pd.to_datetime(master[master['Project']==sel_p].iloc[0]['Start_Date']), pd.to_datetime(master[master['Project']==sel_p].iloc[0]['End_Date'])+pd.Timedelta(days=1)) if not master.empty and sel_p in master['Project'].values else (df_proj['Start_Date'].min(), df_proj['Actual_End'].max()+pd.Timedelta(days=1))
            
            plot_data = []
            plot_data.append({'Task': f"🏢 {sel_p}", 'Start': p_s, 'End': p_e, 'Type': 'P_Plan', 'Label': '', 'Width': 0.8, 'Color': '#D5D8DC'})
            plot_data.append({'Task': f"🏢 {sel_p}", 'Start': p_s, 'End': p_s+((p_e-p_s)*(p_pct/100)), 'Type': 'P_Act', 'Label': f"{int(p_pct)}%", 'Width': 0.8, 'Color': '#2C3E50'})
            
            main_tasks = df_proj.groupby('Main_Task')['Start_Date'].min().sort_values().index
            colors = px.colors.qualitative.Prism
            for idx, mt in enumerate(main_tasks):
                df_mt = df_proj[df_proj['Main_Task'] == mt]; g_col = colors[idx % len(colors)]
                ms, me, mp = df_mt['Start_Date'].min(), df_mt['Actual_End'].max()+pd.Timedelta(days=1), df_mt['Progress'].mean()
                plot_data.append({'Task': f"📑 {mt}", 'Start': ms, 'End': me, 'Type': f'M_P_{idx}', 'Label': '', 'Width': 0.55, 'Color': '#E5E8E8'})
                plot_data.append({'Task': f"📑 {mt}", 'Start': ms, 'End': ms+((me-ms)*(mp/100)), 'Type': f'M_A_{idx}', 'Label': f"{int(mp)}%", 'Width': 0.55, 'Color': g_col})
                
                df_stk = df_mt.groupby(['Sub_Task', 'Dependency']).agg({'Start_Date':'min','Actual_End':'max','Progress':'mean'}).reset_index().sort_values('Start_Date')
                for s_idx, srow in df_stk.iterrows():
                    ss, se, sp = srow['Start_Date'], srow['Actual_End']+pd.Timedelta(days=1), srow['Progress']
                    st_lab = f"&nbsp;&nbsp;&nbsp;&nbsp;└ {srow['Sub_Task']}"
                    plot_data.append({'Task': st_lab, 'Start': ss, 'End': se, 'Type': f'S_P_{idx}_{s_idx}', 'Label': '', 'Width': 0.35, 'Color': '#EBEDEF'})
                    plot_data.append({'Task': st_lab, 'Start': ss, 'End': ss+((se-ss)*(sp/100)), 'Type': f'S_A_{idx}_{s_idx}', 'Label': f"{int(sp)}%", 'Width': 0.35, 'Color': g_col})

            fig = px.timeline(pd.DataFrame(plot_data), x_start="Start", x_end="End", y="Task", color="Type", text="Label", height=len(plot_data)*30+150)
            fig.update_yaxes(categoryorder="array", categoryarray=[r['Task'] for r in plot_data][::-1], tickfont=dict(size=15), title="")
            fig.update_layout(showlegend=False, barmode='overlay')
            st.plotly_chart(fig, use_container_width=True)

with tabs[2]: # Admin
    st.subheader("🛠️ แก้ไข/ลบ")
    df_raw = st.session_state.get('data', pd.DataFrame()).copy()
    if not df_raw.empty:
        df_raw.insert(0, "เลือก", False)
        edit = st.data_editor(df_raw, column_config={"เลือก": st.column_config.CheckboxColumn("ลบ?")}, hide_index=True, use_container_width=True)
        if st.button("💾 บันทึกการแก้ไข", type="primary"):
            final = edit[edit["เลือก"] == False].drop(columns=["เลือก"])
            if save_data(final): load_data(); st.rerun()

with tabs[3]: # Ranking
    if not df_all.empty:
        ld = df_all.groupby('Employee')['Progress'].mean().reset_index().sort_values('Progress', ascending=False)
        st.plotly_chart(px.bar(ld, x='Employee', y='Progress', title="Top Performers"), use_container_width=True)

with tabs[4]: # Report
    st.subheader("📑 รายงานรวม")
    st.dataframe(st.session_state.get('data', pd.DataFrame()), use_container_width=True)