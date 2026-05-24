"""
react_generator.py
Generates React JS files for a given table with FK combo-boxes,
validation, error trapping, and a clean layered service approach.
"""
from .schema_parser import to_pascal, to_camel


def generate_react_code(table_name: str, schema: dict) -> dict:
    tbl      = schema[table_name]
    pascal   = to_pascal(table_name)
    files    = {}

    files[f"components/{pascal}Form.jsx"]    = _form(table_name, tbl, schema)
    files[f"components/{pascal}List.jsx"]    = _list(table_name, tbl)
    files[f"components/FkComboBox.jsx"]      = _fk_combobox()
    files[f"services/{pascal}Service.js"]    = _service(table_name, tbl)
    files[f"utils/validators.js"]            = _validators(table_name, tbl)
    files[f"App.jsx"]                        = _app(table_name, pascal, tbl, schema)

    return files


# ── Form Component ─────────────────────────────────────────────────────────────
def _form(table_name, tbl, schema):
    pascal   = to_pascal(table_name)
    pk       = tbl["pk_field"] or "id"
    fk_map   = {fk["field"]: fk for fk in tbl["foreign_keys"]}

    # Build import for FK services
    fk_service_imports = ""
    for fk in tbl["foreign_keys"]:
        ref_pascal = to_pascal(fk["ref_table"])
        fk_service_imports += f'import {{ getAll{ref_pascal} }} from "../services/{ref_pascal}Service";\n'

    # Build FK state declarations
    fk_states = ""
    for fk in tbl["foreign_keys"]:
        ref_camel = to_camel(fk["ref_table"])
        fk_states += f'  const [{ref_camel}Options, set{to_pascal(fk["ref_table"])}Options] = useState([]);\n'

    # Build FK fetch effects
    fk_effects = ""
    for fk in tbl["foreign_keys"]:
        ref_pascal = to_pascal(fk["ref_table"])
        ref_camel  = to_camel(fk["ref_table"])
        fk_effects += f"""
  useEffect(() => {{
    getAll{ref_pascal}()
      .then(data => set{ref_pascal}Options(data))
      .catch(err => setErrors(prev => ({{ ...prev, {fk["field"]}: "Failed to load {fk["ref_table"]} options" }})));
  }}, []);
"""

    # Build initial form state
    init_fields = ""
    for f in tbl["fields"]:
        if f["is_pk"]:
            continue
        default = '""'
        if f["ts_type"] == "number":
            default = '""'
        init_fields += f'    {f["name"]}: {default},\n'

    # Build form fields JSX
    form_fields_jsx = ""
    for f in tbl["fields"]:
        if f["is_pk"]:
            continue
        label = f["name"].replace("_", " ").title()
        required_attr = "required" if f["required"] else ""

        if f["name"] in fk_map:
            fk         = fk_map[f["name"]]
            ref_table  = fk["ref_table"]
            ref_pascal = to_pascal(ref_table)
            ref_camel  = to_camel(ref_table)
            ref_field  = fk["ref_field"]
            # Try to pick a display field (first non-PK field)
            display_field = ref_field
            if ref_table in schema:
                for rf in schema[ref_table]["fields"]:
                    if not rf["is_pk"]:
                        display_field = rf["name"]
                        break

            form_fields_jsx += f"""
      {{/* FK ComboBox: {f["name"]} → {ref_table} */}}
      <div className="form-group">
        <label htmlFor="{f["name"]}">{label} <span className="required">*</span></label>
        <FkComboBox
          id="{f["name"]}"
          name="{f["name"]}"
          options={{{ref_camel}Options}}
          valueKey="{ref_field}"
          labelKey="{display_field}"
          value={{formData.{f["name"]}}}
          onChange={{handleChange}}
          placeholder="Select {label}..."
          error={{errors.{f["name"]}}}
        />
        {{errors.{f["name"]} && <span className="error-msg">{{errors.{f["name"]}}}</span>}}
      </div>
"""
        elif f["html_input"] == "datetime-local":
            form_fields_jsx += f"""
      <div className="form-group">
        <label htmlFor="{f["name"]}">{label}{' <span className="required">*</span>' if f["required"] else ''}</label>
        <input
          type="date"
          id="{f["name"]}"
          name="{f["name"]}"
          value={{formData.{f["name"]}}}
          onChange={{handleChange}}
          className={{errors.{f["name"]} ? "input-error" : ""}}
          {required_attr}
        />
        {{errors.{f["name"]} && <span className="error-msg">{{errors.{f["name"]}}}</span>}}
      </div>
"""
        else:
            max_len_attr = f'maxLength={{{f["max_len"]}}}' if f["max_len"] else ""
            step_attr = 'step="0.000001"' if f["decimals"] else ""
            form_fields_jsx += f"""
      <div className="form-group">
        <label htmlFor="{f["name"]}">{label}{' <span className="required">*</span>' if f["required"] else ''}</label>
        <input
          type="{f["html_input"]}"
          id="{f["name"]}"
          name="{f["name"]}"
          value={{formData.{f["name"]}}}
          onChange={{handleChange}}
          className={{errors.{f["name"]} ? "input-error" : ""}}
          {max_len_attr}
          {step_attr}
          {required_attr}
        />
        {{errors.{f["name"]} && <span className="error-msg">{{errors.{f["name"]}}}</span>}}
      </div>
"""

    return f"""// ============================================================
// {pascal}Form.jsx  –  Presentation Layer
// Auto-generated | React CRUD Form with FK ComboBoxes
// ============================================================
import React, {{ useState, useEffect }} from "react";
import FkComboBox from "./FkComboBox";
import {{ validate{pascal} }} from "../utils/validators";
import {{
  create{pascal},
  update{pascal},
  get{pascal}ById,
}} from "../services/{pascal}Service";
{fk_service_imports}
import "./Form.css";

/**
 * {pascal}Form
 * Props:
 *   recordId  – null for Create, id value for Edit
 *   onSuccess – callback after save
 *   onCancel  – callback for cancel button
 */
const {pascal}Form = ({{ recordId = null, onSuccess, onCancel }}) => {{
  const isEdit = recordId !== null;

  // ── State ───────────────────────────────────────────────
  const [formData, setFormData] = useState({{
{init_fields}  }});
  const [errors,   setErrors]   = useState({{}});
  const [apiError, setApiError] = useState(null);
  const [loading,  setLoading]  = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // FK option lists
{fk_states}

  // ── Load FK options ─────────────────────────────────────
{fk_effects}

  // ── Load record for edit ─────────────────────────────────
  useEffect(() => {{
    if (isEdit) {{
      setLoading(true);
      get{pascal}ById(recordId)
        .then(data => {{
          setFormData(data);
          setLoading(false);
        }})
        .catch(err => {{
          setApiError("Failed to load record: " + (err.message || "Unknown error"));
          setLoading(false);
        }});
    }}
  }}, [recordId]);

  // ── Handlers ────────────────────────────────────────────
  const handleChange = (e) => {{
    const {{ name, value, type, checked }} = e.target;
    setFormData(prev => ({{
      ...prev,
      [name]: type === "checkbox" ? checked : value
    }}));
    // Clear field error on change
    if (errors[name]) {{
      setErrors(prev => {{ const n = {{ ...prev }}; delete n[name]; return n; }});
    }}
  }};

  const handleSubmit = async (e) => {{
    e.preventDefault();
    setApiError(null);

    // Client-side validation
    const validationErrors = validate{pascal}(formData);
    if (Object.keys(validationErrors).length > 0) {{
      setErrors(validationErrors);
      return;
    }}

    setSubmitting(true);
    try {{
      if (isEdit) {{
        await update{pascal}(recordId, formData);
      }} else {{
        await create{pascal}(formData);
      }}
      if (onSuccess) onSuccess();
    }} catch (err) {{
      const msg = err.response?.data?.message || err.message || "Server error";
      setApiError(`Failed to save: ${{msg}}`);
    }} finally {{
      setSubmitting(false);
    }}
  }};

  const handleReset = () => {{
    setFormData({{
{init_fields}    }});
    setErrors({{}});
    setApiError(null);
  }};

  // ── Render ───────────────────────────────────────────────
  if (loading) return <div className="loading">Loading record…</div>;

  return (
    <div className="form-container">
      <h2 className="form-title">
        {{isEdit ? "✏️ Edit" : "➕ New"}} {label_from(table_name)}
      </h2>

      {{apiError && (
        <div className="alert alert-error" role="alert">
          <strong>Error:</strong> {{apiError}}
          <button className="alert-close" onClick={{() => setApiError(null)}}>✕</button>
        </div>
      )}}

      <form onSubmit={{handleSubmit}} noValidate>
{form_fields_jsx}
        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={{submitting}}>
            {{submitting ? "Saving…" : isEdit ? "💾 Update" : "✅ Create"}}
          </button>
          <button type="button" className="btn btn-secondary" onClick={{handleReset}} disabled={{submitting}}>
            🔄 Reset
          </button>
          {{onCancel && (
            <button type="button" className="btn btn-outline" onClick={{onCancel}} disabled={{submitting}}>
              ❌ Cancel
            </button>
          )}}
        </div>
      </form>
    </div>
  );
}};

export default {pascal}Form;
"""


def label_from(table_name):
    return table_name.replace("_", " ").title()


# ── List Component ──────────────────────────────────────────────────────────────
def _list(table_name, tbl):
    pascal = to_pascal(table_name)
    pk     = tbl["pk_field"] or "id"
    cols   = [f for f in tbl["fields"] if not f["is_pk"]]

    headers = "".join(f'          <th>{f["name"].replace("_", " ").title()}</th>\n' for f in cols)
    cells   = "".join(f'              <td>{{row.{f["name"]}}}</td>\n' for f in cols)

    return f"""// ============================================================
// {pascal}List.jsx  –  Presentation Layer (List/Table View)
// ============================================================
import React, {{ useState, useEffect, useCallback }} from "react";
import {{ getAll{pascal}, delete{pascal} }} from "../services/{pascal}Service";
import "./List.css";

const {pascal}List = ({{ onEdit, refreshToken }}) => {{
  const [records,  setRecords]  = useState([]);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);
  const [search,   setSearch]   = useState("");
  const [page,     setPage]     = useState(0);
  const [pageSize] = useState(10);
  const [deleting, setDeleting] = useState(null);

  const fetchData = useCallback(() => {{
    setLoading(true);
    setError(null);
    getAll{pascal}()
      .then(data => {{
        setRecords(data);
        setLoading(false);
      }})
      .catch(err => {{
        setError("Failed to load data: " + (err.message || "Unknown error"));
        setLoading(false);
      }});
  }}, []);

  useEffect(() => {{ fetchData(); }}, [fetchData, refreshToken]);

  const filtered = records.filter(r =>
    Object.values(r).some(v =>
      String(v).toLowerCase().includes(search.toLowerCase())
    )
  );

  const paged = filtered.slice(page * pageSize, (page + 1) * pageSize);
  const totalPages = Math.ceil(filtered.length / pageSize);

  const handleDelete = async (id) => {{
    if (!window.confirm("Are you sure you want to delete this record?")) return;
    setDeleting(id);
    try {{
      await delete{pascal}(id);
      setRecords(prev => prev.filter(r => r.{pk} !== id));
    }} catch (err) {{
      setError("Delete failed: " + (err.response?.data?.message || err.message));
    }} finally {{
      setDeleting(null);
    }}
  }};

  if (loading) return <div className="loading">⏳ Loading {table_name} records…</div>;

  return (
    <div className="list-container">
      <div className="list-header">
        <h2>{label_from(table_name)} Records</h2>
        <input
          type="search"
          placeholder="🔍 Search…"
          value={{search}}
          onChange={{e => {{ setSearch(e.target.value); setPage(0); }}}}
          className="search-input"
        />
      </div>

      {{error && <div className="alert alert-error">{{error}}</div>}}

      {{paged.length === 0 ? (
        <div className="empty-state">No records found.</div>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
{headers}                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {{paged.map((row, idx) => (
                <tr key={{row.{pk}}}>
                  <td>{{page * pageSize + idx + 1}}</td>
{cells}                  <td className="action-cell">
                    <button
                      className="btn btn-sm btn-edit"
                      onClick={{() => onEdit && onEdit(row.{pk})}}
                    >✏️ Edit</button>
                    <button
                      className="btn btn-sm btn-danger"
                      onClick={{() => handleDelete(row.{pk})}}
                      disabled={{deleting === row.{pk}}}
                    >{{deleting === row.{pk} ? "…" : "🗑️ Del"}}</button>
                  </td>
                </tr>
              ))}}
            </tbody>
          </table>
        </div>
      )}}

      {{totalPages > 1 && (
        <div className="pagination">
          <button onClick={{() => setPage(p => Math.max(0, p - 1))}} disabled={{page === 0}}>‹ Prev</button>
          <span>Page {{page + 1}} / {{totalPages}}</span>
          <button onClick={{() => setPage(p => Math.min(totalPages - 1, p + 1))}} disabled={{page >= totalPages - 1}}>Next ›</button>
        </div>
      )}}
    </div>
  );
}};

export default {pascal}List;
"""


# ── FK ComboBox Component ──────────────────────────────────────────────────────
def _fk_combobox():
    return """// ============================================================
// FkComboBox.jsx  –  Reusable Foreign Key Select Component
// ============================================================
import React from "react";

/**
 * FkComboBox – a styled <select> for Foreign Key fields.
 * Props:
 *   id, name     – HTML id/name
 *   options      – array of objects from the referenced table
 *   valueKey     – key field (FK value sent to server)
 *   labelKey     – display field shown in dropdown
 *   value        – current selected value
 *   onChange     – change handler (same signature as <input>)
 *   placeholder  – placeholder text (first disabled option)
 *   error        – validation error string
 */
const FkComboBox = ({
  id, name, options = [], valueKey, labelKey,
  value, onChange, placeholder = "Select…", error
}) => {
  return (
    <select
      id={id}
      name={name}
      value={value}
      onChange={onChange}
      className={`form-select ${error ? "input-error" : ""}`}
    >
      <option value="" disabled>
        {placeholder}
      </option>
      {options.map(opt => (
        <option key={opt[valueKey]} value={opt[valueKey]}>
          {opt[labelKey] ?? opt[valueKey]}
        </option>
      ))}
    </select>
  );
};

export default FkComboBox;
"""


# ── Service Layer ──────────────────────────────────────────────────────────────
def _service(table_name, tbl):
    pascal = to_pascal(table_name)
    pk     = tbl["pk_field"] or "id"
    endpoint = table_name.replace("_", "-")

    return f"""// ============================================================
// {pascal}Service.js  –  Service Layer (API calls via axios)
// ============================================================
import axios from "axios";

const BASE_URL = process.env.REACT_APP_API_BASE_URL || "http://localhost:8080/api";
const ENDPOINT = `${{BASE_URL}}/{endpoint}`;

// Axios instance with default config
const api = axios.create({{
  baseURL: BASE_URL,
  timeout: 10000,
  headers: {{ "Content-Type": "application/json" }},
}});

// Request interceptor (add auth token if needed)
api.interceptors.request.use(config => {{
  const token = localStorage.getItem("authToken");
  if (token) config.headers.Authorization = `Bearer ${{token}}`;
  return config;
}});

// Response interceptor (normalise errors)
api.interceptors.response.use(
  res => res,
  err => {{
    if (err.response?.status === 401) {{
      // Handle unauthorized
      console.error("Unauthorized – redirect to login");
    }}
    return Promise.reject(err);
  }}
);

// ── CRUD Operations ──────────────────────────────────────
export const getAll{pascal} = async () => {{
  const res = await api.get("/{endpoint}");
  return res.data;
}};

export const get{pascal}ById = async (id) => {{
  const res = await api.get(`/{endpoint}/${{id}}`);
  return res.data;
}};

export const create{pascal} = async (payload) => {{
  const res = await api.post("/{endpoint}", payload);
  return res.data;
}};

export const update{pascal} = async (id, payload) => {{
  const res = await api.put(`/{endpoint}/${{id}}`, payload);
  return res.data;
}};

export const delete{pascal} = async (id) => {{
  await api.delete(`/{endpoint}/${{id}}`);
}};

export default api;
"""


# ── Validators ─────────────────────────────────────────────────────────────────
def _validators(table_name, tbl):
    pascal = to_pascal(table_name)
    fk_fields = {fk["field"] for fk in tbl["foreign_keys"]}

    validations = ""
    for f in tbl["fields"]:
        if f["is_pk"]:
            continue
        field = f["name"]
        label = field.replace("_", " ").title()

        if field in fk_fields or f["required"]:
            validations += f"""
  // {label}
  if (!formData.{field} && formData.{field} !== 0) {{
    errors.{field} = "{label} is required.";
  }}"""

        if f["html_input"] == "text" and f["max_len"]:
            validations += f"""
  if (formData.{field} && formData.{field}.length > {f["max_len"]}) {{
    errors.{field} = "{label} must be at most {f["max_len"]} characters.";
  }}"""

        if f["ts_type"] == "number" and not f["is_pk"] and field not in fk_fields:
            validations += f"""
  if (formData.{field} !== "" && isNaN(Number(formData.{field}))) {{
    errors.{field} = "{label} must be a valid number.";
  }}"""

    return f"""// ============================================================
// validators.js  –  Client-side Validation Rules
// ============================================================

/**
 * validate{pascal}
 * Returns an object of {{ fieldName: "error message" }}
 * Empty object means validation passed.
 */
export const validate{pascal} = (formData) => {{
  const errors = {{}};
{validations}
  return errors;
}};

/**
 * Generic helpers
 */
export const isRequired  = v => v !== null && v !== undefined && String(v).trim() !== "";
export const isEmail     = v => /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(v);
export const isNumeric   = v => !isNaN(parseFloat(v)) && isFinite(v);
export const maxLength   = (v, n) => String(v).length <= n;
export const minLength   = (v, n) => String(v).length >= n;
"""


# ── App.jsx ───────────────────────────────────────────────────────────────────
def _app(table_name, pascal, tbl, schema):
    return f"""// ============================================================
// App.jsx  –  Application Root
// Wires together List + Form for {pascal}
// ============================================================
import React, {{ useState }} from "react";
import {pascal}Form from "./components/{pascal}Form";
import {pascal}List from "./components/{pascal}List";
import "./App.css";

function App() {{
  const [view,         setView]         = useState("list"); // "list" | "create" | "edit"
  const [editId,       setEditId]       = useState(null);
  const [refreshToken, setRefreshToken] = useState(0);

  const handleEdit = (id) => {{
    setEditId(id);
    setView("edit");
  }};

  const handleSuccess = () => {{
    setView("list");
    setRefreshToken(t => t + 1);
    setEditId(null);
  }};

  const handleCancel = () => {{
    setView("list");
    setEditId(null);
  }};

  return (
    <div className="app">
      <header className="app-header">
        <h1>📊 {label_from(table_name)} Management</h1>
        {{view === "list" && (
          <button className="btn btn-primary" onClick={{() => setView("create")}}>
            ➕ New {label_from(table_name)}
          </button>
        )}}
      </header>

      <main className="app-main">
        {{view === "list" && (
          <{pascal}List onEdit={{handleEdit}} refreshToken={{refreshToken}} />
        )}}
        {{(view === "create" || view === "edit") && (
          <{pascal}Form
            recordId={{view === "edit" ? editId : null}}
            onSuccess={{handleSuccess}}
            onCancel={{handleCancel}}
          />
        )}}
      </main>
    </div>
  );
}}

export default App;
"""
