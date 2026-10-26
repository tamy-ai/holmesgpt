from tamy.slack_bot.app import SUPPORT_ACTION, support_offer_blocks


def test_support_offer_has_one_button_that_carries_the_thread():
    blocks = support_offer_blocks("C123", "1700000000.000100")
    button = blocks[0]["elements"][0]
    assert button["action_id"] == SUPPORT_ACTION
    assert button["value"] == "C123|1700000000.000100"


def test_support_offer_value_splits_back_into_channel_and_ts():
    channel, ts = support_offer_blocks("C123", "17.1")[0]["elements"][0]["value"].split("|", 1)
    assert (channel, ts) == ("C123", "17.1")
