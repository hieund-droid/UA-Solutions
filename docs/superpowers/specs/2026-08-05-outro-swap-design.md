# Thiết kế: Tab "Cắt & Gắn Outro" cho Video Remixer

Ngày: 2026-08-05

## 1. Bối cảnh & mục tiêu

Người dùng tải xuống video quảng cáo của đối thủ (mỗi video kết thúc bằng 1 đoạn
outro/CTA giới thiệu app của đối thủ). Cần 1 công cụ: tự động cắt bỏ outro của
đối thủ ở cuối mỗi video, gắn outro của chính mình vào thay thế — giữ nguyên
phần nội dung phía trước, không xáo trộn/ghép với video khác.

Tool này khác biệt hoàn toàn về mục đích và logic xử lý so với tính năng
"Video Remixer" hiện có (tách cảnh, xáo trộn, ghép thành biến thể mới). Hai
tính năng chỉ dùng chung 1 giao diện app.

## 2. Phạm vi

**Trong phạm vi:**
- Thêm tab mới "✂️ Cắt & Gắn Outro" trong cùng app Streamlit hiện tại.
- Thuật toán tự động nhận diện & cắt outro đối thủ dựa trên so khớp hình ảnh
  chéo giữa các video tải lên cùng lúc.
- Gắn 1 trong 2 outro cố định của người dùng (Photo app / Language app) vào
  cuối mỗi video kết quả.
- Quản lý 2 file outro cố định (upload/thay 1 lần, dùng lại nhiều lần).
- Cảnh báo cho người dùng biết video nào nhận diện chắc chắn, video nào phải
  dùng phương án dự phòng.

**Ngoài phạm vi (không làm ở lần này):**
- Không sửa đổi hành vi tab "Video Remixer" hiện có.
- Không có bước xem trước/chỉnh tay điểm cắt từng video (đã chốt: ưu tiên tự
  động hoàn toàn, chấp nhận đánh đổi độ chính xác không tuyệt đối).
- Không hỗ trợ nhận diện chính xác khi chỉ có 1 video duy nhất, hoặc các video
  tải lên không cùng 1 outro chung — các trường hợp này dùng phương án dự
  phòng (xem mục 4).
- Không dùng AI/nhận diện logo, chữ, watermark — chỉ so khớp hình ảnh
  (perceptual hash), giống kỹ thuật đã có sẵn trong `remix_core.py`.

## 3. Kiến trúc

- `app.py`: bọc giao diện hiện tại bằng `st.tabs([...])` — tách phần code
  Video Remixer hiện có vào 1 hàm riêng (không đổi hành vi), thêm 1 hàm mới
  cho tab "Cắt & Gắn Outro".
- `outro_core.py` (file mới): chứa toàn bộ logic nhận diện + cắt + gắn outro.
  Import lại các hàm dùng chung đã có sẵn trong `remix_core.py`
  (`ffprobe_info`, `_grab_frame_bgr`, `_dhash`, `_hash_distance`,
  `pick_target_spec`, `concat_clips`, `detect_scenes`) thay vì viết lại.
- `outros/` (thư mục mới trong project): lưu 2 file cố định —
  `outros/photo.mp4` và `outros/language.mp4`.

## 4. Luồng người dùng

1. Vào tab "Cắt & Gắn Outro".
2. Tải lên nhiều video của đối thủ (cùng 1 app/chiến dịch, có outro giống
   nhau ở cuối).
3. Chọn outro của mình từ dropdown: **Photo app** / **Language app**.
4. Bấm "Xử lý".
5. Với mỗi video, tool tự động:
   - Nhận diện & cắt bỏ đoạn outro của đối thủ ở cuối.
   - Gắn outro đã chọn vào cuối, thay cho outro cũ.
   - Giữ nguyên toàn bộ nội dung phía trước — không xáo trộn, không cắt ghép
     với video khác.
6. Kết quả: N video đầu vào → N video đầu ra tương ứng 1-1, xem/tải về từng
   video như tab Video Remixer hiện tại.

Ngoài ra có 1 khu vực nhỏ riêng "Quản lý outro của tôi" để upload/thay file
`photo.mp4` / `language.mp4` khi cần (không phải upload lại mỗi lần xử lý).

## 5. Thuật toán nhận diện & cắt outro đối thủ

Cơ sở: quan sát trên video mẫu thực tế (bộ Learna) cho thấy outro đối thủ là
1 đoạn giống hệt nhau (từng pixel) ở cuối MỌI video trong cùng bộ, còn nội
dung phía trước thì khác nhau giữa các video. Tận dụng đặc điểm này để nhận
diện, thay vì đoán qua chuyển động hay kiểu hình ảnh.

Với danh sách video tải lên cùng lúc:

1. Với mỗi video, dùng `detect_scenes()` (đã có sẵn) để lấy danh sách scene.
2. Lấy scene CUỐI CÙNG của mỗi video, chụp 1 khung hình đại diện (giữa scene,
   tránh sát biên có thể bị mờ/chuyển cảnh dở dang), tính perceptual hash
   (`_dhash`, đã có sẵn).
3. So khoảng cách hash (`_hash_distance`, đã có sẵn) giữa TỪNG CẶP video.
   Nhóm các video có khoảng cách ≤ ngưỡng (mặc định dùng lại ngưỡng 8, giống
   tính năng "gộp đoạn giống nhau" hiện có — sẽ tinh chỉnh khi test với video
   mẫu thật) vào cùng 1 "nhóm outro chung".
4. Với video thuộc 1 nhóm: mở rộng dò ngược thêm scene liền trước (scene kế
   cuối, kế kế cuối...), so khớp tiếp với scene tương ứng của các video khác
   trong nhóm — còn giống thì tính thêm vào outro, tới khi gặp scene khác
   biệt thì dừng. Xử lý được cả outro dài nhiều scene, không chỉ 1 scene.
5. Video KHÔNG thuộc nhóm nào (không khớp được với video nào khác) → **dùng
   phương án dự phòng**: coi scene cuối cùng là outro (giống logic "có
   outro" hiện có của tab Video Remixer), kèm cảnh báo "không chắc chắn —
   đã dùng phương án dự phòng" để người dùng biết mà tự kiểm tra riêng video
   đó nếu cần.
6. Kết quả mỗi video: 1 mốc thời gian "outro bắt đầu từ giây thứ mấy".

## 6. Xử lý ghép video kết quả

1. Cắt phần nội dung của mỗi video (từ đầu tới mốc outro) — re-encode chính
   xác từng frame, giống cách `split_clips()` hiện tại đang làm.
2. Co giãn/đệm viền đen + chuẩn hoá âm thanh cho cả phần nội dung và file
   outro đã chọn về cùng 1 chuẩn kích thước/fps (dùng lại `pick_target_spec`)
   để nối liền mạch.
3. Nối phần nội dung + outro bằng concat demuxer (dùng lại `concat_clips`).

## 7. Cảnh báo hiển thị

Trong lúc xử lý, hiện với mỗi video 1 trong 2 dòng:
- "✓ Nhận diện chắc chắn — đã cắt X giây outro đối thủ."
- "⚠️ Không tìm được outro chung với video khác — đã dùng phương án dự
  phòng (cắt cảnh cuối cùng theo điểm chuyển cảnh), có thể không chính xác
  hoàn toàn."

## 8. Giới hạn đã biết

- Cần tải lên ít nhất 2 video có cùng outro để nhận diện chính xác bằng cách
  so khớp chéo; ít hơn sẽ luôn rơi vào phương án dự phòng.
- Chỉ so khớp hình ảnh, không hiểu nội dung/chữ/logo — nếu outro của đối thủ
  tự thay đổi nhẹ giữa các video (dù cùng app) có thể không khớp được.
- Ngưỡng so khớp mặc định lấy tạm theo tính năng có sẵn, cần tinh chỉnh dựa
  trên video mẫu thật trong lúc code.

## 9. Kế hoạch kiểm thử

Trước khi bàn giao, chạy thử với bộ video mẫu thật tại
`C:\Users\ADMIN\Downloads\Language\Learna\EN-AR` (đã dùng để khảo sát khi
thiết kế) để xác nhận thuật toán cắt đúng điểm, không cắt hụt/cắt thừa vào
nội dung thật.
