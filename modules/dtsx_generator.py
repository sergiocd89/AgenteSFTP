from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable
import uuid
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, register_namespace, tostring


DTS_NAMESPACE = "www.microsoft.com/SqlServer/Dts"
register_namespace("DTS", DTS_NAMESPACE)

SQL_SERVER_HINTS = (
    "SQL SERVER",
    "MSSQL",
    "SQLOLEDB",
    "MSOLEDBSQL",
    "ODBC DRIVER 17 FOR SQL SERVER",
)
SYBASE_HINTS = (
    "SYBASE",
    "ASEOLEDB",
    "ADAPTIVE SERVER",
    "ASE",
    "SYBOLEDB",
)
CONNECTION_STRING_PATTERN = re.compile(
    r"((?:SERVER|DATA SOURCE)\s*=\s*[^;\r\n]+;.*?(?:DATABASE|INITIAL CATALOG)\s*=\s*[^;\r\n;]+;?)",
    re.IGNORECASE,
)
CONNECT_TO_PATTERN = re.compile(r"EXEC\s+SQL\s+CONNECT\s+TO\s+([A-Z0-9_\-\.]+)", re.IGNORECASE)
USER_PATTERN = re.compile(r"(?:UID|USER ID|USER)\s*=\s*([^;\s]+)", re.IGNORECASE)
SERVER_PATTERN = re.compile(r"(?:SERVER|DATA SOURCE)\s*=\s*([^;\r\n]+)", re.IGNORECASE)
DATABASE_PATTERN = re.compile(r"(?:DATABASE|INITIAL CATALOG)\s*=\s*([^;\r\n]+)", re.IGNORECASE)
SQL_BLOCK_PATTERN = re.compile(r"EXEC\s+SQL(.*?)END-EXEC", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class DatabaseConnection:
    manager_name: str
    database_type: str
    server: str
    database: str
    provider: str
    role: str
    username: str = ""

    @property
    def connection_string(self) -> str:
        if self.database_type == "sqlserver":
            return (
                f"Data Source={self.server};"
                f"Initial Catalog={self.database};"
                "Provider=MSOLEDBSQL;"
                "Integrated Security=SSPI;"
            )

        user_id = self.username or "sybase_user"
        return (
            f"Data Source={self.server};"
            f"Initial Catalog={self.database};"
            "Provider=Sybase.ASEOLEDBProvider;"
            f"User ID={user_id};"
            "Password=${SYBASE_PASSWORD};"
        )


def infer_package_name(filename: str) -> str:
    stem = Path(filename).stem if filename else "legacy_package"
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", stem).strip("_") or "legacy_package"
    return f"{normalized}_ssis_package"


def extract_sql_statements(cobol_source: str) -> list[str]:
    statements: list[str] = []
    for match in SQL_BLOCK_PATTERN.finditer(cobol_source):
        statement = _normalize_space(match.group(1))
        if statement:
            statements.append(statement)
    return statements


def extract_database_connections(cobol_source: str) -> list[DatabaseConnection]:
    normalized_source = cobol_source.upper()
    raw_connections: list[DatabaseConnection] = []

    for index, raw_connection in enumerate(CONNECTION_STRING_PATTERN.findall(cobol_source), start=1):
        database_type = _detect_database_type(raw_connection)
        server = _extract_match(SERVER_PATTERN, raw_connection, f"legacy-host-{index}")
        database = _extract_match(DATABASE_PATTERN, raw_connection, f"legacy_db_{index}")
        user = _extract_match(USER_PATTERN, raw_connection, "")
        raw_connections.append(
            DatabaseConnection(
                manager_name=_build_manager_name(database_type, len(raw_connections) + 1),
                database_type=database_type,
                server=server,
                database=database,
                provider=_provider_for(database_type),
                role="auxiliary",
                username=user,
            )
        )

    for match in CONNECT_TO_PATTERN.findall(cobol_source):
        database_type = _detect_database_type(match)
        raw_connections.append(
            DatabaseConnection(
                manager_name=_build_manager_name(database_type, len(raw_connections) + 1),
                database_type=database_type,
                server=f"{database_type}-host",
                database=match.strip() or f"legacy_db_{len(raw_connections) + 1}",
                provider=_provider_for(database_type),
                role="auxiliary",
            )
        )

    if "SYBASE" in normalized_source and not any(conn.database_type == "sybase" for conn in raw_connections):
        raw_connections.append(
            DatabaseConnection(
                manager_name=_build_manager_name("sybase", len(raw_connections) + 1),
                database_type="sybase",
                server="sybase-host",
                database="sybase_db",
                provider=_provider_for("sybase"),
                role="auxiliary",
            )
        )

    if any(hint in normalized_source for hint in SQL_SERVER_HINTS) and not any(
        conn.database_type == "sqlserver" for conn in raw_connections
    ):
        raw_connections.append(
            DatabaseConnection(
                manager_name=_build_manager_name("sqlserver", len(raw_connections) + 1),
                database_type="sqlserver",
                server="sqlserver-host",
                database="sqlserver_db",
                provider=_provider_for("sqlserver"),
                role="auxiliary",
            )
        )

    deduplicated = _deduplicate_connections(raw_connections)
    return _assign_roles(deduplicated)


def summarize_connections(connections: Iterable[DatabaseConnection]) -> str:
    rows = ["Tipo | Rol | Manager | Servidor | Base", "--- | --- | --- | --- | ---"]
    for connection in connections:
        rows.append(
            f"{connection.database_type} | {connection.role} | {connection.manager_name} | "
            f"{connection.server} | {connection.database}"
        )
    return "\n".join(rows)


def build_dtsx_package(cobol_source: str, package_name: str, generation_notes: str = "") -> str:
    root = Element(
        _dts("Executable"),
        {
            _dts("ExecutableType"): "SSIS.Package.2",
            _dts("ObjectName"): package_name,
            _dts("Description"): "Paquete SSIS generado a partir de un componente COBOL.",
            _dts("DTSID"): _stable_guid(package_name),
        },
    )

    _append_property(root, "PackageFormatVersion", "8")
    _append_property(root, "VersionBuild", "1")
    _append_property(root, "VersionComments", "Generado por IBM i Legacy Agent Migrator")

    connections = extract_database_connections(cobol_source)
    statements = extract_sql_statements(cobol_source)

    connection_managers = SubElement(root, _dts("ConnectionManagers"))
    for connection in connections:
        manager = SubElement(
            connection_managers,
            _dts("ConnectionManager"),
            {
                _dts("ObjectName"): connection.manager_name,
                _dts("CreationName"): "OLEDB",
                _dts("DTSID"): _stable_guid(f"{package_name}:{connection.manager_name}"),
                _dts("Description"): (
                    f"Conexion {connection.role} para {connection.database_type} inferida desde el COBOL"
                ),
            },
        )
        object_data = SubElement(manager, _dts("ObjectData"))
        SubElement(
            object_data,
            _dts("ConnectionManager"),
            {
                _dts("ConnectionString"): connection.connection_string,
                _dts("Provider"): connection.provider,
            },
        )

    variables = SubElement(root, _dts("Variables"))
    for index, statement in enumerate(statements[:10], start=1):
        variable = SubElement(
            variables,
            _dts("Variable"),
            {
                _dts("ObjectName"): f"User::SQLBlock{index:02d}",
                _dts("Namespace"): "User",
                _dts("DataType"): "String",
            },
        )
        value = SubElement(variable, _dts("VariableValue"))
        value.text = statement

    if generation_notes:
        annotation = SubElement(root, _dts("Annotations"))
        note = SubElement(annotation, _dts("Annotation"), {_dts("Name"): "GenerationNotes"})
        note.text = generation_notes

    executables = SubElement(root, _dts("Executables"))
    sequence = SubElement(
        executables,
        _dts("Executable"),
        {
            _dts("ExecutableType"): "STOCK:SEQUENCE",
            _dts("ObjectName"): "Legacy Database Orchestration",
            _dts("DTSID"): _stable_guid(f"{package_name}:sequence"),
        },
    )
    sequence_executables = SubElement(sequence, _dts("Executables"))

    if statements:
        for index, statement in enumerate(statements[:5], start=1):
            task = SubElement(
                sequence_executables,
                _dts("Executable"),
                {
                    _dts("ExecutableType"): "STOCK:SQLTask",
                    _dts("ObjectName"): f"SQL Block {index:02d}",
                    _dts("DTSID"): _stable_guid(f"{package_name}:sqltask:{index}"),
                },
            )
            _append_property(task, "SqlStatementSource", statement)
            if connections:
                _append_property(task, "Connection", connections[0].manager_name)
    else:
        placeholder = SubElement(
            sequence_executables,
            _dts("Executable"),
            {
                _dts("ExecutableType"): "STOCK:SEQUENCE",
                _dts("ObjectName"): "Manual Mapping Required",
                _dts("DTSID"): _stable_guid(f"{package_name}:placeholder"),
            },
        )
        _append_property(
            placeholder,
            "Description",
            "No se detectaron bloques EXEC SQL. Completar manualmente las tareas de flujo de datos.",
        )

    xml_bytes = tostring(root, encoding="utf-8")
    pretty_xml = minidom.parseString(xml_bytes).toprettyxml(indent="  ", encoding="utf-8")
    return pretty_xml.decode("utf-8")


def _append_property(parent: Element, name: str, value: str) -> None:
    prop = SubElement(parent, _dts("Property"), {_dts("Name"): name})
    prop.text = value


def _assign_roles(connections: list[DatabaseConnection]) -> list[DatabaseConnection]:
    has_sybase = any(connection.database_type == "sybase" for connection in connections)
    has_sqlserver = any(connection.database_type == "sqlserver" for connection in connections)
    assigned: list[DatabaseConnection] = []

    for connection in connections:
        role = connection.role
        if has_sybase and has_sqlserver:
            if connection.database_type == "sybase" and not any(item.role == "source" for item in assigned):
                role = "source"
            elif connection.database_type == "sqlserver" and not any(item.role == "destination" for item in assigned):
                role = "destination"
        elif not assigned:
            role = "source"
        assigned.append(
            DatabaseConnection(
                manager_name=connection.manager_name,
                database_type=connection.database_type,
                server=connection.server,
                database=connection.database,
                provider=connection.provider,
                role=role,
                username=connection.username,
            )
        )

    return assigned


def _deduplicate_connections(connections: list[DatabaseConnection]) -> list[DatabaseConnection]:
    deduplicated: list[DatabaseConnection] = []
    seen: set[tuple[str, str, str]] = set()
    for connection in connections:
        key = (connection.database_type, connection.server.lower(), connection.database.lower())
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(connection)
    return deduplicated


def _build_manager_name(database_type: str, index: int) -> str:
    prefix = "CM_SQLServer" if database_type == "sqlserver" else "CM_Sybase"
    return f"{prefix}_{index:02d}"


def _detect_database_type(text: str) -> str:
    normalized = text.upper()
    if any(hint in normalized for hint in SYBASE_HINTS):
        return "sybase"
    return "sqlserver"


def _provider_for(database_type: str) -> str:
    return "MSOLEDBSQL" if database_type == "sqlserver" else "Sybase.ASEOLEDBProvider"


def _extract_match(pattern: re.Pattern[str], text: str, default_value: str) -> str:
    match = pattern.search(text)
    if not match:
        return default_value
    return match.group(1).strip().strip('"').strip("'")


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _stable_guid(seed: str) -> str:
    return "{" + str(uuid.uuid5(uuid.NAMESPACE_URL, seed)).upper() + "}"


def _dts(name: str) -> str:
    return f"{{{DTS_NAMESPACE}}}{name}"