from xml.etree import ElementTree

from dtsx_generator import (
    build_dtsx_package,
    extract_database_connections,
    extract_sql_statements,
)


COBOL_SAMPLE = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LEGACYETL.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-CONN-SYB PIC X(80) VALUE
          'SERVER=SYB01;DATABASE=corebank;UID=etl_user;PWD=secret;Provider=Sybase.ASEOLEDBProvider;'.
       01 WS-CONN-MSS PIC X(80) VALUE
          'SERVER=SQL01;DATABASE=warehouse;Provider=MSOLEDBSQL;'.
       PROCEDURE DIVISION.
           EXEC SQL
               CONNECT TO SYBASE_DB
           END-EXEC.
           EXEC SQL
               SELECT CUST_ID, BALANCE
                 FROM CUSTOMER_BALANCE
           END-EXEC.
           EXEC SQL
               INSERT INTO dbo.customer_balance_stage (cust_id, balance)
               VALUES (:WS-CUST-ID, :WS-BALANCE)
           END-EXEC.
           GOBACK.
"""


def test_extract_database_connections_detects_sqlserver_and_sybase():
    connections = extract_database_connections(COBOL_SAMPLE)

    assert any(connection.database_type == "sybase" for connection in connections)
    assert any(connection.database_type == "sqlserver" for connection in connections)
    assert any(connection.role == "source" for connection in connections)
    assert any(connection.role == "destination" for connection in connections)


def test_extract_sql_statements_returns_exec_sql_blocks():
    statements = extract_sql_statements(COBOL_SAMPLE)

    assert len(statements) == 3
    assert any("SELECT CUST_ID, BALANCE FROM CUSTOMER_BALANCE" in statement for statement in statements)
    assert any("INSERT INTO dbo.customer_balance_stage" in statement for statement in statements)


def test_build_dtsx_package_returns_parseable_xml():
    package_xml = build_dtsx_package(COBOL_SAMPLE, "legacy_etl_package")
    root = ElementTree.fromstring(package_xml)

    namespace = {"DTS": "www.microsoft.com/SqlServer/Dts"}
    managers = root.findall(".//DTS:ConnectionManager", namespace)
    variables = root.findall(".//DTS:Variable", namespace)

    assert root.attrib["{www.microsoft.com/SqlServer/Dts}ObjectName"] == "legacy_etl_package"
    assert len(managers) >= 2
    assert len(variables) >= 2