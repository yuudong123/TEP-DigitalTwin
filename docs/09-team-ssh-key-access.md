# TEP 서버 SSH 접속 준비

Windows 노트북에서 진행한다.

1. 사용자에게 영문 이름 또는 GitHub ID를 물어 `<name>`으로 사용한다.
2. SSH 포트를 확인한다.

```powershell
Test-NetConnection 100.127.7.26 -Port 22
```

3. 기존 키가 없을 때만 Ed25519 키를 생성한다. 개인키는 절대 읽거나 출력하지 않는다.

```powershell
$key = "$env:USERPROFILE\.ssh\tep_<name>_ed25519"
New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh" | Out-Null
if (-not (Test-Path $key)) { ssh-keygen -t ed25519 -f $key -C "tep-<name>" }
```

4. 기존 `$env:USERPROFILE\.ssh\config`를 보존하면서 다음 항목을 한 번만 추가한다.

```sshconfig
Host tep-server
    HostName 100.127.7.26
    User user
    IdentityFile ~/.ssh/tep_<name>_ed25519
    IdentitiesOnly yes
```

5. 공개키와 fingerprint만 사용자에게 보여주고 서버 등록을 기다린다.

```powershell
Get-Content "$key.pub"
ssh-keygen -lf "$key.pub"
```

6. 사용자가 등록 완료를 알리면 접속을 검증한다.

```powershell
ssh -o BatchMode=yes -o ConnectTimeout=8 tep-server "hostname"
```

별도 요청 전에는 서버 상태를 변경하지 않는다.
