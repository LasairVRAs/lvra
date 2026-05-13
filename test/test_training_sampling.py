import pandas as pd
import pytest

from lvra.training import sampling


def _predictions():
    return pd.DataFrame(
        {
            "diaSourceId": [f"s{i}" for i in range(10)],
            "pred": [0.99, 0.95, 0.91, 0.75, 0.55, 0.50, 0.45, 0.20, 0.08, 0.03],
        }
    )


def test_random_sampling_returns_requested_number_of_ids():
    df = _predictions()

    sampled = sampling.random_sampling(df, score_column="pred", N=len(df))

    assert set(sampled) == set(df["diaSourceId"])
    assert len(sampled) == len(df)


def test_random_sampling_raises_when_request_exceeds_available_rows():
    with pytest.raises(ValueError):
        sampling.random_sampling(_predictions(), score_column="pred", N=99)


def test_nsr_sampling_returns_top_ids_plus_mid_bracket_ids():
    sampled = sampling.nsr_sampling(
        _predictions(),
        score_column="pred",
        Ntop=2,
        Nmid=3,
        mid_bracket=(0.4, 0.6),
    )

    assert sampled[:2] == ["s0", "s1"]
    assert set(sampled[2:]) == {"s4", "s5", "s6"}


def test_nsr_sampling_falls_back_when_mid_bracket_is_too_small(capsys):
    sampled = sampling.nsr_sampling(
        _predictions(),
        score_column="pred",
        Ntop=2,
        Nmid=8,
        mid_bracket=(0.49, 0.51),
    )

    assert sampled[:2] == ["s0", "s1"]
    assert set(sampled[2:]) == {"s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9"}
    assert "Not enough samples in mid_bracket" in capsys.readouterr().out


def test_nsr_sampling2_returns_high_mid_and_low_bracket_ids():
    sampled = sampling.nsr_sampling2(
        _predictions(),
        score_column="pred",
        Nhi=3,
        Nmid=3,
        Nlow=2,
        hi_bracket=(0.9, 1.0),
        mid_bracket=(0.4, 0.6),
        low_bracket=(0.0, 0.1),
    )

    assert set(sampled[:3]) == {"s0", "s1", "s2"}
    assert set(sampled[3:6]) == {"s4", "s5", "s6"}
    assert set(sampled[6:]) == {"s8", "s9"}


def test_nsr_sampling2_falls_back_for_sparse_brackets(capsys):
    sampled = sampling.nsr_sampling2(
        _predictions(),
        score_column="pred",
        Nhi=3,
        Nmid=5,
        Nlow=2,
        hi_bracket=(0.995, 1.0),
        mid_bracket=(0.495, 0.505),
        low_bracket=(0.001, 0.002),
    )

    assert sampled[:3] == ["s0", "s1", "s2"]
    assert set(sampled[3:8]) == {"s3", "s4", "s5", "s6", "s7"}
    assert sampled[8:] == ["s8", "s9"]
    output = capsys.readouterr().out
    assert "Not enough samples in hi_bracket" in output
    assert "Not enough samples in mid_bracket" in output
    assert "Not enough samples in low_bracket" in output


def test_sampling_requires_expected_columns():
    with pytest.raises(AttributeError):
        sampling.nsr_sampling(pd.DataFrame({"pred": [0.1]}), Ntop=1, Nmid=0)

    with pytest.raises(AttributeError):
        sampling.random_sampling(pd.DataFrame({"pred": [0.1]}), score_column="pred", N=1)
