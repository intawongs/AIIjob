import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import gspread

# ---------------------------------------------------------
# 1. CONFIGURATION & STYLING (ตัวหนังสือใหญ่ ชัดเจน)
# ---------------------------------------------------------
st.set_page_config(page_title="AII Project Tracker V16.1", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
        .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #dee2e6; }
        [data-testid="stMetricValue"] { font-size: 1.8rem; color: #007bff; }
        .stTabs [data-baseweb="tab"] { font-weight: bold; font-size: 1.1rem; }
        .late-card { background-color: #fff2f2; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b; margin-bottom: 10px; }
        p, th, td { font-size: 16px; }
    </style>
""", unsafe_allow_html=True)

st.title("🌌 AII Project Management System V16.1")

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
                if col not in df_logs.columns:
                    df_logs[col] = "" 

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

if 'data' not in st.session_state: load_data()

# ==========================================
# 3. SIDEBAR (ครบถ้วนห้ามตัด)
# ==========================================
with st.sidebar:
    st.header("⚙️ เมนูควบคุม AII")
    if st.button("🔄 Sync ข้อมูลล่าสุด", use_container_width=True):
        st.cache_data.clear(); load_data(); st.rerun()
    st.divider()
    with st.expander("👤 รายชื่อพนักงาน"):
        st.write(st.session_state.get('employees', []))
        n_emp = st.text_input("เพิ่มชื่อพนักงาน")
        if st.button("บันทึกพนักงาน"):
            sh = connect_gsheet(); sh.worksheet('Employees').append_row([n_emp])
            load_data(); st.rerun()
    with st.expander("📂 Baseline โปรเจกต์"):
        n_p = st.text_input("ชื่อโปรเจกต์ใหม่")
        c1, c2 = st.columns(2); ps = c1.date_input("เริ่ม Baseline"); pe = c2.date_input("จบ Baseline")
        if st.button("บันทึกโปรเจกต์"):
            sh = connect_gsheet(); sh.worksheet('Projects').append_row([n_p, ps.strftime('%Y-%m-%d'), pe.strftime('%Y-%m-%d')])
            load_data(); st.rerun()

# ==========================================
# 4. MAIN TABS
# ==========================================
tabs = st.tabs(["📝 ลงทะเบียน", "📊 แผนผังงาน (Gantt)", "🛠️ แก้ไข/ลบข้อมูล", "🏆 อันดับผลงาน", "📑 รายงาน"])

# --- TAB 0: ลงทะเบียน ---
with tabs[0]:
    st.subheader("📝 มอบหมายงานใหม่")
    df_curr = st.session_state.get('data', pd.DataFrame())
    with st.form("reg_v16_1", clear_on_submit=True):
        p = st.selectbox("📁 เลือกโปรเจกต์", st.session_state.get('projects_list', []))
        sel_mt = st.selectbox("📑 เลือกงานรอง", ["-- สร้างงานรองใหม่ --"] + (df_curr[df_curr['Project'] == p]['Main_Task'].unique().tolist() if p else []))
        new_mt = st.text_input("✨ หรือพิมพ์ชื่อเฟสใหม่"); final_mt = new_mt if sel_mt == "-- สร้างงานรองใหม่ --" else sel_mt
        stk = st.text_input("📌 ชื่องานย่อย (Sub-task)")
        sel_dep = st.selectbox("🔗 งานย่อยที่ต้องรอ", ["-- เริ่มได้ทันที --"] + (df_curr[df_curr['Project'] == p]['Sub_Task'].unique().tolist() if p else []))
        ems = st.multiselect("👥 ผู้รับผิดชอบ", st.session_state.get('employees', []))
        c1, c2 = st.columns(2); ds, de = c1.date_input("วันเริ่ม"), c2.date_input("วันจบ")
        if st.form_submit_button("💾 บันทึกงาน", use_container_width=True):
            if final_mt and stk and ems:
                latest = st.session_state['data']
                new_rows = [{'Employee': e, 'Project': p, 'Main_Task': final_mt, 'Sub_Task': stk, 'Dependency': ("" if sel_dep == "-- เริ่มได้ทันที --" else sel_dep), 'Start_Date': pd.to_datetime(ds), 'End_Date': pd.to_datetime(de), 'Progress': 0, 'Status': '⏳ กำลังทำ'} for e in ems]
                updated = pd.concat([latest, pd.DataFrame(new_rows)], ignore_index=True)
                if save_data(updated): st.success("บันทึกสำเร็จ!"); st.rerun()

# --- TAB 1: Gantt Chart & รายการงานค้าง ---
with tabs[1]:
    df_all = st.session_state.get('data', pd.DataFrame())
    if not df_all.empty:
        # 🚨 ตารางฟ้องงานค้าง (Late Task Alert)
        today = datetime.now().date()
        late_tasks = df_all[(df_all['Progress'] < 100) & (df_all['End_Date'].dt.date < today)].copy()
        if not late_tasks.empty:
            st.error(f"🚩 ตรวจพบงานเลยกำหนดส่ง {len(late_tasks)} รายการ")
            with st.expander("🔍 ดูรายละเอียดงานที่เลยกำหนด (Late Task List)", expanded=True):
                late_tasks['Days_Late'] = (today - late_tasks['End_Date'].dt.date).dt.days
                st.dataframe(late_tasks[['Employee', 'Sub_Task', 'End_Date', 'Days_Late', 'Progress']].style.highlight_max(subset=['Days_Late'], color='#ffcccc'), use_container_width=True, hide_index=True)

        sel_p = st.selectbox("📂 ดูโปรเจกต์:", df_all['Project'].unique().tolist(), key="view_p_v16")
        df_proj = df_all[df_all['Project'] == sel_p].copy()
        
        # Gantt Plotting
        p_pct = df_proj['Progress'].mean(); st.metric(f"🚀 {sel_p} Overall", f"{p_pct:.1f}%")
        master = st.session_state.get('projects_master', pd.DataFrame())
        p_s, p_e = (pd.to_datetime(master[master['Project']==sel_p].iloc[0]['Start_Date']), pd.to_datetime(master[master['Project']==sel_p].iloc[0]['End_Date'])+pd.Timedelta(days=1)) if not master.empty and sel_p in master['Project'].values else (df_proj['Start_Date'].min(), df_proj['End_Date'].max()+pd.Timedelta(days=1))
        
        plot_data = []
        plot_data.append({'Task': f"🏢 {sel_p}", 'Start': p_s, 'End': p_e, 'Type': 'P_Plan', 'Label': '', 'Width': 0.8, 'Color': '#E5E8E8', 'Pos': 'inside'})
        plot_data.append({'Task': f"🏢 {sel_p}", 'Start': p_s, 'End': p_s+((p_e-p_s)*(p_pct/100)), 'Type': 'P_Act', 'Label': f"{int(p_pct)}%", 'Width': 0.8, 'Color': '#2C3E50', 'Pos': 'inside'})
        
        for idx, mt in enumerate(df_proj['Main_Task'].unique()):
            df_mt = df_proj[df_proj['Main_Task'] == mt]; g_col = px.colors.qualitative.Prism[idx % 10]
            ms, me, mp = df_mt['Start_Date'].min(), df_mt['End_Date'].max()+pd.Timedelta(days=1), df_mt['Progress'].mean()
            plot_data.append({'Task': f"📑 {mt}", 'Start': ms, 'End': me, 'Type': f'M_P_{idx}', 'Label': '', 'Width': 0.55, 'Color': '#F2F3F4', 'Pos': 'outside'})
            plot_data.append({'Task': f"📑 {mt}", 'Start': ms, 'End': ms+((me-ms)*(mp/100)), 'Type': f'M_A_{idx}', 'Label': f"{int(mp)}%", 'Width': 0.55, 'Color': g_col, 'Pos': 'outside'})
            
            df_stk = df_mt.groupby(['Sub_Task', 'Dependency']).agg({'Start_Date':'min','End_Date':'max','Progress':'mean'}).reset_index().sort_values('Start_Date')
            for s_idx, srow in df_stk.iterrows():
                ss, se, sp = srow['Start_Date'], srow['End_Date']+pd.Timedelta(days=1), srow['Progress']
                st_lab = f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;└ {srow['Sub_Task']}" + (f" (รอ: {srow['Dependency']})" if srow['Dependency'] else "")
                plot_data.append({'Task': st_lab, 'Start': ss, 'End': se, 'Type': f'S_P_{idx}_{s_idx}', 'Label': '', 'Width': 0.35, 'Color': '#FDFEFE', 'Pos': 'outside'})
                plot_data.append({'Task': st_lab, 'Start': ss, 'End': ss+((se-ss)*(sp/100)), 'Type': f'S_A_{idx}_{s_idx}', 'Label': f"{int(sp)}%", 'Width': 0.35, 'Color': g_col, 'Pos': 'outside'})

        fig = px.timeline(pd.DataFrame(plot_data), x_start="Start", x_end="End", y="Task", color="Type", text="Label", height=len(plot_data)*28+150)
        for i, row in pd.DataFrame(plot_data).iterrows():
            f_col = "white" if row['Pos'] == 'inside' else "black"
            fig.update_traces(marker_color=row['Color'], selector={'name': row['Type']}, patch={"width": row['Width'], "textposition": row['Pos'], "textfont": {"size": 15, "family": "Arial Black", "color": f_col}})
        fig.update_yaxes(categoryorder="array", categoryarray=[r['Task'] for r in plot_data][::-1], tickfont=dict(size=16, family="Arial Black"), title="")
        fig.update_layout(showlegend=False, barmode='overlay', margin=dict(r=150, l=250))
        fig.add_vline(x=datetime.now().timestamp()*1000, line_dash="solid", line_color="red", line_width=2)
        st.plotly_chart(fig, use_container_width=True)

        # --- Popup อัปเดตงานแบบกลุ่ม (Sync ทั้งทีม) ---
        st.markdown("---"); st.subheader("📱 ระบบอัปเดตงานวันนี้ (Sync ทั้งทีม)")
        df_sum = df_proj.groupby(['Sub_Task', 'Main_Task']).agg({'Progress': 'mean'}).reset_index()
        ev = st.dataframe(df_sum, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        if ev.selection.rows:
            sel = df_sum.iloc[ev.selection.rows[0]]
            with st.container(border=True):
                st.markdown(f"### 📝 แก้ไข: {sel['Sub_Task']}")
                c1, c2 = st.columns(2); up_p = c1.slider("%", 0, 100, int(sel['Progress'])); up_i = c2.text_area("ปัญหา/สิ่งที่ทำ:")
                if st.button("🚀 บันทึกอัปเดตทั้งทีม", use_container_width=True, type="primary"):
                    m = (df_all['Project']==sel_p) & (df_all['Sub_Task']==sel['Sub_Task'])
                    df_all.loc[m, 'Progress'] = up_p
                    if up_i: df_all.loc[m, 'Issue'] = up_i
                    df_all.loc[m, 'Status'] = "✅ เสร็จสมบูรณ์" if up_p == 100 else "⏳ กำลังทำ"
                    if save_data(df_all): st.rerun()

# --- TAB 2: แก้ไข/ลบ ---
with tabs[2]:
    st.subheader("🛠️ แก้ไขข้อมูลดิบ (Admin)")
    df_raw = st.session_state.get('data', pd.DataFrame()).copy()
    if not df_raw.empty:
        df_raw.insert(0, "เลือก", False)
        edit = st.data_editor(df_raw, column_config={"เลือก": st.column_config.CheckboxColumn("ลบ?", default=False)}, hide_index=True, use_container_width=True)
        c1, c2 = st.columns(2)
        if c1.button("💾 บันทึกการแก้ไข", type="primary"):
            final = edit.drop(columns=["เลือก"])
            final.loc[final['Progress'] == 100, 'Status'] = "✅ เสร็จสมบูรณ์"
            if save_data(final): st.rerun()
        if c2.button("🗑️ ลบรายการที่เลือก"):
            rem = edit[edit["เลือก"] == False].drop(columns=["เลือก"])
            if save_data(rem): st.rerun()

# --- TAB 3 & 4: Ranking & Reports ---
with tabs[3]:
    st.subheader("🏆 Leaderboard"); ld = df_all.groupby('Employee')['Progress'].mean().reset_index().sort_values('Progress', ascending=False)
    if not ld.empty: st.plotly_chart(px.bar(ld, x='Employee', y='Progress', color='Progress'), use_container_width=True)
with tabs[4]:
    st.subheader("📑 รายงาน"); st.dataframe(df_all, use_container_width=True)
    st.download_button("📥 โหลด CSV", df_all.to_csv(index=False).encode('utf-8-sig'), f"AII_Report_{date.today()}.csv")