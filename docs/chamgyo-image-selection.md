# chamgyo individual account image selection

## 완료된 작업

### bgl.js 수정 (chamgyo main, commit a48cf558)
- `window.__imgWatch` 노출: IIFE 내부 `__imgWatch` 를 `window.__imgWatch = __imgWatch` 로 외부에 공개
- `window.__ch` 오버라이드: `__imgWatch` 에서 채널 결정 시 URL `?ch=` 보다 `window.__ch` 를 우선
  - 관리자 write.php 에서 마스터가 채널 드롭다운 변경 시 `window.__imgWatch()` 호출이 실제로 동작
  - 보드 URL 에 `?ch=` 없어도 write.php 세션 채널 기준으로 이미지 미리보기 갱신

### write_upload.php (기존 완성)
- 비마스터: `images/ch/<본인id>/` 에만 저장
- 마스터 + 특정 채널: `images/ch/<ch>/` 에 저장
- 마스터 + `__all__`: 공용 `images/` 에 저장 (모든 채널 폴백)

### bgl.js 채널별 이미지 로직 (기존 완성)
- `data/img_ver.json` (공용) + `data/img_ver_<ch>.json` (채널) 5초 폴링
- 채널 이미지 있으면 `images/ch/<ch>/<fn>`, 없으면 `images/<fn>` 폴백
