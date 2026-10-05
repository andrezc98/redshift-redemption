import pytest

from rr.config import Target, require_sandbox


def test_require_sandbox_refuses_default_profile(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("AWS_PROFILE", "default")
    with pytest.raises(RuntimeError):
        require_sandbox()


def test_require_sandbox_accepts_sandbox_profile(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("AWS_PROFILE", "sura-sandbox")
    require_sandbox()


def test_require_sandbox_accepts_lab_profile(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("AWS_PROFILE", "morrislabs-poc")
    require_sandbox()


def test_target_parse_cluster_kwargs():
    t = Target.parse("cluster:rr-ra3")
    assert t.api_kwargs() == {"ClusterIdentifier": "rr-ra3", "Database": "tpcds", "DbUser": "awsuser"}


def test_target_parse_workgroup_kwargs():
    t = Target.parse("workgroup:rr-sls")
    assert t.api_kwargs() == {"WorkgroupName": "rr-sls", "Database": "tpcds"}


@pytest.mark.parametrize("bad", ["rr-ra3", "cluster:", "db:rr-ra3"])
def test_target_parse_rejects_bad_specs(bad):
    with pytest.raises(ValueError):
        Target.parse(bad)
