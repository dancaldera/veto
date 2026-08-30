from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_paper_loop_scripts_are_fake_money_only():
    daily = (ROOT / "scripts" / "daily_paper_run.sh").read_text()
    install = (ROOT / "scripts" / "install-timers.sh").read_text()
    service = (ROOT / "scripts" / "systemd" / "veto-paperscan.service").read_text()
    assert "paper_only=true" in daily
    assert "DRY_RUN" in daily
    assert "PAPER" in install
    assert "PAPER" in service
    assert (ROOT / "scripts" / "execute_stock_intents.sh").exists()
    assert (ROOT / "scripts" / "intraday_stop_run.sh").exists()
    assert (ROOT / "scripts" / "systemd" / "veto-stopmonitor.timer").exists()
