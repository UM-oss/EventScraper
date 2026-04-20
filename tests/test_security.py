"""
Varnostni testi — preveri da so P0 popravki na mestu.
"""

import os
import pytest
import yaml


class TestSecretKey:
    def test_no_hardcoded_secret(self):
        """Secret key ne sme biti hardcoded placeholder."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "auth.yaml"
        )
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = yaml.safe_load(f)
            secret = config.get("secret_key", "")
            assert "ZAMENJAJ" not in str(secret), "Secret key je še placeholder!"
            assert secret != "null", "Secret key ni generiran"
            assert len(str(secret)) >= 32, "Secret key je prekratek"


class TestDebugMode:
    def test_debug_not_hardcoded(self):
        """debug=True ne sme biti hardcoded."""
        app_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "app.py"
        )
        with open(app_path) as f:
            content = f.read()
        assert "debug=True" not in content, "debug=True je še hardcoded!"


class TestAuthBypass:
    def test_no_dev_mode_bypass(self):
        """Ko ni uporabnikov, ne sme biti avtomatski dostop."""
        from web.app import app
        app.config["TESTING"] = True

        with app.test_client() as client:
            # Tudi brez uporabnikov mora vrniti ustrezno napako, ne vsebine
            # (dejansko obnašanje je odvisno od AUTH_USERS ob startu)
            resp = client.get("/auth/status")
            # Ne sme biti 200 z "development" mode
            data = resp.get_json()
            if data and data.get("mode") == "development":
                pytest.fail("Dev mode bypass je še aktiven!")


class TestSessionConfig:
    def test_secure_cookie_settings(self):
        """Session cookies morajo imeti varne nastavitve."""
        from web.app import app
        assert app.config.get("SESSION_COOKIE_HTTPONLY") is True
        assert app.config.get("SESSION_COOKIE_SAMESITE") == "Lax"


class TestInputValidation:
    def test_status_validation_exists(self):
        """Validacija statusov mora biti implementirana."""
        from web.app import validate_status, VALID_STATUSES

        # Veljaven status ne sme vreči napake
        for status in VALID_STATUSES:
            result = validate_status(status)
            assert result == status

    def test_invalid_status_raises(self):
        """Neveljaven status mora vreči napako."""
        from web.app import app
        app.config["TESTING"] = True

        with app.test_request_context():
            from web.app import validate_status
            with pytest.raises(Exception):  # abort(400)
                validate_status("hacker_status")


class TestRateLimiting:
    def test_rate_limit_functions_exist(self):
        """Rate limiting funkcije morajo obstajati."""
        from web.app import _check_rate_limit, _record_attempt
        assert callable(_check_rate_limit)
        assert callable(_record_attempt)

    def test_rate_limit_blocks_after_threshold(self):
        """Po 5 poskusih mora blokirati."""
        from web.app import _check_rate_limit, _record_attempt, _login_attempts
        test_ip = "192.168.99.99"
        _login_attempts.pop(test_ip, None)

        for _ in range(5):
            assert not _check_rate_limit(test_ip)
            _record_attempt(test_ip)

        assert _check_rate_limit(test_ip)
        _login_attempts.pop(test_ip, None)  # Cleanup
