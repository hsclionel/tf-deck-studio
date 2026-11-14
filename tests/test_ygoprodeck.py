from tfcore import deckcatalog, importer, ygoprodeck
from tfcore.cardsource import CardSource

# passcodes: Effect Veiler, Monster Reborn, Wiretap (TFSP only; TF6 stand-in 陷阱封锁), Stardust Dragon
VEILER, REBORN, WIRETAP, STARDUST = 97268402, 83764718, 34507039, 44508094
YDK = f"""#created by someone
#main
{VEILER}
{VEILER}
{REBORN}
{REBORN}
{WIRETAP}
12345679
#extra
{STARDUST}
!side
"""


def test_from_ydk_and_links():
    d = ygoprodeck.from_ydk(YDK, ' Test ', 'https://ygoprodeck.com/deck/test-deck-123')
    assert d['main'][:2] == [VEILER, VEILER] and d['extra'] == [STARDUST] and d['side'] == []
    assert d['name'] == 'Test' and d['url'] == 'https://ygoprodeck.com/deck/test-deck-123'
    assert ygoprodeck.from_ydk(YDK)['id'] == d['id']                      # same cards → same id
    assert ygoprodeck.from_ydk('hello') is None
    url = ygoprodeck.search_url('edison format decks')
    assert url.startswith('https://ygoprodeck.com/deck-search/?') and '_sft_category=edison%20format%20decks' in url
    assert set(ygoprodeck.SEARCHES) == {'TF6', 'TFSP'}
    years = {g: {name for _, cat, name, _ in s if cat == 'world championship decks'} for g, s in ygoprodeck.SEARCHES.items()}
    assert years == {'TF6': {'2008', '2009', '2010'}, 'TFSP': {'2011', '2012', '2013', '2014'}}
    assert 'name=2014' in ygoprodeck.search_url('world championship decks', '2014')


def test_fit_per_game(tf6_db, tfsp_db):
    d = ygoprodeck.from_ydk(YDK)
    tf6 = ygoprodeck.fit(d, ygoprodeck.passcode_index(tf6_db.cards, importer.standins(tf6_db.cards)),
                         limit=lambda n: 1 if n == 4842 else 3)           # Monster Reborn limited to 1
    assert 3643 in tf6['main'] and tf6['missing'] == [12345679]           # Wiretap → 陷阱封锁; unknown
    assert tf6['over'] == [(4842, 2, 1)] and tf6['changes'] == 2
    sp = ygoprodeck.fit(d, ygoprodeck.passcode_index(tfsp_db.cards, importer.standins(tfsp_db.cards)))
    assert 11180 in sp['main'] and sp['over'] == [] and sp['changes'] == 1


def test_store_and_entries(tmp_path, tf6_db):
    store = ygoprodeck.Store(str(tmp_path))
    d = ygoprodeck.from_ydk(YDK, 'Test', 'https://ygoprodeck.com/deck/test-7')
    assert store.load() == [] and not store.has(d)
    store.add(d)
    store.add(d)                                                          # saving twice keeps one
    assert store.has(d) and len(store.load()) == 1
    [e] = deckcatalog.from_ygoprodeck(store.load(), tf6_db.cards, {1: {'id': 12345679, 'cn_name': '某卡'}})
    assert e.key == f"ygopro:{d['id']}" and e.group == 'YGOPRODeck' and e.url.endswith('test-7')
    assert e.missing == ['某卡'] and e.extra == [7734]
    store.remove(d['id'])
    assert store.load() == []


MYSTIC_TOMATO, TOMATO_OTHER = 83011277, 83011278             # two passcodes of one card, #4930


def _api(calls, with_all=True):
    def opener(url):
        calls.append(url)
        if 'id=' in url:                                    # a small query for the listed ids only
            return {'data': [{'id': MYSTIC_TOMATO, 'misc_info': [{'konami_id': 4930}],
                              'card_images': [{'id': MYSTIC_TOMATO}, {'id': TOMATO_OTHER}]}]}
        if not with_all:
            raise OSError('offline')
        return {'data': [{'id': MYSTIC_TOMATO, 'misc_info': [{'konami_id': 4930}],
                          'card_images': [{'id': MYSTIC_TOMATO}, {'id': TOMATO_OTHER}]},
                         {'id': 1, 'misc_info': [{}], 'card_images': [{'id': 1}]}]}      # no konami_id: skipped
    return opener


def test_passcode_table_downloaded_once(tmp_path, tf6_db, tfsp_db):
    calls = []
    cache = ygoprodeck.PasscodeCache(str(tmp_path), opener=_api(calls))
    table = cache.lookup([TOMATO_OTHER])                                # first unknown passcode: whole table
    assert len(calls) == 1 and 'id=' not in calls[0] and calls[0].endswith('cardinfo.php?misc=yes')
    assert table == {MYSTIC_TOMATO: 4930, TOMATO_OTHER: 4930}
    cache.lookup([TOMATO_OTHER, MYSTIC_TOMATO])                         # known now: no request
    assert len(calls) == 1
    again = ygoprodeck.PasscodeCache(str(tmp_path), opener=_api(calls))     # and after a restart
    assert again.lookup([TOMATO_OTHER]) and len(calls) == 1
    for db in (tf6_db, tfsp_db):
        assert again.extra_index(db.cards) == {TOMATO_OTHER: 4930, MYSTIC_TOMATO: 4930}
    assert again.extra_index({}) == {}                                  # a game without the card gets nothing
    again.lookup([12345679])                                            # newer than the download: small query
    assert len(calls) == 2 and 'id=12345679' in calls[1] and again.known[12345679] == 0


def test_passcode_lookup_offline_falls_back(tmp_path):
    calls = []
    cache = ygoprodeck.PasscodeCache(str(tmp_path), opener=_api(calls, with_all=False))
    assert cache.lookup([TOMATO_OTHER])[TOMATO_OTHER] == 4930           # the whole table failed; small query worked
    assert len(calls) == 2 and 'id=83011278' in calls[1]


def test_builtin_alternates_need_no_network(tf6_db, tfsp_db):
    alt = importer.builtin_alternates()
    assert alt[TOMATO_OTHER] == 4930 and 100 < len(alt) < 400                # numbers only, small
    assert all(tf6_db.cards.get(n) or tfsp_db.cards.get(n) for n in alt.values())
    assert not any(tfsp_db.cards[n].passcode == p for p, n in alt.items() if n in tfsp_db.cards)   # never the main one
    for db in (tf6_db, tfsp_db):
        src = CardSource('iso', 'test', db.cards)
        r = importer.run(f'#main\n{TOMATO_OTHER}\n{TOMATO_OTHER}\n#extra\n!side\n', src)
        assert r.main == [4930, 4930] and r.unresolved == []
        assert ygoprodeck.passcode_index(db.cards)[TOMATO_OTHER] == 4930


def test_import_uses_looked_up_passcodes(tmp_path, tf6_db):
    newer = 99999917                                                    # not in the built-in map
    src = CardSource('iso', 'test', tf6_db.cards)
    text = f'#main\n{newer}\n#extra\n!side\n'
    assert [ln.num for ln in importer.run(text, src).lines] == [0]
    r = importer.run(text, src, passcodes={newer: 4930})
    assert r.main == [4930] and r.unresolved == []
