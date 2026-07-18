import pytest
from unittest.mock import MagicMock
from app.database import with_db_retry, is_transient_db_error
from sqlalchemy.exc import OperationalError

def test_transient_db_error_detection():
    # Test that connection reset error is detected
    assert is_transient_db_error(ConnectionResetError("Connection reset by peer")) is True
    
    # Test that SQLAlchemy OperationalError is detected
    op_err = OperationalError("statement", {}, Exception("SSL connection closed"))
    assert is_transient_db_error(op_err) is True
    
    # Test that unrelated exceptions are not detected
    assert is_transient_db_error(ValueError("Invalid argument")) is False

def test_with_db_retry_success():
    calls = 0

    @with_db_retry
    def db_operation():
        nonlocal calls
        calls += 1
        return "success"

    result = db_operation()
    assert result == "success"
    assert calls == 1

def test_with_db_retry_transient_recovery():
    calls = 0

    @with_db_retry
    def db_operation():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise OperationalError("statement", {}, Exception("SSL connection closed"))
        return "recovered"

    result = db_operation()
    assert result == "recovered"
    assert calls == 3

def test_with_db_retry_fatal_failure():
    calls = 0

    @with_db_retry
    def db_operation():
        nonlocal calls
        calls += 1
        raise ValueError("Non-transient error")

    with pytest.raises(ValueError):
        db_operation()
    
    assert calls == 1  # Should not retry non-transient error
