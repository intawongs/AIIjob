import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import gspread

# ---------------------------------------------------------
# 1. CONFIGURATION & STYLING
# ---------------------------------------------------------
st.set_page_config(page_title="AII Project Tracker V17.2", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
        .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #dee2e6; }
        [data-testid="stMetricValue"] { font-size: 1.8rem; color: #ff4b4b; }
        .stTabs [data-baseweb="tab"] { font-weight: bold; font-size: 1.1rem; }
        p, th, td { font-size: 16px; font-weight: 500; }
        .late-box { background-color: #fff2f2; border: 1px solid #ff4b4b; padding: 10px; border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

st.title("🌌 AII Project Management System V17.2")

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
    expected_logs = ['Employee', 'Project', 'Main_Task', 'Sub_Task', 'Dependency', 'Start_Date', 'End_Date', 'Revised_End', 'Progress', 'Issue', 'Status']
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs'); ws_emps = sh.worksheet('Employees'); ws_projs = sh.worksheet('Projects')
            df_logs = pd.DataFrame(ws_logs.get_all_records())
            df_projs = pd.DataFrame(ws_projs.get_all_records())
            df_emps = pd.DataFrame(ws_emps.get_all_records())
            
            for col in expected_logs:
                if col not in df_logs.columns: df_logs[col] = "" 
            
            if not df_logs.empty:
                df_logs['Start_Date'] = pd.to_datetime(df_logs['Start_Date'], errors='coerce')
                df_logs['End_Date'] = pd.to_datetime(df_logs['End_Date'], errors='coerce')
                df_logs['Revised_End'] = pd.to_datetime(df_logs['Revised_End'], errors='coerce')
                df_logs['Progress'] = pd.to_numeric(df_logs['Progress'], errors='coerce').fillna(0)
            
            st.session_state['data'] = df_logs
            st.session_state['employees'] = df_emps['Name'].tolist() if not df_emps.empty else []
            st.session_state['projects_master'] = df_projs
            
            p_master = df_projs['Project'].dropna().unique().tolist() if not df_projs.empty else []
            p_logs = df_logs['Project'].dropna().unique().tolist() if not df_logs.empty else []
            st.session_state['projects_list'] = sorted(list(set(p_master + p_logs)))
            return df_logs
        except Exception as e:
            st.error(f"Load Error: {e}"); return pd.DataFrame(columns=expected_logs)
    return pd.DataFrame()

def save_data(df_to_save):
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            save_df = df_to_save.copy().fillna("")
            # จัดการวันที่ให้เป็น String ก่อนเซฟ (Safe Save)
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
# 3. SIDEBAR (Full Management)
# ==========================================
with st.sidebar:
    st.header("⚙️ AII Control Panel")
    if st.button("🔄 Sync & Refresh", use_container_width=True):
        st.cache_data.clear(); load_data(); st.rerun()
    st.divider()
    
    with st.expander("👤 รายชื่อทีมงาน (เพิ่ม/ลบ)"):
        n_emp = st.text_input("เพิ่มชื่อเล่นพนักงาน", key="add_e")
        if st.button("➕ บันทึกพนักงาน", use_container_width=True):
            if n_emp:
                sh = connect_gsheet(); sh.worksheet('Employees').append_row([n_emp])
                st.success(f"เพิ่ม {n_emp} แล้ว"); load_data(); st.rerun()
        st.write("---")
        if st.session_state.get('employees'):
            del_emp = st.selectbox("เลือกคนที่จะลบ", st.session_state['employees'], key="del_e")
            if st.button("🗑️ ยืนยันลบพนักงาน", use_container_width=True, type="secondary"):
                sh = connect_gsheet(); ws_e = sh.worksheet('Employees')
                names = ws_e.col_values(1)
                if del_emp in names:
                    ws_e.delete_rows(names.index(del_emp) + 1)
                    st.warning(f"ลบ {del_emp} แล้ว"); load_data(); st.rerun()

    with st.expander("📂 Baseline โปรเจกต์ (เพิ่ม/ลบ)"):
        n_p = st.text_input("ชื่อโปรเจกต์ Baseline")
        c1, c2 = st.columns(2); ps = c1.date_input("เริ่ม"); pe = c2.date_input("จบ")
        if st.button("➕ บันทึก Baseline", use_container_width=True):
            if n_p:
                sh = connect_gsheet(); sh.worksheet('Projects').append_row([n_p, ps.strftime('%Y-%m-%d'), pe.strftime('%Y-%m-%d')])
                st.success(f"บันทึก {n_p} แล้ว"); load_data(); st.rerun()
        st.write("---")
        m_projs = st.session_state.get('projects_master', pd.DataFrame())
        if not m_projs.empty:
            del_p = st.selectbox("เลือกโปรเจกต์ที่จะลบ", m_projs['Project'].tolist(), key="del_p")
            if st.button("🗑️ ยืนยันลบ Baseline", use_container_width=True, type="secondary"):
                sh = connect_gsheet(); ws_p = sh.worksheet('Projects')
                projs = ws_p.col_values(1)
                if del_p in projs:
                    ws_p.delete_rows(projs.index(del_p) + 1)
                    st.warning(f"ลบ {del_p} แล้ว"); load_data(); st.rerun()

# ==========================================
# 4. MAIN INTERFACE
# ==========================================
tabs = st.tabs(["📝 ลงทะเบียน", "📊 แผนผังงาน (Gantt)", "🛠️ แก้ไข/ลบข้อมูล", "🏆 อันดับผลงาน", "📑 รายงาน"])

# --- TAB 0: ลงทะเบียน (Dependent Dropdown) ---
with tabs[0]:
    st.subheader("📝 มอบหมายงานใหม่")
    df_curr = st.session_state.get('data', pd.DataFrame())
    p_list = st.session_state.get('projects_list', [])
    sel_p_reg = st.selectbox("📁 1. เลือกโปรเจกต์", p_list, key="reg_p_v17_2")
    
    # กรอง Main Task เฉพาะโปรเจกต์นั้น
    filtered_mt = df_curr[df_curr['Project'] == sel_p_reg]['Main_Task'].unique().tolist() if not df_curr.empty else []
    
    with st.form("reg_form_v17_2", clear_on_submit=True):
        sel_mt = st.selectbox("📑 2. เลือกงานรอง", ["-- สร้างงานรองใหม่ --"] + filtered_mt)
        new_mt = st.text_input("✨ หรือพิมพ์ชื่อเฟสใหม่")
        final_mt = new_mt if sel_mt == "-- สร้างงานรองใหม่ --" else sel_mt
        stk = st.text_input("📌 3. ชื่องานย่อย (Sub-task)")
        
        # กรอง Dependency
        filtered_stk = df_curr[df_curr['Project'] == sel_p_reg]['Sub_Task'].unique().tolist() if not df_curr.empty else []
        sel_dep = st.selectbox("🔗 4. งานย่อยที่ต้องรอ", ["-- เริ่มได้ทันที --"] + filtered_stk)
        
        ems = st.multiselect("👥 5. ผู้รับผิดชอบ", st.session_state.get('employees', []))
        c1, c2 = st.columns(2); ds, de = c1.date_input("วันเริ่ม"), c2.date_input("วันจบ")
        
        if st.form_submit_button("💾 บันทึกงาน", use_container_width=True):
            if final_mt and stk and ems:
                latest = st.session_state['data']
                new_rows = [{'Employee': e, 'Project': sel_p_reg, 'Main_Task': final_mt, 'Sub_Task': stk, 'Dependency': ("" if sel_dep == "-- เริ่มได้ทันที --" else sel_dep), 'Start_Date': pd.to_datetime(ds), 'End_Date': pd.to_datetime(de), 'Progress': 0, 'Status': '⏳ กำลังทำ'} for e in ems]
                updated = pd.concat([latest, pd.DataFrame(new_rows)], ignore_index=True)
                if save_data(updated): st.success("บันทึกสำเร็จ!"); load_data(); st.rerun()

# --- TAB 1: Gantt Chart (Validate Start/End Logic) ---
with tabs[1]:
    df_all = st.session_state.get('data', pd.DataFrame())
    if not df_all.empty:
        today = datetime.now().date()
        # 🔥 ใช้ Revised_End ถ้ามี ถ้าไม่มีใช้ End_Date (Safe Calc)
        df_all['Actual_End'] = df_all['Revised_End'].fillna(df_all['End_Date'])
        
        # กรองงานค้าง (Grouped)
        df_valid = df_all.dropna(subset=['Actual_End'])
        df_grouped = df_valid.groupby(['Project', 'Main_Task', 'Sub_Task', 'Actual_End']).agg({'Employee': lambda x: ', '.join(x.unique()), 'Progress': 'mean'}).reset_index()
        late_tasks = df_grouped[(df_grouped['Progress'] < 100) & (df_grouped['Actual_End'].dt.date < today)].copy()
        
        if not late_tasks.empty:
            st.error(f"🚩 งานเลยกำหนดส่ง {len(late_tasks)} งาน (ตรวจสอบวันที่เลื่อนแล้ว)")
            with st.expander("🔍 ดูรายละเอียดงานค้าง"):
                late_tasks['Days_Late'] = late_tasks['Actual_End'].apply(lambda x: (today - x.date()).days)
                st.dataframe(late_tasks[['Employee', 'Project', 'Sub_Task', 'Actual_End', 'Days_Late', 'Progress']].style.highlight_max(subset=['Days_Late'], color='#ffcccc'), use_container_width=True, hide_index=True)

        sel_p = st.selectbox("📂 ดูภาพรวมโปรเจกต์:", st.session_state.get('projects_list', []), key="view_v17_2")
        df_proj = df_all[df_all['Project'] == sel_p].copy().sort_values('Start_Date')
        
        if not df_proj.empty:
            p_pct = df_proj['Progress'].mean(); st.metric(f"🚀 {sel_p} Progress", f"{p_pct:.1f}%")
            
            # Baseline Check
            master = st.session_state.get('projects_master', pd.DataFrame())
            if not master.empty and sel_p in master['Project'].values:
                p_info = master[master['Project'] == sel_p].iloc[0]
                p_s, p_e = pd.to_datetime(p_info['Start_Date']), pd.to_datetime(p_info['End_Date']) + pd.Timedelta(days=1)
            else:
                p_s, p_e = df_proj['Start_Date'].min(), df_proj['Actual_End'].max() + pd.Timedelta(days=1)
            
            # Plotting Logic (Layered)
            plot_data = []
            plot_data.append({'Task': f"🏢 {sel_p}", 'Start': p_s, 'End': p_e, 'Type': 'P_Plan', 'Label': '', 'Width': 0.8, 'Color': '#D5D8DC', 'Pos': 'inside'})
            plot_data.append({'Task': f"🏢 {sel_p}", 'Start': p_s, 'End': p_s+((p_e-p_s)*(p_pct/100)), 'Type': 'P_Act', 'Label': f"{int(p_pct)}%", 'Width': 0.8, 'Color': '#2C3E50', 'Pos': 'inside'})
            
            main_tasks = df_proj.groupby('Main_Task')['Start_Date'].min().sort_values().index
            colors = px.colors.qualitative.Prism
            for idx, mt in enumerate(main_tasks):
                df_mt = df_proj[df_proj['Main_Task'] == mt]; g_col = colors[idx % len(colors)]
                ms, me, mp = df_mt['Start_Date'].min(), df_mt['Actual_End'].max()+pd.Timedelta(days=1), df_mt['Progress'].mean()
                plot_data.append({'Task': f"📑 {mt}", 'Start': ms, 'End': me, 'Type': f'M_P_{idx}', 'Label': '', 'Width': 0.55, 'Color': '#E5E8E8', 'Pos': 'outside'})
                plot_data.append({'Task': f"📑 {mt}", 'Start': ms, 'End': ms+((me-ms)*(mp/100)), 'Type': f'M_A_{idx}', 'Label': f"{int(mp)}%", 'Width': 0.55, 'Color': g_col, 'Pos': 'outside'})
                
                df_stk = df_mt.groupby(['Sub_Task', 'Dependency']).agg({'Start_Date':'min','Actual_End':'max','Progress':'mean'}).reset_index().sort_values('Start_Date')
                for s_idx, srow in df_stk.iterrows():
                    ss, se, sp = srow['Start_Date'], srow['Actual_End']+pd.Timedelta(days=1), srow['Progress']
                    st_lab = f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;└ {srow['Sub_Task']}" + (f" (รอ: {srow['Dependency']})" if srow['Dependency'] else "")
                    plot_data.append({'Task': st_lab, 'Start': ss, 'End': se, 'Type': f'S_P_{idx}_{s_idx}', 'Label': '', 'Width': 0.35, 'Color': '#EBEDEF', 'Pos': 'outside'})
                    plot_data.append({'Task': st_lab, 'Start': ss, 'End': ss+((se-ss)*(sp/100)), 'Type': f'S_A_{idx}_{s_idx}', 'Label': f"{int(sp)}%", 'Width': 0.35, 'Color': g_col, 'Pos': 'outside'})

            fig = px.timeline(pd.DataFrame(plot_data), x_start="Start", x_end="End", y="Task", color="Type", text="Label", height=len(plot_data)*28+150)
            fig.update_yaxes(categoryorder="array", categoryarray=[r['Task'] for r in plot_data][::-1], tickfont=dict(size=16, family="Arial Black"), title="")
            fig.update_layout(showlegend=False, barmode='overlay', margin=dict(r=150, l=250))
            fig.add_vline(x=datetime.now().timestamp()*1000, line_dash="solid", line_color="red", line_width=2)
            st.plotly_chart(fig, use_container_width=True)

            # Popup อัปเดตงานแบบกลุ่ม
            st.markdown("---"); st.subheader("📱 ระบบอัปเดตงานวันนี้ (Sync ทั้งทีม)")
            df_sum = df_proj.groupby(['Sub_Task', 'Main_Task']).agg({'Progress': 'mean'}).reset_index().sort_values('Sub_Task')
            ev = st.dataframe(df_sum, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
            if ev.selection.rows:
                sel = df_sum.iloc[ev.selection.rows[0]]
                with st.container(border=True):
                    st.markdown(f"### 📝 อัปเดตงาน: **{sel['Sub_Task']}**")
                    c1, c2 = st.columns(2); up_p = c1.slider("%", 0, 100, int(sel['Progress'])); up_i = c2.text_area("ปัญหา:")
                    if st.button("🚀 บันทึกและ Sync ทั้งทีม", use_container_width=True, type="primary"):
                        m = (df_all['Project']==sel_p) & (df_all['Sub_Task']==sel['Sub_Task'])
                        df_all.loc[m, 'Progress'] = up_p
                        if up_i: df_all.loc[m, 'Issue'] = up_i
                        df_all.loc[m, 'Status'] = "✅ เสร็จสมบูรณ์" if up_p == 100 else "⏳ กำลังทำ"
                        if save_data(df_all): load_data(); st.rerun()

# --- TAB 2: แก้ไข/ลบ (Safe CRUD) ---
with tabs[2]:
    st.subheader("🛠️ แก้ไขข้อมูลดิบ (Admin)")
    df_raw = st.session_state.get('data', pd.DataFrame()).copy()
    if not df_raw.empty:
        df_raw.insert(0, "เลือก", False)
        edit = st.data_editor(df_raw, column_config={"เลือก": st.column_config.CheckboxColumn("ลบ?", default=False), "Revised_End": st.column_config.DateColumn("วันที่เลื่อนจบ")}, hide_index=True, use_container_width=True)
        c1, c2 = st.columns(2)
        if c1.button("💾 บันทึกการแก้ไข", type="primary", use_container_width=True):
            final = edit[edit["เลือก"] == False].drop(columns=["เลือก"])
            final.loc[final['Progress'] == 100, 'Status'] = "✅ เสร็จสมบูรณ์"
            if save_data(final): st.success("อัปเดตแล้ว!"); load_data(); st.rerun()
        if c2.button("🗑️ ยืนยันลบรายการที่เลือก", use_container_width=True):
            rem = edit[edit["เลือก"] == False].drop(columns=["เลือก"])
            if save_data(rem): st.warning("ลบรายการแล้ว!"); load_data(); st.rerun()

# --- TAB 3 & 4 (Ranking & Report) ---
with tabs[3]:
    st.subheader("🏆 Leaderboard")
    if not df_all.empty:
        ld = df_all.groupby('Employee')['Progress'].mean().reset_index().sort_values('Progress', ascending=False)
        st.plotly_chart(px.bar(ld, x='Employee', y='Progress', color='Progress'), use_container_width=True)
with tabs[4]:
    st.subheader("📑 รายงานภาพรวม"); st.dataframe(st.session_state.get('data', pd.DataFrame()), use_container_width=True)
    st.download_button("📥 โหลด CSV", st.session_state.get('data', pd.DataFrame()).to_csv(index=False).encode('utf-8-sig'), f"Report_{date.today()}.csv")