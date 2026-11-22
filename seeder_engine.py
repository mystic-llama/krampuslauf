"""Character creation integrated into the verified Classic Client + RE bridge.

Explicit opt-in only. Calibration and name-input testing MUST precede irreversible
Create/Enter World. Pending creations are durable; ambiguous submissions are
never repeated automatically. No deletion or replacement of characters.
"""
from __future__ import annotations

import hashlib
import re
import time
import shutil

import pyautogui as pg

from bridge_protocol import BridgeSession, STATUS, read_json
from cycler_engine import (GameWorker, APP_DIR, SEED_PROGRESS_FILE, SEED_MARKERS,
                           SEED_POINTS, load_json, atomic_json, PVP_SHARDS,
                           EmptySlot, Cancelled)


import appearance
from seeder_rules import generated_name, name_hash, account_token, shard_abbreviation
from fantasy_name_generator import (FantasyNameGenerator, STYLES,
                                    is_valid_name as is_valid_fantasy_name)
from seed_recovery import (current_seed_candidates, pending_seed_candidates,
                           candidate_for_status, finish_seed_record,
                           promote_pending_after_world_proof)


class SeedNotReady(RuntimeError):
    pass


def diagnose_world_bridge(session, created_at, expected_shard):
    """Why a world heartbeat is not yet accepted; no credentials are logged.

    A diagnostic only. Never use its result to authorize creation, routing,
    or logout. The normal BridgeSession verification remains authoritative.
    """
    data = read_json(STATUS)
    if not data:
        return ('No current RE bridge status received. Verify that krampuslauf_bridge.py '
                'AutoStarted in the active default profile and is still running.')
    if data.get('protocol') != 1:
        return 'Bridge status has an unexpected protocol version.'
    if data.get('run_id') != session.run_id:
        return 'Bridge heartbeat belongs to an earlier/different Krampuslauf run.'
    if not data.get('connected') or not data.get('instance_id'):
        return 'Bridge heartbeat exists but lacks connected/instance confirmation.'
    now = time.time()
    try:
        seen_at = float(data.get('seen_at', 0))
        started_at = float(data.get('started_at', 0))
    except (TypeError, ValueError):
        return 'Bridge heartbeat timestamps are invalid.'
    if not (now - 3.5 <= seen_at <= now + 1):
        return 'Bridge heartbeat is stale; RE script may have stopped or frozen.'
    if started_at < created_at - 1.5:
        return ('Bridge instance started before final creation submit; '
                'waiting for a new AutoStart instance (possible old character/profile).')
    actual_shard = str(data.get('shard') or '').strip()
    if not actual_shard:
        return 'Bridge is connected but has not reported a shard.'
    if actual_shard.casefold() != expected_shard.strip().casefold():
        return 'Bridge reports a different shard, not the expected creation shard.'
    if not data.get('name_sha256'):
        return 'Bridge is connected but cannot report a character fingerprint yet.'
    return 'Bridge heartbeat present but not yet accepted by session validator.'


class SeederOperations:
    """Mixin for GameWorker. No extra keyboard injection unless opt-in verified."""

    def snapshot_seed_progress(self, reason):
        """Keep immutable copy before manual recovery updates."""
        import uuid
        if not SEED_PROGRESS_FILE.exists():
            raise RuntimeError('Seeder progress file is missing; cannot safely snapshot.')
        snapshot = SEED_PROGRESS_FILE.with_name(
            'seeder_progress.before-{}-{}.json'.format(reason, uuid.uuid4().hex[:12]))
        shutil.copy2(str(SEED_PROGRESS_FILE), str(snapshot))
        return snapshot

    def seed_init(self, nickname):
        self.seed_nickname=nickname
        self.seed_account_id=self.cfg.get('account_history_id') or account_token(nickname)
        self.fantasy_name_generator = None
        from cycle_state import cycle_key, adopt_legacy_creations
        from uuid import uuid4
        from shutil import copy2
        cycle = cycle_key(self.cfg, getattr(self, 'progress_id', ''))
        state = load_json(SEED_PROGRESS_FILE, {})
        if adopt_legacy_creations(state, self.seed_account_id, cycle):
            snapshot = SEED_PROGRESS_FILE.with_name('seeder_progress.before-cycle-tags-' + uuid4().hex[:12] + '.json')
            copy2(str(SEED_PROGRESS_FILE), str(snapshot))
            atomic_json(SEED_PROGRESS_FILE, state)

    def retire_interrupted_routes(self):
        """A fresh logged-out run keeps confirmed characters but never replays their old routes."""
        from shard_policy import is_supported, matches_shard_group
        state = load_json(SEED_PROGRESS_FILE, {})
        group = self.cfg.get('shard_group', 'all')
        changed = False
        for shard, record in state.get('profiles', {}).get(self.seed_account_id, {}).items():
            if not is_supported(shard) or not matches_shard_group(shard, group):
                continue
            interrupted = (set(record.get('created', [])) - set(record.get('completed', []))
                           - set(record.get('abandoned_routes', [])))
            if interrupted:
                record['abandoned_routes'] = sorted(set(record.get('abandoned_routes', [])) | interrupted)
                changed = True
                self.say('Keeping {} previously created character(s) on {}; their interrupted routes will not be replayed.'.format(len(interrupted), shard))
        if changed:
            self.snapshot_seed_progress('interrupted-routes')
            atomic_json(SEED_PROGRESS_FILE, state)

    def _fantasy_generator(self):
        """Single persistent history across all local Seeder profiles.

        Do not reset used names on a restart or change of account nickname.
        Name reservations are made after appearance and before typing a name.
        """
        generator = self.fantasy_name_generator
        if generator is None:
            generator = FantasyNameGenerator(
                history_path=APP_DIR / 'used_fantasy_names.json')
            # Recover names already assigned in the Seeder ledger even if the
            # independent duplicate-history file was removed/restored.
            state = load_json(SEED_PROGRESS_FILE, {})
            assigned = []
            for profile in state.get('profiles', {}).values():
                if not isinstance(profile, dict):
                    continue
                for record in profile.values():
                    if isinstance(record, dict):
                        assigned.extend((record.get('name_assignments') or {}).values())
            if assigned:
                generator.reserve(assigned)
            self.fantasy_name_generator = generator
        return generator

    def seed_name_for_slot(self, shard, index, ordinal, assign=False, choice=None):
        """Keep submitted names stable and apply current settings to future names."""
        mode = self.cfg.get('seed_naming_mode', 'fantasy')
        if mode not in ('convention', 'fantasy'):
            raise SeedNotReady('Unsupported Seeder naming mode: {}'.format(mode))
        _, record = self.seed_record(shard)
        key = str(int(ordinal) + 1)
        assigned = record.get('name_assignments') or {}
        existing = assigned.get(key)
        submitted = set(record.get('created', [])) | set(record.get('completed', []))
        if record.get('pending'):
            submitted.add(record['pending'])
        if existing and existing in submitted:
            return existing
        # Older combined runs only tracked the slot in Shard + Slot names.
        if not existing and submitted and (record.get('combined_shard') or record.get('reserved_seeder_shard')):
            suffix = f' {shard_abbreviation(shard)} {chr(ord("a") + int(ordinal))}'
            for saved in sorted(submitted):
                if saved.endswith(suffix) and re.fullmatch(r'[A-Za-z]{1,10}', saved[:-len(suffix)]):
                    return saved
        if mode == 'convention':
            return generated_name(self.cfg.get('seed_name_prefix', 'Llama'),
                                  self.seed_nickname, index, ordinal, shard=shard)
        style = self.cfg.get('seed_fantasy_style', 'mixed')
        if style not in STYLES:
            raise SeedNotReady('Unsupported fantasy-name style: {}'.format(style))
        if existing and not is_valid_fantasy_name(existing):
            raise SeedNotReady('Saved fantasy name for {} slot {} is invalid; '
                               'refusing to overwrite it.'.format(shard, key))
        if not assign:
            if existing and (style == 'mixed' or (' ' in existing) == (style == 'full')):
                return existing
            return None
        choice = choice or {'race': 'human', 'sex': 'male'}
        category = choice['race'] + '_' + choice['sex']
        generator = self._fantasy_generator()
        if existing and generator.matches(existing, style=style, category=category):
            return existing
        # The generator reserves to disk BEFORE the account progress ledger is
        # updated. If interrupted between those writes, one unused name is
        # consumed; no duplicate creation is possible.
        name = generator.generate(style=style, category=category)
        updated = dict(assigned)
        updated[key] = name
        self.seed_update(shard, name_assignments=updated)
        self.say('FANTASY NAME RESERVED: {} / slot {} -> {}. Saved before typing.'.format(
            shard, key, name))
        return name

    def seed_record(self, shard):
        state=load_json(SEED_PROGRESS_FILE,{})
        profiles=state.setdefault('profiles',{})
        profile=profiles.setdefault(self.seed_account_id,{})
        record=profile.setdefault(shard,{'pending':None,'created':[],'completed':[]})
        return state, record

    def seed_update(self, shard, **kwargs):
        state,record=self.seed_record(shard)
        if getattr(self, '_seeder_reserve_only', False) and 'combined_shard' in kwargs:
            kwargs['reserved_seeder_shard'] = kwargs.pop('combined_shard')
        from cycle_state import cycle_key
        cycle = cycle_key(self.cfg, getattr(self, 'progress_id', ''))
        pending = kwargs.get('pending')
        if cycle and isinstance(pending, str) and pending:
            tags = dict(record.get('creation_cycles') or {})
            if record.get('pending') == pending or pending in record.get('created', []):
                tags.setdefault(pending, cycle)
            else:
                # A confirmed-absent pending attempt may be retried in a later
                # cycle. That genuinely new submission belongs to the new cycle.
                tags[pending] = cycle
            record['creation_cycles'] = tags
        record.update(kwargs)
        atomic_json(SEED_PROGRESS_FILE,state)
        return record

    def check_seed_setup(self):
        missing=[]
        if self.cfg.get('seed_naming_mode', 'fantasy') not in ('convention', 'fantasy'):
            missing.append('Choose a supported Seeder naming mode.')
        if self.cfg.get('seed_fantasy_style', 'mixed') not in STYLES:
            missing.append('Choose Single, Full, or Mixed fantasy names.')
        for marker in SEED_MARKERS:
            if marker not in self.seed_markers:
                missing.append('Built-in Seeder marker {} is missing from assets/screen_markers; reinstall the application'.format(marker))
        for point,_ in SEED_POINTS:
            if point not in self.cfg.get('points',{}):
                missing.append('Built-in Seeder point {} is missing; reinstall the application'.format(point))
        try:
            appearance.choose_profession(self.cfg)
        except appearance.AppearanceError as exc:
            missing.append(str(exc))
        missing.extend(appearance.validate(self.cfg))
        for point in appearance.required_points(self.cfg):
            if point not in self.cfg.get('points', {}):
                missing.append('Record click point {} under Setup > Game Client > Click points'.format(point))
        if missing:raise SeedNotReady('Seeder blocked before character creation: '+ '; '.join(missing))

    def apply_appearance(self):
        """Select race, sex, styles and skin on the verified appearance screen.

        Runs before the name is typed: changing race or sex resets the styles.
        Nothing here submits a character; the final Create click comes later.
        """
        rng = getattr(self, '_appearance_rng', None)
        if rng is None:
            import random
            rng = self._appearance_rng = random.Random()
        choice = appearance.choose(self.cfg, rng)
        if choice is None:
            return None
        p = self.cfg['points']
        self.click(p['app_race_' + choice['race']])
        self.sleep(.25)
        self.click(p['app_sex_' + choice['sex']])
        self.sleep(.25)
        spacing = p['app_hair_item2'][1] - p['app_hair_item1'][1]
        for part in appearance.PARTS:
            if choice[part] is None:
                continue
            self.click(p['app_{}_open'.format(part)])
            self.sleep(.18)
            self.click(appearance.list_item_point(choice[part], p['app_{}_item1'.format(part)], spacing))
            self.sleep(.12)
        if choice['skin'] is not None:
            race = choice['race']
            self.click(p['app_skin_open'])
            self.sleep(.18)
            self.click(appearance.skin_cell_point(race, choice['skin'],
                                                  p['app_skin_{}_first'.format(race)],
                                                  p['app_skin_{}_last'.format(race)]))
            self.sleep(.12)
        for part, field in appearance.COLOR_FIELDS.items():
            if choice.get(field) is None:
                continue
            self.click(p['app_{}_color_open'.format(part)])
            self.sleep(.25)
            origin = self.find_color_palette(race=choice['race'], part=part)
            self.click(appearance.color_cell_point(choice['race'], choice[field], origin))
            self.sleep(.12)
        self.say('Appearance selected: {}.'.format(appearance.describe(choice)))
        return choice

    def seed_wait_marker(self, marker, seconds=35):
        deadline=self.clock()+float(seconds)
        while self.clock()<deadline:
            self.check()
            if self.seed_visible(marker):return
            # An unexpected disconnection is not permission to re-submit.
            stage=self.state()
            if stage in ('login','servers'):
                raise RuntimeError('Disconnected during character creation stage {}'.format(marker))
            self.sleep(.3)
        raise RuntimeError('Stage {} not recognized; no subsequent creation clicks sent.'.format(marker))

    def seed_new_available(self):
        """A missing button is *not* proof of a full account; only skip safely."""
        if self.state()!='characters':
            raise RuntimeError('New character detection requires the character-selection screen.')
        if 'seed_new_button' not in self.seed_markers:
            raise SeedNotReady('Built-in New Character button marker is missing; reinstall the application.')
        confirmed=0
        for sample in range(1,4):
            if self.seed_visible('seed_new_button'):confirmed+=1
            # Two of three samples decide it; stop as soon as the outcome is fixed.
            if confirmed>=2:return True
            if sample-confirmed>=2:return False
            self.sleep(.4)
        return False

    def seed_one(self, index, shard, *, already_on_creation=False, slot_number=None):
        from shard_policy import is_supported
        if not is_supported(shard):
            return False
        self.check_seed_setup()
        state,record=self.seed_record(shard)
        if record.get('pending'):
            raise RuntimeError('UNRESOLVED CREATION: {} / {} is pending; inspect character list manually before retrying.'.format(
                shard,record['pending']))
        unfinished=set(record.get('created',[]))-set(record.get('completed',[]))-set(record.get('abandoned_routes',[]))
        if unfinished:
            raise RuntimeError('Existing world-confirmed character(s) have unfinished routing/logout: {}. '
                               'Return to the login or shard menu and restart the Seeder.'.format(', '.join(sorted(unfinished))))
        if self.cfg.get('reserve_transfer_slot', False):
            from recovery_rules import creation_limit
            if slot_number is None or not 1 <= int(slot_number) <= creation_limit(self.cfg, shard):
                raise SeedNotReady('Transfer slot reserved: the next creation slot must be verified below '
                                   'the saved limit before creating a character.')
        # In combined Gift Cycler + Seeder mode we KNOW which slot the Cycler
        # was processing. Using len(created) would wrongly name slot 5 as 'a'
        # when four older characters already exist. Standalone Seeder retains
        # its previous creation-history sequence until slot discovery is verified.
        ordinal = (int(slot_number) - 1) if slot_number is not None else len(record.get('created', []))
        if ordinal < 0 or ordinal >= (1 if shard.casefold() in PVP_SHARDS else 7):
            raise RuntimeError('Seeder slot out of range for {}: {}'.format(shard, slot_number))
        if already_on_creation:
            self.seed_wait_marker('seed_appearance',10)
        else:
            if not self.seed_new_available():
                self.say('No verified New Character button on {}. Treating as no available slot; no click.'.format(shard))
                return False
            self.click(self.cfg['points']['seed_new_button'])
            self.seed_wait_marker('seed_appearance',self.cfg.get('seed_stage_timeout',35))
        choice = self.apply_appearance()
        name = self.seed_name_for_slot(shard, index, ordinal, assign=True, choice=choice)
        if name in record.get('created', []):
            raise RuntimeError('Previously created character {} cannot be submitted again.'.format(name))
        # This name-entry routine is OFF by default until the user visually tests
        # it. Classic Client previously ignored ordinary Python text injection.
        self.click(self.cfg['points']['seed_name_field'])
        self.sleep(.35)
        pg.write(name,interval=.075)
        self.say('Seeder typed generated name {} (method previously tested by operator).'.format(name))
        self.click(self.cfg['points']['seed_next'])
        self.seed_wait_marker('seed_profession',self.cfg.get('seed_stage_timeout',35))
        profession = appearance.choose_profession(self.cfg, getattr(self, '_appearance_rng', None))
        point = 'seed_profession_preset' if profession == 'blacksmith' else 'seed_profession_' + profession
        self.click(self.cfg['points'][point])
        self.say('Profession selected: {}.'.format(profession.title()))
        self.sleep(.45)
        # If preset selection itself advances, do not click NEXT again.
        if self.seed_visible('seed_profession'):
            self.click(self.cfg['points']['seed_next'])
        self.seed_wait_marker('seed_city',self.cfg.get('seed_stage_timeout',35))
        self.click(self.cfg['points']['seed_city_moonglow'])
        self.sleep(.45)
        self.seed_wait_marker('seed_moonglow_selected',5)
        if not self.seed_visible('seed_city'):
            raise RuntimeError('City screen changed unexpectedly before final submit. Halting.')
        # From this point forward, an unknown result is a PENDING creation.
        _, current = self.seed_record(shard)
        assignments = dict(current.get('name_assignments') or {})
        assignments[str(ordinal + 1)] = name
        self.seed_update(shard, pending=name, name_assignments=assignments)
        self.say('PENDING creation recorded for {} / {} BEFORE final submit.'.format(shard,name))
        creation_started=time.time()
        self.click(self.cfg['points']['seed_next'])
        self.say('Final creation submit clicked. Waiting up to {}s for a new RE AutoStart world confirmation.'.format(int(self.cfg.get('seed_world_timeout', 100))))
        # Poll the world bridge in small increments so an account-online
        # warning is reported immediately instead of waiting 100 seconds.
        # Do NOT clear PENDING: a rejected login is not proof the name was
        # never created on the server.
        status = None
        deadline = self.clock() + float(self.cfg.get('seed_world_timeout', 100))
        next_diagnostic = self.clock() + 5.0
        while self.clock() < deadline:
            self.check()
            status = self.bridge_status(.25, minimum_start=creation_started,
                                        expected_shard=shard)
            if status:
                break
            stage = self.state()
            if stage in ('online_busy', 'sync_error', 'login'):
                raise RuntimeError('Seeder creation outcome unknown: screen {} appeared after '
                                   'final submit for {} on {}. PENDING saved; check the '
                                   'character list and review the saved activity log before restarting. '
                                   ''.format(stage, name, shard))
            if self.clock() >= next_diagnostic:
                self.say('WORLD WAIT: screen={} | {}'.format(stage, diagnose_world_bridge(self.bridge, creation_started, shard)))
                next_diagnostic = self.clock() + 5.0
            self.sleep(.25)
        if not status:
            raise RuntimeError('Creation submitted but RE world bridge never confirmed it. '
                               'PENDING remains: {}. Verify character list before retrying.'.format(name))
        if status.get('name_sha256')!=name_hash(name):
            raise RuntimeError('New character fingerprint mismatch. Refusing route/logout; PENDING remains.')
        self.last_bridge=status
        # Creation has the same in-world shard/fingerprint proof as Gift Cycler.
        self.last_verified_shard = shard
        created=list(record.get('created',[]))
        if name not in created:created.append(name)
        self.seed_update(shard,pending=None,created=created)
        route_delay = self.cfg.get('seed_route_delay_seconds', 5)
        self.say('WORLD CONFIRMED: {} on {}. Waiting {} seconds before the inn route.'.format(name, shard, route_delay))
        self.sleep(route_delay)
        # Do not route if AutoStart switched instances or disconnected while
        # the new character was still settling.
        fresh_status=self.bridge_status(10,expected_shard=shard)
        if (not fresh_status or fresh_status.get('instance_id') != status['instance_id']
                or fresh_status.get('name_sha256') != name_hash(name)):
            raise RuntimeError('Seeder bridge changed after first-login settling; character needs manual verification.')
        self.last_bridge=fresh_status
        self.say('Starting waypoint route to the tested Moonglow inn tile.')
        position=self.bridge.request_route_inn(fresh_status,name_hash(name),timeout=105)
        self.say('Safe route verified: tile {}. Requesting logout.'.format(position))
        # Bridge resumes its status heartbeat after returning from pathfinding.
        refreshed=self.bridge_status(10,expected_shard=shard)
        if not refreshed or refreshed.get('instance_id')!=status['instance_id']:
            raise RuntimeError('Bridge vanished after route; will not assume safe logout.')
        self.last_bridge=refreshed
        self.logout()
        # Route+client logout are both complete, but this newly created char
        # will not receive the current holiday gift event.
        _,current=self.seed_record(shard)
        complete=list(current.get('completed',[]))
        if name not in complete:complete.append(name)
        self.seed_update(shard,completed=complete)
        self.say('SEEDED COMPLETE: {} / {} (not marked as gift received).'.format(shard,name))
        self.sleep(int(self.cfg.get('post_logout_seconds',7)))
        return True

    def seed_from_empty(self, index, shard, slot_number=None):
        """Cycler seeding: require a real creation screen or an available New button.

        A still-visible character list after an unverified slot login is NOT
        proof that the particular slot was empty. The verified New button is
        the permission to seed a *new* character, never to claim a gift.
        """
        if self.seed_visible('seed_appearance'):
            return self.seed_one(index, shard, already_on_creation=True,
                                 slot_number=slot_number)
        if self.state() == 'new_character':
            raise SeedNotReady('New-character screen appeared but appearance marker is not recognized. Refusing further clicks.')
        if self.state() != 'characters':
            raise RuntimeError('Empty slot recovery is not in recognized character menu.')
        return self.seed_one(index, shard, slot_number=slot_number)

    def combined_shard_status(self, shard):
        """Read the durable combined-mode handoff checkpoint for this cycle."""
        _, record = self.seed_record(shard)
        from cycle_state import cycle_key, checkpoint_for_cycle
        if getattr(self, '_seeder_reserve_only', False):
            record = dict(record, combined_shard=record.get('reserved_seeder_shard', {}))
        checkpoint = checkpoint_for_cycle(record, cycle_key(self.cfg, getattr(self, 'progress_id', '')))
        # Raising the creation limit must not keep an old lower-limit handoff
        # permanently complete. Original creation/name records are retained.
        if checkpoint.get('status') == 'complete' and 'cap' in checkpoint:
            from recovery_rules import creation_limit
            if int(checkpoint['cap']) < creation_limit(self.cfg, shard):
                return {}
        return checkpoint

    def complete_combined_shard(self, index, shard, first_slot, *, on_creation=False):
        """Seeder owns the shard from the FIRST missing slot through the cap.

        Do not return control to Gift Cycler between new-character creations.
        Every creation has its own durable pending/created/completed safeguards.
        A disconnected or ambiguous creation is NOT marked finished.
        """
        self.check_seed_setup()
        from cycle_state import cycle_key
        cycle = cycle_key(self.cfg, getattr(self, 'progress_id', ''))
        if not cycle:
            raise RuntimeError('Choose a gift cycle before starting combined mode.')
        from recovery_rules import creation_limit
        from shard_policy import is_supported
        if not is_supported(shard):
            return True
        limit = creation_limit(self.cfg, shard)
        capacity = 1 if shard.casefold() in PVP_SHARDS else int(self.cfg.get('account_cap', 7))
        checkpoint = self.combined_shard_status(shard)
        if checkpoint.get('status') == 'complete':
            self.say('COMBINED SEEDER: {} already finished in this Gift Cycle; moving to next shard.'.format(shard))
            return True
        if checkpoint.get('status') == 'in_progress':
            slot = int(checkpoint.get('next_slot', first_slot))
            self.say('RESUMING COMBINED SEEDER on {} at naming slot {}. Gift Cycler will not re-enter previously visited character rows.'.format(shard, slot))
        else:
            slot = int(first_slot)
        if not 1 <= slot <= capacity + 1:
            raise RuntimeError('Combined Seeder slot {} outside {} cap {}.'.format(slot, shard, limit))
        self.say('HANDOFF: Gift Cycler -> Character Seeder on {}. Seeder retains control until this shard is finished.'.format(shard))
        self.seed_update(shard, combined_shard={
            'cycle_id': cycle, 'status': 'in_progress', 'next_slot': slot, 'cap': limit})
        # A changed limit cannot hide an unfinished or uncertain creation.
        _, record = self.seed_record(shard)
        if record.get('pending'):
            raise RuntimeError('PENDING creation on {} must be checked against the character list and saved activity log '
                               'before applying a new creation limit.'.format(shard))
        if set(record.get('created', [])) - set(record.get('completed', [])) - set(record.get('abandoned_routes', [])):
            raise RuntimeError('Unfinished routing on {}: return to the login or shard menu and restart the Seeder before applying a new creation limit.'.format(shard))
        if slot > limit:
            if on_creation:
                self.recover_empty_slot()
            self.seed_update(shard, combined_shard={
                'cycle_id': cycle, 'status': 'complete', 'next_slot': slot, 'cap': limit,
                'reason': 'transfer_slot_reserved' if self.cfg.get('reserve_transfer_slot') else 'configured_capacity_reached'})
            self.say('CREATION LIMIT: {} stops at {} total character(s). No character created or deleted.'.format(shard, limit))
            return True
        created_this_handoff = 0
        while slot <= limit:
            self.check()
            # A prior creation can have completed before a program crash, or
            # can have been manually recovered. Never re-submit its name.
            _, record = self.seed_record(shard)
            name = (self.seed_name_for_slot(shard, index, slot - 1, assign=False)
                    if hasattr(self, 'seed_name_for_slot') else
                    generated_name(self.cfg.get('seed_name_prefix', 'Llama'),
                                   self.seed_nickname, index, slot - 1, shard=shard))
            if record.get('pending'):
                raise RuntimeError('Combined seeding interrupted on {}: {} is PENDING. Check the character list and saved activity log; no new character will be submitted.'.format(shard, record['pending']))
            if name and name in record.get('created', []):
                if name not in record.get('completed', []) and name not in record.get('abandoned_routes', []):
                    raise RuntimeError('Combined seeding interrupted on {}: {} has an interrupted route. Return to the login or shard menu and restart the Seeder.'.format(shard, name))
                self.say('Combined Seeder: {} was already created; keeping it and skipping duplicate creation.'.format(name))
                slot += 1
                self.seed_update(shard, combined_shard={
                    'cycle_id': cycle, 'status': 'in_progress', 'next_slot': slot, 'cap': limit})
                on_creation = False
                continue

            if not on_creation:
                reached = self.reach_characters(index)
                if reached == 'creation':
                    # Empty shard (zero characters) can go straight from shard
                    # selection into the appearance screen. No NEW click.
                    on_creation = True
                else:
                    self.title_identity_check(shard, wait_seconds=.2)
                    # A positive New button permits creation. Absence must be
                    # stable across several samples: don't assume one missed
                    # image match means the account is full.
                    available = False
                    for check_number in range(3):
                        self.check()
                        if self.seed_new_available():
                            available = True
                            break
                        if check_number < 2:
                            self.sleep(1)
                    if not available:
                        self.say('COMBINED SEEDER: no New Character button detected on {} after 3 checks. No additional creation attempted.'.format(shard))
                        self.seed_update(shard, combined_shard={
                            'cycle_id': cycle, 'status': 'complete', 'next_slot': slot, 'cap': limit,
                            'reason': 'new_button_absent_after_three_checks'})
                        self.say('SHARD SEEDING FINISHED: {} (New Character unavailable). Gift Cycler advances to next shard; no new characters counted as gifts.'.format(shard))
                        return True

            self.say('COMBINED SEEDER {}: creating character {} of up to {} ({}).'.format(
                shard, slot, limit, name or 'random name assigned at creation'))
            # This includes the pending->world->route->logout verification.
            # Any exception leaves combined_shard IN PROGRESS for safe resume.
            created = self.seed_one(index, shard, already_on_creation=on_creation,
                                    slot_number=slot)
            if not created:
                # A disappearing New button isn't permission to press Create.
                # Do not call it 'fully seeded' on one ambiguous reading.
                raise RuntimeError('Seeder could not verify an available New Character button on {}. Check the screen and resume; shard progress remains saved.'.format(shard))
            created_this_handoff += 1
            self.refresh_seeded_roster(shard)
            slot += 1
            self.seed_update(shard, combined_shard={
                'cycle_id': cycle, 'status': 'in_progress', 'next_slot': slot, 'cap': limit})
            on_creation = False
            self.say('COMBINED SEEDER {}: character safely logged out; {} created in this handoff. Continuing to next empty slot without returning to Gift Cycler.'.format(shard, created_this_handoff))

        self.seed_update(shard, combined_shard={
            'cycle_id': cycle, 'status': 'complete', 'next_slot': slot, 'cap': limit,
            'reason': 'transfer_slot_reserved' if self.cfg.get('reserve_transfer_slot') else 'configured_capacity_reached'})
        self.say('SHARD SEEDING FINISHED: {} (configured capacity {}). Created {} this handoff. Gift Cycler advances directly to the next shard.'.format(shard, limit, created_this_handoff))
        return True

    def resume_unfinished_current(self):
        """Finish the route of a MANUALLY logged-in, already-created character.

        This entry point NEVER clicks menus or submits character creation.
        It uses an active bridge's actual shard and name fingerprint to find
        a previously created-but-unfinished record for this local history.
        """
        history = load_json(SEED_PROGRESS_FILE, {})
        candidates = current_seed_candidates(history, self.seed_account_id)
        pending = pending_seed_candidates(history, self.seed_account_id)
        all_candidates = candidates + [item for item in pending if item not in candidates]
        if not all_candidates:
            raise RuntimeError('No unfinished or pending creations in this Seeder history.')
        self.say('Recovery mode: {} unfinished world-confirmed and {} pending record(s). '
                 'No new character will be submitted.'.format(len(candidates), len(pending)))
        with BridgeSession(self.stop) as bridge:
            self.bridge = bridge
            try:
                self.sleep(1.0)
                status = self.bridge_status(18)
                if not status:
                    raise RuntimeError('No RE AutoStart bridge response from the logged-in character. '
                                       'Log into the already-created character and check default RE profile.')
                match = candidate_for_status(all_candidates, status)
                if match is None:
                    raise RuntimeError('Logged-in RE character/shard does not match any unfinished or pending '
                                       'record for this Seeder history. No route or logout sent.')
                shard, name = match
                if match in pending:
                    # Evidence of the live character is definitive. Convert
                    # PENDING to CREATED before attempting any routing so a
                    # route failure remains safely resumable.
                    updated = load_json(SEED_PROGRESS_FILE, {})
                    promote_pending_after_world_proof(updated, self.seed_account_id,
                                                      shard, name, status)
                    self.snapshot_seed_progress('pending-world-verified')
                    atomic_json(SEED_PROGRESS_FILE, updated)
                    self.say('Verified pending creation {} exists on {}; converted to CREATED '
                             'before route recovery.'.format(name, shard))
                self.last_bridge = status
                self.last_verified_shard = shard
                self.say('RECOVERING: {} on {}. Checking Moonglow inn route.'.format(name, shard))
                position = bridge.request_route_inn(status, name_hash(name), timeout=120)
                self.say('Inn route reached {}. Verifying same RE bridge before logout.'.format(position))
                fresh = self.bridge_status(10, expected_shard=shard)
                if (not fresh or fresh.get('instance_id') != status.get('instance_id')
                        or fresh.get('name_sha256') != name_hash(name)):
                    raise RuntimeError('Bridge changed during recovery. Character left uncompleted.')
                self.last_bridge = fresh
                self.logout()  # Verifies actual return to login before allowing completion.
                # Freshly re-read to preserve any progress saved since recovery began.
                updated = load_json(SEED_PROGRESS_FILE, {})
                finish_seed_record(updated, self.seed_account_id, shard, name)
                # Keep a recovery snapshot before modifying history. Never
                # overwrite an older snapshot from an earlier run.
                snapshot = SEED_PROGRESS_FILE.with_name(
                    'seeder_progress.before-route-recovery-{}.json'.format(
                        __import__('uuid').uuid4().hex[:12]))
                shutil.copy2(str(SEED_PROGRESS_FILE), str(snapshot))
                atomic_json(SEED_PROGRESS_FILE, updated)
                self.say('Original Seeder history backed up to {}.'.format(snapshot.name))
                self.say('RECOVERED AND COMPLETED: {} / {}. No new character was created.'.format(shard, name))
                self.sleep(int(self.cfg.get('post_logout_seconds', 7)))
            finally:
                self.bridge = None

    def run_seeder(self):
        from shard_policy import run_shards
        self.check_seed_setup()
        if self.cfg.get('reserve_transfer_slot', False):
            # Reuse the established row discovery and per-shard handoff. The
            # old standalone loop counts new creations, not existing people,
            # so reducing its loop count would not reserve a transfer slot.
            original_config = self.cfg
            self.cfg = dict(original_config, create_missing=True, auto_detect_slots=True, skip_slots={})
            self._seeder_reserve_only = True
            self.say('SEEDER: keeping one slot empty. Existing character rows may be logged in '
                     'and out to check occupancy before creation. Gift completion records are unchanged.')
            try:
                return self.run(creation_only=True)
            finally:
                self.cfg = original_config
                self._seeder_reserve_only = False
        self.say('Seeder-only mode. Existing characters are NEVER deleted or replaced.')
        with BridgeSession(self.stop) as bridge:
            self.bridge=bridge
            try:
                self.sleep(1)
                if bridge.get_status():
                    raise RuntimeError('Seeder must start from login/shard menu, not from a logged-in character.')
                self.retire_interrupted_routes()
                from account_profiles import shard_seed_complete
                for index,shard in run_shards(self.cfg):
                    self.check()
                    limit=int(self.cfg.get('account_cap',7))
                    _, record = self.seed_record(shard)
                    if shard_seed_complete(record, limit):
                        self.say('SEEDER RESUME: {} already finished; skipping without opening it.'.format(shard))
                        continue
                    self.seed_update(shard, standalone_seed={'status': 'in_progress', 'cap': limit})
                    self.say('SEEDER {}: maximum {} character(s) per account.'.format(shard,limit))
                    for _ in range(limit):
                        self.check()
                        reached=self.reach_characters(index)
                        if reached=='creation':
                            self.say('Seeder: zero-character shard {} opened directly to creation.'.format(shard))
                            self.seed_one(index,shard,already_on_creation=True)
                            continue
                        if not self.seed_new_available():
                            self.say('No New button on {}. Saving this shard as finished.'.format(shard))
                            self.seed_update(shard, standalone_seed={'status': 'complete', 'cap': limit,
                                                                   'reason': 'new_button_absent'})
                            break
                        _, current = self.seed_record(shard)
                        # A world-confirmed character is already real. On a new,
                        # logged-out run, never resubmit it or replay its route.
                        unfinished = set(current.get('created', [])) - set(current.get('completed', []))
                        if unfinished:
                            retired = set(current.get('abandoned_routes', [])) | unfinished
                            self.seed_update(shard, abandoned_routes=sorted(retired))
                            self.say('Keeping prior world-confirmed characters on {}; their interrupted routes will not be replayed.'.format(shard))
                        self.seed_one(index,shard)
                    else:
                        self.seed_update(shard, standalone_seed={'status': 'complete', 'cap': limit,
                                                               'reason': 'creation_limit_reached'})
                self.say('Seeder completed included shards. Review any unresolved pending records.')
            finally:
                self.bridge=None


class MergedWorker(SeederOperations,GameWorker):
    def __init__(self,config,nickname,event_label,stop,emit,pause=None):
        GameWorker.__init__(self,config,nickname,event_label,stop,emit,pause)
        self.seed_init(nickname)
