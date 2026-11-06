from unittest.mock import patch
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from careerpilot.database import DatabaseSettings, load_database_settings


def test_generated_file_bom_comments_and_defaults(tmp_path, monkeypatch):
    path = tmp_path / '.env'
    path.write_text('\ufeff# Local only\n\nCAREERPILOT_POSTGRES_PASSWORD=test-secret\n', encoding='utf-8')
    monkeypatch.setenv('CAREERPILOT_POSTGRES_PASSWORD', 'unrelated')
    settings = load_database_settings(path)
    assert settings.password == 'test-secret'
    assert (settings.host, settings.port, settings.database, settings.user) == (
        '127.0.0.1', 5433, 'careerpilot', 'careerpilot')
    assert 'test-secret' not in repr(settings)
    import os
    assert os.environ['CAREERPILOT_POSTGRES_PASSWORD'] == 'unrelated'


def test_explicit_connection_values(tmp_path):
    path = tmp_path / '.env'
    path.write_text('CAREERPILOT_POSTGRES_PASSWORD=a=b\nCAREERPILOT_POSTGRES_HOST=localhost\n'
                    'CAREERPILOT_POSTGRES_PORT=5544\nCAREERPILOT_POSTGRES_DB=testdb\n'
                    'CAREERPILOT_POSTGRES_USER=testuser\n')
    settings = load_database_settings(path)
    connect = Mock()
    with patch.dict('sys.modules', psycopg=SimpleNamespace(connect=connect)):
        settings.connect()
    assert connect.call_args.kwargs == dict(host='localhost', port=5544, dbname='testdb',
        user='testuser', password='a=b', connect_timeout=10,
        options='-c statement_timeout=30000 -c lock_timeout=10000')


@pytest.mark.parametrize('body', [
    '', 'PASSWORD=secret', 'export CAREERPILOT_POSTGRES_PASSWORD=secret',
    'CAREERPILOT_POSTGRES_PASSWORD=', 'CAREERPILOT_POSTGRES_PASSWORD="secret"',
    'CAREERPILOT_POSTGRES_PASSWORD=secret\nCAREERPILOT_POSTGRES_PASSWORD=second',
    'CAREERPILOT_POSTGRES_PASSWORD=secret\nCAREERPILOT_POSTGRES_PORT=abc',
    'CAREERPILOT_POSTGRES_PASSWORD=secret\nCAREERPILOT_POSTGRES_PORT=0',
])
def test_invalid_files_fail_without_echoing_values(tmp_path, body):
    path = tmp_path / '.env'
    path.write_text(body)
    with pytest.raises(ValueError) as error:
        load_database_settings(path)
    assert 'secret' not in str(error.value)


@pytest.mark.parametrize('changes', [dict(password=''), dict(host='\x00'), dict(user=' '),
    dict(port=True), dict(port=65536), dict(port='5433')])
def test_invalid_settings(changes):
    args = dict(password='test')
    args.update(changes)
    with pytest.raises(ValueError):
        DatabaseSettings(**args)
