"""Desktop startup must wait for HTTP readiness, without real processes or browser windows."""
import importlib
import json
from unittest.mock import Mock
import pytest


def launcher():
    return importlib.import_module('scripts.launch_desktop')


@pytest.fixture(autouse=True)
def isolated_launcher(tmp_path,monkeypatch):
    mod=launcher()
    monkeypatch.setattr(mod,'ROOT',tmp_path)
    python=tmp_path/'.venv/Scripts/pythonw.exe'
    python.parent.mkdir(parents=True)
    python.write_bytes(b'fake executable, never launched')


def test_waits_for_ready_health_instead_of_a_fixed_startup_delay(monkeypatch):
    mod=launcher();clock=[0.0];attempts=[]
    def ready(url,timeout=1):attempts.append(clock[0]);return len(attempts)>=3
    monkeypatch.setattr(mod,'is_server_ready',ready)
    monkeypatch.setattr(mod.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(mod.time,'sleep',lambda seconds:clock.__setitem__(0,clock[0]+seconds))
    assert mod.wait_for_server('http://localhost:8080',timeout=5,interval=.5)
    assert len(attempts)==3


def test_readiness_wait_is_bounded(monkeypatch):
    mod=launcher();clock=[0.0]
    monkeypatch.setattr(mod,'is_server_ready',lambda *a,**kw:False)
    monkeypatch.setattr(mod.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(mod.time,'sleep',lambda seconds:clock.__setitem__(0,clock[0]+seconds))
    assert not mod.wait_for_server('http://localhost:8080',timeout=2,interval=.5)
    assert clock[0]==2


def test_a_healthy_server_is_reused_without_starting_another(monkeypatch):
    mod=launcher();opened=[]
    monkeypatch.setattr(mod,'is_server_ready',lambda *a,**kw:True)
    monkeypatch.setattr(mod.subprocess,'Popen',lambda *a,**kw:(_ for _ in ()).throw(AssertionError('Duplicate server')))
    monkeypatch.setattr(mod,'open_app_window',opened.append)
    mod.launch()
    assert opened==['http://localhost:8080']


def test_browser_opens_only_after_server_is_ready(monkeypatch):
    mod=launcher();events=[]
    monkeypatch.setattr(mod,'is_server_ready',lambda *a,**kw:False)
    def spawn(args,**kwargs):
        assert kwargs['env']['NO_BROWSER']=='1'
        assert kwargs['cwd']==str(mod.ROOT)
        assert kwargs['stdout'].name==str(mod.ROOT/'outputs/server.log')
        assert kwargs['stderr'] is kwargs['stdout']
        events.append('server')
        return Mock(poll=lambda:None)
    monkeypatch.setattr(mod.subprocess,'Popen',spawn)
    monkeypatch.setattr(mod,'wait_for_server',lambda *a,**kw:events.append('ready') or True)
    monkeypatch.setattr(mod,'open_app_window',lambda url:events.append('window'))
    mod.launch()
    assert events==['server','ready','window']


def test_failed_start_does_not_open_an_offline_app_window(monkeypatch):
    import pytest
    mod=launcher();opened=[]
    monkeypatch.setattr(mod,'is_server_ready',lambda *a,**kw:False)
    monkeypatch.setattr(mod.subprocess,'Popen',lambda *a,**kw:Mock(poll=lambda:1))
    monkeypatch.setattr(mod,'wait_for_server',lambda *a,**kw:False)
    monkeypatch.setattr(mod,'open_app_window',opened.append)
    with pytest.raises(RuntimeError):mod.launch()
    assert opened==[]


def test_cold_start_health_probe_is_short_and_keeps_browser_origin_unchanged(monkeypatch):
    import urllib.error
    mod=launcher();requests=[]
    def unavailable(url,timeout):
        requests.append((url,timeout))
        raise urllib.error.URLError('Synthetic connection refused')
    monkeypatch.setattr(mod._LOCAL_HTTP,'open',unavailable)
    assert not mod.is_server_ready('http://localhost:8080')
    assert requests[0][0]=='http://127.0.0.1:8080/api/health'
    assert requests[0][1]<=.25
    assert mod.APP_URL=='http://localhost:8080'


def test_repeated_startup_probes_also_use_the_short_connection_budget(monkeypatch):
    mod=launcher();clock=[0.0];budgets=[]
    def unavailable(url,timeout):budgets.append(timeout);return False
    monkeypatch.setattr(mod,'is_server_ready',unavailable)
    monkeypatch.setattr(mod.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(mod.time,'sleep',lambda seconds:clock.__setitem__(0,clock[0]+seconds))
    assert not mod.wait_for_server(timeout=1,interval=.25)
    assert max(budgets)<=.25
