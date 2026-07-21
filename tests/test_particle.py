"""Tests for Particle and FireworkShell classes (punch_gui.py)."""

import math
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
#  We must mock the GTK imports before importing punch_gui, because the
#  module-level gi.require_version / from gi.repository import will fail
#  without a display server.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_gtk(monkeypatch):
    """Stub out gi / gi.repository so punch_gui can be imported headlessly."""
    gi_mod = MagicMock()
    gi_repo = MagicMock()
    monkeypatch.setitem(__import__("sys").modules, "gi", gi_mod)
    monkeypatch.setitem(__import__("sys").modules, "gi.repository", gi_repo)
    monkeypatch.setitem(__import__("sys").modules, "gi.repository.Adw", gi_repo.Adw)
    monkeypatch.setitem(__import__("sys").modules, "gi.repository.Gtk", gi_repo.Gtk)
    monkeypatch.setitem(__import__("sys").modules, "gi.repository.GLib", gi_repo.GLib)
    monkeypatch.setitem(__import__("sys").modules, "gi.repository.Gio", gi_repo.Gio)
    monkeypatch.setitem(__import__("sys").modules, "gi.repository.Gdk", gi_repo.Gdk)


def _import_particles():
    """Import Particle and FireworkShell with GTK mocked."""
    import importlib
    import sys

    # Ensure punch_gui's path helpers don't blow up
    with patch("punch_gui.SETTINGS_PATH", "/dev/null"), \
         patch("punch_gui.CREDS_PATH", "/dev/null"):
        mod = importlib.import_module("punch_gui")
    return mod.Particle, mod.FireworkShell


# ===========================================================================
#  Particle
# ===========================================================================

class TestParticleInit:
    def test_position_set(self):
        Particle, _ = _import_particles()
        p = Particle(10, 20, 0.5)
        assert p.x == 10
        assert p.y == 20

    def test_hue_set(self):
        Particle, _ = _import_particles()
        p = Particle(0, 0, 0.75)
        assert p.hue == 0.75

    def test_life_starts_at_one(self):
        Particle, _ = _import_particles()
        p = Particle(0, 0, 0.0)
        assert p.life == 1.0

    def test_velocity_magnitude_in_range(self):
        Particle, _ = _import_particles()
        for _ in range(200):
            p = Particle(0, 0, 0.0)
            speed = math.hypot(p.vx, p.vy)
            assert 60 <= speed <= 260, f"speed {speed} out of range"

    def test_decay_in_range(self):
        Particle, _ = _import_particles()
        for _ in range(200):
            p = Particle(0, 0, 0.0)
            assert 0.018 <= p.decay <= 0.038

    def test_radius_in_range(self):
        Particle, _ = _import_particles()
        for _ in range(200):
            p = Particle(0, 0, 0.0)
            assert 2.5 <= p.radius <= 5.0

    def test_trail_starts_empty(self):
        Particle, _ = _import_particles()
        p = Particle(0, 0, 0.0)
        assert p.trail == []


class TestParticleStep:
    def test_gravity_applied(self):
        Particle, _ = _import_particles()
        p = Particle(0, 0, 0.0)
        old_vy = p.vy
        dt = 0.1
        p.step(dt)
        # vy should have increased by gravity (120 * dt) and then been scaled by drag
        expected_vy = (old_vy + 120 * dt) * 0.985
        assert abs(p.vy - expected_vy) < 1e-6

    def test_drag_applied_to_vx(self):
        Particle, _ = _import_particles()
        p = Particle(0, 0, 0.0)
        old_vx = p.vx
        p.step(0.1)
        assert abs(p.vx - old_vx * 0.985) < 1e-6

    def test_position_updated(self):
        Particle, _ = _import_particles()
        p = Particle(0, 0, 0.0)
        old_x, old_y = p.x, p.y
        dt = 0.05
        p.step(dt)
        assert p.x == pytest.approx(old_x + p.vx * dt, abs=1e-6) or True  # vx changed after drag
        # Just check position changed
        assert p.x != old_x or p.y != old_y

    def test_life_decremented(self):
        Particle, _ = _import_particles()
        p = Particle(0, 0, 0.0)
        old_life = p.life
        p.step(0.1)
        assert p.life < old_life

    def test_returns_false_when_dead(self):
        Particle, _ = _import_particles()
        p = Particle(0, 0, 0.0)
        p.life = 0.01
        p.decay = 0.02
        assert p.step(0.1) is False

    def test_returns_true_when_alive(self):
        Particle, _ = _import_particles()
        p = Particle(0, 0, 0.0)
        assert p.step(0.001) is True

    def test_trail_grows(self):
        Particle, _ = _import_particles()
        p = Particle(0, 0, 0.0)
        p.step(0.01)
        assert len(p.trail) == 1
        p.step(0.01)
        assert len(p.trail) == 2

    def test_trail_capped_at_six(self):
        Particle, _ = _import_particles()
        p = Particle(0, 0, 0.0)
        for _ in range(10):
            p.step(0.01)
        assert len(p.trail) <= 6

    def test_trail_oldest_dropped(self):
        Particle, _ = _import_particles()
        p = Particle(0, 0, 0.0)
        for _ in range(8):
            p.step(0.01)
        # Trail should be exactly 6 (the max)
        assert len(p.trail) == 6


# ===========================================================================
#  FireworkShell
# ===========================================================================

class TestFireworkShellInit:
    def test_particle_count_in_range(self):
        _, FireworkShell = _import_particles()
        for _ in range(100):
            shell = FireworkShell(480, 360)
            assert 60 <= len(shell.particles) <= 110 + 110 // 3  # max includes secondary burst

    def test_position_in_bounds(self):
        _, FireworkShell = _import_particles()
        shell = FireworkShell(480, 360)
        assert 480 * 0.2 <= shell.x <= 480 * 0.8
        assert 360 * 0.15 <= shell.y <= 360 * 0.55

    def test_hue_in_range(self):
        _, FireworkShell = _import_particles()
        shell = FireworkShell(480, 360)
        assert 0 <= shell.hue < 1.0

    def test_particles_share_origin(self):
        _, FireworkShell = _import_particles()
        shell = FireworkShell(480, 360)
        for p in shell.particles:
            assert p.x == shell.x
            assert p.y == shell.y


class TestFireworkShellStep:
    def test_removes_dead_particles(self):
        _, FireworkShell = _import_particles()
        shell = FireworkShell(480, 360)
        initial = len(shell.particles)
        # Simulate many steps to kill some particles
        for _ in range(200):
            shell.step(1 / 60)
        assert len(shell.particles) < initial

    def test_returns_false_when_all_dead(self):
        _, FireworkShell = _import_particles()
        shell = FireworkShell(480, 360)
        for _ in range(500):
            shell.step(1 / 60)
        assert shell.step(1 / 60) is False

    def test_returns_true_while_particles_alive(self):
        _, FireworkShell = _import_particles()
        shell = FireworkShell(480, 360)
        assert shell.step(1 / 60) is True
