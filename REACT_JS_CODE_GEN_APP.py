import streamlit as st
import pandas as pd
import io
import zipfile
import json
from generators.schema_parser import parse_schema
from generators.react_generator import generate_react_code
from generators.springboot_generator import generate_springboot_code


def _to_pascal(s):
    return "".join(w.capitalize() for w in s.split("_"))

st.set_page_config(
    page_title="React + Spring Boot Code Generator",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
        text-align: center;
    }
    .main-header h1 { font-size: 2.2rem; margin: 0; }
    .main-header p { opacity: 0.8; margin-top: 0.5rem; }
    .section-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1.2rem;
        margin-bottom: 1rem;
    }
    .table-badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 600;
        margin: 0.2rem;
    }
    .badge-master { background: #dbeafe; color: #1e40af; }
    .badge-transaction { background: #dcfce7; color: #166534; }
    .fk-info {
        background: #fef3c7;
        border-left: 4px solid #f59e0b;
        padding: 0.5rem 0.8rem;
        border-radius: 0 6px 6px 0;
        font-size: 0.85rem;
        margin: 0.3rem 0;
    }
    .code-tab { font-size: 0.9rem; }
    .download-btn { margin-top: 1rem; }
    .stTabs [data-baseweb="tab"] { font-size: 0.9rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>⚙️ React JS + Spring Boot Code Generator</h1>
    <p>Upload your database schema CSV → Select a table → Auto-generate full-stack code with FK relationships</p>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("📁 Schema Input")
    upload_mode = st.radio("Source", ["Upload CSV", "Use Sample Schema"])

    schema_df = None

    if upload_mode == "Upload CSV":
        uploaded = st.file_uploader("Upload Schema CSV", type=["csv"])
        if uploaded:
            try:
                schema_df = pd.read_csv(uploaded)
                st.success(f"✅ Loaded {len(schema_df)} rows")
            except Exception as e:
                st.error(f"Error reading CSV: {e}")
    else:
        # load bundled sample
        try:
            schema_df = pd.read_csv("/mnt/user-data/uploads/reactjs_codegen.csv")
            st.info("Using uploaded sample schema (reactjs_codegen.csv)")
        except Exception:
            st.warning("Sample not found — please upload a CSV.")

    st.markdown("---")
    st.markdown("### 📋 CSV Format Required")
    st.markdown("""
    | Column | Description |
    |---|---|
    | `table_name` | DB table name |
    | `field_name` | Column name |
    | `data_type` | SQL type |
    | `identity` | `yes` = PK auto |
    | `len` | Max length |
    | `dec` | Decimals |
    | `index` | `yes` = indexed |
    | `constraint` | FK definition |
    """)

# ── Main ──────────────────────────────────────────────────────────────────────
if schema_df is None:
    st.info("👈 Upload a schema CSV or choose **Use Sample Schema** from the sidebar to get started.")
    st.stop()

# Validate columns
required_cols = {"table_name", "field_name", "data_type"}
missing = required_cols - set(schema_df.columns.str.lower())
if missing:
    st.error(f"CSV is missing required columns: {missing}")
    st.stop()

schema_df.columns = schema_df.columns.str.lower().str.strip()

# ── Parse schema ──────────────────────────────────────────────────────────────
schema = parse_schema(schema_df)

tables = list(schema.keys())
master_tables = [t for t in tables if t.startswith("mas_")]
trn_tables    = [t for t in tables if t.startswith("trn_")]
other_tables  = [t for t in tables if t not in master_tables + trn_tables]

# ── Schema overview ───────────────────────────────────────────────────────────
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("📊 Schema Overview")
    cats = []
    if master_tables:
        cats.append(("Master Tables", master_tables, "badge-master"))
    if trn_tables:
        cats.append(("Transaction Tables", trn_tables, "badge-transaction"))
    if other_tables:
        cats.append(("Other Tables", other_tables, "badge-master"))

    for cat_name, tbl_list, badge_cls in cats:
        st.markdown(f"**{cat_name}**")
        badges = " ".join(
            f'<span class="table-badge {badge_cls}">{t}</span>' for t in tbl_list
        )
        st.markdown(badges, unsafe_allow_html=True)

    st.markdown("---")
    total_fks = sum(len(v["foreign_keys"]) for v in schema.values())
    c1, c2, c3 = st.columns(3)
    c1.metric("Tables", len(tables))
    c2.metric("Fields", len(schema_df))
    c3.metric("FK Links", total_fks)

with col_right:
    st.subheader("🗂️ Select Table to Generate Code")
    selected_table = st.selectbox(
        "Choose a table",
        tables,
        format_func=lambda t: f"{'🔵' if t.startswith('mas_') else '🟢'} {t}"
    )

    if selected_table:
        tbl = schema[selected_table]
        st.markdown(f"**Fields in `{selected_table}`:**")
        field_rows = []
        for f in tbl["fields"]:
            fk_ref = ""
            for fk in tbl["foreign_keys"]:
                if fk["field"] == f["name"]:
                    fk_ref = f"→ {fk['ref_table']}.{fk['ref_field']}"
            field_rows.append({
                "Field": f["name"],
                "Type": f["data_type"],
                "PK": "✅" if f["is_pk"] else "",
                "FK": fk_ref,
                "Nullable": "" if f["required"] else "nullable"
            })
        st.dataframe(pd.DataFrame(field_rows), use_container_width=True, hide_index=True)

        if tbl["foreign_keys"]:
            st.markdown("**Foreign Key Relationships:**")
            for fk in tbl["foreign_keys"]:
                st.markdown(
                    f'<div class="fk-info">🔗 <code>{fk["field"]}</code> → '
                    f'<code>{fk["ref_table"]}.{fk["ref_field"]}</code> '
                    f'<em>(combo-box auto-populated from {fk["ref_table"]})</em></div>',
                    unsafe_allow_html=True
                )

# ── Code Generation ────────────────────────────────────────────────────────────
st.markdown("---")

gen_col1, gen_col2 = st.columns([2, 1])
with gen_col1:
    st.subheader(f"🚀 Generate Code for `{selected_table}`")
with gen_col2:
    generate_btn = st.button("⚡ Generate Full-Stack Code", type="primary", use_container_width=True)

if generate_btn or "generated" in st.session_state:
    if generate_btn:
        with st.spinner("Generating React + Spring Boot code..."):
            react_files   = generate_react_code(selected_table, schema)
            spring_files  = generate_springboot_code(selected_table, schema)
            st.session_state["generated"] = {
                "table": selected_table,
                "react": react_files,
                "spring": spring_files
            }
        st.success(f"✅ Code generated for `{selected_table}`!")

    gen = st.session_state["generated"]

    # Only show if same table
    if gen["table"] == selected_table:
        react_files  = gen["react"]
        spring_files = gen["spring"]

        tab_react, tab_spring, tab_download = st.tabs([
            "⚛️ React JS Code", "☕ Spring Boot Code", "📦 Download"
        ])

        with tab_react:
            for fname, code in react_files.items():
                with st.expander(f"📄 `{fname}`", expanded=(fname.endswith("Form.jsx"))):
                    st.code(code, language="jsx" if fname.endswith(".jsx") else "javascript")

        with tab_spring:
            for fname, code in spring_files.items():
                lang = "java"
                if fname.endswith(".xml"):  lang = "xml"
                if fname.endswith(".yml"):  lang = "yaml"
                if fname.endswith(".properties"): lang = "properties"
                with st.expander(f"📄 `{fname}`", expanded=(fname.endswith("Controller.java"))):
                    st.code(code, language=lang)

        with tab_download:
            st.markdown("### 📦 Download Generated Code")
            st.markdown("Download all generated files as a ZIP archive:")

            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for fname, code in react_files.items():
                    zf.writestr(f"react/src/{fname}", code)
                for fname, code in spring_files.items():
                    zf.writestr(f"springboot/src/{fname}", code)

                # Write a README
                readme = f"""# Generated Code for table: {selected_table}

## React JS (frontend)
- Component: {selected_table} CRUD form with FK combo-boxes
- Location: react/src/

## Spring Boot (backend)
- REST API with layered architecture
- Location: springboot/src/

## Architecture
### React
- components/       UI components (Form, List, ComboBox)
- services/         API service layer (axios)
- utils/            Validators & helpers
- types/            TypeScript-style prop definitions

### Spring Boot
- controller/       REST Controllers (@RestController)
- service/          Business Logic Layer
- repository/       Data Access Layer (JPA)
- model/            Entity classes
- dto/              Data Transfer Objects
- exception/        Custom exceptions & global handler

## Transaction Support
All write operations (create/update/delete) use:
  @Transactional with rollback on RuntimeException

Generated by React + Spring Boot Code Generator
"""
                zf.writestr("README.md", readme)

            zip_buf.seek(0)
            st.download_button(
                label=f"⬇️ Download {selected_table}_fullstack_code.zip",
                data=zip_buf.getvalue(),
                file_name=f"{selected_table}_fullstack_code.zip",
                mime="application/zip",
                use_container_width=True,
                type="primary"
            )

            st.markdown("---")
            st.markdown("### 📁 File Structure")
            file_tree = f"""
```
{selected_table}_fullstack_code.zip
├── README.md
├── react/src/
│   ├── components/
│   │   ├── {_to_pascal(selected_table)}Form.jsx
│   │   ├── {_to_pascal(selected_table)}List.jsx
│   │   └── FkComboBox.jsx
│   ├── services/
│   │   └── {_to_pascal(selected_table)}Service.js
│   ├── utils/
│   │   └── validators.js
│   └── App.jsx
└── springboot/src/
    ├── controller/
    │   └── {_to_pascal(selected_table)}Controller.java
    ├── service/
    │   └── {_to_pascal(selected_table)}Service.java
    ├── repository/
    │   └── {_to_pascal(selected_table)}Repository.java
    ├── model/
    │   └── {_to_pascal(selected_table)}.java
    ├── dto/
    │   └── {_to_pascal(selected_table)}DTO.java
    ├── exception/
    │   └── GlobalExceptionHandler.java
    └── resources/
        └── application.yml
```
"""
            st.markdown(file_tree)
    else:
        st.info("Table selection changed. Click **Generate** again for the new table.")
