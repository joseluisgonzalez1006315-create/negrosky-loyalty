from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Role = Literal["super_admin", "business_admin", "branch_admin", "worker"]


class LoginInput(BaseModel):
    identifier: str | None = None
    email: str | None = None
    password: str

    @model_validator(mode="after")
    def validate_identifier(self):
        if not (self.identifier or self.email):
            raise ValueError("Escribe tu usuario o correo")
        return self


class TenantInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(default="", max_length=200)
    setup_mode: Literal["admin", "owner", "shared"] = "owner"

class RaffleInput(BaseModel):
    tenant_id: int
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    image_url: str | None = Field(default=None, max_length=8_000_000)
    ticket_price: float = Field(default=0, ge=0)
    ticket_count: int = Field(default=100, ge=0, le=1000000)
    draw_at: str | None = None
    tickets_per_purchase: int = Field(default=1, ge=1, le=100)
    customer_ticket_limit: int | None = Field(default=None, ge=1, le=1000000)
class RaffleTicketInput(BaseModel):
    ticket_number: str = Field(min_length=1, max_length=20)
    customer_name: str = Field(min_length=2, max_length=120)
    customer_phone: str | None = Field(default=None, max_length=30)
class RaffleStatusInput(BaseModel):
    enabled: bool
class RouletteInput(BaseModel):
    tenant_id: int
    name: str = Field(min_length=2, max_length=120)
    prizes: list[str] = Field(min_length=2, max_length=50)
    difficulty: int = Field(default=50, ge=1, le=100)
    schedule: str | None = None
    enabled: bool = True

class RouletteStatusInput(BaseModel):
    enabled: bool

class TenantUpdate(TenantInput):
    pass


class BrandingInput(BaseModel):
    theme_key: Literal["custom", "food", "coffee", "beauty", "pets", "health", "fitness", "retail", "pool", "premium"] = "custom"
    display_name: str | None = Field(default=None, max_length=120)
    welcome_text: str = Field(default="Bienvenido a nuestro club de beneficios", min_length=3, max_length=180)
    primary_color: str = Field(default="#a970ff", pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str = Field(default="#7547d8", pattern=r"^#[0-9A-Fa-f]{6}$")
    button_color: str = Field(default="#7c3aed", pattern=r"^#[0-9A-Fa-f]{6}$")
    background_style: Literal["dark", "light", "custom"] = "dark"
    background_color: str = Field(default="#07070d", pattern=r"^#[0-9A-Fa-f]{6}$")
    background_same_frame: bool = True
    background_fit_desktop: Literal["cover", "contain"] = "cover"
    background_x_desktop: int = Field(default=50, ge=0, le=100)
    background_y_desktop: int = Field(default=50, ge=0, le=100)
    background_fit_mobile: Literal["cover", "contain"] = "cover"
    background_x_mobile: int = Field(default=50, ge=0, le=100)
    background_y_mobile: int = Field(default=50, ge=0, le=100)
    background_image_opacity: int = Field(default=100, ge=0, le=100)
    background_overlay_opacity: int = Field(default=35, ge=0, le=85)
    card_style: Literal["soft", "solid", "glass"] = "soft"
    card_shape: Literal["square", "rounded", "pill", "ticket", "cut", "diagonal", "double", "soft-shadow", "notched", "wave", "frame", "hex", "glass-border"] = "rounded"
    card_opacity: int = Field(default=94, ge=35, le=100)
    logo_shape: Literal["square", "rounded", "circle"] = "rounded"
    logo_fit: Literal["contain", "cover"] = "contain"
    logo_size: int = Field(default=64, ge=44, le=140)
    logo_opacity: int = Field(default=100, ge=20, le=100)
    logo_background_color: str = Field(default="#ffffff", pattern=r"^#[0-9A-Fa-f]{6}$")
    font_family: Literal["modern", "classic", "friendly", "compact"] = "modern"
    font_scale: int = Field(default=100, ge=85, le=125)
    text_color: str = Field(default="#f7f5ff", pattern=r"^#[0-9A-Fa-f]{6}$")
    button_shape: Literal["square", "rounded", "pill"] = "rounded"
    button_label: str = Field(default="Registrar mi compra", min_length=2, max_length=40)
    stamp_shape: Literal["circle", "rounded", "square"] = "circle"
    stamp_done_color: str = Field(default="#7547d8", pattern=r"^#[0-9A-Fa-f]{6}$")
    stamp_pending_color: str = Field(default="#252334", pattern=r"^#[0-9A-Fa-f]{6}$")
    progress_start_color: str = Field(default="#a970ff", pattern=r"^#[0-9A-Fa-f]{6}$")
    progress_end_color: str = Field(default="#7547d8", pattern=r"^#[0-9A-Fa-f]{6}$")
    progress_style: Literal["slim", "normal", "thick"] = "normal"
    show_profile: bool = True
    show_rewards: bool = True
    show_appointments: bool = True
    show_contact: bool = True
    show_business_hours: bool = True
    show_campaign_title: bool = True
    show_campaign_stamps: bool = True
    show_campaign_progress: bool = True
    show_campaign_reward: bool = True
    show_campaign_button: bool = True
    contact_phone: str | None = Field(default=None, max_length=30)
    whatsapp_number: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=180)
    instagram_url: str | None = Field(default=None, max_length=500)
    facebook_url: str | None = Field(default=None, max_length=500)
    tiktok_url: str | None = Field(default=None, max_length=500)
    website_url: str | None = Field(default=None, max_length=500)
    maps_url: str | None = Field(default=None, max_length=500)
    social_display_mode: Literal["icon", "label", "both"] = "both"
    social_size: Literal["small", "medium", "large"] = "medium"
    social_layout: Literal["inline", "floating"] = "inline"
    social_position: Literal["bottom-right", "bottom-left", "top-right", "top-left"] = "bottom-right"
    show_social_mobile: bool = True
    show_social_desktop: bool = True
    module_order_mobile: str = Field(default="contact,profile,campaigns,rewards,appointments", max_length=160)
    module_order_desktop: str = Field(default="contact,profile,campaigns,rewards,appointments", max_length=160)
    module_widths_mobile: str = Field(default="contact:100,profile:100,campaigns:100,rewards:100,appointments:100", max_length=200)
    module_widths_desktop: str = Field(default="contact:100,profile:50,campaigns:50,rewards:50,appointments:50", max_length=200)

    @field_validator("instagram_url", "facebook_url", "tiktok_url", "website_url", "maps_url")
    @classmethod
    def validate_public_url(cls, value):
        if value is None or not value.strip():
            return None
        value = value.strip()
        if not value.lower().startswith(("https://", "http://")):
            raise ValueError("Los enlaces deben comenzar por https:// o http://")
        return value

    @field_validator("contact_phone", "whatsapp_number", "address")
    @classmethod
    def clean_optional_text(cls, value):
        return value.strip() if value and value.strip() else None


class BrandingLogoInput(BaseModel):
    tenant_id: int | None = None
    data_url: str = Field(min_length=20, max_length=3_000_000)


class BrandingBackgroundInput(BaseModel):
    tenant_id: int | None = None
    data_url: str = Field(min_length=20, max_length=7_500_000)


class ProgramIconInput(BaseModel):
    data_url: str = Field(min_length=20, max_length=1_500_000)


class BranchInput(BaseModel):
    tenant_id: int | None = None
    name: str = Field(min_length=2, max_length=120)
    city: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=180)
    phone: str | None = Field(default=None, max_length=30)


class UserInput(BaseModel):
    tenant_id: int | None = None
    branch_id: int | None = None
    name: str = Field(min_length=2, max_length=120)
    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: str | None = Field(default=None, max_length=180)
    password: str = Field(min_length=10, max_length=128)
    role: Role


class UserUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    username: str = Field(min_length=3, max_length=50)
    email: str | None = Field(default=None, max_length=180)
    tenant_id: int | None = None
    branch_id: int | None = None
    role: Role


class UserStatusInput(BaseModel):
    status: Literal["active", "blocked"]


class WorkerAccessInput(BaseModel):
    tenant_id: int | None = None
    user_id: int | None = None
    permissions: dict[str, bool] = Field(default_factory=dict)
    schedule: list[dict] = Field(default_factory=list, max_length=7)


class PlatformAdInput(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    message: str | None = Field(default=None, max_length=500)
    image_url: str = Field(min_length=20, max_length=8_000_000)
    target_tenants: list[int] = Field(default_factory=list, max_length=500)
    starts_at: str | None = None
    ends_at: str | None = None
    ad_seconds: int = Field(default=5, ge=1, le=60)
    is_active: bool = True

class BusinessAdInput(BaseModel):
    tenant_id: int | None = None
    title: str = Field(min_length=2, max_length=120)
    message: str | None = Field(default=None, max_length=500)
    image_url: str = Field(min_length=20, max_length=8_000_000)
    starts_at: str | None = None
    ends_at: str | None = None
    ad_seconds: int = Field(default=5, ge=1, le=60)
    is_active: bool = True


class PasswordChangeInput(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)


class SupportCodeInput(BaseModel):
    minutes: int = Field(default=15, ge=5, le=60)


class SupportResetInput(BaseModel):
    identifier: str = Field(min_length=3, max_length=180)
    code: str = Field(pattern=r"^[0-9]{6}$")
    new_password: str = Field(min_length=10, max_length=128)


class AssistedCustomerInput(BaseModel):
    tenant_id: int | None = None
    branch_id: int | None = None
    phone: str = Field(pattern=r"^[0-9+ ]{7,20}$")
    name: str | None = Field(default=None, max_length=120)


class CustomerMetaInput(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)
    tags: str | None = Field(default=None, max_length=500)


class MergeCustomersInput(BaseModel):
    primary_id: int
    duplicate_id: int


class RestoreBackupInput(BaseModel):
    filename: str = Field(pattern=r"^negrosky_[0-9]{8}_[0-9]{6}(?:_[a-z]+)?\.db$")


class ResetPlatformInput(BaseModel):
    confirmation: str


class CustomerIdentifyInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(pattern=r"^[0-9]{10}$")
    marketing_consent: bool = False
    branch_id: int | None = None
    birth_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    birthday_consent: bool | None = None

class BirthdaySettingsInput(BaseModel):
    tenant_id: int | None = None
    enabled: bool = True
    days_before: int = Field(default=3, ge=0, le=30)
    monthly_limit: int = Field(default=0, ge=0, le=100000)
    promotion: str = Field(default="¡Feliz cumpleaños! Te tenemos una sorpresa especial.", min_length=3, max_length=500)

class NotificationSendInput(BaseModel):
    tenant_id: int
    audience: Literal["all", "selected", "loyal"] = "all"
    customer_ids: list[int] = Field(default_factory=list, max_length=200)
    title: str = Field(min_length=2, max_length=120)
    message: str = Field(min_length=2, max_length=1000)
    image_url: str | None = Field(default=None, max_length=2_500_000)
    branch_id: int | None = None

class PushSubscriptionInput(BaseModel):
    endpoint: str = Field(min_length=20, max_length=2000)
    p256dh: str = Field(min_length=20, max_length=500)
    auth: str = Field(min_length=10, max_length=500)

class CollaborationContactInput(BaseModel):
    tenant_id: int
    whatsapp: str = Field(min_length=7, max_length=30)
    visible: bool = True

class CollaborationCreateInput(BaseModel):
    tenant_id: int
    partner_tenant_id: int
    title: str = Field(min_length=2, max_length=120)
    message: str = Field(default="", max_length=500)
    image_url: str | None = Field(default=None, max_length=2_500_000)
    ends_at: str | None = Field(default=None, max_length=40)
    ad_seconds: int = Field(default=5, ge=1, le=60)

class CollaborationUpdateInput(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    message: str = Field(default="", max_length=500)
    image_url: str | None = Field(default=None, max_length=2_500_000)
    ends_at: str | None = Field(default=None, max_length=40)
    ad_seconds: int = Field(default=5, ge=1, le=60)

class CollaborationStatusInput(BaseModel):
    status: Literal["accepted", "rejected"]

class CollaborationActiveInput(BaseModel):
    active: bool


class LoyaltyProgramInput(BaseModel):
    tenant_id: int | None = None
    name: str = Field(min_length=2, max_length=120)
    target_purchases: int = Field(ge=2, le=100)
    reward_name: str = Field(min_length=2, max_length=160)
    progress_emoji: str = Field(default="⭐", min_length=1, max_length=16)
    reward_stock: int | None = Field(default=None, ge=1, le=1_000_000)
    reward_display: Literal["hidden", "unlimited", "quantity"] = "hidden"
    title_mode: Literal["inherit", "show", "hide"] = "inherit"
    stamps_mode: Literal["inherit", "show", "hide"] = "inherit"
    progress_mode: Literal["inherit", "show", "hide"] = "inherit"
    reward_mode: Literal["inherit", "show", "hide"] = "inherit"
    button_mode: Literal["inherit", "show", "hide"] = "inherit"

class LoyaltyProgramUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    target_purchases: int = Field(ge=2, le=100)
    reward_name: str = Field(min_length=2, max_length=160)
    progress_emoji: str = Field(default="⭐", min_length=1, max_length=16)
    reward_stock: int | None = Field(default=None, ge=1, le=1_000_000)
    reward_display: Literal["hidden", "unlimited", "quantity"] = "hidden"
    title_mode: Literal["inherit", "show", "hide"] = "inherit"
    stamps_mode: Literal["inherit", "show", "hide"] = "inherit"
    progress_mode: Literal["inherit", "show", "hide"] = "inherit"
    reward_mode: Literal["inherit", "show", "hide"] = "inherit"
    button_mode: Literal["inherit", "show", "hide"] = "inherit"

class LoyaltyProgramStatusUpdate(BaseModel):
    active: bool


class OperationTokenInput(BaseModel):
    program_id: int

class RewardBatchInput(BaseModel):
    program_id: int
    quantity: int = Field(ge=1, le=50)


class ValidateOperationInput(BaseModel):
    code: str = Field(pattern=r"^[0-9]{6}$")


class BusinessHourInput(BaseModel):
    weekday: int = Field(ge=0, le=6)
    enabled: bool = True
    opens_at: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    closes_at: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class ServiceSettingsInput(BaseModel):
    manual_closed: bool = False
    closed_message: str = Field(min_length=5, max_length=300)
    timezone: str = Field(default="America/Bogota", min_length=3, max_length=80)
    schedule_mode: Literal["inherit", "custom"] = "inherit"
    hours: list[BusinessHourInput] = Field(min_length=7, max_length=7)
    modules: dict[str, bool] = {}


class ModuleSettingsInput(BaseModel):
    tenant_id: int
    branch_id: int | None = None
    modules: dict[str, bool] = Field(default_factory=dict)


class CopyServiceSettingsInput(BaseModel):
    tenant_id: int
    source_branch_id: int | None = None
    target_branch_ids: list[int] = Field(min_length=1, max_length=100)


class AppointmentServiceInput(BaseModel):
    tenant_id: int | None = None
    branch_id: int | None = None
    name: str = Field(min_length=2, max_length=120)
    duration_minutes: int = Field(default=30, ge=10, le=480)
    price: int | None = Field(default=None, ge=0, le=100_000_000)


class AppointmentServiceStatusInput(BaseModel):
    active: bool


class AppointmentBookingInput(BaseModel):
    branch_id: int
    service_id: int
    starts_at: str = Field(min_length=16, max_length=40)
    notes: str | None = Field(default=None, max_length=500)


class AppointmentStatusInput(BaseModel):
    status: Literal["scheduled", "confirmed", "completed", "cancelled", "no_show"]


class AppointmentCancelInput(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class AppointmentDelayInput(BaseModel):
    delay_minutes: int = Field(ge=0, le=180)
    reason: str | None = Field(default=None, max_length=250)

class TimeServiceInput(BaseModel):
    tenant_id: int | None = None
    branch_id: int | None = None
    name: str = Field(min_length=2, max_length=120)
    duration_minutes: int = Field(default=60, ge=5, le=1440)
    price: int = Field(default=0, ge=0, le=100_000_000)
class TimeServiceStatusInput(BaseModel): active: bool
class TimeSessionStartInput(BaseModel):
    tenant_id: int | None = None
    branch_id: int
    service_id: int
    customer_id: int
class TimeSessionCloseInput(BaseModel): notes: str | None = Field(default=None, max_length=500)
