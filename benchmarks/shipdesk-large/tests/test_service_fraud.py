from shipdesk.services.fraud_service import action_for, risk_score


def test_score_components():
    assert risk_score(5000, False, False) == 5
    assert risk_score(5000, True, True) == 60
    assert risk_score(10**9, True, True) == 95


def test_actions():
    assert action_for(1000, False, False) == "accept"
    assert action_for(15000, True, False) == "review"
    assert action_for(15000, True, True) == "hold"
    assert action_for(10**9, True, True) == "block"
