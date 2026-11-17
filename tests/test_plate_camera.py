from sigma_vial.domain.scenario import Access
from sigma_vial.domain.simulation import Simulation
from sigma_vial.presentation.plate_camera import rear_camera


def test_rear_plate_is_inside_image_and_follows_motion(qapp):
    sim = Simulation()
    sim.add_vehicle(Access.NORTH)
    vehicle = sim.vehicles[0]
    near = rear_camera(vehicle, 0)
    vehicle.position = 230
    far = rear_camera(vehicle, 1)
    assert near.track == far.track
    assert far.timestamp == 1
    assert far.image.rect().contains(far.plate_rect.toRect())
    assert far.crop().width() >= 200 and far.crop().height() >= 45
    assert near.plate_rect != far.plate_rect
    assert near.image != far.image
    assert "recorte por geometría" in far.provenance
    empty = rear_camera(None, 2)
    assert empty.track is None and empty.crop().isNull()
