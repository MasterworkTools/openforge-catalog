from psycopg.rows import dict_row

import openforge.db.sql.blueprints as blueprint_sql
import openforge.db.sql.tags as tag_sql

from .test_helpers import create_test_blueprint


def test_insert_and_get_tag(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint()
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag = tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            assert tag["tag"] == "foo|bar"
            assert tag["blueprint_id"] == inserted_bp["id"]


def test_get_tags_for_blueprint(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint()
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            tags = tag_sql.get_tags(curs, inserted_bp["id"])
            assert len(tags) == 1
            assert tags[0]["tag"] == "foo|bar"


def test_insert_duplicate_tag(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint()
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag1 = tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            tag2 = tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            assert tag1["id"] == tag2["id"]


def test_delete_tag(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint()
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            rows = tag_sql.delete_tag(curs, inserted_bp["id"], "foo|bar")
            assert rows == 1
            tags = tag_sql.get_tags(curs, inserted_bp["id"])
            assert len(tags) == 0


def test_delete_all_blueprint_tags(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint()
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            tag_sql.insert_tag(curs, inserted_bp["id"], "baz|qux")
            rows = tag_sql.delete_all_blueprint_tags(curs, inserted_bp["id"])
            assert rows == 2
            tags = tag_sql.get_tags(curs, inserted_bp["id"])
            assert len(tags) == 0


def test_delete_all_tags(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp1 = create_test_blueprint()
            bp2 = create_test_blueprint()
            inserted_bp1 = blueprint_sql.insert_blueprint(curs, bp1)
            inserted_bp2 = blueprint_sql.insert_blueprint(curs, bp2)
            tag_sql.insert_tag(curs, inserted_bp1["id"], "foo|bar")
            tag_sql.insert_tag(curs, inserted_bp2["id"], "foo|bar")
            rows = tag_sql.delete_all_tags(curs)
            assert rows == 2
            tags = tag_sql.get_tags(curs, inserted_bp1["id"])
            assert len(tags) == 0


def test_get_blueprint_ids_by_tag(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp1 = create_test_blueprint()
            bp2 = create_test_blueprint()
            inserted_bp1 = blueprint_sql.insert_blueprint(curs, bp1)
            inserted_bp2 = blueprint_sql.insert_blueprint(curs, bp2)
            tag_sql.insert_tag(curs, inserted_bp1["id"], "foo|bar")
            tag_sql.insert_tag(curs, inserted_bp2["id"], "foo|bar")
            ids = tag_sql.get_blueprint_ids_by_tag(curs, "foo|bar")
            assert len(ids) == 2
            assert inserted_bp1["id"] in ids
            assert inserted_bp2["id"] in ids


def test_tag_search_blueprints(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint(blueprint_type="model")
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            results = tag_sql.tag_search_blueprints(
                curs, [{"tag": "foo|bar"}], [], [], None, None, 20, True, False, None
            )
            assert len(results) == 1
            assert results[0]["id"] == inserted_bp["id"]

            # A bare string is silently ignored by the search, so a
            # test that passes one asserts only that some model
            # exists. Searching for a tag nothing carries has to come
            # back empty — and this negative case is the half that
            # carries the test. Reverting the call above to a bare
            # string still passes; reverting this one does not. Do
            # not delete it as redundant.
            assert (
                tag_sql.tag_search_blueprints(
                    curs,
                    [{"tag": "no|such"}],
                    [],
                    [],
                    None,
                    None,
                    20,
                    True,
                    False,
                    None,
                )
                == []
            )


def test_tag_search_blueprints_is_ordered_by_name(test_db):
    """The ORDER BY is load-bearing, not cosmetic.

    Guides resolve a role by asking for the single best candidate
    (`LIMIT 1`), so this ordering is the only thing that makes a
    recommendation reproducible — and therefore the only thing that
    makes a shared guide URL show the same parts twice. Inserted out
    of order on purpose.
    """
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            for name in ["c wall", "a wall", "b wall"]:
                inserted = blueprint_sql.insert_blueprint(
                    curs,
                    create_test_blueprint(blueprint_name=name, blueprint_type="model"),
                )
                tag_sql.insert_tag(curs, inserted["id"], "foo|bar")

            results = tag_sql.tag_search_blueprints(
                curs, [{"tag": "foo|bar"}], [], [], None, None, 20, True, False, None
            )

            assert [r["blueprint_name"] for r in results] == [
                "a wall",
                "b wall",
                "c wall",
            ]

            # Four more sharing a name: the full listing has to order
            # the ties by id, which the name alone cannot do. Four
            # rather than two because random uuids fall in ascending
            # order often enough by chance to make a smaller sample a
            # weak assertion.
            for _ in range(4):
                dup = blueprint_sql.insert_blueprint(
                    curs,
                    create_test_blueprint(
                        blueprint_name="a wall", blueprint_type="model"
                    ),
                )
                tag_sql.insert_tag(curs, dup["id"], "foo|bar")

            def listing():
                return [
                    r["id"]
                    for r in tag_sql.tag_search_blueprints(
                        curs,
                        [{"tag": "foo|bar"}],
                        [],
                        [],
                        None,
                        None,
                        20,
                        True,
                        False,
                        None,
                    )
                ]

            before = listing()
            curs.execute(
                "UPDATE blueprints SET file_size = 99 WHERE id = %s",
                (before[0],),
            )

            assert listing() == before

            # And the ties are in id order, which is the only thing
            # that makes the listing stable rather than merely
            # repeatable within one read.
            tied = [
                r["id"]
                for r in tag_sql.tag_search_blueprints(
                    curs,
                    [{"tag": "foo|bar"}],
                    [],
                    [],
                    None,
                    None,
                    20,
                    True,
                    False,
                    None,
                )
                if r["blueprint_name"] == "a wall"
            ]
            assert len(tied) == 5
            assert [str(i) for i in tied] == sorted(str(i) for i in tied)


def test_tag_search_blueprints_limit_takes_the_first_by_name(test_db):
    """`LIMIT 1` must mean the first alphabetically, not an arbitrary row."""
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            for name in ["z wall", "a wall"]:
                inserted = blueprint_sql.insert_blueprint(
                    curs,
                    create_test_blueprint(blueprint_name=name, blueprint_type="model"),
                )
                tag_sql.insert_tag(curs, inserted["id"], "foo|bar")

            results = tag_sql.tag_search_blueprints(
                curs, [{"tag": "foo|bar"}], [], [], None, None, 1, True, False, None
            )

            assert [r["blueprint_name"] for r in results] == ["a wall"]


def test_tag_search_is_stable_when_names_collide(test_db):
    """blueprint_name is not unique, so it cannot order alone.

    159 names in the catalog are shared by two or more records, mostly
    bases — the very role a guide resolves. With only the name in the
    ORDER BY, LIMIT 1 picks arbitrarily among the ties and any
    unrelated write can change which one comes back, so a shared guide
    URL would show a different part later. The id makes it total.

    This asserts the property rather than sampling it. Asking twice
    with a write in between only compares two executions out of a
    space the test does not control: whether an arbitrary pick moves
    depends on the plan, and at these row counts Postgres chooses one
    that happens to preserve heap order until the table is ANALYZEd.
    The lowest id among the ties is what a total order must return,
    whatever the plan does.
    """
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            for _ in range(20):
                inserted = blueprint_sql.insert_blueprint(
                    curs,
                    create_test_blueprint(
                        blueprint_name="same name", blueprint_type="model"
                    ),
                )
                tag_sql.insert_tag(curs, inserted["id"], "foo|bar")
            # Give the planner real statistics, so the test does not
            # depend on the plan an unanalysed table happens to get.
            curs.execute("ANALYZE blueprints")
            curs.execute("ANALYZE tags")
            curs.execute(
                "SELECT id FROM blueprints WHERE blueprint_name = %s "
                "ORDER BY id LIMIT 1",
                ("same name",),
            )
            lowest = curs.fetchone()["id"]

            found = tag_sql.tag_search_blueprints(
                curs, [{"tag": "foo|bar"}], [], [], None, None, 1, True, False, None
            )

            assert found[0]["id"] == lowest


def test_tag_search_tags(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint(blueprint_type="model")
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            results = tag_sql.tag_search_tags(
                curs, ["foo|bar"], [], [], None, None, 20, True, False, None
            )
            assert len(results) == 1
            assert results[0]["tag"] == ["foo", "bar"]


def test_tag_search_blueprint_images(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint()
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            results = tag_sql.tag_search_blueprint_images(
                curs, ["foo|bar"], [], [], None, None, 20, True, False, None
            )
            assert len(results) == 0


def test_tag_search_blueprint_count(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint(blueprint_type="model")
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            count = tag_sql.tag_search_blueprint_count(
                curs, ["foo|bar"], [], [], True, False, None
            )
            assert count == 1


def test_tag_search_tag_count(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint(blueprint_type="model")
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            count = tag_sql.tag_search_tag_count(
                curs, ["foo|bar"], [], [], True, False, None
            )
            assert count[0]["tag"] == ["foo", "bar"]
            assert count[0]["tag_count"] == 1
