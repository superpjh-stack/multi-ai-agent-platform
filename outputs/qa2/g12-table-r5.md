| # | 키 | 종류 | 원천 근거 (spec v0.3 §4.2 입력값) | 기대 v0.3 글자 | (참고) v0.2 글자 | 대시보드 | 일치 |
|---|---|---|---|---|---|---|---|
| 1 | `S:fa752590-2b31-4e52-8518-a10dfe99f988` | SESSION | S1 status=busy · pid 살아 있음 · 마지막 기록 2026-10-21T04:15:47Z (82초 전) · 마지막 줄 assistant:text · 마지막 tool_use ScheduleWakeup · ScheduleWakeup 2026-10-21T04:45:34Z(미래) · 자식 13 (미종료 2) | RUNNING R-02a | RUNNING R-02a | RUNNING R-02a | O |
| 2 | `A:a328106ffaca540ab` | SUBAGENT | 세션 fa752590 S1 busy · 마지막 기록 10-21T04:17:09 (0초 전) · 마지막 활동 10-21T04:17:09 · 반환 없음 | RUNNING R-09 | RUNNING R-09 | RUNNING R-09 | O |
| 3 | `A:a4a00befc95de6a68` | SUBAGENT | 세션 fa752590 S1 busy · 마지막 기록 10-21T04:16:31 (38초 전) · 마지막 활동 10-21T04:16:25 · 반환 없음 | RUNNING R-09 | RUNNING R-09 | RUNNING R-09 | O |
| 4 | `S:fc3908a3-be19-4ec8-bbec-53711cb56817` | SESSION | S1 status=idle · pid 살아 있음 · 마지막 기록 2026-10-21T03:14:48Z (3741초 전) · 마지막 줄 user:message · 마지막 tool_use Bash · 자식 3 (미종료 0) | WAITING_INPUT R-05 | WAITING_INPUT R-05 | WAITING_INPUT R-05 | O |
| 5 | `S:dbd09a2a-f7cb-4121-9a92-cf8d0352ad28` | SESSION | S1 없음 · 마지막 기록 2026-10-14T17:55:19Z (555710초 전) · 마지막 줄 assistant:tool_use · 마지막 tool_use AskUserQuestion · 결과 없는 tool_use ['AskUserQuestion'] · ScheduleWakeup 2026-10-14T17:34:00Z(지남) · 자식 64 (미종료 0) | STALE R-06 | STALE R-06 | STALE R-06 | O |
| 6 | `A:acfbcbeabcb648847` | SUBAGENT | 세션 dbd09a2a S1 없음 (프로세스 없음) · 마지막 기록 10-12T17:27:26 (730183초 전) · 마지막 활동 10-12T17:26:57 · 반환 없음 | STALE R-11 | STALE R-11 | STALE R-11 | O |
| 7 | `A:a24b6a447d6e7fb9e` | SUBAGENT | 세션 67760b59 S1 없음 (프로세스 없음) · 마지막 기록 10-08T22:31:30 (1057539초 전) · 마지막 활동 10-08T22:31:29 · 반환 notification:failed@10-08T22:31:30 | FAILED R-08 | FAILED R-08 | FAILED R-08 | O |
| 8 | `A:a770b69985c666cbf` | SUBAGENT | 세션 fa752590 S1 busy · 마지막 기록 10-21T04:13:30 (219초 전) · 마지막 활동 10-21T04:13:29 · 반환 handback@10-21T04:13:29 | DONE R-08 | DONE R-08 | DONE R-08 | O |
| 9 | `A:a0167300959299bf6` | SUBAGENT | 세션 fa752590 S1 busy · 마지막 기록 10-21T03:51:13 (1556초 전) · 마지막 활동 10-21T03:51:12 · 반환 notification:completed@10-21T03:43:27, handback@10-21T03:51:12 | DONE R-08 | DONE R-08 | DONE R-08 | O |
| 10 | `S:493d1a8d-6430-4776-95f1-f6b085637edd` | SESSION | S1 없음 · 마지막 기록 2026-10-17T16:37:41Z (301168초 전) · 마지막 줄 assistant:text · 마지막 tool_use Bash · 자식 0 (미종료 0) | DONE R-07 | DONE R-07 | DONE R-07 | O |
