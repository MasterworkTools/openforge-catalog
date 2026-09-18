import operator
import os
from abc import ABC, abstractmethod
from importlib import import_module

from psycopg import connection, cursor, sql


class SchemaBase(ABC):
    def __init__(self, conn: connection):
        self.conn = conn

    def up(self) -> bool:
        with self.conn.cursor() as curs:
            if not self.version_exists(curs):
                print(f"Upgrading schema version {self.version}")
                self.up_impl(curs)
                self.insert_version(curs)
                self.report_success(True)
                return True
            else:
                print(f"Schema version {self.version} already exists")
                return True

    @abstractmethod
    def up_impl(self, curs: cursor): ...

    def down(self, ver: int) -> bool:
        with self.conn.cursor() as curs:
            if self.version >= ver:
                if self.version_exists(curs):
                    print(f"Downgrading schema version {self.version}")
                    self.down_impl(curs)
                    self.delete_version(curs)
                    self.report_success(False)
                return True
        return False

    @abstractmethod
    def down_impl(self, curs: cursor): ...

    def version_exists(self, curs: cursor) -> bool:
        query = sql.SQL(
            "SELECT version FROM schema_versions WHERE version = {version}"
        ).format(version=sql.Literal(self.version))
        curs.execute(query)
        result = curs.fetchone()
        if result is not None:
            return True
        else:
            return False

    def report_success(self, up: bool):
        if up:
            print(f"Schema upgraded to version {self.version}")
        else:
            print(f"Schema downgraded from version {self.version}")

    def insert_version(self, curs: cursor):
        query = sql.SQL(
            """
INSERT INTO schema_versions
  (version, created_at)
VALUES ({version}, NOW())
"""
        ).format(version=sql.Literal(self.version))
        curs.execute(query)

    def delete_version(self, curs: cursor):
        query = sql.SQL(
            """
DELETE FROM schema_versions
  WHERE version = {version}
"""
        ).format(version=sql.Literal(self.version))
        curs.execute(query)


SCHEMA_VERSIONS = []


class SchemaVersionDecorator:
    def __init__(self, version: int):
        self.version = version

    def __call__(self, cls):
        SCHEMA_VERSIONS.append((self.version, cls))
        setattr(cls, "version", self.version)
        return cls


def get_schema_versions():
    for module in os.listdir(os.path.dirname(__file__)):
        if module == "__init__.py" or module[-3:] != ".py":
            continue
        import_module(f".{module[:-3]}", __name__)
    SCHEMA_VERSIONS.sort(key=operator.itemgetter(0))
    return [m[1] for m in SCHEMA_VERSIONS]


def get_current_schema_version(curs: cursor):
    query = sql.SQL(
        """
SELECT version
  FROM schema_versions
  ORDER BY version DESC
  LIMIT 1
"""
    )
    curs.execute(query)
    return curs.fetchone()[0]
