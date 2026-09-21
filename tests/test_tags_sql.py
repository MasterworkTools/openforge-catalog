from psycopg.rows import dict_row

import openforge.db.sql.blueprints as blueprint_sql
import openforge.db.sql.tags as tag_sql

from .test_helpers import create_test_blueprint


def _tagged(curs, name, tags):
    """A searchable model with these tags, named for sort order.

    The search orders by blueprint_name, so the names here are chosen
    to make the expected order readable in the assertion.
    """
    data = create_test_blueprint(blueprint_name=name, blueprint_type="model")
    data.pop("tags", None)
    data.pop("images", None)
    blueprint = blueprint_sql.insert_blueprint(curs, data)
    for tag in tags:
        tag_sql.insert_tag(curs, blueprint["id"], tag)
    return blueprint


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


def test_tag_search_orders_ties_by_id(test_db):
    """Names collide, so the listing needs a second key.

    Thirteen rows share a name, with two others after them. Thirteen
    rather than a handful because a short run of random uuids lands in
    ascending order often enough to let the assertion pass with the
    tiebreak removed; the two other names because a sort with nothing
    to do can return its input untouched, and then the missing
    tiebreak does not show.

    The write in the middle is a perturbation, not the assertion — it
    moves a row in the heap so the rows do not reach the final sort
    already in the order being asserted. Comparing two reads and
    calling that stability, which an earlier version of this test did,
    proves less again: it samples one pair of executions out of a
    space the test does not control.
    """
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            for name in ["a wall"] * 13 + ["b wall", "c wall"]:
                inserted = blueprint_sql.insert_blueprint(
                    curs,
                    create_test_blueprint(blueprint_name=name, blueprint_type="model"),
                )
                tag_sql.insert_tag(curs, inserted["id"], "foo|bar")

            curs.execute(
                "UPDATE blueprints SET file_size = 99 WHERE id = ("
                "SELECT id FROM blueprints ORDER BY id LIMIT 1)"
            )

            found = tag_sql.tag_search_blueprints(
                curs,
                [{"tag": "foo|bar"}],
                [],
                [],
                None,
                None,
                30,
                True,
                False,
                None,
            )
            tied = [str(r["id"]) for r in found if r["blueprint_name"] == "a wall"]

            assert [r["blueprint_name"] for r in found[-2:]] == [
                "b wall",
                "c wall",
            ]
            assert len(tied) == 13
            assert tied == sorted(tied)


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
    The lowest ids among the ties are what a total order must return,
    whatever the plan does — which is also why this needs no ANALYZE:
    an earlier version only caught the regression on the plan an
    unanalysed table happens to get.

    It asks for five rather than one on purpose. Constraining a single
    position still lets an arbitrary pick satisfy it by luck — with
    twenty ties, one run in twenty — and a test that passes 5% of the
    time when the bug is present is not a witness. Pinning the whole
    five-row prefix drops that to one in 15,504.
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
            curs.execute(
                "SELECT id FROM blueprints WHERE blueprint_name = %s "
                "ORDER BY id LIMIT 5",
                ("same name",),
            )
            lowest = [row["id"] for row in curs.fetchall()]

            found = tag_sql.tag_search_blueprints(
                curs, [{"tag": "foo|bar"}], [], [], None, None, 5, True, False, None
            )

            assert [row["id"] for row in found] == lowest


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


def test_deny_children_keeps_the_tag_and_refuses_what_is_below_it(test_db):
    """ "A plain wall" without listing every variant that is not one.

    Denying `component|wall|*` by hand would mean editing every guide
    each time a new variant is designed, which is the opposite of
    tagging being the thing that keeps the catalog current.
    """
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            plain = _tagged(curs, "a plain wall", ["shape|wall", "component|wall"])
            _tagged(
                curs,
                "b arrow slit",
                ["shape|wall", "component|wall", "component|wall|arrow_slit"],
            )
            _tagged(
                curs,
                "c curved",
                ["shape|wall", "component|wall", "component|wall|curved"],
            )

            # `component|wall` is deliberately *not* required here, so
            # that it is not exempt: what keeps the plain wall in is
            # that the sweep takes what is strictly below the tag, not
            # the tag itself.
            found = tag_sql.tag_search_blueprints(
                curs,
                accept=[],
                require=[{"tag": "shape|wall"}],
                deny=[],
                deny_children=[{"tag": "component|wall"}],
            )

            assert [b["id"] for b in found] == [plain["id"]]


def test_a_required_child_survives_the_sweep_that_removes_its_siblings(test_db):
    """The sweep runs after the includes, which is the whole point.

    "shape|floor|wall and nothing else under shape|floor" is one
    predicate rather than a contradiction: the required child is exempt
    from the deny by construction, so the two terms do not have to know
    about each other.
    """
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            wanted = _tagged(
                curs, "a floor for a wall", ["shape|floor", "shape|floor|wall"]
            )
            _tagged(curs, "b curved floor", ["shape|floor", "shape|floor|curved"])
            _tagged(
                curs,
                "c curved floor for a wall",
                ["shape|floor", "shape|floor|wall", "shape|floor|curved"],
            )
            _tagged(curs, "d bare floor", ["shape|floor"])

            found = tag_sql.tag_search_blueprints(
                curs,
                accept=[],
                require=[{"tag": "shape|floor"}, {"tag": "shape|floor|wall"}],
                deny=[],
                deny_children=[{"tag": "shape|floor"}],
            )

            # "c" carries the required child *and* a swept one, so it
            # goes: the sweep spares the tags that were asked for, not
            # the blueprints that happen to carry one.
            assert [b["id"] for b in found] == [wanted["id"]]


def test_allow_spares_a_child_without_requiring_it(test_db):
    """`allow` asks for nothing; it only survives the sweep.

    That is what makes it different from `accept`, which is a
    requirement that some tag exists below a prefix.
    """
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bare = _tagged(curs, "a bare base", ["shape|base"])
            square = _tagged(curs, "b square base", ["shape|base", "shape|base|square"])
            _tagged(curs, "c wall base", ["shape|base", "shape|base|wall"])

            found = tag_sql.tag_search_blueprints(
                curs,
                accept=[],
                require=[{"tag": "shape|base"}],
                deny=[],
                deny_children=[{"tag": "shape|base"}],
                allow=[{"tag": "shape|base|square"}],
            )

            # The bare one has nothing to sweep; the square one is
            # spared; the wall one is not.
            assert [b["id"] for b in found] == [bare["id"], square["id"]]
