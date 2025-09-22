from server.src.memory.ids import entity_id, person_id, wallet_id


def test_entity_id_deterministic():
    first = entity_id("person", "Thomas Francis")
    second = entity_id("person", "Thomas Francis")
    assert first == second


def test_entity_id_qualifiers_change_hash():
    base = entity_id("wallet", "Primary", qualifiers=["user-a"])
    other = entity_id("wallet", "Primary", qualifiers=["user-b"])
    assert base != other


def test_person_and_wallet_helpers():
    person = person_id("Jordan Shreeve")
    wallet = wallet_id("jordan_shreeve", "primary")
    assert person.startswith("person:")
    assert wallet.startswith("wallet:")
