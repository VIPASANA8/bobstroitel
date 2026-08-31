"""Profile layout and independent API states, with deterministic player data."""
import pytest
from playwright.sync_api import expect, sync_playwright

from online.achievements import ACHIEVEMENTS

pytestmark = pytest.mark.e2e


def profile_data():
    achievements = []
    for item in ACHIEVEMENTS.values():
        tier = 1 if item.code in ('straight', 'flush', 'full_house') else 0
        progress = 62 if item.code == 'grind' else tier
        achievements.append(dict(code=item.code, title='???' if item.secret else item.title,
                                 rarity=item.rarity, secret=item.secret, tier=tier, tiers=len(item.tiers),
                                 progress=progress, next_threshold=None if tier else item.tiers[0]))
    return {
        '/api/profile': dict(display_name='MARTAXER', telegram_user_id=101, level=8, rank='PLAYER',
                             xp=2380, xp_to_next_level=200, wins=819, hands_played=2482,
                             available_units=128450, active_table_stack_units=3850, active_table_id='micro-a'),
        '/api/config': dict(open_access=True, development_profiles=[], self_top_up_enabled=False),
        '/api/profile/stats': dict(hands=1200, result_hands=960, hands_won=400, sessions=32, days_played=18,
                                   net_bb=148.5, bb_per_100=15.5, biggest_pot_bb=168,
                                   longest_session_minutes=84, confidence='medium',
                                   best_day=dict(day='2026-08-30', net_bb=72.5),
                                   worst_day=dict(day='2026-08-29', net_bb=-23)),
        '/api/profile/missions': dict(completed=1, completion_xp=50, resets_in_seconds=7200, reroll_available=True,
                                     missions=[dict(slot='volume', title='Сыграйте 20 раздач', progress=20, target=20, xp=50, done=True),
                                               dict(slot='session', title='Проведите 30 минут за столом', progress=18, target=30, xp=55, done=False),
                                               dict(slot='variety', title='Сыграйте с четырёх разных позиций', progress=2, target=4, xp=60, done=False)]),
        '/api/profile/achievements': dict(completed=3, total=12, achievement_points=30, achievements=achievements),
        '/api/profile/hands': dict(hands=[dict(completed_at='2026-08-31T09:20:00Z',
                                             players=[dict(you=True, net_units=(1 if n % 2 else -1) * 450), {}]) for n in range(8)]),
        '/api/profile/play-journal': dict(entries=[dict(kind='faucet_grant', amount_units=100000, created_at='2026-08-31T09:00:00Z')]),
    }


@pytest.fixture
def profile_page(online_server):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        data = profile_data()
        calls = []
        signed_in = False

        def api(route):
            nonlocal signed_in
            from urllib.parse import urlparse
            path = urlparse(route.request.url).path
            calls.append((route.request.method, path))
            if path == '/api/auth/guest':
                signed_in = True
                return route.fulfill(json={'display_name': 'MARTAXER', 'telegram_user_id': 101})
            if path == '/api/profile' and not signed_in:
                return route.fulfill(status=401, json={})
            if path.endswith('/reroll'):
                data['/api/profile/missions']['reroll_available'] = False
                return route.fulfill(json={'ok': True})
            if path == '/api/profile/play-top-up':
                amount = route.request.post_data_json['amount_units']
                assert route.request.post_data_json['request_id']
                data['/api/profile']['available_units'] += amount
                return route.fulfill(json={'available_units': data['/api/profile']['available_units']})
            payload = data.get(path)
            return route.fulfill(status=200 if payload is not None else 503, json=payload or {})

        page.route('**/api/**', api)
        page.route('https://telegram.org/**', lambda route: route.fulfill(body='', content_type='text/javascript'))
        # Typography is checked visually with the real fonts; interaction tests
        # must not wait on a third-party CDN before local scripts can execute.
        page.route('https://fonts.googleapis.com/**', lambda route: route.fulfill(body='', content_type='text/css'))
        yield page, data, calls, online_server
        browser.close()


@pytest.mark.parametrize('width', [360, 390, 768, 1280])
def test_profile_has_one_summary_and_fits_the_viewport(profile_page, width):
    page, data, _, server = profile_page
    data['/api/profile']['display_name'] = 'ОченьДлинноеИмяИгрокаБезПробеловДляПроверки'
    page.set_viewport_size({'width': width, 'height': 900})
    page.goto(server + '/static/profile.html')
    expect(page.locator('#levelBadge')).to_have_text('8')
    expect(page.locator('#missionList .mission')).to_have_count(3)
    expect(page.locator('#returnToTable')).to_be_visible()
    expect(page.locator('#topupAmount')).to_be_hidden()
    assert page.locator('#xp').count() == 1
    assert page.locator('#statHands, #statHandsWon').count() == 0
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert page.locator('#achievementList > :visible').count() == 6
    expect(page.locator('#profileLoading')).to_be_hidden()


def test_history_and_collection_expand_without_losing_their_data(profile_page):
    page, _, calls, server = profile_page
    page.goto(server + '/static/profile.html')
    expect(page.locator('#handHistory .history-row:visible')).to_have_count(5)
    page.get_by_role('button', name='Все раздачи').click()
    expect(page.locator('#handHistory .history-row:visible')).to_have_count(8)
    page.get_by_role('tab', name='Операции').click()
    expect(page.locator('#handHistory')).to_be_hidden()
    expect(page.locator('#ledger')).to_contain_text('Начисление')
    page.get_by_role('tab', name='Операции').press('ArrowLeft')
    expect(page.get_by_role('tab', name='Раздачи')).to_be_focused()
    expect(page.locator('#handHistory')).to_be_visible()
    page.get_by_role('button', name='Все достижения').click()
    expect(page.locator('#achievementList > :visible')).to_have_count(12)
    assert 'Роял' not in page.locator('#achievementList').inner_text()
    assert 'ROYAL' not in page.locator('#achievementList').inner_text()
    page.get_by_role('button', name='Заменить: Проведите 30 минут за столом', exact=True).click()
    expect(page.locator('[data-reroll]')).to_have_count(0)
    assert sum(method == 'POST' and path.endswith('/reroll') for method, path in calls) == 1
    page.get_by_text('Как считается результат', exact=True).click()
    expect(page.locator('#statsAccounting')).to_be_visible()
    expect(page.locator('#statsAccounting')).to_contain_text('1 200')
    expect(page.locator('#statsAccounting')).to_contain_text('400')


def test_one_failed_section_does_not_blank_the_profile(profile_page):
    page, data, _, server = profile_page
    data['/api/profile/missions'] = None
    data['/api/profile/hands'] = None
    page.goto(server + '/static/profile.html')
    expect(page.locator('#missionsError')).to_contain_text('Не удалось загрузить')
    expect(page.locator('#statsGrid')).to_contain_text('148,5')
    expect(page.locator('#achievementList > :visible')).to_have_count(6)
    page.get_by_role('tab', name='Операции').click()
    expect(page.locator('#ledger')).to_contain_text('Начисление')


def test_empty_stats_are_not_presented_as_a_measured_winrate(profile_page):
    page, data, _, server = profile_page
    data['/api/profile/stats'].update(hands=0, result_hands=0, net_bb=0, bb_per_100=None,
                                     sessions=0, days_played=0, best_day=None, worst_day=None)
    data['/api/profile']['active_table_id'] = None
    page.goto(server + '/static/profile.html#topup')
    expect(page.locator('#statsEmpty')).to_be_visible()
    expect(page.locator('#statBbPer100')).to_have_text('—')
    expect(page.locator('#returnToTable')).to_be_hidden()
    expect(page.locator('#topup')).to_contain_text('Пополнение пока недоступно')


def test_enabled_topup_keeps_working_without_random_uuid(profile_page):
    page, data, calls, server = profile_page
    data['/api/config']['self_top_up_enabled'] = True
    page.add_init_script("Object.defineProperty(Crypto.prototype, 'randomUUID', {value: undefined})")
    page.goto(server + '/static/profile.html#topup')
    expect(page.locator('#topupAmount')).to_be_visible()
    page.locator('#topupAmount').fill('250')
    page.get_by_role('button', name='Пополнить', exact=True).click()
    expect(page.locator('#walletBalance')).to_have_text('1 534,50')
    expect(page.locator('#topupNote')).to_contain_text('Зачислено')
    assert calls.count(('POST', '/api/profile/play-top-up')) == 1


def test_max_level_and_losses_keep_their_meaning(profile_page):
    page, data, _, server = profile_page
    data['/api/profile'].update(level=50, xp=45000, rank='VETERAN', xp_to_next_level=None)
    data['/api/profile/stats'].update(net_bb=-148.5, bb_per_100=-15.5)
    page.goto(server + '/static/profile.html')
    expect(page.locator('#levelProgress')).to_have_text('Максимальный уровень')
    expect(page.locator('#statNetBb')).to_have_class('down')
    expect(page.locator('#statBbPer100')).to_have_text('-15,5')


def test_login_failure_finishes_loading_and_offers_no_active_controls(profile_page):
    page, data, _, server = profile_page
    data['/api/profile'] = None
    page.goto(server + '/static/profile.html')
    expect(page.locator('#profileError')).to_contain_text('Профиль не загрузился')
    expect(page.locator('[aria-busy="true"]')).to_have_count(0)
    expect(page.locator('#profileLoading')).to_be_hidden()
    expect(page.locator('#topupAmount')).to_be_hidden()
    expect(page.locator('[data-reroll]')).to_have_count(0)
