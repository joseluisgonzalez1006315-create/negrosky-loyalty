"""Restablece únicamente la cuenta del administrador general.

No elimina negocios, clientes, compras, imágenes ni configuraciones.
"""

from .database import connection, init_db
from .security import hash_password


USERNAME = "admin"
EMAIL = "admin@negrosky.local"
PASSWORD = "ChangeMe123!"


def main() -> None:
    init_db()
    with connection() as con:
        admin = con.execute(
            "SELECT id FROM users WHERE role='super_admin' ORDER BY id LIMIT 1"
        ).fetchone()
        if admin:
            con.execute(
                """UPDATE users
                   SET username=?, email=?, password_hash=?, status='active',
                       failed_attempts=0, locked_until=NULL, force_password_change=0,
                       updated_at=CURRENT_TIMESTAMP
                 WHERE id=?""",
                (USERNAME, EMAIL, hash_password(PASSWORD), admin["id"]),
            )
        else:
            con.execute(
                """INSERT INTO users
                   (name, username, email, password_hash, role, status,
                    failed_attempts, force_password_change)
                   VALUES (?, ?, ?, ?, 'super_admin', 'active', 0, 0)""",
                ("Administrador General", USERNAME, EMAIL, hash_password(PASSWORD)),
            )
    print("Administrador restablecido correctamente.")
    print(f"Usuario: {USERNAME}")
    print(f"Contraseña: {PASSWORD}")


if __name__ == "__main__":
    main()
