"""Regression coverage without accessing the production database."""
import pytest
from app.database import _PostgresConnection

class FakeCursor:
    rowcount = 1
    def __init__(self, row=None): self.row = row
    def fetchone(self): return self.row

class TransactionModel:
    """Model PostgreSQL's aborted transaction after undefined lastval()."""
    def __init__(self, generated_id=None):
        self.aborted = False
        self.generated_id = generated_id
    def execute(self, sql, params=()):
        if sql.startswith('ROLLBACK TO SAVEPOINT'):
            self.aborted = False
            return FakeCursor()
        if self.aborted:
            raise RuntimeError('current transaction is aborted')
        if sql == 'SELECT lastval()':
            if self.generated_id is None:
                self.aborted = True
                raise RuntimeError('lastval is not yet defined in this session')
            return FakeCursor((self.generated_id,))
        return FakeCursor()


def test_insert_without_sequence_does_not_abort_branding_transaction():
    con = _PostgresConnection(TransactionModel())
    cur = con.execute('INSERT INTO business_branding (tenant_id) VALUES (?)', (11,))
    assert cur.lastrowid is None
    con.execute('UPDATE business_branding SET display_name=? WHERE tenant_id=?', ('Mi negocio', 11))


def test_generated_identifiers_still_work():
    con = _PostgresConnection(TransactionModel(42))
    assert con.execute('INSERT INTO tenants (name) VALUES (?)', ('Test',)).lastrowid == 42


def test_branding_first_save_update_and_public_read(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('SUPABASE_DB_URL', raising=False)
    monkeypatch.setenv('NEGROSKY_DB_PATH', str(tmp_path / 'test.db'))
    from app import main
    from app.database import init_db, connection
    from app.schemas import BrandingInput
    init_db()
    with connection() as con:
        con.execute("INSERT INTO tenants (id,name,slug) VALUES (901,'Prueba','prueba-diseno')")
        con.execute("INSERT INTO tenants (id,name,slug) VALUES (902,'Otro','otro-diseno')")
    # No authenticated production account is involved in this isolated test.
    monkeypatch.setattr(main, 'audit', lambda *args, **kwargs: None)
    user = {'id': 1, 'role': 'super_admin'}
    first = BrandingInput(display_name='Diseño uno', primary_color='#123456',
        module_widths_mobile='contact:100:1,profile:50:7,campaigns:50:1,rewards:100:1,appointments:100:1')
    main.update_branding(first, 901, user)
    assert main.get_branding(901, user)['primary_color'] == '#123456'
    second = first.model_copy(update={'primary_color': '#abcdef', 'card_opacity': 70})
    main.update_branding(second, 901, user)
    public = main.public_branding('prueba-diseno')
    assert public['primary_color'] == '#abcdef'
    assert public['card_opacity'] == 70
    assert public['module_widths_mobile'] == first.module_widths_mobile
    assert main.get_branding(902, user)['primary_color'] != '#abcdef'
