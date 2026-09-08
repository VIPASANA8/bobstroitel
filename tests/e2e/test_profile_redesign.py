"""Profile layout and independent API states, with deterministic player data."""
import re

import pytest
from playwright.sync_api import expect, sync_playwright

from online.achievements import ACHIEVEMENTS

pytestmark = pytest.mark.e2e


def swipe(page, selector, *, direction='left', pointer_type='touch', distance=150, dy=0,
          end_pointer_id=1, cancel=False):
    start_x = 280 if direction == 'left' else 80
    end_x = start_x - distance if direction == 'left' else start_x + distance
    target = page.locator(selector)
    if pointer_type == 'touch':
        target.evaluate("""(element, gesture) => {
            const touch = (identifier, x, y) => new Touch({
                identifier, target: element, clientX: x, clientY: y,
                screenX: x, screenY: y, pageX: x, pageY: y,
            });
            const start = touch(1, gesture.startX, 100);
            element.dispatchEvent(new TouchEvent('touchstart', {
                bubbles: true, cancelable: true, touches: [start], changedTouches: [start],
            }));
            if (gesture.cancel) {
                element.dispatchEvent(new TouchEvent('touchcancel', {
                    bubbles: true, cancelable: false, touches: [], changedTouches: [start],
                }));
            }
            const end = touch(gesture.endId, gesture.endX, 100 + gesture.dy);
            element.dispatchEvent(new TouchEvent('touchend', {
                bubbles: true, cancelable: true, touches: [], changedTouches: [end],
            }));
        }""", dict(startX=start_x, endX=end_x, endId=end_pointer_id,
                     dy=dy, cancel=cancel))
        return
    target.dispatch_event('pointerdown', {
        'pointerType': pointer_type, 'pointerId': 1, 'isPrimary': True,
        'clientX': start_x, 'clientY': 100, 'buttons': 1,
    })
    if cancel:
        target.dispatch_event('pointercancel', {
            'pointerType': pointer_type, 'pointerId': 1, 'isPrimary': True,
            'clientX': start_x, 'clientY': 100, 'buttons': 0,
        })
    target.dispatch_event('pointerup', {
        'pointerType': pointer_type, 'pointerId': end_pointer_id, 'isPrimary': True,
        'clientX': end_x, 'clientY': 100 + dy, 'buttons': 0,
    })


def assert_swipe_helper_loaded(page):
    assert page.evaluate("typeof window.Poker8SwipeNav === 'function'")


def native_touch_swipe(page, selector, *, direction='left', distance=150, dy=0):
    page.set_viewport_size({'width': 390, 'height': 900})
    box = page.locator(selector).bounding_box()
    assert box
    start_x = min(box['x'] + box['width'] - 20, 300) if direction == 'left' else max(box['x'] + 20, 80)
    end_x = start_x - distance if direction == 'left' else start_x + distance
    start_y = box['y'] + box['height'] / 2
    session = page.context.new_cdp_session(page)
    session.send('Emulation.setTouchEmulationEnabled', {'enabled': True, 'maxTouchPoints': 5})
    session.send('Input.dispatchTouchEvent', {
        'type': 'touchStart', 'touchPoints': [{'x': start_x, 'y': start_y, 'id': 1}],
    })
    session.send('Input.dispatchTouchEvent', {
        'type': 'touchMove', 'touchPoints': [{'x': end_x, 'y': start_y + dy, 'id': 1}],
    })
    session.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    session.detach()


def multi_touch_swipe(page, selector):
    page.locator(selector).evaluate("""element => {
        const touch = (identifier, x) => new Touch({
            identifier, target: element, clientX: x, clientY: 100,
            screenX: x, screenY: 100, pageX: x, pageY: 100,
        });
        const first = touch(1, 280);
        const second = touch(2, 240);
        element.dispatchEvent(new TouchEvent('touchstart', {
            bubbles: true, cancelable: true,
            touches: [first, second], changedTouches: [first, second],
        }));
        const firstEnd = touch(1, 100);
        const secondEnd = touch(2, 60);
        element.dispatchEvent(new TouchEvent('touchend', {
            bubbles: true, cancelable: true,
            touches: [], changedTouches: [firstEnd, secondEnd],
        }));
    }""")


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
        '/api/profile/hands': dict(hands=[dict(hand_id=f'play-{n}', completed_at='2026-08-31T09:20:00Z',
                                             players=[dict(you=True, net_units=(1 if n % 2 else -1) * 450), {}]) for n in range(8)]),
        '/api/profile/cash-hands': dict(hands=[dict(hand_id=f'cash-{n}', completed_at=f'2026-08-31T10:0{n}:00Z',
                                                       players=[dict(you=True, net_micros=(1 if n else -1) * 200000), {}]) for n in range(2)]),
        '/api/profile/play-journal': dict(entries=[
            dict(kind='faucet_grant', amount_units=100000, created_at='2026-08-31T09:00:00Z'),
            dict(kind='settlement', reference_id='play-0', amount_units=-450, created_at='2026-08-31T09:20:00Z'),
        ]),
        '/api/cube/history': dict(rounds=[dict(round_id='cube-1', selected=[2, 4], roll=4, won=True,
                                               net_micros=300000, created_at='2026-08-31T10:15:00Z')]),
        '/api/cash/wallet': dict(available_usdt='19.01', available_units='190.1', escrow_usdt='0', escrow_units='0',
                                 withdrawal_usdt='2.50', withdrawal_units='25', journal=[
                                     dict(id='deposit-1', scope='c2c', kind='deposit', amount_micros=1000000, created_at='2026-08-31T08:00:00Z'),
                                     dict(id='payout-1', scope='withdrawal-payout', kind='payout', amount_micros=-500000, created_at='2026-08-31T08:30:00Z'),
                                 ]),
        '/api/cash/operations': dict(entries=[
            dict(id='deposit-1', scope='c2c', kind='deposit', amount_micros=1000000, created_at='2026-08-31T08:00:00Z'),
            dict(id='payout-1', scope='withdrawal-payout', kind='payout', amount_micros=-500000, created_at='2026-08-31T08:30:00Z'),
        ]),
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
            from urllib.parse import parse_qs, urlparse
            parsed = urlparse(route.request.url)
            path = parsed.path
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
            payload = (data.get('/api/profile/cash-hands')
                       if path == '/api/profile/hands' and parse_qs(parsed.query).get('asset') == ['CASH_USDT']
                       else data.get(path))
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
    page.locator('#playModeTab').click()
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
    expect(page.locator('#allHistory .history-row:visible')).to_have_count(5)
    page.get_by_role('button', name='Вся история').click()
    expect(page.locator('#allHistory .history-row:visible')).to_have_count(14)
    page.get_by_role('tab', name='POKER', exact=True).click()
    expect(page.locator('#pokerHistory')).to_contain_text('Начисление')
    expect(page.locator('#pokerHistory')).to_contain_text('Тренировочные фишки')
    page.get_by_role('tab', name='POKER', exact=True).press('ArrowRight')
    expect(page.get_by_role('tab', name='Операции', exact=True)).to_be_focused()
    expect(page.locator('#operationsHistory')).to_contain_text('Пополнение')
    expect(page.locator('#operationsHistory')).to_contain_text('Вывод средств')
    page.locator('#playModeTab').click()
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
    page.get_by_role('tab', name='Профиль Poker', exact=True).click()
    expect(page.locator('#missionsError')).to_contain_text('Не удалось загрузить')
    expect(page.locator('#statsGrid')).to_contain_text('148,5')
    expect(page.locator('#achievementList > :visible')).to_have_count(6)
    page.locator('#cashModeTab').click()
    page.get_by_role('tab', name='POKER', exact=True).click()
    expect(page.locator('#pokerHistory')).to_contain_text('Начисление')
    expect(page.locator('#pokerHistory')).to_contain_text('Расчёт раздачи')
    expect(page.locator('#pokerHistory')).to_contain_text('Не удалось загрузить часть истории POKER')


def test_failed_cube_history_does_not_claim_that_cube_is_empty(profile_page):
    page, data, _, server = profile_page
    data['/api/cube/history'] = None
    page.goto(server + '/static/profile.html')
    page.get_by_role('tab', name='CUBE', exact=True).click()
    expect(page.locator('#cubeHistory')).to_contain_text('Не удалось загрузить историю CUBE')
    expect(page.locator('#cubeHistory')).not_to_contain_text('Игр в CUBE пока нет')


def test_empty_stats_are_not_presented_as_a_measured_winrate(profile_page):
    page, data, _, server = profile_page
    data['/api/profile/stats'].update(hands=0, result_hands=0, net_bb=0, bb_per_100=None,
                                     sessions=0, days_played=0, best_day=None, worst_day=None)
    data['/api/profile']['active_table_id'] = None
    page.goto(server + '/static/profile.html#topup')
    page.locator('#playModeTab').click()
    expect(page.locator('#statsEmpty')).to_be_visible()
    expect(page.locator('#statBbPer100')).to_have_text('—')
    expect(page.locator('#returnToTable')).to_be_hidden()
    expect(page.locator('#topupNote')).to_be_empty()


def test_enabled_topup_keeps_working_without_random_uuid(profile_page):
    page, data, calls, server = profile_page
    data['/api/config']['self_top_up_enabled'] = True
    page.add_init_script("Object.defineProperty(Crypto.prototype, 'randomUUID', {value: undefined})")
    page.goto(server + '/static/profile.html#topup')
    page.locator('#playModeTab').click()
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
    expect(page.locator('#profileError')).to_contain_text('Профиль временно недоступен')
    expect(page.locator('[aria-busy="true"]')).to_have_count(0)
    expect(page.locator('#profileLoading')).to_be_hidden()
    expect(page.locator('#topupAmount')).to_be_hidden()
    expect(page.locator('[data-reroll]')).to_have_count(0)


def test_cube_cashier_has_one_active_slot_and_one_blank_reserved_slot(profile_page):
    page, _, _, server = profile_page
    page.goto(server + '/static/profile.html?app=cube#cash')

    cash = page.get_by_role('tab', name='USDT-касса $$$', exact=True)
    reserved = page.locator('#playModeTab')
    expect(cash).to_be_visible()
    expect(cash).to_have_attribute('aria-selected', 'true')
    expect(reserved).to_be_visible()
    expect(reserved).to_be_disabled()
    expect(reserved).to_have_js_property('disabled', True)
    expect(reserved).to_have_js_property('tabIndex', -1)
    expect(reserved).to_have_text('')
    expect(page.get_by_role('tab', name='', exact=True)).to_have_count(1)
    cash_box = cash.bounding_box()
    reserved_box = reserved.bounding_box()
    assert cash_box and reserved_box
    assert abs(cash_box['width'] - reserved_box['width']) <= 1

    reserved.evaluate('element => element.click()')
    expect(cash).to_have_attribute('aria-selected', 'true')
    expect(reserved).to_have_attribute('aria-selected', 'false')
    expect(page.locator('#cashSection')).to_be_visible()
    expect(page.locator('#playSection')).to_be_hidden()

    reserved.focus()
    expect(reserved).not_to_be_focused()
    page.keyboard.press('Enter')
    expect(cash).to_have_attribute('aria-selected', 'true')
    expect(reserved).to_have_attribute('aria-selected', 'false')
    expect(page.locator('#cashSection')).to_be_visible()
    expect(page.locator('#playSection')).to_be_hidden()


@pytest.mark.parametrize('failure', ['wallet', 'auth'])
def test_cube_cashier_failure_keeps_a_visible_error_and_hides_dead_controls(profile_page, failure):
    page, data, _, server = profile_page
    if failure == 'wallet':
        data['/api/cash/wallet'] = None
    else:
        data['/api/profile'] = None
        data['/api/config'] = dict(open_access=False, development_profiles=[])

    page.goto(server + '/static/profile.html?app=cube#cash')

    cash = page.locator('#cashModeTab')
    expect(cash).to_be_visible()
    expect(cash).to_have_attribute('aria-selected', 'true')
    expect(page.locator('#cashSection')).to_be_visible()
    expect(page.locator('#cashError')).to_be_visible()
    expect(page.locator('#cashError')).to_contain_text(
        'Войдите через Telegram' if failure == 'auth' else 'USDT-касса временно недоступна')
    expect(page.locator('.cash-wallet-grid')).to_be_hidden()
    expect(page.locator('.cash-actions')).to_be_hidden()
    expect(page.locator('#cashHistory')).to_be_hidden()
    expect(page.locator('#cashSection [aria-busy="true"]')).to_have_count(0)
    expect(page.locator('#cashSection')).not_to_contain_text('Загружаем историю')


def test_cube_cashier_shows_pending_usdt_without_cash_conversion(profile_page):
    page, _, _, server = profile_page
    page.goto(server + '/static/profile.html?app=cube#cash')

    expect(page.locator('#profileCashWithdrawal')).to_have_text('2.50 USDT')
    expect(page.locator('#profileCashWithdrawalUsdt')).to_have_text('')


def test_cube_cashier_play_card_opens_cube(profile_page):
    page, _, _, server = profile_page
    page.goto(server + '/static/profile.html?app=cube#cash')

    escrow_card = page.locator('#profileCashEscrow').locator('..')
    expect(escrow_card).to_have_attribute('role', 'link')
    expect(escrow_card).to_have_accessible_name('Играть')
    expect(escrow_card.locator('span')).to_have_text('Играть')
    expect(escrow_card).not_to_contain_text('За столами')
    escrow_card.click()
    expect(page).to_have_url(server + '/cube')


def test_cube_cashier_play_card_opens_cube_from_keyboard(profile_page):
    page, _, _, server = profile_page
    page.goto(server + '/static/profile.html?app=cube#cash')

    escrow_card = page.locator('#profileCashEscrow').locator('..')
    escrow_card.focus()
    expect(escrow_card).to_be_focused()
    escrow_card.press('Enter')
    expect(page).to_have_url(server + '/cube')


def test_poker_cashier_puts_pending_usdt_before_cash(profile_page):
    page, _, _, server = profile_page
    page.goto(server + '/static/profile.html?app=poker#cash')

    expect(page.locator('#profileCashWithdrawal')).to_have_text('2.50 USDT')
    expect(page.locator('#profileCashWithdrawalUsdt')).to_have_text('25 CASH')


@pytest.mark.parametrize(
    ('start', 'other_product', 'other_label', 'other_href', 'brand_product', 'brand_href'),
    [
        ('/static/profile.html?app=poker', 'CUBE', 'В CUBE', '/cube', 'poker', '/'),
        ('/static/profile.html?app=cube#cash', 'POKER', 'В POKER', '/', 'cube', '/cube'),
    ],
)
def test_cashier_headers_link_to_the_other_game_and_their_own_brand(
        profile_page, start, other_product, other_label, other_href, brand_product, brand_href):
    page, _, _, server = profile_page
    page.goto(server + start)

    header = page.locator('.profile-header')
    back = header.get_by_role('link', name=re.compile(other_product, re.I))
    brand = header.get_by_role('link', name=re.compile(brand_product, re.I))
    expect(back.locator('#backToProductLabel')).to_have_text(other_label)
    expect(back.locator('.ui-arrow')).to_be_visible()
    expect(back).to_have_attribute('href', other_href)
    expect(brand).to_have_attribute('href', brand_href)
    brand.focus()
    expect(brand).to_be_focused()
    back.focus()
    expect(back).to_be_focused()
    back.press('Enter')
    expect(page).to_have_url(server + other_href)


def test_cube_game_header_links_to_poker_and_its_own_brand(profile_page):
    page, _, _, server = profile_page
    page.goto(server + '/cube')

    header = page.locator('.cube-header')
    poker = header.get_by_role('link', name=re.compile('POKER', re.I))
    brand = header.get_by_role('link', name=re.compile('CUBE', re.I))
    expect(poker).to_contain_text('В POKER')
    expect(poker.locator('.ui-arrow')).to_be_visible()
    expect(poker).to_have_attribute('href', '/')
    expect(brand).to_have_attribute('href', '/cube')
    brand.focus()
    expect(brand).to_be_focused()
    poker.focus()
    expect(poker).to_be_focused()
    poker.press('Enter')
    expect(page).to_have_url(server + '/')


@pytest.mark.parametrize('width', [390, 1280])
def test_cube_result_strip_is_above_and_clear_of_the_cube(profile_page, width):
    page, _, _, server = profile_page
    page.set_viewport_size({'width': width, 'height': 900})
    page.goto(server + '/cube')

    card = page.locator('#diceCard').bounding_box()
    result = page.locator('#resultLine').bounding_box()
    cube = page.locator('.cube-scene').bounding_box()
    assert card and result and cube
    assert abs(result['y'] - card['y']) <= 2
    assert cube['y'] - (result['y'] + result['height']) >= 12


def test_native_touch_swipe_opens_the_poker_cashier(profile_page):
    page, _, _, server = profile_page
    page.goto(server + '/')
    assert_swipe_helper_loaded(page)

    native_touch_swipe(page, '.section-heading')

    expect(page).to_have_url(server + '/static/profile.html?app=poker#cash')


@pytest.mark.parametrize(
    ('start', 'selector', 'direction', 'destination'),
    [
        ('/', '#tableGrid', 'left', '/static/profile.html?app=poker#cash'),
        ('/cube', '#cubeMain', 'left', '/static/profile.html?app=cube#cash'),
        ('/static/profile.html?app=poker#cash', '#profileMain', 'right', '/'),
        ('/static/profile.html?app=cube#cash', '#profileMain', 'right', '/cube'),
    ],
)
def test_touch_swipes_follow_each_game_cashier_route(
        profile_page, start, selector, direction, destination):
    page, _, _, server = profile_page
    page.goto(server + start)
    assert_swipe_helper_loaded(page)
    if start.startswith('/static/profile.html'):
        expect(page.locator('#cashSection')).to_be_visible()

    swipe(page, selector, direction=direction)

    expect(page).to_have_url(server + destination)


def test_poker_cashier_swipe_uses_the_panel_selected_after_load(profile_page):
    page, _, _, server = profile_page
    page.goto(server + '/static/profile.html?app=poker')
    expect(page.locator('#cashSection')).to_be_visible()

    swipe(page, '#profileMain', direction='right')

    expect(page).to_have_url(server + '/')


def test_poker_profile_panel_disables_cashier_swipe_with_cash_hash(profile_page):
    page, _, _, server = profile_page
    start = server + '/static/profile.html?app=poker#cash'
    page.goto(start)
    page.locator('#playModeTab').click()
    expect(page.locator('#cashSection')).to_be_hidden()

    swipe(page, '#profileMain', direction='right')
    page.wait_for_timeout(100)

    assert page.url == start


@pytest.mark.parametrize(
    ('start', 'selector', 'wrong_direction'),
    [
        ('/', '#tableGrid', 'right'),
        ('/cube', '#cubeMain', 'right'),
        ('/static/profile.html?app=poker#cash', '#profileMain', 'left'),
        ('/static/profile.html?app=cube#cash', '#profileMain', 'left'),
    ],
)
def test_swipes_in_the_wrong_direction_do_not_leave_the_page(
        profile_page, start, selector, wrong_direction):
    page, _, _, server = profile_page
    page.goto(server + start)
    assert_swipe_helper_loaded(page)

    swipe(page, selector, direction=wrong_direction)
    page.wait_for_timeout(100)

    assert page.url == server + start


@pytest.mark.parametrize(
    ('pointer_type', 'distance', 'dy'),
    [
        ('mouse', 150, 0),
        ('touch', 50, 0),
        ('touch', 100, 180),
    ],
)
def test_swipe_navigation_rejects_mouse_short_and_vertical_gestures(
        profile_page, pointer_type, distance, dy):
    page, _, _, server = profile_page
    page.goto(server + '/')
    assert_swipe_helper_loaded(page)

    swipe(page, '#tableGrid', pointer_type=pointer_type, distance=distance, dy=dy)
    page.wait_for_timeout(100)

    assert page.url == server + '/'


@pytest.mark.parametrize(
    ('cancel', 'end_pointer_id'),
    [
        (True, 1),
        (False, 2),
    ],
)
def test_swipe_navigation_rejects_cancelled_and_mismatched_pointers(
        profile_page, cancel, end_pointer_id):
    page, _, _, server = profile_page
    page.goto(server + '/')
    assert_swipe_helper_loaded(page)

    swipe(page, '#tableGrid', cancel=cancel, end_pointer_id=end_pointer_id)
    page.wait_for_timeout(100)

    assert page.url == server + '/'


def test_swipe_navigation_rejects_multi_touch_gestures(profile_page):
    page, _, _, server = profile_page
    page.goto(server + '/')

    multi_touch_swipe(page, '#tableGrid')
    page.wait_for_timeout(100)

    assert page.url == server + '/'


@pytest.mark.parametrize(
    ('start', 'selector', 'direction'),
    [
        ('/', '.game-tab-cube', 'left'),
        ('/', '#quickPlay', 'left'),
        ('/static/profile.html?app=poker#cash', '#withdrawUsdt', 'right'),
        ('/static/profile.html?app=poker#cash', 'label[for="withdrawUsdt"]', 'right'),
        ('/static/profile.html?app=poker#cash', '#topupDetails summary', 'right'),
        ('/cube', '#cubeCanvas', 'left'),
    ],
)
def test_swipes_starting_on_interactive_controls_are_ignored(
        profile_page, start, selector, direction):
    page, _, _, server = profile_page
    page.goto(server + start)
    assert_swipe_helper_loaded(page)
    if start.startswith('/static/profile.html'):
        expect(page.locator('#cashSection')).to_be_visible()

    swipe(page, selector, direction=direction)
    page.wait_for_timeout(100)

    assert page.url == server + start


def test_swipes_starting_inside_an_open_dialog_are_ignored(profile_page):
    page, _, _, server = profile_page
    start = server + '/static/profile.html?app=poker#cash'
    page.goto(start)
    expect(page.locator('#cashSection')).to_be_visible()
    page.locator('#depositDialog').evaluate('dialog => dialog.showModal()')

    swipe(page, '#depositDialog h2', direction='right')
    page.wait_for_timeout(100)

    assert page.url == start
