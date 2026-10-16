from __future__ import annotations

import pytest
from test_frontend_control import run_control


def test_real_frontend_wait_notice_clears_on_delta_without_replaying_actions() -> None:
    run_control(
        """
// The shared minimal DOM omits DOMStringMap; provide this standard element property.
document.querySelector('#service-notice').dataset = {};
const owner = await readyControl();
owner.message({type:'turn_started', turn_id:'turn-one', stream_id:'stream-one'});
owner.message({type:'assistant_started', session_id:'browser', stream_id:'stream-one'});
owner.message({type:'assistant_retry_wait', session_id:'browser',
  stream_id:'stream-one', retry_after_seconds:60});
const notice = document.querySelector('#service-notice');
assert.equal(notice.hidden, false);
assert.match(notice.textContent, /60/);
assert.match(notice.textContent, /不會重做/);
assert.equal(targetCalls().length, 0);
owner.message({type:'assistant_delta', session_id:'browser',
  stream_id:'stream-one', text:'confirmed answer'});
assert.equal(notice.hidden, true);
assert.equal(targetCalls().length, 0);
"""
    )


@pytest.mark.parametrize("state", ["cancelled", "failed"])
def test_real_frontend_terminal_clears_wait_notice_and_rejects_late_wait(state: str) -> None:
    run_control(
        f"const terminalState = {state!r};\n"
        + """
// The shared minimal DOM omits DOMStringMap; provide this standard element property.
document.querySelector('#service-notice').dataset = {};
const owner = await readyControl();
owner.message({type:'turn_started', turn_id:'turn-one', stream_id:'stream-one'});
owner.message({type:'assistant_started', session_id:'browser', stream_id:'stream-one'});
owner.message({type:'assistant_retry_wait', session_id:'browser',
  stream_id:'stream-one', retry_after_seconds:60});
const notice = document.querySelector('#service-notice');
assert.equal(notice.hidden, false);
if (terminalState === 'cancelled') await document.querySelector('#cancel').onclick();
owner.message({type:'assistant_terminal', session_id:'browser', stream_id:'stream-one',
  state:terminalState, error:terminalState === 'failed' ? 'HTTPStatusError' : null});
assert.equal(notice.hidden, true);
owner.message({type:'assistant_retry_wait', session_id:'browser',
  stream_id:'stream-one', retry_after_seconds:1});
assert.equal(notice.hidden, true);
assert.equal(targetCalls().length, terminalState === 'cancelled' ? 1 : 0);
if (terminalState === 'cancelled')
  assert.equal(targetCalls()[0].url, '/v1/turns/turn-one/cancel');
assert.equal(targetCalls().filter(call => call.url.includes('/conversations/')).length, 0);
"""
    )
