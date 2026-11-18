/* Fixed Git snapshot; AST syntax evidence only, not a semantic resolver. */
window.prototypeGraphData = {
  "sha": "76d21d26c682e1ca6ca25bd8e81edf9f609ac52f",
  "modules": [
    {
      "id": "__init__",
      "path": "tinydb/__init__.py",
      "defs": []
    },
    {
      "id": "database",
      "path": "tinydb/database.py",
      "defs": [
        {
          "name": "TinyDB",
          "kind": "class",
          "line": 17
        },
        {
          "name": "TinyDB.__init__",
          "kind": "function",
          "line": 87
        },
        {
          "name": "TinyDB.__repr__",
          "kind": "function",
          "line": 100
        },
        {
          "name": "TinyDB.table",
          "kind": "function",
          "line": 111
        },
        {
          "name": "TinyDB.tables",
          "kind": "function",
          "line": 135
        },
        {
          "name": "TinyDB.drop_tables",
          "kind": "function",
          "line": 163
        },
        {
          "name": "TinyDB.drop_table",
          "kind": "function",
          "line": 176
        },
        {
          "name": "TinyDB.storage",
          "kind": "function",
          "line": 205
        },
        {
          "name": "TinyDB.close",
          "kind": "function",
          "line": 214
        },
        {
          "name": "TinyDB.__enter__",
          "kind": "function",
          "line": 232
        },
        {
          "name": "TinyDB.__exit__",
          "kind": "function",
          "line": 244
        },
        {
          "name": "TinyDB.__getattr__",
          "kind": "function",
          "line": 251
        },
        {
          "name": "TinyDB.__len__",
          "kind": "function",
          "line": 260
        },
        {
          "name": "TinyDB.__iter__",
          "kind": "function",
          "line": 270
        }
      ]
    },
    {
      "id": "middlewares",
      "path": "tinydb/middlewares.py",
      "defs": [
        {
          "name": "Middleware",
          "kind": "class",
          "line": 10
        },
        {
          "name": "Middleware.__init__",
          "kind": "function",
          "line": 21
        },
        {
          "name": "Middleware.__call__",
          "kind": "function",
          "line": 25
        },
        {
          "name": "Middleware.__getattr__",
          "kind": "function",
          "line": 67
        },
        {
          "name": "CachingMiddleware",
          "kind": "class",
          "line": 76
        },
        {
          "name": "CachingMiddleware.__init__",
          "kind": "function",
          "line": 88
        },
        {
          "name": "CachingMiddleware.read",
          "kind": "function",
          "line": 96
        },
        {
          "name": "CachingMiddleware.write",
          "kind": "function",
          "line": 104
        },
        {
          "name": "CachingMiddleware.flush",
          "kind": "function",
          "line": 113
        },
        {
          "name": "CachingMiddleware.close",
          "kind": "function",
          "line": 122
        }
      ]
    },
    {
      "id": "mypy_plugin",
      "path": "tinydb/mypy_plugin.py",
      "defs": [
        {
          "name": "TinyDBPlugin",
          "kind": "class",
          "line": 12
        },
        {
          "name": "TinyDBPlugin.__init__",
          "kind": "function",
          "line": 13
        },
        {
          "name": "TinyDBPlugin.get_dynamic_class_hook",
          "kind": "function",
          "line": 18
        },
        {
          "name": "TinyDBPlugin.get_dynamic_class_hook.hook",
          "kind": "function",
          "line": 20
        },
        {
          "name": "plugin",
          "kind": "function",
          "line": 37
        }
      ]
    },
    {
      "id": "operations",
      "path": "tinydb/operations.py",
      "defs": [
        {
          "name": "delete",
          "kind": "function",
          "line": 15
        },
        {
          "name": "delete.transform",
          "kind": "function",
          "line": 19
        },
        {
          "name": "add",
          "kind": "function",
          "line": 25
        },
        {
          "name": "add.transform",
          "kind": "function",
          "line": 29
        },
        {
          "name": "subtract",
          "kind": "function",
          "line": 35
        },
        {
          "name": "subtract.transform",
          "kind": "function",
          "line": 39
        },
        {
          "name": "set",
          "kind": "function",
          "line": 45
        },
        {
          "name": "set.transform",
          "kind": "function",
          "line": 49
        },
        {
          "name": "increment",
          "kind": "function",
          "line": 55
        },
        {
          "name": "increment.transform",
          "kind": "function",
          "line": 59
        },
        {
          "name": "decrement",
          "kind": "function",
          "line": 65
        },
        {
          "name": "decrement.transform",
          "kind": "function",
          "line": 69
        }
      ]
    },
    {
      "id": "queries",
      "path": "tinydb/queries.py",
      "defs": [
        {
          "name": "is_sequence",
          "kind": "function",
          "line": 27
        },
        {
          "name": "QueryLike",
          "kind": "class",
          "line": 31
        },
        {
          "name": "QueryLike.__call__",
          "kind": "function",
          "line": 50
        },
        {
          "name": "QueryLike.__hash__",
          "kind": "function",
          "line": 52
        },
        {
          "name": "QueryInstance",
          "kind": "class",
          "line": 55
        },
        {
          "name": "QueryInstance.__init__",
          "kind": "function",
          "line": 72
        },
        {
          "name": "QueryInstance.is_cacheable",
          "kind": "function",
          "line": 76
        },
        {
          "name": "QueryInstance.__call__",
          "kind": "function",
          "line": 79
        },
        {
          "name": "QueryInstance.__hash__",
          "kind": "function",
          "line": 88
        },
        {
          "name": "QueryInstance.__repr__",
          "kind": "function",
          "line": 94
        },
        {
          "name": "QueryInstance.__eq__",
          "kind": "function",
          "line": 97
        },
        {
          "name": "QueryInstance.__and__",
          "kind": "function",
          "line": 105
        },
        {
          "name": "QueryInstance.__or__",
          "kind": "function",
          "line": 115
        },
        {
          "name": "QueryInstance.__invert__",
          "kind": "function",
          "line": 125
        },
        {
          "name": "Query",
          "kind": "class",
          "line": 130
        },
        {
          "name": "Query.__init__",
          "kind": "function",
          "line": 163
        },
        {
          "name": "Query.__init__.notest",
          "kind": "function",
          "line": 168
        },
        {
          "name": "Query.__repr__",
          "kind": "function",
          "line": 176
        },
        {
          "name": "Query.__hash__",
          "kind": "function",
          "line": 179
        },
        {
          "name": "Query.__getattr__",
          "kind": "function",
          "line": 182
        },
        {
          "name": "Query.__getitem__",
          "kind": "function",
          "line": 196
        },
        {
          "name": "Query._generate_test",
          "kind": "function",
          "line": 207
        },
        {
          "name": "Query._generate_test.runner",
          "kind": "function",
          "line": 224
        },
        {
          "name": "Query.__eq__",
          "kind": "function",
          "line": 243
        },
        {
          "name": "Query.__ne__",
          "kind": "function",
          "line": 256
        },
        {
          "name": "Query.__lt__",
          "kind": "function",
          "line": 269
        },
        {
          "name": "Query.__le__",
          "kind": "function",
          "line": 282
        },
        {
          "name": "Query.__gt__",
          "kind": "function",
          "line": 295
        },
        {
          "name": "Query.__ge__",
          "kind": "function",
          "line": 308
        },
        {
          "name": "Query.exists",
          "kind": "function",
          "line": 321
        },
        {
          "name": "Query.matches",
          "kind": "function",
          "line": 332
        },
        {
          "name": "Query.matches.test",
          "kind": "function",
          "line": 341
        },
        {
          "name": "Query.search",
          "kind": "function",
          "line": 349
        },
        {
          "name": "Query.search.test",
          "kind": "function",
          "line": 360
        },
        {
          "name": "Query.test",
          "kind": "function",
          "line": 368
        },
        {
          "name": "Query.any",
          "kind": "function",
          "line": 393
        },
        {
          "name": "Query.any.test",
          "kind": "function",
          "line": 416
        },
        {
          "name": "Query.any.test",
          "kind": "function",
          "line": 420
        },
        {
          "name": "Query.all",
          "kind": "function",
          "line": 428
        },
        {
          "name": "Query.all.test",
          "kind": "function",
          "line": 449
        },
        {
          "name": "Query.all.test",
          "kind": "function",
          "line": 453
        },
        {
          "name": "Query.one_of",
          "kind": "function",
          "line": 461
        },
        {
          "name": "Query.fragment",
          "kind": "function",
          "line": 474
        },
        {
          "name": "Query.fragment.test",
          "kind": "function",
          "line": 475
        },
        {
          "name": "Query.noop",
          "kind": "function",
          "line": 488
        },
        {
          "name": "Query.map",
          "kind": "function",
          "line": 500
        },
        {
          "name": "where",
          "kind": "function",
          "line": 516
        }
      ]
    },
    {
      "id": "storages",
      "path": "tinydb/storages.py",
      "defs": [
        {
          "name": "touch",
          "kind": "function",
          "line": 16
        },
        {
          "name": "Storage",
          "kind": "class",
          "line": 36
        },
        {
          "name": "Storage.read",
          "kind": "function",
          "line": 48
        },
        {
          "name": "Storage.write",
          "kind": "function",
          "line": 60
        },
        {
          "name": "Storage.close",
          "kind": "function",
          "line": 71
        },
        {
          "name": "JSONStorage",
          "kind": "class",
          "line": 79
        },
        {
          "name": "JSONStorage.__init__",
          "kind": "function",
          "line": 84
        },
        {
          "name": "JSONStorage.close",
          "kind": "function",
          "line": 122
        },
        {
          "name": "JSONStorage.read",
          "kind": "function",
          "line": 125
        },
        {
          "name": "JSONStorage.write",
          "kind": "function",
          "line": 142
        },
        {
          "name": "MemoryStorage",
          "kind": "class",
          "line": 164
        },
        {
          "name": "MemoryStorage.__init__",
          "kind": "function",
          "line": 169
        },
        {
          "name": "MemoryStorage.read",
          "kind": "function",
          "line": 177
        },
        {
          "name": "MemoryStorage.write",
          "kind": "function",
          "line": 180
        }
      ]
    },
    {
      "id": "table",
      "path": "tinydb/table.py",
      "defs": [
        {
          "name": "Document",
          "kind": "class",
          "line": 28
        },
        {
          "name": "Document.__init__",
          "kind": "function",
          "line": 36
        },
        {
          "name": "Table",
          "kind": "class",
          "line": 41
        },
        {
          "name": "Table.__init__",
          "kind": "function",
          "line": 100
        },
        {
          "name": "Table.__repr__",
          "kind": "function",
          "line": 120
        },
        {
          "name": "Table.name",
          "kind": "function",
          "line": 130
        },
        {
          "name": "Table.storage",
          "kind": "function",
          "line": 137
        },
        {
          "name": "Table.insert",
          "kind": "function",
          "line": 143
        },
        {
          "name": "Table.insert.updater",
          "kind": "function",
          "line": 168
        },
        {
          "name": "Table.insert_multiple",
          "kind": "function",
          "line": 183
        },
        {
          "name": "Table.insert_multiple.updater",
          "kind": "function",
          "line": 192
        },
        {
          "name": "Table.all",
          "kind": "function",
          "line": 227
        },
        {
          "name": "Table.search",
          "kind": "function",
          "line": 241
        },
        {
          "name": "Table.get",
          "kind": "function",
          "line": 286
        },
        {
          "name": "Table.get",
          "kind": "function",
          "line": 289
        },
        {
          "name": "Table.get",
          "kind": "function",
          "line": 294
        },
        {
          "name": "Table.get",
          "kind": "function",
          "line": 299
        },
        {
          "name": "Table.get",
          "kind": "function",
          "line": 304
        },
        {
          "name": "Table.get",
          "kind": "function",
          "line": 309
        },
        {
          "name": "Table.get",
          "kind": "function",
          "line": 314
        },
        {
          "name": "Table.get",
          "kind": "function",
          "line": 319
        },
        {
          "name": "Table.get",
          "kind": "function",
          "line": 323
        },
        {
          "name": "Table.contains",
          "kind": "function",
          "line": 386
        },
        {
          "name": "Table.update",
          "kind": "function",
          "line": 410
        },
        {
          "name": "Table.update.perform_update",
          "kind": "function",
          "line": 432
        },
        {
          "name": "Table.update.perform_update",
          "kind": "function",
          "line": 437
        },
        {
          "name": "Table.update.updater",
          "kind": "function",
          "line": 451
        },
        {
          "name": "Table.update.updater",
          "kind": "function",
          "line": 472
        },
        {
          "name": "Table.update.updater",
          "kind": "function",
          "line": 500
        },
        {
          "name": "Table.update_multiple",
          "kind": "function",
          "line": 514
        },
        {
          "name": "Table.update_multiple.perform_update",
          "kind": "function",
          "line": 527
        },
        {
          "name": "Table.update_multiple.updater",
          "kind": "function",
          "line": 542
        },
        {
          "name": "Table.upsert",
          "kind": "function",
          "line": 566
        },
        {
          "name": "Table.remove",
          "kind": "function",
          "line": 608
        },
        {
          "name": "Table.remove.updater",
          "kind": "function",
          "line": 634
        },
        {
          "name": "Table.remove.updater",
          "kind": "function",
          "line": 655
        },
        {
          "name": "Table.truncate",
          "kind": "function",
          "line": 681
        },
        {
          "name": "Table.count",
          "kind": "function",
          "line": 692
        },
        {
          "name": "Table.clear_cache",
          "kind": "function",
          "line": 701
        },
        {
          "name": "Table.__len__",
          "kind": "function",
          "line": 708
        },
        {
          "name": "Table.__iter__",
          "kind": "function",
          "line": 715
        },
        {
          "name": "Table._get_next_id",
          "kind": "function",
          "line": 727
        },
        {
          "name": "Table._read_table",
          "kind": "function",
          "line": 762
        },
        {
          "name": "Table._update_table",
          "kind": "function",
          "line": 787
        }
      ]
    },
    {
      "id": "utils",
      "path": "tinydb/utils.py",
      "defs": [
        {
          "name": "with_typehint",
          "kind": "function",
          "line": 17
        },
        {
          "name": "LRUCache",
          "kind": "class",
          "line": 39
        },
        {
          "name": "LRUCache.__init__",
          "kind": "function",
          "line": 53
        },
        {
          "name": "LRUCache.lru",
          "kind": "function",
          "line": 58
        },
        {
          "name": "LRUCache.length",
          "kind": "function",
          "line": 62
        },
        {
          "name": "LRUCache.clear",
          "kind": "function",
          "line": 65
        },
        {
          "name": "LRUCache.__len__",
          "kind": "function",
          "line": 68
        },
        {
          "name": "LRUCache.__contains__",
          "kind": "function",
          "line": 71
        },
        {
          "name": "LRUCache.__setitem__",
          "kind": "function",
          "line": 74
        },
        {
          "name": "LRUCache.__delitem__",
          "kind": "function",
          "line": 77
        },
        {
          "name": "LRUCache.__getitem__",
          "kind": "function",
          "line": 80
        },
        {
          "name": "LRUCache.__iter__",
          "kind": "function",
          "line": 87
        },
        {
          "name": "LRUCache.get",
          "kind": "function",
          "line": 90
        },
        {
          "name": "LRUCache.set",
          "kind": "function",
          "line": 100
        },
        {
          "name": "FrozenDict",
          "kind": "class",
          "line": 114
        },
        {
          "name": "FrozenDict.__hash__",
          "kind": "function",
          "line": 123
        },
        {
          "name": "FrozenDict._immutable",
          "kind": "function",
          "line": 127
        },
        {
          "name": "FrozenDict.update",
          "kind": "function",
          "line": 137
        },
        {
          "name": "FrozenDict.pop",
          "kind": "function",
          "line": 140
        },
        {
          "name": "freeze",
          "kind": "function",
          "line": 144
        }
      ]
    },
    {
      "id": "version",
      "path": "tinydb/version.py",
      "defs": []
    }
  ],
  "imports": [
    {
      "from": "__init__",
      "to": "queries",
      "line": 27,
      "kind": "import"
    },
    {
      "from": "__init__",
      "to": "storages",
      "line": 28,
      "kind": "import"
    },
    {
      "from": "__init__",
      "to": "database",
      "line": 29,
      "kind": "import"
    },
    {
      "from": "__init__",
      "to": "version",
      "line": 30,
      "kind": "import"
    },
    {
      "from": "database",
      "to": "__init__",
      "line": 7,
      "kind": "import"
    },
    {
      "from": "database",
      "to": "storages",
      "line": 8,
      "kind": "import"
    },
    {
      "from": "database",
      "to": "table",
      "line": 9,
      "kind": "import"
    },
    {
      "from": "database",
      "to": "utils",
      "line": 10,
      "kind": "import"
    },
    {
      "from": "queries",
      "to": "utils",
      "line": 22,
      "kind": "import"
    },
    {
      "from": "table",
      "to": "queries",
      "line": 21,
      "kind": "import"
    },
    {
      "from": "table",
      "to": "storages",
      "line": 22,
      "kind": "import"
    },
    {
      "from": "table",
      "to": "utils",
      "line": 23,
      "kind": "import"
    }
  ],
  "calls": [
    {
      "from": "__init__",
      "to": "_update_table",
      "line": 118,
      "kind": "call"
    },
    {
      "from": "insert",
      "to": "_update_table",
      "line": 179,
      "kind": "call"
    },
    {
      "from": "insert",
      "to": "_get_next_id",
      "line": 165,
      "kind": "call"
    },
    {
      "from": "insert_multiple",
      "to": "_update_table",
      "line": 223,
      "kind": "call"
    },
    {
      "from": "insert_multiple",
      "to": "_get_next_id",
      "line": 218,
      "kind": "call"
    },
    {
      "from": "search",
      "to": "_read_table",
      "line": 260,
      "kind": "call"
    },
    {
      "from": "get",
      "to": "_read_table",
      "line": 342,
      "kind": "call"
    },
    {
      "from": "get",
      "to": "_read_table",
      "line": 375,
      "kind": "call"
    },
    {
      "from": "contains",
      "to": "get",
      "line": 402,
      "kind": "call"
    },
    {
      "from": "contains",
      "to": "get",
      "line": 406,
      "kind": "call"
    },
    {
      "from": "update",
      "to": "_update_table",
      "line": 462,
      "kind": "call"
    },
    {
      "from": "update",
      "to": "_update_table",
      "line": 491,
      "kind": "call"
    },
    {
      "from": "update",
      "to": "_update_table",
      "line": 510,
      "kind": "call"
    },
    {
      "from": "update_multiple",
      "to": "_update_table",
      "line": 562,
      "kind": "call"
    },
    {
      "from": "upsert",
      "to": "update",
      "line": 598,
      "kind": "call"
    },
    {
      "from": "upsert",
      "to": "insert",
      "line": 606,
      "kind": "call"
    },
    {
      "from": "remove",
      "to": "_update_table",
      "line": 645,
      "kind": "call"
    },
    {
      "from": "remove",
      "to": "_update_table",
      "line": 675,
      "kind": "call"
    },
    {
      "from": "truncate",
      "to": "_update_table",
      "line": 687,
      "kind": "call"
    },
    {
      "from": "count",
      "to": "search",
      "line": 699,
      "kind": "call"
    },
    {
      "from": "__len__",
      "to": "_read_table",
      "line": 713,
      "kind": "call"
    },
    {
      "from": "__iter__",
      "to": "_read_table",
      "line": 723,
      "kind": "call"
    },
    {
      "from": "_get_next_id",
      "to": "_read_table",
      "line": 743,
      "kind": "call"
    },
    {
      "from": "_update_table",
      "to": "clear_cache",
      "line": 837,
      "kind": "call"
    }
  ]
};
