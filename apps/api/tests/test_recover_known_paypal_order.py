import json
import os

import pytest

from scripts import recover_known_paypal_order as recovery


def test_recovery_merchant_mapping_comes_from_local_config_only():
    registry = recovery._trusted_recovery_registry({
        "PAYPAL_SANDBOX_MERCHANTS": {recovery.INTERNAL_MERCHANT_ID: "SANDBOX_TEST_ACCOUNT"},
    })

    assert registry.resolve(recovery.INTERNAL_MERCHANT_ID).paypal_merchant_id == "SANDBOX_TEST_ACCOUNT"


def test_recovery_loads_owner_only_local_configuration(tmp_path, monkeypatch):
    config_path = tmp_path / "sandbox.json"
    config = {"PAYPAL_SANDBOX_MERCHANTS": {recovery.INTERNAL_MERCHANT_ID: "SANDBOX_TEST_ACCOUNT"}}
    config_path.write_text(json.dumps(config), encoding="utf-8")
    os.chmod(config_path, 0o600)
    monkeypatch.setattr(recovery, "CONFIG_PATH", config_path)

    loaded = recovery._read_provider_config()

    assert recovery._trusted_recovery_registry(loaded).resolve(
        recovery.INTERNAL_MERCHANT_ID
    ).paypal_merchant_id == "SANDBOX_TEST_ACCOUNT"


def test_recovery_fails_safely_when_local_configuration_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "CONFIG_PATH", tmp_path / "missing.json")

    with pytest.raises(RuntimeError, match="Sandbox configuration is unavailable"):
        recovery._read_provider_config()


@pytest.mark.parametrize("config", [{}, {"PAYPAL_SANDBOX_MERCHANTS": {}}])
def test_recovery_fails_safely_when_required_merchant_mapping_is_missing(config):
    with pytest.raises(RuntimeError, match="Trusted Sandbox merchant mapping for recovery is unavailable"):
        recovery._trusted_recovery_registry(config)
