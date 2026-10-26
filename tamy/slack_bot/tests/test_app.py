from tamy.slack_bot.app import SUPPORT_ACTION, decision_handler, resolved_handler, support_offer_blocks, thread_of_click


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


def test_the_thread_of_a_click_comes_from_the_message_that_holds_the_button() -> None:
    assert thread_of_click({"message": {"thread_ts": "1.0", "ts": "2.0"}}) == "1.0"
    assert thread_of_click({"container": {"thread_ts": "3.0"}}) == "3.0"
    assert thread_of_click({"message": {"ts": "2.0"}}) is None


def test_the_answer_to_a_click_stays_in_the_thread_and_is_not_dropped_in_the_channel() -> None:
    bot = _Bot()
    replies: list[dict] = []

    decision_handler(bot, approved=True)(
        lambda: None,
        {"user": {"id": "U1"}, "message": {"thread_ts": "9.0"}},
        {"value": "req-1"},
        lambda **kw: replies.append(kw),
    )

    assert replies[0]["thread_ts"] == "9.0"


class _ResolveJira:
    def issue_labels(self, key: str) -> list[str]:
        return ["origem-slack", "slack-C1-9.0"]

    def add_comment(self, key: str, body: dict) -> None: ...

    def add_label(self, key: str, label: str) -> None: ...

    def reopen(self, key: str) -> None: ...


class _Slack:
    def __init__(self, root_user: str) -> None:
        self.root_user, self.posts = root_user, []

    def replies(self, channel: str, thread_ts: str) -> list[dict]:
        return [{"user": self.root_user}]

    def display_name(self, user: str) -> str:
        return "Matheus"

    def post(self, **kwargs) -> str:
        self.posts.append(kwargs)
        return "1.1"


def test_the_thanks_for_resolveu_is_a_public_message_in_the_thread() -> None:
    slack = _Slack("U1")
    replies: list[dict] = []

    resolved_handler(_ResolveJira(), slack, resolved=True)(
        lambda: None,
        {"user": {"id": "U1"}, "channel": {"id": "C1"}, "message": {"thread_ts": "9.0"}},
        {"value": "TA-5"},
        lambda **kw: replies.append(kw),
    )

    assert slack.posts and slack.posts[0]["thread_ts"] == "9.0" and slack.posts[0]["channel"] == "C1"
    assert replies == []


def test_a_stranger_gets_a_private_answer_inside_the_thread() -> None:
    slack = _Slack("U1")
    replies: list[dict] = []

    resolved_handler(_ResolveJira(), slack, resolved=True)(
        lambda: None,
        {"user": {"id": "U2"}, "message": {"thread_ts": "9.0"}},
        {"value": "TA-5"},
        lambda **kw: replies.append(kw),
    )

    assert slack.posts == [] and replies[0]["thread_ts"] == "9.0" and replies[0]["response_type"] == "ephemeral"
