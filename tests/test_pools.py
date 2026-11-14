from tfcore import pools


def test_builtin_pools_load():
    tf6, sp = pools.load('TF6'), pools.load('TFSP')
    assert len(tf6) == 5392 and len(sp) == 7254
    assert tf6.row_of(3459) == 1 and tf6.row_of(9839) == 5392 and tf6.row_of(4006) == 0
    assert 4007 in tf6 and 11657 in sp and 11657 not in tf6


def test_builtin_pools_match_isos(tf6_db, tfsp_db):
    assert pools.matches(pools.load('TF6'), tf6_db)
    assert pools.matches(pools.load('TFSP'), tfsp_db)
    assert tf6_db.row_of(4007) == pools.load('TF6').row_of(4007) == 312
