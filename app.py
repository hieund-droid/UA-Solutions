"""Video Tools — giao diện web đơn giản chạy trên máy, gồm 2 công cụ:

  🎬 Video Remixer — kéo-thả nhiều video vào, tách từng đoạn theo cảnh, xáo
     trộn ngẫu nhiên rồi ghép lại thành nhiều video mới, dùng làm creative
     chạy ads.

  ✂️ Cắt & Gắn Outro — tải lên nhiều video của ĐỐI THỦ (có outro/CTA giống
     nhau ở cuối), tự động cắt bỏ outro đó và gắn outro của MÌNH vào thay
     thế, giữ nguyên nội dung gốc — không xáo trộn/ghép gì. Đây là tính
     năng khác biệt hoàn toàn với Video Remixer, chỉ dùng chung giao diện.
"""

import random
import shutil
import tempfile
import uuid
from pathlib import Path

import streamlit as st

import remix_core as core
import outro_core

st.set_page_config(page_title="Video Tools", page_icon="🎬", layout="wide")

st.markdown(
    """
    <style>
    .block-container { padding-top: 2.5rem; padding-bottom: 3rem; max-width: 1200px; }
    h1, h2, h3 { letter-spacing: -0.02em; }
    div.stButton > button, div.stDownloadButton > button {
        border-radius: 8px; border: 1px solid #111111; font-weight: 600;
    }
    div.stButton > button[kind="primary"], div.stDownloadButton > button {
        background-color: #111111; color: #FFFFFF;
    }
    div.stButton > button[kind="primary"]:hover, div.stDownloadButton > button:hover {
        background-color: #333333; border-color: #333333; color: #FFFFFF;
    }
    div.stButton > button[kind="secondary"] {
        background-color: #FFFFFF; color: #111111;
    }
    [data-testid="stFileUploaderDropzone"] {
        border-radius: 10px; border: 1.5px dashed #cccccc;
    }
    [data-testid="stExpander"] {
        border: 1px solid #e5e5e5; border-radius: 10px;
    }
    [data-testid="stTabs"] button [data-testid="stMarkdownContainer"] p {
        font-size: 1.02rem; font-weight: 600;
    }
    hr { margin: 1.6rem 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

OUTRO_DIR = Path(__file__).parent / "outros"
OUTRO_DIR.mkdir(exist_ok=True)
OUTRO_PRESETS = {"Photo app": OUTRO_DIR / "photo.mp4", "Language app": OUTRO_DIR / "language.mp4"}

# Mật khẩu chung chặn người lạ — đặt trong .streamlit/secrets.toml (máy này)
# hoặc mục "Secrets" của Streamlit Cloud (lúc deploy), KHÔNG viết thẳng vào
# code/git. Dạng: APP_PASSWORD = "..."
#
# Đây là giải pháp tạm, đơn giản, làm được ngay không cần dịch vụ ngoài. Khi
# nào cần chặt chẽ hơn (phân biệt từng người dùng theo email @apero.vn /
# @talent.apero.vn) có thể nâng cấp sang đăng nhập Google (st.login) sau,
# không phải viết lại gì nhiều — chỉ thay nội dung hàm require_login() này.


def require_login():
    """Chặn truy cập nếu chưa nhập đúng mật khẩu chung của team."""
    if st.session_state.get("authed"):
        with st.sidebar:
            st.button("Đăng xuất", on_click=lambda: st.session_state.pop("authed", None), key="logout_btn")
        return

    correct_password = st.secrets.get("APP_PASSWORD")
    if not correct_password:
        st.warning(
            "⚠️ Chưa đặt mật khẩu (APP_PASSWORD trong Secrets) — hiện ai có "
            "link cũng vào dùng được. Nhớ đặt mật khẩu trước khi chia sẻ link "
            "cho người khác."
        )
        return

    st.title("🎬 Video Tools")
    pwd = st.text_input("Nhập mật khẩu truy cập", type="password")
    if st.button("Vào"):
        if pwd == correct_password:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("Sai mật khẩu.")
    st.stop()


require_login()


def check_ffmpeg():
    missing = [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]
    if missing:
        st.error(
            "Thiếu " + ", ".join(missing) + " trên máy. Cài ffmpeg rồi mở lại app này."
        )
        st.stop()


def save_uploads(uploaded_files, prefix="video_remixer_"):
    workdir = Path(tempfile.mkdtemp(prefix=prefix))
    paths = []
    for f in uploaded_files:
        p = workdir / f"src_{uuid.uuid4().hex[:8]}{Path(f.name).suffix}"
        p.write_bytes(f.getvalue())
        paths.append(p)
    return workdir, paths


def render_results_grid(paths, download_key_prefix, cols_per_row=3):
    """Hiển thị các video kết quả dạng lưới (thay vì xếp chồng dọc) — tận
    dụng bố cục rộng, dễ xem/tải nhiều video cùng lúc hơn."""
    existing = [p for p in paths if p.exists()]
    if not existing:
        return
    cols = st.columns(cols_per_row)
    for i, out_path in enumerate(existing):
        with cols[i % cols_per_row]:
            st.video(str(out_path))
            st.download_button(
                f"⬇️ {out_path.name}",
                data=out_path.read_bytes(),
                file_name=out_path.name,
                mime="video/mp4",
                key=f"{download_key_prefix}_{out_path.name}_{i}",
                use_container_width=True,
            )


def render_video_remixer():
    """Tab 'Video Remixer' — HÀNH VI GIỮ NGUYÊN 100% so với trước, chỉ tách
    ra thành hàm riêng để dùng chung giao diện với tab 'Cắt & Gắn Outro'."""
    st.title("🎬 Video Remixer")
    st.caption(
        "Tách nhiều video thành từng đoạn theo cảnh, trộn lẫn ngẫu nhiên, "
        "ghép lại thành nhiều video mới."
    )

    for key, default in [
        ("outputs", []), ("scene_warning", None), ("variant_warning", None),
        ("analysis", None), ("variants_value", 5),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    uploaded_files = st.file_uploader(
        "Kéo-thả các video vào đây (có thể chọn nhiều video cùng lúc)",
        type=["mp4", "mov", "mkv", "avi", "webm"],
        accept_multiple_files=True,
        key="remix_uploader",
    )
    has_files = bool(uploaded_files)

    has_outro = st.checkbox(
        "Mỗi video có đoạn outro/logo cố định ở cuối",
        value=False,
        help=(
            "Bật lên nếu video nào cũng kết thúc bằng 1 đoạn giống nhau (logo, CTA...). "
            "Tool sẽ coi đoạn CUỐI CÙNG của mỗi video là outro, tách riêng ra khỏi rổ "
            "trộn (không xáo trộn lẫn vào giữa), và chỉ gắn đúng 1 outro vào cuối mỗi "
            "video kết quả — dù nhiều video nguồn cùng có outro giống hệt nhau."
        ),
    )

    merge_similar = st.checkbox(
        "Gộp lại các đoạn nhìn giống nhau (giảm tách vụn do rung lắc/mất nét/đổi filter)",
        value=True,
        help=(
            "So sánh hình ảnh ở ranh giới 2 đoạn liền kề; nếu giống nhau thì gộp lại "
            "thành 1 đoạn thay vì tách rời. Đây là so khung hình chứ không nhận diện "
            "khuôn mặt/bối cảnh thật, nên chỉ giảm bớt tách vụn chứ không đảm bảo "
            "đúng 100% — nếu filter đổi quá mạnh vẫn có thể bị tách nhầm."
        ),
    )

    with st.expander("Tuỳ chọn nâng cao (không cần đụng vào nếu không rõ)"):
        detector = st.selectbox(
            "Cách nhận diện đoạn cắt",
            ["content", "adaptive"],
            help="'content' phù hợp đa số trường hợp. Nếu tách sai nhiều, thử 'adaptive'.",
        )
        threshold = st.number_input(
            "Độ nhạy cắt cảnh (số nhỏ hơn = nhạy hơn, dễ tách vụn)",
            min_value=1.0, max_value=100.0, value=27.0, step=1.0,
        )
        min_scene_len = st.number_input(
            "Độ dài scene tối thiểu khi dò (giây) — tăng lên nếu bị tách vụn 1 cảnh "
            "thành nhiều đoạn",
            min_value=0.0, value=0.5, step=0.1,
        )
        merge_threshold = st.number_input(
            "Ngưỡng 'giống nhau' để gộp đoạn (0-64, thấp = khắt khe hơn)",
            min_value=0, max_value=64, value=8, step=1, disabled=not merge_similar,
        )
        min_clip_len = st.number_input(
            "Bỏ qua đoạn ngắn hơn (giây)", min_value=0.0, value=0.0, step=0.1
        )
        max_clips = st.number_input(
            "Giới hạn số đoạn mỗi video mới (0 = không giới hạn)", min_value=0, value=0, step=1
        )
        use_seed = st.checkbox("Cố định kết quả ngẫu nhiên (để tái lập lần sau)")
        seed = st.number_input("Seed", min_value=0, value=42, step=1, disabled=not use_seed)
        keep_clips = st.checkbox("Giữ lại các đoạn lẻ đã tách")
        strip_audio = st.checkbox("Bỏ âm thanh trong video mới")

    def current_signature():
        return (
            tuple((f.name, f.size) for f in uploaded_files),
            threshold, detector, min_scene_len, has_outro,
            merge_similar, merge_threshold,
        )

    st.divider()
    st.subheader("Bước 1 — Phân tích")
    st.caption("Dò thử xem mỗi video tách được bao nhiêu đoạn, trước khi quyết định tạo bao nhiêu biến thể.")

    if st.button("Phân tích video", disabled=not has_files):
        workdir, input_paths = save_uploads(uploaded_files)
        with st.spinner("Đang dò điểm cắt cảnh..."):
            analyzed = core.analyze_sources(
                input_paths, threshold, detector, min_scene_len, has_outro,
                merge_similar, merge_threshold,
            )
        st.session_state.analysis = {
            "sig": current_signature(),
            "analyzed": analyzed,
            "workdir": workdir,
        }
        total_clips = sum(len(a["content_scenes"]) for a in analyzed)
        st.session_state.variants_value = max(1, min(total_clips, 20))

    analysis = st.session_state.analysis
    if analysis and analysis["sig"] == current_signature():
        analyzed = analysis["analyzed"]
        total_clips = sum(len(a["content_scenes"]) for a in analyzed)
        total_duration = sum(a["info"]["duration"] for a in analyzed)
        n_with_outro = sum(1 for a in analyzed if a["outro_scene"])

        for a in analyzed:
            n_content = len(a["content_scenes"])
            dur = a["info"]["duration"]
            outro_note = "  (+ 1 outro ở cuối)" if a["outro_scene"] else ""
            notes = []
            if n_content <= 1 and not a["outro_scene"]:
                notes.append("⚠️ chỉ 1 đoạn, có thể tách chưa đúng")
            elif n_content >= 3:
                avg_len = dur / max(len(a["scenes"]), 1)
                if avg_len < 1.0:
                    notes.append(
                        f"⚠️ trung bình mỗi đoạn chỉ ~{avg_len:.1f}s — có thể đang bị "
                        "tách vụn 1 cảnh thành nhiều đoạn. Thử tăng 'Độ nhạy cắt cảnh' "
                        "hoặc 'Độ dài scene tối thiểu' trong Tuỳ chọn nâng cao."
                    )
            note_text = ("  " + " | ".join(notes)) if notes else ""
            st.write(f"- **{a['path'].name}**: {n_content} đoạn nội dung, {dur:.1f}s{outro_note}{note_text}")

        if has_outro and n_with_outro == 0:
            st.warning(
                "Đã bật 'có outro' nhưng không video nào tách được từ 2 đoạn trở lên "
                "để tách outro riêng — tool sẽ dùng cả video làm nội dung, không có outro."
            )

        st.success(
            f"Tổng cộng **{total_clips} đoạn nội dung** từ {len(analyzed)} video, "
            f"tổng ~{total_duration:.1f} giây gốc."
        )
        suggested = max(1, min(total_clips, 20))
        st.info(
            f"Gợi ý của tôi (không phải con số chính xác, chỉ ước lượng theo "
            f"**số đoạn tách được** — càng nhiều đoạn thì càng ghép được nhiều tổ "
            f"hợp khác nhau, không phụ thuộc thời lượng video dài hay ngắn): thử "
            f"khoảng **{suggested} biến thể**. Đây chỉ là điểm khởi đầu để tham "
            "khảo — một đoạn được dùng lại ở vài biến thể khác nhau là bình "
            "thường, tool sẽ tự kiểm tra khi bấm 'Tạo biến thể' và cảnh báo rõ "
            "nếu có cặp nào bị trùng quá nhiều."
        )
    elif has_files:
        st.caption("Chưa phân tích — bấm nút phía trên để xem trước số đoạn.")

    st.divider()
    st.subheader("Bước 2 — Tạo biến thể")

    duration_range = st.slider(
        "Thời lượng mỗi video mới (giây, không tính outro nếu có)",
        min_value=5, max_value=120, value=(30, 45),
        help=(
            "Mỗi biến thể sẽ ưu tiên ghép trong khoảng này. Nếu 1 đoạn dài hơn mức "
            "tối đa mà video vẫn chưa đạt mức tối thiểu, tool vẫn giữ nguyên đoạn đó "
            "(không cắt bớt, không bỏ phí creative) thay vì cắt ngắn hay loại bỏ."
        ),
    )
    target_min, target_max = duration_range

    variants = st.number_input(
        "Số video muốn tạo ra", min_value=1, max_value=200, step=1, key="variants_value"
    )

    run_clicked = st.button("Tạo biến thể", type="primary", disabled=not has_files)

    if run_clicked and has_files:
        st.session_state.outputs = []
        st.session_state.scene_warning = None
        st.session_state.variant_warning = None

        cached = st.session_state.analysis
        if cached and cached["sig"] == current_signature():
            analyzed = cached["analyzed"]
            workdir = cached["workdir"]
        else:
            workdir, input_paths = save_uploads(uploaded_files)
            with st.spinner("Đang dò điểm cắt cảnh..."):
                analyzed = core.analyze_sources(
                    input_paths, threshold, detector, min_scene_len, has_outro,
                    merge_similar, merge_threshold,
                )

        try:
            with st.status("Đang xử lý video...", expanded=True) as status:
                clips_dir = workdir / "clips"
                progress = st.progress(0.0)
                warnings = []

                def on_source(i, total, name, n_scenes, n_clips):
                    status.write(f"[{i + 1}/{total}] {name}: {n_scenes} đoạn tìm thấy")
                    if n_scenes <= 1:
                        warnings.append(
                            f"'{name}' chỉ tìm thấy 1 đoạn duy nhất — có thể tách chưa "
                            "đúng. Thử giảm 'Độ nhạy cắt cảnh' hoặc chọn 'adaptive'."
                        )
                    progress.progress(0.0)

                def on_progress(done, total):
                    progress.progress(min(done / max(total, 1), 1.0))

                status.write(f"Đang cắt clip từ {len(analyzed)} video...")
                clips, outro_clip = core.split_sources(
                    analyzed, clips_dir, min_clip_len, strip_audio,
                    on_source=on_source, on_progress=on_progress,
                )
                progress.empty()

                if warnings:
                    st.session_state.scene_warning = " | ".join(warnings)

                if not clips:
                    raise RuntimeError(
                        "Không tách được đoạn nào từ các video đã tải lên. "
                        "Giảm 'Bỏ qua đoạn ngắn hơn' hoặc 'Độ nhạy cắt cảnh'."
                    )

                clip_durs = {c: core.ffprobe_info(c)["duration"] for c in clips}
                status.write(f"Tổng cộng {len(clips)} đoạn nội dung trong rổ chung.")

                outro_dur = 0.0
                if outro_clip:
                    outro_dur = core.ffprobe_info(outro_clip)["duration"]
                    clip_durs[outro_clip] = outro_dur
                    status.write(f"Outro dùng chung: {outro_clip.name} ({outro_dur:.1f}s)")

                content_min = max(1.0, float(target_min) - outro_dur)
                content_max = max(content_min, float(target_max) - outro_dur)

                status.write(f"Đang ghép {variants} video mới...")
                rng = random.Random(int(seed) if use_seed else None)
                orders, similarity_warnings = core.build_variants(
                    clips, rng, clip_durs, content_min, content_max, int(variants),
                    int(max_clips) if max_clips else 0,
                )
                made = []
                variant_warnings = []
                for v, order in enumerate(orders, start=1):
                    full_order = order + [outro_clip] if outro_clip else order
                    out_path = workdir / f"remix_{v:02d}.mp4"
                    core.concat_clips(full_order, out_path, workdir)
                    made.append(out_path)
                    status.write(f"✓ {out_path.name} ({len(full_order)} đoạn)")
                    w = similarity_warnings[v - 1]
                    if w:
                        variant_warnings.append(w)

                if variant_warnings:
                    st.session_state.variant_warning = " | ".join(variant_warnings)

                if not keep_clips:
                    for c in clips:
                        c.unlink(missing_ok=True)
                    if outro_clip:
                        outro_clip.unlink(missing_ok=True)

                status.update(label="Xong!", state="complete", expanded=False)

            st.session_state.outputs = made

        except RuntimeError as e:
            st.error(f"Xử lý thất bại: {e}")

    if st.session_state.scene_warning:
        st.warning(st.session_state.scene_warning)

    if st.session_state.variant_warning:
        st.warning(st.session_state.variant_warning)

    if st.session_state.outputs:
        st.subheader("Kết quả")
        render_results_grid(st.session_state.outputs, "dl")


def render_outro_swap():
    """Tab 'Cắt & Gắn Outro' — tính năng khác biệt hoàn toàn với Video
    Remixer: cắt outro của ĐỐI THỦ ở cuối mỗi video, gắn outro của MÌNH vào
    thay thế, GIỮ NGUYÊN nội dung gốc — không xáo trộn/ghép video với nhau.
    Mỗi video đầu vào cho ra đúng 1 video kết quả tương ứng."""
    st.title("✂️ Cắt & Gắn Outro")
    st.caption(
        "Tải lên nhiều video của ĐỐI THỦ (có đoạn giới thiệu app/CTA giống "
        "nhau ở cuối) — tool tự động cắt bỏ outro đó và gắn outro của bạn "
        "vào thay thế, giữ nguyên toàn bộ nội dung phía trước."
    )

    for key, default in [("outro_outputs", []), ("outro_run_error", None)]:
        if key not in st.session_state:
            st.session_state[key] = default

    with st.expander("⚙️ Quản lý outro của tôi (upload 1 lần, dùng lại nhiều lần)"):
        for label, path in OUTRO_PRESETS.items():
            cols = st.columns([3, 2])
            if path.exists():
                dur = core.ffprobe_info(path)["duration"]
                cols[0].success(f"**{label}**: đã có sẵn ({dur:.1f}s)")
            else:
                cols[0].warning(f"**{label}**: chưa có — hãy upload")
            new_file = cols[1].file_uploader(
                f"Thay outro {label}", type=["mp4", "mov", "mkv"],
                key=f"outro_upload_{label}", label_visibility="collapsed",
            )
            if new_file is not None:
                path.write_bytes(new_file.getvalue())
                st.success(f"Đã lưu outro {label} mới.")
                st.rerun()

    uploaded_files = st.file_uploader(
        "Kéo-thả video của đối thủ vào đây (nên tải nhiều video CÙNG 1 app/chiến "
        "dịch cùng lúc — tool cần ≥2 video có outro giống nhau để nhận diện chính xác)",
        type=["mp4", "mov", "mkv", "avi", "webm"],
        accept_multiple_files=True,
        key="outro_uploader",
    )
    has_files = bool(uploaded_files)

    outro_choice = st.selectbox("Outro của tôi (gắn vào cuối mọi video kết quả)",
                                 list(OUTRO_PRESETS.keys()))
    chosen_outro_path = OUTRO_PRESETS[outro_choice]
    outro_ready = chosen_outro_path.exists()
    if not outro_ready:
        st.warning(f"Chưa có file outro cho '{outro_choice}' — mở mục 'Quản lý outro của tôi' ở trên để upload trước.")

    with st.expander("Tuỳ chọn nâng cao (không cần đụng vào nếu không rõ)"):
        detector = st.selectbox(
            "Cách nhận diện đoạn cắt (chỉ dùng cho phương án dự phòng)",
            ["content", "adaptive"], key="outro_detector",
            help="Dùng khi 1 video không khớp được outro với video nào khác.",
        )
        threshold = st.number_input(
            "Độ nhạy cắt cảnh cho phương án dự phòng", min_value=1.0, max_value=100.0,
            value=27.0, step=1.0, key="outro_scene_threshold",
        )
        min_scene_len = st.number_input(
            "Độ dài scene tối thiểu cho phương án dự phòng (giây)",
            min_value=0.0, value=0.5, step=0.1, key="outro_min_scene_len",
        )
        match_threshold = st.number_input(
            "Ngưỡng nhận outro chung giữa các video (thấp = khắt khe hơn, ít nhận "
            "nhầm nhưng dễ bỏ sót)",
            min_value=1, max_value=100, value=outro_core.DEFAULT_MATCH_THRESHOLD, step=1,
        )
        strip_audio = st.checkbox("Bỏ âm thanh trong video kết quả", key="outro_strip_audio")

    run_clicked = st.button("Xử lý", type="primary", disabled=not (has_files and outro_ready))

    if run_clicked and has_files and outro_ready:
        st.session_state.outro_outputs = []
        st.session_state.outro_run_error = None
        workdir, input_paths = save_uploads(uploaded_files, prefix="outro_swap_")

        try:
            with st.status("Đang xử lý video...", expanded=True) as status:
                made = []

                def on_source(i, total, name, result):
                    if result["reason"] == "matched":
                        status.write(
                            f"[{i + 1}/{total}] ✓ {name}: nhận diện chắc chắn — "
                            f"đã cắt {result['outro_cut_seconds']:.1f}s outro đối thủ."
                        )
                    elif result["reason"] == "fallback":
                        status.write(
                            f"[{i + 1}/{total}] ⚠️ {name}: không tìm được outro chung "
                            f"với video khác — đã dùng phương án dự phòng (cắt cảnh "
                            f"cuối cùng, {result['outro_cut_seconds']:.1f}s), có thể "
                            "không chính xác hoàn toàn."
                        )
                    else:
                        status.write(
                            f"[{i + 1}/{total}] ⚠️ {name}: không xác định được outro "
                            "— GIỮ NGUYÊN toàn bộ video gốc (video có thể có 2 outro "
                            "nối tiếp nhau nếu bản gốc vốn đã có outro riêng)."
                        )
                    made.append(result)

                outro_core.process_outro_swap(
                    input_paths, chosen_outro_path, workdir,
                    threshold, detector, min_scene_len, strip_audio,
                    tail_match_threshold=match_threshold, on_source=on_source,
                )
                status.update(label="Xong!", state="complete", expanded=False)

            st.session_state.outro_outputs = made

        except RuntimeError as e:
            st.session_state.outro_run_error = str(e)

    if st.session_state.outro_run_error:
        st.error(f"Xử lý thất bại: {st.session_state.outro_run_error}")

    if st.session_state.outro_outputs:
        st.subheader("Kết quả")
        render_results_grid([r["path"] for r in st.session_state.outro_outputs], "outro_dl")


check_ffmpeg()

tab_remix, tab_outro = st.tabs(["🎬 Video Remixer", "✂️ Cắt & Gắn Outro"])
with tab_remix:
    render_video_remixer()
with tab_outro:
    render_outro_swap()
