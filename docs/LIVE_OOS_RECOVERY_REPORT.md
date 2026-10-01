# Live OOS recovery hotfix

Ngày validation: 2026-09-30; hoàn tất E2E và kiểm tra WIP ngày 2026-10-01. Branch: `hotfix/live-search-oos-recovery`, base `v1.2.1` / `044f52d730930943e6ce54d54767f93cdc3fbc69`.

Không Live API, commit, tag, push hoặc ghi database production. Session được đọc bằng SQLite `mode=ro` và `PRAGMA query_only=ON`. Hai stash generated `next-env.d.ts` được giữ nguyên: stash trước release và stash riêng trước hotfix. Không reset/restore/clean.

## A. Root cause có bằng chứng

Session `05479307-6d2d-4c17-b445-8719d935aa3c`, nhu cầu “Tôi cần điện thoại khoảng 10 triệu, camera tốt, pin lâu”, lưu 49 raw sources, 10 provider calls, 8 rounds, 24 page attempts, 19 product attempts và 5 discovery attempts. Tổng thời gian lưu: 48,483.431 ms. Stop reason thật là `page_budget`; `no_progress_rounds` vẫn bằng 0 ở cuối mỗi round.

CellphoneS có ba lần kiểm tra trang trước khi bỏ qua A56:

| URL | Inspection ms | Kết quả lịch sử |
| --- | ---: | --- |
| `/oppo-reno-8t.html` | 1661.178 | Verified, OOS |
| `/oppo-reno8-z.html` | 3458.520 | Verified, OOS |
| `/vivo-v50-lite-5g-cu-da-kich-hoat.html` | 1088.690 | Timeout, unverified |

Domain ledger ghi 6208.989 ms trên budget 6000 ms, một failure và một skip. Sai lệch nhỏ so với timeout là overhead; không phải budget mới. A56 ở round cuối bị `resource_budget`, `page_requested=false`. `skip_page()` đưa URL vào `sources`, còn `verify()` trả lại source đã có; URL không được xét lại bằng một cơ hội recovery riêng.

**Không có bằng chứng bài viết CellphoneS làm cạn domain budget này.** Các URL `/sforum/` đã được giữ metadata, không fetch. Cơ chế lãng phí ở global budget là các URL hãng như `/newsroom/press/…` và `/events` chưa được `source_plan()` nhận diện; bốn press pages và một event page của OPPO đã được fetch nhưng không tạo offer.

49 raw sources không đồng nghĩa 49 HTTP requests. Trong 24 requests, chỉ hai có valid offer; 22 còn lại bao gồm bài viết, listing, thiếu proof và timeout, không phải 22 bài viết.

## B. Filter hiện tại đúng

OPPO Reno8 T 5G và OPPO Reno8 Z đều có availability `out_of_stock`, nên bị loại ở `availability`. Hotfix không sửa hard filter và không cho OOS đáp ứng target.

Vivo V50 Lite tại Thegioididong có `identity_match=true` nhưng thiếu một price/commercial proof rõ ràng cùng nguồn. Identity đúng không đủ chứng nhận offer; trường hợp này tiếp tục unverified.

## C. Vì sao bị thiếu capacity

Normal domain ledger dùng chung thời gian hoạt động/failure cho các trang thực sự được fetch, không phân biệt bài viết, listing và direct product. Nguồn đã nhận diện metadata thì không dùng HTTP budget. Trang chỉ biết là article sau khi tải được trả lại product slot, nhưng global HTTP attempt và thời gian domain vẫn đã tiêu tốn.

URL ưu tiên direct và đa dạng merchant/model đã tồn tại trong từng round. A56 chỉ được phát hiện ở round 8; ưu tiên trong queue không thể lấy lại domain budget đã dùng ở các round trước. Những URL press/event bị nhận diện nhầm cũng có model/digit nên có thể nhận priority cao. Không phải mọi direct URL đều đứng sau mọi bài viết.

Trước hotfix không có capacity riêng cho direct URL chưa fetch khi tất cả offer đã verified là OOS. Alternate-merchant/model queries vẫn chạy, nhưng URL mới có thể bị budget skip và không có bước xử lý lại trước khi kết thúc.

## D. Recovery trước/sau

- Trước: domain budget hết → skip/cache source unverified; hết query/no-progress/global cap → kết thúc, không có lượt riêng cho URL đã biết nhưng chưa được request.
- Sau: khi chưa có offer đạt `ready()` (empty, toàn OOS hoặc chỉ fallback yếu), xem xét direct opportunities sau mỗi query round và trước khi kết thúc query loop.
- Chỉ chọn URL có product-path/model evidence; đây là dấu hiệu để xếp lịch, **không** chứng nhận trang bán. URL phải đi qua resolver/page validator hiện tại.
- Ưu tiên direct URL có near-budget hint và model chưa gặp; tiếp theo merchant khác; rồi các tiêu chí budget/model/merchant hiện có, URL làm tie-break deterministic. Price-topic/model hints không được ghi thành offer price.
- Khi có near-budget model hint chưa search trong trạng thái không có offer tốt, commercial exact-model query được ưu tiên trong query budget hiện có.
- Không retry URL đã từng được HTTP inspect. Chỉ source `resource_budget` chưa request hoặc direct URL còn pending được xét. Trang đã fetch nhưng thiếu price như Vivo không được nâng cấp bằng snippet suy đoán.
- Các path newsroom/press/event được giữ metadata ngay từ đầu. Article/review/video và generic brand/store page không được dùng reserved direct slot.

## E. Stop conditions và diagnostics

`enough()`/`ready()` vẫn yêu cầu offer eligible và chất lượng theo logic cũ; OOS không đạt target. Unknown stock được giữ nguyên unknown, không đổi thành in-stock. Recovery dừng khi đủ chất lượng, hết direct opportunities hoặc chạm các giới hạn.

Các hard stop `time_budget`, `candidate_budget`, `page_budget` vẫn ưu tiên. Sau recovery chưa tạo được offer tốt, `recovery_opportunities_exhausted` chỉ ra không còn URL phù hợp chưa inspect; `recovery_budget` chỉ ra còn URL nhưng recovery allowance không cho tiếp tục. Những stop khác của luồng hiện tại được giữ nếu không có recovery.

Diagnostics thêm `direct_recovery`: limit, timeout, attempted URLs và thời gian/attempts từng domain. Dữ liệu này theo snapshot execution và được integration test kiểm tra qua GET. Không đổi route hoặc typed response/database schema; chỉ thêm metadata vào diagnostics dictionary hiện có. Không backfill session cũ.

## F. Giới hạn tài nguyên

| Giới hạn | Sau hotfix |
| --- | --- |
| Global deadline | Không đổi; vẫn dùng thời gian còn lại của retrieval |
| Max queries | Không đổi; recovery URL không gọi provider mới |
| Max page requests | Không đổi, default 24 |
| Max product attempts | Không đổi, default 20 |
| Reserve page slots | Tối đa 2 từ tổng capacity cũ; low-value work không được dùng hai slots cuối khi cần recovery |
| Recovery probes | Tối đa 2 toàn lượt, tối đa 1/domain |
| Timeout/probe | `min(2s, page_budget, domain_budget, remaining_global_time)` |
| Domain normal budget | Không đổi, default 6s |
| Domain recovery budget | Riêng, tối đa thêm 2s cho một direct URL chưa request; vẫn nằm trong global deadline/caps |
| Failure circuit | Hai direct-fetch failures liên tiếp chặn reserve; low-value failures không tự tước cơ hội direct probe |
| Concurrency | Giữ page/domain semaphores; recovery tuần tự, không tạo task không giới hạn |

Đây là reallocation global attempts cộng một domain allowance nhỏ có giới hạn, **không** phải khẳng định domain cap tuyệt đối vẫn chỉ 6s. Tổng wall time có thể tăng tối đa theo hai probe mới và overhead, nhưng không mở rộng hard global deadline. Không tăng tất cả config limits.

Cache scope đổi retrieval version **8 → 9** để cache kết quả cũ không che hotfix; TTL, budget semantics, snapshot behavior không đổi. Regression thêm trường hợp cache v8.

## G. Offline replay

Artifacts: [fixture](../backend/tests/fixtures/live_oos_05479307.json), [script](../backend/scripts/replay_oos_recovery.py), [JSON kết quả](LIVE_OOS_RECOVERY_REPLAY.json).

Chạy `backend/.venv/Scripts/python.exe -B -X utf8 scripts/replay_oos_recovery.py` từ backend. Baseline đọc source từ `git show v1.2.1`, không checkout. Replay giữ archived query rounds/snippets/proofs; dùng recorded inspection costs trên virtual serial clock. Không tái dựng parallel wall time, HTML, kết quả query mới hoặc thời gian Live.

| Metric | Before v1.2.1 replay | After replay |
| --- | ---: | ---: |
| Provider rounds / calls | 8 / 10 | 8 / 10 |
| Page attempts | 24 | 20 |
| Product-attempt counter | 19 | 15 |
| Attempts không có valid offer lịch sử | 22 | 18 |
| Newsroom/event attempts | 5 | 0 |
| OOS verified | 2 | 2 |
| Eligible verified | 0 | 0 |
| Resource-budget rejections | 1 | 0 |
| Stop reason | page_budget | recovery_opportunities_exhausted |

A56 (`https://cellphones.com.vn/dien-thoai-samsung-galaxy-a56.html`) nhận một reserved attempt sau hotfix. Response gốc không tồn tại vì URL chưa từng được fetch; replay ghi `offline_unrecorded_response`, giữ **unverified**, không tạo price/image/merchant/recommendation. Probe cost của URL chưa capture là không biết; giá trị 0 của virtual replay không phải phép đo network.

Test synthetic qua pipeline thật xác nhận khi direct response mới có valid in-stock offer thì 0 → 1 recommendation. Đó là test mock, không phải Live acceptance của session này.

## H. Targeted tests

- Regression rộng retrieval/relevance/cache/image: **298 PASS, 0 FAIL, 2 warnings**, 40.31s.
- Bộ hotfix hoàn chỉnh (unit + API, gồm archived replay và các nhánh stock): **26 PASS, 0 FAIL, 2 warnings**, 10.77s. Hai nhóm có overlap, không cộng thành số tests độc lập.
- Các nhánh được cover: hai OOS + pending direct; low-value domain budget; direct failure circuit; không còn opportunities; hard deadline/cancellation; hard global caps; target đã đạt; OOS không tính target; article/review/video/generic page không dùng reserve; deterministic order; unknown stock; fallback yếu; không retry URL đã request; GET diagnostics; không ảnh vẫn giữ recommendation; scoring weights unchanged.
- Một assertion cũ yêu cầu editorial dùng đủ 24 slots đã được đổi thành **chính xác 22 editorial attempts + 2 reserved slots chưa dùng**, giữ total cap 24 và query cap 12. Không xóa test hoặc nới validator để qua test.

## I–K. Final validation

- Backend: **798 collected / 798 PASS / 0 FAIL / 0 errors / 2 warnings**, 87.51s. Database/schema do fixture tạo trên DB tạm; không dùng production DB.
- Hai backend warnings cũ: Starlette/httpx deprecation và quyền ghi pytest cache.
- Frontend `npm test`: **41 PASS / 0 FAIL / 0 skipped**; có Node module-type notices cũ.
- `npm run lint`: **PASS**, 0 errors/warnings.
- `npm run build`: **PASS**.
- E2E chạy lại ngày 2026-10-01: **15 PASS, 0 FAIL, exit 0**, 2.6m, Demo backend/DB tạm và fixtures; không gọi Live. Sau khi cả 15 cases đã báo `ok`, runner chờ teardown trên Windows; đóng riêng hai test-server processes của lượt chạy này để hoàn tất. Có notices `NO_COLOR`/`FORCE_COLOR`; không sửa launcher/source.
- `git diff --check`: **PASS**. Không stage file, không đưa generated `next-env.d.ts` vào hotfix.
- Sau teardown: **0 test listeners** trên `13000`/`18000`, **0 recorded E2E processes** còn chạy; Playwright `.last-run.json` ghi `passed`, `failedTests=[]`.

Lượt tiếp tục chỉ hoàn tất validation và báo cáo; không sửa source/tests. Backend full đã có kết quả cuối rõ ràng ở lượt trước như trên. Frontend không có diff, nên giữ kết quả `npm test`/lint/build đã PASS, không chạy lại riêng ba lệnh đó. E2E tự build bundle local theo cấu hình hiện tại.

Frontend regression được chạy vì kết quả search/GET diagnostics thay đổi, dù không có source UI/schema edit.

## Files thay đổi

- `backend/app/services/search/progressive_retrieval.py`
- `backend/app/services/search/retrieval_diagnostics.py`
- `backend/app/services/search/cached_search_service.py`
- `backend/tests/unit/test_candidate_discovery.py`
- `backend/tests/integration/test_candidate_discovery_api.py`
- `backend/tests/unit/test_oos_recovery.py` (mới)
- `backend/tests/integration/test_oos_recovery_api.py` (mới)
- `backend/tests/fixtures/live_oos_05479307.json` (mới)
- `backend/scripts/replay_oos_recovery.py` (mới)
- `docs/LIVE_OOS_RECOVERY_REPLAY.json` (mới)
- `docs/LIVE_OOS_RECOVERY_REPORT.md` (mới)

## L. Giới hạn còn lại

- Không chạy Live; không khẳng định A56 hiện có giá/stock/ảnh hợp lệ hoặc Live latency giảm.
- Replay chỉ bảo đảm cơ hội xác minh được cấp; khi provider/page thiếu proof, kết quả vẫn có thể bằng 0.
- Model hints như `Apple A13 Bionic` vẫn có thể gây query chất lượng thấp; hotfix này không mở rộng thành đợt sửa model parser.
- Không đo lại toàn bộ HTML hay response của các query chưa từng chạy. Generic URL classification có thể chưa nhận diện mọi editorial path; page validation vẫn là ranh giới bắt buộc.
- Hai probe reserve là hữu hạn: không bảo đảm mọi domain hoặc model mới đều được thử.

Hotfix ngăn direct product URL tiềm năng chưa được xác minh mất cơ hội chỉ vì normal retrieval budget khi tập verified rỗng/OOS/yếu, trong phạm vi reserve và hard caps. Không bảo đảm sẽ có recommendation; kết quả Live vẫn phụ thuộc response và proof thật.

Không commit, merge, tag, push hoặc Live API. `main` và `v1.2.1` vẫn ở base release; hai stash giữ nguyên, không apply/drop.

**LIVE OOS RECOVERY HOTFIX = PASS**
