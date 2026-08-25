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

import base64
import io
import random
import re
import shutil
import tempfile
import time
import uuid
import zipfile
from pathlib import Path

import cv2
import numpy as np
import streamlit as st
from PIL import Image
from streamlit_cropper import st_cropper

import remix_core as core
import outro_core
import trademark_core

# Import "mềm" — nếu logo_cover_core lỗi (vd thư viện tracking khác nhau
# giữa các máy/hệ điều hành, như đã từng gặp), tab "Video Remixer" và
# "Cắt & Gắn Outro" (2 tool đang dùng thật) VẪN PHẢI chạy được bình thường,
# không được để 1 tính năng (hiện đang khoá tạm) kéo sập cả app.
try:
    import logo_cover_core
    LOGO_COVER_IMPORT_ERROR = None
except Exception as e:  # noqa: BLE001 — cố ý bắt mọi lỗi import ở đây
    logo_cover_core = None
    LOGO_COVER_IMPORT_ERROR = str(e)

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

    /* Ẩn nút thu gọn/mở rộng GỐC của Streamlit (mũi tên « ở đầu sidebar +
    nút hiện lại khi đã ẩn hẳn) — chỉ dùng ĐÚNG 1 nút thu gọn/mở rộng tự
    làm riêng (xem render_sidebar_nav ở cuối file), tránh có 2 cơ chế cùng
    lúc gây rối. */
    [data-testid="stSidebarCollapseButton"], [data-testid="collapsedControl"] {
        display: none !important;
    }

    /* Thanh menu bên trái — style nền tối, tối giản (xem render_sidebar_nav
    ở cuối file để biết phần CSS ĐỘNG theo trạng thái thu gọn/mở rộng +
    mục đang chọn, chỉ khai báo tĩnh chung ở đây). */
    section[data-testid="stSidebar"] {
        background-color: #14161b;
    }
    section[data-testid="stSidebar"] * { color: #9aa0a6; }
    [class*="st-key-nav_"] button {
        display: flex; align-items: center; justify-content: flex-start !important;
        gap: 0.6rem; width: 100%; border: none !important; background: transparent;
        border-radius: 10px; padding: 0.55rem 0.8rem; margin-bottom: 2px;
        text-align: left; font-weight: 500;
    }
    /* KHÔNG !important ở trên — để CSS động (màu nền mục ĐANG CHỌN, xem
    _sidebar_state_css) luôn thắng được, tránh 2 luật cùng độ ưu tiên
    "đấu nhau" tuỳ thứ tự chèn vào trang (đã gặp thật: nền cam của mục đang
    chọn bị luật "trong suốt mặc định" này đè mất dù chèn SAU). */
    [class*="st-key-nav_"] button:hover { background: #1e2129 !important; }
    [class*="st-key-nav_"] button p { text-align: left; }

    /* Ghim khối tài khoản/đăng xuất xuống cuối thanh bên trái — neo trực
    tiếp theo chiều cao màn hình (100vh) ở đúng vùng nội dung sidebar, tránh
    phụ thuộc chuỗi height % của nhiều lớp cha (dễ gãy giữa chừng, gây hiện
    tượng chỉ cao được 1 nửa). */
    [data-testid="stSidebarUserContent"] {
        display: flex; flex-direction: column; min-height: 100vh;
    }
    .st-key-sidebar_footer { margin-top: auto; }

    /* Tiêu đề + dòng phụ đầu thanh bên, nút thu gọn/mở rộng (mũi tên tròn
    nhỏ, giống mẫu tham khảo) và nút "Log out" — tất cả theo tông tối. */
    .sidebar-title { color: #e8eaed; font-weight: 700; font-size: 1.05rem; white-space: nowrap; }
    .sidebar-subtitle { color: #6b7280; font-size: 0.78rem; white-space: nowrap; margin-bottom: 0.5rem; }
    .st-key-sidebar_toggle button {
        border-radius: 50% !important; border: 1px solid #2a2d35 !important;
        background: #1e2129 !important; width: 30px !important; height: 30px !important;
        padding: 0 !important; min-height: 30px !important;
    }
    .st-key-sidebar_toggle button span { color: #9aa0a6 !important; }
    .st-key-logout_btn button {
        border: 1px solid #2a2d35 !important; background: transparent !important;
        color: #9aa0a6 !important; justify-content: flex-start !important; gap: 0.6rem;
    }
    .st-key-logout_btn button:hover { background: #1e2129 !important; border-color: #3a3d45 !important; }

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


def _hex_to_rgba(hex_color, alpha=255):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return (r, g, b, alpha)


@st.cache_data(show_spinner=False)
def _sample_frame_from_upload(_file_bytes, sig, suffix):
    """Lấy 1 khung hình mẫu từ file upload (để làm nền xem trước trademark)
    — cache theo `sig` (tên+size, rẻ để so sánh) chứ KHÔNG hash toàn bộ nội
    dung file (`_file_bytes` bắt đầu bằng gạch dưới nên Streamlit bỏ qua
    khi tính cache key) — tránh phải hash lại vài MB dữ liệu mỗi lần trang
    tự load lại (mỗi khi kéo thanh trượt)."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="tm_preview_"))
    tmp_path = tmp_dir / f"sample{suffix}"
    tmp_path.write_bytes(_file_bytes)
    try:
        return core._grab_frame_bgr(tmp_path, 1.0)
    finally:
        tmp_path.unlink(missing_ok=True)


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


_LOGIN_CROC_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Titan+One&display=swap');
header[data-testid="stHeader"] { display: none; }
.block-container { padding-top: 0 !important; }
[data-testid="stAppViewContainer"], [data-testid="stMain"], body { background: #0d1b0f !important; }
[data-testid="stForm"] { border: none !important; padding: 0 !important; background: transparent !important; }
/* Ẩn nút "Vào" — chỉ giữ lại để Streamlit chấp nhận Enter là submit form
(bắt buộc phải có 1 nút submit trong form), không cho hiện ra màn hình. */
.st-key-login_btn { position: fixed !important; top: -200px; left: -200px; }
/* Ẩn dòng gợi ý "Press Enter to submit form" Streamlit tự thêm vào form. */
[data-testid="InputInstructions"] { display: none !important; }

.login-title {
    position: fixed; top: calc(50vh - 320px); left: 50%; transform: translateX(-50%);
    font-family: 'Titan One', cursive;
    color: #d9f2c4; font-size: 52px; letter-spacing: 0.03em;
    text-shadow: 3px 3px 0 #1f4a20, -1px -1px 0 #1f4a20, 1px -1px 0 #1f4a20, -1px 1px 0 #1f4a20;
    z-index: 6; text-align: center; width: 100%;
}
.croc-stage {
    position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
    width: 520px; height: 520px; z-index: 1; pointer-events: none;
}
.croc-head-top {
    position: absolute; top: 20px; left: 10px; width: 500px; height: 150px;
    background: linear-gradient(180deg, #5aa64a 0%, #3f8a3a 100%);
    border-radius: 250px 250px 20px 20px / 140px 140px 10px 10px;
    box-shadow: inset 0 -8px 18px rgba(0,0,0,0.15);
}
.croc-spot { position: absolute; background: #2f6b30; border-radius: 50%; opacity: 0.5; }
.croc-eye {
    position: absolute; top: 18px; width: 50px; height: 50px;
    background: #eede9a; border-radius: 50%; border: 4px solid #3f8a3a;
    display: flex; align-items: center; justify-content: center;
}
.croc-eye.left { left: 90px; }
.croc-eye.right { right: 90px; }
.croc-pupil { width: 18px; height: 18px; background: #1a1a1a; border-radius: 50%; }
.croc-nostril {
    position: absolute; top: 6px; width: 14px; height: 18px;
    background: #1f4a20; border-radius: 50%;
}
.croc-nostril.left { left: 235px; }
.croc-nostril.right { right: 235px; }

.croc-jaw-top {
    position: absolute; top: 170px; left: 10px; width: 500px; height: 40px;
    background: #4a9640; border-radius: 30px 30px 0 0;
}
.croc-teeth-top {
    position: absolute; top: 196px; left: 10px; width: 500px; height: 30px;
    background: #f5f0e0;
    clip-path: polygon(
      2% 0%, 10% 0%, 14% 100%, 18% 0%, 26% 0%, 30% 100%, 34% 0%,
      42% 0%, 46% 100%, 50% 0%, 58% 0%, 62% 100%, 66% 0%,
      74% 0%, 78% 100%, 82% 0%, 90% 0%, 94% 100%, 98% 0%
    );
}
.croc-mouth-inside {
    position: absolute; top: 200px; left: 40px; width: 440px; height: 180px;
    background: radial-gradient(ellipse at center, #8a2828 0%, #4a1010 100%);
    border-radius: 24px; box-shadow: inset 0 6px 20px rgba(0,0,0,0.5);
    transition: opacity 0.25s ease 0.3s;
}
.croc-stage.closing .croc-mouth-inside { opacity: 0; }

.croc-lower-jaw-group { position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 3; }
.croc-lower-jaw-group.closing { animation: crocCloseJaw 0.6s cubic-bezier(0.55,0,0.1,1) forwards; }
.croc-jaw-bottom {
    position: absolute; top: 365px; left: 10px; width: 500px; height: 140px;
    background: linear-gradient(180deg, #3f8a3a 0%, #2d6b2c 100%);
    border-radius: 0 0 200px 200px / 0 0 110px 110px;
}
.croc-teeth-bottom {
    position: absolute; top: 350px; left: 10px; width: 500px; height: 30px;
    background: #f5f0e0;
    clip-path: polygon(
      2% 100%, 10% 100%, 14% 0%, 18% 100%, 26% 100%, 30% 0%, 34% 100%,
      42% 100%, 46% 0%, 50% 100%, 58% 100%, 62% 0%, 66% 100%,
      74% 100%, 78% 0%, 82% 100%, 90% 100%, 94% 0%, 98% 100%
    );
}

@keyframes crocCloseJaw { from { transform: translateY(0); } to { transform: translateY(-158px); } }
@keyframes crocShake {
    10%, 90% { transform: translateX(-1px); }
    20%, 80% { transform: translateX(2px); }
    30%, 50%, 70% { transform: translateX(-5px); }
    40%, 60% { transform: translateX(5px); }
}

/* Định vị lại ô nhập mật khẩu (widget thật của Streamlit) để nằm ĐÚNG vào
khoang miệng cá sấu vẽ ở trên — xem _croc_stage_html(). */
.st-key-login_pwd {
    position: fixed !important; top: calc(50% + 20px) !important; left: 50%;
    transform: translateX(-50%); width: 280px !important; z-index: 6;
}
.st-key-login_pwd input {
    text-align: center; border-radius: 10px !important; border: 3px solid transparent !important;
    box-shadow: 0 3px 10px rgba(0,0,0,0.35);
}
</style>
"""


def _croc_stage_html(closing=False):
    stage_cls = "croc-stage closing" if closing else "croc-stage"
    lower_cls = "croc-lower-jaw-group closing" if closing else "croc-lower-jaw-group"
    return f"""
    <div class="{stage_cls}">
      <div class="croc-mouth-inside"></div>
      <div class="croc-jaw-top"></div>
      <div class="croc-teeth-top"></div>
      <div class="{lower_cls}">
        <div class="croc-jaw-bottom"></div>
        <div class="croc-teeth-bottom"></div>
      </div>
      <div class="croc-head-top">
        <div class="croc-spot" style="width:30px;height:30px;top:60px;left:100px;"></div>
        <div class="croc-spot" style="width:24px;height:24px;top:90px;left:390px;"></div>
        <div class="croc-nostril left"></div>
        <div class="croc-nostril right"></div>
        <div class="croc-eye left"><div class="croc-pupil"></div></div>
        <div class="croc-eye right"><div class="croc-pupil"></div></div>
      </div>
    </div>
    """


def require_login():
    """Chặn truy cập nếu chưa nhập đúng mật khẩu chung của team — màn hình
    cá sấu há miệng, gõ mật khẩu vào đúng vòm miệng nó. (Nút đăng xuất nằm
    ở thanh bên trái, xem render_sidebar_nav().)"""
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

    st.markdown(_LOGIN_CROC_CSS, unsafe_allow_html=True)
    st.markdown('<div class="login-title">UA Agent</div>', unsafe_allow_html=True)

    # Bọc trong 1 placeholder để có thể XOÁ SẠCH (ô nhập + nút) ngay khi
    # đúng mật khẩu, thay bằng cảnh "ngậm miệng" — không có cách nào phát
    # animation chuyển cảnh (transition) qua 2 lần rerun khác nhau trong
    # Streamlit (mỗi lần rerun là 1 lần dựng lại DOM mới hoàn toàn), nên
    # thay vào đó dùng animation TỰ CHẠY (@keyframes ... forwards) ngay khi
    # phần tử "đang đóng" vừa được chèn vào trang — luôn chạy được bất kể
    # DOM cũ trông ra sao trước đó.
    stage_ph = st.empty()
    with stage_ph.container():
        st.markdown(_croc_stage_html(), unsafe_allow_html=True)
        # Dùng st.form thay vì text_input + button rời — Streamlit chỉ
        # "chốt" giá trị ô nhập khi bấm Enter/rời khỏi ô, nếu tách rời 2
        # widget thì bấm nút ngay sau khi gõ có thể bị lỡ mất giá trị mới
        # nhất (đã kiểm chứng thực tế bằng cách giả lập thao tác gõ+bấm).
        # st.form gộp cả 2 lại, chốt giá trị đúng lúc bấm nút HOẶC bấm
        # Enter trong ô — không còn rủi ro lỡ giá trị.
        with st.form("login_form", clear_on_submit=False, border=False):
            pwd = st.text_input(
                "Mật khẩu", type="password", placeholder="Nhập mật khẩu...",
                key="login_pwd", label_visibility="collapsed",
            )
            clicked = st.form_submit_button("Vào", key="login_btn")

    if clicked:
        if pwd == correct_password:
            stage_ph.empty()
            st.markdown(_croc_stage_html(closing=True), unsafe_allow_html=True)
            time.sleep(0.75)  # cho animation ngam mieng kip chay xong tren trinh duyet
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.markdown(
                "<style>.st-key-login_pwd input {"
                "border-color: #e53935 !important; animation: crocShake 0.45s; }</style>",
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div style="position:fixed; top:calc(50% + 75px); left:50%; '
                'transform:translateX(-50%); color:#ffb4b4; font-size:14px; z-index:6;">'
                "Sai mật khẩu — cá sấu chưa cho vào 🐊</div>",
                unsafe_allow_html=True,
            )
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


def render_results_grid(paths, download_key_prefix, cols_per_row=4):
    """Hiển thị các video kết quả dạng lưới (thay vì xếp chồng dọc) — tận
    dụng bố cục rộng, dễ xem/tải nhiều video cùng lúc hơn. Có nút tải hết
    1 lần (nén thành .zip) bên cạnh nút tải từng video riêng."""
    existing = [p for p in paths if p.exists()]
    if not existing:
        return

    if len(existing) > 1:
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_STORED) as zf:
            for out_path in existing:
                zf.write(out_path, arcname=out_path.name)
        st.download_button(
            f"⬇️ Download All ({len(existing)} video, .zip)",
            data=zip_buf.getvalue(),
            file_name="ket_qua.zip",
            mime="application/zip",
            key=f"{download_key_prefix}_zip_all",
            type="primary",
        )

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
    st.caption("Tách cảnh, trộn ngẫu nhiên, ghép thành video mới.")

    for key, default in [
        ("outputs", []), ("scene_warning", None), ("variant_warning", None),
        ("analysis", None), ("variants_value", 5),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    uploaded_files = st.file_uploader(
        "Kéo-thả video vào đây",
        type=["mp4", "mov", "mkv", "avi", "webm"],
        accept_multiple_files=True,
        key="remix_uploader",
    )
    has_files = bool(uploaded_files)

    has_outro = st.checkbox(
        "Mỗi video có outro/logo cố định ở cuối",
        value=False,
        help="Tách riêng đoạn cuối ra khỏi rổ trộn, chỉ gắn lại 1 lần vào mỗi video kết quả.",
    )

    merge_similar = st.checkbox(
        "Gộp các đoạn giống nhau (giảm tách vụn)",
        value=True,
        help="Gộp lại nếu 2 đoạn liền kề nhìn giống nhau — không đảm bảo đúng 100%.",
    )

    with st.expander("Tuỳ chọn nâng cao"):
        detector = st.selectbox(
            "Cách nhận diện đoạn cắt",
            ["content", "adaptive"],
            help="'content' phù hợp đa số trường hợp, tách sai nhiều thì thử 'adaptive'.",
        )
        threshold = st.number_input(
            "Độ nhạy cắt cảnh (nhỏ hơn = nhạy hơn)",
            min_value=1.0, max_value=100.0, value=27.0, step=1.0,
        )
        min_scene_len = st.number_input(
            "Độ dài scene tối thiểu (giây)", min_value=0.0, value=0.5, step=0.1,
        )
        merge_threshold = st.number_input(
            "Ngưỡng gộp đoạn giống nhau (0-64, thấp = khắt khe hơn)",
            min_value=0, max_value=64, value=8, step=1, disabled=not merge_similar,
        )
        min_clip_len = st.number_input(
            "Bỏ qua đoạn ngắn hơn (giây)", min_value=0.0, value=0.0, step=0.1
        )
        max_clips = st.number_input(
            "Giới hạn số đoạn mỗi video mới (0 = không giới hạn)", min_value=0, value=0, step=1
        )
        use_seed = st.checkbox("Cố định kết quả ngẫu nhiên")
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
    st.caption("Xem trước số đoạn tách được.")

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
                    notes.append(f"⚠️ trung bình ~{avg_len:.1f}s/đoạn — có thể bị tách vụn")
            note_text = ("  " + " | ".join(notes)) if notes else ""
            st.write(f"- **{a['path'].name}**: {n_content} đoạn nội dung, {dur:.1f}s{outro_note}{note_text}")

        if has_outro and n_with_outro == 0:
            st.warning("Không video nào tách được ≥2 đoạn để tách outro — dùng cả video làm nội dung.")

        st.success(f"Tổng **{total_clips} đoạn** từ {len(analyzed)} video, ~{total_duration:.1f}s gốc.")
        suggested = max(1, min(total_clips, 20))
        st.info(f"Gợi ý: thử khoảng **{suggested} biến thể** (ước lượng theo số đoạn tách được).")
    elif has_files:
        st.caption("Chưa phân tích — bấm nút phía trên.")

    st.divider()
    st.subheader("Bước 2 — Tạo biến thể")

    duration_range = st.slider(
        "Thời lượng mỗi video mới (giây)",
        min_value=5, max_value=120, value=(30, 45),
        help="Nếu 1 đoạn dài hơn mức tối đa, vẫn giữ nguyên (không cắt bớt).",
    )
    target_min, target_max = duration_range

    variants = st.number_input(
        "Số video muốn tạo ra", min_value=1, max_value=200, step=1, key="variants_value"
    )

    output_name = st.text_input(
        "Đặt tên file xuất ra (tuỳ chọn)",
        placeholder="vd: hieund.apero → hieund.apero.1, hieund.apero.2, ...",
        key="remix_output_name",
        help="Để trống thì dùng tên tự động.",
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
                        warnings.append(f"'{name}' chỉ 1 đoạn — thử giảm 'Độ nhạy cắt cảnh'.")
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
                    raise RuntimeError("Không tách được đoạn nào — thử giảm 'Bỏ qua đoạn ngắn hơn' hoặc 'Độ nhạy cắt cảnh'.")

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
    st.caption("Cắt outro đối thủ ở cuối video, gắn outro của bạn vào thay thế.")

    for key, default in [("outro_outputs", []), ("outro_run_error", None), ("outro_uploader_version", 0)]:
        if key not in st.session_state:
            st.session_state[key] = default

    with st.expander("⚙️ Quản lý outro của tôi"):
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
                st.caption("Chưa có outro nào — thêm ở ô bên dưới.")

            new_files = st.file_uploader(
                f"Thêm outro cho {category}",
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
        "Kéo-thả video đối thủ vào đây",
        type=["mp4", "mov", "mkv", "avi", "webm"],
        accept_multiple_files=True,
        # Key đổi theo "outro_uploader_version" — tăng số này lên (nút xoá
        # bên dưới) là cách duy nhất để RESET hẳn ô tải lên (Streamlit không
        # có cách "xoá file đã chọn" nào khác ngoài đổi key sang 1 widget
        # coi như hoàn toàn mới).
        key=f"outro_uploader_{st.session_state.outro_uploader_version}",
    )
    has_files = bool(uploaded_files)

    if has_files or st.session_state.outro_outputs:
        if st.button("🗑️ Xoá hết video & làm mẻ mới", key="outro_clear_batch"):
            st.session_state.outro_uploader_version += 1
            st.session_state.outro_outputs = []
            st.session_state.outro_run_error = None
            st.rerun()

    outro_category = st.selectbox("Loại outro của tôi", list(OUTRO_CATEGORY_SLUGS.keys()),
                                   key="outro_category_choice")
    available_outros = _list_outros(outro_category)

    chosen_outro_path = None
    if not available_outros:
        st.caption(f"Chưa có outro cho '{outro_category}' — không chọn cũng được, vẫn cắt outro đối thủ bình thường.")
    else:
        st.write("Chọn outro muốn dùng:")
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
            st.caption("Chưa chọn outro — vẫn cắt outro đối thủ bình thường, chỉ không gắn gì vào cuối.")
        else:
            chosen_outro_path = picked[0]

    with st.expander("Tuỳ chọn nâng cao"):
        match_threshold = st.number_input(
            "Ngưỡng nhận outro chung (thấp = khắt khe hơn)",
            min_value=1, max_value=100, value=outro_core.DEFAULT_MATCH_THRESHOLD, step=1,
        )
        max_workers = st.number_input(
            "Số video xử lý song song (chỉ tăng nếu chạy server riêng — máy chủ "
            "miễn phí dễ crash nếu để cao)",
            min_value=1, max_value=16, value=1, step=1, key="outro_max_workers",
        )
        safety_margin = st.number_input(
            "Cắt dư thêm vào nội dung (giây) — chắc chắn không sót outro",
            min_value=0.0, max_value=2.0, value=0.15, step=0.05, key="outro_safety_margin",
            help="Tăng lên nếu vẫn thấy sót outro ở cuối video.",
        )
        strip_audio = st.checkbox("Bỏ âm thanh trong video kết quả", key="outro_strip_audio")

    with st.expander("🏷️ Thêm trademark bay (tuỳ chọn)"):
        add_trademark = st.checkbox("Gắn trademark vào video kết quả", key="outro_add_trademark")
        trademark_kind = trademark_text = None
        trademark_logo_file = None
        trademark_opacity = trademark_size = trademark_speed = trademark_range = None
        trademark_font_style = "Đậm"
        trademark_text_color = "#FFFFFF"
        trademark_stroke_color = "#000000"
        trademark_path_style = trademark_core.PATH_STYLES[0]
        if add_trademark:
            settings_col, preview_col = st.columns([3, 2])

            with settings_col:
                trademark_kind = st.radio(
                    "Loại trademark", ["Chữ", "Logo/hình ảnh"], key="outro_trademark_kind", horizontal=True,
                )
                if trademark_kind == "Chữ":
                    trademark_text = st.text_input("Nội dung chữ", key="outro_trademark_text")
                    tm_font_col, tm_color1_col, tm_color2_col = st.columns(3)
                    trademark_font_style = tm_font_col.selectbox(
                        "Kiểu chữ", trademark_core.FONT_STYLES, key="outro_trademark_font_style",
                    )
                    trademark_text_color = tm_color1_col.color_picker(
                        "Màu chữ", "#FFFFFF", key="outro_trademark_text_color",
                    )
                    trademark_stroke_color = tm_color2_col.color_picker(
                        "Màu viền", "#000000", key="outro_trademark_stroke_color",
                    )
                else:
                    trademark_logo_file = st.file_uploader(
                        "Ảnh logo (khuyến khích PNG nền trong suốt)", type=["png", "jpg", "jpeg"],
                        key="outro_trademark_logo",
                    )
                trademark_opacity = st.slider("Độ mờ (%)", 10, 100, 70, key="outro_trademark_opacity")
                trademark_size = st.slider(
                    "Độ lớn (% chiều rộng video)", 5, 40, 15, key="outro_trademark_size",
                )
                trademark_speed = st.slider(
                    "Tốc độ bay", 30, 400, 150, key="outro_trademark_speed",
                )
                trademark_path_style = st.selectbox(
                    "Kiểu bay", trademark_core.PATH_STYLES, key="outro_trademark_path_style",
                    help="Zigzag: nảy khắp khung hình. Vòng tròn: bay theo elip, tốc độ đổi nhanh/chậm.",
                )
                trademark_range = st.slider(
                    "Phạm vi bay (% vùng khả dụng)", 20, 100, 100, key="outro_trademark_range",
                    help="100% = bay sát hết phạm vi, nhỏ hơn = thu hẹp lại gần giữa.",
                )
                st.caption("⚠️ Đường bay đi khắp khung hình, có thể đi qua chủ thể chính.")

            with preview_col:
                st.caption("👁️ Xem trước nhanh:")
                preview_overlay = None
                if trademark_kind == "Chữ" and trademark_text and trademark_text.strip():
                    preview_overlay = trademark_core.render_text_overlay(
                        trademark_text.strip(), font_style=trademark_font_style,
                        text_color=_hex_to_rgba(trademark_text_color),
                        stroke_color=_hex_to_rgba(trademark_stroke_color),
                    )
                elif trademark_kind == "Logo/hình ảnh" and trademark_logo_file is not None:
                    tmp_logo_dir = Path(tempfile.mkdtemp(prefix="tm_logo_preview_"))
                    tmp_logo = tmp_logo_dir / f"logo{Path(trademark_logo_file.name).suffix}"
                    tmp_logo.write_bytes(trademark_logo_file.getvalue())
                    preview_overlay = trademark_core.load_logo_overlay(tmp_logo)

                if preview_overlay is None:
                    st.info("Nhập chữ hoặc tải logo để xem trước.")
                elif not has_files:
                    st.info("Tải video lên để xem trước.")
                else:
                    first_file = uploaded_files[0]
                    sample_frame = _sample_frame_from_upload(
                        first_file.getvalue(), (first_file.name, first_file.size),
                        Path(first_file.name).suffix,
                    )
                    if sample_frame is None:
                        st.warning("Không đọc được khung hình mẫu từ video đầu tiên.")
                    else:
                        preview_bytes = trademark_core.generate_preview_animation(
                            sample_frame, preview_overlay,
                            opacity=trademark_opacity / 100, size_percent=trademark_size,
                            speed_px_per_sec=trademark_speed, path_style=trademark_path_style,
                            range_percent=trademark_range,
                        )
                        # Dùng thẻ <img> nhúng trực tiếp (base64) thay vì
                        # st.image() — st.image() có thể chỉ hiện khung hình
                        # ĐẦU TIÊN của ảnh động (không chạy hoạt ảnh), trong
                        # khi nhúng qua HTML thì trình duyệt luôn tự chạy
                        # hoạt ảnh WEBP/GIF bình thường (giống cách hiện GIF
                        # ở màn hình "sắp ra mắt" đã dùng và chạy tốt).
                        preview_b64 = base64.b64encode(preview_bytes).decode()
                        st.markdown(
                            f'<img src="data:image/webp;base64,{preview_b64}" '
                            'style="width:100%; border-radius:8px;">',
                            unsafe_allow_html=True,
                        )

    output_name = st.text_input(
        "Đặt tên file xuất ra (tuỳ chọn)",
        placeholder="vd: hieund.apero → hieund.apero.1, hieund.apero.2, ...",
        key="outro_output_name",
        help="Để trống thì dùng tên tự động.",
    )

    run_clicked = st.button("Xử lý", type="primary", disabled=not has_files)

    if run_clicked and has_files:
        st.session_state.outro_outputs = []
        st.session_state.outro_run_error = None
        workdir, input_paths = save_uploads(uploaded_files, prefix="outro_swap_")

        try:
            with st.status("Đang xử lý video...", expanded=True) as status:
                made = []

                def on_source(done, total, name, result):
                    if result["reason"] == "matched":
                        status.write(f"[{done}/{total}] ✓ {name}: đã cắt {result['outro_cut_seconds']:.1f}s outro")
                    else:
                        tail = (
                            "video này có thể có 2 outro nối tiếp — kiểm tra lại."
                            if chosen_outro_path else "giữ nguyên, không gắn gì thêm."
                        )
                        status.write(
                            f"[{done}/{total}] ⚠️ {name}: không tìm được video nào cùng "
                            "outro trong mẻ này, không dám cắt liều — " + tail
                        )
                    made.append(result)

                outro_core.process_outro_swap(
                    input_paths, chosen_outro_path, workdir, strip_audio,
                    tail_match_threshold=match_threshold, on_source=on_source,
                    max_workers=int(max_workers), safety_margin_seconds=safety_margin,
                )

                trademark_ready = add_trademark and (
                    (trademark_kind == "Chữ" and trademark_text and trademark_text.strip())
                    or (trademark_kind == "Logo/hình ảnh" and trademark_logo_file is not None)
                )
                if add_trademark and not trademark_ready:
                    status.write("⚠️ Chưa nhập chữ/chưa chọn logo trademark — bỏ qua bước gắn trademark.")
                elif trademark_ready:
                    status.write("Đang gắn trademark bay ziczac lên từng video...")
                    if trademark_kind == "Chữ":
                        overlay_rgba = trademark_core.render_text_overlay(
                            trademark_text.strip(), font_style=trademark_font_style,
                            text_color=_hex_to_rgba(trademark_text_color),
                            stroke_color=_hex_to_rgba(trademark_stroke_color),
                        )
                    else:
                        logo_path = workdir / f"trademark_logo_{uuid.uuid4().hex[:8]}{Path(trademark_logo_file.name).suffix}"
                        logo_path.write_bytes(trademark_logo_file.getvalue())
                        overlay_rgba = trademark_core.load_logo_overlay(logo_path)

                    # Không cho trademark bay đè lên đoạn outro của bạn ở
                    # cuối video kết quả (nếu có chọn outro) — chỉ gắn
                    # trong phần nội dung phía trước. own_outro_dur giống
                    # nhau cho mọi video (cùng 1 file outro được chọn), nên
                    # chỉ cần tính 1 lần. Bằng 0 nếu không chọn outro nào
                    # (không có đoạn nào cần tránh).
                    own_outro_dur = core.ffprobe_info(chosen_outro_path)["duration"] if chosen_outro_path else 0.0
                    for r in made:
                        final_dur = core.ffprobe_info(r["path"])["duration"]
                        skip_after = max(final_dur - own_outro_dur, 0.0)
                        tm_path = r["path"].parent / f"{r['path'].stem}_tm{r['path'].suffix}"
                        trademark_core.apply_trademark(
                            r["path"], overlay_rgba, tm_path, workdir,
                            opacity=trademark_opacity / 100, size_percent=trademark_size,
                            speed_px_per_sec=trademark_speed, path_style=trademark_path_style,
                            skip_after_seconds=skip_after, range_percent=trademark_range,
                        )
                        r["path"].unlink(missing_ok=True)
                        r["path"] = tm_path

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

    if logo_cover_core is None:
        st.error(
            f"Module `logo_cover_core` bị lỗi khi import, tool này tạm thời "
            f"không dùng được trên máy chủ hiện tại (không ảnh hưởng 2 tool "
            f"kia). Chi tiết lỗi: `{LOGO_COVER_IMPORT_ERROR}`"
        )
        return
    if not logo_cover_core.TRACKER_FACTORIES:
        st.error(
            "Bản OpenCV trên máy chủ này không có sẵn thuật toán theo dõi "
            "vật thể (CSRT/KCF) — tool này tạm thời không dùng được ở đây."
        )
        return

    st.caption("Khoanh vùng logo đối thủ ở 1 khung hình — tool tự bám theo và vẽ đè logo của bạn lên.")
    st.info("⚠️ Chỉ bám theo trong 1 cảnh liên tục — cắt cảnh khác cần khoanh vùng lại riêng.")

    for key, default in [("cover_result", None), ("cover_error", None)]:
        if key not in st.session_state:
            st.session_state[key] = default

    uploaded = st.file_uploader(
        "Video đối thủ (1 video)", type=["mp4", "mov", "mkv", "avi", "webm"],
        accept_multiple_files=False, key="cover_uploader",
    )
    logo_file = st.file_uploader(
        "Logo/trademark của bạn (nên dùng PNG nền trong suốt)",
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

    st.write("Kéo khung đỏ cho vừa khít logo cần che:")
    box = st_cropper(
        pil_img, return_type="box", box_color="#FF0000",
        key=f"cropper_{sig[0]}_{sig[1]}",
    )
    bbox = (int(box["left"]), int(box["top"]), int(box["width"]), int(box["height"]))

    with st.expander("Tuỳ chọn nâng cao"):
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
            "Độ phóng to logo che", min_value=1.0, max_value=2.0, value=1.15, step=0.05, key="cover_scale",
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
# chỉ cần thêm 1 dòng vào đây (icon Material Symbols + nhãn + hàm render),
# không cần sửa gì chỗ khác. Thứ tự trong list = thứ tự hiện trên menu.
NAV_ITEMS = [
    {"key": "outro", "label": "Outro Solution", "icon": "content_cut", "fn": render_outro_swap},
    {"key": "remix", "label": "Video Remixer", "icon": "shuffle", "fn": render_video_remixer},
    {"key": "logocover", "label": "Logo Cover", "icon": "shield", "fn": render_logo_cover},
]

if "nav_page" not in st.session_state:
    st.session_state.nav_page = NAV_ITEMS[0]["key"]
if "sidebar_collapsed" not in st.session_state:
    st.session_state.sidebar_collapsed = False


def _sidebar_state_css(collapsed, active_key):
    """CSS ĐỘNG theo trạng thái hiện tại — tách riêng khỏi CSS tĩnh ở đầu
    file vì phụ thuộc session_state (thu gọn/mở rộng, mục đang chọn), phải
    tính lại mỗi lần vẽ trang. Thu gọn: chỉ ép hẹp bề rộng thanh bên +
    ẩn phần chữ (nhãn, tiêu đề, dòng phụ) — vẫn giữ icon để bấm được bình
    thường, không tắt hẳn."""
    width = "76px" if collapsed else "230px"
    label_display = "none" if collapsed else "inline"
    text_display = "none" if collapsed else "block"
    rules = [
        f'section[data-testid="stSidebar"] {{ width: {width} !important; min-width: {width} !important; }}',
        f'[class*="st-key-nav_"] button p {{ display: {label_display}; }}',
        f'.sidebar-title, .sidebar-subtitle, .st-key-logout_btn button p {{ display: {text_display}; }}',
    ]
    for item in NAV_ITEMS:
        cls = f'.st-key-nav_{item["key"]} button'
        if item["key"] == active_key:
            rules.append(
                f'{cls} {{ background: rgba(245,166,35,0.16) !important; color: #f5a623 !important; }} '
                f'{cls} span[data-testid="stIconMaterial"] {{ color: #f5a623 !important; }}'
            )
        else:
            rules.append(f'{cls} span[data-testid="stIconMaterial"] {{ color: #9aa0a6; }}')
    return "<style>" + "\n".join(rules) + "</style>"


with st.sidebar:
    st.markdown(_sidebar_state_css(st.session_state.sidebar_collapsed, st.session_state.nav_page), unsafe_allow_html=True)

    top_left, top_right = st.columns([5, 1])
    with top_left:
        st.markdown('<div class="sidebar-title">UA Solutions</div>', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-subtitle">Apero internal tools</div>', unsafe_allow_html=True)
    with top_right:
        if st.button("", icon=":material/chevron_right:", key="sidebar_toggle"):
            st.session_state.sidebar_collapsed = not st.session_state.sidebar_collapsed
            st.rerun()

    for item in NAV_ITEMS:
        if st.button(
            item["label"], icon=f":material/{item['icon']}:", key=f"nav_{item['key']}",
            use_container_width=True,
        ):
            st.session_state.nav_page = item["key"]
            st.rerun()

    with st.container(key="sidebar_footer"):
        st.divider()
        st.button(
            "Log out", icon=":material/logout:", key="logout_btn", use_container_width=True,
            on_click=lambda: st.session_state.pop("authed", None),
        )

active_item = next(x for x in NAV_ITEMS if x["key"] == st.session_state.nav_page)
active_item["fn"]()
