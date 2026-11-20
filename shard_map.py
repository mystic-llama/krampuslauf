"""Persistent, privacy-safe shard maps indexed by Windows time zone.

Only recognized shard names are stored. Neither full game titles nor account
identifiers enter the map. Maps for different time zones are retained separately.
"""
from __future__ import annotations
import os
import json
import secrets
import time
from datetime import datetime


def timezone_key():
    if os.name=='nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                  r'SYSTEM\CurrentControlSet\Control\TimeZoneInformation') as k:
                return str(winreg.QueryValueEx(k,'TimeZoneKeyName')[0])
        except (OSError,ImportError):pass
    return '|'.join(str(x) for x in time.tzname)+'|UTC{}'.format(time.timezone)


def geometry_key(config):
    return {'visible_rows':int(config.get('visible_rows',9)),
            'row_spacing':int(config.get('row_spacing',25))}


def _profiles(raw):
    if raw.get('version')==2 and isinstance(raw.get('profiles'),dict):
        return dict(raw['profiles'])
    if raw.get('version')==1 and raw.get('timezone'):
        return {raw['timezone']:{key:value for key,value in raw.items() if key!='version'}}
    return {}


def load_json(path,default):
    try:
        obj=json.loads(path.read_text(encoding='utf-8'))
        return obj if isinstance(obj,dict) else default
    except (FileNotFoundError,OSError,ValueError,UnicodeError):
        return default


def atomic_json(path,object_):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+secrets.token_hex(6)+'.tmp')
    try:
        temp.write_text(json.dumps(object_,indent=2,ensure_ascii=False),encoding='utf-8')
        os.replace(str(temp),str(path))
    finally:
        try:temp.unlink()
        except FileNotFoundError:pass


def load_map(path, config, *, require_complete=True):
    data=_profiles(load_json(path,{})).get(timezone_key())
    if not isinstance(data,dict) or data.get('geometry')!=geometry_key(config):return None
    names=data.get('shards')
    if not isinstance(names,list) or not names or any(not isinstance(x,str) for x in names):return None
    if len({x.casefold() for x in names})!=len(names):return None
    if require_complete and not data.get('complete',False):return None
    return data


def save_map(path,config,names,*,complete=False):
    profiles=_profiles(load_json(path,{}))
    payload={'timezone':timezone_key(),'geometry':geometry_key(config),
             'complete':bool(complete),'shards':list(names),
             'scanned_at':datetime.now().isoformat(timespec='seconds'),
             'scroll_behavior':'resets-to-top-after-character-back'}
    profiles[timezone_key()]=payload
    atomic_json(path,{'version':2,'profiles':profiles})
    return payload


def map_status(path,config):
    raw=load_json(path,{})
    profiles=_profiles(raw)
    if not profiles:return 'No shard scan saved'
    record=profiles.get(timezone_key())
    if not record:return 'No map for current Windows time zone — rescan'
    if record.get('geometry')!=geometry_key(config):return 'Row geometry changed — rescan required'
    return '{} shard(s) scanned{}'.format(len(record.get('shards',[])),
               ' — VERIFIED' if record.get('complete') else ' — INCOMPLETE')
