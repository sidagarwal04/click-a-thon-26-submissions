from atlys_agentic import paths


def test_problem_statement_paths_resolve():
    assert paths.BASE_CONTEXT_MD.exists()
    assert paths.DATA_DIR.joinpath("ddl.sql").exists()


def test_spec_dir_helper():
    d = paths.spec_dir("01_express_checkout")
    assert d.exists()
    assert paths.spec_md("01_express_checkout").exists()
    assert paths.events_ndjson("01_express_checkout").exists()


def test_unseen_spec_dir_does_not_exist_yet():
    d = paths.spec_dir("06_unseen")
    assert not paths.spec_md("06_unseen").exists()
