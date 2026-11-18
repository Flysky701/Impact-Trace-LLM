import subprocess
import pytest

pytest.importorskip("tree_sitter_language_pack", reason="离线 Demo 需要 requirements-analysis.txt")
pytest.importorskip("tree_sitter_kotlin", reason="离线 Demo 需要 requirements-analysis.txt")

from app.code_graph import analyze, line_changes, parse_kotlin


def test_kotlin_activity_preserves_branch_loop_and_deferred_body():
    source = '''package sample
// fun imaginary() { danger() }
class Account {
    fun bind(id: Int) {
        val note = "fake()"
        if (id > 0) save(id) else fail()
        while (busy()) { waitMore() }
        scope.launch { later() }
        return
    }
    fun bind(id: String) = save(id)
}'''
    parsed = parse_kotlin("sample.kt", source, "app", "desktop", flows=["bind"])
    functions = [s for s in parsed["symbols"] if s["kind"] == "function"]
    assert len(functions) == 2 and functions[0]["id"] != functions[1]["id"]
    assert not parsed["errors"]
    calls = {c["name"] for s in functions for c in s["calls"]}
    assert "fake" not in calls and "danger" not in calls
    flow = functions[0]["flow"]
    assert [n["kind"] for n in flow] == ["step", "if", "loop", "scope", "exit"]
    assert flow[1]["branches"][1]["items"][0]["label"] == "fail()"
    assert flow[3]["children"][0]["label"] == "later()"
    assert flow[3]["boundary"]


def test_room_fields_and_foreign_keys_are_extracted_from_annotations():
    source = '''@Entity(tableName = "runs", primaryKeys = ["id"], foreignKeys = [
      ForeignKey(entity = Account::class, parentColumns = ["id"],
                 childColumns = ["account_id"], onDelete = ForeignKey.SET_NULL)])
data class Run(val id: Long, @ColumnInfo(name = "account_id") val accountId: Long?)'''
    entity = parse_kotlin("Entities.kt", source, "shared", "upstream")["entities"][0]
    assert entity["table"] == "runs"
    assert entity["fields"][0]["primary"]
    assert entity["fields"][1]["name"] == "account_id"
    assert entity["foreignKeys"][0] == {"target": "Account", "parentColumns": ["id"], "childColumns": ["account_id"], "onDelete": "SET_NULL"}


def test_line_changes_include_deleted_old_lines_and_added_new_lines():
    before, after = line_changes("a\ndelete\nc\n", "a\nreplace\nadd\nc\n")
    assert before == [[2, 2]] and after == [[2, 3]]
    assert line_changes("a\n", "a\nnew\n") == ([], [[2, 2]])


def test_extension_receivers_and_anonymous_object_owners_have_distinct_ids():
    source = '''class Database {
    val FIRST = object : Migration {
        fun migrate(db: Connection) { first() }
    }
    val SECOND = object : Migration {
        fun migrate(db: Connection) { second() }
    }
}
fun JsonObject.string() = 1
fun JsonElement.string() = 2
'''
    parsed = parse_kotlin("sample.kt", source, "shared", "desktop")
    functions = [s for s in parsed["symbols"] if s["kind"] == "function"]
    assert len(functions) == 4
    assert len({s["id"] for s in functions}) == 4
    assert {s["qualified"] for s in functions} == {"Database.FIRST.migrate", "Database.SECOND.migrate", "JsonObject.string", "JsonElement.string"}


def test_git_snapshot_compare_ignores_crlf_and_preserves_real_changed_function(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    def git(*args):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    git("init")
    git("config", "user.name", "Offline Test")
    git("config", "user.email", "offline@example.invalid")
    git("config", "core.autocrlf", "false")
    src = repo / "src"
    src.mkdir()
    before = 'class Sample {\n fun work() { old() }\n fun stable() = 1\n}\n'
    (src / "Sample.kt").write_bytes(before.encode())
    (src / "Unchanged.kt").write_bytes(b'fun same() = 42\n')
    git("add", ".")
    git("commit", "-m", "base")
    (src / "Sample.kt").write_bytes(before.replace("old()", "fresh()").replace("\n", "\r\n").encode())
    (src / "Unchanged.kt").write_bytes(b'fun same() = 42\r\n')
    result = analyze(repo, {"sourceRoots": [{"path": "src", "module": "app"}]})
    assert [c["path"] for c in result["changes"]] == ["src/Sample.kt"]
    changed = [s for f in result["after"]["files"] for s in f["symbols"] if s["kind"] == "function" and s["status"] != "unchanged"]
    assert [s["qualified"] for s in changed] == ["Sample.work"]
    assert changed[0]["flow"][0]["label"] == "fresh()"
    assert result["before"]["commit"] == result["after"]["commit"]
