"""Exercise real Windows account controls using temporary data and no game input."""
import json
import os
from pathlib import Path
import sys
import tempfile


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    with tempfile.TemporaryDirectory(prefix='krampuslauf-account-check-') as temporary:
        os.environ['LOCALAPPDATA'] = temporary
        import Krampuslauf as gui
        gui.game_windows = lambda: []
        gui.Application.EnableVisualStyles()
        gui.Application.SetCompatibleTextRenderingDefault(False)
        window = gui.MainWindow()
        try:
            assert len(window.account_radios) == 15
            assert window.account_field.MaxLength == 16
            for slot, radio in window.account_radios.items():
                radio.Checked = True
                gui.Application.DoEvents()
                assert window.selected_account_slot == slot
                assert sum(bool(item.Checked) for item in window.account_radios.values()) == 1
            window.account_radios['account2'].Checked = True
            gui.Application.DoEvents()
            assert window.selected_account_slot == 'account2'
            account_id = window.active_profile_key
            window.account_field.Text = 'Overnight'
            window.shard_checks.SetItemChecked(0, False)
            window.slots_field.Text = 'Atlantic: 2,4'
            window.save_slot_rules()
            window.seed_capacity_pick.SelectedIndex = 0
            window.reserve_slot_checkbox.Checked = True
            window.seed_route_delay.Value = gui.Decimal.Parse('17')
            window.save_account_profile()
            assert window.active_profile_key == account_id
            assert window.account_radios['account2'].Text == 'Overnight'
            cycle = window.cfg['gift_cycle_id']
            excluded = list(window.cfg['excluded'])
            window.account_radios['main'].Checked = True
            gui.Application.DoEvents()
            assert window.cfg['gift_cycle_id'] != cycle
            assert gui.net_integer(window.seed_route_delay.Value) == 5
            window.seed_route_delay.Value = gui.Decimal.Parse('9')
            window.select_no_shards()
            assert window.cfg['excluded'] == window.cfg['shards']
            window.account_radios['account2'].Checked = True
            gui.Application.DoEvents()
            assert window.cfg['excluded'] == excluded
            assert window.cfg['skip_slots'] == {'Atlantic': [2,4]}
            assert window.cfg['account_cap'] == 5 and window.cfg['reserve_transfer_slot']
            assert window.cfg['seed_route_delay_seconds'] == 17
            assert gui.net_integer(window.seed_route_delay.Value) == 17
            assert window.cfg['gift_cycle_id'] == cycle
            assert window.account_field.Text == 'Overnight'
            window.account_radios['account15'].Checked = True
            window.account_field.Text = 'Account Fifteen!'
            window.save_account_profile()
            fifteenth_id = window.active_profile_key
            fifteenth_cycle = window.cfg['gift_cycle_id']
            assert fifteenth_id != account_id and fifteenth_cycle != cycle
            window.account_radios['account2'].Checked = True
            window.save_settings()
        finally:
            window.ui_timer.Stop()
            window.activity_window.Dispose()
            window.Dispose()
        reopened = gui.MainWindow()
        try:
            assert reopened.selected_account_slot == 'account2'
            assert reopened.active_profile_key == account_id
            assert reopened.account_field.Text == 'Overnight'
            assert reopened.cfg['excluded'] == excluded
            assert reopened.cfg['skip_slots'] == {'Atlantic': [2,4]}
            assert reopened.cfg['gift_cycle_id'] == cycle
            assert reopened.cfg['seed_route_delay_seconds'] == 17
            assert gui.net_integer(reopened.seed_route_delay.Value) == 17
            reopened.select_all_shards()
            assert reopened.cfg['excluded'] == []
            reopened.account_radios['main'].Checked = True
            gui.Application.DoEvents()
            assert reopened.cfg['excluded'] == reopened.cfg['shards']
            assert reopened.cfg['seed_route_delay_seconds'] == 9
            assert gui.net_integer(reopened.seed_route_delay.Value) == 9
            reopened.account_radios['account15'].Checked = True
            gui.Application.DoEvents()
            assert reopened.active_profile_key == fifteenth_id
            assert reopened.account_field.Text == 'Account Fifteen!'
            assert reopened.cfg['gift_cycle_id'] == fifteenth_cycle
            assert not reopened.cfg['excluded']
        finally:
            reopened.ui_timer.Stop()
            reopened.activity_window.Dispose()
            reopened.Dispose()
        print(json.dumps({'passed': True, 'checks': ['radio selection', 'stable nickname identity',
              'account exclusions and slot skips', 'capacity and reservation', 'separate gift cycles',
              'last account on relaunch', 'bulk shard selection', 'all 15 account radios',
              '16-character nickname limit', 'Account 15 persistence', 'per-account inn-route pause']}))


if __name__ == '__main__':
    main()
