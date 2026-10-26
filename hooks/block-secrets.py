"""PreToolUse 훅: git commit / git push 직전에 민감 정보·위험 파일을 검사해 차단한다.

- commit: 스테이징된 변경(같은 명령에 git add / commit -a 가 있으면 작업 트리 변경까지)
- push  : 아직 원격에 없는 커밋 전부
검사 대상과 무관한 명령은 즉시 통과한다.
"""
import json
import os
import re
import subprocess
import sys

# 올리면 안 되는 파일 이름 (경로의 마지막 부분 기준)
DANGEROUS_FILES = [
    (re.compile(r"^\.env$|^\.env\.(?!example$|sample$|template$).+|.+\.env$", re.I), ".env 환경변수 파일"),
    (re.compile(r"\.(pem|key|p12|pfx|jks|keystore|ppk)$", re.I), "인증서/개인키 파일"),
    (re.compile(r"^id_(rsa|dsa|ecdsa|ed25519)$", re.I), "SSH 개인키"),
    (re.compile(r"^(credentials?|secrets?)(\.[a-z]+)?$|^client_secret.*\.json$|^service[-_]?account.*\.json$", re.I), "자격증명 파일"),
    (re.compile(r"^secrets\.toml$", re.I), "Streamlit secrets"),
    (re.compile(r"^(token|.*_token)\.json$|.*api_?key.*\.txt$", re.I), "토큰/키 파일"),
    (re.compile(r"^\.(netrc|pgpass|npmrc|pypirc)$", re.I), "인증 설정 파일"),
]

# 내용에서 찾을 비밀값 패턴
SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY"), "개인키 블록"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS Access Key"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"), "Anthropic API Key"),
    (re.compile(r"\bsk-(proj-)?[A-Za-z0-9_\-]{20,}"), "OpenAI API Key"),
    (re.compile(r"\bgsk_[A-Za-z0-9]{20,}"), "Groq API Key"),
    (re.compile(r"\bhf_[A-Za-z0-9]{30,}"), "HuggingFace Token"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}"), "Google API Key"),
    (re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{40,}"), "GitHub Token"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"), "Slack Token"),
    (re.compile(r"\b[MN][A-Za-z\d]{23,25}\.[\w-]{6}\.[\w-]{27,}"), "Discord Bot Token"),
    (re.compile(r"\b(mysql|postgres(ql)?|mongodb(\+srv)?|redis)://[^\s:/@]+:[^\s@]{3,}@"), "DB 접속 비밀번호"),
    # key = "값" 형태의 하드코딩 (값 8자 이상, 따옴표로 감싼 리터럴)
    (re.compile(
        r"(?i)\b[\w.]*(api[_-]?key|secret[_-]?key|client[_-]?secret|access[_-]?token|auth[_-]?token|password|passwd|pwd)\b"
        r"\s*[:=]\s*[\"']([^\"'\s]{8,})[\"']"), "하드코딩된 키/비밀번호"),
]

# 예시 값이면 통과
PLACEHOLDER = re.compile(
    r"(?i)your[_-]|xxx|\*\*\*|<.*>|example|sample|dummy|changeme|placeholder|여기에|입력|getenv|environ|\$\{")


def run_git(args, cwd):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else ""


def to_win_path(path):
    # Git Bash 경로(/c/Users/...)는 Windows 파이썬이 못 읽는다
    m = re.match(r"^/([a-zA-Z])(/.*)?$", path)
    return f"{m.group(1).upper()}:{m.group(2) or '/'}" if m else path


def resolve_cwd(command, cwd):
    cwd = to_win_path(cwd)
    m = re.search(r"git\s+-C\s+(\"[^\"]+\"|'[^']+'|\S+)", command)
    if not m:
        m = re.search(r"(?:^|[;&|]\s*)(?:cd|Set-Location)\s+(\"[^\"]+\"|'[^']+'|[^\s;&|]+)", command)
    if not m:
        return cwd
    target = to_win_path(m.group(1).strip("\"'"))
    full = target if os.path.isabs(target) else os.path.join(cwd, target)
    return full if os.path.isdir(full) else cwd


def scan_files(names):
    hits = []
    for path in names:
        base = path.replace("\\", "/").rsplit("/", 1)[-1]
        for pat, label in DANGEROUS_FILES:
            if pat.search(base):
                hits.append(f"[파일] {path}  ({label})")
                break
    return hits


def mask(value):
    return value[:4] + "*" * 6 if len(value) > 6 else "***"


def scan_diff(diff):
    hits, current = [], "?"
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else line[4:]
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        added = line[1:]
        for pat, label in SECRET_PATTERNS:
            m = pat.search(added)
            if m and not PLACEHOLDER.search(m.group(0)):
                # key = "값" 패턴만 값 그룹을, 나머지는 매치 전체를 마스킹
                value = m.group(2) if label == "하드코딩된 키/비밀번호" else m.group(0)
                hits.append(f"[내용] {current}  ({label}: {mask(value)})")
                break
    return hits


def untracked_diff(cwd):
    """같은 명령의 git add 로 새로 추가될 파일까지 미리 검사한다."""
    names = [n for n in run_git(["ls-files", "--others", "--exclude-standard"], cwd).splitlines() if n]
    chunks = []
    for n in names:
        try:
            with open(f"{cwd}/{n}", encoding="utf-8", errors="ignore") as f:
                body = f.read(500_000)
        except OSError:
            continue
        chunks.append(f"+++ b/{n}\n" + "\n".join("+" + l for l in body.splitlines()))
    return names, "\n".join(chunks)


def check_commit(command, cwd):
    names = run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMR"], cwd).splitlines()
    diff = run_git(["diff", "--cached", "-U0"], cwd)
    if re.search(r"git\s+add\b|commit\s+(-\w*a|--all)", command):
        names += run_git(["diff", "HEAD", "--name-only", "--diff-filter=ACMR"], cwd).splitlines()
        diff += "\n" + run_git(["diff", "HEAD", "-U0"], cwd)
        new_names, new_diff = untracked_diff(cwd)
        names += new_names
        diff += "\n" + new_diff
    return scan_files(sorted(set(n for n in names if n))) + scan_diff(diff)


def check_push(cwd):
    commits = run_git(["rev-list", "HEAD", "--not", "--remotes"], cwd).split()
    names, diff = set(), []
    for c in commits:
        names.update(run_git(["show", "--name-only", "--diff-filter=ACMR", "--format=", c], cwd).split("\n"))
        diff.append(run_git(["show", "-U0", "--format=", c], cwd))
    return scan_files(sorted(n for n in names if n)) + scan_diff("\n".join(diff))


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}, ensure_ascii=False))
    sys.exit(0)


def main():
    data = json.load(sys.stdin)
    command = (data.get("tool_input") or {}).get("command", "")
    is_commit = re.search(r"\bgit\b[^;&|]*\bcommit\b", command)
    is_push = re.search(r"\bgit\b[^;&|]*\bpush\b", command)
    if not (is_commit or is_push):
        return

    try:
        cwd = resolve_cwd(command, data.get("cwd", "."))
        hits = []
        if is_commit:
            hits += check_commit(command, cwd)
        if is_push:
            hits += check_push(cwd)
    except Exception as e:  # 검사 실패 시 올리지 않는 쪽으로
        deny(f"[보안 훅] 민감 정보 검사 중 오류가 나서 차단했습니다: {e}")

    if hits:
        body = "\n".join(f"  - {h}" for h in dict.fromkeys(hits))
        deny("[보안 훅] GitHub 업로드 전에 민감 정보/위험 파일이 발견되어 차단했습니다.\n"
             f"{body}\n"
             "조치: 파일은 git rm --cached + .gitignore, 키는 os.getenv()/.env 로 옮긴 뒤 다시 시도하세요. "
             "이미 커밋됐다면 해당 커밋을 수정해야 합니다. 오탐이면 사용자에게 확인을 요청하세요.")


if __name__ == "__main__":
    main()
