# claude-hook
클로드 Hook 생성

Claude Code에서 쓰는 훅 모음입니다.

---

## 1. 민감 정보 차단 훅

### 깃허브
https://github.com/Youkjooyoung/claude-hook/blob/main/hooks/block-secrets.py

### 훅 이름
`block-secrets.py` (이벤트: `PreToolUse`, 대상: Bash·PowerShell)

### 훅 설명
Claude가 `git commit` / `git push`를 실행하기 직전에 민감 정보를 찾으면 명령을 차단합니다.

- **검사 시점**
  - commit: 스테이징된 변경을 봅니다. 같은 명령에 `git add`가 있으면 새 파일까지 봅니다.
  - push: 아직 원격에 없는 커밋을 모두 봅니다.
  - 그 밖의 명령은 바로 통과합니다.
- **차단 파일**: `.env`, `.env.*`, `*.pem`, `*.key`, `id_rsa`, `credentials*`, `secrets*`, `client_secret*.json`, `secrets.toml`, `*token*.json`, `.netrc`, `.npmrc`, `.pypirc`
  - `.env.example`, `.env.sample`, `.env.template`은 허용합니다.
- **차단 내용**
  - 개인키 블록
  - AWS, Anthropic, OpenAI, Groq, HuggingFace, Google, GitHub, Slack, Discord 키·토큰
  - DB URL 속 비밀번호
  - `api_key = "..."`처럼 8자 이상 하드코딩된 값
- **예외**: `os.getenv(...)`, `your_...`, `example`, `<...>` 같은 예시 값은 통과합니다.

### 훅 설치 명령어
```powershell
git clone https://github.com/Youkjooyoung/claude-hook.git
cd claude-hook
New-Item -ItemType Directory -Force "$HOME\.claude\hooks" | Out-Null
Copy-Item hooks\block-secrets.py "$HOME\.claude\hooks\"
```
그다음 `settings.example.json`의 `PreToolUse` 부분을 `~/.claude/settings.json`의 `hooks`에 병합합니다.
- `<사용자>`는 내 계정 이름으로 바꿉니다.
- 파이썬 경로는 내 환경에 맞게 바꿉니다. Python 3.8 이상이 필요합니다.

병합한 뒤 Claude Code를 다시 시작합니다.

### 훅 사용 예시
```
사용자: 이거 커밋하고 깃허브에 올려줘

PreToolUse:Bash hook error: [보안 훅] GitHub 업로드 전에 민감 정보/위험 파일이 발견되어 차단했습니다.
  - [파일] .env  (.env 환경변수 파일)
  - [내용] app.py  (Groq API Key: gsk_******)
조치: 파일은 git rm --cached + .gitignore, 키는 os.getenv()/.env 로 옮긴 뒤 다시 시도하세요.
```

---

## 2. 답변 완료 알림 훅

### 깃허브
https://github.com/Youkjooyoung/claude-hook/blob/main/hooks/notify-done.ps1

### 훅 이름
`notify-done.ps1` (이벤트: `Stop`)

### 훅 설명
Claude 답변이 끝나면 화면 중앙에 작업 폴더 이름이 적힌 알림창을 띄우고, 5초 뒤 자동으로 닫습니다. Windows 전용이고, 백그라운드로 실행되어 작업을 늦추지 않습니다.

### 훅 설치 명령어
```powershell
git clone https://github.com/Youkjooyoung/claude-hook.git
cd claude-hook
New-Item -ItemType Directory -Force "$HOME\.claude\hooks" | Out-Null
Copy-Item hooks\notify-done.ps1 "$HOME\.claude\hooks\"
```
그다음 `settings.example.json`의 `Stop` 부분을 `~/.claude/settings.json`의 `hooks`에 병합합니다. 병합한 뒤 Claude Code를 다시 시작합니다.

### 훅 사용 예시
```
사용자: 이 코드 리뷰해줘   (질문 후 다른 창에서 작업)
→ Claude 답변이 끝나면 화면 중앙에 민트색 알림창이 뜨고 5초 뒤 사라짐
```

---

## 주의
- 민감 정보 차단 훅은 Claude가 실행하는 명령만 검사합니다. 터미널에서 직접 하는 push는 막지 못합니다.
- 정규식 기반이라 오탐·미탐이 있을 수 있습니다.
