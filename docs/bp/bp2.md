# BP2 · Giải thích biến động sản lượng lúa

BP2 trả lời hai câu hỏi cho doanh nghiệp thu mua và chế biến. Phần thay đổi sản lượng gắn với diện tích và phần gắn với năng suất là bao nhiêu? Vùng hoặc tỉnh nào đóng góp nhiều nhất vào mức tăng hoặc giảm trong kỳ so sánh?

## Chạy BP2

Từ thư mục gốc của repo, chạy bằng môi trường Python đã cài `requirements.txt`.

```powershell
python -m src.bp2.bp2
python -m streamlit run dashboard/bp2/bp2.py
```

Mở địa chỉ Streamlit in trong terminal. Dashboard mặc định so sánh hai năm gần nhất. Chọn **Cả nước** để so sánh bảy vùng hoặc chọn một vùng để xem các tỉnh. Hai bộ lọc năm cho phép chọn bất kỳ cặp mốc nào có trong dữ liệu với năm gốc đứng trước năm so sánh.

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
| Cam | Chênh lệch đối chiếu | Là phần điều chỉnh khi đối chiếu với sản lượng công bố |
| Trắng ngà | Thay đổi theo NSO | Số tổng quan sát được, không phải tác nhân thứ tư |

Màu thể hiện **loại chỉ tiêu**, thống nhất trên thẻ số liệu và hai biểu đồ. Dấu dương/âm và chiều cột thể hiện **hướng thay đổi**. Vì vậy, một cột năng suất vàng có thể tăng hoặc giảm. Trong biểu đồ phân rã, mỗi cột bắt đầu tại mức cộng dồn trước đó; cột trắng ngà cuối cùng thể hiện tổng thay đổi theo NSO. Biểu đồ so sánh địa phương dùng hình thoi trắng ngà để đánh dấu tổng này, phân biệt với ba thanh thành phần.

## Đầu ra và cách kiểm tra

[production_changes.parquet](../../data/analytics/bp2/production_changes.parquet) chứa 7.455 dòng cho 105 cặp năm. Mỗi cặp có 63 dòng `province`, 7 dòng `region` và 1 dòng `national` trong cột `level`. Khóa gồm hai năm, cấp địa lý và định danh tỉnh hoặc vùng tương ứng. Tệp lưu diện tích và sản lượng ở hai mốc, số tỉnh, biến động sản lượng và ba thành phần tính bằng tấn. Dashboard hiển thị theo nghìn tấn.

Kiểm tra mỗi dòng bằng cách cộng ba thành phần rồi đối chiếu với sản lượng cuối kỳ trừ sản lượng đầu kỳ. Với mỗi cặp năm, tổng của bảy vùng phải khớp với tổng 63 tỉnh. Mức sai số tuyệt đối lớn nhất khi đối chiếu trên tệp hiện tại là dưới 0,000001 tấn trước khi làm tròn hiển thị.

## Ví dụ trình bày giai đoạn 2023–2024

Tổng sản lượng của 63 tỉnh/thành giảm **46,11 nghìn tấn**. Phần gắn với diện tích là **+66,00 nghìn tấn**, phần gắn với năng suất là **−114,04 nghìn tấn**, và chênh lệch đối chiếu là **+1,93 nghìn tấn**. Phần giảm gắn với năng suất lớn hơn phần tăng gắn với diện tích.

Đồng bằng sông Hồng giảm **464,02 nghìn tấn**, trong đó phần gắn với năng suất là **−410,48 nghìn tấn**. Đồng bằng sông Cửu Long tăng **361,02 nghìn tấn**, với cả hai thành phần diện tích và năng suất cùng dương. Các kết quả phản ánh phép phân rã số học ở cấp tỉnh. Để giải thích nguyên nhân thực tế hoặc quyết định thu mua, doanh nghiệp cần thêm bằng chứng về điều kiện sản xuất, nhà cung cấp, giá, chất lượng và logistics.
