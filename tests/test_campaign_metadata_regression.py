"""Session counters must agree across the modular state and legacy mirror."""

import json

from src.storage.campaign_manager import CampaignManager


def test_saving_session_four_updates_the_mirrored_session_count(tmp_path):
    manager = CampaignManager(campaigns_dir=str(tmp_path))
    state = {
        "campaign_name": "Candlekeep 2.0",
        "sessions_count": 3,
        "last_session": 4,
        "sessions": [{"session_number": n} for n in (1, 2, 3, 4)],
    }

    mirror_path = manager.save_campaign(state)

    assert json.loads(mirror_path.read_text(encoding="utf-8"))["sessions_count"] == 4
    assert manager.load_modular("Candlekeep 2.0")["sessions_count"] == 4


def test_loading_modular_sessions_recomputes_a_stale_counter(tmp_path):
    campaign_dir = tmp_path / "candlekeep_2.0"
    sessions_dir = campaign_dir / "sessions"
    sessions_dir.mkdir(parents=True)
    entities_dir = campaign_dir / "entities"
    entities_dir.mkdir()
    (entities_dir / "npcs.json").write_text("[]", encoding="utf-8")
    (campaign_dir / "campaign.json").write_text(
        json.dumps({"campaign_name": "Candlekeep 2.0", "storage_version": 2,
                    "last_session": 3, "sessions_count": 3}), encoding="utf-8"
    )
    for number in (1, 2, 3, 4):
        (sessions_dir / f"session_{number}.json").write_text(
            json.dumps({"session_number": number}), encoding="utf-8"
        )

    state = CampaignManager(campaigns_dir=str(tmp_path)).load_modular("Candlekeep 2.0")

    assert state["last_session"] == 4
    assert state["sessions_count"] == 4
