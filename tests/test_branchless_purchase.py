from datetime import datetime,timedelta,timezone
import pytest
from fastapi import HTTPException
from app import main
from app.database import connection,init_db
from app.schemas import ValidateOperationInput

@pytest.fixture
def user(tmp_path,monkeypatch):
    monkeypatch.delenv('DATABASE_URL',raising=False)
    monkeypatch.delenv('SUPABASE_DB_URL',raising=False)
    monkeypatch.setenv('NEGROSKY_DB_PATH',str(tmp_path/'test.db'))
    init_db()
    with connection() as c:
        c.execute("INSERT INTO tenants(id,name,slug) VALUES(1,'Test','test'),(2,'Otro','otro')")
        c.execute("INSERT INTO users(id,tenant_id,name,email,password_hash,role) VALUES(1,1,'Operador','test@local','x','branch_admin')")
        c.execute("INSERT INTO customers(id,tenant_id,name,phone) VALUES(1,1,'Cliente','123')")
        c.execute("INSERT INTO loyalty_programs(id,tenant_id,name,target_purchases,reward_name) VALUES(1,1,'Club',2,'Premio')")
        c.execute("INSERT INTO loyalty_cards(tenant_id,customer_id,program_id) VALUES(1,1,1)")
        c.execute("INSERT INTO branches(id,tenant_id,name) VALUES(1,1,'Sucursal')")
        for code,branch,tenant in [('111111',None,1),('222222',None,1),('333333',1,1),('444444',None,2)]:
            c.execute("INSERT INTO operation_tokens(tenant_id,customer_id,program_id,operation_type,branch_id,code,expires_at) VALUES(?,?,1,'purchase',?,?,?)",(tenant,1,branch,code,(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()))
    return {'id':1,'tenant_id':1,'branch_id':None,'name':'Operador','role':'branch_admin'}

def test_purchase_reward_history(user):
    assert main.validate_purchase(ValidateOperationInput(code='111111'),user)['progress']==1
    result=main.validate_purchase(ValidateOperationInput(code='222222'),user)
    assert result['reward'] and result['progress']==0
    assert len(main.customer_history({'id':1,'tenant_id':1,'origin_branch_id':None})['purchases'])==2
    with connection() as c:
        assert c.execute('SELECT branch_id FROM purchases').fetchone()[0] is None
        assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
        c.execute("INSERT INTO operation_tokens(tenant_id,customer_id,program_id,operation_type,reference_id,code,expires_at) VALUES(1,1,1,'reward',?,'555555',?)",(result['reward']['id'],(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()))
    assert main.validate_reward(ValidateOperationInput(code='555555'),user)['status']=='used'
    with pytest.raises(HTTPException) as e: main.validate_purchase(ValidateOperationInput(code='111111'),user)
    assert e.value.status_code==409

@pytest.mark.parametrize('code,status',[('333333',403),('444444',404)])
def test_scope_protection(user,code,status):
    with pytest.raises(HTTPException) as e: main.validate_purchase(ValidateOperationInput(code=code),user)
    assert e.value.status_code==status

def test_migration_preserves_existing(user):
    main.validate_purchase(ValidateOperationInput(code='333333'),dict(user,branch_id=1))
    main.validate_purchase(ValidateOperationInput(code='111111'),user)
    with connection() as c:
        assert [r[0] for r in c.execute('SELECT branch_id FROM purchases ORDER BY id')]==[1,None]
        assert c.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_purchases_tenant'").fetchone()
