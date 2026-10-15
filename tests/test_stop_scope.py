"""Exercise the Windows shutdown guard without touching Docker or WSL."""
import base64
from pathlib import Path
import shutil
import subprocess

import pytest


POWERSHELL = shutil.which('powershell.exe')
GUARD = Path(__file__).resolve().parents[1] / 'deploy/check-stop-scope.ps1'
pytestmark = pytest.mark.skipif(POWERSHELL is None, reason='Windows PowerShell guard')


@pytest.mark.parametrize('docker_exit,labels,backend,distros,wsl_exit,expected', [
    (0, 'com.docker.compose.project=tep_digitaltwin', False, 'docker-desktop', 0, 0),
    (0, 'com.docker.compose.project=other', False, 'docker-desktop', 0, 2),
    (0, '', False, 'docker-desktop', 0, 2),
    (0, 'com.docker.compose.project=tep_digitaltwin', False, 'Ubuntu', 0, 2),
    (1, '', True, 'docker-desktop', 0, 2),
    (1, '', False, '', 0, 0),
    (0, 'com.docker.compose.project=tep_digitaltwin', False, '', 1, 2),
])
def test_shutdown_scope_is_fail_closed(docker_exit, labels, backend, distros, wsl_exit, expected):
    script = f"""
function global:docker {{
    if ($args[0] -eq 'info') {{ $global:LASTEXITCODE={docker_exit}; return }}
    if ($args[0] -ne 'ps') {{ throw 'Unexpected Docker mutation' }}
    $global:LASTEXITCODE=0
    '{{"Names":"fixture","Labels":"{labels}"}}'
}}
function global:Get-Process {{
    param($Name, $ErrorAction)
    if ($Name -ne 'com.docker.backend') {{ throw 'Unexpected process inventory' }}
    if (${str(backend).lower()}) {{ [pscustomobject]@{{ProcessName='com.docker.backend'}} }}
}}
function global:wsl.exe {{
    if (($args -join ' ') -ne '--list --running --quiet') {{ throw 'Unexpected WSL mutation' }}
    $global:LASTEXITCODE={wsl_exit}
    '{distros}'
}}
& '{GUARD}'
exit $LASTEXITCODE
"""
    encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    result = subprocess.run([POWERSHELL, '-NoProfile', '-EncodedCommand', encoded],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == expected, result.stdout + result.stderr
