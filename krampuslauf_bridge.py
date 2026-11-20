# krampuslauf_bridge.py  —  Razor Enhanced / IronPython (official UO Classic Client)
# Install in RE's existing default Scripts profile and enable "AutoStart on Login".
# This script NEVER logs out on its own. It only follows a fresh, scoped
# command from an active local Krampuslauf GUI session.
# No network, account/password access, chat text, or external Python needed.

import json
import time
import hashlib
from System import Guid, Environment
from System.IO import File, Directory, Path

# Same data folder the desktop app uses. Start Krampuslauf once after updating
# so an older data folder is moved here before this script runs.
ROOT = Path.Combine(Environment.GetFolderPath(
    Environment.SpecialFolder.LocalApplicationData), "Krampuslauf")
SESSION = Path.Combine(ROOT, "bridge_session.json")
STATUS = Path.Combine(ROOT, "bridge_status.json")
COMMAND = Path.Combine(ROOT, "bridge_command.json")
ACK = Path.Combine(ROOT, "bridge_ack.json")
INSTANCE_ID = Guid.NewGuid().ToString("N")
STARTED_AT = time.time()
POLL_MS = 450
PROTOCOL = 1

# RE builds can expose different Python engines. In Python 2, json.loads()
# can return unicode, which is included in basestring but not plain str.
# In Python 3, basestring no longer exists. Support both explicitly.
try:
    STRING_TYPES = (basestring,)
except NameError:
    STRING_TYPES = (str,)

seen_commands = set()


def name_digest():
    try:
        return hashlib.sha256(str(Player.Name).strip().lower().encode('utf-8')).hexdigest()
    except:
        return ''


def route_to_moonglow(cmd, expected_digest):
    """Walk to the two verified Moonglow tiles, with safe delayed retries.

    The connection bridge can start before a brand-new client's world is fully
    interactive. Only server-confirmed positions authorize route completion;
    never dismiss unknown gumps or log out from an unverified location.
    """
    if not Player.Connected or name_digest() != expected_digest:
        raise RuntimeError('Unexpected character or disconnected during route')
    if cmd.get('waypoints') != [[4403, 1170], [4403, 1164]]:
        raise RuntimeError('Unsupported route; refusing to walk')

    def xyz():
        pos = Player.Position
        return (int(pos.X), int(pos.Y), int(pos.Z))

    def route_session_ok(stage):
        session = read_json(SESSION)
        if (not valid_session(session, time.time()) or
                session.get('run_id') != cmd.get('run_id') or
                not Player.Connected or name_digest() != expected_digest):
            raise RuntimeError('GUI session stopped or character changed at ' + stage)

    def nearby(x, y, tolerance):
        cx, cy, cz = xyz()
        return max(abs(cx-x), abs(cy-y)) <= tolerance

    def open_gump_ids():
        # Diagnostic only: NEVER automatically close arbitrary first-login gumps.
        try:
            return [hex(int(v)) for v in list(Gumps.AllGumpIDs())[:12]]
        except Exception:
            return []

    # A first-login RE AutoStart heartbeat is not always proof that movement
    # and world initialization have settled. Wait for a valid spawn coordinate.
    spawn_deadline = time.time() + 12.0
    while time.time() < spawn_deadline:
        route_session_ok('waiting for Moonglow spawn')
        cx, cy, cz = xyz()
        if abs(cx-4403) <= 50 and abs(cy-1170) <= 50:
            break
        Misc.Pause(400)
    else:
        raise RuntimeError('Moonglow starting position was not ready; last=' + str(xyz()))

    # Additional short settling period for initial news/stat/creation overlays.
    for _ in range(8):
        route_session_ok('new-character world settling')
        Misc.Pause(500)

    for index, pair in enumerate(cmd['waypoints']):
        x, y = int(pair[0]), int(pair[1])
        tolerance = 0 if index == 1 else 1
        last_result = None
        last_position = xyz()
        # A path may be temporarily obstructed by load/door lag or by a
        # first-login modal. Retry pathfinding, NEVER character creation.
        for attempt in range(1, 4):
            route_session_ok('waypoint {} attempt {}'.format(index+1, attempt))
            if nearby(x, y, tolerance):
                break
            write_json(ACK, {
                'protocol': PROTOCOL, 'run_id': cmd['run_id'],
                'instance_id': INSTANCE_ID, 'command_id': cmd['command_id'],
                'result': 'started', 'stage': 'waypoint_{}'.format(index+1),
                'attempt': attempt, 'position': list(xyz()),
                'seen_at': time.time()
            })
            route = PathFinding.Route()
            route.X = x
            route.Y = y
            route.Run = False
            route.StopIfStuck = True
            route.MaxRetry = 3
            route.Timeout = 18
            route.UseResync = True
            last_result = PathFinding.Go(route)
            # Give server position updates time to arrive; do not trust the
            # boolean alone, since the destination tile is our ground truth.
            for _ in range(5):
                route_session_ok('verifying waypoint {}'.format(index+1))
                if nearby(x, y, tolerance):
                    break
                Misc.Pause(300)
            last_position = xyz()
            if nearby(x, y, tolerance):
                break
            if attempt < 3:
                Misc.Pause(1000)
        else:
            raise RuntimeError(
                'Waypoint {} failed after 3 attempts: expected=({}, {}), '
                'actual={}, Go() returned={}, open_gump_ids={}. '
                'Check doors and dismiss any first-login prompts manually; '
                'do not create another character.'.format(
                    index+1, x, y, last_position, last_result, open_gump_ids()))

    route_session_ok('inn safe-tile verification')
    if not nearby(4403, 1164, 0):
        raise RuntimeError('Inn safe tile not reached; final=' + str(xyz()))
    return list(xyz())


def tidy_gumps(cmd):
    """Close only RE-managed windows; never guess client-side window IDs.

    Town Crier matching uses visible gump text. An optional explicit 'all'
    mode closes all RE-detected gumps on the current, verified character.
    """
    mode = str(cmd.get('mode', 'town_crier'))
    if mode not in ('town_crier', 'all'):
        raise RuntimeError('Unsupported gump cleanup mode')
    if not Player.Connected or name_digest() != cmd.get('name_sha256'):
        raise RuntimeError('Character changed before gump cleanup')
    closed = []
    ids = list(Gumps.AllGumpIDs())
    for gumpid in ids:
        # A stop request invalidates operations even during the cleanup loop.
        verify = read_json(SESSION)
        if not valid_session(verify, time.time()) or verify.get('run_id') != cmd.get('run_id'):
            raise RuntimeError('Krampuslauf session stopped during gump cleanup')
        match = mode == 'all'
        if not match:
            try:
                text = ' '.join([str(t) for t in Gumps.GetGumpText(gumpid)]).lower()
                match = any(fragment in text for fragment in (
                    'town crier', 'ultima online publish',
                    'close and do not show this version again'))
            except Exception:
                pass
        if match:
            Gumps.CloseGump(gumpid)
            closed.append(int(gumpid))
            Misc.Pause(100)
    # Reopen only the backpack; it is an item container, not a Gumps gump.
    if Player.Connected and Player.Backpack is not None:
        Items.UseItem(Player.Backpack.Serial)
    return closed


def read_json(path):
    try:
        if not File.Exists(path):
            return None
        data = json.loads(File.ReadAllText(path))
        return data if isinstance(data, dict) else None
    except:
        return None


def write_json(path, data):
    # The RE script writes only status/ACK files in a local appdata folder.
    # File.Copy(overwrite=True) avoids exposing a partly written JSON payload.
    Directory.CreateDirectory(ROOT)
    tmp = path + "." + INSTANCE_ID + ".tmp"
    File.WriteAllText(tmp, json.dumps(data))
    File.Copy(tmp, path, True)
    File.Delete(tmp)


def valid_session(data, now):
    if not data or data.get('protocol') != PROTOCOL or data.get('enabled') is not True:
        return False
    rid = data.get('run_id', '')
    if not isinstance(rid, STRING_TYPES) or len(rid) != 32:
        return False
    try:
        return (now - 7.0 < float(data.get('updated_at', 0)) <= now + 1.0 and
                now < float(data.get('expires_at', 0)) <= now + 7.5)
    except:
        return False


# Some RE builds schedule AutoStart just before Player.Connected becomes True.
# Allow a brief, passive connection warmup; never treat this as permission
# to send any commands or disconnect the player.
ready_deadline = time.time() + 20.0
while not Player.Connected and time.time() < ready_deadline:
    Misc.Pause(250)

# AutoStart on normal gameplay is safe: no active GUI heartbeat = no action.
# This loops at low frequency while the character stays connected.
while Player.Connected:
    now = time.time()
    session = read_json(SESSION)
    if valid_session(session, now):
        rid = session['run_id']
        shard = str(Misc.ShardName() or "")
        if shard:
            try:
                write_json(STATUS, {
                    'protocol': PROTOCOL, 'run_id': rid,
                    'instance_id': INSTANCE_ID, 'shard': shard,
                    'connected': True, 'started_at': STARTED_AT,
                    'name_sha256': name_digest(),
                    'seen_at': time.time()
                })
            except:
                pass  # Without status the GUI fails closed.

            cmd = read_json(COMMAND)
            if cmd and cmd.get('command_id') not in seen_commands:
                try:
                    issued = float(cmd.get('issued_at', 0))
                    expires = float(cmd.get('expires_at', 0))
                    ok = (cmd.get('protocol') == PROTOCOL and
                          cmd.get('action') in ('logout', 'route_inn', 'tidy_gumps') and
                          cmd.get('run_id') == rid and
                          cmd.get('instance_id') == INSTANCE_ID and
                          cmd.get('shard') == shard and
                          isinstance(cmd.get('command_id'), STRING_TYPES) and
                          len(cmd['command_id']) >= 16 and
                          now - 4.5 < issued <= now + 0.5 and
                          issued <= expires <= issued + 4.5 and now < expires and
                          issued >= STARTED_AT - 1.0)
                    if ok:
                        # Recheck GUI heartbeat immediately before disconnect.
                        verify = read_json(SESSION)
                        ok = (valid_session(verify, time.time()) and
                              verify.get('run_id') == rid and Player.Connected)
                    if ok:
                        seen_commands.add(cmd['command_id'])
                        try:
                            write_json(ACK, {
                                'protocol': PROTOCOL, 'run_id': rid,
                                'instance_id': INSTANCE_ID,
                                'command_id': cmd['command_id'],
                                'result': 'accepted', 'seen_at': time.time()
                            })
                        except:
                            ok = False  # Don't disconnect unless GUI can observe ACK.
                    if ok and cmd.get('action') == 'route_inn':
                        try:
                            if name_digest() != cmd.get('name_sha256') or not name_digest():
                                raise RuntimeError('Character identity does not match route request')
                            position=route_to_moonglow(cmd,cmd['name_sha256'])
                            write_json(ACK, {
                                'protocol': PROTOCOL,'run_id':rid,'instance_id':INSTANCE_ID,
                                'command_id':cmd['command_id'],'result':'completed',
                                'position':position,'seen_at':time.time()
                            })
                        except Exception as error:
                            write_json(ACK, {
                                'protocol': PROTOCOL,'run_id':rid,'instance_id':INSTANCE_ID,
                                'command_id':cmd['command_id'],'result':'failed',
                                'error':str(error),'seen_at':time.time()
                            })
                    elif ok and cmd.get('action') == 'tidy_gumps':
                        try:
                            closed = tidy_gumps(cmd)
                            write_json(ACK, {
                                'protocol': PROTOCOL, 'run_id': rid,
                                'instance_id': INSTANCE_ID, 'command_id': cmd['command_id'],
                                'result': 'completed', 'closed': closed,
                                'seen_at': time.time()
                            })
                        except Exception as error:
                            write_json(ACK, {
                                'protocol': PROTOCOL, 'run_id': rid,
                                'instance_id': INSTANCE_ID, 'command_id': cmd['command_id'],
                                'result': 'failed', 'error': str(error),
                                'seen_at': time.time()
                            })
                    elif ok:
                        Misc.Disconnect()
                        break
                except:
                    pass  # Invalid commands cannot cause disconnect.
    Misc.Pause(POLL_MS)
