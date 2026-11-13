# BP2 · Giải thích biến động sản lượng lúa

BP2 trả lời hai câu hỏi cho doanh nghiệp thu mua và chế biến. Phần thay đổi sản lượng gắn với diện tích và phần gắn với năng suất là bao nhiêu? Vùng hoặc tỉnh nào đóng góp nhiều nhất vào mức tăng hoặc giảm trong kỳ so sánh?

## Chạy BP2

Từ thư mục gốc của repo, chạy bằng môi trường Python đã cài `requirements.txt`.

```powershell
python -m src.bp2.bp2
python -m streamlit run dashboard/app.py --theme.base=configs/config.toml
```

Nếu tệp Parquet BP2 đã có sẵn, có thể chạy web trực tiếp. Mở **BP2 · Explaining production changes** từ trang chủ, thanh bên hoặc đường dẫn `/bp2`. Bộ lọc và bốn thẻ số liệu nằm ở đầu trang, phía trên các tab. Chọn **Vietnam** để so sánh bảy vùng hoặc chọn một vùng để xem các tỉnh. **Base year** là năm gốc và **Comparison year** là năm so sánh. Mặc định là hai năm gần nhất.

## Bốn chế độ xem

| Tab | Cách đọc | Ví dụ với phạm vi Vietnam |
|---|---|---|
| **Overview** | Biểu đồ thác nước trả lời *mức thay đổi của phạm vi đang chọn được chia thành những phần nào?* Đọc ba phần xanh lá, vàng, cam từ trái sang phải; cột xanh xám cuối là tổng NSO. | Cả nước 2023–2024: **+66,00** do phần gắn với diện tích, **−114,04** do phần gắn với năng suất và **+1,93** chênh lệch báo cáo, nên tổng là **−46,11 nghìn tấn**. |
| **Compare places** | Biểu đồ chấm trả lời *địa phương nào biến động nhiều nhất trong kỳ?* Mỗi chấm là một vùng hoặc tỉnh. Chọn một chỉ tiêu để xếp hạng theo độ lớn tuyệt đối; bên trái 0 là giảm, bên phải 0 là tăng. | 2023–2024, Đồng bằng sông Hồng có tổng giảm **464,02 nghìn tấn**; Đồng bằng sông Cửu Long tăng **361,02 nghìn tấn**. Hai chấm nằm hai phía của mốc 0. |
| **Year by year** | Ma trận nhiệt trả lời *biến động lặp lại ở đâu và vào năm nào?* Mỗi ô là một địa phương trong một năm so với năm liền trước. Đỏ là âm, xanh ngọc là dương, nhạt gần 0. | Khi chọn cả nước 2023–2024, bản đồ vẫn cho bối cảnh 2019–2024. Ô Đồng bằng sông Cửu Long năm **2022** là **−791,09 nghìn tấn** so với 2021. |
| **Area vs. yield** | Biểu đồ bốn góc phần tư trả lời *diện tích và năng suất có cùng chiều hay bù trừ?* Mỗi chấm là một địa phương; trục ngang là đóng góp diện tích, trục dọc là đóng góp năng suất. Hai góc chéo là bù trừ. | Bắc Trung Bộ 2023–2024 nằm gần trục dọc, hơi sang trái vì diện tích **−0,37**, còn năng suất **+62,17 nghìn tấn**. Tổng NSO vẫn tăng **62,11 nghìn tấn**. |

Tab **Year by year** luôn gồm các năm nằm trong khoảng đã chọn. Nếu khoảng chỉ có một hoặc vài năm, trang tự bổ sung tối đa năm năm trước năm gốc để dễ thấy bối cảnh; các thẻ số liệu ở đầu trang vẫn chỉ phản ánh đúng hai mốc đang chọn. Ma trận nhiệt dùng thang màu đối xứng quanh 0 và thay đổi theo chỉ tiêu/phạm vi đang xem. Khi so sánh giữa các bộ lọc, hãy dùng số trong tooltip. Tab này chỉ có ma trận nhiệt, không lặp lại biểu đồ cột thay đổi một năm của phần **Overview**.

## Hiểu con số “Reporting difference”

Đây là **phần chênh lệch khi đối chiếu số NSO**, không phải một nguyên nhân thứ ba khiến lúa tăng/giảm. Sản lượng `P` được công bố trong bảng riêng; tích diện tích `A` × năng suất `Y` từ hai bảng còn lại có thể không khớp tuyệt đối với `P`. Chúng tôi lấy `(P − A×Y)` ở năm sau trừ đi `(P − A×Y)` ở năm trước. Sự thay đổi này được cộng vào hai phần diện tích và năng suất để tổng khớp đúng với thay đổi sản lượng NSO. Số công bố có thể khác vì làm tròn hoặc quy ước báo cáo; dữ liệu hiện có không xác định được chính xác nguồn gốc từng sai khác.

Ví dụ cả nước 2023–2024: `+66,00 − 114,04 + 1,93 = −46,11` **nghìn tấn** sau khi làm tròn để hiển thị. `+1,93` nghĩa là chênh lệch giữa `P` và `A×Y` tăng khoảng **1.930 tấn** từ 2023 sang 2024. Không nên gọi đó là sản lượng “tăng thêm do nguyên nhân khác”.

## Dữ liệu và công thức

- Đầu vào là [Parquet dùng chung](../../data/processed/agriculture/rice_province_year/rice_province_year.parquet), gồm 945 dòng, 63 tỉnh/thành lịch sử, giai đoạn 2010–2024. Diện tích tính bằng ha, năng suất bằng tấn/ha và sản lượng bằng tấn. Tệp dùng chung không có cột trạng thái số liệu.
- Khóa là `province_id, year`. BP2 kiểm tra ID, tên tỉnh và vùng theo [JSON của dự án](../../data/vietnam_regions_provinces.json), từ chối khóa trùng và dữ liệu thiếu hoặc không hợp lệ. Tổng vùng và cả nước chỉ cộng các tỉnh hợp lệ trong JSON.
- Gọi `A` là diện tích, `Y` là năng suất NSO, `P` là sản lượng NSO. Chỉ số `0` là năm gốc, `1` là năm so sánh.

| Thành phần | Công thức ở cấp tỉnh | Đơn vị |
|---|---|---|
| Diện tích | (A₁ − A₀) × (Y₀ + Y₁) / 2 | tấn |
| Năng suất | (Y₁ − Y₀) × (A₀ + A₁) / 2 | tấn |
| Chênh lệch đối chiếu | (P₁ − A₁Y₁) − (P₀ − A₀Y₀) | tấn |
| Thay đổi theo NSO | P₁ − P₀ | tấn |

Hai thành phần đầu chia đều phần tương tác giữa thay đổi diện tích và thay đổi năng suất. Tổng của chúng bằng thay đổi của tích A × Y. Sản lượng NSO và tích A × Y có thể lệch do độ chính xác của các chỉ tiêu được công bố. Cột chênh lệch đối chiếu ghi phần sai khác giữa hai mức thay đổi, để ba thành phần cộng lại đúng bằng P₁ − P₀.

BP2 cộng từng thành phần từ tỉnh lên vùng và cả nước để giữ tính cộng được giữa các cấp. Vì vậy, phần năng suất của một vùng là tổng đóng góp năng suất của các tỉnh trong vùng. Khi hai mốc cách nhau nhiều năm, công thức so sánh trực tiếp hai đầu kỳ.

## Cách đọc màu và biểu đồ

| Màu | Thành phần | Lý do chọn |
|---|---|---|
| Xanh lá | Diện tích | Gợi diện tích đất gieo trồng |
| Vàng lúa | Năng suất | Gợi hạt lúa và kết quả trên mỗi hecta |
| Cam đất | Reporting difference, chênh lệch báo cáo | Nhấn rõ đây là phần điều chỉnh để khớp tổng NSO, khác hai đóng góp sản xuất |
| Xanh xám | Thay đổi theo NSO | Màu trung tính đánh dấu tổng thay đổi quan sát được |

Màu thể hiện **loại chỉ tiêu** trên các thẻ số liệu, thác nước và chấm xếp hạng. Dấu dương/âm, vị trí so với 0 và hướng cột thể hiện **chiều thay đổi**. Vì vậy, một cột năng suất vàng có thể tăng hoặc giảm. Trong biểu đồ phân rã, mỗi cột đóng góp bắt đầu tại mức cộng dồn trước đó; cột xanh xám cuối cùng bắt đầu từ 0 và là tổng thay đổi NSO. Riêng ma trận nhiệt và màu chấm ở biểu đồ bốn góc phần tư, **đỏ là giảm, xanh ngọc là tăng**, vì hai biểu đồ này dùng màu để đọc chiều biến động.

## Đầu ra và cách kiểm tra

[production_changes.parquet](../../data/analytics/bp2/production_changes.parquet) chứa 7.455 dòng cho 105 cặp năm. Mỗi cặp có 63 dòng `province`, 7 dòng `region` và 1 dòng `national` trong cột `level`. Khóa gồm hai năm, cấp địa lý và định danh tỉnh hoặc vùng tương ứng. Tệp lưu diện tích và sản lượng ở hai mốc, số tỉnh, biến động sản lượng và ba thành phần tính bằng tấn. Dashboard hiển thị theo nghìn tấn.

Kiểm tra mỗi dòng bằng cách cộng ba thành phần rồi đối chiếu với sản lượng cuối kỳ trừ sản lượng đầu kỳ. Với mỗi cặp năm, tổng của bảy vùng phải khớp với tổng 63 tỉnh. Mức sai số tuyệt đối lớn nhất khi đối chiếu trên tệp hiện tại là dưới 0,000001 tấn trước khi làm tròn hiển thị.

## Ví dụ trình bày giai đoạn 2023–2024

Tổng sản lượng của 63 tỉnh/thành giảm **46,11 nghìn tấn**. Phần gắn với diện tích là **+66,00 nghìn tấn**, phần gắn với năng suất là **−114,04 nghìn tấn**, và chênh lệch đối chiếu là **+1,93 nghìn tấn**. Phần giảm gắn với năng suất lớn hơn phần tăng gắn với diện tích.

Đồng bằng sông Hồng giảm **464,02 nghìn tấn**, trong đó phần gắn với năng suất là **−410,48 nghìn tấn**. Đồng bằng sông Cửu Long tăng **361,02 nghìn tấn**, với cả hai thành phần diện tích và năng suất cùng dương. Các kết quả phản ánh phép phân rã số học ở cấp tỉnh. Để giải thích nguyên nhân thực tế hoặc quyết định thu mua, doanh nghiệp cần thêm bằng chứng về điều kiện sản xuất, nhà cung cấp, giá, chất lượng và logistics.
