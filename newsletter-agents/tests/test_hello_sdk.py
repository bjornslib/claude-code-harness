from hello_sdk import hello

def test_hello_returns_expected_string():
    assert hello() == 'SDK pipeline works!'
