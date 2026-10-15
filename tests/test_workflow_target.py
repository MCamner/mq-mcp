"""Explicit workflow targets must never fall back to the server repository."""
import importlib.util
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('workflow_target_server', ROOT / 'mq-mcp/server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    path = tmp_path / 'target'
    path.mkdir()
    subprocess.run(['git', 'init', '-q', str(path)], check=True)
    (path / 'a.py').write_text('x = 1\n')
    subprocess.run(['git', '-C', str(path), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(path), '-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-qm', 'initial'], check=True)
    monkeypatch.setenv('MQ_MCP_LOCAL_REPOS', str(path))
    return path


def test_diff_uses_target_including_staged_changes(repo):
    (repo / 'a.py').write_text('x = 2\n')
    subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
    result = server.git_diff(repo_path=str(repo))
    assert result['repo_path'] == str(repo.resolve())
    assert result['status'] == 'PASS'
    assert '+x = 2' in result['output']


def test_invalid_targets_fail_closed(repo):
    for tool in (server.git_diff, server.review_diff, server.run_tests):
        result = tool(repo_path=str(repo / 'missing'))
        assert result['status'] == 'ERROR'


def test_review_passes_target_to_each_file(repo, monkeypatch):
    (repo / 'a.py').write_text('x = 2\n')
    calls = []
    monkeypatch.setattr(server, 'review_file', lambda path, **kw: calls.append((path, kw)) or 'review_file failed: no API')
    result = server.review_diff(repo_path=str(repo))
    assert calls == [('a.py', {'mode': 'comment', 'deep': False, 'repo_path': str(repo.resolve())})]
    assert result['status'] == 'ERROR'
    assert result['coverage']['reviewed_files'] == 0


def test_tests_report_exit_and_actual_cwd(repo, monkeypatch):
    real_run = subprocess.run
    def run(args, **kwargs):
        if args[:3] == ['python3', '-m', 'pytest']:
            assert kwargs['cwd'] == str(repo.resolve())
            return subprocess.CompletedProcess(args, 1, '1 failed', '')
        return real_run(args, **kwargs)
    monkeypatch.setattr(server.subprocess, 'run', run)
    result = server.run_tests(repo_path=str(repo))
    assert result['status'] == 'FAIL'
    assert result['exit_code'] == 1


def test_context_is_bounded_and_scoped(repo, monkeypatch):
    (repo / 'a.py').write_text('x = 2\n')
    observed = []
    monkeypatch.setattr(server, 'review_file', lambda *a, **kw: observed.append(server._WORKFLOW_REVIEW_CONTEXT.get()) or 'review completed')
    assert server.review_diff(repo_path=str(repo), context='card data')['status'] == 'COMPLETED'
    assert observed == ['card data']
    assert server._WORKFLOW_REVIEW_CONTEXT.get() == ''
    assert server.review_diff(repo_path=str(repo), context='x' * 12001)['status'] == 'ERROR'


def test_status_is_target_bound(repo):
    assert server.git_status(repo_path=str(repo))['repo_path'] == str(repo.resolve())


def test_nonroot_and_relative_targets_rejected(repo):
    (repo / 'sub').mkdir()
    assert server.git_diff(repo_path=str(repo / 'sub'))['status'] == 'ERROR'
    assert server.git_diff(repo_path='.')['status'] == 'ERROR'


def test_review_reports_unsupported_files_as_limited(repo, monkeypatch):
    (repo / 'asset.txt').write_text('changed\n')
    subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
    monkeypatch.setattr(server, 'review_file', lambda *a, **kw: pytest.fail('unsupported file reviewed'))
    result = server.review_diff(repo_path=str(repo))
    assert result['status'] == 'LIMITED'
    assert result['coverage'] == {'changed_files': 1, 'eligible_files': 0, 'reviewed_files': 0, 'complete': False}


def test_unallowed_target_does_not_fall_back(repo, monkeypatch):
    monkeypatch.delenv('MQ_MCP_LOCAL_REPOS')
    monkeypatch.delenv('MQ_MCP_ALLOWED_PATHS', raising=False)
    assert server.git_diff(repo_path=str(repo))['status'] == 'ERROR'


def test_clean_target_diff_is_empty(repo):
    result = server.git_diff(repo_path=str(repo))
    assert result['status'] == 'PASS'
    assert result['output'] == ''


def test_mismatched_repo_name_is_rejected(repo):
    assert server.run_tests(repo_name='mq-mcp', repo_path=str(repo))['status'] == 'ERROR'


@pytest.mark.parametrize('output', ['No review output.', 'Not reviewed: 2 further section(s) were truncated.'])
def test_empty_or_limited_review_is_not_complete(repo, monkeypatch, output):
    (repo / 'a.py').write_text('x = 2\n')
    monkeypatch.setattr(server, 'review_file', lambda *args, **kwargs: output)
    result = server.review_diff(repo_path=str(repo))
    assert result['status'] == 'ERROR'
    assert result['coverage']['complete'] is False
    assert result['coverage']['reviewed_files'] == 0
