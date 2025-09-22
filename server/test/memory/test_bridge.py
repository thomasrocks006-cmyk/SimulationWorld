from datetime import date

from server.src.memory.config import load_memory_config
from server.src.memory.integration import MemoryBridge
from sim.world.state import WorldState


def test_memory_bridge_runs(memory_env):
    config = load_memory_config(memory_env)
    bridge = MemoryBridge.from_config(config)
    world_state = WorldState.from_files(seed=1337)
    day = date(2025, 9, 21)

    bridge.on_day_complete(day, world_state)

    latest_security_state = bridge.store.get_latest_entity_state(bridge.security_entity_id)
    assert latest_security_state is not None
    assert latest_security_state.state
