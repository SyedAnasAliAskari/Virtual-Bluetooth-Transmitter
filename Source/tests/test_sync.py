from dualsync.core.sync_engine import DriftController


def test_controller_bounds_and_health():
    controller = DriftController(1000)
    for _ in range(100):
        ppm = controller.update(100_000)
    assert ppm == 250
    assert controller.health == "High"
