"""Genera un entorno de demostración aislado con negocios variados."""
from datetime import date, timedelta
from .database import connection, init_db
from .security import hash_password

MODULES = ("loyalty", "appointments", "time_sales", "notifications", "public_page", "raffles", "roulette", "collaborations")
BUSINESSES = [
    ("PIZZAS", "pizzas", "food", "#f97316", "#9a3412", "Pizzas, combos y domicilios", (1,0,0,1,1,1,1,1)),
    ("Santuario Granizados", "santuario", "food", "#06b6d4", "#164e63", "Granizados, bebidas y premios", (1,1,0,1,1,1,0,1)),
    ("Café Aurora", "cafe-aurora", "coffee", "#c084fc", "#6d28d9", "Café artesanal, postres y desayunos", (1,1,0,1,1,0,0,1)),
    ("Barbería Norte", "barberia-norte", "beauty", "#38bdf8", "#0f172a", "Cortes, barba y cuidado masculino", (1,1,0,1,1,0,0,0)),
    ("Spa Luna", "spa-luna", "beauty", "#fb7185", "#be185d", "Bienestar, masajes y tratamientos", (1,1,0,1,1,0,0,1)),
    ("Gym Titan", "gym-titan", "fitness", "#22c55e", "#14532d", "Entrenamiento y vida saludable", (1,0,1,1,1,0,1,0)),
    ("Moda Viva", "moda-viva", "retail", "#facc15", "#a16207", "Moda, accesorios y novedades", (1,0,0,1,1,1,0,1)),
    ("Mundo Mascotas", "mundo-mascotas", "pets", "#14b8a6", "#115e59", "Alimentos, baño y cuidado de mascotas", (1,1,0,1,1,0,1,1)),
]

def seed_many_businesses():
    init_db()
    with connection() as con:
        if not con.execute("SELECT 1 FROM users WHERE role='super_admin'").fetchone():
            con.execute("INSERT INTO users (name,email,password_hash,role,username) VALUES (?,?,?,?,?)", ("Administrador General", "admin@negrosky.demo", hash_password("ChangeMe123!"), "super_admin", "admin"))
        for index, (name, slug, theme, primary, secondary, welcome, flags) in enumerate(BUSINESSES, 1):
            row = con.execute("SELECT id FROM tenants WHERE slug=?", (slug,)).fetchone()
            if row:
                tenant_id = row["id"]
            else:
                tenant_id = con.execute("INSERT INTO tenants (name,slug,public_key) VALUES (?,?,?)", (name, slug, f"demo-{slug}")).lastrowid
            branch_id = con.execute("SELECT id FROM branches WHERE tenant_id=? ORDER BY id LIMIT 1", (tenant_id,)).fetchone()
            if branch_id:
                branch_id = branch_id["id"]
            else:
                branch_id = con.execute("INSERT INTO branches (tenant_id,name,city,address,phone) VALUES (?,?,?,?,?)", (tenant_id, "Sede principal", "Acacías", f"Calle {10+index} # {20+index}", f"300555{index:04d}")).lastrowid
            email = f"dueno@{slug}.demo"
            con.execute("INSERT OR IGNORE INTO users (tenant_id,branch_id,name,email,password_hash,role,username) VALUES (?,?,?,?,?,?,?)", (tenant_id, branch_id, f"Dueño {name}", email, hash_password("Demo12345!"), "business_admin", slug.replace('-','')))
            con.execute("INSERT OR REPLACE INTO business_branding (tenant_id,theme_key,display_name,welcome_text,primary_color,secondary_color,button_color,contact_phone,whatsapp_number,address) VALUES (?,?,?,?,?,?,?,?,?,?)", (tenant_id, theme, name, welcome, primary, secondary, primary, f"300555{index:04d}", f"57300555{index:04d}", f"Calle {10+index} # {20+index}, Acacías"))
            for key, enabled in zip(MODULES, flags):
                con.execute("INSERT OR REPLACE INTO feature_modules (tenant_id,branch_id,module_key,enabled) VALUES (?,NULL,?,?)", (tenant_id, key, enabled))
            con.execute("INSERT OR REPLACE INTO tenant_onboarding (tenant_id,completed,current_step,setup_mode) VALUES (?,1,8,'owner')", (tenant_id,))
            con.execute("DELETE FROM business_hours WHERE tenant_id=? AND branch_id IS NULL", (tenant_id,))
            for weekday in range(7):
                enabled = 0 if weekday == 6 and index % 3 == 0 else 1
                con.execute("INSERT INTO business_hours (tenant_id,weekday,enabled,opens_at,closes_at) VALUES (?,?,?,?,?)", (tenant_id, weekday, enabled, "08:00" if weekday else "10:00", "20:00" if weekday < 6 else "16:00"))
            program = con.execute("SELECT id FROM loyalty_programs WHERE tenant_id=? LIMIT 1", (tenant_id,)).fetchone()
            if not program:
                program = con.execute("INSERT INTO loyalty_programs (tenant_id,name,target_purchases,reward_name,progress_emoji,reward_display,reward_stock) VALUES (?,?,?,?,?,?,?)", (tenant_id, f"Compra {3+index%4} y gana", 3+index%4, "Premio especial", "⭐" if index%2 else "🎁", "quantity", 25+index*5)).lastrowid
            else:
                program = program["id"]
            for n in range(1, 41):
                phone = f"301{index:02d}{n:05d}"
                birth = date(1985+n%15, ((n+index)%12)+1, ((n*2+index)%27)+1).isoformat()
                customer = con.execute("SELECT id FROM customers WHERE tenant_id=? AND phone=?", (tenant_id, phone)).fetchone()
                if customer:
                    customer_id = customer["id"]
                else:
                    customer_id = con.execute("INSERT INTO customers (tenant_id,name,phone,marketing_consent,origin_branch_id,birth_date,birthday_consent,search_key) VALUES (?,?,?,?,?,?,?,?)", (tenant_id, f"Cliente {name} {n:02d}", phone, 1, branch_id, birth, 1, f"cliente {name.lower()} {n:02d}")).lastrowid
                con.execute("INSERT OR IGNORE INTO loyalty_cards (tenant_id,customer_id,program_id,progress,cycle) VALUES (?,?,?,?,?)", (tenant_id, customer_id, program, (n+index)% (3+index%4), 1))
            if flags[5]:
                if not con.execute("SELECT 1 FROM raffles WHERE tenant_id=?", (tenant_id,)).fetchone():
                    con.execute("INSERT INTO raffles (tenant_id,name,description,image_url,ticket_count,status,tickets_per_purchase,customer_ticket_limit) VALUES (?,?,?,?,?,?,?,?)", (tenant_id, f"Rifa {name}", "Premio de demostración", None, 100, "active", 1+index%4, 2+index%5))
            con.execute("INSERT OR REPLACE INTO birthday_settings (tenant_id,enabled,days_before,monthly_limit,promotion) VALUES (?,?,?,?,?)", (tenant_id, 1, index%7, 5+index*2, f"Promoción de cumpleaños de {name}"))
    print(f"Creados {len(BUSINESSES)} negocios de prueba y {len(BUSINESSES)*40} clientes.")

if __name__ == "__main__":
    seed_many_businesses()
