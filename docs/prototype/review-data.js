/* TinyDB source excerpts: MIT; see tinydb-LICENSE.txt. Fixed historical input, not analysis output. */
window.reviewData = {
  "base": "8a2dc204c265c07ce8506a3599a28e720b6dcdd7",
  "head": "76d21d26c682e1ca6ca25bd8e81edf9f609ac52f",
  "before": [
    {
      "line": 425,
      "text": ""
    },
    {
      "line": 426,
      "text": "        # Define the function that will perform the update"
    },
    {
      "line": 427,
      "text": "        if callable(fields):"
    },
    {
      "line": 428,
      "text": "            def perform_update(table, doc_id):"
    },
    {
      "line": 429,
      "text": "                # Update documents by calling the update function provided by"
    },
    {
      "line": 430,
      "text": "                # the user"
    },
    {
      "line": 431,
      "text": "                fields(table[doc_id])"
    },
    {
      "line": 432,
      "text": "        else:"
    },
    {
      "line": 433,
      "text": "            def perform_update(table, doc_id):"
    },
    {
      "line": 434,
      "text": "                # Update documents by setting all fields from the provided data"
    },
    {
      "line": 435,
      "text": "                table[doc_id].update(fields)"
    },
    {
      "line": 436,
      "text": ""
    },
    {
      "line": 437,
      "text": "        if doc_ids is not None:"
    },
    {
      "line": 438,
      "text": "            # Perform the update operation for documents specified by a list"
    },
    {
      "line": 439,
      "text": "            # of document IDs"
    },
    {
      "line": 440,
      "text": ""
    },
    {
      "line": 441,
      "text": "            updated_ids = list(doc_ids)"
    },
    {
      "line": 442,
      "text": ""
    },
    {
      "line": 443,
      "text": "            def updater(table: dict):"
    },
    {
      "line": 444,
      "text": "                # Call the processing callback with all document IDs"
    },
    {
      "line": 445,
      "text": "                for doc_id in updated_ids:"
    },
    {
      "line": 446,
      "text": "                    perform_update(table, doc_id)"
    },
    {
      "line": 447,
      "text": ""
    },
    {
      "line": 448,
      "text": "            # Perform the update operation (see _update_table for details)"
    },
    {
      "line": 449,
      "text": "            self._update_table(updater)"
    },
    {
      "line": 450,
      "text": ""
    },
    {
      "line": 451,
      "text": "            return updated_ids"
    }
  ],
  "after": [
    {
      "line": 429,
      "text": ""
    },
    {
      "line": 430,
      "text": "        # Define the function that will perform the update"
    },
    {
      "line": 431,
      "text": "        if callable(fields):"
    },
    {
      "line": 432,
      "text": "            def perform_update(table, doc_id):"
    },
    {
      "line": 433,
      "text": "                # Update documents by calling the update function provided by"
    },
    {
      "line": 434,
      "text": "                # the user"
    },
    {
      "line": 435,
      "text": "                fields(table[doc_id])"
    },
    {
      "line": 436,
      "text": "        else:"
    },
    {
      "line": 437,
      "text": "            def perform_update(table, doc_id):"
    },
    {
      "line": 438,
      "text": "                # Update documents by setting all fields from the provided data"
    },
    {
      "line": 439,
      "text": "                table[doc_id].update(fields)"
    },
    {
      "line": 440,
      "text": ""
    },
    {
      "line": 441,
      "text": "        if doc_ids is not None:"
    },
    {
      "line": 442,
      "text": "            # Perform the update operation for documents specified by a list"
    },
    {
      "line": 443,
      "text": "            # of document IDs. Document IDs that don't exist in the table are"
    },
    {
      "line": 444,
      "text": "            # silently skipped, mirroring the behaviour of ``get(doc_ids=...)``"
    },
    {
      "line": 445,
      "text": "            # (see issue #591). The list of *actually* updated IDs is"
    },
    {
      "line": 446,
      "text": "            # determined inside the updater so it reflects the table state at"
    },
    {
      "line": 447,
      "text": "            # write time."
    },
    {
      "line": 448,
      "text": "            requested_ids = list(doc_ids)"
    },
    {
      "line": 449,
      "text": "            updated_ids: List[int] = []"
    },
    {
      "line": 450,
      "text": ""
    },
    {
      "line": 451,
      "text": "            def updater(table: dict):"
    },
    {
      "line": 452,
      "text": "                # Filter to IDs that exist *before* performing any updates,"
    },
    {
      "line": 453,
      "text": "                # so the operation is atomic: either every existing target is"
    },
    {
      "line": 454,
      "text": "                # updated, or none is."
    },
    {
      "line": 455,
      "text": "                updated_ids.extend("
    },
    {
      "line": 456,
      "text": "                    doc_id for doc_id in requested_ids if doc_id in table"
    },
    {
      "line": 457,
      "text": "                )"
    },
    {
      "line": 458,
      "text": "                for doc_id in updated_ids:"
    },
    {
      "line": 459,
      "text": "                    perform_update(table, doc_id)"
    },
    {
      "line": 460,
      "text": ""
    },
    {
      "line": 461,
      "text": "            # Perform the update operation (see _update_table for details)"
    },
    {
      "line": 462,
      "text": "            self._update_table(updater)"
    },
    {
      "line": 463,
      "text": ""
    },
    {
      "line": 464,
      "text": "            return updated_ids"
    }
  ],
  "diffs": {
    "tinydb/table.py": "diff --git a/tinydb/table.py b/tinydb/table.py\nindex 5641d22..e390c9b 100644\n--- a/tinydb/table.py\n+++ b/tinydb/table.py\n@@ -416,6 +416,10 @@ class Table:\n         \"\"\"\n         Update all matching documents to have a given set of fields.\n \n+        When ``doc_ids`` is given, IDs that don't refer to an existing\n+        document are silently skipped, and the returned list only contains\n+        the IDs that were actually updated.\n+\n         :param fields: the fields that the matching documents will have\n                        or a method that will update the documents\n         :param cond: which documents to update\n@@ -436,12 +440,21 @@ class Table:\n \n         if doc_ids is not None:\n             # Perform the update operation for documents specified by a list\n-            # of document IDs\n-\n-            updated_ids = list(doc_ids)\n+            # of document IDs. Document IDs that don't exist in the table are\n+            # silently skipped, mirroring the behaviour of ``get(doc_ids=...)``\n+            # (see issue #591). The list of *actually* updated IDs is\n+            # determined inside the updater so it reflects the table state at\n+            # write time.\n+            requested_ids = list(doc_ids)\n+            updated_ids: List[int] = []\n \n             def updater(table: dict):\n-                # Call the processing callback with all document IDs\n+                # Filter to IDs that exist *before* performing any updates,\n+                # so the operation is atomic: either every existing target is\n+                # updated, or none is.\n+                updated_ids.extend(\n+                    doc_id for doc_id in requested_ids if doc_id in table\n+                )\n                 for doc_id in updated_ids:\n                     perform_update(table, doc_id)\n \n@@ -579,12 +592,10 @@ class Table:\n                              \"specify a doc_id. Hint: use a table.Document \"\n                              \"object.\")\n \n-        # Perform the update operation\n-        try:\n-            updated_docs: Optional[List[int]] = self.update(document, cond, doc_ids)\n-        except KeyError:\n-            # This happens when a doc_id is specified, but it's missing\n-            updated_docs = None\n+        # Perform the update operation. ``update`` returns an empty list\n+        # when no existing document matches the doc_id / query, in which\n+        # case we fall through to insert below.\n+        updated_docs = self.update(document, cond, doc_ids)\n \n         # If documents have been updated: return their IDs\n         if updated_docs:\n@@ -602,23 +613,33 @@ class Table:\n         \"\"\"\n         Remove all matching documents.\n \n+        When ``doc_ids`` is given, IDs that don't refer to an existing\n+        document are silently skipped, and the returned list only contains\n+        the IDs that were actually removed.\n+\n         :param cond: the condition to check against\n         :param doc_ids: a list of document IDs\n         :returns: a list containing the removed documents' ID\n         \"\"\"\n         if doc_ids is not None:\n-            # This function returns the list of IDs for the documents that have\n-            # been removed. When removing documents identified by a set of\n-            # document IDs, it's this list of document IDs we need to return\n-            # later.\n-            # We convert the document ID iterator into a list, so we can both\n-            # use the document IDs to remove the specified documents and\n-            # to return the list of affected document IDs\n-            removed_ids = list(doc_ids)\n+            # This function returns the list of IDs for the documents that\n+            # have been removed. Document IDs that don't exist in the table\n+            # are silently skipped, mirroring the behaviour of\n+            # ``get(doc_ids=...)`` (see issue #591). The list of *actually*\n+            # removed IDs is determined inside the updater so it reflects the\n+            # table state at write time.\n+            requested_ids = list(doc_ids)\n+            removed_ids: List[int] = []\n \n             def updater(table: dict):\n+                # Filter to IDs that exist *before* performing any removals,\n+                # so the operation is atomic: either every existing target is\n+                # removed, or none is.\n+                removed_ids.extend(\n+                    doc_id for doc_id in requested_ids if doc_id in table\n+                )\n                 for doc_id in removed_ids:\n-                    table.pop(doc_id)\n+                    del table[doc_id]\n \n             # Perform the remove operation\n             self._update_table(updater)\n",
    "tests/test_tinydb.py": "diff --git a/tests/test_tinydb.py b/tests/test_tinydb.py\nindex 655027a..762a460 100644\n--- a/tests/test_tinydb.py\n+++ b/tests/test_tinydb.py\n@@ -211,6 +211,25 @@ def test_remove_returns_ids(db: TinyDB):\n     assert db.remove(where('char') == 'b') == [2]\n \n \n+def test_remove_ids_missing(db: TinyDB):\n+    # Removing by a non-existent doc_id should not raise; the returned list\n+    # only contains IDs that were actually removed. This mirrors the silent\n+    # behaviour of ``get(doc_id=N)`` / ``get(doc_ids=[N])``.\n+    assert db.remove(doc_ids=[99]) == []\n+    assert len(db) == 3\n+\n+\n+def test_remove_ids_mixed(db: TinyDB):\n+    # When a mix of existing and missing IDs is passed, only the existing\n+    # documents should be removed and the missing IDs ignored. The removal\n+    # must be atomic - either every existing target is removed or none is\n+    # (no partial state on failure).\n+    assert sorted(db.remove(doc_ids=[1, 99])) == [1]\n+    assert len(db) == 2\n+    assert db.get(doc_id=1) is None\n+    assert db.get(doc_id=2) is not None\n+\n+\n def test_update(db: TinyDB):\n     assert len(db) == 3\n \n@@ -265,6 +284,34 @@ def test_update_ids(db: TinyDB):\n     assert db.count(where('int') == 2) == 2\n \n \n+def test_update_ids_missing(db: TinyDB):\n+    # Updating by a non-existent doc_id should not raise; the returned list\n+    # only contains IDs that were actually updated. This mirrors the silent\n+    # behaviour of ``get(doc_id=N)`` / ``get(doc_ids=[N])``.\n+    assert db.update({'int': 9}, doc_ids=[99]) == []\n+    assert db.count(where('int') == 9) == 0\n+    assert db.count(where('int') == 1) == 3\n+\n+\n+def test_update_ids_mixed(db: TinyDB):\n+    # When a mix of existing and missing IDs is passed, only the existing\n+    # documents should be updated and the missing IDs ignored. The update\n+    # must be atomic - either every existing target is updated or none is\n+    # (no partial state on failure).\n+    assert sorted(db.update({'int': 9}, doc_ids=[1, 99])) == [1]\n+    assert db.count(where('int') == 9) == 1\n+    assert db.count(where('int') == 1) == 2\n+\n+\n+def test_doc_id_missing_consistency(db: TinyDB):\n+    # ``get``, ``update`` and ``remove`` must all behave consistently when\n+    # given an ID that does not exist (see #591). None of them should raise.\n+    assert db.get(doc_id=99) is None\n+    assert db.get(doc_ids=[99]) == []\n+    assert db.update({'int': 9}, doc_ids=[99]) == []\n+    assert db.remove(doc_ids=[99]) == []\n+\n+\n def test_update_multiple(db: TinyDB):\n     assert len(db) == 3\n \n",
    "docs/changelog.rst": "diff --git a/docs/changelog.rst b/docs/changelog.rst\nindex 84d7802..9902ade 100644\n--- a/docs/changelog.rst\n+++ b/docs/changelog.rst\n@@ -22,7 +22,14 @@ see `semver.org <http://semver.org/>`_\n unreleased\n ^^^^^^^^^^\n \n-- *nothing yet*\n+- Fix: Make ``Table.update(doc_ids=...)`` and ``Table.remove(doc_ids=...)``\n+  behave consistently with ``Table.get(doc_id=...)`` when given document\n+  IDs that don't exist: missing IDs are now silently skipped and the\n+  returned list only contains IDs that were actually updated/removed.\n+  Previously both methods raised ``KeyError``, and ``update`` could leave\n+  the table in a partially-updated state when a mix of existing and\n+  missing IDs was passed\n+  (see `issue 591 <https://github.com/msiemens/tinydb/issues/591>`_).\n \n v4.8.2 (2024-10-12)\n ^^^^^^^^^^^^^^^^^^^\n"
  }
};
