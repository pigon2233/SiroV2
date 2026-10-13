from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _run_result_renderer(checks: str) -> None:
    """Exercise the real renderer with a synthetic DOM; no provider or browser operation."""
    html = Path("src/siro/services/presentation/static/index.html").read_text()
    script = html[
        html.index("      function updateToolProposal(") : html.index(
            "      async function submitText("
        )
    ]
    setup = r"""
const assert = require('node:assert/strict');
const cards = new Map();
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this._text = ''; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child=>child.textContent).join(''); }
  set innerHTML(value) { throw new Error('Tool result entered HTML'); }
  appendChild(child) { this.children.push(child); return child; }
  querySelector(selector) {
    if (selector === '.tool-status')
      return this.children.find(child=>child.className==='tool-status');
    return undefined;
  }
}
const document = {querySelector: selector=>cards.get(selector),
  createElement: tag=>new Element(tag)};
const show = data=>{
  const card = new Element('div'); cards.set('#tool-'+data.proposal_id,card);
  renderToolResult(data); return card;
};
"""
    result = subprocess.run(
        ["node", "-e", setup + script + checks], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("reason", "explanation"),
    [
        ("invalid_url", "網址格式不正確"),
        ("main_origin_denied", "主頁不在這次授權的網站範圍"),
        ("redirect_denied", "網站轉往未授權的來源"),
        ("subresource_denied", "部分跨站資源已阻擋"),
    ],
)
def test_scope_failure_shows_fixed_chinese_reason_with_compatible_error_name(
    reason: str, explanation: str
) -> None:
    import json

    _run_result_renderer(
        "const reason="
        + json.dumps(reason)
        + "; const explanation="
        + json.dumps(explanation)
        + r""";
const card = show({proposal_id:'failure', capability:'browser.navigate+read',
  error:'ScopeViolation', result:{reason}});
assert(card.textContent.startsWith('失敗\uFF1AScopeViolation'));
assert(card.textContent.includes(explanation));
assert(!card.textContent.includes('完成\uFF1A'));
assert(!card.textContent.includes(reason));
"""
    )


def test_unknown_prototype_and_malicious_failure_reasons_are_not_shown() -> None:
    _run_result_renderer(
        r"""
for (const reason of ['unknown-private-canary', '__proto__', 'constructor', 'toString',
  '<img src=x onerror="globalThis.injected=1">private-canary']) {
  const card = show({proposal_id:'unknown', capability:'browser.read',
    error:'ScopeViolation', result:{reason, message:'private-message-canary'}});
  assert.equal(card.textContent,'失敗\uFF1AScopeViolation');
  assert(!card.textContent.includes('private-canary'));
  assert(!card.textContent.includes('private-message-canary'));
  assert.equal(globalThis.injected,undefined);
}
"""
    )


def test_ordinary_and_old_error_payloads_keep_existing_safe_display() -> None:
    _run_result_renderer(
        r"""
let card = show({proposal_id:'ordinary', capability:'browser.read', error:'RuntimeError',
  result:{reason:'redirect_denied',message:'private-canary'}});
assert.equal(card.textContent,'失敗\uFF1ARuntimeError');
card = show({proposal_id:'old',capability:'browser.navigate+read',error:'ScopeViolation'});
assert.equal(card.textContent,'失敗\uFF1AScopeViolation');
"""
    )


def test_partial_with_missing_or_malicious_reason_stays_partial_and_does_not_leak_reason() -> None:
    _run_result_renderer(
        r"""
for (const reason of [undefined,'<img src=x onerror="globalThis.injected=1">private-canary']) {
  const card = show({proposal_id:'unknown-partial',capability:'browser.read',error:null,
    result:{load_status:'partial',reason,title:'Synthetic title',
      url:'https://synthetic.invalid/partial',text:'Synthetic visible text'}});
  assert(card.textContent.includes('部分載入'));
  assert(card.textContent.includes('可能不完整'));
  assert(card.textContent.includes('Synthetic visible text'));
  assert(!card.textContent.includes('完成\uFF1A'));
  assert(!card.textContent.includes('private-canary'));
  assert.equal(globalThis.injected,undefined);
}
"""
    )


@pytest.mark.parametrize(
    "capability", ["browser.navigate+read", "browser.read", "browser.fill", "browser.click"]
)
def test_partial_browser_readback_stays_readable_and_never_reports_complete(
    capability: str,
) -> None:
    import json

    _run_result_renderer(
        "const capability="
        + json.dumps(capability)
        + r""";
const card = show({proposal_id:'partial',capability,error:null,result:{
  load_status:'partial',reason:'subresource_denied',
  title:'<img src=x onerror="globalThis.injected=1">Synthetic title',
  url:'https://synthetic.invalid/readback',text:'Synthetic visible text'}});
assert(card.textContent.includes('部分載入'));
assert(card.textContent.includes('部分跨站資源已阻擋'));
assert(card.textContent.includes('Synthetic visible text'));
assert(card.textContent.includes('<img src=x'));
assert(!card.textContent.includes('完成\uFF1A'));
assert.equal(globalThis.injected,undefined);
// Repeated delivery updates one status node instead of accumulating contradictory results.
renderToolResult({proposal_id:'partial',capability,error:'ScopeViolation',
  result:{reason:'redirect_denied'}});
assert.equal(card.children.length,1);
assert(!card.textContent.includes('Synthetic visible text'));
assert(card.textContent.includes('網站轉往未授權的來源'));
"""
    )


def test_full_browser_and_computer_results_keep_existing_completion_contract() -> None:
    _run_result_renderer(
        r"""
const browser = show({proposal_id:'full',capability:'browser.navigate+read',error:null,
  result:{title:'Synthetic title',url:'https://synthetic.invalid/full',text:'Synthetic text'}});
assert(browser.textContent.startsWith('完成\uFF1ASynthetic title'));
assert(browser.textContent.includes('Synthetic text'));
assert(!browser.textContent.includes('部分載入'));
const computer = show({proposal_id:'computer',capability:'computer.execute',error:null,
  result:{returncode:0,stdout:'<svg onload="globalThis.injected=1">literal output',
    truncated:false}});
assert(computer.textContent.includes('完成\uFF08結束碼 0\uFF09'));
assert(computer.textContent.includes('<svg onload='));
assert.equal(globalThis.injected,undefined);
"""
    )
