import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import gspread

# ---------------------------------------------------------
# 1. CONFIGURATION & STYLING
# ---------------------------------------------------------
st.set_page_config(page_title="AII Project Tracker V17.5", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
        .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #dee2e6; }
        [data-testid="stMetricValue"] { font-size: 1.8rem; color: #ff4b4b; }
        .stTabs [data-baseweb="tab"] { font-weight: bold; font-size: 1.1rem; }
        p, th, td { font-size: 16px; font-weight: 500; }
    </style>
""", unsafe_allow_html=True)

st.title("🌌 AII Project Management System V17.5")

# ==========================================
# 2. DATA ENGINE (Ironclad Protection)
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
    sh = connect_gsheet()
    if not sh: return pd.DataFrame()
    try:
        ws_logs = sh.worksheet('Logs')
        data = ws_logs.get_all_records()
        
        # 11 คอลัมน์มาตรฐาน
        cols = ['Employee', 'Project', 'Main_Task', 'Sub_Task', 'Dependency', 'Start_Date', 'End_Date', 'Revised_End', 'Progress', 'Issue', 'Status']
        
        if not data:
            df = pd.DataFrame(columns=cols)
        else:
            df = pd.DataFrame(data)
            
        # ตรวจสอบและซ่อมแซมคอลัมน์ที่ขาด
        for col in cols:
            if col not in df.columns: df[col] = ""
            
        # Format วันที่และตัวเลข
        for col in ['Start_Date', 'End_Date', 'Revised_End']:
            df[col] = pd.to_datetime(df[col], errors='coerce')
        df['Progress'] = pd.to_numeric(df['Progress'], errors='coerce').fillna(0)
            
        st.session_state['data'] = df
        st.session_state['employees'] = sh.worksheet('Employees').col_values(1)[1:] # เว้นหัวตาราง
        st.session_state['projects_master'] = pd.DataFrame(sh.worksheet('Projects').get_all_records())
        
        # รวมรายชื่อโปรเจกต์ทั้งหมด
        p_m = st.session_state['projects_master']['Project'].dropna().unique().tolist() if not st.session_state['projects_master'].empty else []
        p_l = df['Project'].dropna().unique().tolist() if not df.empty else []
        st.session_state['projects_list'] = sorted(list(set(p_m + p_l)))
        
        return df
    except Exception as e:
        st.error(f"⚠️ Load Error: {e}")
        return pd.DataFrame()

# ฟังก์ชันเซฟสำหรับ Admin (ล้างแล้วเขียนใหม่แบบมี Safety Check)
def admin_safe_save(df_to_save):
    if df_to_save.empty:
        st.error("🛑 ระบบระงับการบันทึก: ตรวจพบว่าข้อมูลว่างเปล่า (ห้ามลบงานทั้งหมด)")
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
# 3. SIDEBAR (Full Management)
# ==========================================
with st.sidebar:
    st.header("⚙️ AII Control Panel")
    if st.button("🔄 Sync & Refresh Data", use_container_width=True):
        st.cache_data.clear(); load_data(); st.rerun()
    st.divider()
    
    with st.expander("👤 จัดการทีมงาน"):
        new_e = st.text_input("ชื่อเล่นพนักงาน", key="side_add_e")
        if st.button("➕ บันทึกพนักงาน"):
            if new_e:
                sh = connect_gsheet(); sh.worksheet('Employees').append_row([new_e])
                load_data(); st.rerun()
        st.write("---")
        if st.session_state.get('employees'):
            del_e = st.selectbox("เลือกคนที่จะลบ", st.session_state['employees'])
            if st.button("🗑️ ลบพนักงาน"):
                sh = connect_gsheet(); ws_e = sh.worksheet('Employees')
                all_n = ws_e.col_values(1)
                if del_e in all_n:
                    ws_e.delete_rows(all_n.index(del_e) + 1)
                    load_data(); st.rerun()

    with st.expander("📂 จัดการ Baseline โปรเจกต์"):
        with st.form("side_add_p"):
            np = st.text_input("ชื่อโปรเจกต์")
            c1, c2 = st.columns(2); ps = c1.date_input("เริ่ม"); pe = c2.date_input("จบ")
            if st.form_submit_button("➕ บันทึก Baseline"):
                if np:
                    sh = connect_gsheet(); sh.worksheet('Projects').append_row([np, ps.strftime('%Y-%m-%d'), pe.strftime('%Y-%m-%d')])
                    load_data(); st.rerun()

# ==========================================
# 4. MAIN INTERFACE
# ==========================================
tabs = st.tabs(["📝 ลงทะเบียนงาน", "📊 Gantt Chart", "🛠️ Admin (แก้ไข/ลบ)", "🏆 Leaderboard", "📑 รายงาน"])

# --- TAB 0: ลงทะเบียน (Append Mode - ปลอดภัย 100%) ---
with tabs[0]:
    st.subheader("📝 มอบหมายงานใหม่")
    p_list = st.session_state.get('projects_list', [])
    sel_p = st.selectbox("📁 1. เลือกโปรเจกต์", p_list, key="reg_p_v17_5")
    df_all = st.session_state.get('data', pd.DataFrame())
    
    # กรองงานรองเฉพาะของโปรเจกต์นี้
    f_mt = df_all[df_all['Project'] == sel_p]['Main_Task'].unique().tolist() if not df_all.empty else []

    with st.form("reg_work_form", clear_on_submit=True):
        mt_sel = st.selectbox("📑 2. เลือกงานรอง (Main Task)", ["-- สร้างใหม่ --"] + f_mt)
        mt_new = st.text_input("✨ หรือพิมพ์งานรองใหม่")
        final_mt = mt_new if mt_sel == "-- สร้างใหม่ --" else mt_sel
        
        stk = st.text_input("📌 3. ชื่องานย่อย (Sub-task)")
        
        f_stk = df_all[df_all['Project'] == sel_p]['Sub_Task'].unique().tolist() if not df_all.empty else []
        sel_dep = st.selectbox("🔗 4. งานย่อยที่ต้องรอ", ["-- เริ่มได้ทันที --"] + f_stk)
        
        ems = st.multiselect("👥 5. ผู้รับผิดชอบ", st.session_state.get('employees', []))
        c1, c2 = st.columns(2); ds, de = c1.date_input("วันเริ่ม"), c2.date_input("วันจบ")
        
        if st.form_submit_button("💾 บันทึกงาน (เพิ่มต่อท้าย)", use_container_width=True):
            if final_mt and stk and ems:
                sh = connect_gsheet(); ws_logs = sh.worksheet('Logs')
                # บันทึกแบบต่อท้าย (Append) ไม่ล้างชีตเดิม
                new_rows = [[e, sel_p, final_mt, stk, ("" if sel_dep == "-- เริ่มได้ทันที --" else sel_dep), ds.strftime('%Y-%m-%d'), de.strftime('%Y-%m-%d'), "", 0, "", "⏳ กำลังทำ"] for e in ems]
                ws_logs.append_rows(new_rows)
                st.success(f"บันทึกสำเร็จ! เพิ่มงานใหม่ {len(new_rows)} แถว")
                load_data(); st.rerun()

# --- TAB 1: Gantt Chart ---
with tabs[1]:
    df_g = st.session_state.get('data', pd.DataFrame())
    if not df_g.empty:
        today = datetime.now().date()
        sel_v = st.selectbox("📂 เลือกโปรเจกต์ดู Gantt:", p_list, key="gantt_p_v17_5")
        df_p = df_g[df_g['Project'] == sel_v].copy().sort_values('Start_Date')
        
        if not df_p.empty:
            df_p['Actual_End'] = df_p['Revised_End'].fillna(df_p['End_Date'])
            p_pct = df_p['Progress'].mean(); st.metric(f"🚀 {sel_v} Overall", f"{p_pct:.1f}%")
            
            # Baseline & Plotting Logic
            master = st.session_state.get('projects_master', pd.DataFrame())
            p_s, p_e = (pd.to_datetime(master[master['Project']==sel_v].iloc[0]['Start_Date']), pd.to_datetime(master[master['Project']==sel_v].iloc[0]['End_Date'])+pd.Timedelta(days=1)) if not master.empty and sel_v in master['Project'].values else (df_p['Start_Date'].min(), df_p['Actual_End'].max()+pd.Timedelta(days=1))
            
            plot_data = []
            plot_data.append({'Task': f"🏢 {sel_v}", 'Start': p_s, 'End': p_e, 'Type': 'P_Plan', 'Label': '', 'Width': 0.8, 'Color': '#D5D8DC'})
            plot_data.append({'Task': f"🏢 {sel_v}", 'Start': p_s, 'End': p_s+((p_e-p_s)*(p_pct/100)), 'Type': 'P_Act', 'Label': f"{int(p_pct)}%", 'Width': 0.8, 'Color': '#2C3E50'})
            
            for idx, mt in enumerate(df_p.groupby('Main_Task')['Start_Date'].min().sort_values().index):
                df_mt = df_p[df_p['Main_Task'] == mt]; g_col = px.colors.qualitative.Prism[idx % 10]
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

# --- TAB 2: Admin (Safe Edit) ---
with tabs[2]:
    st.subheader("🛠️ แก้ไข/ลบข้อมูลรวม")
    df_raw = st.session_state.get('data', pd.DataFrame()).copy()
    if not df_raw.empty:
        df_raw.insert(0, "ลบรายการ", False)
        edit = st.data_editor(df_raw, hide_index=True, use_container_width=True, column_config={"Revised_End": st.column_config.DateColumn("วันที่เลื่อนจบ")})
        c1, c2 = st.columns(2)
        if c1.button("💾 บันทึกการแก้ไข", type="primary", use_container_width=True):
            final = edit[edit["ลบรายการ"] == False].drop(columns=["ลบรายการ"])
            final.loc[final['Progress'] == 100, 'Status'] = "✅ เสร็จสมบูรณ์"
            if admin_safe_save(final): load_data(); st.rerun()
        if c2.button("🗑️ ยืนยันลบรายการที่เลือก", use_container_width=True):
            final_rem = edit[edit["ลบรายการ"] == False].drop(columns=["ลบรายการ"])
            if admin_safe_save(final_rem): load_data(); st.rerun()

# --- TAB 3 & 4: Rankings & Report ---
with tabs[3]:
    st.subheader("🏆 Leaderboard")
    if not df_all.empty:
        ld = df_all.groupby('Employee')['Progress'].mean().reset_index().sort_values('Progress', ascending=False)
        st.plotly_chart(px.bar(ld, x='Employee', y='Progress', color='Progress'), use_container_width=True)

with tabs[4]:
    st.subheader("📑 รายงานรวมทั้งหมด")
    st.dataframe(st.session_state.get('data', pd.DataFrame()), use_container_width=True)
    st.download_button("📥 โหลด CSV", st.session_state.get('data', pd.DataFrame()).to_csv(index=False).encode('utf-8-sig'), f"AII_Report_{date.today()}.csv")