import pytest
from sqlalchemy.orm import Session

from src.infra.db.repos.jurisdiction_repo import PgJurisdictionRepo
from tests.utils.builders.knowledge_base import make_jurisdiction

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_search_case_insensitive(db_session: Session) -> None:
    repo = PgJurisdictionRepo(db_session)
    repo.save(
        make_jurisdiction(
            name="City and County of Denver", slug="tst-denver-co-us"
        )
    )

    results = repo.search_by_name("DENVER")

    slugs = [j.slug for j in results]
    assert "tst-denver-co-us" in slugs


@pytest.mark.integration
def test_search_substring_match(db_session: Session) -> None:
    repo = PgJurisdictionRepo(db_session)
    repo.save(
        make_jurisdiction(
            name="City and County of Denver", slug="tst-denver-county-sub"
        )
    )

    results = repo.search_by_name("county")

    slugs = [j.slug for j in results]
    assert "tst-denver-county-sub" in slugs


@pytest.mark.integration
def test_search_empty_query_matches_all(db_session: Session) -> None:
    repo = PgJurisdictionRepo(db_session)
    repo.save(make_jurisdiction(name="Tst Alpha City", slug="tst-alpha-city"))
    repo.save(make_jurisdiction(name="Tst Beta City", slug="tst-beta-city"))

    results = repo.search_by_name("")

    slugs = {j.slug for j in results}
    assert "tst-alpha-city" in slugs
    assert "tst-beta-city" in slugs


@pytest.mark.integration
def test_search_no_match_returns_empty(db_session: Session) -> None:
    repo = PgJurisdictionRepo(db_session)
    repo.save(
        make_jurisdiction(
            name="City and County of Denver", slug="tst-denver-no-match"
        )
    )

    results = repo.search_by_name("portland")

    slugs = {j.slug for j in results}
    assert "tst-denver-no-match" not in slugs


@pytest.mark.integration
def test_search_results_ordered_ascending_by_name(
    db_session: Session,
) -> None:
    repo = PgJurisdictionRepo(db_session)
    repo.save(
        make_jurisdiction(name="Tst Denver City", slug="tst-order-denver")
    )
    repo.save(
        make_jurisdiction(name="Tst Boulder City", slug="tst-order-boulder")
    )

    results = repo.search_by_name("tst")

    tst_results = [
        j
        for j in results
        if j.slug in {"tst-order-denver", "tst-order-boulder"}
    ]
    assert len(tst_results) == 2
    assert tst_results[0].name < tst_results[1].name


@pytest.mark.integration
def test_search_percent_wildcard_is_escaped(db_session: Session) -> None:
    repo = PgJurisdictionRepo(db_session)
    repo.save(
        make_jurisdiction(name="Tst No Special Chars", slug="tst-no-special")
    )

    results = repo.search_by_name("%")

    slugs = {j.slug for j in results}
    assert "tst-no-special" not in slugs
