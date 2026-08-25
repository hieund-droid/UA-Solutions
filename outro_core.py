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

  Video nào không khớp được với video nào khác (vd chỉ tải lên 1 video duy
  nhất, hoặc không tìm được video nào khác cùng app trong mẻ tải lên) sẽ
  KHÔNG cắt gì cả, giữ nguyên toàn bộ — chủ động chọn AN TOÀN thay vì đoán
  liều (vd cắt cảnh cuối cùng): với số lượng lớn video trộn lẫn, rất có thể
  1 video không khớp được ai đơn giản vì nó KHÔNG HỀ CÓ outro, nên đoán liều
  dễ cắt nhầm vào nội dung thật hơn là giúp ích.

Dùng module (import từ app.py):
    process_outro_swap(paths, own_outro_path, workdir, strip_audio)

Yêu cầu: ffmpeg, ffprobe trong PATH (giống remix_core.py).
"""

import concurrent.futures
from pathlib import Path

import cv2
import numpy as np

from remix_core import _grab_frame_bgr, concat_clips, ffprobe_info, split_clips

# Các mốc giây tính từ cuối video dùng để "dò thử" xem 2 video có outro
# chung không. DÙNG NHIỀU MỐC (không phải 1 mốc cố định) vì outro thực tế
# dài rất khác nhau tuỳ app — đã gặp thật: outro app A chỉ ~1 giây (dò ở mốc
# 1.5s sẽ trượt hẳn qua, so sánh nhầm sang nội dung phía trước, làm gãy toàn
# bộ việc nhận diện), outro app B dài ~3-4 giây. Dò đủ nhiều mốc để bắt được
# cả 2 trường hợp mà không cần biết trước outro app nào dài bao nhiêu.
CANDIDATE_PROBE_OFFSETS = [0.5, 1.0, 1.5, 2.5, 4.0]
# Bước dò lùi dần khi tìm ranh giới chính xác (giây).
SEARCH_STEP = 0.5
# Không dò lùi quá xa mốc này — outro thực tế không dài tới mức này, nếu
# dò xa hơn mà vẫn khớp thì dừng lại để tránh nuốt nhầm nội dung thật.
MAX_OUTRO_LOOKBACK = 20.0
# Ngưỡng mặc định cho _match() — xem lý do dùng "màu trung bình theo lưới"
# thay vì so vân ảnh (perceptual hash) ngay bên dưới.
DEFAULT_MATCH_THRESHOLD = 15


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


def _sample_hash(path, t):
    frame = _grab_frame_bgr(path, max(t, 0.0))
    return _color_thumb(frame) if frame is not None else None


def _match(h1, h2, threshold):
    if h1 is None or h2 is None:
        return False
    return float(np.abs(h1 - h2).mean()) <= threshold


def _refine_boundary(path, ref_hash, threshold, known_match_t, known_mismatch_t):
    """Thu hẹp khoảng [known_mismatch_t, known_match_t] bằng chia đôi để tìm
    ranh giới chính xác hơn giữa nội dung (không khớp) và outro (khớp)."""
    lo, hi = known_mismatch_t, known_match_t
    for _ in range(5):
        mid = (lo + hi) / 2
        h = _sample_hash(path, mid)
        if _match(h, ref_hash, threshold):
            hi = mid
        else:
            lo = mid
    return hi



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


def _multi_probe_hashes(path, duration):
    """Hash tại NHIỀU mốc thời gian khác nhau trước khi kết thúc (xem
    CANDIDATE_PROBE_OFFSETS) — để bắt được cả outro rất ngắn lẫn outro dài
    hơn, không cố định 1 mốc duy nhất. Trả về dict {offset: hash}."""
    hashes = {}
    for off in CANDIDATE_PROBE_OFFSETS:
        t = duration - off
        if t > 0:
            hashes[off] = _sample_hash(path, t)
    return hashes


def _best_matching_offset(hashes_a, hashes_b, threshold):
    """Trả về mốc NHỎ NHẤT (gần cuối video nhất) mà 2 video khớp nhau — chỉ
    khi có ÍT NHẤT `MIN_MATCHING_OFFSETS` mốc LIỀN KỀ nhau (trong thứ tự
    CANDIDATE_PROBE_OFFSETS) cùng khớp, KHÔNG phải bất kỳ 2 mốc nào bất kỳ.

    Lý do đòi hỏi "liền kề": đã gặp thật 1 cặp khớp ở mốc 0.5s (outro thật)
    VÀ mốc 1.5s (trùng hợp ngẫu nhiên) nhưng KHÔNG khớp ở mốc 1.0s nằm giữa
    — outro thật là 1 vùng liên tục nên khớp đều ở các mốc kế tiếp nhau,
    còn trùng hợp ngẫu nhiên thường "nhảy cóc" kiểu vậy. Yêu cầu liền kề lọc
    được ca này mà vẫn giữ đúng các outro ngắn (chỉ khớp ở 2 mốc đầu, liền
    kề nhau) hay dài (khớp ở nhiều mốc liên tiếp)."""
    offsets_sorted = sorted(hashes_a.keys())
    matched_flags = [_match(hashes_a[off], hashes_b.get(off), threshold) for off in offsets_sorted]

    best = None
    run_len = 0
    for idx, is_match in enumerate(matched_flags):
        run_len = run_len + 1 if is_match else 0
        if run_len >= MIN_MATCHING_OFFSETS:
            run_start = offsets_sorted[idx - run_len + 1]
            if best is None or run_start < best:
                best = run_start
    return best


def _find_boundary_by_time(path, ref_hash, threshold, duration, start_offset):
    """Dò lùi dần theo thời gian TỪ `start_offset` (mốc đã CHẮC CHẮN khớp —
    chính là mốc dùng để gom nhóm), tìm mốc mà hình ảnh KHÔNG còn khớp với
    `ref_hash` nữa — đó là điểm bắt đầu outro.

    KHÔNG dò bắt đầu từ sát mép cuối file: OpenCV đọc khung hình trong
    khoảng dưới ~0.3 giây cuối file thường không ổn định (nhiễu/giải mã
    sai), dễ báo "không khớp" giả trong khi outro thực tế vẫn kéo dài tới
    hết file — `start_offset` (lấy từ bước gom nhóm) đã né được vùng này."""
    cursor = max(0.0, duration - start_offset)
    last_match = cursor
    limit = max(0.0, duration - MAX_OUTRO_LOOKBACK)
    while cursor > limit:
        h = _sample_hash(path, cursor)
        if _match(h, ref_hash, threshold):
            last_match = cursor
            cursor -= SEARCH_STEP
        else:
            return _refine_boundary(path, ref_hash, threshold, last_match, cursor)
    return limit  # khớp tới tận giới hạn dò -> cắt tại giới hạn cho an toàn


def find_outro_boundaries(paths, threshold=DEFAULT_MATCH_THRESHOLD):
    """Xác định mốc thời gian bắt đầu outro đối thủ cho mỗi video, bằng cách
    so khớp hình ảnh CHÉO giữa các video trong cùng danh sách `paths`ở NHIỀU
    mốc thời gian khác nhau (xem CANDIDATE_PROBE_OFFSETS — outro thực tế dài
    rất khác nhau tuỳ app, từ ~1 giây tới vài giây). Tự gom nhóm theo độ
    giống nhau — tải lên trộn lẫn nhiều app/đối thủ khác nhau trong 1 lần
    vẫn tự tách đúng thành từng nhóm riêng, không cần tự sắp xếp trước.

    Trả về list dict cùng độ dài `paths`:
      - outro_start: giây bắt đầu outro trong video gốc, None nếu không cắt.
      - reason: "matched" (khớp được với video khác — chắc chắn) |
                "none" (không khớp được video nào khác — GIỮ NGUYÊN, không
                đoán liều, vì rất có thể video đó không hề có outro).
    """
    n = len(paths)
    durations = [ffprobe_info(p)["duration"] for p in paths]
    probe_hashes = [_multi_probe_hashes(paths[i], durations[i]) for i in range(n)]

    groups = []
    for i in range(n):
        if not probe_hashes[i]:
            continue
        placed = False
        for g in groups:
            if any(_best_matching_offset(probe_hashes[i], probe_hashes[j], threshold) is not None for j in g):
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
            # Mốc "an toàn" để bắt đầu dò lùi cho video i: mốc nhỏ nhất mà
            # nó khớp được với BẤT KỲ thành viên khác trong nhóm — PHẢI thử
            # qua HẾT các thành viên khác, không chỉ 1 video cố định. Nhóm
            # được gộp theo kiểu "bắt cầu" (A khớp B, B khớp C -> A,B,C cùng
            # nhóm dù A có thể KHÔNG khớp trực tiếp C) — nếu chỉ so với 1
            # video cố định trong nhóm, video nào không khớp TRỰC TIẾP với
            # đúng video đó sẽ bị bỏ qua (không cắt được gì) dù nó vẫn thực
            # sự chung outro với 1 video khác trong nhóm (bug đã gặp thật,
            # gây hiện tượng "không cắt" ngẫu nhiên khi tải lên từ 3 video
            # trở lên). Ưu tiên mốc NHỎ NHẤT (gần cuối video, đáng tin cậy
            # nhất) trong số tất cả các cặp khớp trực tiếp tìm được.
            anchor_offset, ref_hash = None, None
            for j in g:
                if j == i:
                    continue
                off = _best_matching_offset(probe_hashes[i], probe_hashes[j], threshold)
                if off is not None and (anchor_offset is None or off < anchor_offset):
                    anchor_offset, ref_hash = off, probe_hashes[j][off]
            if anchor_offset is None:
                continue
            boundary = _find_boundary_by_time(paths[i], ref_hash, threshold, durations[i], anchor_offset)
            results[i] = {"outro_start": boundary, "reason": "matched"}

    return results


def _process_one_video(i, p, boundary, own_outro_path, own_info, clips_dir, workdir, strip_audio):
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

    return {"path": out_path, "outro_cut_seconds": cut_seconds, "reason": boundary["reason"]}


def process_outro_swap(paths, own_outro_path, workdir, strip_audio,
                        tail_match_threshold=DEFAULT_MATCH_THRESHOLD, on_source=None,
                        max_workers=1):
    """Với mỗi video trong `paths`: cắt outro đối thủ (nếu xác định được),
    rồi gắn `own_outro_path` vào cuối — GIỮ NGUYÊN nội dung gốc, không xáo
    trộn, không ghép với video khác. Mỗi video đầu vào cho ra đúng 1 video
    kết quả.

    `own_outro_path` có thể là None — khi đó CHỈ cắt outro đối thủ (nếu xác
    định được), KHÔNG gắn thêm gì vào cuối. Dùng cho người chỉ cần bỏ outro
    đối thủ đi (vd để tự gắn trademark riêng, hoặc không cần outro nào cả).

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
    gì), "reason": xem find_outro_boundaries()}.
    """
    workdir = Path(workdir)
    clips_dir = workdir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    boundaries = find_outro_boundaries(paths, tail_match_threshold)
    own_info = ffprobe_info(own_outro_path) if own_outro_path is not None else None

    made = [None] * len(paths)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _process_one_video, i, p, b, own_outro_path, own_info, clips_dir, workdir, strip_audio,
            ): i
            for i, (p, b) in enumerate(zip(paths, boundaries))
        }
        done_count = 0
        for future in concurrent.futures.as_completed(futures):
            i = futures[future]
            result = future.result()
            made[i] = result
            done_count += 1
            if on_source:
                on_source(done_count, len(paths), paths[i].name, result)

    return made
