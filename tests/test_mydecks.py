from tfcore import deckcatalog, mydecks


def _deck(name, main, stamp=None):
    return dict(name=name, main=list(main), extra=[], side=[], stamp=stamp)


def test_draft_round_trip(tmp_path):
    orig = {0: _deck('A', [1, 2], (2026, 10, 1)), 1: _deck('B', [3], (2026, 10, 2))}
    work = {0: _deck('A', [1, 2, 2], (2026, 10, 1)), 1: _deck('B', [3], (2026, 10, 2)), 5: _deck('新', [7])}
    drafts = mydecks.Drafts(str(tmp_path))
    changed = mydecks.changed(work, orig)
    assert set(changed) == {0, 5} and changed[0]['base'] == [2026, 10, 1] and changed[5]['base'] is None
    drafts.store(r'C:\x\ULJM059400001', changed)

    fresh = {i: dict(d) for i, d in orig.items()}                      # the page reloads
    restored, moved, removed = mydecks.restore(fresh, orig, drafts.load(r'C:\x\ULJM059400001'))
    assert restored == [0, 5] and moved == [] and removed == [] and fresh[0]['main'] == [1, 2, 2] and fresh[5]['name'] == '新'
    assert fresh[0]['stamp'] == (2026, 10, 1)

    drafts.store(r'C:\x\ULJM059400001', {})                             # saved or dropped
    assert drafts.load(r'C:\x\ULJM059400001') == {}


def test_draft_reports_decks_the_game_changed(tmp_path):
    drafts = mydecks.Drafts(str(tmp_path))
    drafts.store('save', mydecks.changed({0: _deck('A', [9])}, {0: _deck('A', [1], (2026, 1, 1))}))
    later = {0: _deck('A', [1, 4], (2026, 2, 2)), 1: _deck('B', [2], (2026, 2, 2))}
    work = {i: dict(d) for i, d in later.items()}
    assert mydecks.restore(work, later, drafts.load('save')) == ([0], [0], [])
    assert work[0]['main'] == [9]


def test_draft_already_saved_is_skipped(tmp_path):
    orig = {0: _deck('A', [1, 2], (2026, 1, 1))}
    work = {0: dict(orig[0])}
    assert mydecks.restore(work, orig, {0: {**_deck('A', [1, 2]), 'base': [2026, 1, 1]}}) == ([], [], [])


def test_deleted_deck_survives_a_reload(tmp_path):
    """Deleting a deck is an unsaved edit like any other: the draft has to remember it."""
    orig = {0: _deck('A', [1, 2], (2026, 1, 1)), 1: _deck('B', [3], (2026, 1, 2))}
    work = {0: _deck('A', [1, 2], (2026, 1, 1))}                 # #1 deleted, nothing else touched
    drafts = mydecks.Drafts(str(tmp_path))
    changed = mydecks.changed(work, orig, removed={1})
    assert changed == {1: None}
    drafts.store('save', changed)

    fresh = {i: dict(d) for i, d in orig.items()}                 # the page reloads
    assert mydecks.restore(fresh, orig, drafts.load('save')) == ([], [], [1])
    assert 1 not in fresh and 0 in fresh

    drafts.store('save', {})                                      # saved, or dropped
    assert mydecks.restore(dict(orig), orig, drafts.load('save')) == ([], [], [])


def test_restore_skips_deleting_a_slot_the_save_no_longer_has(tmp_path):
    drafts = mydecks.Drafts(str(tmp_path))
    drafts.store('save', {1: None})
    work = {0: _deck('A', [1])}
    assert mydecks.restore(work, work, drafts.load('save')) == ([], [], [])
    assert 1 not in work


def test_library_and_catalog(tmp_path):
    lib = mydecks.Library(str(tmp_path))
    first = lib.save('TF6', '真六武众', _deck('x', [1, 2, 3]))
    assert lib.save('TF6', '真六武众', _deck('x', [1, 2])) == first      # same name: replaced
    lib.save('TFSP', '其他', _deck('y', [4]))
    assert [d['name'] for d in lib.load('TF6')] == ['真六武众'] and lib.load('TF6')[0]['main'] == [1, 2]
    entries = deckcatalog.from_library(lib.load('TF6'), {1: None})
    assert entries[0].key == f'my:{first}' and entries[0].group == deckcatalog.MINE
    assert entries[0].main == [1] and entries[0].missing == ['#2']
    lib.remove(first)
    assert lib.load('TF6') == []
