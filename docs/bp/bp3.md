# BP3 · Dự báo sản lượng lúa và kịch bản nguồn cung

BP3 trả lời câu hỏi cốt lõi cho các doanh nghiệp thu mua và chế biến lúa gạo:
> **Triển vọng sản lượng lúa cấp tỉnh trong năm tới như thế nào và độ chính xác của phương pháp dự báo đã qua kiểm chứng lịch sử ra sao?**

Dashboard cung cấp dự báo 1 năm tới (cho năm **2025** sử dụng dữ liệu đến hết năm **2024**), đánh giá kiểm định mô hình theo thứ tự thời gian (walk-forward cross-validation từ **2017 đến 2024** mà không rò rỉ dữ liệu tương lai), và xây dựng các **kịch bản nguồn cung (sourcing scenarios)** dựa trên phân phối sai số lịch sử để hỗ trợ lập kế hoạch dự trữ an toàn và phòng ngừa rủi ro thiếu hụt nguồn cung.

---

## 1. Chạy BP3

Từ thư mục gốc của repository, chạy bằng môi trường Python dự án:

```powershell
# Xây dựng các bảng Parquet phân tích BP3
python -m src.bp3.bp3

# Khởi chạy giao diện Streamlit chia sẻ
python -m streamlit run dashboard/app.py --theme.base=configs/config.toml
```

Sau khi mở ứng dụng tại `http://localhost:8501`, chọn **BP3 · Production forecasting** từ trang chủ hoặc thanh bên, hoặc truy cập trực tiếp đường dẫn `/bp3`.

---

## 2. Bốn chế độ xem trên Dashboard

| Chế độ xem | Nội dung phân tích | Ý nghĩa cho lập kế hoạch thu mua |
|---|---|---|
| **Outlook & Forecast** | Dự báo sản lượng năm 2025 cấp Quốc gia, 7 Vùng và 63 Tỉnh; so sánh với mức thực tế năm 2024; xếp hạng các tỉnh trọng điểm. | Xác định tổng quy mô nguồn cung kỳ vọng và tỷ trọng sản lượng giữa các vùng nguyên liệu. |
| **Model Accuracy & Backtest** | Bảng điểm so sánh các mô hình với Baseline (Naive Lag-1); diễn biến sai số qua 8 năm kiểm định (2017–2024); phân phối độ tin cậy MAPE theo tỉnh. | Đánh giá độ tin cậy của thuật toán dự báo, khẳng định tính khả thi của phương pháp trên dữ liệu thực tế. |
| **Sourcing Scenarios** | 3 kịch bản: Cơ sở (Base Outlook), Kịch bản bi quan (-1 MAE) và Kịch bản khả quan (+1 MAE); thanh trượt điều chỉnh biên độ an toàn; phân nhóm ưu tiên thu mua theo vùng. | Định lượng mức thâm hụt sản lượng tối đa có thể xảy ra trong điều kiện bất lợi để ký hợp đồng dự phòng. |
| **Province Deep Dive** | Chuỗi thời gian 2010–2024 kèm phễu dự báo 2025; phân tích xu hướng diện tích gieo trồng và năng suất của từng tỉnh. | Khảo sát chi tiết từng địa phương cụ thể trước khi đàm phán hợp đồng cung ứng dài hạn. |

---

## 3. Phương pháp dự báo và mô hình toán học

### 3.1. Nguyên tắc kiểm định Walk-Forward (Không rò rỉ dữ liệu)
Để phản ánh chính xác quy trình ra quyết định trong thực tế:
- Dự báo cho năm kiểm định $T$ ($T \in [2017, \dots, 2024]$) chỉ được phép sử dụng tập dữ liệu lịch sử tại các năm $t \le T-1$.
- Dữ liệu của năm $T$ và các năm sau đó tuyệt đối không xuất hiện trong quá trình ước lượng tham số (expanding training window).

### 3.2. Danh mục mô hình kiểm định (Sử dụng thư viện tiêu chuẩn)

Toàn bộ các mô hình dự báo được xây dựng dựa trên các thư viện chuẩn công nghiệp (`statsmodels`, `scikit-learn`, `pandas`) nhằm đảm bảo tính chuẩn xác về mặt toán học và thuật toán tối ưu hóa tham số:

1. **Naive Baseline (Lag-1 Persistence):**
   - *Thực thi:* Sử dụng `pandas.Series.iloc[-1]`.
   - *Công thức:* $\hat{y}_{T} = y_{T-1}$.
   - *Ý nghĩa:* Giả định sản lượng năm tới bằng đúng sản lượng năm trước. Đây là chuẩn đối sánh cơ bản trong quản trị chuỗi cung ứng.

2. **3-Year Simple Moving Average (SMA-3):**
   - *Thực thi:* Sử dụng `pandas.Series.rolling(window=3).mean()`.
   - *Công thức:* $\hat{y}_{T} = \frac{1}{3} \sum_{i=1}^{3} y_{T-i}$.
   - *Ý nghĩa:* San bằng các biến động đột biến hàng năm do thời tiết ngắn hạn.

3. **Damped Holt's Linear Exponential Smoothing:**
   - *Thực thi:* Sử dụng `statsmodels.tsa.holtwinters.Holt(damped_trend=True)`.
   - *Công thức:* Tối ưu hóa tham số mức ($l_t$), xu thế ($b_t$) và hệ số suy giảm xu thế ($\phi$) tự động qua Maximum Likelihood Estimation (MLE) / L-BFGS-B từ `statsmodels`.
   - *Ý nghĩa:* Nắm bắt quán tính xu thế tăng trưởng dài hạn nhưng triệt tiêu việc phóng đại xu thế quá mức trong nông nghiệp.

4. **Linear Trend (Hồi quy xu thế tuyến tính 5 năm):**
   - *Thực thi:* Sử dụng `sklearn.linear_model.LinearRegression()`.
   - *Công thức:* Khớp mô hình hồi quy OLS trên cửa sổ 5 năm gần nhất: $\hat{y} = \beta_0 + \beta_1 \cdot t$.
   - *Ý nghĩa:* Bắt kịp xu hướng tăng hoặc giảm đều đặn trong ngắn hạn.

5. **Component Model (Mô hình thành phần Diện tích × Năng suất):**
   - *Thực thi:* Kết hợp `sklearn.linear_model.LinearRegression` (dự báo diện tích $\hat{A}_T$) và `statsmodels.tsa.holtwinters.Holt` (dự báo năng suất $\hat{Y}_T$).
   - *Công thức:* $\hat{P}_{T} = \max\left(0, \hat{A}_{T} \times \hat{Y}_{T}\right)$.
   - *Ý nghĩa:* Phản ánh bản chất nông nghiệp: diện tích phụ thuộc vào quy hoạch/chuyển đổi đất, còn năng suất phản ánh tiến bộ giống và thời tiết.

### 3.3. Cơ chế chọn mô hình tối ưu theo tỉnh (Best-per-Province Selector)
Mỗi tỉnh có đặc thù sản xuất riêng: một số tỉnh ĐBSCL có xu hướng tương đối ổn định (phù hợp Naive/SMA), trong khi các tỉnh miền núi đang mở rộng năng suất (phù hợp Holt/Component). BP3 tự động lựa chọn mô hình đạt sai số tuyệt đối trung bình (MAE) thấp nhất trong giai đoạn kiểm định lịch sử cho từng tỉnh.

---

## 4. Xây dựng kịch bản nguồn cung (Sourcing Scenarios)

Dựa trên sai số tuyệt đối trung bình lịch sử ($\text{MAE}_i$) của từng tỉnh trong giai đoạn backtest:

- **Kịch bản Cơ sở (Expected Base Outlook):** Giá trị dự báo điểm $\hat{y}_{i, 2025}$.
- **Kịch bản Khả quan (Optimistic / High Supply):** $\hat{y}_{\text{opt}} = \hat{y}_{i, 2025} + k \cdot \text{MAE}_i$ (với $k$ là hệ số an toàn, mặc định $k=1.0$).
- **Kịch bản Bi quan (Pessimistic / Low Supply):** $\hat{y}_{\text{pess}} = \max\left(0, \hat{y}_{i, 2025} - k \cdot \text{MAE}_i\right)$.
- **Biên độ rủi ro thâm hụt (Downside Buffer Gap):** $\Delta_{\text{buffer}} = \hat{y}_{i, 2025} - \hat{y}_{\text{pess}}$.

### Phân tầng ưu tiên thu mua (Sourcing Risk Tiers)
1. **Core Stable Supplier:** Sản lượng $\ge 500.000$ tấn và sai số $\text{MAPE} \le 6\%$ (ví dụ: An Giang, Kiên Giang, Đồng Tháp). Ký hợp đồng bao tiêu dài hạn.
2. **High-Volume Volatile:** Sản lượng $\ge 500.000$ tấn nhưng sai số $\text{MAPE} > 6\%$. Cần duy trì nhà cung cấp thay thế và theo dõi sát lịch thời vụ.
3. **Moderate Supply:** Sản lượng từ $100.000$ đến $500.000$ tấn. Cung ứng vệ tinh bổ sung.
4. **Minor / Local Supply:** Sản lượng $< 100.000$ tấn. Phục vụ tiêu thụ nội tỉnh.

---

## 5. Dữ liệu đầu ra (Analytics Marts)

Pipeline xuất 4 tệp Parquet vào thư mục `data/analytics/bp3/`:

| Tệp Parquet | Cấp độ hạt | Số dòng | Mô tả |
|---|---|---|---|
| `forecast_next_year.parquet` | Province (63), Region (7), National (1) | 71 | Dự báo 2025, sản lượng 2024, các mốc kịch bản Base/Pessimistic/Optimistic, tỷ lệ thay đổi, phân tầng rủi ro. |
| `historical_backtest.parquet` | Province × Test Year (2017–2024) × Model | 2.520 | Chi tiết từng lượt dự báo kiểm định, giá trị thực tế NSO, sai số tuyệt đối và phần trăm. |
| `model_performance.parquet` | Geography (Province, Region, National) × Model | 355 | Các chỉ số đánh giá MAE, RMSE, MAPE, Bias và cờ đánh dấu `is_best_model`. |
| `sourcing_scenarios.parquet` | Region (7) | 7 | Tổng hợp kịch bản nguồn cung theo vùng, mức đệm an toàn đề xuất và khuyến nghị chiến lược thu mua. |

---

## 6. Kết quả kiểm chứng chính

1. **Tổng sản lượng lúa cả nước năm 2025** dự báo đạt khoảng **43,37 triệu tấn** (thay đổi khoảng **-0,18%** so với mức 43,45 triệu tấn của năm 2024).
2. **Phạm vi kịch bản cả nước:**
   - Kịch bản Bi quan: **42,48 triệu tấn** (thấp hơn khoảng 892 nghìn tấn so với kỳ vọng cơ sở).
   - Kịch bản Khả quan: **44,26 triệu tấn** (cao hơn khoảng 892 nghìn tấn).
3. **Độ chính xác kiểm định:**
   - Ở cấp độ toàn quốc, sai số MAPE trung bình chỉ khoảng **1,3% – 1,7%**, nhờ hiệu ứng bù trừ biến động giữa các vùng sinh thái.
   - Ở cấp độ tỉnh, sai số trung bình (MAPE) dao động quanh mức **4,8% – 5,2%**.
   - Vùng Đồng bằng sông Cửu Long tiếp tục là vựa lúa chủ lực với hơn **24,1 triệu tấn** (chiếm ~55,6% sản lượng cả nước), với mức độ biến động thấp và độ tin cậy dự báo cao nhất.
