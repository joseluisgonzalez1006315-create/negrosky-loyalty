import os
import sqlite3
import secrets
import unicodedata
import base64
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "negrosky_v2.db"


def database_path() -> Path:
    return Path(os.getenv("NEGROSKY_DB_PATH", str(DEFAULT_DB)))


@contextmanager
def connection():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    with connection() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS tenants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                public_key TEXT UNIQUE,
                status TEXT NOT NULL DEFAULT 'active',
                timezone TEXT NOT NULL DEFAULT 'America/Bogota',
                manual_closed INTEGER NOT NULL DEFAULT 0,
                closed_message TEXT NOT NULL DEFAULT 'En este momento estamos fuera de servicio. Te esperamos en nuestro próximo horario de atención.',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS branches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                city TEXT,
                address TEXT,
                phone TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                schedule_mode TEXT NOT NULL DEFAULT 'inherit',
                manual_closed INTEGER NOT NULL DEFAULT 0,
                closed_message TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (tenant_id, name),
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER,
                branch_id INTEGER,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                username TEXT UNIQUE,
                email_optional INTEGER NOT NULL DEFAULT 0,
                force_password_change INTEGER NOT NULL DEFAULT 0,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until TEXT,
                updated_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                FOREIGN KEY (branch_id) REFERENCES branches(id)
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER,
                branch_id INTEGER,
                user_id INTEGER,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                FOREIGN KEY (branch_id) REFERENCES branches(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_branches_tenant ON branches(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_logs(tenant_id);

            CREATE TABLE IF NOT EXISTS user_sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_agent TEXT,
                ip_address TEXT,
                revoked_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS support_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS business_hours (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                branch_id INTEGER,
                weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
                enabled INTEGER NOT NULL DEFAULT 1,
                opens_at TEXT NOT NULL DEFAULT '00:00',
                closes_at TEXT NOT NULL DEFAULT '23:59',
                UNIQUE (tenant_id, branch_id, weekday),
                FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                FOREIGN KEY (branch_id) REFERENCES branches(id)
            );

            CREATE TABLE IF NOT EXISTS feature_modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                branch_id INTEGER,
                module_key TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                UNIQUE (tenant_id, branch_id, module_key),
                FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                FOREIGN KEY (branch_id) REFERENCES branches(id)
            );

            CREATE TABLE IF NOT EXISTS raffles (id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, name TEXT NOT NULL, description TEXT, image_url TEXT, ticket_price REAL NOT NULL DEFAULT 0, ticket_count INTEGER NOT NULL DEFAULT 100, draw_at TEXT, status TEXT NOT NULL DEFAULT 'draft', winner_ticket TEXT, winner_name TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (tenant_id) REFERENCES tenants(id));
            CREATE TABLE IF NOT EXISTS raffle_tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, raffle_id INTEGER NOT NULL, ticket_number TEXT NOT NULL, customer_name TEXT NOT NULL, customer_phone TEXT, status TEXT NOT NULL DEFAULT 'reserved', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(raffle_id,ticket_number), FOREIGN KEY (raffle_id) REFERENCES raffles(id));
            CREATE TABLE IF NOT EXISTS raffle_operation_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                customer_id INTEGER NOT NULL,
                raffle_id INTEGER NOT NULL,
                branch_id INTEGER,
                code TEXT NOT NULL UNIQUE,
                ticket_ids_json TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                rejected_at TEXT,
                validated_by_name TEXT,
                validated_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (raffle_id) REFERENCES raffles(id)
            );
            CREATE TABLE IF NOT EXISTS roulette_configs (id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, name TEXT NOT NULL, prizes_json TEXT NOT NULL, difficulty INTEGER NOT NULL DEFAULT 50, schedule_json TEXT, enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (tenant_id) REFERENCES tenants(id));
            CREATE TABLE IF NOT EXISTS roulette_spins (id INTEGER PRIMARY KEY AUTOINCREMENT, config_id INTEGER NOT NULL, customer_name TEXT, customer_phone TEXT, prize TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (config_id) REFERENCES roulette_configs(id));

            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                marketing_consent INTEGER NOT NULL DEFAULT 0,
                origin_branch_id INTEGER,
                status TEXT NOT NULL DEFAULT 'active',
                notes TEXT,
                tags TEXT,
                created_by_user_id INTEGER,
                merged_into_id INTEGER,
                search_key TEXT,
                birth_date TEXT,
                birthday_consent INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (tenant_id, phone),
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
                ,FOREIGN KEY (origin_branch_id) REFERENCES branches(id)
                ,FOREIGN KEY (created_by_user_id) REFERENCES users(id)
                ,FOREIGN KEY (merged_into_id) REFERENCES customers(id)
            );

            CREATE TABLE IF NOT EXISTS loyalty_programs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                target_purchases INTEGER NOT NULL,
                reward_name TEXT NOT NULL,
                progress_emoji TEXT NOT NULL DEFAULT '⭐',
                reward_stock INTEGER,
                reward_display TEXT NOT NULL DEFAULT 'hidden',
                title_mode TEXT NOT NULL DEFAULT 'inherit',
                stamps_mode TEXT NOT NULL DEFAULT 'inherit',
                progress_mode TEXT NOT NULL DEFAULT 'inherit',
                reward_mode TEXT NOT NULL DEFAULT 'inherit',
                button_mode TEXT NOT NULL DEFAULT 'inherit',
                status TEXT NOT NULL DEFAULT 'active',
                deleted_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            );

            CREATE TABLE IF NOT EXISTS loyalty_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                customer_id INTEGER NOT NULL,
                program_id INTEGER NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                cycle INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (customer_id, program_id),
                FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (program_id) REFERENCES loyalty_programs(id)
            );

            CREATE TABLE IF NOT EXISTS operation_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                customer_id INTEGER NOT NULL,
                program_id INTEGER NOT NULL,
                operation_type TEXT NOT NULL,
                reference_id INTEGER,
                code TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (program_id) REFERENCES loyalty_programs(id)
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                branch_id INTEGER NOT NULL,
                customer_id INTEGER NOT NULL,
                program_id INTEGER NOT NULL,
                worker_id INTEGER NOT NULL,
                operation_token_id INTEGER NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                FOREIGN KEY (branch_id) REFERENCES branches(id),
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (program_id) REFERENCES loyalty_programs(id),
                FOREIGN KEY (worker_id) REFERENCES users(id),
                FOREIGN KEY (operation_token_id) REFERENCES operation_tokens(id)
            );

            CREATE TABLE IF NOT EXISTS rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                customer_id INTEGER NOT NULL,
                program_id INTEGER NOT NULL,
                card_cycle INTEGER NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'available',
                unlocked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                claimed_at TEXT,
                branch_id INTEGER,
                worker_id INTEGER,
                UNIQUE (customer_id, program_id, card_cycle),
                FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (program_id) REFERENCES loyalty_programs(id),
                FOREIGN KEY (branch_id) REFERENCES branches(id),
                FOREIGN KEY (worker_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS operation_token_rewards (
                operation_token_id INTEGER NOT NULL,
                reward_id INTEGER NOT NULL,
                PRIMARY KEY (operation_token_id, reward_id),
                FOREIGN KEY (operation_token_id) REFERENCES operation_tokens(id),
                FOREIGN KEY (reward_id) REFERENCES rewards(id)
            );

            CREATE TABLE IF NOT EXISTS appointment_services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                branch_id INTEGER,
                name TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL DEFAULT 30,
                price INTEGER,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (tenant_id, branch_id, name),
                FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                FOREIGN KEY (branch_id) REFERENCES branches(id)
            );

            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                branch_id INTEGER NOT NULL,
                customer_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                starts_at TEXT NOT NULL,
                ends_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'scheduled',
                notes TEXT,
                cancellation_reason TEXT,
                cancelled_at TEXT,
                cancelled_by TEXT,
                delay_minutes INTEGER NOT NULL DEFAULT 0,
                delay_reason TEXT,
                estimated_end_at TEXT,
                created_by_user_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                FOREIGN KEY (branch_id) REFERENCES branches(id),
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (service_id) REFERENCES appointment_services(id),
                FOREIGN KEY (created_by_user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                branch_id INTEGER,
                customer_id INTEGER,
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                read_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                FOREIGN KEY (branch_id) REFERENCES branches(id),
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );

            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                tenant_id INTEGER NOT NULL,
                endpoint TEXT NOT NULL UNIQUE,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            );

            CREATE TABLE IF NOT EXISTS push_keys (
                id INTEGER PRIMARY KEY CHECK (id=1),
                private_key_pem TEXT NOT NULL,
                public_key TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS collaboration_contacts (
                tenant_id INTEGER PRIMARY KEY,
                whatsapp TEXT NOT NULL,
                visible INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            );

            CREATE TABLE IF NOT EXISTS collaborations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requester_tenant_id INTEGER NOT NULL,
                partner_tenant_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                message TEXT,
                image_url TEXT,
                ends_at TEXT,
                ad_seconds INTEGER NOT NULL DEFAULT 5,
                is_active INTEGER NOT NULL DEFAULT 1,
                requester_status TEXT NOT NULL DEFAULT 'pending',
                partner_status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT,
                FOREIGN KEY (requester_tenant_id) REFERENCES tenants(id),
                FOREIGN KEY (partner_tenant_id) REFERENCES tenants(id)
            );

            CREATE TABLE IF NOT EXISTS business_branding (
                tenant_id INTEGER PRIMARY KEY,
                theme_key TEXT NOT NULL DEFAULT 'custom',
                display_name TEXT,
                welcome_text TEXT NOT NULL DEFAULT 'Bienvenido a nuestro club de beneficios',
                primary_color TEXT NOT NULL DEFAULT '#a970ff',
                secondary_color TEXT NOT NULL DEFAULT '#7547d8',
                button_color TEXT NOT NULL DEFAULT '#7c3aed',
                background_style TEXT NOT NULL DEFAULT 'dark',
                background_color TEXT NOT NULL DEFAULT '#07070d',
                background_same_frame INTEGER NOT NULL DEFAULT 1,
                background_fit_desktop TEXT NOT NULL DEFAULT 'cover',
                background_x_desktop INTEGER NOT NULL DEFAULT 50,
                background_y_desktop INTEGER NOT NULL DEFAULT 50,
                background_fit_mobile TEXT NOT NULL DEFAULT 'cover',
                background_x_mobile INTEGER NOT NULL DEFAULT 50,
                background_y_mobile INTEGER NOT NULL DEFAULT 50,
                background_image_opacity INTEGER NOT NULL DEFAULT 100,
                background_overlay_opacity INTEGER NOT NULL DEFAULT 35,
                card_style TEXT NOT NULL DEFAULT 'soft',
                card_shape TEXT NOT NULL DEFAULT 'rounded',
                card_opacity INTEGER NOT NULL DEFAULT 94,
                logo_shape TEXT NOT NULL DEFAULT 'rounded',
                logo_fit TEXT NOT NULL DEFAULT 'contain',
                logo_size INTEGER NOT NULL DEFAULT 64,
                logo_opacity INTEGER NOT NULL DEFAULT 100,
                logo_background_color TEXT NOT NULL DEFAULT '#ffffff',
                font_family TEXT NOT NULL DEFAULT 'modern',
                font_scale INTEGER NOT NULL DEFAULT 100,
                text_color TEXT NOT NULL DEFAULT '#f7f5ff',
                button_shape TEXT NOT NULL DEFAULT 'rounded',
                button_label TEXT NOT NULL DEFAULT 'Registrar mi compra',
                stamp_shape TEXT NOT NULL DEFAULT 'circle',
                stamp_done_color TEXT NOT NULL DEFAULT '#7547d8',
                stamp_pending_color TEXT NOT NULL DEFAULT '#252334',
                progress_start_color TEXT NOT NULL DEFAULT '#a970ff',
                progress_end_color TEXT NOT NULL DEFAULT '#7547d8',
                progress_style TEXT NOT NULL DEFAULT 'normal',
                show_profile INTEGER NOT NULL DEFAULT 1,
                show_rewards INTEGER NOT NULL DEFAULT 1,
                show_appointments INTEGER NOT NULL DEFAULT 1,
                show_contact INTEGER NOT NULL DEFAULT 1,
                show_business_hours INTEGER NOT NULL DEFAULT 1,
                show_campaign_title INTEGER NOT NULL DEFAULT 1,
                show_campaign_stamps INTEGER NOT NULL DEFAULT 1,
                show_campaign_progress INTEGER NOT NULL DEFAULT 1,
                show_campaign_reward INTEGER NOT NULL DEFAULT 1,
                show_campaign_button INTEGER NOT NULL DEFAULT 1,
                contact_phone TEXT,
                whatsapp_number TEXT,
                address TEXT,
                instagram_url TEXT,
                facebook_url TEXT,
                tiktok_url TEXT,
                website_url TEXT,
                maps_url TEXT,
                social_display_mode TEXT NOT NULL DEFAULT 'both',
                social_size TEXT NOT NULL DEFAULT 'medium',
                social_layout TEXT NOT NULL DEFAULT 'inline',
                social_position TEXT NOT NULL DEFAULT 'bottom-right',
                show_social_mobile INTEGER NOT NULL DEFAULT 1,
                show_social_desktop INTEGER NOT NULL DEFAULT 1,
                module_order_mobile TEXT NOT NULL DEFAULT 'contact,profile,campaigns,rewards,appointments',
                module_order_desktop TEXT NOT NULL DEFAULT 'contact,profile,campaigns,rewards,appointments',
                module_widths_mobile TEXT NOT NULL DEFAULT 'contact:100,profile:100,campaigns:100,rewards:100,appointments:100',
                module_widths_desktop TEXT NOT NULL DEFAULT 'contact:100,profile:50,campaigns:50,rewards:50,appointments:50',
                logo_mime TEXT,
                logo_blob BLOB,
                background_mime TEXT,
                background_blob BLOB,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            );

            CREATE TABLE IF NOT EXISTS program_icons (
                program_id INTEGER PRIMARY KEY,
                tenant_id INTEGER NOT NULL,
                icon_mime TEXT NOT NULL,
                icon_blob BLOB NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (program_id) REFERENCES loyalty_programs(id),
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            );

            CREATE TABLE IF NOT EXISTS time_services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                branch_id INTEGER,
                name TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL DEFAULT 60,
                price INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                FOREIGN KEY (branch_id) REFERENCES branches(id)
            );

            CREATE TABLE IF NOT EXISTS time_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                branch_id INTEGER NOT NULL,
                customer_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                worker_id INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                planned_end_at TEXT NOT NULL,
                ended_at TEXT,
                minutes_used INTEGER,
                total_price INTEGER,
                status TEXT NOT NULL DEFAULT 'open',
                notes TEXT,
                close_notes TEXT,
                closed_by_user_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                FOREIGN KEY (branch_id) REFERENCES branches(id),
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (service_id) REFERENCES time_services(id),
                FOREIGN KEY (worker_id) REFERENCES users(id),
                FOREIGN KEY (closed_by_user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_customers_tenant ON customers(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_cards_customer ON loyalty_cards(customer_id);
            CREATE INDEX IF NOT EXISTS idx_tokens_code ON operation_tokens(code);
            CREATE INDEX IF NOT EXISTS idx_purchases_tenant ON purchases(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_rewards_customer ON rewards(customer_id);
            CREATE INDEX IF NOT EXISTS idx_appointments_tenant ON appointments(tenant_id, starts_at);
            CREATE INDEX IF NOT EXISTS idx_appointments_customer ON appointments(customer_id, starts_at);
            CREATE INDEX IF NOT EXISTS idx_notifications_tenant ON notifications(tenant_id, read_at, created_at);
            CREATE INDEX IF NOT EXISTS idx_time_services_tenant ON time_services(tenant_id, branch_id, status);
            CREATE INDEX IF NOT EXISTS idx_time_sessions_open ON time_sessions(tenant_id, branch_id, status);
            CREATE INDEX IF NOT EXISTS idx_time_sessions_customer ON time_sessions(customer_id, status);
            """
        )
        con.execute("""CREATE TABLE IF NOT EXISTS worker_access (
            user_id INTEGER PRIMARY KEY,
            permissions_json TEXT NOT NULL DEFAULT '{}',
            schedule_json TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS platform_ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message TEXT,
            image_url TEXT NOT NULL,
            target_tenants_json TEXT NOT NULL DEFAULT '[]',
            starts_at TEXT,
            ends_at TEXT,
            ad_seconds INTEGER NOT NULL DEFAULT 5,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS business_ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT,
            image_url TEXT NOT NULL,
            starts_at TEXT,
            ends_at TEXT,
            ad_seconds INTEGER NOT NULL DEFAULT 5,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS tenant_onboarding (
            tenant_id INTEGER PRIMARY KEY,
            completed INTEGER NOT NULL DEFAULT 0,
            current_step INTEGER NOT NULL DEFAULT 0,
            setup_mode TEXT NOT NULL DEFAULT 'owner',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
        )""")
        onboarding_columns = {row[1] for row in con.execute("PRAGMA table_info(tenant_onboarding)")}
        if "setup_mode" not in onboarding_columns:
            con.execute("ALTER TABLE tenant_onboarding ADD COLUMN setup_mode TEXT NOT NULL DEFAULT 'owner'")
        con.execute("""CREATE TABLE IF NOT EXISTS birthday_settings (
            tenant_id INTEGER PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1,
            days_before INTEGER NOT NULL DEFAULT 3,
            monthly_limit INTEGER NOT NULL DEFAULT 0,
            promotion TEXT NOT NULL DEFAULT '¡Feliz cumpleaños! Te tenemos una sorpresa especial.',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
        )""")
        columns = {row[1] for row in con.execute("PRAGMA table_info(loyalty_programs)")}
        notification_columns = {row[1] for row in con.execute("PRAGMA table_info(notifications)")}
        customer_columns = {row[1] for row in con.execute("PRAGMA table_info(customers)")}
        if "birth_date" not in customer_columns:
            con.execute("ALTER TABLE customers ADD COLUMN birth_date TEXT")
        if "birthday_consent" not in customer_columns:
            con.execute("ALTER TABLE customers ADD COLUMN birthday_consent INTEGER NOT NULL DEFAULT 0")
        if "image_url" not in notification_columns:
            con.execute("ALTER TABLE notifications ADD COLUMN image_url TEXT")
        if not con.execute("SELECT 1 FROM push_keys WHERE id=1").fetchone():
            # Push is optional: the server must still start if dependencies are not installed yet.
            try:
                from cryptography.hazmat.primitives import serialization
                from cryptography.hazmat.primitives.asymmetric import ec
                private_key = ec.generate_private_key(ec.SECP256R1())
                private_pem = private_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
                public_raw = private_key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
                public_key = base64.urlsafe_b64encode(public_raw).rstrip(b"=").decode()
                con.execute("INSERT INTO push_keys(id,private_key_pem,public_key) VALUES(1,?,?)", (private_pem, public_key))
            except ImportError:
                pass
        token_columns = {row[1] for row in con.execute("PRAGMA table_info(operation_tokens)")}
        if "branch_id" not in token_columns:
            con.execute("ALTER TABLE operation_tokens ADD COLUMN branch_id INTEGER")
        if "progress_emoji" not in columns:
            con.execute("ALTER TABLE loyalty_programs ADD COLUMN progress_emoji TEXT NOT NULL DEFAULT '⭐'")
        if "reward_stock" not in columns:
            con.execute("ALTER TABLE loyalty_programs ADD COLUMN reward_stock INTEGER")
        if "reward_display" not in columns:
            con.execute("ALTER TABLE loyalty_programs ADD COLUMN reward_display TEXT NOT NULL DEFAULT 'hidden'")
        if "deleted_at" not in columns:
            con.execute("ALTER TABLE loyalty_programs ADD COLUMN deleted_at TEXT")
        for name in ("title_mode", "stamps_mode", "progress_mode", "reward_mode", "button_mode"):
            if name not in columns:
                con.execute(f"ALTER TABLE loyalty_programs ADD COLUMN {name} TEXT NOT NULL DEFAULT 'inherit'")
        branding_columns = {row[1] for row in con.execute("PRAGMA table_info(business_branding)")}
        for name, definition in {
            "theme_key": "TEXT NOT NULL DEFAULT 'custom'",
            "background_same_frame": "INTEGER NOT NULL DEFAULT 1",
            "background_fit_desktop": "TEXT NOT NULL DEFAULT 'cover'", "background_x_desktop": "INTEGER NOT NULL DEFAULT 50",
            "background_y_desktop": "INTEGER NOT NULL DEFAULT 50", "background_fit_mobile": "TEXT NOT NULL DEFAULT 'cover'",
            "background_x_mobile": "INTEGER NOT NULL DEFAULT 50", "background_y_mobile": "INTEGER NOT NULL DEFAULT 50",
            "background_image_opacity": "INTEGER NOT NULL DEFAULT 100", "background_overlay_opacity": "INTEGER NOT NULL DEFAULT 35",
            "logo_shape": "TEXT NOT NULL DEFAULT 'rounded'", "logo_fit": "TEXT NOT NULL DEFAULT 'contain'",
            "logo_size": "INTEGER NOT NULL DEFAULT 64", "logo_opacity": "INTEGER NOT NULL DEFAULT 100",
            "logo_background_color": "TEXT NOT NULL DEFAULT '#ffffff'",
            "card_shape": "TEXT NOT NULL DEFAULT 'rounded'", "card_opacity": "INTEGER NOT NULL DEFAULT 94",
            "font_family": "TEXT NOT NULL DEFAULT 'modern'", "font_scale": "INTEGER NOT NULL DEFAULT 100",
            "text_color": "TEXT NOT NULL DEFAULT '#f7f5ff'", "button_shape": "TEXT NOT NULL DEFAULT 'rounded'",
            "button_label": "TEXT NOT NULL DEFAULT 'Registrar mi compra'", "stamp_shape": "TEXT NOT NULL DEFAULT 'circle'",
            "stamp_done_color": "TEXT NOT NULL DEFAULT '#7547d8'", "stamp_pending_color": "TEXT NOT NULL DEFAULT '#252334'",
            "progress_start_color": "TEXT NOT NULL DEFAULT '#a970ff'", "progress_end_color": "TEXT NOT NULL DEFAULT '#7547d8'",
            "progress_style": "TEXT NOT NULL DEFAULT 'normal'",
            "show_profile": "INTEGER NOT NULL DEFAULT 1", "show_rewards": "INTEGER NOT NULL DEFAULT 1",
            "show_appointments": "INTEGER NOT NULL DEFAULT 1", "background_mime": "TEXT", "background_blob": "BLOB",
            "show_contact": "INTEGER NOT NULL DEFAULT 1", "show_business_hours": "INTEGER NOT NULL DEFAULT 1",
            "contact_phone": "TEXT", "whatsapp_number": "TEXT", "address": "TEXT",
            "show_campaign_title": "INTEGER NOT NULL DEFAULT 1", "show_campaign_stamps": "INTEGER NOT NULL DEFAULT 1",
            "show_campaign_progress": "INTEGER NOT NULL DEFAULT 1", "show_campaign_reward": "INTEGER NOT NULL DEFAULT 1",
            "show_campaign_button": "INTEGER NOT NULL DEFAULT 1",
            "instagram_url": "TEXT", "facebook_url": "TEXT", "tiktok_url": "TEXT",
            "website_url": "TEXT", "maps_url": "TEXT",
            "social_display_mode": "TEXT NOT NULL DEFAULT 'both'", "social_size": "TEXT NOT NULL DEFAULT 'medium'",
            "social_layout": "TEXT NOT NULL DEFAULT 'inline'", "social_position": "TEXT NOT NULL DEFAULT 'bottom-right'",
            "show_social_mobile": "INTEGER NOT NULL DEFAULT 1", "show_social_desktop": "INTEGER NOT NULL DEFAULT 1",
            "module_order_mobile": "TEXT NOT NULL DEFAULT 'contact,profile,campaigns,rewards,appointments'",
            "module_order_desktop": "TEXT NOT NULL DEFAULT 'contact,profile,campaigns,rewards,appointments'",
            "module_widths_mobile": "TEXT NOT NULL DEFAULT 'contact:100,profile:100,campaigns:100,rewards:100,appointments:100'",
            "module_widths_desktop": "TEXT NOT NULL DEFAULT 'contact:100,profile:50,campaigns:50,rewards:50,appointments:50'",
        }.items():
            if name not in branding_columns:
                con.execute(f"ALTER TABLE business_branding ADD COLUMN {name} {definition}")
        collaboration_columns = {row[1] for row in con.execute("PRAGMA table_info(collaborations)")}
        for name, definition in {
            "ends_at": "TEXT",
            "ad_seconds": "INTEGER NOT NULL DEFAULT 5",
            "is_active": "INTEGER NOT NULL DEFAULT 1",
        }.items():
            if name not in collaboration_columns:
                con.execute(f"ALTER TABLE collaborations ADD COLUMN {name} {definition}")
        customer_columns = {row[1] for row in con.execute("PRAGMA table_info(customers)")}
        raffle_columns = {row[1] for row in con.execute("PRAGMA table_info(raffles)")}
        raffle_operation_columns = {row[1] for row in con.execute("PRAGMA table_info(raffle_operation_tokens)")}
        if "validated_by_name" not in raffle_operation_columns:
            con.execute("ALTER TABLE raffle_operation_tokens ADD COLUMN validated_by_name TEXT")
        if "validated_at" not in raffle_operation_columns:
            con.execute("ALTER TABLE raffle_operation_tokens ADD COLUMN validated_at TEXT")
        if "tickets_per_purchase" not in raffle_columns:
            con.execute("ALTER TABLE raffles ADD COLUMN tickets_per_purchase INTEGER NOT NULL DEFAULT 1")
        if "customer_ticket_limit" not in raffle_columns:
            con.execute("ALTER TABLE raffles ADD COLUMN customer_ticket_limit INTEGER")
        if "origin_branch_id" not in customer_columns:
            con.execute("ALTER TABLE customers ADD COLUMN origin_branch_id INTEGER")
        tenant_columns = {row[1] for row in con.execute("PRAGMA table_info(tenants)")}
        if "public_key" not in tenant_columns:
            con.execute("ALTER TABLE tenants ADD COLUMN public_key TEXT")
        for row in con.execute("SELECT id FROM tenants WHERE public_key IS NULL OR public_key='' ").fetchall():
            con.execute("UPDATE tenants SET public_key=? WHERE id=?", (secrets.token_urlsafe(12), row[0]))
        if "timezone" not in tenant_columns:
            con.execute("ALTER TABLE tenants ADD COLUMN timezone TEXT NOT NULL DEFAULT 'America/Bogota'")
        if "manual_closed" not in tenant_columns:
            con.execute("ALTER TABLE tenants ADD COLUMN manual_closed INTEGER NOT NULL DEFAULT 0")
        if "closed_message" not in tenant_columns:
            con.execute("ALTER TABLE tenants ADD COLUMN closed_message TEXT NOT NULL DEFAULT 'En este momento estamos fuera de servicio. Te esperamos en nuestro próximo horario de atención.'")
        branch_columns = {row[1] for row in con.execute("PRAGMA table_info(branches)")}
        if "schedule_mode" not in branch_columns:
            con.execute("ALTER TABLE branches ADD COLUMN schedule_mode TEXT NOT NULL DEFAULT 'inherit'")
        if "manual_closed" not in branch_columns:
            con.execute("ALTER TABLE branches ADD COLUMN manual_closed INTEGER NOT NULL DEFAULT 0")
        if "closed_message" not in branch_columns:
            con.execute("ALTER TABLE branches ADD COLUMN closed_message TEXT")
        if "deleted_at" not in tenant_columns:
            con.execute("ALTER TABLE tenants ADD COLUMN deleted_at TEXT")
        if "deleted_at" not in branch_columns:
            con.execute("ALTER TABLE branches ADD COLUMN deleted_at TEXT")
        user_columns = {row[1] for row in con.execute("PRAGMA table_info(users)")}
        for name, definition in {
            "username": "TEXT",
            "email_optional": "INTEGER NOT NULL DEFAULT 0",
            "force_password_change": "INTEGER NOT NULL DEFAULT 0",
            "failed_attempts": "INTEGER NOT NULL DEFAULT 0",
            "locked_until": "TEXT",
            "updated_at": "TEXT",
        }.items():
            if name not in user_columns:
                con.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(lower(username)) WHERE username IS NOT NULL")
        con.execute("UPDATE users SET username=lower(substr(email,1,instr(email,'@')-1)) WHERE username IS NULL AND instr(email,'@')>1 AND NOT EXISTS (SELECT 1 FROM users other WHERE other.id!=users.id AND lower(other.username)=lower(substr(users.email,1,instr(users.email,'@')-1)))")
        customer_columns = {row[1] for row in con.execute("PRAGMA table_info(customers)")}
        for name, definition in {
            "notes": "TEXT", "tags": "TEXT", "created_by_user_id": "INTEGER", "merged_into_id": "INTEGER", "search_key": "TEXT"
        }.items():
            if name not in customer_columns:
                con.execute(f"ALTER TABLE customers ADD COLUMN {name} {definition}")
        for row in con.execute("SELECT id,name FROM customers WHERE search_key IS NULL OR search_key='' ").fetchall():
            key = unicodedata.normalize("NFKD", row["name"]).encode("ascii", "ignore").decode("ascii").lower()
            con.execute("UPDATE customers SET search_key=? WHERE id=?", (key, row["id"]))
        con.execute("CREATE INDEX IF NOT EXISTS idx_customers_search ON customers(tenant_id,search_key)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_support_user ON support_codes(user_id)")
        appointment_columns = {row[1] for row in con.execute("PRAGMA table_info(appointments)")}
        for name, definition in {
            "cancellation_reason": "TEXT", "cancelled_at": "TEXT", "cancelled_by": "TEXT",
            "delay_minutes": "INTEGER NOT NULL DEFAULT 0", "delay_reason": "TEXT", "estimated_end_at": "TEXT",
        }.items():
            if name not in appointment_columns:
                con.execute(f"ALTER TABLE appointments ADD COLUMN {name} {definition}")
