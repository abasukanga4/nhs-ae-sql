from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def test_app_default_trust_and_empty_comparison():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert app.metric[0].value == "1,451,010"
    selected_provider = app.sidebar.selectbox[0].options[1]
    app.sidebar.selectbox[0].select(selected_provider).run()
    assert not app.exception
    assert app.metric[0].value != "1,451,010"
    app.sidebar.radio[0].set_value("All A&E types").run()
    assert not app.exception
    app.number_input[0].set_value(500000).run()
    assert not app.exception
    assert any("No providers meet" in x.value for x in app.info)
