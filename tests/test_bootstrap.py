from sim.world.state import WorldState


def test_world_loads_minimal():
    state = WorldState.from_files(seed=42)
    assert "thomas" in state.people
    assert "jordy" in state.people
    assert state.price_for.__call__
