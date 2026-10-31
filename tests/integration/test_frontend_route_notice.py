from __future__ import annotations

from test_frontend_control import run_control


def test_route_notice_stays_visible_beside_the_answer_and_clears_next_turn() -> None:
    run_control(
        """
document.querySelector('#service-notice').dataset = {};
const owner = await readyControl();
owner.message({type:'turn_started', turn_id:'turn-one', stream_id:'stream-one'});
owner.message({type:'assistant_started', session_id:'browser', stream_id:'stream-one'});
owner.message({type:'assistant_route_notice', session_id:'browser', stream_id:'stream-one',
  text:'Claude 額度已用完 改用 Groq 預計 2026-10-31 18:00 可以再用'});
const notice = document.querySelector('#service-notice');
assert.equal(notice.hidden, false);
assert.match(notice.textContent, /改用 Groq/);
assert.match(notice.textContent, /可以再用/);
owner.message({type:'assistant_delta', session_id:'browser', stream_id:'stream-one', text:'答案'});
assert.equal(notice.hidden, false);
assert.match(notice.textContent, /改用 Groq/);
owner.message({type:'assistant_started', session_id:'browser', stream_id:'stream-two'});
assert.equal(notice.hidden, true);
assert.equal(notice.textContent, '');
"""
    )
