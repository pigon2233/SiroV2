"""Reproduce a trusted readiness race using only repository source and synthetic callbacks."""
from pathlib import Path
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).parent


def probe(source: Path, module_name: str, capture: bool) -> dict:
    spec = importlib.util.spec_from_file_location(module_name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    checks = 0
    executions = 0

    def readiness():
        nonlocal checks
        checks += 1
        return checks % 2 == 1

    async def execute(arguments):
        nonlocal executions
        executions += 1
        raise AssertionError('read-only capture dispatched')

    catalog = module.ToolCatalog((module.ToolDescriptor(
        'computer.execute', module.DEFAULT_MODEL_TOOLS[1], execute, readiness,
        'python.argv', 'computer'),))
    if capture:
        view = catalog.capture()
        rows, definitions = view.inventory, view.definitions
    else:
        rows, definitions = catalog.snapshot(), catalog.definitions()
    result = {'available': rows[0]['available'], 'definition_names': [d.name for d in definitions],
              'readiness_checks': checks, 'executions': executions}
    return result


before = probe(OUTPUT / 'before/src/siro/services/tools/orchestrator.py', 'ri002_before', False)
after = probe(ROOT / 'src/siro/services/tools/orchestrator.py', 'ri002_after', True)
assert before['available'] and before['definition_names'] == [] and before['readiness_checks'] == 2
assert after['available'] and after['definition_names'] == ['computer.execute'] and after['readiness_checks'] == 1
assert before['executions'] == after['executions'] == 0
(OUTPUT / 'capture-before-after.json').write_text(json.dumps({'before': before, 'after': after}, indent=2)+'\n')
print('capture mismatch reproduced before; same-sample capture verified after; zero effects')
