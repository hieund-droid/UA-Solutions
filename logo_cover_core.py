#!/usr/bin/env python3
"""
logo_cover_core.py — Che logo/trademark của ĐỐI THỦ đang di chuyển trong
video, bằng cách:
  1. Người dùng khoanh 1 khung chữ nhật quanh logo/chữ đó ở 1 khung hình cụ
     thể (thời điểm t0) — xem app.py, dùng streamlit_cropper để vẽ.
  2. Tool dùng kỹ thuật OBJECT TRACKING (OpenCV, thuật toán CSRT — theo dõi
     vật thể chuẩn, đã được kiểm chứng rộng rãi) để tự "đuổi theo" khung đó
     ở các khung hình tiếp theo (và lùi lại các khung hình trước đó).
  3. Ở mỗi khung hình bám theo được, vẽ đè logo/trademark của người dùng lên
     đúng vị trí + kích thước đã theo dõi.

GIỚI HẠN QUAN TRỌNG (đã kiểm chứng qua thử nghiệm, không phải giả định):
  - Object tracking thường MẤT DẤU khi video CẮT CẢNH (bối cảnh đổi đột
    ngột) — vì vậy tool CHỈ bám theo trong phạm vi 1 SCENE (1 cảnh liên tục,
    xác định bằng PySceneDetect như remix_core.py) chứa thời điểm t0, không
    cố đuổi qua điểm cắt cảnh để tránh che sai chỗ.
  - Nếu video có nhiều cảnh chứa logo, cần khoanh vùng riêng cho từng cảnh
    (chạy tool nhiều lần) — đây là đánh đổi chấp nhận được để đổi lấy độ
    chính xác, thay vì cố tự động hoàn toàn (đã thử và không khả thi với
    loại video quay tay/cắt cảnh nhanh — xem lịch sử trò chuyện).

Dùng module (import từ app.py):
    result = cover_logo_in_scene(video_path, own_logo_path, out_path,
                                  workdir, t0, bbox)
"""

from pathlib import Path

import cv2
import numpy as np

from remix_core import detect_scenes, ffprobe_info, run

def _find_tracker_factory(name):
    """API theo dõi vật thể (CSRT/KCF) nằm ở chỗ khác nhau tuỳ phiên bản/hệ
    điều hành build OpenCV — có bản để thẳng ở cv2.TrackerXXX_create, có bản
    chuyển vào cv2.legacy.TrackerXXX_create. Dò cả 2 chỗ thay vì cố định 1
    chỗ, để tránh lỗi mất hẳn tính năng (hoặc tệ hơn — sập cả module lúc
    import) chỉ vì khác bản OpenCV giữa máy dev và máy chủ thật."""
    for holder in (cv2, getattr(cv2, "legacy", None)):
        factory = getattr(holder, f"Tracker{name}_create", None)
        if factory is not None:
            return factory
    return None


# Chỉ liệt kê tracker THỰC SỰ có sẵn trên máy đang chạy — nếu bản OpenCV
# không có cái nào (hiếm), dict này rỗng, UI sẽ tự báo rõ thay vì crash.
TRACKER_FACTORIES = {}
_csrt = _find_tracker_factory("CSRT")
if _csrt:
    TRACKER_FACTORIES["CSRT (chính xác hơn, chậm hơn)"] = _csrt
_kcf = _find_tracker_factory("KCF")
if _kcf:
    TRACKER_FACTORIES["KCF (nhanh hơn, kém chính xác hơn)"] = _kcf


def _scene_containing(scenes, t0):
    for start, end in scenes:
        if start <= t0 <= end:
            return start, end
    # t0 nam ngoai moi scene da biet (hiem, do sai so lam tron) -> dung ca video
    return 0.0, None


def _overlay_logo(frame, logo, bbox, cover_scale=1.15):
    """Vẽ đè `logo` (có thể có kênh alpha) lên `frame` tại tâm của `bbox`,
    phóng to theo `cover_scale` để đảm bảo che kín hoàn toàn logo gốc bên
    dưới (không chỉ vừa khít, tránh còn hở viền)."""
    fh, fw = frame.shape[:2]
    x, y, w, h = bbox
    if w <= 0 or h <= 0:
        return frame
    cx, cy = x + w / 2, y + h / 2
    ow, oh = max(int(w * cover_scale), 1), max(int(h * cover_scale), 1)
    resized = cv2.resize(logo, (ow, oh), interpolation=cv2.INTER_AREA)

    x0, y0 = int(cx - ow / 2), int(cy - oh / 2)
    x1, y1 = x0 + ow, y0 + oh
    sx0, sy0 = max(x0, 0), max(y0, 0)
    sx1, sy1 = min(x1, fw), min(y1, fh)
    if sx1 <= sx0 or sy1 <= sy0:
        return frame
    rx0, ry0 = sx0 - x0, sy0 - y0
    rx1, ry1 = rx0 + (sx1 - sx0), ry0 + (sy1 - sy0)
    patch = resized[ry0:ry1, rx0:rx1]

    if patch.shape[2] == 4:
        alpha = (patch[:, :, 3:4].astype(np.float32)) / 255.0
        rgb = patch[:, :, :3].astype(np.float32)
        bg = frame[sy0:sy1, sx0:sx1].astype(np.float32)
        frame[sy0:sy1, sx0:sx1] = (rgb * alpha + bg * (1 - alpha)).astype(np.uint8)
    else:
        frame[sy0:sy1, sx0:sx1] = patch[:, :, :3]
    return frame


def _patch_gray(frame, bbox, size):
    """Cắt vùng `bbox` trong `frame`, chuyển xám, co về đúng `size` (w,h)
    để so sánh được với patch tham chiếu dù kích thước tracker trả về có
    đổi chút ít qua từng khung."""
    x, y, w, h = bbox
    fh, fw = frame.shape[:2]
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, fw), min(y + h, fh)
    if x1 <= x0 or y1 <= y0:
        return None
    patch = frame[y0:y1, x0:x1]
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, size, interpolation=cv2.INTER_AREA)


def _patch_similarity(ref_gray, frame, bbox):
    """So khớp vùng đang bám theo với patch GỐC (lúc mới khoanh vùng) —
    trả về hệ số 0..1 (1 = giống hệt). Dùng để tự phát hiện trường hợp
    OpenCV tracker báo "vẫn bám được" (update() trả True) nhưng thực chất
    đã bám nhầm sang nền tĩnh phía sau vì watermark đã biến mất khỏi khung
    hình — hay gặp với watermark ẩn/hiện chập chờn chứ không phải lúc nào
    cũng hiển thị suốt cảnh."""
    h, w = ref_gray.shape
    patch = _patch_gray(frame, bbox, (w, h))
    if patch is None:
        return -1.0
    res = cv2.matchTemplate(patch, ref_gray, cv2.TM_CCOEFF_NORMED)
    return float(res[0, 0])


def _track_range(video_path, seed_frame_idx, bbox, frame_indices, tracker_factory,
                  similarity_threshold=0.4):
    """Bám theo `bbox` xuất phát từ khung `seed_frame_idx`, dọc theo dãy chỉ
    số khung `frame_indices` (đã sắp đúng thứ tự cần đọc — tăng dần cho
    chiều tiến, giảm dần cho chiều lùi). Đọc tuần tự bằng cv2 (nhanh hơn
    nhiều so với seek từng khung).

    Dừng khi: (a) OpenCV tracker tự báo mất dấu, HOẶC (b) vùng đang bám
    theo không còn giống patch gốc đủ nhiều (xem _patch_similarity) — vế
    (b) quan trọng vì tracker CSRT/KCF của OpenCV vẫn có thể báo "còn bám
    được" dù thực chất đã trôi sang nền tĩnh khi vật thể gốc biến mất.

    Trả về dict {frame_idx: (x,y,w,h)}."""
    cap = cv2.VideoCapture(str(video_path))
    start_idx = frame_indices[0]
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_idx)

    tracked = {}
    ok, frame = cap.read()
    if not ok:
        cap.release()
        return tracked

    tracker = tracker_factory()
    tracker.init(frame, bbox)
    tracked[start_idx] = bbox
    ref_gray = _patch_gray(frame, bbox, (max(bbox[2], 1), max(bbox[3], 1)))

    for idx in frame_indices[1:]:
        ok, frame = cap.read()
        if not ok:
            break
        ok_t, box = tracker.update(frame)
        if not ok_t:
            break
        box = tuple(int(round(v)) for v in box)
        if ref_gray is not None and _patch_similarity(ref_gray, frame, box) < similarity_threshold:
            break
        tracked[idx] = box

    cap.release()
    return tracked


def cover_logo_in_scene(video_path, own_logo_path, out_path, workdir, t0, bbox,
                         threshold=27.0, detector="content", min_scene_len=0.5,
                         tracker_name="CSRT (chính xác hơn, chậm hơn)", cover_scale=1.15):
    """Che logo đối thủ trong PHẠM VI 1 SCENE chứa thời điểm `t0`, bằng
    object tracking xuất phát từ `bbox` (x,y,w,h, toạ độ pixel) tại `t0`.

    Trả về dict:
      - out_path, scene_start, scene_end (giây, ranh giới cảnh chứa t0)
      - covered_start, covered_end (giây, đoạn THỰC TẾ đã che được — có thể
        hẹp hơn cả cảnh nếu tracker mất dấu giữa chừng)
      - lost_forward / lost_backward (bool — có bị mất dấu trước khi hết
        cảnh không, để báo người dùng biết cần khoanh thêm đoạn khác)
    """
    workdir = Path(workdir)
    info = ffprobe_info(video_path)
    fps = info["fps"] or 30.0
    duration = info["duration"]

    scenes = detect_scenes(video_path, threshold, detector, min_scene_len)
    scene_start, scene_end = _scene_containing(scenes, t0)
    if scene_end is None:
        scene_end = duration

    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    f0 = min(max(int(round(t0 * fps)), 0), total_frames - 1)
    f_start = min(max(int(round(scene_start * fps)), 0), f0)
    f_end = min(int(round(scene_end * fps)), total_frames - 1)
    f_end = max(f_end, f0)

    tracker_factory = TRACKER_FACTORIES[tracker_name]

    forward_indices = list(range(f0, f_end + 1))
    tracked_fwd = _track_range(video_path, f0, bbox, forward_indices, tracker_factory) if len(forward_indices) > 1 else {f0: bbox}

    tracked_bwd = {}
    if f0 > f_start:
        backward_indices = list(range(f0, f_start - 1, -1))
        tracked_bwd = _track_range(video_path, f0, bbox, backward_indices, tracker_factory)

    tracked = {**tracked_bwd, **tracked_fwd}  # f0 co trong ca 2, giong nhau

    last_fwd_idx = max(tracked_fwd.keys()) if tracked_fwd else f0
    last_bwd_idx = min(tracked_bwd.keys()) if tracked_bwd else f0
    lost_forward = last_fwd_idx < f_end
    lost_backward = last_bwd_idx > f_start

    # Ghi video (khong am thanh) voi logo da ve de, roi mux lai am thanh goc.
    own_logo = cv2.imread(str(own_logo_path), cv2.IMREAD_UNCHANGED)
    if own_logo is None:
        raise RuntimeError(f"Không đọc được ảnh logo: {own_logo_path}")

    silent_path = workdir / f"{Path(out_path).stem}_silent.mp4"
    cap = cv2.VideoCapture(str(video_path))
    writer = cv2.VideoWriter(str(silent_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    idx = -1
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        idx += 1
        if idx in tracked:
            frame = _overlay_logo(frame, own_logo, tracked[idx], cover_scale)
        writer.write(frame)
    writer.release()
    cap.release()

    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(silent_path), "-i", str(video_path),
        "-map", "0:v:0", "-map", "1:a:0?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", "-movflags", "+faststart", str(out_path),
    ])
    silent_path.unlink(missing_ok=True)

    return {
        "out_path": Path(out_path),
        "scene_start": scene_start, "scene_end": scene_end,
        "covered_start": last_bwd_idx / fps, "covered_end": last_fwd_idx / fps,
        "lost_forward": lost_forward, "lost_backward": lost_backward,
    }
