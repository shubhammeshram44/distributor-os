"""
Regression test for DB-4: several Alembic migrations guard their upgrade()
add_column/create_index/create_table/create_check_constraint calls with the
project's column_exists()/index_exists()/table_exists() idempotency helpers
(needed because the initial-schema migration's create_all() fast path may
have already created these objects against the *current* ORM models -- see
app/utils/migration_helpers.py), but the matching downgrade() drop_column/
drop_index/drop_table/drop_constraint calls were left unguarded. On a
database where upgrade() took the "already exists, skip" branch, downgrade()
would still unconditionally try to drop something that this migration never
actually added -- on Postgres this can raise (e.g. dropping a nonexistent
object) or, worse, silently remove a column/index/table that predates this
migration entirely.

This is a static-analysis test (source-inspection, not execution) so it runs
everywhere without needing a live database: for every migration whose
upgrade() calls one of the project's *_exists() guard helpers, its
downgrade() must call at least one of the same helper family too.

The full corrected downgrade chain (all 26 non-baseline migrations,
upgrade -> downgrade -> re-upgrade) was additionally verified live against a
real Postgres 16 instance during development of this fix -- this static test
guards against a future regression silently reintroducing an unguarded
drop_*, which this source-level check can catch immediately in CI without
needing that live-database round trip every time.
"""
import ast
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"

_GUARD_HELPER_NAMES = {"column_exists", "index_exists", "table_exists", "unique_constraint_exists"}

# The very first, auto-generated "Initial schema" migration predates the
# column_exists()/index_exists() idempotency-helper pattern entirely (it has
# no guards in upgrade() either, since it always runs against a genuinely
# empty database) and has pre-existing, unrelated downgrade issues (e.g. an
# unnamed unique constraint that cannot be dropped by name) that are out of
# scope for this fix -- excluded here rather than silently glossed over.
_EXCLUDED_FILES = {"9eb6a140e6af_initial_schema.py"}


def _function_source(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _calls_any_guard_helper(func_node: ast.FunctionDef) -> bool:
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _GUARD_HELPER_NAMES:
                return True
    return False


def _has_drop_call(func_node: ast.FunctionDef) -> bool:
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr.startswith("drop_"):
                return True
    return False


def test_every_guarded_upgrade_has_a_guarded_downgrade():
    migration_files = sorted(
        f for f in MIGRATIONS_DIR.glob("*.py")
        if f.name != "__init__.py" and f.name not in _EXCLUDED_FILES
    )
    assert migration_files, "Expected to find migration files to check"

    unguarded = []
    for path in migration_files:
        tree = ast.parse(path.read_text(), filename=str(path))
        upgrade_fn = _function_source(tree, "upgrade")
        downgrade_fn = _function_source(tree, "downgrade")
        if upgrade_fn is None or downgrade_fn is None:
            continue
        if not _calls_any_guard_helper(upgrade_fn):
            continue  # this migration doesn't use the idempotency pattern at all
        if not _has_drop_call(downgrade_fn):
            continue  # downgrade doesn't drop anything (e.g. pure data backfill)
        if not _calls_any_guard_helper(downgrade_fn):
            unguarded.append(path.name)

    assert not unguarded, (
        "The following migrations guard their upgrade() add/create calls with "
        "column_exists()/index_exists()/table_exists() but their downgrade() "
        "drop_* calls have no matching guard (see DB-4):\n  " + "\n  ".join(unguarded)
    )
