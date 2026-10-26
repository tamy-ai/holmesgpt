from tamy.code.budget import Budget


def test_the_calls_of_one_conversation_stop_at_the_limit() -> None:
    budget = Budget(limit=3, window_s=600, clock=lambda: 0.0)

    assert [budget.spend("c1") for _ in range(5)] == [True, True, True, False, False]


def test_another_conversation_has_its_own_budget() -> None:
    budget = Budget(limit=1, window_s=600, clock=lambda: 0.0)

    assert budget.spend("c1") and not budget.spend("c1")
    assert budget.spend("c2")


def test_the_budget_comes_back_after_the_window() -> None:
    now = [0.0]
    budget = Budget(limit=1, window_s=600, clock=lambda: now[0])

    assert budget.spend("c1") and not budget.spend("c1")
    now[0] = 601.0
    assert budget.spend("c1")
