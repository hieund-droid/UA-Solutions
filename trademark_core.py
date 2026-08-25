#!/usr/bin/env python3
"""
trademark_core.py — Gắn trademark của BẠN (chữ hoặc logo/hình ảnh) lên
video, bay theo đường ZIGZAG (kiểu logo DVD nảy quanh khung hình) xuyên
suốt video — không cố định 1 chỗ. Chỉnh được độ mờ (opacity) và độ lớn.

Đây là tính năng khác hẳn logo_cover_core.py: bên đó CHE watermark của ĐỐI
THỦ đã có sẵn trong video (cần khoanh vùng + bám theo); bên này THÊM MỚI
watermark của BẠN vào video, tự sinh đường bay, không cần biết trước video
có gì.

Lưu ý đã nói rõ với người dùng: đường bay đi KHẮP khung hình (theo yêu cầu),
nên có lúc trademark sẽ đi qua vùng giữa (thường là chủ thể chính) — không
có cách nào tránh 100% mà không nhận diện nội dung (đã xác nhận việc đó
không khả thi ở logo_cover_core.py). Người dùng tự cân đối bằng độ mờ/độ
lớn để giảm mức che.

Dùng module (import từ app.py):
    render_text_overlay(text) -> RGBA numpy array
    load_logo_overlay(path) -> RGBA numpy array
    apply_trademark(video_path, overlay_rgba, out_path, workdir,
                     opacity, size_percent, speed_px_per_sec)
    generate_preview_animation(sample_frame_bgr, overlay_rgba, opacity,
                                size_percent, speed_px_per_sec) -> bytes
        (WEBP động) — xem trước NHANH (ảnh nhỏ, vài giây) để biết thực tế
        độ mờ/độ lớn/tốc độ trông ra sao trước khi xử lý cả video, tránh
        phải chỉnh mù theo số.
"""

import io
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from remix_core import ffprobe_info

# Font hỗ trợ dấu tiếng Việt — mỗi kiểu (đậm/thường) thử theo thứ tự, dùng
# cái đầu tiên có trên máy đang chạy (Windows dev vs server Linux khác
# nhau — server Linux dùng DejaVu Sans, luôn có sẵn nhờ khai trong
# packages.txt, không phụ thuộc gói nào khác kéo theo).
FONT_CANDIDATES = {
    "Đậm": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/tahomabd.ttf",
    ],
    "Thường": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
    ],
}
FONT_STYLES = list(FONT_CANDIDATES.keys())


def _load_font(size, font_style="Đậm"):
    for path in FONT_CANDIDATES.get(font_style, FONT_CANDIDATES[FONT_STYLES[0]]):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def render_text_overlay(text, font_size=64, font_style="Đậm",
                         text_color=(255, 255, 255, 255), stroke_color=(0, 0, 0, 255)):
    """Vẽ `text` ra 1 ảnh RGBA (nền trong suốt), có viền quanh chữ (màu
    `stroke_color`) để đọc được trên nền video bất kỳ (sáng hay tối). Trả
    về numpy array RGBA — kích thước vừa khít chữ.

    - font_style: 1 trong FONT_STYLES ("Đậm"/"Thường").
    - text_color / stroke_color: tuple RGBA (0-255)."""
    font = _load_font(font_size, font_style)
    dummy = Image.new("RGBA", (10, 10))
    bbox = ImageDraw.Draw(dummy).textbbox((0, 0), text, font=font, stroke_width=3)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = 8
    img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text(
        (pad - bbox[0], pad - bbox[1]), text, font=font, fill=text_color,
        stroke_width=3, stroke_fill=stroke_color,
    )
    return np.array(img)


def load_logo_overlay(path):
    """Đọc ảnh logo (PNG nền trong suốt lý tưởng nhất) thành RGBA numpy
    array. Ảnh không có kênh alpha (jpg...) sẽ được coi là hoàn toàn không
    trong suốt (alpha=255 toàn bộ)."""
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise RuntimeError(f"Không đọc được ảnh: {path}")
    if img.shape[2] == 3:
        alpha = np.full(img.shape[:2], 255, dtype=np.uint8)
        img = np.dstack([img, alpha])
    # cv2 doc theo BGR(A), chuyen sang RGB(A) cho dong bo voi render_text_overlay
    return cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)


def _bounce(distance, max_extent):
    """1 chiều của đường 'nảy' (triangle wave) trong đoạn [0, max_extent]."""
    if max_extent <= 0:
        return 0
    period = 2 * max_extent
    d = distance % period
    return d if d <= max_extent else period - d


def _zigzag_position(t_seconds, max_x, max_y, speed_px_per_sec):
    """Vị trí (x, y) tại thời điểm t — nảy độc lập theo 2 chiều với tỉ lệ
    tốc độ khác nhau (0.71 ≈ không phải số nguyên/phân số đơn giản) để
    đường đi không lặp lại theo 1 chu kỳ ngắn, tạo cảm giác zigzag khắp
    khung hình thay vì đi lại đúng 1 đường chéo đơn điệu."""
    x = _bounce(speed_px_per_sec * t_seconds, max_x)
    y = _bounce(speed_px_per_sec * 0.71 * t_seconds, max_y)
    return int(x), int(y)


def _blend_overlay_at(frame_bgr, overlay_rgba, x, y):
    """Dán `overlay_rgba` (RGBA) lên `frame_bgr` (BGR, sửa trực tiếp) tại
    góc trên-trái (x, y), trộn theo kênh alpha."""
    fh, fw = frame_bgr.shape[:2]
    oh, ow = overlay_rgba.shape[:2]
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + ow, fw), min(y + oh, fh)
    if x1 <= x0 or y1 <= y0:
        return frame_bgr
    ox0, oy0 = x0 - x, y0 - y
    ox1, oy1 = ox0 + (x1 - x0), oy0 + (y1 - y0)
    patch = overlay_rgba[oy0:oy1, ox0:ox1]

    alpha = (patch[:, :, 3:4].astype(np.float32)) / 255.0
    rgb_bgr = patch[:, :, [2, 1, 0]].astype(np.float32)  # RGB -> BGR
    bg = frame_bgr[y0:y1, x0:x1].astype(np.float32)
    frame_bgr[y0:y1, x0:x1] = (rgb_bgr * alpha + bg * (1 - alpha)).astype(np.uint8)
    return frame_bgr


def apply_trademark(video_path, overlay_rgba, out_path, workdir,
                     opacity=0.7, size_percent=15, speed_px_per_sec=120,
                     skip_after_seconds=None):
    """Gắn `overlay_rgba` (chữ hoặc logo, xem render_text_overlay /
    load_logo_overlay) lên `video_path`, bay theo đường zigzag, xuất ra
    `out_path`.

    - opacity: 0..1 (độ mờ — 1 = đậm hoàn toàn).
    - size_percent: kích thước trademark tính theo % chiều rộng video.
    - speed_px_per_sec: tốc độ bay (pixel/giây).
    - skip_after_seconds: nếu có, KHÔNG gắn trademark từ giây này tới hết
      video — dùng khi video đã có sẵn 1 đoạn outro riêng gắn ở cuối (vd
      tab "Cắt & Gắn Outro") và không muốn trademark bay đè lên đoạn đó.

    LƯU Ý: trong phạm vi được gắn, đường bay đi khắp khung hình, không
    tránh vùng giữa (chủ thể chính) — không có cách nhận diện nội dung để
    tự tránh (xem logo_cover_core.py để biết vì sao việc này không khả thi
    tự động). Giảm size_percent/opacity để hạn chế mức che nếu cần."""
    workdir = Path(workdir)
    info = ffprobe_info(video_path)
    fps = info["fps"] or 30

    cap = cv2.VideoCapture(str(video_path))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    overlay_w = max(int(width * size_percent / 100), 1)
    scale = overlay_w / overlay_rgba.shape[1]
    overlay_h = max(int(overlay_rgba.shape[0] * scale), 1)
    overlay = cv2.resize(overlay_rgba, (overlay_w, overlay_h), interpolation=cv2.INTER_AREA).copy()
    overlay[:, :, 3] = (overlay[:, :, 3].astype(np.float32) * max(0.0, min(opacity, 1.0))).astype(np.uint8)

    max_x = max(width - overlay_w, 0)
    max_y = max(height - overlay_h, 0)

    # Ghi thẳng từng khung hình đã xử lý vào ffmpeg qua pipe (stdin) để mã
    # hoá LUÔN 1 LẦN — trước đây ghi ra file tạm bằng cv2.VideoWriter rồi
    # ffmpeg đọc lại + mã hoá lần 2 (mã hoá 2 LẦN cho mỗi video, chậm gấp
    # đôi không cần thiết). Lỗi ffmpeg (nếu có) ghi ra file log riêng thay
    # vì đọc qua pipe stderr, để tránh nguy cơ tắc nghẽn (deadlock) giữa
    # lúc vừa ghi stdin vừa đọc stderr.
    err_log = workdir / f"{Path(out_path).stem}_ffmpeg_err.log"
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}", "-r", str(fps),
        "-i", "-",
        "-i", str(video_path),
        "-map", "0:v:0", "-map", "1:a:0?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", "-movflags", "+faststart", str(out_path),
    ]
    with open(err_log, "wb") as errf:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=errf)
        frame_idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            t = frame_idx / fps
            if skip_after_seconds is None or t < skip_after_seconds:
                x, y = _zigzag_position(t, max_x, max_y, speed_px_per_sec)
                frame = _blend_overlay_at(frame, overlay, x, y)
            proc.stdin.write(frame.tobytes())
            frame_idx += 1
        cap.release()
        proc.stdin.close()
        proc.wait()

    if proc.returncode != 0:
        err_text = err_log.read_text(errors="replace") if err_log.exists() else ""
        raise RuntimeError(f"Lệnh ffmpeg thất bại khi gắn trademark:\n{err_text[-2000:]}")
    err_log.unlink(missing_ok=True)
    return out_path


def generate_preview_animation(sample_frame_bgr, overlay_rgba, opacity=0.7, size_percent=15,
                                speed_px_per_sec=150, duration_sec=3.0, fps=8, preview_width=220):
    """Sinh 1 ảnh ĐỘNG nhỏ, NHANH (không dùng ffmpeg, chỉ vài khung hình độ
    phân giải thấp) để xem trước ngay khi chỉnh độ mờ/độ lớn/tốc độ — không
    cần đợi xử lý cả video mới biết trông ra sao. Trả về bytes ảnh WEBP động
    (không dùng GIF — đã đo thực tế: GIF của PIL chậm hơn WEBP animation tới
    15-20 lần cho cùng số khung hình, do PIL phải tính lại bảng màu giới hạn
    256 màu cho từng khung — không phù hợp để cập nhật theo thời gian thực
    mỗi lần kéo thanh trượt)."""
    h, w = sample_frame_bgr.shape[:2]
    scale = preview_width / w
    small_frame = cv2.resize(sample_frame_bgr, (preview_width, max(int(h * scale), 1)), interpolation=cv2.INTER_AREA)
    fh, fw = small_frame.shape[:2]

    overlay_w = max(int(fw * size_percent / 100), 1)
    oscale = overlay_w / overlay_rgba.shape[1]
    overlay_h = max(int(overlay_rgba.shape[0] * oscale), 1)
    overlay = cv2.resize(overlay_rgba, (overlay_w, overlay_h), interpolation=cv2.INTER_AREA).copy()
    overlay[:, :, 3] = (overlay[:, :, 3].astype(np.float32) * max(0.0, min(opacity, 1.0))).astype(np.uint8)

    max_x = max(fw - overlay_w, 0)
    max_y = max(fh - overlay_h, 0)

    frames = []
    for i in range(int(duration_sec * fps)):
        t = i / fps
        x, y = _zigzag_position(t, max_x, max_y, speed_px_per_sec)
        frame = _blend_overlay_at(small_frame.copy(), overlay, x, y)
        frames.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))

    buf = io.BytesIO()
    frames[0].save(
        buf, format="WEBP", save_all=True, append_images=frames[1:],
        duration=int(1000 / fps), loop=0, quality=70, method=0,
    )
    return buf.getvalue()
