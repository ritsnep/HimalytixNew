# filepath: c:\PythonProjects\ERPCURSOR\Himalytix\ERP\components\core\tests\test_metadata_loader.py
from ..metadata_loader import get_entity_schema

def test_schema_loading(monkeypatch):
    class DummyCursor:
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): pass
        def execute(self, sql, params): pass
        @property
        def description(self): return [('FieldName',), ('DataType',)]
        def fetchall(self): return [('account_code', 'varchar'), ('ExternalCode', 'varchar')]
    monkeypatch.setattr('django.db.connection.cursor', lambda: DummyCursor())
    fields = get_entity_schema('ChartOfAccounts')
    assert any(f['FieldName'] == 'ExternalCode' for f in fields)
