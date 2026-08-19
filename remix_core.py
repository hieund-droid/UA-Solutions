#!/usr/bin/env python3
"""
remix_core.py — Tách NHIỀU video khác nhau thành các clip nhỏ theo scene,
rồi trộn lẫn (xáo trộn ngẫu nhiên) clip từ tất cả các video đó để ghép ra
(các) video mới.

Pipeline:
  1. SPLIT  : với mỗi video đầu vào, dùng PySceneDetect (ContentDetector)
              phát hiện điểm cắt cảnh, cắt ra từng file riêng (re-encode để
              cắt chính xác từng frame). Mọi clip được co giãn/đệm viền đen
              về cùng 1 kích thước + fps + có/không âm thanh thống nhất, để
              clip từ các nguồn khác nhau vẫn nối liền mạch được với nhau.
  2. POOL   : gom clip từ TẤT CẢ video đầu vào thành 1 rổ chung.
  3. REMIX  : xáo trộn ngẫu nhiên rổ clip chung rồi nối lại bằng ffmpeg
              concat demuxer (stream copy — nhanh, không giảm chất lượng,
              vì mọi clip đã được đưa về cùng 1 chuẩn ở bước SPLIT).

Dùng làm module (import từ app.py) hoặc chạy trực tiếp dòng lệnh:
  python3 remix_core.py --input a.mp4 b.mp4 c.mp4 --outdir out --variants 5

Yêu cầu: ffmpeg, ffprobe trong PATH; pip install scenedetect
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from scenedetect import detect, ContentDetector, AdaptiveDetector

# Console Windows mặc định dùng bảng mã cp1252, không hiển thị được tiếng Việt
# có dấu / ký tự mũi tên khi in ra bằng print(). Chuyển sang utf-8 để in CLI
# không bị crash (không ảnh hưởng khi chạy qua Streamlit vì đó không dùng stdout).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def run(cmd, **kw):
    """Chạy lệnh, raise nếu lỗi, trả về stdout."""
    res = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if res.returncode != 0:
        raise RuntimeError(f"Lệnh thất bại: {' '.join(cmd)}\n{res.stderr}")
    return res.stdout


def ffprobe_info(path):
    """Lấy duration, có audio không, resolution, fps."""
    out = run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ])
    data = json.loads(out)
    info = {"duration": float(data["format"].get("duration", 0)),
            "has_audio": False, "width": None, "height": None, "fps": None}
    for s in data.get("streams", []):
        if s["codec_type"] == "audio":
            info["has_audio"] = True
        if s["codec_type"] == "video" and info["width"] is None:
            info["width"] = s.get("width")
            info["height"] = s.get("height")
            r = s.get("r_frame_rate", "0/1")
            try:
                n, d = r.split("/")
                info["fps"] = round(float(n) / float(d), 3) if float(d) else None
            except Exception:
                pass
    return info


def _grab_frame_bgr(path, t):
    cap = cv2.VideoCapture(str(path))
    cap.set(cv2.CAP_PROP_POS_MSEC, max(t, 0) * 1000)
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


def _dhash(frame, hash_size=8):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    return small[:, 1:] > small[:, :-1]


def _hash_distance(h1, h2):
    if h1 is None or h2 is None:
        return None
    return int(np.count_nonzero(h1 != h2))


def merge_similar_scenes(path, scenes, max_distance=8):
    """Gộp lại 2 scene liền kề nếu hình ảnh ở ngay ranh giới thực chất
    GIỐNG NHAU — dùng để giảm việc PySceneDetect tách nhầm 1 cảnh liền mạch
    thành nhiều đoạn khi camera rung lắc, mất nét/mất khung hình tạm thời,
    hoặc đổi filter màu giữa chừng nhưng vẫn cùng 1 bối cảnh/nhân vật.

    Đây là so sánh khung hình bằng perceptual hash (không phải nhận diện
    khuôn mặt/bối cảnh thật), nên chỉ là ước lượng — giảm bớt tách vụn chứ
    không đảm bảo đúng tuyệt đối trong mọi trường hợp, đặc biệt khi filter
    thay đổi quá mạnh khiến hình ảnh biến dạng nhiều.
    """
    if len(scenes) < 2:
        return scenes
    merged = [list(scenes[0])]
    for start, end in scenes[1:]:
        prev_start, prev_end = merged[-1]
        f_before = _grab_frame_bgr(path, max(prev_end - 0.15, prev_start))
        f_after = _grab_frame_bgr(path, min(start + 0.15, max(end - 0.01, start)))
        h1 = _dhash(f_before) if f_before is not None else None
        h2 = _dhash(f_after) if f_after is not None else None
        dist = _hash_distance(h1, h2)
        if dist is not None and dist <= max_distance:
            merged[-1][1] = end  # giống nhau -> gộp, không phải cắt cảnh thật
        else:
            merged.append([start, end])
    return [tuple(m) for m in merged]


def detect_scenes(path, threshold, detector_type, min_scene_len,
                   merge_similar=False, merge_threshold=8):
    """Trả về list (start_sec, end_sec) cho từng scene."""
    min_len_frames = f"{min_scene_len}s" if min_scene_len else 15
    if detector_type == "adaptive":
        det = AdaptiveDetector(min_scene_len=min_len_frames)
    else:
        det = ContentDetector(threshold=threshold, min_scene_len=min_len_frames)
    scenes = detect(str(path), det, show_progress=False)
    result = [(s.seconds, e.seconds) for s, e in scenes]
    if merge_similar:
        result = merge_similar_scenes(path, result, merge_threshold)
    return result


def pick_target_spec(infos):
    """Chọn kích thước/fps chuẩn để đồng nhất mọi clip khi trộn nhiều
    video khác nhau — lấy theo video đầu tiên."""
    first = infos[0]
    return {
        "width": first["width"] or 1280,
        "height": first["height"] or 720,
        "fps": first["fps"] or 30,
    }


def split_clips(path, scenes, clips_dir, has_audio, want_audio, min_clip_len,
                 target_spec, name_prefix="clip", on_progress=None):
    """Cắt từng scene thành 1 file mp4 riêng (re-encode, chính xác frame),
    đồng thời co giãn/đệm viền đen về đúng target_spec và chuẩn hoá audio
    (thêm âm thanh câm nếu nguồn không có nhưng cần audio) để clip từ nhiều
    nguồn khác nhau vẫn nối liền mạch được."""
    clips_dir.mkdir(parents=True, exist_ok=True)
    clip_paths = []
    w, h, fps = target_spec["width"], target_spec["height"], target_spec["fps"]
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
          f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,fps={fps}")
    idx = 0
    for start, end in scenes:
        dur = end - start
        if dur < min_clip_len:
            continue
        out = clips_dir / f"{name_prefix}_{idx:03d}.mp4"
        cmd = ["ffmpeg", "-y", "-loglevel", "error",
               "-ss", f"{start:.3f}", "-i", str(path), "-t", f"{dur:.3f}"]
        if want_audio and not has_audio:
            # Nguồn không có tiếng nhưng cần audio để khớp các clip khác
            # có tiếng -> chèn thêm 1 track lặng thinh.
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                    "-shortest", "-map", "0:v", "-map", "1:a"]
        cmd += ["-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-pix_fmt", "yuv420p"]
        cmd += ["-c:a", "aac", "-b:a", "128k"] if want_audio else ["-an"]
        cmd += ["-movflags", "+faststart", str(out)]
        run(cmd)
        clip_paths.append(out)
        idx += 1
        if on_progress:
            on_progress(idx, len(scenes))
    return clip_paths


def analyze_sources(paths, threshold, detector, min_scene_len, has_outro=False,
                     merge_similar=False, merge_threshold=8):
    """Chỉ dò điểm cắt cảnh cho từng video (nhanh, KHÔNG cắt/re-encode) — dùng
    để xem trước sẽ có bao nhiêu đoạn trước khi quyết định tạo bao nhiêu
    biến thể.

    Nếu has_outro=True và nguồn có từ 2 scene trở lên, scene CUỐI CÙNG được
    coi là outro/logo cố định — tách riêng ra khỏi phần nội dung ngay từ
    bước phân tích để hiển thị đúng số đoạn nội dung thực tế.
    """
    results = []
    for p in paths:
        info = ffprobe_info(p)
        scenes = detect_scenes(p, threshold, detector, min_scene_len,
                                merge_similar, merge_threshold)
        if has_outro and len(scenes) >= 2:
            content_scenes, outro_scene = scenes[:-1], scenes[-1]
        else:
            content_scenes, outro_scene = scenes, None
        results.append({
            "path": p, "info": info, "scenes": scenes,
            "content_scenes": content_scenes, "outro_scene": outro_scene,
        })
    return results


def split_sources(analyzed, clips_dir, min_clip_len, strip_audio,
                   on_source=None, on_progress=None):
    """Cắt clip cho các nguồn đã có từ analyze_sources(), gom phần NỘI DUNG
    vào 1 rổ chung đã đồng nhất kích thước/fps/audio, sẵn sàng để trộn.

    Nếu nguồn có outro (xem analyze_sources), outro được cắt riêng, KHÔNG
    đưa vào rổ trộn. Trả về (rổ_clip_nội_dung, 1_clip_outro_đại_diện_hoặc_None)
    — chỉ giữ đúng 1 outro dùng chung cho mọi biến thể, vì các nguồn thường
    dùng chung 1 outro giống hệt nhau.
    """
    infos = [a["info"] for a in analyzed]
    target_spec = pick_target_spec(infos)
    want_audio = (not strip_audio) and any(i["has_audio"] for i in infos)

    # Chỉ cần cắt outro của ĐÚNG 1 nguồn (nguồn đầu tiên có outro) — các
    # nguồn khác dù cũng có outro giống hệt cũng không cần cắt, đỡ tốn công
    # và khỏi để lại file thừa.
    outro_source_idx = next(
        (i for i, a in enumerate(analyzed) if a.get("outro_scene")), None
    )

    all_clips = []
    outro_clip = None
    for i, a in enumerate(analyzed):
        content_scenes = a.get("content_scenes", a["scenes"])

        clips = split_clips(a["path"], content_scenes, clips_dir, a["info"]["has_audio"],
                             want_audio, min_clip_len, target_spec,
                             name_prefix=f"src{i:02d}", on_progress=on_progress)
        all_clips.extend(clips)

        if i == outro_source_idx:
            outro = split_clips(a["path"], [a["outro_scene"]], clips_dir,
                                 a["info"]["has_audio"], want_audio, 0.0,
                                 target_spec, name_prefix=f"outro{i:02d}")
            outro_clip = outro[0] if outro else None

        if on_source:
            on_source(i, len(analyzed), a["path"].name, len(a["scenes"]), len(clips))

    return all_clips, outro_clip


def process_sources(paths, clips_dir, threshold, detector, min_scene_len,
                     min_clip_len, strip_audio, has_outro=False,
                     merge_similar=False, merge_threshold=8,
                     on_source=None, on_progress=None):
    """Tách scene + cắt clip cho TẤT CẢ video đầu vào trong 1 bước (dùng cho
    CLI). Trả về (rổ clip nội dung, clip outro hoặc None, infos, scene_counts)."""
    analyzed = analyze_sources(paths, threshold, detector, min_scene_len, has_outro,
                                merge_similar, merge_threshold)
    clips, outro_clip = split_sources(analyzed, clips_dir, min_clip_len, strip_audio,
                                       on_source=on_source, on_progress=on_progress)
    infos = [a["info"] for a in analyzed]
    scene_counts = [len(a["scenes"]) for a in analyzed]
    return clips, outro_clip, infos, scene_counts


def concat_clips(clip_paths, out_path, workdir):
    """Nối các clip (đồng nhất spec) bằng concat demuxer — stream copy."""
    list_file = workdir / f"concat_list_{out_path.stem}.txt"
    with open(list_file, "w") as f:
        for c in clip_paths:
            f.write(f"file '{c.resolve()}'\n")
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", "-movflags", "+faststart", str(out_path),
    ])
    list_file.unlink(missing_ok=True)


def build_variant(clip_paths, rng, clip_durs, target_min, target_max, max_clips=0):
    """Chọn & xáo trộn clip ngẫu nhiên từ rổ chung (nhiều nguồn khác nhau) cho
    1 biến thể, nhắm tới độ dài [target_min, target_max] giây.

    Ưu tiên đạt tối thiểu target_min; một khi đã đạt, dừng lại quanh mức
    target_max thay vì dùng hết cả rổ. Nếu đoạn tiếp theo dài tới mức làm
    vượt target_max nhưng vẫn CHƯA đạt target_min, vẫn lấy đoạn đó (thà dư
    một chút thời lượng còn hơn bỏ phí creative hoặc cắt ngắn đoạn gốc).
    """
    order = clip_paths[:]
    rng.shuffle(order)
    chosen, total = [], 0.0
    for c in order:
        d = clip_durs[c]
        if chosen and total >= target_min and total + d > target_max:
            break
        chosen.append(c)
        total += d
        if max_clips and len(chosen) >= max_clips:
            break
        if total >= target_max:
            break
    return chosen


def _too_similar(shared, size):
    """1 biến thể có `size` đoạn, trùng `shared` đoạn với 1 biến thể khác thì
    có bị coi là quá giống nhau không.

    Biến thể chỉ 1-2 đoạn: trùng tối đa (size - 1) đoạn vẫn được (vì với ít
    đoạn như vậy khác biệt tối đa vốn dĩ chỉ có thể là 1 đoạn). Từ 3 đoạn trở
    lên: bắt buộc khác nhau ít nhất 2 đoạn, tức chỉ được trùng tối đa
    (size - 2) đoạn.
    """
    if size <= 0:
        return False
    limit = (size - 1) if size <= 2 else (size - 2)
    return shared > limit


def _closest_match(candidate, accepted):
    """Trong các biến thể đã chấp nhận trước đó, tìm bản GIỐNG candidate NHẤT.
    Trả về (số đoạn trùng, size nhỏ hơn giữa 2 bên, index bản đó) hoặc None
    nếu chưa có biến thể nào trước đó."""
    worst = None
    cand_set = set(candidate)
    for idx, prev in enumerate(accepted):
        shared = len(cand_set & set(prev))
        size = min(len(candidate), len(prev))
        if worst is None or shared > worst[0]:
            worst = (shared, size, idx)
    return worst


def build_variants(clip_paths, rng, clip_durs, target_min, target_max, count,
                    max_clips=0, max_attempts=200):
    """Tạo `count` biến thể, mỗi biến thể vẫn chọn bằng build_variant() như cũ,
    nhưng cố gắng đảm bảo KHÔNG có 2 biến thể nào giống nhau quá mức (xem
    _too_similar). Với mỗi biến thể mới, thử xáo trộn lại tối đa max_attempts
    lần cho tới khi tìm được bản đủ khác so với TẤT CẢ biến thể đã chọn
    trước đó.

    Nếu hết max_attempts vẫn không tìm được bản nào đủ khác (thường do rổ
    đoạn quá ít so với số biến thể muốn tạo), vẫn lấy bản GIỐNG ÍT NHẤT tìm
    được trong số đó, và trả về kèm 1 dòng cảnh báo cho biến thể đó.

    Trả về (list_biến_thể, list_cảnh_báo) — 2 list cùng độ dài `count`,
    cảnh báo là None nếu biến thể đó đủ khác biệt.
    """
    accepted = []
    warnings = []
    for v in range(count):
        best, best_match, ok = None, None, False
        for _ in range(max_attempts):
            candidate = build_variant(clip_paths, rng, clip_durs, target_min,
                                       target_max, max_clips)
            match = _closest_match(candidate, accepted)
            if match is None or not _too_similar(match[0], match[1]):
                best, ok = candidate, True
                break
            if best is None or match[0] < best_match[0]:
                best, best_match = candidate, match
        if not ok and best_match is not None:
            shared, size, idx = best_match
            warnings.append(
                f"Biến thể #{v + 1} khá giống biến thể #{idx + 1} (trùng "
                f"{shared}/{size} đoạn) — có thể do chưa đủ đoạn nguồn cho "
                "số biến thể này."
            )
        else:
            warnings.append(None)
        accepted.append(best)
    return accepted, warnings


def main():
    import random

    ap = argparse.ArgumentParser(
        description="Tách scene từ nhiều video + trộn lẫn ngẫu nhiên"
    )
    ap.add_argument("--input", required=True, nargs="+",
                    help="Một hoặc nhiều video đầu vào")
    ap.add_argument("--outdir", default="remix_out", help="Thư mục xuất")
    ap.add_argument("--variants", type=int, default=1, help="Số video mới tạo ra")
    ap.add_argument("--threshold", type=float, default=27.0,
                    help="Ngưỡng phát hiện scene (thấp=nhạy hơn, mặc định 27)")
    ap.add_argument("--detector", choices=["content", "adaptive"], default="content",
                    help="Thuật toán: content (mặc định) hoặc adaptive")
    ap.add_argument("--min-scene-len", type=float, default=0.0,
                    help="Độ dài scene tối thiểu khi detect (giây)")
    ap.add_argument("--merge-similar", action="store_true",
                    help="Gộp lại các đoạn liền kề nhìn giống nhau (giảm tách "
                         "vụn do rung lắc/mất nét/đổi filter)")
    ap.add_argument("--merge-threshold", type=int, default=8,
                    help="Ngưỡng coi là 'giống nhau' khi gộp (0-64, thấp hơn = "
                         "khắt khe hơn, mặc định 8)")
    ap.add_argument("--min-clip-len", type=float, default=0.0,
                    help="Bỏ clip ngắn hơn (giây)")
    ap.add_argument("--max-clips", type=int, default=0,
                    help="Giới hạn số clip mỗi biến thể (0 = không giới hạn)")
    ap.add_argument("--target-min", type=float, default=30.0,
                    help="Độ dài tối thiểu mỗi biến thể (giây, mặc định 30)")
    ap.add_argument("--target-max", type=float, default=45.0,
                    help="Độ dài tối đa mỗi biến thể (giây, mặc định 45; có thể "
                         "vượt nếu 1 đoạn dài hơn và chưa đạt tối thiểu)")
    ap.add_argument("--seed", type=int, default=None, help="Seed ngẫu nhiên")
    ap.add_argument("--keep-clips", action="store_true",
                    help="Giữ lại các clip lẻ đã tách")
    ap.add_argument("--strip-audio", action="store_true", help="Bỏ âm thanh")
    ap.add_argument("--has-outro", action="store_true",
                    help="Coi scene CUỐI của mỗi video là outro/logo cố định: "
                         "tách riêng, không xáo trộn, chỉ giữ 1 outro ở cuối "
                         "mỗi video kết quả")
    args = ap.parse_args()

    paths = [Path(p) for p in args.input]
    for p in paths:
        if not p.exists():
            sys.exit(f"Không tìm thấy file: {p}")
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    clips_dir = outdir / "clips"
    rng = random.Random(args.seed)

    def on_source(i, total, name, n_scenes, n_clips):
        print(f"→ [{i + 1}/{total}] {name}: {n_scenes} scene, {n_clips} clip")
        if n_scenes <= 1:
            print("  [CẢNH BÁO] Chỉ 1 scene — thử giảm --threshold (vd 20) "
                  "hoặc dùng --detector adaptive.")

    print(f"→ Xử lý {len(paths)} video đầu vào…")
    clips, outro_clip, infos, scene_counts = process_sources(
        paths, clips_dir, args.threshold, args.detector, args.min_scene_len,
        args.min_clip_len, args.strip_audio, args.has_outro,
        args.merge_similar, args.merge_threshold, on_source=on_source,
    )
    if not clips:
        sys.exit("Không tách được clip nào từ các video đầu vào.")
    clip_durs = {c: ffprobe_info(c)["duration"] for c in clips}
    print(f"  Tổng cộng {len(clips)} clip nội dung trong rổ chung.")

    outro_dur = 0.0
    if outro_clip:
        outro_dur = ffprobe_info(outro_clip)["duration"]
        clip_durs[outro_clip] = outro_dur
        print(f"  Outro: {outro_clip.name} ({outro_dur:.1f}s) — dùng chung cho mọi biến thể.")

    content_min = max(1.0, args.target_min - outro_dur)
    content_max = max(content_min, args.target_max - outro_dur)

    print(f"→ Tạo {args.variants} biến thể remix…")
    orders, similarity_warnings = build_variants(
        clips, rng, clip_durs, content_min, content_max, args.variants,
        args.max_clips,
    )
    made = []
    for v, order in enumerate(orders, start=1):
        full_order = order + [outro_clip] if outro_clip else order
        out_path = outdir / f"remix_{v:02d}.mp4"
        concat_clips(full_order, out_path, outdir)
        d = sum(clip_durs[c] for c in full_order)
        made.append(out_path)
        print(f"  ✓ {out_path.name}  ({len(full_order)} clip, ~{d:.1f}s)")
        w = similarity_warnings[v - 1]
        if w:
            print(f"  [CẢNH BÁO] {w}")

    if not args.keep_clips:
        for c in clips:
            c.unlink(missing_ok=True)
        if outro_clip:
            outro_clip.unlink(missing_ok=True)
        try:
            clips_dir.rmdir()
        except OSError:
            pass
    else:
        print(f"  (Giữ clip lẻ tại {clips_dir}/)")

    print("\nXong! File kết quả:")
    for m in made:
        print(f"  {m}")


if __name__ == "__main__":
    main()
