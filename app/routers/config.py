from fastapi import APIRouter, Request


router = APIRouter(prefix="/api/config", tags=["config"])


def _login_bot(request: Request, tenant_slug: str) -> dict[str, str]:
    """What startup learned about this tenant's bot, or nothing yet."""
    return getattr(request.app.state, "telegram_login_bots", {}).get(tenant_slug, {})


@router.get("")
async def public_config(request: Request):
    settings = request.app.state.settings
    host = request.headers.get("host", "").split(":", 1)[0].lower()
    tenant_slug = getattr(request.app.state, "tenant_hosts", {}).get(host, settings.default_tenant_slug)
    branding = settings.tenant_configs.get(tenant_slug, {})
    return {
        "network_brand": "Poker8",
        # The browser has no initData, so this is how somebody arriving at the
        # site signs in as themselves rather than being turned away.
        # How somebody who arrived at the site gets in: the app first, and the
        # browser login for whoever would rather stay in the browser.
        "telegram_app_url": _login_bot(request, tenant_slug).get("app_url"),
        "telegram_login_bot": _login_bot(request, tenant_slug).get("username"),
        "open_access": settings.open_access,
        # Off on a deployment by design -- money there has to arrive through a
        # payment, not through /api/profile/play-top-up. The profile page reads
        # this so it can say so, instead of offering a button with a 404 behind
        # it (the exact trap v022-balance-topup.js was written to avoid).
        "self_top_up_enabled": settings.self_top_up_enabled,
        "cash_mode": settings.cash_mode,
        "play_room_creation_enabled": settings.legacy_play_rooms_enabled,
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
