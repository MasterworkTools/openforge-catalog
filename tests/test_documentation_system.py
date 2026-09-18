from psycopg.rows import dict_row


def test_documentation_type_enum_extension(test_db):
    """Test that the documentation_type_enum has been extended with 'instructions'."""
    with test_db.connection() as conn:
        with conn.cursor() as curs:
            curs.execute("SELECT unnest(enum_range(NULL::documentation_type_enum))")
            enum_values = [row[0] for row in curs.fetchall()]
            assert "changelog" in enum_values
            assert "instructions" in enum_values


def test_image_type_enum_creation(test_db):
    """Test that image_type_enum has been created."""
    with test_db.connection() as conn:
        with conn.cursor() as curs:
            curs.execute("SELECT unnest(enum_range(NULL::image_type_enum))")
            enum_values = [row[0] for row in curs.fetchall()]
            assert "thumbnail" in enum_values
            assert "documentation" in enum_values


def test_tags_documentation_table_creation(test_db):
    """Test that tag_documentation table has been created."""
    with test_db.connection() as conn:
        with conn.cursor() as curs:
            curs.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_name = 'tag_documentation'
            """)
            result = curs.fetchone()
            assert result is not None


def test_sessions_table_creation(test_db):
    """Test that sessions table has been created."""
    with test_db.connection() as conn:
        with conn.cursor() as curs:
            curs.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_name = 'sessions'
            """)
            result = curs.fetchone()
            assert result is not None


def test_blueprint_documentation_sql_operations(test_db):
    """Test blueprint documentation SQL operations."""
    from openforge.db.sql import blueprint_documentation as blueprint_doc_sql

    # Create a test blueprint first
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            # Insert a test blueprint
            curs.execute("""
                INSERT INTO blueprints (blueprint_name, blueprint_type, file_md5,
                                        file_name, config)
                VALUES ('test_blueprint', 'model', 'test_md5', 'test.stl', '{}')
                RETURNING id
            """)
            blueprint_id = curs.fetchone()["id"]

            # Test creating documentation
            doc = blueprint_doc_sql.create_blueprint_documentation(
                curs, blueprint_id, "Test changelog", "changelog"
            )
            assert doc["document"] == "Test changelog"
            assert doc["document_type"] == "changelog"
            assert doc["blueprint_id"] == blueprint_id

            # Test getting documentation
            docs = blueprint_doc_sql.get_blueprint_documentation(curs, blueprint_id)
            assert len(docs) == 1
            assert docs[0]["document"] == "Test changelog"

            # Test updating documentation
            updated_doc = blueprint_doc_sql.update_blueprint_documentation(
                curs, doc["id"], "Updated changelog"
            )
            assert updated_doc["document"] == "Updated changelog"

            # Test deleting documentation
            result = blueprint_doc_sql.delete_blueprint_documentation(curs, doc["id"])
            assert result["id"] == doc["id"]

            # Verify deletion
            docs = blueprint_doc_sql.get_blueprint_documentation(curs, blueprint_id)
            assert len(docs) == 0


def test_tags_documentation_sql_operations(test_db):
    """Test tags documentation SQL operations."""
    from openforge.db.sql import tags_documentation as tags_doc_sql

    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            tag_array = ["texture", "dungeon_stone"]

            # Test creating documentation
            doc = tags_doc_sql.create_tag_documentation(
                curs, tag_array, "Test instructions", "instructions"
            )
            assert doc["document"] == "Test instructions"
            assert doc["document_type"] == "instructions"
            # The tag is stored as array in DB but converted to
            # pipe-delimited string by convert_tag_dict
            assert doc["tag"] == "texture|dungeon_stone"

            # Test getting documentation
            docs = tags_doc_sql.get_tag_documentation(curs, tag_array)
            assert len(docs) == 1
            assert docs[0]["document"] == "Test instructions"

            # Test updating documentation
            updated_doc = tags_doc_sql.update_tag_documentation(
                curs, doc["id"], "Updated instructions"
            )
            assert updated_doc["document"] == "Updated instructions"

            # Test deleting documentation
            result = tags_doc_sql.delete_tag_documentation(curs, doc["id"])
            assert result["id"] == doc["id"]

            # Verify deletion
            docs = tags_doc_sql.get_tag_documentation(curs, tag_array)
            assert len(docs) == 0


def test_get_tag_documentation_for_blueprint(test_db):
    """Test get_tag_documentation_for_blueprint function."""
    from openforge.db.sql import tags_documentation as tags_doc_sql

    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            # Create a test blueprint
            curs.execute("""
                INSERT INTO blueprints (blueprint_name, blueprint_type, config)
                VALUES ('test_blueprint', 'model', '{}')
                RETURNING id
            """)
            blueprint_id = curs.fetchone()["id"]

            # Create test tags for the blueprint
            tag_arrays = [
                ["texture", "dungeon_stone"],
                ["connection", "openforge"],
                ["build", "topless"],
            ]

            # Add tags to the blueprint
            for tag_array in tag_arrays:
                curs.execute(
                    """
                    INSERT INTO tags (blueprint_id, tag)
                    VALUES (%s, %s)
                """,
                    (blueprint_id, tag_array),
                )

            # Create test documentation for the tags
            created_docs = []
            for tag_array in tag_arrays:
                doc = tags_doc_sql.create_tag_documentation(
                    curs,
                    tag_array,
                    f"Test instructions for {'/'.join(tag_array)}",
                    "instructions",
                )
                created_docs.append(doc)

            # Test getting documentation for blueprint tags
            result = tags_doc_sql.get_tag_documentation_for_blueprint(
                curs, blueprint_id
            )

            # Verify the result structure
            assert len(result) == 3
            assert "texture|dungeon_stone" in result
            assert "connection|openforge" in result
            assert "build|topless" in result

            # Verify each tag has documentation
            for tag_string, docs in result.items():
                assert len(docs) == 1
                assert docs[0]["document"].startswith("Test instructions for")
                assert docs[0]["document_type"] == "instructions"

            # Test with blueprint that has no tags
            curs.execute("""
                INSERT INTO blueprints (blueprint_name, blueprint_type, config)
                VALUES ('empty_blueprint', 'model', '{}')
                RETURNING id
            """)
            empty_blueprint_id = curs.fetchone()["id"]

            empty_result = tags_doc_sql.get_tag_documentation_for_blueprint(
                curs, empty_blueprint_id
            )
            assert empty_result == {}

            # Clean up
            for doc in created_docs:
                tags_doc_sql.delete_tag_documentation(curs, doc["id"])

            # Clean up test data
            curs.execute("DELETE FROM tags WHERE blueprint_id = %s", (blueprint_id,))
            curs.execute("DELETE FROM blueprints WHERE id = %s", (blueprint_id,))
            curs.execute("DELETE FROM blueprints WHERE id = %s", (empty_blueprint_id,))


def test_changelog_history_function(test_db):
    """Test the changelog history SQL function."""
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            # Create test blueprints with successor chain
            curs.execute("""
                INSERT INTO blueprints (blueprint_name, blueprint_type, file_md5,
                                        file_name, config)
                VALUES ('blueprint_v1', 'model', 'md5_v1', 'v1.stl', '{}')
                RETURNING id
            """)
            blueprint_v1_id = curs.fetchone()["id"]

            curs.execute(
                """
                INSERT INTO blueprints (blueprint_name, blueprint_type, file_md5,
                                        file_name, successor_id, config)
                VALUES ('blueprint_v2', 'model', 'md5_v2', 'v2.stl', %s, '{}')
                RETURNING id
            """,
                (blueprint_v1_id,),
            )
            blueprint_v2_id = curs.fetchone()["id"]

            # Add changelog documentation
            curs.execute(
                """
                INSERT INTO blueprint_documentation
                    (blueprint_id, document, document_type)
                VALUES (%s, 'Version 1 changelog', 'changelog')
            """,
                (blueprint_v1_id,),
            )

            curs.execute(
                """
                INSERT INTO blueprint_documentation
                    (blueprint_id, document, document_type)
                VALUES (%s, 'Version 2 changelog', 'changelog')
            """,
                (blueprint_v2_id,),
            )

            # Test the function
            curs.execute(
                """
                SELECT blueprint_id, blueprint_name, changelog, depth
                FROM get_blueprint_changelog_history(%s, 10)
                ORDER BY depth
            """,
                (blueprint_v2_id,),
            )

            results = curs.fetchall()
            assert len(results) == 2

            # Check that v2 (current) comes first (depth 0)
            assert results[0]["blueprint_name"] == "blueprint_v2"
            assert results[0]["depth"] == 0
            assert results[0]["changelog"] == "Version 2 changelog"

            # Check that v1 (predecessor) comes second (depth 1)
            assert results[1]["blueprint_name"] == "blueprint_v1"
            assert results[1]["depth"] == 1
            assert results[1]["changelog"] == "Version 1 changelog"
