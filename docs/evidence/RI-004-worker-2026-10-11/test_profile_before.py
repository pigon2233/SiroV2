import pytest
from siro.adapters.skill_worker import WorkerSupervisor


def test_explicit_strict_profile_is_constructible():
    WorkerSupervisor(profile='python-stdlib-single')


def test_unknown_profile_is_rejected_as_value_error():
    with pytest.raises(ValueError):
        WorkerSupervisor(profile='unknown')
