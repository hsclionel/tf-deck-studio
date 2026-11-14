from tfcore import tags

# Konami ids: Effect Veiler, Maxx "C", Battle Fader, Gorz, Torrential Tribute, Bottomless Trap Hole,
# Dimensional Prison, Solemn Judgment, Breakthrough Skill, Monster Reborn, Cyber Dinosaur, Chaos Hunter
VEILER, MAXXC, FADER, GORZ, TORRENTIAL, BOTTOMLESS, DPRISON, JUDGMENT, BTS, REBORN, CYBERDINO, CHAOSHUNTER = \
    8933, 9455, 8617, 6558, 5114, 5400, 7400, 4861, 10437, 4842, 6727, 9454


def _tags(db, num, **kw):
    return tags.tags_of(db.cards[num], **kw)


def test_hand_traps_both_games(tf6_db, tfsp_db):
    for db in (tf6_db, tfsp_db):
        for num in (VEILER, MAXXC, GORZ, FADER):
            assert 'handtrap' in _tags(db, num), (db.cards[num].name)
        for num in (CYBERDINO, CHAOSHUNTER, REBORN):
            assert 'handtrap' not in _tags(db, num), db.cards[num].name


def test_trap_roles(tf6_db, tfsp_db):
    for db in (tf6_db, tfsp_db):
        assert {'summon_react', 'wipe'} <= _tags(db, TORRENTIAL)
        assert 'summon_react' in _tags(db, BOTTOMLESS)
        assert 'attack_react' in _tags(db, DPRISON)
        assert 'negate' in _tags(db, JUDGMENT)
        assert 'revive' in _tags(db, REBORN)
    assert {'gy', 'negate'} <= _tags(tfsp_db, BTS)


def test_staples_and_marks(tfsp_db):
    assert VEILER in tags.staples() and 'staple' in _tags(tfsp_db, VEILER)
    assert 'staple' not in _tags(tfsp_db, VEILER, not_staples=[VEILER])
    assert 'staple' in _tags(tfsp_db, CYBERDINO, extra_staples=[CYBERDINO])
    assert 'limited' in _tags(tfsp_db, REBORN, allowed=1) and 'limited' not in _tags(tfsp_db, REBORN)
    assert set(tags.TAGS) >= {'staple', 'handtrap', 'gy', 'summon_react', 'attack_react'}
