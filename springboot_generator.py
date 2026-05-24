"""
springboot_generator.py
Generates Spring Boot Java code with full layered architecture:
  - Entity (model)
  - DTO
  - Repository (DAL)
  - Service (BL) with @Transactional
  - Controller (REST)
  - GlobalExceptionHandler
  - application.yml
"""
from .schema_parser import to_pascal, to_camel


def generate_springboot_code(table_name: str, schema: dict) -> dict:
    tbl    = schema[table_name]
    pascal = to_pascal(table_name)
    files  = {}

    files[f"model/{pascal}.java"]                           = _entity(table_name, tbl)
    files[f"dto/{pascal}DTO.java"]                          = _dto(table_name, tbl)
    files[f"repository/{pascal}Repository.java"]            = _repository(table_name, tbl)
    files[f"service/{pascal}Service.java"]                  = _service_interface(table_name, tbl)
    files[f"service/impl/{pascal}ServiceImpl.java"]         = _service_impl(table_name, tbl, schema)
    files[f"controller/{pascal}Controller.java"]            = _controller(table_name, tbl)
    files[f"exception/GlobalExceptionHandler.java"]        = _exception_handler()
    files[f"exception/ResourceNotFoundException.java"]     = _resource_not_found()
    files[f"exception/ValidationException.java"]           = _validation_exception()
    files[f"resources/application.yml"]                    = _app_yml(table_name)

    return files


PKG = "com.example.app"


# ── Entity ─────────────────────────────────────────────────────────────────────
def _entity(table_name, tbl):
    pascal  = to_pascal(table_name)
    pk      = tbl["pk_field"] or "id"
    fk_set  = {fk["field"] for fk in tbl["foreign_keys"]}

    imports = set([
        "jakarta.persistence.*",
        "lombok.Data",
        "lombok.NoArgsConstructor",
        "lombok.AllArgsConstructor",
        "lombok.Builder",
    ])
    for f in tbl["fields"]:
        if f["java_type"] in ("BigDecimal",):
            imports.add("java.math.BigDecimal")
        if f["java_type"] in ("LocalDateTime", "LocalDate"):
            imports.add("java.time.LocalDateTime")

    import_block = "\n".join(f"import {i};" for i in sorted(imports))

    fields_java = ""
    for f in tbl["fields"]:
        col_ann = ""
        if f["is_pk"]:
            col_ann = "  @Id\n  @GeneratedValue(strategy = GenerationType.IDENTITY)\n"
        elif f["name"] in fk_set:
            col_ann = f'  @Column(name = "{f["name"]}", nullable = false)\n'
        else:
            nullable = "" if f["required"] else ", nullable = true"
            length   = f', length = {f["max_len"]}' if f["max_len"] else ""
            col_ann  = f'  @Column(name = "{f["name"]}"{length}{nullable})\n'

        fields_java += f"{col_ann}  private {f['java_type']} {to_camel(f['name'])};\n\n"

    return f"""// ============================================================
// {pascal}.java  –  Model / Entity Layer
// Table: {table_name}
// ============================================================
package {PKG}.model;

{import_block}

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
@Entity
@Table(name = "{table_name}")
public class {pascal} {{

{fields_java}}}
"""


# ── DTO ────────────────────────────────────────────────────────────────────────
def _dto(table_name, tbl):
    pascal = to_pascal(table_name)

    imports = set([
        "lombok.Data",
        "lombok.NoArgsConstructor",
        "lombok.AllArgsConstructor",
        "lombok.Builder",
        "jakarta.validation.constraints.NotNull",
        "jakarta.validation.constraints.NotBlank",
        "jakarta.validation.constraints.Size",
        "jakarta.validation.constraints.Positive",
    ])
    for f in tbl["fields"]:
        if f["java_type"] == "BigDecimal":
            imports.add("java.math.BigDecimal")
        if f["java_type"] in ("LocalDateTime",):
            imports.add("java.time.LocalDateTime")

    import_block = "\n".join(f"import {i};" for i in sorted(imports))

    fk_set  = {fk["field"] for fk in tbl["foreign_keys"]}
    fields_java = ""
    for f in tbl["fields"]:
        annotations = ""
        if f["is_pk"]:
            annotations = "  // PK – auto-generated; omit on create\n"
        elif f["required"] or f["name"] in fk_set:
            if f["java_type"] == "String":
                annotations = '  @NotBlank(message = "' + f["name"].replace("_", " ").title() + ' is required")\n'
                if f["max_len"]:
                    annotations += f'  @Size(max = {f["max_len"]}, message = "Max {f["max_len"]} chars")\n'
            else:
                annotations = '  @NotNull(message = "' + f["name"].replace("_", " ").title() + ' is required")\n'
        elif f["ts_type"] == "number":
            annotations = "  @Positive\n"

        fields_java += f"{annotations}  private {f['java_type']} {to_camel(f['name'])};\n\n"

    return f"""// ============================================================
// {pascal}DTO.java  –  Data Transfer Object
// ============================================================
package {PKG}.dto;

{import_block}

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class {pascal}DTO {{

{fields_java}}}
"""


# ── Repository ─────────────────────────────────────────────────────────────────
def _repository(table_name, tbl):
    pascal    = to_pascal(table_name)
    pk_java   = "Long" if tbl["pk_field"] else "Long"

    custom_queries = ""
    for fk in tbl["foreign_keys"]:
        ref_field  = to_camel(fk["field"])
        ref_pascal = to_pascal(fk["field"])
        custom_queries += f"""
  // Find all {table_name} by FK: {fk["field"]}
  java.util.List<{pascal}> findBy{ref_pascal}(Integer {ref_field});
"""

    return f"""// ============================================================
// {pascal}Repository.java  –  Data Access Layer (JPA Repository)
// ============================================================
package {PKG}.repository;

import {PKG}.model.{pascal};
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import java.util.List;
import java.util.Optional;

@Repository
public interface {pascal}Repository extends JpaRepository<{pascal}, {pk_java}> {{

  // ── Custom finders ─────────────────────────────────
{custom_queries}

  // ── Search by keyword (JPQL example) ───────────────
  @Query("SELECT e FROM {pascal} e WHERE " +
         "CAST(e.{to_camel(tbl["pk_field"] or "id")} AS string) LIKE %:kw% " +
         "ORDER BY e.{to_camel(tbl["pk_field"] or "id")} DESC")
  List<{pascal}> search(@Param("kw") String keyword);
}}
"""


# ── Service Interface ──────────────────────────────────────────────────────────
def _service_interface(table_name, tbl):
    pascal  = to_pascal(table_name)
    pk_java = "Long"

    return f"""// ============================================================
// {pascal}Service.java  –  Business Logic Layer (Interface)
// ============================================================
package {PKG}.service;

import {PKG}.dto.{pascal}DTO;
import java.util.List;

public interface {pascal}Service {{

  List<{pascal}DTO> findAll();

  {pascal}DTO findById({pk_java} id);

  {pascal}DTO create({pascal}DTO dto);

  {pascal}DTO update({pk_java} id, {pascal}DTO dto);

  void delete({pk_java} id);
}}
"""


# ── Service Impl ───────────────────────────────────────────────────────────────
def _service_impl(table_name, tbl, schema):
    pascal   = to_pascal(table_name)
    camel    = to_camel(table_name)
    pk_field = to_camel(tbl["pk_field"] or "id")
    fk_set   = {fk["field"] for fk in tbl["foreign_keys"]}

    # Build mapping from entity → dto
    to_dto_lines = "\n".join(
        f"      .{to_camel(f['name'])}(e.get{to_pascal(f['name'])}())"
        for f in tbl["fields"]
    )
    # Build mapping from dto → entity
    to_entity_lines = "\n".join(
        f"      .{to_camel(f['name'])}(dto.get{to_pascal(f['name'])}())"
        for f in tbl["fields"] if not f["is_pk"]
    )

    return f"""// ============================================================
// {pascal}ServiceImpl.java  –  Business Logic Layer (Implementation)
// Uses @Transactional for BEGIN / COMMIT / ROLLBACK
// ============================================================
package {PKG}.service.impl;

import {PKG}.dto.{pascal}DTO;
import {PKG}.exception.ResourceNotFoundException;
import {PKG}.exception.ValidationException;
import {PKG}.model.{pascal};
import {PKG}.repository.{pascal}Repository;
import {PKG}.service.{pascal}Service;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.annotation.Propagation;
import java.util.List;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class {pascal}ServiceImpl implements {pascal}Service {{

  private final {pascal}Repository repository;

  // ── READ ALL ──────────────────────────────────────────────
  @Override
  @Transactional(readOnly = true)
  public List<{pascal}DTO> findAll() {{
    log.info("Fetching all {table_name} records");
    return repository.findAll()
        .stream()
        .map(this::toDTO)
        .collect(Collectors.toList());
  }}

  // ── READ ONE ─────────────────────────────────────────────
  @Override
  @Transactional(readOnly = true)
  public {pascal}DTO findById(Long id) {{
    log.info("Fetching {table_name} with id={{}}", id);
    {pascal} entity = repository.findById(id)
        .orElseThrow(() -> new ResourceNotFoundException(
            "{pascal}", "id", id));
    return toDTO(entity);
  }}

  // ── CREATE (BEGIN → business logic → COMMIT / ROLLBACK on error)
  @Override
  @Transactional(propagation = Propagation.REQUIRED,
                 rollbackFor  = Exception.class)
  public {pascal}DTO create({pascal}DTO dto) {{
    log.info("Creating {table_name}: {{}}", dto);
    validateDTO(dto);
    {pascal} entity = toEntity(dto);
    {pascal} saved  = repository.save(entity);   // commit happens on method exit
    log.info("{table_name} created with id={{}}", saved.get{to_pascal(tbl["pk_field"] or "id")}());
    return toDTO(saved);
  }}

  // ── UPDATE ────────────────────────────────────────────────
  @Override
  @Transactional(propagation = Propagation.REQUIRED,
                 rollbackFor  = Exception.class)
  public {pascal}DTO update(Long id, {pascal}DTO dto) {{
    log.info("Updating {table_name} id={{}}", id);
    {pascal} existing = repository.findById(id)
        .orElseThrow(() -> new ResourceNotFoundException("{pascal}", "id", id));
    validateDTO(dto);
    mergeFields(existing, dto);
    {pascal} saved = repository.save(existing);
    log.info("{table_name} updated id={{}}", saved.get{to_pascal(tbl["pk_field"] or "id")}());
    return toDTO(saved);
  }}

  // ── DELETE ────────────────────────────────────────────────
  @Override
  @Transactional(propagation = Propagation.REQUIRED,
                 rollbackFor  = Exception.class)
  public void delete(Long id) {{
    log.info("Deleting {table_name} id={{}}", id);
    if (!repository.existsById(id)) {{
      throw new ResourceNotFoundException("{pascal}", "id", id);
    }}
    repository.deleteById(id);
    log.info("{table_name} id={{}} deleted", id);
  }}

  // ── Private helpers ───────────────────────────────────────

  private void validateDTO({pascal}DTO dto) {{
    if (dto == null) throw new ValidationException("{pascal} payload cannot be null");
    // Add custom business rules here
  }}

  private {pascal} toEntity({pascal}DTO dto) {{
    return {pascal}.builder()
{to_entity_lines}
      .build();
  }}

  private {pascal}DTO toDTO({pascal} e) {{
    return {pascal}DTO.builder()
{to_dto_lines}
      .build();
  }}

  private void mergeFields({pascal} e, {pascal}DTO dto) {{
{chr(10).join(
    f"    e.set{to_pascal(f['name'])}(dto.get{to_pascal(f['name'])}());"
    for f in tbl["fields"] if not f["is_pk"]
)}
  }}
}}
"""


# ── Controller ────────────────────────────────────────────────────────────────
def _controller(table_name, tbl):
    pascal   = to_pascal(table_name)
    camel    = to_camel(table_name)
    endpoint = table_name.replace("_", "-")

    return f"""// ============================================================
// {pascal}Controller.java  –  Presentation / REST Layer
// ============================================================
package {PKG}.controller;

import {PKG}.dto.{pascal}DTO;
import {PKG}.service.{pascal}Service;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@Slf4j
@RestController
@RequestMapping("/api/{endpoint}")
@CrossOrigin(origins = "*")   // adjust for production
@RequiredArgsConstructor
public class {pascal}Controller {{

  private final {pascal}Service service;

  /** GET /api/{endpoint} – list all */
  @GetMapping
  public ResponseEntity<List<{pascal}DTO>> getAll() {{
    log.debug("GET /api/{endpoint}");
    return ResponseEntity.ok(service.findAll());
  }}

  /** GET /api/{endpoint}/{{id}} – get one */
  @GetMapping("/{{id}}")
  public ResponseEntity<{pascal}DTO> getById(@PathVariable Long id) {{
    log.debug("GET /api/{endpoint}/{{}}", id);
    return ResponseEntity.ok(service.findById(id));
  }}

  /** POST /api/{endpoint} – create */
  @PostMapping
  public ResponseEntity<{pascal}DTO> create(@Valid @RequestBody {pascal}DTO dto) {{
    log.debug("POST /api/{endpoint}: {{}}", dto);
    {pascal}DTO created = service.create(dto);
    return ResponseEntity.status(HttpStatus.CREATED).body(created);
  }}

  /** PUT /api/{endpoint}/{{id}} – update */
  @PutMapping("/{{id}}")
  public ResponseEntity<{pascal}DTO> update(
      @PathVariable Long id,
      @Valid @RequestBody {pascal}DTO dto) {{
    log.debug("PUT /api/{endpoint}/{{}}: {{}}", id, dto);
    return ResponseEntity.ok(service.update(id, dto));
  }}

  /** DELETE /api/{endpoint}/{{id}} – delete */
  @DeleteMapping("/{{id}}")
  public ResponseEntity<Void> delete(@PathVariable Long id) {{
    log.debug("DELETE /api/{endpoint}/{{}}", id);
    service.delete(id);
    return ResponseEntity.noContent().build();
  }}
}}
"""


# ── Exception Handler ─────────────────────────────────────────────────────────
def _exception_handler():
    return f"""// ============================================================
// GlobalExceptionHandler.java  –  Centralised Error Trapping
// ============================================================
package {PKG}.exception;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

@RestControllerAdvice
public class GlobalExceptionHandler {{

  // ── 404 Resource Not Found ───────────────────────────────
  @ExceptionHandler(ResourceNotFoundException.class)
  public ResponseEntity<ErrorResponse> handleNotFound(ResourceNotFoundException ex) {{
    return ResponseEntity.status(HttpStatus.NOT_FOUND)
        .body(new ErrorResponse(HttpStatus.NOT_FOUND.value(), ex.getMessage()));
  }}

  // ── 400 Validation (Bean Validation) ────────────────────
  @ExceptionHandler(MethodArgumentNotValidException.class)
  public ResponseEntity<Map<String, Object>> handleValidation(
      MethodArgumentNotValidException ex) {{
    Map<String, String> fieldErrors = new HashMap<>();
    for (FieldError fe : ex.getBindingResult().getFieldErrors()) {{
      fieldErrors.put(fe.getField(), fe.getDefaultMessage());
    }}
    Map<String, Object> body = new HashMap<>();
    body.put("status",    400);
    body.put("message",   "Validation failed");
    body.put("errors",    fieldErrors);
    body.put("timestamp", LocalDateTime.now().toString());
    return ResponseEntity.badRequest().body(body);
  }}

  // ── 400 Business Validation ──────────────────────────────
  @ExceptionHandler(ValidationException.class)
  public ResponseEntity<ErrorResponse> handleBusiness(ValidationException ex) {{
    return ResponseEntity.badRequest()
        .body(new ErrorResponse(400, ex.getMessage()));
  }}

  // ── 500 Generic ──────────────────────────────────────────
  @ExceptionHandler(Exception.class)
  public ResponseEntity<ErrorResponse> handleGeneric(Exception ex) {{
    return ResponseEntity.internalServerError()
        .body(new ErrorResponse(500, "Internal server error: " + ex.getMessage()));
  }}

  // ── ErrorResponse record ─────────────────────────────────
  public record ErrorResponse(int status, String message) {{
    public String timestamp() {{ return LocalDateTime.now().toString(); }}
  }}
}}
"""


def _resource_not_found():
    return f"""package {PKG}.exception;

public class ResourceNotFoundException extends RuntimeException {{
  public ResourceNotFoundException(String resource, String field, Object value) {{
    super(resource + " not found with " + field + " = '" + value + "'");
  }}
}}
"""


def _validation_exception():
    return f"""package {PKG}.exception;

public class ValidationException extends RuntimeException {{
  public ValidationException(String message) {{
    super(message);
  }}
}}
"""


# ── application.yml ────────────────────────────────────────────────────────────
def _app_yml(table_name):
    return f"""# ============================================================
# application.yml  –  Spring Boot Configuration
# ============================================================
server:
  port: 8080

spring:
  application:
    name: {table_name}-service

  datasource:
    url: jdbc:sqlserver://localhost:1433;databaseName=your_db;encrypt=true;trustServerCertificate=true
    username: ${{DB_USERNAME:sa}}
    password: ${{DB_PASSWORD:yourPassword}}
    driver-class-name: com.microsoft.sqlserver.jdbc.SQLServerDriver

  jpa:
    hibernate:
      ddl-auto: validate          # never auto-alter schema in prod
    show-sql: true
    properties:
      hibernate:
        format_sql: true
        dialect: org.hibernate.dialect.SQLServerDialect

  transaction:
    default-timeout: 30           # seconds

logging:
  level:
    com.example.app: DEBUG
    org.springframework.transaction: TRACE  # shows BEGIN/COMMIT/ROLLBACK
    org.hibernate.SQL: DEBUG

management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics
"""
