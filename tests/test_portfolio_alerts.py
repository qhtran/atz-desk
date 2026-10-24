from backend.portfolio_alerts import position_alert


def test_position_alert_bands_and_zones():
    assert position_alert(None, None) == "Chưa có giá"
    assert position_alert(100.0, 100.0) == "—"
    assert position_alert(100.0, 92.0) == "−8%"
    assert position_alert(100.0, 101.0, support=100.0) == "Gần hỗ trợ"
    assert position_alert(100.0, 95.0, support=100.0) == "Dưới hỗ trợ · −5%"
    assert position_alert(100.0, 121.0, resistance=120.0) == "Gần kháng cự · +10%"
    assert "Gần hỗ trợ" in position_alert(10.0, 10.1, support=10.0)
    assert position_alert(10.0, 10.6) == "+5%"
    assert position_alert(10.0, 9.1) == "−8%"
    assert position_alert(10.0, 10.1) == "—"
