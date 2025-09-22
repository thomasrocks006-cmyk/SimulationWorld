from __future__ import annotations

from contextlib import redirect_stdout
from datetime import date, timedelta
from io import StringIO

from sim.output.render import DailyRenderer
from sim.world.choices import pick_choices
from sim.world.state import WorldState


def _prep_renderer(
    tmp_path,
    *,
    view="narrative",
    verbosity="normal",
    interactive=False,
    story_length="adaptive",
    story_tone="neutral",
):
    renderer = DailyRenderer(
        view=view,
        verbosity=verbosity,
        interactive=interactive,
        seed=1337,
        start=date(2025, 9, 20),
        story_length=story_length,
        story_tone=story_tone,
    )
    renderer.logs_dir = tmp_path / "logs"
    renderer.logs_dir.mkdir(parents=True, exist_ok=True)
    renderer.saves_dir = tmp_path / "saves"
    renderer.saves_dir.mkdir(parents=True, exist_ok=True)
    renderer.output_dir = tmp_path / "out"
    renderer.output_dir.mkdir(parents=True, exist_ok=True)
    renderer.finance_csv_path = renderer.output_dir / f"finance_{renderer.run_id}.csv"
    renderer.social_csv_path = renderer.output_dir / f"social_{renderer.run_id}.csv"
    renderer._ensure_csv_headers()
    return renderer


def test_renderer_narrative_sections(tmp_path):
    renderer = _prep_renderer(tmp_path, story_tone="journalistic")
    day = date(2025, 9, 21)
    renderer.start_day(
        day,
        index=2,
        location="South Yarra, Melbourne",
        moods={"Thomas": 58, "Jordy": 64},
        calendar_week=1,
        rng_seed=1337,
        clock_step="day",
    )
    renderer.add_story_sentence("Story line one.")
    renderer.add_highlight("Finance moves logged.")
    renderer.add_finance_line(
        "Sample finance line",
        holder="Thomas Francis",
        value=1000.0,
        price=0.05,
        token_quantity=2000000,
        cash=100.0,
    )
    buf = StringIO()
    with redirect_stdout(buf):
        renderer.present_day(choices=None)
    output = buf.getvalue()
    assert "=== 2025-09-21" in output
    assert "[STORY]" in output
    assert "Report: Story line one." in output
    assert "[HIGHLIGHTS]" in output
    assert "Finance moves logged." in output
    assert "[FINANCE SNAPSHOT]" in output
    renderer.finalise_day()


def test_choices_trim_origin(tmp_path):
    state = WorldState.from_files(seed=42)
    symbol = state.coin_symbol
    state.people["thomas"].add_tokens(symbol, 2_000_000)
    start_cash = state.people["thomas"].holdings.cash_usd

    choices = pick_choices(state, "2025-09-22", k=3)
    ids = {choice.id for choice in choices}
    assert "trim_origin" in ids

    for choice in choices:
        if choice.id == "trim_origin":
            logs = choice.effect(state, "2025-09-22")
            assert any("Trims" in line or "trim" in line for line in logs)
            break

    updated_qty = state.people["thomas"].token_quantity(symbol)
    assert updated_qty < 2_000_000
    assert state.people["thomas"].holdings.cash_usd > start_cash


def test_weekly_rollup_emits(tmp_path):
    renderer = _prep_renderer(tmp_path, interactive=False)
    base_day = date(2025, 9, 15)
    for offset in range(6):
        day = base_day + timedelta(days=offset)
        renderer.start_day(
            day,
            index=offset + 1,
            location="South Yarra, Melbourne",
            moods={"Thomas": 60},
            calendar_week=1,
            rng_seed=1337,
            clock_step="day",
        )
        renderer.add_highlight(f"Finance placeholder day {offset}.")
        renderer.add_finance_line(
            f"Finance line {offset}",
            holder="Thomas Francis",
            value=100000 + offset,
            price=0.05,
            token_quantity=2_000_000,
            cash=100.0,
        )
        with redirect_stdout(StringIO()):
            renderer.present_day(choices=None)
        renderer.finalise_day()

    sunday = base_day + timedelta(days=6)
    renderer.start_day(
        sunday,
        index=7,
        location="South Yarra, Melbourne",
        moods={"Thomas": 60},
        calendar_week=1,
        rng_seed=1337,
        clock_step="day",
    )
    renderer.add_highlight("Finance placeholder day 6.")
    renderer.add_finance_line(
        "Finance line 6",
        holder="Thomas Francis",
        value=100006,
        price=0.05,
        token_quantity=2_000_000,
        cash=100.0,
    )
    buf = StringIO()
    with redirect_stdout(buf):
        renderer.present_day(choices=None)
        renderer.maybe_render_weekly_summary()
    assert "[WEEKLY ROLLUP]" in buf.getvalue()
    renderer.finalise_day()


def test_story_length_short_caps_output(tmp_path):
    renderer = _prep_renderer(tmp_path, story_length="short", story_tone="neutral")
    renderer.start_day(
        date(2025, 9, 22),
        index=3,
        location="South Yarra, Melbourne",
        moods={"Thomas": 60},
        calendar_week=1,
        rng_seed=1337,
        clock_step="day",
    )
    renderer.add_story_sentence("Thomas drafts a late-night email to the team.")
    renderer.add_story_sentence("Jordy locks in supplier quotes before midnight.")
    with redirect_stdout(StringIO()):
        renderer.present_day(choices=None)
    story_section = renderer.sections_payload.get("story", [])
    assert len(story_section) == 1
    renderer.finalise_day()


def test_story_tone_drama_appends_clause(tmp_path):
    renderer = _prep_renderer(tmp_path, story_tone="drama")
    renderer.start_day(
        date(2025, 9, 23),
        index=4,
        location="South Yarra, Melbourne",
        moods={"Thomas": 60},
        calendar_week=1,
        rng_seed=1337,
        clock_step="day",
    )
    renderer.add_story_sentence("Thomas lines up his pitch deck against the ORIGIN narrative arc.")
    with redirect_stdout(StringIO()):
        renderer.present_day(choices=None)
    story_lines = renderer.sections_payload.get("story", [])
    assert any("The pressure is palpable." in line for line in story_lines)
    renderer.finalise_day()
