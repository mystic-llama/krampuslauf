"""Resumable, title-verified shard discovery for official UO Classic Client.

Every character-menu Back restores the shard scrollbar to TOP (operator-tested).
No character is ever selected; any unrecognized or dangerous screen halts.
Only known shard suffixes from the OS window title are stored, never account names.
"""
import time
from cycler_engine import GameWorker, KNOWN_SHARDS, APP_DIR, selected_window
from shard_identity import shard_from_title
from shard_map import save_map, load_map
from scan_layout import row_for_index

MAP_FILE = APP_DIR / 'shard_map.json'
MAX_NAV_ATTEMPTS = 3
CLICK_WAIT_SECONDS = 6.0
BACK_WAIT_SECONDS = 7.0


class ShardScanner(GameWorker):
    def _visible_shard(self):
        """Read only an allowlisted shard suffix, never the rest of window title."""
        title = selected_window(self.window_title).title
        return shard_from_title(title, KNOWN_SHARDS)

    def _select_shard(self, index, click_point):
        """Retry clicks only while selection is not known to have happened.

        A verified title change is sufficient for a no-character shard that
        opens the appearance/creation screen instead of character selection.
        """
        for attempt in range(1, MAX_NAV_ATTEMPTS + 1):
            self.check()
            state = self.state()
            if state != 'servers':
                raise RuntimeError('Unsafe to repeat shard click: screen is {} at row {}.'.format(state,index+1))
            self.say('SCAN row {}: selecting shard.'.format(index+1) if attempt == 1 else
                     'SCAN row {}: retry {}/{} after no response.'.format(index+1,attempt,MAX_NAV_ATTEMPTS))
            self.click(click_point, expected='servers', settle=.35, double=True)
            deadline = self.clock() + CLICK_WAIT_SECONDS
            seen_title = None
            stable_since = None
            while self.clock() < deadline:
                self.sleep(.25)
                state = self.state()
                if state in ('login','online_busy','sync_error'):
                    raise RuntimeError('Scan encountered {} at row {}; progress saved.'.format(state,index+1))
                name = self._visible_shard()
                if name:
                    if state == 'servers':
                        # Don't accept a stale title while the shard list remains visible.
                        self.sleep(.2)
                        continue
                    if state in ('characters','new_character'):
                        return name
                    # Some CC builds show appearance immediately on empty shards.
                    # Accept a *stable* recognized shard title without requiring
                    # an additional fragile screenshot marker.
                    if state == 'unknown':
                        if name != seen_title:
                            seen_title,stable_since = name,self.clock()
                        elif self.clock()-stable_since >= .65:
                            self.say('SCAN row {}: shard title {} confirmed; no character list (likely empty shard).'.format(index+1,name))
                            return name
                elif state not in ('servers','unknown'):
                    # Do not reclick on any unexpected screen.
                    raise RuntimeError('Unexpected {} after selecting row {}; progress saved.'.format(state,index+1))
            final = self.state()
            title = self._visible_shard()
            if title or final != 'servers':
                # Might be entering an unrecognized menu; don't click a
                # second time where a character slot could now be present.
                raise RuntimeError('Shard row {} changed to screen {} / title {}; refusing duplicate click.'.format(
                    index+1,final,title or '<unrecognized>'))
            if attempt < MAX_NAV_ATTEMPTS:
                self.say('SCAN row {}: still on shard list; retrying after 1 second.'.format(index+1))
                self.sleep(1)
        raise RuntimeError('Shard row {} did not respond after {} attempts. Resume from saved checkpoint.'.format(index+1,MAX_NAV_ATTEMPTS))

    def _back_to_top(self, shard):
        for attempt in range(1,MAX_NAV_ATTEMPTS+1):
            self.check()
            if self.state() == 'servers':
                return
            title=self._visible_shard()
            state=self.state()
            if title != shard or state in ('login','online_busy','sync_error'):
                raise RuntimeError('Refusing Back: unexpected screen {} or shard {}. Saved previous scan rows.'.format(state,title))
            self.say('SCAN {}: Back attempt {}/{}.'.format(shard,attempt,MAX_NAV_ATTEMPTS))
            self.click(self.cfg['points']['back'])
            deadline=self.clock()+BACK_WAIT_SECONDS
            while self.clock()<deadline:
                self.sleep(.3)
                state=self.state()
                if state=='servers':
                    return
                if state in ('login','online_busy','sync_error'):
                    raise RuntimeError('Scan Back reached {}. Progress saved.'.format(state))
            if attempt<MAX_NAV_ATTEMPTS:
                self.say('Back did not return to shard list; retrying safely.')
                self.sleep(.7)
        raise RuntimeError('Unable to return to shard list after {} attempts on {}. Resume after manually returning to shard list.'.format(MAX_NAV_ATTEMPTS,shard))

    def scan(self,total=27,*,resume=False):
        total=int(total)
        if total<1 or total>40:
            raise ValueError('Shard scan count must be 1–40')
        if self.state()!='servers':
            raise RuntimeError('Open the shard list before scanning; no menu input sent.')
        prior=load_map(MAP_FILE,self.cfg,require_complete=False) if resume else None
        names=list(prior['shards']) if prior and not prior.get('complete') else []
        if len(names)>total:
            raise RuntimeError('Checkpoint has more rows than requested; start a fresh scan.')
        if len(names)==total:
            save_map(MAP_FILE,self.cfg,names,complete=(total==27))
            return names
        self.say('SCAN {}: {}/{} complete. Starting at row {} (shard list must be at TOP).'.format(
            'RESUME' if names else 'NEW',len(names),total,len(names)+1))
        if not names:
            # Clear old partial map immediately so new scans can't accidentally
            # resume outdated names after a failure on row 1.
            save_map(MAP_FILE,self.cfg,[],complete=False)
        for index in range(len(names),total):
            self.check()
            if self.state()!='servers':
                raise RuntimeError('Shard list lost before row {}. {} rows preserved.'.format(index+1,len(names)))
            row,down=row_for_index(index,int(self.cfg['visible_rows']))
            self.say('SCAN {}/{}: scrolling DOWN {} time(s); visible row {}.'.format(index+1,total,down,row+1))
            for _ in range(down):
                self.click(self.cfg['points']['scroll_down'])
                self.sleep(.10)
            first=self.cfg['points']['first_row']
            click_point=(first[0],first[1]+row*int(self.cfg['row_spacing']))
            row_picture=self.shard_row_strip(row)
            name=self._select_shard(index,click_point)
            if name.casefold() in (s.casefold() for s in names):
                raise RuntimeError('Duplicate shard {} at row {}. Sort or scrolling changed; partial map saved.'.format(name,index+1))
            self.say('SCAN row {}: identified {} from client title.'.format(index+1,name))
            self.save_shard_template(name,row_picture)
            # Do not commit this row until the client safely returned to menu.
            self._back_to_top(name)
            names.append(name)
            save_map(MAP_FILE,self.cfg,names,complete=(len(names)==27 and total==27))
            self.say('CHECKPOINT SAVED: {}/27, next row {}.'.format(len(names),len(names)+1))
            self.sleep(.2)
        self.say('SCAN FINISHED: {} title-verified shards; {}.'.format(
            len(names),'COMPLETE' if total==27 else 'partial scan only'))
        return names
