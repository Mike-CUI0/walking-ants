# CLAUDE.md — Walking Ants 프로젝트

이 파일은 Claude Code가 세션 시작 시 자동으로 읽는 지침 파일이다.

---

## GitHub 정보
- **레포**: https://github.com/Mike-CUI0/walking-ants
- **토큰 경로**: `C:\Users\kkich\Desktop\mikedb001\.env` → `git_key` 값 사용
- **Remote URL 형식**: `https://<git_key>@github.com/Mike-CUI0/walking-ants.git`

---

## 프로그램 버전 현황

| 버전   | 파일             | 태그    | 설명                                      |
|--------|------------------|---------|-------------------------------------------|
| v1.0.0 | mike_ant.py      | v1.0.0  | M자 개미가 화면을 걸어다님                |
| v2.0.0 | word_physics.py  | v2.0.0  | 글자 공이 중력/탄성으로 튀어다님          |
| v3.0.0 | flower_word.py   | v3.0.0  | 꽃잎이 날아와 꽃 모양으로 조립           |
| v4.0.0 | sakura_words.py  | v4.0.0  | 벚꽃이 떨어져 바닥에 단어 모양으로 쌓임  |

**다음 신규 프로그램은 v5.0.0부터 시작.**

---

## 새 프로그램 추가 / 수정 시 규칙

1. **버전 번호**: 새 프로그램마다 major 버전 +1 (v5.0.0, v6.0.0 …)
2. **기존 프로그램 수정**: patch 버전 +1 (예: word_physics 수정 → v2.0.1)
3. **빌드**: 항상 PyInstaller로 exe 생성
   ```
   python -m PyInstaller --onefile --noconsole --name "<name>" <name>.py
   ```
4. **커밋 메시지 형식**: `v<version>: <filename> - <한 줄 설명>`
5. **태그**: 커밋 직후 태그 생성
   ```
   git tag v<version> -m "<filename> v<version>"
   ```
6. **푸쉬**: 커밋 + 태그 모두 push
   ```
   git push origin master
   git push origin --tags
   ```

---

## 공통 기술 규칙

- **투명 오버레이**: `overrideredirect(True)`, `-topmost True`, `-transparentcolor '#FF00FF'`
- **클릭**: 단클릭=다음 단어, 더블클릭(300ms)=파일재선택, 우클릭=종료
- **자동 전환**: 15초 (`AUTO_S = 15`)
- **파일 입력**: txt 파일, 줄바꿈 기준 단어 분리
- **중국어 우선 정렬**: 한자+한글 혼합 행은 한자→숫자→한글 순서로 재정렬
- **tkinter 색상**: 반드시 6자리 hex(`#RRGGBB`), 8자리 불가
- **실행파일**: `dist/` 폴더에 생성됨
