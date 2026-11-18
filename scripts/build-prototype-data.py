import ast
import json
import subprocess
from pathlib import Path

sha = '76d21d26c682e1ca6ca25bd8e81edf9f609ac52f'
def git(*args):
    return subprocess.check_output(['git', '-C', 'data/local/tinydb', *args], text=True, encoding='utf8')
paths = [p for p in git('ls-tree', '-r', '--name-only', sha).splitlines() if p.startswith('tinydb/') and p.endswith('.py')]
modules = []
imports = []
calls = []
for path in paths:
    name = Path(path).stem
    tree = ast.parse(git('show', sha + ':' + path))
    defs = []
    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.scope = []
        def visit_ClassDef(self, node):
            defs.append({'name': '.'.join(self.scope + [node.name]), 'kind': 'class', 'line': node.lineno})
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()
        def visit_FunctionDef(self, node):
            defs.append({'name': '.'.join(self.scope + [node.name]), 'kind': 'function', 'line': node.lineno})
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()
    Visitor().visit(tree)
    modules.append({'id':name, 'path':path, 'defs':defs})
    for n in tree.body:
        if isinstance(n, ast.ImportFrom) and n.level == 1:
            imports.append({'from':name, 'to':n.module or '__init__', 'line':n.lineno, 'kind':'import'})
    if name == 'table':
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Table')
        methods = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
        for fn in cls.body:
            if not isinstance(fn, ast.FunctionDef):
                continue
            for n in ast.walk(fn):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == 'self' and n.func.attr in methods:
                    calls.append({'from':fn.name, 'to':n.func.attr, 'line':n.lineno, 'kind':'call'})
data = {'sha':sha, 'modules':modules, 'imports':imports, 'calls':calls}
Path('docs/prototype/graph-data.js').write_text('/* Fixed Git snapshot; AST syntax evidence only, not a semantic resolver. */\nwindow.prototypeGraphData = ' + json.dumps(data, ensure_ascii=False, indent=2) + ';\n', encoding='utf8')
print(json.dumps({'modules':len(modules),'definitions':sum(len(m['defs']) for m in modules),'imports':len(imports),'tableCallSites':len(calls)}))
