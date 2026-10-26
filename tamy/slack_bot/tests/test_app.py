from tamy.slack_bot.app import SUPPORT_ACTION, decision_handler, support_offer_blocks


def test_support_offer_has_one_button_that_carries_the_thread():
    blocks = support_offer_blocks("C123", "1700000000.000100")
    button = blocks[0]["elements"][0]
    assert button["action_id"] == SUPPORT_ACTION
    assert button["value"] == "C123|1700000000.000100"


def test_support_offer_value_splits_back_into_channel_and_ts():
    channel, ts = support_offer_blocks("C123", "17.1")[0]["elements"][0]["value"].split("|", 1)
    assert (channel, ts) == ("C123", "17.1")


class _Bot:
    def __init__(self) -> None:
        self.seen: list[tuple[str, str, bool]] = []

    def decide(self, *, request_id: str, user: str, approved: bool) -> str:
        self.seen.append((request_id, user, approved))
        return "ok"


def _click(handler) -> list[dict]:
    replies: list[dict] = []
    handler(lambda: None, {"user": {"id": "U1"}}, {"value": "req-1"}, lambda **kw: replies.append(kw))
    return replies


def test_the_approve_button_approves_and_the_deny_button_denies():
    bot = _Bot()
    _click(decision_handler(bot, approved=True))
    _click(decision_handler(bot, approved=False))
    assert bot.seen == [("req-1", "U1", True), ("req-1", "U1", False)]
