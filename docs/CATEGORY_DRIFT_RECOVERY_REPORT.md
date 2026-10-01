# Category drift + empty-eligible recovery hotfix

2026-10-01 · `hotfix/live-search-oos-recovery` · tiếp tục WIP OOS, không reset/restore/commit/merge/tag/push/Live.

## A. Nguồn contamination chính xác

Session `ab719401-e035-4c5b-add6-5ce11a01cdad`, requirement điện thoại / FLEXIBLE_TARGET 10.000.000 VND / camera tốt / pin lâu. Snapshot ghi 40.568,874 ms, 20 product attempts, 23 page attempts, hai scoring candidates và không có eligible/recommendation. Cả hai candidates là tablet và đồng thời có stock OOS; category là hard-filter rejection đầu tiên. Filter đang đúng.

Đường lan truyền được đối chiếu từ raw payload, page proof và round diagnostics:

1. Query `"Oppo Find X8s Plus" mua Việt Nam VND` trả về `https://www.duchuymobile.com/oppo-find-x8s-plus`.
2. `raw_text` của source này có nội dung OPPO, rồi danh sách iPad và `Samsung Galaxy Tab S10 Ultra 5G (12GB | 256GB) Chính Hãng`. Title là OPPO; proof của trang này có `discovery=[]`. Vì vậy nguồn khởi đầu là **snippet/content search result**, không phải listing child hay `page_validation.discovery` của OPPO.
3. `model_hints()` gọi `observed_models(title + content)` trên toàn snippet, nhận `Samsung Galaxy Tab S10 Ultra 5G` nhưng không kiểm tra category. Đó là đường vào query round 4 `"Samsung Galaxy Tab S10 Ultra 5G" giá Việt Nam VND`.
4. Round 5 tiếp tục `site:cuahangsamsung.vn "Samsung Galaxy Tab S10 Ultra 5G" giá bán Việt Nam VND`. Source `https://cuahangsamsung.vn/shop/product/samsung-galaxy-tab-s9-fe-wifi-6gb-128gb` xuất hiện trong kết quả. Proof có heading và structured discovery `Samsung Samsung Galaxy Tab S9 FE WIFI 6GB 128GB`, dù snippet của nó vẫn nhắc S10/phụ kiện.
5. Nhánh discovery làm sạch brand/name thành `Samsung Galaxy Tab S9 FE WIFI 6GB 128GB`, đánh rank bằng `SUGGESTED_RANGE`, không có category gate. Round 7 phát sinh exact-model S9; CellphoneS trả về Tab S9 FE 5G. Đây là lan truyền thứ hai từ **merchant search result → page discovery → model hint**.

Không có historical HTML/HAR để chứng nhận vị trí DOM chính xác của khối sản phẩm khác. Bằng chứng xác định được là nội dung snippet đã persist và structured page proof; không suy diễn đó là một particular DOM widget. Không có bằng chứng cần viện dẫn listing-child path để giải thích hai hint này.

## B. Category-safe hints

- Tái sử dụng `infer_product_category`, normalized text và `category_matches`. Thêm family evidence ở lớp retrieval cho Galaxy Tab/Redmi Pad/Lenovo Tab, Galaxy phone/Redmi Note và AirPods/Galaxy Buds. Không chỉ chặn literal Samsung Tab; test gồm tablet, iPad, laptop, tai nghe, TV và category alias.
- Áp dụng cho từng model từ title/snippet, từng discovery item, main verified proof và child link. Evidence của một model không được áp sang mọi related model.
- Giữ category conflict theo lookup key khi tách tên làm mất từ loại sản phẩm: ví dụ `Máy tính bảng Dell Z12` → `Dell Z12`. Một mention lặp lại trong snippet không thể bỏ qua category đã biết.
- Unknown category vẫn được discovery; không tự gán category request vào product. Galaxy S25 được tìm cho điện thoại; Galaxy Tab vẫn được tìm khi request là tablet.
- Tên family điện thoại có feature “camera” không tự biến thành máy ảnh. Không sửa product normalizer/hard filter/page validator.

## C. Query behavior

Hint conflicting bị loại trước exact-model/alternative-model/merchant queries. `model_query()` có guard cuối: trả về category commercial query theo requested category nếu nhận hint xung đột. Không tiếp tục chuỗi Tab S10 → Tab S9 cho phone request. Related phone model và child cùng category vẫn được giữ.

## D. Empty-eligible trigger

`recovery_needed()` trước đó đã dùng `not any(ready(...))`; `ready()` gọi eligibility/hard filters. Vì vậy all-category-rejected cũng đã thỏa điều kiện boolean, không phải bị bỏ quên khỏi trigger.

Trong session này, `product_attempts=20` chạm hard cap nên recovery không được request thêm. Reserve cũ chỉ giữ page slots; với `page_attempts=23/24`, còn page slot nhưng không còn product slot. Thêm nữa, pending `https://www.duchuymobile.com/nothing-phone-4a` không qua bộ nhận diện model brand cũ và URL không có prefix `/products/`, nên bị loại khỏi recovery opportunities.

Sau sửa, low-value work phải chừa cả page slots lẫn product slots. Direct URL với loại sản phẩm rõ ràng và identity token có số khớp title/URL có thể vào queue dù brand chưa được model parser nhận diện. Đây chỉ là quyền được xác minh; không tạo price, stock hoặc verified offer từ snippet.

Unit tests và API tests xác nhận all-category/availability/budget/brand/exclusion rejected + pending phone vẫn recovery. Wrong-category URL không được dùng reserve. Đủ phone target thì không recovery thừa.

## E. Bounds và safety

- Recovery tối đa **2 probes/toàn lượt, 1/domain**.
- Timeout `min(2s, page_budget, domain_budget, remaining_global_time)`; không tăng hard global deadline.
- Max product attempts vẫn **20**, max page requests vẫn **24** theo defaults. Không vượt cap để “cố ra kết quả”.
- Reserve giữ capacity khỏi low-value work; không bảo đảm còn capacity nếu nhiều direct-looking URLs thực sự đã dùng hết hard cap.
- Ưu tiên category evidence phù hợp → near-budget rank → unseen model → alternate merchant; tie-break deterministic.
- Không retry URL đã inspect hoặc wrong-category URL; giữ failure circuit, semaphores và resolver lifetime của OOS hotfix.
- Category/stock/budget filters, score weights 25/30/20/10/5/10, image resolver và snapshot semantics không đổi.
- Retrieval cache version **9 → 10**, test thêm v9 để cached empty/drift result không che thay đổi. Không backfill hoặc sửa DB schema/production data.

## F. Offline replay

[Fixture](../backend/tests/fixtures/live_category_ab719401.json) được xuất bằng SQLite URI `mode=ro` và `PRAGMA query_only=ON`; chỉ chọn requirement, query/source/proof/diagnostics, không export API keys/user identity.

[Script](../backend/scripts/replay_category_recovery.py) chạy actual query policy với map responses đã lưu, socket network bị chặn. `before` được chạy và lưu **trước khi sửa source follow-up**, có SHA256 source; [JSON before/after](CATEGORY_RECOVERY_REPLAY.json) giữ kết quả đó. `after` có thể chạy lại từ backend:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 scripts/replay_category_recovery.py after
```

| Metric | Before WIP OOS | After follow-up |
| --- | ---: | ---: |
| Product attempts | 20 | 12 |
| Page attempts | 23 | 15 |
| Galaxy Tab exact/scoped queries | 3 | 0 |
| Eligible | 0 | 0 |
| Recovery attempts trong policy replay | 0 | 0 |
| Nothing Phone 4a được inspect trong normal flow | Không | Có |
| Stop reason | candidate_budget | no_progress |

Recovery counter của **policy replay** vẫn 0 vì normal flow đã có capacity để thử Nothing Phone 4a; không cần reserved retry. Bài replay độc lập với hai historical rejected candidates + known pending Nothing Phone 4a xác nhận **0 → 1 reserved probe**. Không chèn URL vào response của query chưa từng chạy.

After policy có bốn query chưa có archived response; replay trả “không có rows lưu” và ghi `missing_queries`, không khẳng định Live trả rỗng. Hai URL được thử chưa có response lịch sử là homepage Đức Huy và Nothing Phone 4a. Chúng giữ unverified; không fabricate recommendation. Thời gian inspect được mô phỏng bằng serial recorded costs; thời gian unknown không được coi là network latency 0. Không khẳng định latency Live giảm.

## G–I. Backend validation

- Tests mới tái hiện lỗi trước sửa: 18 fail / 4 pass; thêm ba case category evidence và một feature-category case cũng được quan sát fail rồi sửa.
- Targeted cuối: **56 passed / 0 failed / 0 errors / 2 warnings**, 15.48s (category + OOS unit/API).
- Regression mở rộng cuối: **342 passed / 0 failed / 0 errors / 2 warnings**, 39.36s. Gồm progressive retrieval, model hints, category evidence, OOS/direct recovery, cache, budget/scoring, image và search integration.
- Full backend `python -B -X utf8 -m pytest`: **829 collected / 829 passed / 0 failed / 0 errors / 2 warnings**, 85.74s, exit 0.
- Hai warnings: Starlette/httpx deprecation và `PytestCacheWarning` do WinError 5 khi ghi `.pytest_cache`. Không nâng dependency hoặc sửa quyền cache ngoài phạm vi.
- Các nhóm targeted/regression nằm trong full suite, không cộng số tests giữa các lượt. Tăng 31 tests so với 798: 27 category unit/replay cases, 3 API category-rejection variants, 1 legacy-v9 cache case.
- Tests dùng DB/schema tạm từ `tests/conftest.py`, provider/HTML mock. Không mở app engine với production DB khi xuất fixture.

## J. Frontend

Không đổi UI, routes hoặc API response schema. Search/GET contract được kiểm tra bằng backend integration. Không chạy lại frontend trong follow-up này; tham chiếu lượt validation trước: **41/41 npm test**, lint/build PASS, **15/15 E2E exit 0**. Đây không phải kết quả mới của follow-up.

`frontend/next-env.d.ts` đã modified khi bắt đầu follow-up (generated `.next/dev/types`); giữ nguyên, không chỉnh/restore/stage. Hai stash cũ không apply/drop.

## K. Files và diff check

Follow-up sửa: `backend/app/services/search/retrieval_relevance.py`, `progressive_retrieval.py`, `cached_search_service.py`, `backend/tests/integration/test_candidate_discovery_api.py`, `test_oos_recovery_api.py`.

Tạo: `backend/tests/unit/test_category_recovery.py`, `backend/tests/fixtures/live_category_ab719401.json`, `backend/scripts/replay_category_recovery.py`, `docs/CATEGORY_RECOVERY_REPLAY.json`, báo cáo này. Các thay đổi OOS trước đó được giữ nguyên.

Final `git diff --check`: **PASS**, exit 0. Các untracked text files không có trailing whitespace; JSON parse PASS. Git có LF/CRLF notices, không có whitespace error. Không stage/commit/merge/tag/push. HEAD/main/v1.2.1 vẫn ở `044f52d730930943e6ce54d54767f93cdc3fbc69`; hai stash giữ nguyên.

## L. Remaining limitations

- Không Live API, chưa có Live acceptance mới. Hotfix không bảo đảm recommendation.
- Unknown family/category không bị cấm tìm; validator và hard filter cuối vẫn bắt buộc. Không thể nhận diện mọi taxonomy/family bằng danh sách hữu hạn.
- Snippet lẫn navigation/related text vẫn có thể chứa các same-category hints chất lượng thấp; không mở rộng thành parser/refactor toàn bộ.
- Replay không có response cho query mới hoặc historical HTML của URL trước đây chưa fetch; không dự đoán stock/price hiện tại.

## Final-report-only verification — 2026-10-01

Đã chạy lại `git branch --show-current`, `git status --short`, `git diff --stat`, `git diff --check`, `git stash list` và kiểm tra staged diff. Branch đúng `hotfix/live-search-oos-recovery`, diff check exit 0, không có staged files, hai stash vẫn nguyên vẹn. `next-env.d.ts` chỉ có generated imports từ `.next/types` sang `.next/dev/types`, giống WIP đã ghi nhận từ đầu follow-up; không sửa/restore/stage file này. Lượt chốt báo cáo không thay implementation và không chạy lại validation suites; các số validation phía trên là kết quả đã hoàn tất trước đó.

**CATEGORY DRIFT + RECOVERY HOTFIX = PASS**

PASS cho implementation và validation offline; chưa tuyên bố Live acceptance hoặc bảo đảm có recommendation.
