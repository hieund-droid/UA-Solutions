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

  Video nào không khớp được với video nào khác (vd chỉ tải lên 1 video,
  nhiều đối thủ khác nhau trong 1 lần, hoặc video đó thực sự không có outro
  giống các video còn lại) sẽ dùng phương án dự phòng: coi scene cuối cùng
  (theo PySceneDetect) là outro — kém chắc chắn hơn nên luôn kèm cảnh báo.

Dùng module (import từ app.py):
    process_outro_swap(paths, own_outro_path, workdir, threshold, detector,
                        min_scene_len, strip_audio)

Yêu cầu: ffmpeg, ffprobe trong PATH (giống remix_core.py).
"""

from pathlib import Path

import cv2
import numpy as np

from remix_core import (
    _grab_frame_bgr,
    concat_clips,
    detect_scenes,
    ffprobe_info,
    split_clips,
)

# Giây tính từ cuối video dùng để "dò thử" xem 2 video có outro chung không.
# Outro quan sát được trên thực tế dài ~3-4s, nên mốc 1.5s trước khi kết
# thúc gần như chắc chắn còn nằm trong outro nếu video đó CÓ outro.
PROBE_OFFSET = 1.5
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


def _find_boundary_by_time(path, ref_hash, threshold, duration):
    """Dò lùi dần theo thời gian, tìm mốc mà hình ảnh KHÔNG còn khớp với
    `ref_hash` nữa — đó là điểm bắt đầu outro.

    Bắt đầu dò từ đúng mốc `duration - PROBE_OFFSET` (điểm đã CHẮC CHẮN khớp
    — chính là nơi lấy probe_hash để gom nhóm), KHÔNG dò từ sát mép cuối
    file: OpenCV đọc khung hình trong khoảng dưới ~1 giây cuối file thường
    không ổn định (nhiễu/giải mã sai), dễ báo "không khớp" giả trong khi
    outro thực tế vẫn kéo dài tới hết file."""
    cursor = max(0.0, duration - PROBE_OFFSET)
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


def find_outro_boundaries(paths, threshold=DEFAULT_MATCH_THRESHOLD, fallback_scenes=None):
    """Xác định mốc thời gian bắt đầu outro đối thủ cho mỗi video, bằng cách
    so khớp hình ảnh CHÉO giữa các video trong cùng danh sách `paths`.

    `fallback_scenes`: list scene (từ detect_scenes) song song với `paths`,
    dùng cho phương án dự phòng khi 1 video không khớp được với video nào
    khác. Nếu không truyền, video không khớp sẽ không bị cắt gì.

    Trả về list dict cùng độ dài `paths`:
      - outro_start: giây bắt đầu outro trong video gốc, None nếu không cắt.
      - reason: "matched" (khớp được với video khác — chắc chắn) |
                "fallback" (không khớp ai, dùng scene cuối cùng — kém chắc
                chắn hơn) | "none" (không xác định được, giữ nguyên).
    """
    n = len(paths)
    durations = [ffprobe_info(p)["duration"] for p in paths]

    probe_hash = {}
    for i in range(n):
        t = durations[i] - PROBE_OFFSET
        probe_hash[i] = _sample_hash(paths[i], t) if t > 0 else None

    groups = []
    for i in range(n):
        if probe_hash[i] is None:
            continue
        placed = False
        for g in groups:
            if any(_match(probe_hash[i], probe_hash[j], threshold) for j in g):
                g.add(i)
                placed = True
                break
        if not placed:
            groups.append({i})

    results = [None] * n
    for g in groups:
        if len(g) < 2:
            continue
        ref_i = next(iter(g))
        ref_hash = probe_hash[ref_i]
        for i in g:
            boundary = _find_boundary_by_time(paths[i], ref_hash, threshold, durations[i])
            results[i] = {"outro_start": boundary, "reason": "matched"}

    for i in range(n):
        if results[i] is not None:
            continue
        scenes = fallback_scenes[i] if fallback_scenes else None
        if scenes and len(scenes) >= 2:
            results[i] = {"outro_start": scenes[-1][0], "reason": "fallback"}
        else:
            results[i] = {"outro_start": None, "reason": "none"}

    return results


def process_outro_swap(paths, own_outro_path, workdir, threshold, detector, min_scene_len,
                        strip_audio, tail_match_threshold=DEFAULT_MATCH_THRESHOLD, on_source=None):
    """Với mỗi video trong `paths`: cắt outro đối thủ (nếu xác định được),
    gắn `own_outro_path` vào cuối — GIỮ NGUYÊN nội dung gốc, không xáo trộn,
    không ghép với video khác. Mỗi video đầu vào cho ra đúng 1 video kết quả.

    on_source(i, total, name, boundary_info) được gọi sau mỗi video xử lý
    xong, để UI báo tiến độ + cảnh báo.

    Trả về list dict: {"path": Path video kết quả, "outro_cut_seconds": số
    giây outro đối thủ đã cắt (0 nếu không cắt được gì), "reason": xem
    find_outro_boundaries()}.
    """
    workdir = Path(workdir)
    clips_dir = workdir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    # Scene chỉ cần cho phương án dự phòng (khi không khớp được video nào
    # khác) — không dùng để định vị outro trong đường đi chính nữa.
    fallback_scenes = [detect_scenes(p, threshold, detector, min_scene_len) for p in paths]
    boundaries = find_outro_boundaries(paths, tail_match_threshold, fallback_scenes)

    own_info = ffprobe_info(own_outro_path)

    made = []
    for i, (p, b) in enumerate(zip(paths, boundaries)):
        info = ffprobe_info(p)
        # Không cần đồng nhất kích thước với các video khác (không ghép
        # chéo nội dung giữa các video như remix_core.py) — nhưng PHẢI chọn
        # khung hình chuẩn theo bên nào có ĐỘ PHÂN GIẢI CAO HƠN giữa video
        # nguồn và outro của bạn. Nếu luôn lấy theo video nguồn (thường thấp
        # hơn, vì là file tải về từ đối thủ) thì outro chất lượng cao của
        # bạn sẽ bị co nhỏ xuống theo, gây mờ — đã gặp lỗi này trên thực tế.
        target_spec = _pick_larger_spec(info, own_info)
        want_audio = (not strip_audio) and (info["has_audio"] or own_info["has_audio"])

        content_end = b["outro_start"] if b["outro_start"] is not None else info["duration"]
        content_clips = split_clips(
            p, [(0.0, content_end)], clips_dir, info["has_audio"], want_audio, 0.0,
            target_spec, name_prefix=f"content{i:02d}",
        )
        outro_clips = split_clips(
            own_outro_path, [(0.0, own_info["duration"])], clips_dir, own_info["has_audio"],
            want_audio, 0.0, target_spec, name_prefix=f"ownoutro{i:02d}",
        )

        out_path = workdir / f"outro_swap_{i + 1:02d}.mp4"
        concat_clips(content_clips + outro_clips, out_path, workdir)

        cut_seconds = (info["duration"] - content_end) if b["outro_start"] is not None else 0.0
        result = {"path": out_path, "outro_cut_seconds": cut_seconds, "reason": b["reason"]}
        made.append(result)

        for c in content_clips + outro_clips:
            c.unlink(missing_ok=True)

        if on_source:
            on_source(i, len(paths), p.name, result)

    return made
