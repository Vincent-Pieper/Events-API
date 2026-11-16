from models import User


def test_password_hashing():
    password = "SecureTestPassword123!"

    user = User(username="unit_test_user")
    user.set_password(password)

    assert user.password_hash
    assert user.password_hash != password

    assert user.check_password(password) is True
    assert user.check_password("WrongPassword123!") is False
