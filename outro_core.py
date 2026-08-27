#!/usr/bin/env python3
"""
outro_core.py — Tự động cắt đoạn outro của ĐỐI THỦ ở cuối video và gắn outro
của MÌNH vào thay thế — GIỮ NGUYÊN nội dung gốc, không xáo trộn/ghép clip
như remix_core.py (đây là tính năng khác biệt hoàn toàn, chỉ dùng chung
giao diện app với Video Remixer).

Cách nhận diện outro đối thủ:
  Outro của cùng 1 đối thủ/app thường là 1 đoạn dựng sẵn — GIỐNG HỆT NHAU ở
  mọi video quảng cáo của họ, trong khi nội dung phía trước (người nói
  chuyện, cảnh quay...) thì mỗi video một kiểu. Vì vậy: chụp khung hình ở
  gần cuối mỗi video, so màu trung bình theo lưới ô nhỏ (xem `_color_thumb`)
  CHÉO GIỮA CÁC VIDEO tải lên CÙNG LÚC — video nào có đoạn cuối trùng với
  video khác thì coi đó là outro đối thủ, rồi dò lùi dần theo THỜI GIAN
  (không dựa vào ranh giới scene — đã thử và không đáng tin cậy, vì outro
  thường không được PySceneDetect tách thành 1 scene riêng mà bị dính chung
  với đoạn nội dung ngay trước đó) để tìm đúng điểm bắt đầu outro.

  Dùng cách so màu theo lưới thay vì perceptual hash (vân ảnh, cách đã có
  sẵn trong remix_core.py cho tính năng "gộp đoạn giống nhau") vì outro
  thực tế có hiệu ứng ánh sáng động nhẹ trên nền — vân ảnh nhạy với hướng
  chuyển màu giữa các pixel liền kề nên bị nhiễu bởi hiệu ứng này, trong khi
  so màu trung bình theo lưới ổn định hơn nhiều mà vẫn phân biệt rõ với nội
  dung video thật (đã kiểm chứng bằng video mẫu thật).

  Tải lên càng nhiều video 1 lúc càng tốt, kể cả trộn lẫn NHIỀU đối thủ/app
  khác nhau trong cùng 1 lần — thuật toán tự gom nhóm theo từng app riêng
  biệt (mỗi nhóm so khớp chéo với nhau), không cần tự sắp xếp/lọc trước.

  Video nào không khớp được với video nào khác trong CÙNG mẻ tải lên sẽ
  được thử tiếp 2 lớp dự phòng, theo thứ tự:
    2. So với THƯ VIỆN outro đối thủ đã từng nhận diện được trước đó (xem
       KNOWN_OUTRO_DIR/_match_against_known_library) — mỗi khi 1 video cắt
       thành công đủ tin cậy (khớp chéo hoặc dò-đơn-lẻ có badge xác nhận),
       đoạn outro đó tự động được LƯU LẠI vào thư viện dùng chung cho cả
       team, để lần sau chỉ cần 1 video (không có gì để so khớp chéo) vẫn
       nhận ra được nếu đã từng gặp outro đó. Đây vẫn là so khớp chéo
       (đáng tin hơn), chỉ khác là so với thư viện thay vì so với video
       khác trong cùng mẻ.
    3. Nếu cả thư viện cũng không khớp: dò điểm chuyển cảnh gần cuối video
       + xác nhận bằng badge cửa hàng ứng dụng ("GET IT ON Google Play" /
       "Download on the App Store" — 2 mẫu CHUẨN HOÁ giống nhau ở mọi app,
       so mẫu được) — xem find_solo_outro_boundary.
  Chỉ khi CẢ 3 lớp đều không tìm được gì mới GIỮ NGUYÊN, không cắt — chủ
  động chọn AN TOÀN thay vì đoán liều (vd cắt cứng N giây cuối): rất có thể
  video đó không hề có outro thật, đoán liều dễ cắt nhầm vào nội dung thật
  hơn là giúp ích.

Dùng module (import từ app.py):
    process_outro_swap(paths, own_outro_path, workdir, strip_audio)

Yêu cầu: ffmpeg, ffprobe trong PATH (giống remix_core.py).
"""

import concurrent.futures
import uuid
from pathlib import Path

import cv2
import numpy as np

from remix_core import concat_clips, ffprobe_info, split_clips

# Thư viện outro đối thủ ĐÃ TỪNG NHẬN DIỆN ĐƯỢC — dùng chung cho cả team
# (không chia theo người như outros/users/<id>/, vì đây là nhận diện outro
# ĐỐI THỦ, ai gặp trước cũng nên giúp ích được cho người sau). Chỉ chứa
# đúng ĐOẠN OUTRO đã cắt ra (không phải cả video), không âm thanh (so khớp
# chỉ cần hình). Xem _save_to_known_library / _match_against_known_library.
KNOWN_OUTRO_DIR = Path(__file__).parent / "known_outros"
KNOWN_OUTRO_DIR.mkdir(exist_ok=True)

# Thư mục chứa ảnh mẫu badge cửa hàng ứng dụng (Google Play, App Store) —
# dùng cho _find_solo_outro_boundary bên dưới. Đây là ẢNH TĨNH đi kèm code
# (không phải dữ liệu người dùng), nên nằm trong assets/, được commit vào
# git (khác với outros/ chứa video người dùng tải lên, bị .gitignore).
BADGE_TEMPLATES_DIR = Path(__file__).parent / "assets" / "badges"

# Các mốc giây tính từ cuối video dùng để "dò thử" xem 2 video có outro
# chung không. DÙNG NHIỀU MỐC (không phải 1 mốc cố định) vì outro thực tế
# dài rất khác nhau tuỳ app — đã gặp thật: outro app A chỉ ~1 giây (dò ở mốc
# 1.5s sẽ trượt hẳn qua, so sánh nhầm sang nội dung phía trước, làm gãy toàn
# bộ việc nhận diện), outro app B dài ~3-4 giây. Dò đủ nhiều mốc để bắt được
# cả 2 trường hợp mà không cần biết trước outro app nào dài bao nhiêu.
#
# Các mốc XA (từ 0.5s trở đi) — cố định theo giây, không cần chính xác tới
# từng khung hình vì ở khoảng cách này sai số nửa khung hình là không đáng
# kể so với thời lượng đang xét.
FAR_PROBE_OFFSETS = [0.5, 1.0, 1.5, 2.5, 4.0]
# Số khung hình ĐẦU (gần cuối video nhất) cần dò riêng theo ĐÚNG fps thực
# tế của từng video — xem _probe_offsets() ngay dưới để biết vì sao KHÔNG
# thể dùng số giây cố định (vd 0.04, 0.08...) cho phần này.
NEAR_TAIL_FRAME_COUNT = 9


def _probe_offsets(fps):
    """Danh sách mốc (giây) để dò, phần GẦN CUỐI (9 khung hình đầu) tính
    THEO ĐÚNG FPS THẬT của video đang xét — bắt được cả outro CỰC NGẮN,
    kiểu "thẻ logo" chỉ hiện 2-3 khung hình rồi file kết thúc luôn (đã gặp
    thật: app Vividix, outro chỉ ~0.1 giây). Phải dò DÀY từng khung hình một
    ở vùng này — nếu dò cách khung rất dễ "nhảy qua" lọt cả đoạn outro ngắn
    cỡ này (không đủ mốc liền kề theo yêu cầu chống nhận nhầm ở
    _best_matching_offset bên dưới) dù outro đó hoàn toàn có thật.

    QUAN TRỌNG: phải tính theo fps THẬT (1/fps, 2/fps, ...) chứ KHÔNG được
    dùng số giây cố định như 0.04/0.08 — đã gặp thật: video quay ở 30fps
    (khung hình cách nhau 0.0333s), mốc cố định 0.04s không rơi đúng vào
    khung hình nào cả, mỗi lần làm tròn về khung gần nhất lại lệch một chút
    khác nhau tuỳ điểm, đủ để phá vỡ toàn bộ chuỗi khớp liên tiếp (dò được
    với video 25fps nhưng lại trượt hoàn toàn với video 30fps cùng 1 outro).
    Dùng đúng bội số của 1/fps đảm bảo luôn trúng CHÍNH XÁC khung hình,
    không phụ thuộc video quay ở tốc độ khung hình nào."""
    frame = 1.0 / fps
    near = [round(frame * k, 5) for k in range(1, NEAR_TAIL_FRAME_COUNT + 1)]
    return near + FAR_PROBE_OFFSETS
# Không dò lùi quá xa mốc này — outro thực tế không dài tới mức này, nếu
# dò xa hơn mà vẫn khớp thì dừng lại để tránh nuốt nhầm nội dung thật. Cũng
# chính là khoảng thời gian đọc TUẦN TỰ từ cuối video (xem _read_tail_hashes).
MAX_OUTRO_LOOKBACK = 20.0
# Ngưỡng mặc định cho _match() — xem lý do dùng "màu trung bình theo lưới"
# thay vì so vân ảnh (perceptual hash) ngay bên dưới.
DEFAULT_MATCH_THRESHOLD = 15
# Số giây NỘI DUNG THẬT tối thiểu phải còn lại sau khi cắt — xem
# _process_one_video: chặn trường hợp ranh giới xác định sai khiến outro
# "nuốt" gần hết/hết cả video, tạo ra 1 đoạn nội dung gần như rỗng làm hỏng
# bước ghép clip (đã gặp thật, xem comment tại chỗ dùng).
MIN_CONTENT_SECONDS = 1.0


def _pick_larger_spec(info_a, info_b):
    """Chọn khung hình chuẩn (width/height) theo bên nào có ĐỘ PHÂN GIẢI
    CAO HƠN giữa 2 nguồn — dùng khi ghép content (từ video đối thủ) với
    outro (của bạn). Nếu luôn lấy theo video đối thủ (thường là file tải
    về, độ phân giải thấp hơn) thì outro chất lượng cao của bạn sẽ bị co
    nhỏ xuống theo khi ghép, gây mờ dù file gốc trên máy không hề mờ."""
    area_a = (info_a["width"] or 0) * (info_a["height"] or 0)
    area_b = (info_b["width"] or 0) * (info_b["height"] or 0)
    bigger = info_a if area_a >= area_b else info_b
    return {
        "width": bigger["width"] or 1280,
        "height": bigger["height"] or 720,
        "fps": info_a["fps"] or info_b["fps"] or 30,
    }


def _color_thumb(frame, size=12):
    """Ảnh thu nhỏ còn `size`x`size`, lấy màu trung bình mỗi ô lưới.

    Dùng cách này thay vì perceptual hash (vân ảnh, đã dùng cho tính năng
    "gộp đoạn giống nhau" ở remix_core.py) vì outro thực tế có hiệu ứng ánh
    sáng động nhẹ trên nền — vân ảnh (nhạy với hướng chuyển màu giữa các
    pixel liền kề) bị nhiễu bởi hiệu ứng này ngay cả khi so 2 khung hình
    trong CÙNG 1 outro, trong khi so màu trung bình theo lưới ổn định hơn
    nhiều mà vẫn phân biệt rõ với nội dung video thật (test thực tế: cùng
    outro lệch thời điểm ~7-10, khác video nhưng cùng outro ~0-1, nội dung
    thật khác hẳn ~70+)."""
    small = cv2.resize(frame, (size, size), interpolation=cv2.INTER_AREA)
    return small.astype(np.float32)


def _read_tail_hashes(path, duration, fps, lookback_seconds):
    """Đọc TUẦN TỰ (không tua/seek ngẫu nhiên từng mốc riêng lẻ) mọi khung
    hình từ khoảng `lookback_seconds` giây trước khi kết thúc video, cho
    tới ĐÚNG khung hình CUỐI CÙNG — thu nhỏ ngay thành hash màu
    (_color_thumb) rồi bỏ khung hình gốc (nhẹ RAM, chỉ giữ lưới 12x12 mỗi
    khung chứ không giữ cả khung hình đầy đủ).

    Dùng cách này thay vì tua tới từng mốc riêng lẻ rồi đọc 1 khung (cách
    cũ): TUA NGẪU NHIÊN tới trong khoảng dưới ~0.3 giây cuối file thường
    KHÔNG ổn định (nhiều codec không có keyframe sát mép cuối, dễ đọc nhầm
    khung hình lân cận hoặc đọc thất bại hẳn) — trong khi ĐỌC TUẦN TỰ (chỉ 1
    lần tua tới điểm AN TOÀN vài giây trước khi kết thúc, sau đó chỉ gọi
    read() liên tiếp, không tua nữa) luôn chính xác, kể cả những khung hình
    cuối cùng. Bắt buộc phải làm vậy vì có outro RẤT NGẮN (dưới 0.2 giây,
    chỉ 2-3 khung hình) nằm lọt hẳn trong vùng tua không ổn định — đã gặp
    thật (app Vividix, video bị cắt gần như ngay giữa lúc chuyển sang thẻ
    outro, chỉ còn lại 2-3 khung hình mờ ở sát mép cuối file).

    Trả về dict {"hashes": [...theo thứ tự thời gian TĂNG DẦN...],
    "start_t": giây bắt đầu đọc, "fps": fps, "duration": duration}."""
    cap = cv2.VideoCapture(str(path))
    start_t = max(duration - lookback_seconds, 0.0)
    cap.set(cv2.CAP_PROP_POS_MSEC, start_t * 1000)
    hashes = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        hashes.append(_color_thumb(frame))
    cap.release()
    return {"hashes": hashes, "start_t": start_t, "fps": fps, "duration": duration}


def _tail_hash_at_offset(tail, offset):
    """Lấy hash khung hình gần nhất với thời điểm `offset` giây TRƯỚC KHI
    KẾT THÚC video, tra trong dữ liệu đã đọc sẵn ở `tail` (xem
    _read_tail_hashes). Trả về None nếu offset vượt ngoài phạm vi đã đọc."""
    hashes = tail["hashes"]
    if not hashes:
        return None
    target_t = tail["duration"] - offset
    idx = round((target_t - tail["start_t"]) * tail["fps"])
    if idx < 0 or idx >= len(hashes):
        return None
    return hashes[idx]


def _match(h1, h2, threshold):
    if h1 is None or h2 is None:
        return False
    return float(np.abs(h1 - h2).mean()) <= threshold




# Khi dò nhiều mốc thời gian, càng nhiều mốc/cặp video đem so thì càng dễ
# gặp 1 khung hình TRÙNG HỢP NGẪU NHIÊN (vd cùng tư thế/ánh sáng giống nhau
# tình cờ ở 1 mốc nào đó) bị hiểu nhầm là outro chung — đã gặp thật (khớp
# duy nhất ở 1 mốc, nhưng mốc liền kề khác hẳn). Outro THẬT thì ngược lại:
# vì là 1 vùng hình ảnh lặp/tĩnh kéo dài, nó khớp ở NHIỀU mốc liên tiếp cùng
# lúc (đã kiểm chứng thực tế: outro ngắn của app A khớp ở cả 2 mốc 0.5s và
# 1.0s cùng lúc). Vì vậy: chỉ tính là khớp thật khi có ÍT NHẤT 2 mốc khác
# nhau (không phải 1 mốc duy nhất) đều khớp — lọc được trùng hợp ngẫu nhiên
# mà không cần biết trước outro dài bao nhiêu.
MIN_MATCHING_OFFSETS = 2


# Các độ lệch (giây) thử THÊM khi 2 video KHÔNG khớp được ở độ lệch = 0 —
# dùng cho trường hợp CÙNG 1 outro nhưng bị cắt ở ĐỘ DÀI KHÁC NHAU giữa các
# bản export (đã gặp thật: 1 video bị cắt cụt ngay giữa lúc chuyển sang thẻ
# outro, chỉ còn vài khung mờ ở mép cuối file; video khác có nguyên vẹn cả
# đoạn outro dài hơn hẳn) — khi đó "cùng 1 mốc tính từ cuối" ở 2 video lại
# là 2 THỜI ĐIỂM KHÁC NHAU trong outro, so trực tiếp sẽ không khớp dù thực
# ra cùng 1 outro. Thử dịch chuyển thời gian (cả 2 chiều) để tìm lại đúng
# điểm 2 video "cùng nhìn vào 1 chỗ" trong outro.
#
# Phạm vi dò độ lệch (giây) — không dịch xa hơn mốc này.
MAX_SHIFT_SECONDS = 8.0
# Thử NHIỀU độ lệch làm tăng rủi ro trùng hợp ngẫu nhiên (mỗi độ lệch là 1
# lượt "thử vận may" riêng) — đòi hỏi số mốc liền kề khớp NHIỀU HƠN mức
# thường (MIN_MATCHING_OFFSETS) để bù lại, chỉ chấp nhận bằng chứng chắc
# chắn hơn khi dùng độ lệch khác 0.
SHIFT_MIN_MATCHING_OFFSETS = MIN_MATCHING_OFFSETS + 1


def _shift_candidates(fps):
    """Danh sách độ lệch (giây) thử khi 2 video KHÔNG khớp được ở độ lệch =
    0 — PHẢI tính theo ĐÚNG bội số của 1/fps (lý do giống hệt _probe_offsets
    ở trên: dùng bước cố định như 0.04s dễ "trật khung hình" với video quay
    ở fps khác 25 — đã gặp thật, video 30fps chỉ khớp đúng ở độ lệch
    0.0333s/1 khung hình, thử 0.04s do làm tròn khác đi là trượt mất)."""
    frame = 1.0 / fps
    n = int(MAX_SHIFT_SECONDS / frame)
    positive = [round(frame * k, 5) for k in range(1, n + 1)]
    return positive + [-s for s in positive]


def _matching_run(tail_a, tail_b, threshold, shift):
    """Tìm đoạn (run) DÀI NHẤT các mốc LIỀN KỀ nhau (theo _probe_offsets
    của `tail_a`) mà `tail_a` khớp với `tail_b` đã dịch đi `shift` giây —
    tại mỗi mốc `off`, so khung hình tail_a[off] với khung
    hình tail_b[off + shift]. Trả về (run_len, offset_nhỏ_nhất_của_run)
    hoặc (0, None) nếu không có run nào."""
    offsets = _probe_offsets(tail_a["fps"])
    matched_flags = [
        _match(_tail_hash_at_offset(tail_a, off), _tail_hash_at_offset(tail_b, off + shift), threshold)
        for off in offsets
    ]
    best_len, best_start = 0, None
    run_len = 0
    for idx, is_match in enumerate(matched_flags):
        run_len = run_len + 1 if is_match else 0
        if run_len > best_len:
            best_len = run_len
            best_start = offsets[idx - run_len + 1]
    return best_len, best_start


def _best_matching_offset(tail_a, tail_b, threshold):
    """Trả về (offset, shift) — mốc NHỎ NHẤT (gần cuối video A nhất) mà A
    khớp với B, và độ lệch thời gian cần dịch B đi để khớp (0.0 nếu 2 video
    thẳng hàng, không cần dịch). Trả về None nếu không khớp được kiểu nào.

    Ưu tiên độ lệch = 0 trước (an toàn, đã kiểm chứng kỹ — chỉ cần
    MIN_MATCHING_OFFSETS mốc liền kề khớp là đủ). Chỉ khi độ lệch 0 không ra
    kết quả mới thử các độ lệch khác (xem _shift_candidates), với yêu cầu
    khớp CHẶT hơn (SHIFT_MIN_MATCHING_OFFSETS) để bù rủi ro trùng hợp ngẫu
    nhiên tăng lên do phải thử nhiều độ lệch.

    Lý do đòi hỏi "liền kề" (không phải bất kỳ N mốc nào khớp): đã gặp thật
    1 cặp khớp ở mốc 0.5s (outro thật) VÀ mốc 1.5s (trùng hợp ngẫu nhiên)
    nhưng KHÔNG khớp ở mốc 1.0s nằm giữa — outro thật là 1 vùng liên tục nên
    khớp đều ở các mốc kế tiếp nhau, còn trùng hợp ngẫu nhiên thường "nhảy
    cóc" kiểu vậy."""
    run_len, start = _matching_run(tail_a, tail_b, threshold, shift=0.0)
    if run_len >= MIN_MATCHING_OFFSETS:
        return start, 0.0

    # Mốc dò chỉ dày đặc/chính xác khung hình GẦN 0 CỦA CHÍNH VIDEO ĐANG LÀM
    # GỐC (_probe_offsets(tail["fps"])) — nếu video A có outro NGẮN (outro
    # nằm gần mốc 0 của A) còn video B có outro DÀI hơn (outro nằm xa mốc 0
    # của B), neo (anchor) theo lưới mốc của A khớp được, nhưng neo theo
    # lưới mốc (thưa/lệch khung hơn ở xa) của B thì trật — PHẢI thử cả 2
    # CHIỀU (lấy A làm gốc, và lấy B làm gốc) mới chắc chắn không bỏ sót,
    # đồng thời mỗi chiều dùng đúng fps của video làm gốc để không lệch
    # khung hình (xem _shift_candidates).
    best = None  # (run_len, offset_theo_A, shift)
    for shift in _shift_candidates(tail_a["fps"]):
        run_len, start = _matching_run(tail_a, tail_b, threshold, shift)
        if run_len >= SHIFT_MIN_MATCHING_OFFSETS and (best is None or run_len > best[0]):
            best = (run_len, start, shift)
    for shift in _shift_candidates(tail_b["fps"]):
        run_len, start_b = _matching_run(tail_b, tail_a, threshold, shift)
        if run_len >= SHIFT_MIN_MATCHING_OFFSETS and (best is None or run_len > best[0]):
            # start_b la moc cua B (B[start_b] khop A[start_b+shift]) -> quy
            # doi ve moc cua A + do lech can de dich B cho khop lai A.
            best = (run_len, start_b + shift, -shift)
    return (best[1], best[2]) if best else None


def _find_boundary_by_time(tail, other_tail, threshold, start_offset, shift=0.0):
    """Dò lùi dần TỪNG KHUNG HÌNH MỘT (đã có sẵn TOÀN BỘ khung hình trong
    `tail`/`other_tail`, xem _read_tail_hashes, nên đi thẳng từng khung cho
    kết quả CHÍNH XÁC TỚI TỪNG KHUNG HÌNH), bắt đầu từ `start_offset` (mốc
    đã CHẮC CHẮN khớp — chính là mốc dùng để gom nhóm).

    Ở MỖI mốc offset, so khung hình của `tail` (video đang xét) với khung
    hình của `other_tail` (video khác đã khớp cùng nhóm) ĐÃ DỊCH ĐI `shift`
    giây (0.0 nếu 2 video thẳng hàng, xem _best_matching_offset) — KHÔNG so
    1 video với chính các khung hình trước đó của nó (đã thử và SAI: outro
    có thể đổi hình RẤT NHANH theo từng khung — vd hiệu ứng chuyển cảnh/mờ
    chuyển động — khiến 2 khung liền kề trong CÙNG 1 video lệch nhau nhiều,
    làm việc dò lùi tưởng nhầm là "hết outro" quá sớm, dù thực ra 2 video
    vẫn đang cùng phát cùng 1 outro, đồng bộ khung hình với nhau — đã kiểm
    chứng thực tế: 2 video khớp khít ở TỪNG mốc CHÉO xuyên suốt outro (kể cả
    outro cực ngắn, đổi hình nhanh — app Vividix), trong khi tự so 1 video
    với khung hình liền trước của chính nó lại lệch hẳn).

    Trả về giây (tính từ ĐẦU video `tail`) bắt đầu outro."""
    duration, start_t, fps = tail["duration"], tail["start_t"], tail["fps"]
    if not tail["hashes"] or not other_tail["hashes"]:
        return duration - start_offset

    step = 1.0 / fps
    max_offset = min(MAX_OUTRO_LOOKBACK, duration - start_t)
    offset = start_offset
    last_match_offset = start_offset
    while offset <= max_offset:
        h = _tail_hash_at_offset(tail, offset)
        h_other = _tail_hash_at_offset(other_tail, offset + shift)
        if not _match(h, h_other, threshold):
            break
        last_match_offset = offset
        offset += step

    return max(duration - last_match_offset, duration - MAX_OUTRO_LOOKBACK)


# ============================================================================
# Dò outro cho video ĐƠN LẺ — không có video nào khác để so khớp chéo
# (xem find_outro_boundaries: trường hợp reason="none" ở trên). Trước đây
# gặp trường hợp này là CHỊU, giữ nguyên không cắt gì (an toàn nhưng vô dụng
# nếu người dùng chỉ có 1 video/app tại 1 thời điểm — phản hồi thực tế từ
# người dùng: tải nhiều video nhưng KHÁC app nhau, mỗi app chỉ 1 video, nên
# không video nào khớp được ai, không cắt được gì cả dù rõ ràng có outro).
#
# Cách nhận diện KHÔNG dựa vào so khớp chéo nữa mà dựa vào chính bản thân
# video đó có 2 đặc điểm outro thường có:
#   1. ĐIỂM CHUYỂN CẢNH rõ rệt gần cuối video (nội dung thật chuyển sang
#      1 màn hình khác hẳn — thường là card tĩnh/hiệu ứng đồ hoạ).
#   2. Card đó có dấu hiệu ĐẶC TRƯNG của outro quảng cáo app: badge cửa hàng
#      ứng dụng ("GET IT ON Google Play" / "Download on the App Store") —
#      2 mẫu này gần như CHUẨN HOÁ, giống hệt nhau ở MỌI app trên thế giới,
#      khác hẳn logo/tên app (mỗi nơi 1 kiểu, không so mẫu chung được).
#
# Chỉ cắt khi có ĐIỂM CHUYỂN CẢNH — badge chỉ để TĂNG độ tin cậy (không bắt
# buộc, vì không phải outro nào cũng có badge — có thể chỉ có chữ/logo tự
# thiết kế, xem phản hồi người dùng). Vẫn giữ triết lý AN TOÀN: không tìm
# được điểm chuyển cảnh nào đủ rõ thì KHÔNG cắt, giống hệt trường hợp
# reason="none" hiện tại.
SOLO_SCENE_LOOKBACK = 15.0
# Ngưỡng chênh lệch histogram màu (Bhattacharyya, 0 = giống hệt, 1 = khác
# hẳn) giữa 2 khung hình liền kề để coi là "chuyển cảnh". Xác định bằng
# cách đo thực tế trên video mẫu: chuyển cảnh thật (vào outro) luôn ≥ 0.35,
# trong khi nhiễu/chuyển động bình thường trong nội dung thật chỉ ~0.02-0.15
# — để ngưỡng 0.2 ở GIỮA 2 vùng này, chừa biên độ an toàn cả 2 phía.
SOLO_SCENE_CUT_THRESHOLD = 0.2
# Ngưỡng độ khớp mẫu badge (TM_CCOEFF_NORMED, 1 = khớp tuyệt đối). Đo thực
# tế: badge thật khớp ≥ 0.65 (dù ảnh mẫu chụp ở độ phân giải khác hẳn video
# đang xét), vùng nội dung thường không vượt quá ~0.5.
SOLO_BADGE_MATCH_THRESHOLD = 0.6
# Các tỉ lệ thu nhỏ ảnh mẫu badge thử khi so khớp — badge trong video có
# thể to/nhỏ rất khác nhau tuỳ độ phân giải + cách dàn trang của từng app.
SOLO_BADGE_SCALES = [round(s, 3) for s in np.arange(0.12, 1.01, 0.04)]


def _load_badge_templates():
    """Đọc sẵn các ảnh mẫu badge (Google Play, App Store...) trong
    assets/badges/ — gọi 1 lần, cache lại (xem find_solo_outro_boundary),
    vì đây là ảnh cố định đi kèm code, không đổi giữa các lần gọi."""
    templates = []
    if not BADGE_TEMPLATES_DIR.exists():
        return templates
    for f in sorted(BADGE_TEMPLATES_DIR.glob("*.*")):
        img = cv2.imread(str(f))
        if img is not None:
            templates.append(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    return templates


_BADGE_TEMPLATES_CACHE = None


def _badge_templates():
    global _BADGE_TEMPLATES_CACHE
    if _BADGE_TEMPLATES_CACHE is None:
        _BADGE_TEMPLATES_CACHE = _load_badge_templates()
    return _BADGE_TEMPLATES_CACHE


def _frame_color_hist(frame_bgr):
    """Histogram màu 2D (Hue+Saturation, 32 bin/kênh) đã chuẩn hoá — dùng để
    so ĐỘ KHÁC BIỆT giữa 2 khung hình liền kề (_hist_diff), nhạy với đổi
    CẢNH (màu sắc/bố cục thay đổi hẳn) hơn nhiều so với so màu trung bình
    theo lưới (_color_thumb, dùng cho so khớp CHÉO giữa 2 video khác nhau ở
    trên) — ở đây cần cái ngược lại: PHÂN BIỆT rõ 2 khung hình khác cảnh,
    không cần bền với chuyển động/hiệu ứng nhỏ như _color_thumb."""
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    return hist


def _hist_diff(h1, h2):
    return float(cv2.compareHist(h1, h2, cv2.HISTCMP_BHATTACHARYYA))


def _badge_best_score(frame_gray, templates, scales):
    """Điểm khớp badge CAO NHẤT trên 1 khung hình, thử tất cả mẫu × tất cả
    tỉ lệ thu nhỏ (xem SOLO_BADGE_SCALES) — trả về 0.0 nếu không có mẫu nào
    nạp được (thư mục assets/badges rỗng) thay vì lỗi, để tính năng còn lại
    (dò chuyển cảnh) vẫn chạy được kể cả thiếu ảnh mẫu."""
    if not templates:
        return 0.0
    fh, fw = frame_gray.shape[:2]
    best = 0.0
    for tmpl in templates:
        th, tw = tmpl.shape[:2]
        for scale in scales:
            w, h = int(tw * scale), int(th * scale)
            if w < 8 or h < 8 or w >= fw or h >= fh:
                continue
            resized = cv2.resize(tmpl, (w, h), interpolation=cv2.INTER_AREA)
            res = cv2.matchTemplate(frame_gray, resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            if max_val > best:
                best = max_val
    return best


def find_solo_outro_boundary(path, duration, fps,
                              lookback_seconds=SOLO_SCENE_LOOKBACK,
                              cut_threshold=SOLO_SCENE_CUT_THRESHOLD,
                              badge_threshold=SOLO_BADGE_MATCH_THRESHOLD):
    """Dò outro cho 1 video ĐƠN LẺ, không cần video nào khác để so khớp chéo
    — xem giải thích cách làm ở khối comment phía trên. Đọc TUẦN TỰ (giống
    _read_tail_hashes) để tránh lỗi tua ngẫu nhiên gần cuối file.

    Trả về dict {"outro_start": giây, "confidence": "badge" | "scene"} nếu
    tìm được ranh giới đủ tin cậy, hoặc None nếu không tìm được gì (giữ
    nguyên, không cắt — an toàn)."""
    cap = cv2.VideoCapture(str(path))
    start_t = max(duration - lookback_seconds, 0.0)
    cap.set(cv2.CAP_PROP_POS_MSEC, start_t * 1000)

    prev_hist = None
    # cut_candidates: list các mốc "giây trước khi kết thúc" mà tại đó phát
    # hiện chuyển cảnh — chỉ giữ giây (số thực nhẹ), KHÔNG giữ khung hình
    # gốc (tốn RAM, xem lý do tương tự _read_tail_hashes: server miễn phí
    # RAM rất hạn chế).
    cut_candidates = []
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        hist = _frame_color_hist(frame)
        if prev_hist is not None:
            diff = _hist_diff(prev_hist, hist)
            if diff >= cut_threshold:
                t = start_t + idx / fps
                cut_candidates.append(duration - t)
        prev_hist = hist
        idx += 1
    cap.release()

    if not cut_candidates:
        return None

    # Lấy mốc GẦN CUỐI VIDEO NHẤT (nhỏ nhất) trong số các điểm chuyển cảnh —
    # đây chính là điểm chuyển vào "cảnh cuối cùng" (outro, nếu có). Các
    # điểm chuyển cảnh XA hơn (vd giữa 2 đoạn nội dung thật) bị bỏ qua, kể
    # cả khi độ chênh lệch màu ở đó lớn hơn — đã kiểm chứng thực tế: 1 video
    # có thể có nhiều điểm chuyển cảnh trong phần nội dung, chỉ điểm GẦN
    # CUỐI NHẤT mới đáng tin là ranh giới outro.
    outro_start_before_end = min(cut_candidates)
    outro_start = max(duration - outro_start_before_end, 0.0)

    # Xác nhận thêm bằng badge — chỉ cần ĐỌC LẠI 1 đoạn NGẮN (từ điểm chuyển
    # cảnh tới hết video), không phải đọc lại toàn bộ lookback_seconds như
    # lần quét đầu.
    templates = _badge_templates()
    badge_found = False
    if templates:
        cap2 = cv2.VideoCapture(str(path))
        cap2.set(cv2.CAP_PROP_POS_MSEC, outro_start * 1000)
        checked = 0
        while checked < int(round(outro_start_before_end * fps)) + 2:
            ok, frame = cap2.read()
            if not ok:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            score = _badge_best_score(gray, templates, SOLO_BADGE_SCALES)
            if score >= badge_threshold:
                badge_found = True
                break
            checked += 1
        cap2.release()

    return {
        "outro_start": outro_start,
        "confidence": "badge" if badge_found else "scene",
    }


# ============================================================================
# Thư viện outro đối thủ ĐÃ TỪNG NHẬN DIỆN ĐƯỢC — xem KNOWN_OUTRO_DIR.
def list_known_outros():
    return sorted(KNOWN_OUTRO_DIR.glob("*.mp4"), key=lambda p: p.name.lower())


def _match_against_known_library(path, duration, fps, threshold, safety_margin_seconds):
    """So video `path` (không khớp được video nào khác trong mẻ đang xử lý)
    với TỪNG outro đã lưu trong thư viện — dùng LẠI đúng cơ chế so khớp
    chéo (_read_tail_hashes/_best_matching_offset/_find_boundary_by_time)
    như so giữa 2 video thật, chỉ khác nguồn so là thư viện thay vì video
    khác trong mẻ. Trả về giây bắt đầu outro (đã trừ safety_margin) nếu
    khớp đủ tin cậy, hoặc None nếu không khớp gì / thư viện đang rỗng."""
    known = list_known_outros()
    if not known:
        return None
    tail = _read_tail_hashes(path, duration, fps, MAX_OUTRO_LOOKBACK)
    if not tail["hashes"]:
        return None

    best_boundary = None
    for k in known:
        k_info = ffprobe_info(k)
        if not k_info["duration"]:
            continue
        # Outro luu trong thu vien la doan NGAN da cat san (khong phai ca
        # video) - doc toan bo lam "duoi" de so khop, khong can lookback
        # rieng.
        k_tail = _read_tail_hashes(k, k_info["duration"], k_info["fps"] or 30, k_info["duration"])
        if not k_tail["hashes"]:
            continue
        res = _best_matching_offset(tail, k_tail, threshold)
        if res is None:
            continue
        anchor_offset, anchor_shift = res
        boundary = _find_boundary_by_time(tail, k_tail, threshold, anchor_offset, anchor_shift)
        if best_boundary is None or boundary < best_boundary:
            best_boundary = boundary

    if best_boundary is None:
        return None
    candidate_start = max(best_boundary - safety_margin_seconds, 0.0)
    if candidate_start < MIN_CONTENT_SECONDS:
        return None
    return candidate_start


def _save_to_known_library(video_path, outro_start, duration, threshold, workdir):
    """Trích đúng đoạn outro [outro_start, duration] của `video_path` ra
    thành 1 clip ngắn, lưu vào thư viện — NHƯNG bỏ qua nếu đoạn này đã
    khá giống 1 outro có sẵn trong thư viện rồi (tránh thư viện phình to
    vô ích vì lưu trùng lặp nhiều lần cùng 1 outro thực tế). Lỗi ở bước
    này KHÔNG được làm hỏng video đang xử lý — gọi hàm này trong try/except
    ở nơi gọi (xem _process_one_video)."""
    fps = ffprobe_info(video_path)["fps"] or 30
    new_tail = _read_tail_hashes(video_path, duration, fps, duration - outro_start)
    if not new_tail["hashes"]:
        return None

    for k in list_known_outros():
        k_info = ffprobe_info(k)
        if not k_info["duration"]:
            continue
        k_tail = _read_tail_hashes(k, k_info["duration"], k_info["fps"] or 30, k_info["duration"])
        if not k_tail["hashes"]:
            continue
        if _best_matching_offset(new_tail, k_tail, threshold) is not None:
            return None  # da co outro nay trong thu vien roi, khong luu trung

    info = ffprobe_info(video_path)
    target_spec = {"width": info["width"] or 1280, "height": info["height"] or 720, "fps": info["fps"] or 30}
    clips = split_clips(
        video_path, [(outro_start, duration)], workdir, info["has_audio"], False, 0.0,
        target_spec, name_prefix=f"newknown{uuid.uuid4().hex[:8]}",
    )
    if not clips:
        return None
    out_path = KNOWN_OUTRO_DIR / f"known_{uuid.uuid4().hex[:10]}.mp4"
    clips[0].rename(out_path)
    for c in clips[1:]:
        c.unlink(missing_ok=True)
    return out_path


def find_outro_boundaries(paths, threshold=DEFAULT_MATCH_THRESHOLD, safety_margin_seconds=0.15,
                           enable_solo_detection=True):
    """Xác định mốc thời gian bắt đầu outro đối thủ cho mỗi video, bằng cách
    so khớp hình ảnh CHÉO giữa các video trong cùng danh sách `paths`ở NHIỀU
    mốc thời gian khác nhau (xem _probe_offsets — outro thực tế dài
    rất khác nhau tuỳ app, từ ~1 giây tới vài giây). Tự gom nhóm theo độ
    giống nhau — tải lên trộn lẫn nhiều app/đối thủ khác nhau trong 1 lần
    vẫn tự tách đúng thành từng nhóm riêng, không cần tự sắp xếp trước.

    `safety_margin_seconds`: chỉ áp dụng cho video ĐÃ xác định được ranh
    giới ("matched") — lùi ranh giới đó thêm 1 chút VÀO PHÍA NỘI DUNG THẬT
    (cắt dư 1 ít nội dung thay vì cắt thiếu outro). Thuật toán so khớp màu
    theo lưới (_color_thumb) tìm ranh giới khá chính xác nhưng KHÔNG tuyệt
    đối 100% mọi trường hợp (vd outro có chuyển động/hiệu ứng phức tạp) —
    thà mất thêm vài phần mười giây nội dung thật (thường không ai nhận ra
    trên 1 video quảng cáo vài chục giây) còn hơn để sót 1 khung outro lộ
    liễu ở cuối video. KHÔNG áp dụng cho video "none" (không khớp được ai)
    — ở đó không có ranh giới nào để lùi cả.

    Trả về list dict cùng độ dài `paths`:
      - outro_start: giây bắt đầu outro trong video gốc, None nếu không cắt.
      - reason: "matched" (khớp được với video khác trong cùng mẻ — chắc
                chắn nhất) |
                "library_match" (không khớp được video nào trong mẻ, nhưng
                khớp với 1 outro đã có sẵn trong thư viện — cũng là so
                khớp chéo nên khá chắc chắn, chỉ xếp sau "matched" vì thư
                viện có thể chứa outro hơi khác bản đang xét) |
                "solo_badge" (không khớp được video nào khác/thư viện,
                nhưng dò được điểm chuyển cảnh gần cuối VÀ xác nhận có
                badge cửa hàng ứng dụng — khá tin cậy) |
                "solo_scene" (chỉ dò được điểm chuyển cảnh gần cuối, KHÔNG
                thấy badge xác nhận — kém tin cậy nhất trong các loại có
                cắt, nên soát lại kết quả) |
                "none" (không tìm được dấu hiệu outro nào — GIỮ NGUYÊN,
                không đoán liều).

    `enable_solo_detection`: tắt đi (False) để chỉ dùng so khớp chéo như
    trước đây — dùng khi cần so sánh/kiểm tra hồi quy, bình thường luôn để
    True.
    """
    n = len(paths)
    infos = [ffprobe_info(p) for p in paths]
    durations = [info["duration"] for info in infos]
    # Đọc TUẦN TỰ 1 lần/video (xem _read_tail_hashes) — dùng chung cho cả
    # bước dò offset lẫn bước dò ranh giới bên dưới, khỏi phải mở lại video
    # nhiều lần (trước đây mỗi mốc thời gian mở video riêng 1 lần, khá tốn).
    tails = [
        _read_tail_hashes(paths[i], durations[i], infos[i]["fps"] or 30, MAX_OUTRO_LOOKBACK)
        for i in range(n)
    ]

    groups = []
    for i in range(n):
        if not tails[i]["hashes"]:
            continue
        placed = False
        for g in groups:
            if any(_best_matching_offset(tails[i], tails[j], threshold) is not None for j in g):
                g.add(i)
                placed = True
                break
        if not placed:
            groups.append({i})

    results = [{"outro_start": None, "reason": "none"} for _ in range(n)]
    for g in groups:
        if len(g) < 2:
            continue
        for i in g:
            # Dò ranh giới với TỪNG thành viên khác trong nhóm (không chỉ 1
            # video cố định — nhóm được gộp theo kiểu "bắt cầu": A khớp B,
            # B khớp C -> A,B,C cùng nhóm dù A có thể KHÔNG khớp trực tiếp
            # C), rồi lấy kết quả CẮT ĐƯỢC NHIỀU NHẤT (content_end nhỏ nhất)
            # trong số đó — không phải kết quả có mốc neo (anchor) gần cuối
            # nhất. Lý do: 1 video "bạn so sánh" có thể tự nó cũng bị cắt
            # cụt/thiếu 1 phần outro (đã gặp thật), khiến việc dò lùi dừng
            # quá sớm dù video đang xét vẫn còn outro thật kéo dài hơn — so
            # với NHIỀU video khác rồi lấy bằng chứng "đi xa nhất" (nhiều
            # khung hình khớp liên tiếp nhất) mới đáng tin cậy nhất, tránh
            # cắt sót do "bạn so sánh" không đủ dữ liệu.
            best_boundary = None
            for j in g:
                if j == i:
                    continue
                res = _best_matching_offset(tails[i], tails[j], threshold)
                if res is None:
                    continue
                anchor_offset, anchor_shift = res
                boundary = _find_boundary_by_time(
                    tails[i], tails[j], threshold, anchor_offset, anchor_shift,
                )
                if best_boundary is None or boundary < best_boundary:
                    best_boundary = boundary
            if best_boundary is None:
                continue
            candidate_start = max(best_boundary - safety_margin_seconds, 0.0)
            # An toàn: lấy kết quả "cắt được NHIỀU NHẤT" trong cả nhóm (xem
            # comment phía trên) có rủi ro thật — nếu dù chỉ 1 VIDEO KHÁC
            # trong nhóm có nội dung giống bất thường (trùng lặp/gần trùng,
            # không chỉ trùng đúng đoạn outro), việc dò lùi có thể chạy quá
            # xa, khiến ranh giới tính ra nuốt gần hết/hết video — đã gặp
            # thật (báo lỗi thực tế): 1 video trong mẻ 30 video làm ghép
            # clip lỗi vì đoạn nội dung còn lại gần như rỗng. Không tin kết
            # quả nếu nội dung còn lại dưới MIN_CONTENT_SECONDS — coi như
            # KHÔNG xác định được (giữ nguyên "none"), an toàn hơn cắt sai.
            if candidate_start < MIN_CONTENT_SECONDS:
                continue
            results[i] = {"outro_start": candidate_start, "reason": "matched"}

    # Video nào vẫn "none" (không khớp được video nào khác trong CÙNG mẻ) —
    # thử so với THƯ VIỆN outro đã từng nhận diện được trước đó (vẫn là so
    # khớp chéo, chỉ khác nguồn so — đáng tin hơn lớp dò-đơn-lẻ bên dưới,
    # nên ưu tiên chạy trước).
    for i in range(n):
        if results[i]["reason"] != "none":
            continue
        candidate_start = _match_against_known_library(
            paths[i], durations[i], infos[i]["fps"] or 30, threshold, safety_margin_seconds,
        )
        if candidate_start is None:
            continue
        results[i] = {"outro_start": candidate_start, "reason": "library_match"}

    # Video nào vẫn "none" sau CẢ 2 lớp trên — thử thêm 1 lớp nhận diện
    # KHÔNG cần so khớp chéo (xem find_solo_outro_boundary phía trên: dò
    # điểm chuyển cảnh gần cuối + xác nhận bằng badge cửa hàng ứng dụng).
    # Đây là lớp dự phòng CUỐI CÙNG, kém tin cậy nhất trong 3 lớp.
    if enable_solo_detection:
        for i in range(n):
            if results[i]["reason"] != "none":
                continue
            solo = find_solo_outro_boundary(paths[i], durations[i], infos[i]["fps"] or 30)
            if solo is None:
                continue
            outro_start = max(solo["outro_start"] - safety_margin_seconds, 0.0)
            reason = "solo_badge" if solo["confidence"] == "badge" else "solo_scene"
            results[i] = {"outro_start": outro_start, "reason": reason}

    return results


def _process_one_video(i, p, boundary, own_outro_path, own_info, clips_dir, workdir, strip_audio,
                        tail_match_threshold=DEFAULT_MATCH_THRESHOLD):
    """Xử lý 1 video: cắt outro (nếu xác định được) + gắn outro của mình
    (NẾU có chọn — `own_outro_path`/`own_info` có thể là None, khi đó chỉ
    cắt outro đối thủ, không gắn gì thêm vào cuối). Tách riêng thành hàm để
    chạy song song nhiều video cùng lúc (xem process_outro_swap) — mỗi
    video dùng tên file riêng biệt (theo `i`) nên chạy đồng thời không
    đụng nhau."""
    info = ffprobe_info(p)
    if own_info is not None:
        # Không cần đồng nhất kích thước với các video khác (không ghép
        # chéo nội dung giữa các video như remix_core.py) — nhưng PHẢI
        # chọn khung hình chuẩn theo bên nào có ĐỘ PHÂN GIẢI CAO HƠN giữa
        # video nguồn và outro của bạn. Nếu luôn lấy theo video nguồn
        # (thường thấp hơn, vì là file tải về từ đối thủ) thì outro chất
        # lượng cao của bạn sẽ bị co nhỏ xuống theo, gây mờ — đã gặp lỗi
        # này trên thực tế.
        target_spec = _pick_larger_spec(info, own_info)
        want_audio = (not strip_audio) and (info["has_audio"] or own_info["has_audio"])
    else:
        target_spec = {"width": info["width"] or 1280, "height": info["height"] or 720, "fps": info["fps"] or 30}
        want_audio = (not strip_audio) and info["has_audio"]

    content_end = boundary["outro_start"] if boundary["outro_start"] is not None else info["duration"]
    if content_end < MIN_CONTENT_SECONDS:
        # An toàn: nếu ranh giới xác định được lại NUỐT GẦN HẾT/HẾT video
        # (dưới 1 giây nội dung còn lại) — gần như chắc chắn là nhận diện
        # sai (không video quảng cáo thật nào chỉ có <1s nội dung thật),
        # không phải ai đó cố tình tải lên 1 video toàn outro. Trả về giữ
        # nguyên cả video thay vì tạo ra 1 đoạn nội dung RỖNG — đã gặp thật:
        # đoạn rỗng khiến bước ghép clip (concat) sau đó lỗi hẳn ("Output
        # file does not contain any stream"), làm HỎNG CẢ MẺ xử lý dù chỉ 1
        # video trong đó bị nhận diện sai.
        content_end = info["duration"]
        boundary = {"outro_start": None, "reason": "none"}

    # saved_to_library: True CHỈ khi _save_to_known_library thực sự lưu ra
    # 1 file mới (trả về Path) — False nếu không đủ điều kiện thử lưu, HOẶC
    # có thử nhưng bị coi là trùng lặp với outro đã có sẵn (trả về None),
    # HOẶC lỗi. Trả ra ngoài (khác trước đây — âm thầm bỏ qua) để app.py
    # báo cho người dùng biết CHÍNH XÁC video nào vừa được tự động thêm vào
    # thư viện — phản hồi thật: người dùng không biết việc này đang tự động
    # xảy ra, tưởng thiếu 1 nút "lưu vào thư viện".
    saved_to_library = False
    if boundary["reason"] in ("matched", "solo_badge") and content_end < info["duration"] - 0.05:
        # Cắt được ĐỦ TIN CẬY (khớp chéo trong mẻ, hoặc dò-đơn-lẻ có badge
        # xác nhận — KHÔNG lưu từ "library_match"/"solo_scene" để tránh
        # thư viện tự lưu lại chính nó hoặc lưu outro kém tin cậy) — tự lưu
        # đoạn outro vào thư viện dùng chung, để lần sau video khác cùng
        # outro này (dù không có gì so khớp chéo trong mẻ) vẫn nhận ra
        # được. Lỗi ở bước này KHÔNG được làm hỏng video đang xử lý.
        try:
            saved_path = _save_to_known_library(p, content_end, info["duration"], tail_match_threshold, clips_dir)
            saved_to_library = saved_path is not None
        except Exception:
            pass

    all_clips = split_clips(
        p, [(0.0, content_end)], clips_dir, info["has_audio"], want_audio, 0.0,
        target_spec, name_prefix=f"content{i:02d}",
    )
    if own_outro_path is not None:
        all_clips += split_clips(
            own_outro_path, [(0.0, own_info["duration"])], clips_dir, own_info["has_audio"],
            want_audio, 0.0, target_spec, name_prefix=f"ownoutro{i:02d}",
        )

    out_path = workdir / f"outro_swap_{i + 1:02d}.mp4"
    concat_clips(all_clips, out_path, workdir)

    cut_seconds = (info["duration"] - content_end) if boundary["outro_start"] is not None else 0.0
    for c in all_clips:
        c.unlink(missing_ok=True)

    return {
        "path": out_path, "outro_cut_seconds": cut_seconds, "reason": boundary["reason"],
        "saved_to_library": saved_to_library,
    }


def process_outro_swap(paths, own_outro_path, workdir, strip_audio,
                        tail_match_threshold=DEFAULT_MATCH_THRESHOLD, on_source=None,
                        max_workers=1, safety_margin_seconds=0.15, enable_solo_detection=True,
                        boundaries=None):
    """Với mỗi video trong `paths`: cắt outro đối thủ (nếu xác định được),
    rồi gắn `own_outro_path` vào cuối — GIỮ NGUYÊN nội dung gốc, không xáo
    trộn, không ghép với video khác. Mỗi video đầu vào cho ra đúng 1 video
    kết quả.

    `own_outro_path` có thể là None — khi đó CHỈ cắt outro đối thủ (nếu xác
    định được), KHÔNG gắn thêm gì vào cuối. Dùng cho người chỉ cần bỏ outro
    đối thủ đi (vd để tự gắn trademark riêng, hoặc không cần outro nào cả).

    `safety_margin_seconds`: xem find_outro_boundaries() — cắt dư thêm 1 ít
    vào nội dung thật để chắc chắn không còn sót khung outro nào ở cuối.

    `boundaries`: truyền sẵn kết quả find_outro_boundaries() nếu ĐÃ tính từ
    trước (vd lấy từ cache — xem app.py, dò/cắt outro là bước NẶNG nhất
    trong cả quy trình, trong khi kết quả không đổi nếu video đầu vào không
    đổi, dù người dùng đổi outro của mình/trademark rồi bấm "Xử lý" lại —
    phản hồi thật: gen lại cùng 1 mẻ video tốn rất nhiều thời gian dù chỉ
    đổi 1 chút cấu hình phía sau bước dò outro). None (mặc định) = tự tính
    như trước đây, không có gì thay đổi cho nơi gọi không cần cache.

    Có thể xử lý SONG SONG tối đa `max_workers` video cùng lúc để tận dụng
    nhiều lõi CPU — nhưng MẶC ĐỊNH LÀ 1 (tuần tự, an toàn) vì mỗi video chạy
    song song là 1 tiến trình ffmpeg riêng, tốn thêm RAM đáng kể; máy chủ
    miễn phí (RAM rất hạn chế) đã từng bị crash giữa chừng khi để giá trị
    này cao — chỉ tăng lên khi chắc chắn đang chạy trên server đủ mạnh.

    on_source(done_count, total, name, result) được gọi mỗi khi 1 video xử
    lý xong (theo thứ tự HOÀN THÀNH, không nhất thiết theo thứ tự tải lên,
    vì chạy song song) — để UI báo tiến độ + cảnh báo.

    Trả về list dict (đúng thứ tự `paths`): {"path": Path video kết quả,
    "outro_cut_seconds": số giây outro đối thủ đã cắt (0 nếu không cắt được
    gì), "reason": xem find_outro_boundaries(), "saved_to_library": True nếu
    outro vừa cắt được TỰ ĐỘNG thêm vào thư viện dùng chung (KNOWN_OUTRO_DIR)
    — chỉ xảy ra khi reason là "matched"/"solo_badge" VÀ chưa có sẵn outro
    giống hệt trong thư viện, xem _process_one_video/_save_to_known_library}.
    """
    workdir = Path(workdir)
    clips_dir = workdir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    if boundaries is None:
        boundaries = find_outro_boundaries(
            paths, tail_match_threshold, safety_margin_seconds, enable_solo_detection,
        )
    own_info = ffprobe_info(own_outro_path) if own_outro_path is not None else None

    made = [None] * len(paths)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _process_one_video, i, p, b, own_outro_path, own_info, clips_dir, workdir, strip_audio,
                tail_match_threshold,
            ): i
            for i, (p, b) in enumerate(zip(paths, boundaries))
        }
        done_count = 0
        for future in concurrent.futures.as_completed(futures):
            i = futures[future]
            try:
                result = future.result()
            except Exception as e:
                # 1 video lỗi (vd ffmpeg gặp file hỏng) KHÔNG được làm sập
                # cả mẻ — ghi nhận lỗi RIÊNG cho đúng video này, các video
                # khác trong mẻ vẫn tiếp tục xử lý bình thường (đã gặp
                # thật: 1 video lỗi làm mất hết tiến độ 29 video còn lại
                # trong mẻ 30 video, dù chúng không hề có vấn đề gì).
                result = {"path": None, "outro_cut_seconds": 0.0, "reason": "error", "error": str(e)}
            made[i] = result
            done_count += 1
            if on_source:
                on_source(done_count, len(paths), paths[i].name, result)

    return made
