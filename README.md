# REACTJS_FULL_STACK_CODE_GEN_TOOL


## Streamlit App

### Setup

pip install streamlit pandas
streamlit run app.py

### Features
- Upload any DB schema CSV (table_name, field_name, data_type, identity, len, dec, index, constraint)

- Select a table → generates FULL-STACK code

- FK fields auto-get ComboBox selects (populated from referenced tables)

- Client-side validation + server-side Bean Validation

- Spring Boot layered: Controller → Service → Repository → Entity

- @Transactional (BEGIN/COMMIT/ROLLBACK) on all write ops

- Download as ZIP

### CSV Format

| Column | Description |
|---|---|
| table_name | DB table name |
| field_name | Column name |
| data_type | SQL data type |
| identity | yes = PK auto-increment |
| len | Max length |
| dec | Decimal places |
| index | yes = indexed field |
| constraint | FOREIGN KEY (...) REFERENCES ...(...) |

### Generated Code Structure

#react/src/

  components/{Table}Form.jsx      # CRUD form with FK combos
  components/{Table}List.jsx      # Paginated list + search
  components/FkComboBox.jsx       # Reusable FK select
  services/{Table}Service.js      # Axios API layer
  utils/validators.js             # Client-side validation
  App.jsx                         # Root wiring

#springboot/src/

  controller/{Table}Controller.java   # REST endpoints
  service/{Table}Service.java         # BL interface
  service/impl/{Table}ServiceImpl.java # BL + @Transactional
  repository/{Table}Repository.java   # DAL (JPA)
  model/{Table}.java                  # Entity class
  dto/{Table}DTO.java                 # DTO + Bean Validation
  exception/GlobalExceptionHandler.java
  exception/ResourceNotFoundException.java
  exception/ValidationException.java
  resources/application.yml
