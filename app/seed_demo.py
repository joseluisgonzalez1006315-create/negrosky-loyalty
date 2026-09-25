"""Crea datos locales de demostración de forma repetible."""

from .database import connection, init_db
from .security import hash_password


def seed_demo() -> None:
    init_db()
    with connection() as con:
        tenant = con.execute("SELECT id FROM tenants WHERE slug='santuario'").fetchone()
        if tenant:
            tenant_id = tenant["id"]
        else:
            tenant_id = con.execute(
                "INSERT INTO tenants (name, slug) VALUES ('Santuario Granizados', 'santuario')"
            ).lastrowid

        branch = con.execute(
            "SELECT id FROM branches WHERE tenant_id=? AND name='Acacías'", (tenant_id,)
        ).fetchone()
        if branch:
            branch_id = branch["id"]
        else:
            branch_id = con.execute(
                """INSERT INTO branches (tenant_id, name, city, address, phone)
                VALUES (?, 'Acacías', 'Acacías', 'Sucursal principal demo', '3000000000')""",
                (tenant_id,),
            ).lastrowid

        worker = con.execute(
            "SELECT id FROM users WHERE email='trabajador@santuario.demo'"
        ).fetchone()
        if not worker:
            con.execute(
                """INSERT INTO users
                (tenant_id, branch_id, name, email, password_hash, role)
                VALUES (?, ?, 'Trabajador Demo', 'trabajador@santuario.demo', ?, 'worker')""",
                (tenant_id, branch_id, hash_password("Demo12345!")),
            )

        program = con.execute(
            "SELECT id FROM loyalty_programs WHERE tenant_id=? AND name='Compra 2 y gana'",
            (tenant_id,),
        ).fetchone()
        if program:
            program_id = program["id"]
        else:
            program_id = con.execute(
                """INSERT INTO loyalty_programs
                (tenant_id, name, target_purchases, reward_name)
                VALUES (?, 'Compra 2 y gana', 2, '1 granizado gratis')""",
                (tenant_id,),
            ).lastrowid

        customer = con.execute(
            "SELECT id FROM customers WHERE tenant_id=? AND phone='3001234567'",
            (tenant_id,),
        ).fetchone()
        if customer:
            customer_id = customer["id"]
        else:
            customer_id = con.execute(
                """INSERT INTO customers (tenant_id, name, phone, marketing_consent)
                VALUES (?, 'José González', '3001234567', 1)""",
                (tenant_id,),
            ).lastrowid
        con.execute(
            """INSERT OR IGNORE INTO loyalty_cards
            (tenant_id, customer_id, program_id, progress, cycle)
            VALUES (?, ?, ?, 0, 1)""",
            (tenant_id, customer_id, program_id),
        )


if __name__ == "__main__":
    seed_demo()
    print("NEGROSKY DEMO cargada correctamente")
