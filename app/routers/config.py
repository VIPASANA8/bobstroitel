from fastapi import APIRouter, Request


router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
async def public_config(request: Request):
    settings = request.app.state.settings
    branding = settings.tenant_configs.get(settings.default_tenant_slug, {})
    return {
        "network_brand": "Poker8",
        "tenant": {
            "slug": settings.default_tenant_slug,
            "name": branding.get("name", "Poker8"),
            "support_url": branding.get("support_url"),
            "branding": branding.get("branding", {}),
        },
        "development_profiles": [
            {"telegram_user_id": user_id, "display_name": name}
            for user_id, name in sorted(settings.dev_profiles.items())
        ] if settings.environment == "development" else [],
    }
