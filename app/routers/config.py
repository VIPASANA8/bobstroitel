from fastapi import APIRouter, Request


router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
async def public_config(request: Request):
    settings = request.app.state.settings
    host = request.headers.get("host", "").split(":", 1)[0].lower()
    tenant_slug = getattr(request.app.state, "tenant_hosts", {}).get(host, settings.default_tenant_slug)
    branding = settings.tenant_configs.get(tenant_slug, {})
    return {
        "network_brand": "Poker8",
        "tenant": {
            "slug": tenant_slug,
            "name": branding.get("name", "Poker8"),
            "support_url": branding.get("support_url"),
            "branding": branding.get("branding", {}),
        },
        "development_profiles": [
            {"telegram_user_id": user_id, "display_name": name}
            for user_id, name in sorted(settings.dev_profiles.items())
        ] if settings.environment == "development" else [],
    }
