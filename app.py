"""Video Tools — giao diện web đơn giản chạy trên máy, gồm 2 công cụ:

  🎬 Video Remixer — kéo-thả nhiều video vào, tách từng đoạn theo cảnh, xáo
     trộn ngẫu nhiên rồi ghép lại thành nhiều video mới, dùng làm creative
     chạy ads.

  ✂️ Cắt & Gắn Outro — tải lên nhiều video của ĐỐI THỦ (có outro/CTA giống
     nhau ở cuối), tự động cắt bỏ outro đó và gắn outro của MÌNH vào thay
     thế, giữ nguyên nội dung gốc — không xáo trộn/ghép gì.

  🚫 Che Logo Đối Thủ — khoanh vùng logo/chữ thương hiệu đối thủ ở 1 khung
     hình, tool tự bám theo (object tracking) và vẽ đè logo của bạn lên
     đúng vị trí trong phạm vi 1 cảnh liên tục.

  Cả 3 tính năng khác biệt hoàn toàn về mục đích/logic, chỉ dùng chung giao
  diện app.
"""

import random
import re
import shutil
import tempfile
import uuid
from pathlib import Path

import cv2
import numpy as np
import streamlit as st
from PIL import Image
from streamlit_cropper import st_cropper

import remix_core as core
import outro_core
import logo_cover_core

st.set_page_config(page_title="Video Tools", page_icon="🎬", layout="wide")

# Khoá tạm tính năng "Che Logo Đối Thủ" — hiện màn hình "sắp ra mắt" thay vì
# giao diện thật (đã build xong, chỉ đang ẩn). Đổi thành False để mở lại.
LOGO_COVER_LOCKED = True
COMING_SOON_GIF = "https://media.giphy.com/media/IhEXkpvYS0rYH8A4eq/giphy.gif"

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

    /* Thanh menu bên trái: cho ô radio trông giống danh sách điều hướng,
    tô nền đen cho mục đang chọn — chỉ đổi màu nền/chữ, KHÔNG đụng tới
    font-family, để chữ tiếng Việt luôn hiển thị đúng. Ép rộng hết chiều
    ngang thanh bên trái (trước đó chỉ vừa khít chữ). */
    section[data-testid="stSidebar"] div[role="radiogroup"] {
        width: 100%;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label {
        display: flex; padding: 0.55rem 0.7rem; border-radius: 8px;
        width: 100%; box-sizing: border-box; margin-bottom: 2px;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label > div {
        width: 100%;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background-color: #F0F0F0;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
        background-color: #111111;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p {
        color: #FFFFFF;
    }

    /* Ghim khối tài khoản/đăng xuất xuống cuối thanh bên trái — neo trực
    tiếp theo chiều cao màn hình (100vh) ở đúng vùng nội dung sidebar, tránh
    phụ thuộc chuỗi height % của nhiều lớp cha (dễ gãy giữa chừng, gây hiện
    tượng chỉ cao được 1 nửa). */
    [data-testid="stSidebarUserContent"] {
        display: flex; flex-direction: column; min-height: 100vh;
    }
    .st-key-sidebar_footer { margin-top: auto; }

    /* Chuyển mượt khi ảnh xem trước outro đổi giữa mờ (không được chọn) và
    rõ (đang chọn), thay vì đổi ngay lập tức. */
    [data-testid="stImage"] img { transition: filter 0.25s ease, opacity 0.25s ease; }
    </style>
    """,
    unsafe_allow_html=True,
)

OUTRO_DIR = Path(__file__).parent / "outros"
OUTRO_DIR.mkdir(exist_ok=True)
# Mỗi loại giờ là 1 THƯ MỤC chứa được nhiều outro (thay vì đúng 1 file cố
# định như trước) — người dùng chọn 1 trong số đó mỗi lần chạy.
OUTRO_CATEGORY_SLUGS = {"Photo app": "photo", "Language app": "language"}


def _outro_dir_for(category):
    d = OUTRO_DIR / OUTRO_CATEGORY_SLUGS[category]
    d.mkdir(parents=True, exist_ok=True)
    # Di cư dữ liệu cũ (1 file cố định outros/photo.mp4) sang cấu trúc thư
    # mục mới nếu có, để không mất outro đã upload từ trước.
    legacy_file = OUTRO_DIR / f"{OUTRO_CATEGORY_SLUGS[category]}.mp4"
    if legacy_file.exists() and not any(d.iterdir()):
        legacy_file.rename(d / legacy_file.name)
    return d


def _list_outros(category):
    d = _outro_dir_for(category)
    files = [f for ext in ("*.mp4", "*.mov", "*.mkv") for f in d.glob(ext)]
    return sorted(files, key=lambda p: p.name.lower())


def _enforce_single_outro_tick(category, just_ticked_name, all_names):
    """Tích 1 outro mới thì TỰ BỎ TÍCH các outro khác cùng loại — mô phỏng
    chọn kiểu radio (chỉ 1 cái được chọn) nhưng vẫn giữ được lưới thumbnail
    tự do thay vì dùng st.radio (không chèn ảnh theo từng ô được)."""
    if not st.session_state.get(f"outro_tick_{category}_{just_ticked_name}"):
        return
    for name in all_names:
        if name != just_ticked_name:
            st.session_state[f"outro_tick_{category}_{name}"] = False


@st.cache_data(show_spinner=False)
def _outro_preview(path_str, mtime, max_width=190):
    """Ảnh thumbnail (RGB, đã thu nhỏ) + thời lượng của 1 outro — cache theo
    (đường dẫn, thời điểm sửa file) để KHÔNG phải đọc lại video/gọi ffprobe
    mỗi khi trang tự load lại (vd tích ô khác, đổi loại outro...). Thu nhỏ
    ảnh xuống `max_width` px vì đây chỉ là ảnh xem trước nhỏ — ảnh gốc có
    thể full-HD, nặng và chậm khi Streamlit phải truyền lại mỗi lần trang
    load lại (dù không tính lại từ video nhờ cache, riêng việc gửi ảnh lớn
    qua lại vẫn gây trễ)."""
    path = Path(path_str)
    frame = core._grab_frame_bgr(path, 0.3)
    thumb = None
    if frame is not None:
        h, w = frame.shape[:2]
        if w > max_width:
            frame = cv2.resize(frame, (max_width, int(h * max_width / w)), interpolation=cv2.INTER_AREA)
        thumb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    duration = core.ffprobe_info(path)["duration"]
    return thumb, duration


@st.cache_data(show_spinner=False)
def _outro_duration(path_str, mtime):
    """Chỉ lấy thời lượng (không kèm thumbnail) — cache riêng để dùng ở mục
    quản lý (hiển thị video thật, không cần ảnh xem trước) mà vẫn tránh gọi
    lại ffprobe mỗi khi trang tự load lại."""
    return core.ffprobe_info(Path(path_str))["duration"]


def _fade_thumb(thumb, amount=0.7):
    """Làm ảnh nhạt dần về màu trắng (amount=0 giữ nguyên, 1 = trắng hoàn
    toàn) — dùng để làm mờ các outro KHÔNG được chọn, làm nổi bật cái đang
    chọn."""
    if thumb is None:
        return None
    faded = thumb.astype(np.float32) * (1 - amount) + 255 * amount
    return faded.astype(np.uint8)

# Mật khẩu chung chặn người lạ — đặt trong .streamlit/secrets.toml (máy này)
# hoặc mục "Secrets" của Streamlit Cloud (lúc deploy), KHÔNG viết thẳng vào
# code/git. Dạng: APP_PASSWORD = "..."
#
# Đây là giải pháp tạm, đơn giản, làm được ngay không cần dịch vụ ngoài. Khi
# nào cần chặt chẽ hơn (phân biệt từng người dùng theo email @apero.vn /
# @talent.apero.vn) có thể nâng cấp sang đăng nhập Google (st.login) sau,
# không phải viết lại gì nhiều — chỉ thay nội dung hàm require_login() này.


def require_login():
    """Chặn truy cập nếu chưa nhập đúng mật khẩu chung của team. (Nút đăng
    xuất nằm ở thanh bên trái, xem render_sidebar_nav().)"""
    if st.session_state.get("authed"):
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


def _sanitize_name_prefix(name):
    name = name.strip()
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def apply_output_naming(paths, prefix):
    """Đổi tên các file kết quả theo cú pháp "prefix.1", "prefix.2", ... nếu
    người dùng có nhập tên ở ô 'Đặt tên file xuất ra' — giữ nguyên tên mặc
    định (tự động) nếu để trống."""
    prefix = _sanitize_name_prefix(prefix) if prefix else ""
    if not prefix:
        return paths
    renamed = []
    for i, p in enumerate(paths, start=1):
        new_path = p.parent / f"{prefix}.{i}{p.suffix}"
        try:
            p.rename(new_path)
            renamed.append(new_path)
        except OSError:
            renamed.append(p)  # doi ten loi (vd trung ten file) -> giu nguyen, khong chan luong
    return renamed


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

    output_name = st.text_input(
        "Đặt tên file xuất ra (tuỳ chọn)",
        placeholder="vd: hieund.apero → hieund.apero.1, hieund.apero.2, ...",
        key="remix_output_name",
        help="Để trống thì dùng tên tự động (remix_01, remix_02, ...).",
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

                made = apply_output_naming(made, output_name)

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

    with st.expander("⚙️ Quản lý outro của tôi (lưu nhiều outro mỗi loại, dùng lại nhiều lần)"):
        for category in OUTRO_CATEGORY_SLUGS:
            st.markdown(f"**{category}**")
            outro_dir = _outro_dir_for(category)
            existing = _list_outros(category)

            if existing:
                cols = st.columns(4)
                for idx, f in enumerate(existing):
                    with cols[idx % 4]:
                        # Mục quản lý xem lại được toàn bộ video (đúng chất
                        # lượng gốc), KHÁC với ảnh nhỏ ở mục tích chọn bên
                        # dưới (cố tình thu nhỏ để thao tác nhanh, không lag).
                        st.video(str(f))
                        dur = _outro_duration(str(f), f.stat().st_mtime)
                        st.caption(f"{dur:.1f}s")
                        new_name = st.text_input(
                            "Tên", value=f.stem, key=f"rename_outro_{category}_{f.name}",
                            label_visibility="collapsed",
                        )
                        rcol, dcol = st.columns(2)
                        if rcol.button("✏️ Đổi tên", key=f"rename_btn_{category}_{f.name}", use_container_width=True):
                            clean_name = _sanitize_name_prefix(new_name)
                            if not clean_name:
                                st.error("Tên không được để trống.")
                            elif clean_name == f.stem:
                                st.info("Tên không đổi.")
                            else:
                                new_path = f.parent / f"{clean_name}{f.suffix}"
                                if new_path.exists():
                                    st.error(f"Đã có outro tên '{clean_name}' rồi, chọn tên khác.")
                                else:
                                    f.rename(new_path)
                                    st.rerun()
                        if dcol.button("🗑️ Xoá", key=f"del_outro_{category}_{f.name}", use_container_width=True):
                            f.unlink(missing_ok=True)
                            st.rerun()
            else:
                st.caption("Chưa có outro nào cho loại này — thêm ở ô bên dưới.")

            new_files = st.file_uploader(
                f"Thêm outro mới cho {category} (chọn được nhiều file cùng lúc)",
                type=["mp4", "mov", "mkv"], accept_multiple_files=True,
                key=f"outro_upload_multi_{category}",
            )
            if new_files:
                # File tải lên vẫn còn "dính" trong ô upload ở MỌI lần trang
                # tự load lại sau đó, nên phải nhớ đã lưu batch NÀY rồi — nếu
                # không, code sẽ tưởng là file mới, ghi lại + rerun() liên
                # tục mỗi lần trang tải lại, khiến trang cứ tự nhảy không dừng.
                sig = tuple((f.name, f.size) for f in new_files)
                if st.session_state.get(f"outro_saved_sig_{category}") != sig:
                    for f in new_files:
                        (outro_dir / f.name).write_bytes(f.getvalue())
                    st.session_state[f"outro_saved_sig_{category}"] = sig
                    st.success(f"Đã thêm {len(new_files)} outro vào '{category}'.")
                    st.rerun()
            st.divider()

    uploaded_files = st.file_uploader(
        "Kéo-thả video của đối thủ vào đây — có thể tải rất nhiều video cùng lúc, "
        "kể cả TRỘN LẪN nhiều app/đối thủ khác nhau, tool tự tách đúng theo từng "
        "nhóm (mỗi nhóm cần ≥2 video cùng outro mới nhận diện chính xác được)",
        type=["mp4", "mov", "mkv", "avi", "webm"],
        accept_multiple_files=True,
        key="outro_uploader",
    )
    has_files = bool(uploaded_files)

    outro_category = st.selectbox("Loại outro của tôi", list(OUTRO_CATEGORY_SLUGS.keys()),
                                   key="outro_category_choice")
    available_outros = _list_outros(outro_category)

    chosen_outro_path = None
    if not available_outros:
        st.warning(f"Chưa có outro nào cho '{outro_category}' — mở mục 'Quản lý outro của tôi' ở trên để thêm.")
    else:
        st.write(f"Tích chọn outro muốn dùng cho '{outro_category}' (tích cái khác sẽ tự bỏ tích cái cũ):")
        all_names = [f.name for f in available_outros]
        selected_name = next(
            (n for n in all_names if st.session_state.get(f"outro_tick_{outro_category}_{n}")), None,
        )
        cols = st.columns(6)
        picked = []
        for idx, f in enumerate(available_outros):
            with cols[idx % 6]:
                thumb, dur = _outro_preview(str(f), f.stat().st_mtime)
                if selected_name is not None and f.name != selected_name:
                    thumb = _fade_thumb(thumb)  # KHONG duoc chon -> lam mo trang di, noi bat cai dang chon
                if thumb is not None:
                    st.image(thumb, use_container_width=True)
                if st.checkbox(
                    f"{f.stem} ({dur:.1f}s)", key=f"outro_tick_{outro_category}_{f.name}",
                    on_change=_enforce_single_outro_tick,
                    args=(outro_category, f.name, all_names),
                ):
                    picked.append(f)

        if len(picked) == 0:
            st.warning("Chưa tích chọn outro nào.")
        else:
            chosen_outro_path = picked[0]

    outro_ready = chosen_outro_path is not None

    with st.expander("Tuỳ chọn nâng cao (không cần đụng vào nếu không rõ)"):
        match_threshold = st.number_input(
            "Ngưỡng nhận outro chung giữa các video (thấp = khắt khe hơn, ít nhận "
            "nhầm nhưng dễ bỏ sót)",
            min_value=1, max_value=100, value=outro_core.DEFAULT_MATCH_THRESHOLD, step=1,
        )
        max_workers = st.number_input(
            "Số video xử lý song song cùng lúc (tăng lên nếu máy chủ nhiều lõi CPU "
            "để xử lý nhanh hơn khi tải lên nhiều video; giảm xuống nếu bị treo/lỗi "
            "do quá tải)",
            min_value=1, max_value=16, value=4, step=1, key="outro_max_workers",
        )
        strip_audio = st.checkbox("Bỏ âm thanh trong video kết quả", key="outro_strip_audio")

    output_name = st.text_input(
        "Đặt tên file xuất ra (tuỳ chọn)",
        placeholder="vd: hieund.apero → hieund.apero.1, hieund.apero.2, ...",
        key="outro_output_name",
        help="Để trống thì dùng tên tự động (outro_swap_01, outro_swap_02, ...).",
    )

    run_clicked = st.button("Xử lý", type="primary", disabled=not (has_files and outro_ready))

    if run_clicked and has_files and outro_ready:
        st.session_state.outro_outputs = []
        st.session_state.outro_run_error = None
        workdir, input_paths = save_uploads(uploaded_files, prefix="outro_swap_")

        try:
            with st.status("Đang xử lý video...", expanded=True) as status:
                made = []

                def on_source(done, total, name, result):
                    if result["reason"] == "matched":
                        status.write(
                            f"[{done}/{total}] ✓ {name}: nhận diện chắc chắn — đã cắt "
                            f"{result['outro_cut_seconds']:.1f}s outro đối thủ, gắn "
                            "outro của bạn vào cuối."
                        )
                    else:
                        status.write(
                            f"[{done}/{total}] ⚠️ {name}: không tìm được video nào "
                            "khác cùng outro trong mẻ này (có thể do nó không có "
                            "outro, hoặc là app duy nhất/lẻ trong mẻ tải lên) — "
                            "KHÔNG dám cắt liều để tránh mất nội dung thật, nhưng "
                            "**outro của bạn vẫn được gắn vào cuối** — video này có "
                            "thể có 2 outro nối tiếp nhau (outro cũ của đối thủ nếu "
                            "có, rồi tới outro của bạn), nên xem lại riêng video này."
                        )
                    made.append(result)

                outro_core.process_outro_swap(
                    input_paths, chosen_outro_path, workdir, strip_audio,
                    tail_match_threshold=match_threshold, on_source=on_source,
                    max_workers=int(max_workers),
                )

                new_paths = apply_output_naming([r["path"] for r in made], output_name)
                for r, new_p in zip(made, new_paths):
                    r["path"] = new_p

                status.update(label="Xong!", state="complete", expanded=False)

            st.session_state.outro_outputs = made

        except RuntimeError as e:
            st.session_state.outro_run_error = str(e)

    if st.session_state.outro_run_error:
        st.error(f"Xử lý thất bại: {st.session_state.outro_run_error}")

    if st.session_state.outro_outputs:
        st.subheader("Kết quả")
        render_results_grid([r["path"] for r in st.session_state.outro_outputs], "outro_dl")


def render_logo_cover():
    """Tab 'Che Logo Đối Thủ' — khoanh vùng logo/chữ thương hiệu đối thủ ở 1
    khung hình, tool bám theo (object tracking) trong phạm vi 1 cảnh liên
    tục và vẽ đè logo của bạn lên đúng vị trí + kích thước đã bám được.

    Đã thử nghiệm và bỏ hướng tự động hoàn toàn (không biết trước watermark
    là gì) vì không khả thi với video quay tay/cắt cảnh nhanh — xem
    logo_cover_core.py để biết chi tiết lý do.

    Hiện đang KHOÁ TẠM (xem LOGO_COVER_LOCKED ở đầu file) cho người dùng
    thường — code phía dưới vẫn hoạt động đầy đủ, chỉ ẩn sau màn hình "sắp
    ra mắt". Có ô nhỏ cuối trang để người test nội bộ (biết mật khẩu riêng
    DEV_UNLOCK_PASSWORD) mở khoá thử nghiệm mà không cần tắt khoá chung."""
    if LOGO_COVER_LOCKED and not st.session_state.get("logo_cover_unlocked"):
        st.title("🚫 Che Logo Đối Thủ")
        st.markdown("### 🚧 Skill upcoming...")
        st.image(COMING_SOON_GIF, use_container_width=True)
        st.caption("Đang hoàn thiện thêm — quay lại sau nhé ☕")

        with st.expander("🔧 Dành cho người test nội bộ"):
            dev_pwd = st.text_input("Mật khẩu test", type="password", key="logo_cover_dev_pwd")
            if st.button("Mở khoá để test", key="logo_cover_unlock_btn"):
                correct = st.secrets.get("DEV_UNLOCK_PASSWORD")
                if correct and dev_pwd == correct:
                    st.session_state["logo_cover_unlocked"] = True
                    st.rerun()
                else:
                    st.error("Sai mật khẩu test.")
        return

    st.title("🚫 Che Logo Đối Thủ")
    st.caption(
        "Khoanh vùng logo/chữ thương hiệu đối thủ ở 1 khung hình — tool tự "
        "bám theo (object tracking) và vẽ đè logo của bạn lên đúng vị trí."
    )
    st.info(
        "⚠️ Giới hạn: tool chỉ bám theo trong phạm vi **1 cảnh liên tục** — "
        "nếu video cắt sang cảnh khác, cần khoanh vùng lại riêng cho cảnh "
        "đó (chạy tool thêm lần nữa). Đây là đánh đổi để đảm bảo không che "
        "sai chỗ, thay vì cố tự động hoàn toàn (đã thử, không chính xác)."
    )

    for key, default in [("cover_result", None), ("cover_error", None)]:
        if key not in st.session_state:
            st.session_state[key] = default

    uploaded = st.file_uploader(
        "Video đối thủ (1 video)", type=["mp4", "mov", "mkv", "avi", "webm"],
        accept_multiple_files=False, key="cover_uploader",
    )
    logo_file = st.file_uploader(
        "Logo/trademark của bạn (khuyến khích ảnh PNG nền trong suốt để che đẹp hơn)",
        type=["png", "jpg", "jpeg"], key="cover_logo_uploader",
    )

    if not uploaded:
        st.caption("Tải video lên để bắt đầu.")
        return

    sig = (uploaded.name, uploaded.size)
    if st.session_state.get("cover_video_sig") != sig:
        workdir, paths = save_uploads([uploaded], prefix="logo_cover_")
        st.session_state.cover_video_sig = sig
        st.session_state.cover_workdir = workdir
        st.session_state.cover_video_path = paths[0]
        st.session_state.cover_result = None
        st.session_state.cover_error = None
    workdir = st.session_state.cover_workdir
    video_path = st.session_state.cover_video_path

    info = core.ffprobe_info(video_path)
    duration = info["duration"]

    t0 = st.slider(
        "Kéo tới giây đang thấy RÕ logo/chữ cần che", 0.0, max(duration, 0.1),
        min(2.0, duration), 0.1, key="cover_t0",
    )
    frame_bgr = core._grab_frame_bgr(video_path, t0)
    if frame_bgr is None:
        st.error("Không đọc được khung hình tại giây này, thử kéo sang mốc khác.")
        return
    pil_img = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))

    st.write("Kéo/chỉnh khung đỏ bên dưới cho vừa khít logo/chữ cần che:")
    box = st_cropper(
        pil_img, return_type="box", box_color="#FF0000",
        key=f"cropper_{sig[0]}_{sig[1]}",
    )
    bbox = (int(box["left"]), int(box["top"]), int(box["width"]), int(box["height"]))

    with st.expander("Tuỳ chọn nâng cao (không cần đụng vào nếu không rõ)"):
        detector = st.selectbox(
            "Cách nhận diện điểm cắt cảnh", ["content", "adaptive"], key="cover_detector",
        )
        threshold = st.number_input(
            "Độ nhạy cắt cảnh", min_value=1.0, max_value=100.0, value=27.0, step=1.0,
            key="cover_threshold",
        )
        min_scene_len = st.number_input(
            "Độ dài scene tối thiểu (giây)", min_value=0.0, value=0.5, step=0.1,
            key="cover_min_scene_len",
        )
        tracker_name = st.selectbox(
            "Thuật toán bám theo", list(logo_cover_core.TRACKER_FACTORIES.keys()),
            key="cover_tracker",
        )
        cover_scale = st.slider(
            "Độ phóng to logo che (đảm bảo che kín hoàn toàn, không hở viền)",
            min_value=1.0, max_value=2.0, value=1.15, step=0.05, key="cover_scale",
        )

    output_name = st.text_input(
        "Đặt tên file xuất ra (tuỳ chọn)",
        placeholder="vd: hieund.apero → hieund.apero.1",
        key="cover_output_name",
        help="Để trống thì dùng tên tự động.",
    )

    if not logo_file:
        st.warning("Cần tải lên logo/trademark của bạn (ô phía trên) trước khi xử lý.")
    run_clicked = st.button("Xử lý", type="primary", disabled=not logo_file)

    if run_clicked and logo_file:
        logo_path = workdir / f"logo_{uuid.uuid4().hex[:8]}{Path(logo_file.name).suffix}"
        logo_path.write_bytes(logo_file.getvalue())
        out_path = workdir / f"covered_{uuid.uuid4().hex[:8]}.mp4"
        st.session_state.cover_error = None
        try:
            with st.spinner("Đang bám theo & che logo — có thể mất 1-2 phút..."):
                result = logo_cover_core.cover_logo_in_scene(
                    video_path, logo_path, out_path, workdir, t0, bbox,
                    threshold, detector, min_scene_len, tracker_name, cover_scale,
                )
            result["out_path"] = apply_output_naming([result["out_path"]], output_name)[0]
            st.session_state.cover_result = result
        except RuntimeError as e:
            st.session_state.cover_error = str(e)

    if st.session_state.cover_error:
        st.error(f"Xử lý thất bại: {st.session_state.cover_error}")

    if st.session_state.cover_result:
        r = st.session_state.cover_result
        st.subheader("Kết quả")
        msg = (
            f"Đã che từ giây {r['covered_start']:.1f}s đến {r['covered_end']:.1f}s "
            f"(cảnh này kéo dài {r['scene_start']:.1f}s–{r['scene_end']:.1f}s)."
        )
        if r["lost_forward"] or r["lost_backward"]:
            st.warning(
                msg + " ⚠️ Bị MẤT DẤU trước khi hết cảnh — phần còn lại của cảnh "
                "này CHƯA được che, khoanh vùng lại riêng cho đoạn đó nếu cần."
            )
        else:
            st.success(msg + " Che trọn vẹn cả cảnh, không bị mất dấu giữa chừng.")
        render_results_grid([r["out_path"]], "cover_dl")


check_ffmpeg()

# Danh sách công cụ hiện trên thanh menu bên trái — thêm công cụ mới sau này
# chỉ cần thêm 1 dòng vào đây (nhãn hiện trên menu -> hàm render tương ứng),
# không cần sửa gì chỗ khác.
PAGES = {
    "🎬  Video Remixer": render_video_remixer,
    "✂️  Cắt & Gắn Outro": render_outro_swap,
    "🚫  Che Logo Đối Thủ": render_logo_cover,
}

with st.sidebar:
    st.markdown("## 🧰 Video Tools")
    st.caption("Bộ công cụ nội bộ Apero")
    choice = st.radio(
        "Công cụ", list(PAGES.keys()), label_visibility="collapsed", key="nav_choice",
    )
    with st.container(key="sidebar_footer"):
        st.divider()
        st.caption("🔓 Đã đăng nhập")
        st.button("Đăng xuất", on_click=lambda: st.session_state.pop("authed", None), key="logout_btn")

PAGES[choice]()
