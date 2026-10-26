# claude-hook
클로드 Hook 생성

Claude Code에서 쓰는 훅 모음입니다. `.gitignore`만으로는 막지 못하는 실수(키 하드코딩, `git add -f`로 올린 `.env` 등)를 Claude가 `git commit` / `git push`를 실행하기 직전에 한 번 더 막습니다.

## 훅 목록

| 파일 | 이벤트 | 하는 일 |
|------|--------|---------|
| `hooks/block-secrets.py` | `PreToolUse` (Bash, PowerShell) | commit·push 직전에 민감 정보·위험 파일을 찾으면 명령을 차단 |
| `hooks/notify-done.ps1` | `Stop` | Claude 답변이 끝나면 화면 중앙에 알림창을 띄우고 5초 뒤 닫음 (Windows) |

## block-secrets.py

### 검사 시점
- **commit**: 스테이징된 변경. 같은 명령에 `git add`나 `commit -a`가 있으면 작업 트리 변경과 새 파일까지 미리 검사
- **push**: 아직 원격에 없는 커밋 전부
- 그 밖의 명령은 검사 없이 바로 통과

### 차단 대상
- **파일 이름**: `.env`, `.env.*`(`.env.example`·`.env.sample`·`.env.template`은 허용), `*.pem` `*.key` `*.p12` `*.pfx` `*.jks` `*.ppk`, `id_rsa` 등 SSH 개인키, `credentials*`, `secrets*`, `client_secret*.json`, `secrets.toml`, `*token*.json`, `.netrc` `.npmrc` `.pypirc`
- **내용**: 개인키 블록, AWS / Anthropic / OpenAI / Groq / HuggingFace / Google / GitHub / Slack / Discord 키·토큰, DB 접속 URL 속 비밀번호, `api_key = "..."` `password = "..."` 같은 하드코딩(8자 이상)
- **예외**: `os.getenv(...)`, `your_...`, `example`, `<...>`, `xxx` 같은 예시 값은 통과

### 차단 화면 예시
```
[보안 훅] GitHub 업로드 전에 민감 정보/위험 파일이 발견되어 차단했습니다.
  - [내용] e.py  (GitHub Token: ghp_******)
조치: 파일은 git rm --cached + .gitignore, 키는 os.getenv()/.env 로 옮긴 뒤 다시 시도하세요.
```
값은 앞 4자만 보이게 가립니다. 검사 중 오류가 나면 commit·push를 막는 쪽으로 동작합니다.

## 설치

1. `hooks/` 안의 파일을 `C:\Users\<사용자>\.claude\hooks\`에 복사합니다.
2. `settings.example.json`의 `hooks` 내용을 `C:\Users\<사용자>\.claude\settings.json`에 **병합**합니다. (기존 설정을 덮어쓰지 않도록 주의)
   - `<사용자>`를 내 계정 이름으로, 파이썬 경로를 내 환경에 맞게 바꿉니다. (Python 3.8 이상, 표준 라이브러리만 사용)
3. Claude Code를 다시 시작하거나 `/hooks`를 한 번 열면 적용됩니다.

### 동작 확인
```bash
echo '{"cwd":"<레포 경로>","tool_input":{"command":"git commit -m test"}}' | python -X utf8 hooks/block-secrets.py
```
문제가 없으면 아무것도 출력하지 않고, 발견되면 `"permissionDecision": "deny"` JSON을 출력합니다.

## 한계
- Claude가 실행하는 명령만 검사합니다. 터미널에서 직접 하는 push는 막지 못하므로 git `pre-commit` 훅을 함께 쓰는 것을 권장합니다.
- 정규식 기반이라 오탐·미탐이 있을 수 있습니다.
