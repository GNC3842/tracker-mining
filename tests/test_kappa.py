from tm.feasibility.kappa import cohen_kappa


def test_perfect_agreement():
    k, observed = cohen_kappa(["tracking", "non_tracking"], ["tracking", "non_tracking"])
    assert k == 1.0 and observed == 1.0


def test_hand_computed_example():
    # accord observé = 3/4 ; accord attendu = (2*1 + 2*3)/16 = 1/2 ; kappa = 0.5
    a = ["t", "t", "n", "n"]
    b = ["t", "n", "n", "n"]
    k, observed = cohen_kappa(a, b)
    assert observed == 0.75 and k == 0.5
