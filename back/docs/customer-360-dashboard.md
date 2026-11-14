# Customer 360 Profile và Customer Portfolio & Spend Ranking

## Mục tiêu

Hai trang trả lời hai lớp câu hỏi khác nhau nhưng dùng chung một customer snapshot:

1. **Customer Portfolio & Spend Ranking**: cơ cấu toàn bộ khách hàng, tỷ lệ khách hàng và tỷ lệ chi tiêu theo hạng, hành vi sử dụng dịch vụ, khách giá trị cao nhưng gắn kết thấp và danh sách ưu tiên hành động.
2. **Customer 360 Profile**: hồ sơ hợp nhất của một khách hàng, giá trị, hành vi, dịch vụ đã dùng, sở thích, hoạt động gần đây và hành động tiếp theo có thể giải thích.

Không còn trang Customer Journey. `customer_activity.csv` chỉ là bảng hoạt động chi tiết để hỗ trợ profile và drill-through theo khách hàng; không suy diễn causal journey hay marketing attribution.

## Dữ liệu demo và script tái sử dụng

Script chuyên trách là `scripts/build_customer_dashboard_data.py`. Toàn bộ tham số chỉnh tay nằm ở khối `MANUAL CONFIGURATION` trên đầu file, gồm seed, thời gian bắt đầu, số sự kiện, số khách hàng, cửa sổ hành vi, số dòng hoạt động gần đây, ngưỡng xếp hạng và bảng màu.

Chạy riêng phần customer:

```powershell
python scripts/build_customer_dashboard_data.py --output-dir artifacts/powerbi_demo --skip-contract-validation
```

Chạy toàn bộ bộ demo đồng bộ:

```powershell
python scripts/build_portfolio_demo_data.py --output-dir artifacts/powerbi_demo --skip-contract-validation
```

Script tổng gọi lại script customer nên cùng seed, event stream và customer pool. `customer_journey.csv` cũ được xóa tự động nếu còn tồn tại.

| File | Grain | Dòng mặc định | Vai trò |
|---|---|---:|---|
| `customer_360.csv` | 1 dòng/customer | 200 | Snapshot hợp nhất, chi tiêu, hạng và hành vi |
| `customer_activity.csv` | 1 dòng/hoạt động gần đây | khoảng 1.130 | Hoạt động chi tiết cho profile |
| `customer_affinity.csv` | customer × 4 affinity | 800 | Sở thích nội dung |
| `customer_rank_share.csv` | metric × hạng | 10 | Tỷ lệ khách hàng và tỷ lệ chi tiêu theo hạng |
| `customer_dashboard_manifest.json` | manifest | 1 | Seed, cửa sổ và quy tắc hạng |

## Quy tắc hạng thành viên

Hạng chỉ dựa trên `net_spend_12m` sau hoàn tiền. Hành vi không làm tăng hoặc giảm hạng.

| Hạng | Chi tiêu ròng 12 tháng | Màu |
|---|---:|---|
| Diamond | từ 10.000.000 VND | `#20D9E8` |
| Platinum | từ 5.000.000 VND | `#D9E2EC` |
| Gold | từ 2.000.000 VND | `#F5C451` |
| Silver | từ 500.000 VND | `#94A3B8` |
| Basic | dưới 500.000 VND | `#4B5563` |

`net_spend_12m = ticket_spend_12m + subscription_spend_12m + content_spend_12m - refund_value_12m`.

Vì event sample chỉ bao phủ khoảng 100 ngày, script bổ sung synthetic historical spend cho phần còn lại của cửa sổ 12 tháng. Khoản này deterministic, bị giới hạn trần và luôn subordinate với các amounts quan sát được; không phải dữ liệu tài chính thật.

## Trang Customer Portfolio & Spend Ranking

- Bộ lọc: hạng thành viên, phân khúc hành vi, gói subscription và khu vực.
- KPI: số khách hàng, tổng chi tiêu 12 tháng, tỷ lệ khách Gold+, tỷ lệ chi tiêu Gold+, khách đa dịch vụ và khách giá trị cao/gắn kết thấp.
- Biểu đồ: tỷ lệ khách hàng so với tỷ lệ chi tiêu theo hạng, Spend × Engagement, hành vi theo hạng, service mix và segment × rank.
- Bảng ưu tiên: customer, hạng, chi tiêu, engagement, rủi ro hành vi và next-best-action.

`customer_rank_share.csv` là snapshot aggregate cố định theo toàn bộ portfolio. Các visual khác tính trực tiếp từ `customer_360.csv` và phản hồi theo filter context.

## Trang Customer 360 Profile

- Slicer single-customer.
- KPI: lifetime value proxy, net spend 12M, contribution margin proxy, recency và engagement score.
- Identity/profile: vùng, consent, thiết bị, hạng, phân khúc hành vi, gói và trạng thái subscription.
- Affinity: bốn nhóm Action, Concert, Family và Sports, có màu riêng.
- Cross-service usage: streaming, ticketing, events và membership.
- Recent activity: thời gian, nhãn, chi tiết, kết quả và màu trạng thái.
- Explainable action: next-best-action cùng profile note.

## Màu và ý nghĩa

- Màu hạng nằm trực tiếp trong `member_rank_color`.
- Màu rủi ro nằm trong `behavior_risk_color`: đỏ/cao, vàng/trung bình, xanh/thấp.
- Màu hoạt động nằm trong `activity_color`: xanh/thành công, đỏ/thất bại, vàng/đang xử lý, cyan/thông tin.
- Màu sở thích nằm trong `affinity_color`.

Các cột màu được render vào CSV để PBIP hoặc visual tùy chỉnh có thể dùng conditional formatting mà không phải mã hóa lại logic.

## Kiểm tra

```powershell
python scripts/validate_dashboard_demo_data.py --data-dir artifacts/powerbi_demo
python scripts/build_pbip.py --project-dir .. --data-dir artifacts/powerbi_demo --model-only
python scripts/build_pbip.py --project-dir .. --data-dir artifacts/powerbi_demo --report-only
python scripts/validate_pbip.py --project-dir .. --data-dir artifacts/powerbi_demo
```

Validator kiểm tra unique customer grain, ngưỡng hạng, cân bằng spend components, color fields, activity keys, affinity cardinality, tổng share bằng 100% và không còn `customer_journey.csv`.

## Giới hạn production

- Dataset là deterministic synthetic data, không đại diện kết quả kinh doanh thật.
- Identity hiện là synthetic key; production cần identity resolution, consent, masking/RLS và retention policy.
- Lifetime value, contribution margin và historical spend là analytical proxy; cần Finance sign-off trước khi dùng vận hành.
- Customer snapshot không phải slowly changing dimension và không hỗ trợ point-in-time history.
