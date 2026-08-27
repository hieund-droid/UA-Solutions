#!/usr/bin/env python3
"""
drive_sync.py — Đồng bộ thư mục outros/, logos/, known_outros/ với 1 thư mục
Google Drive dùng chung, để KHÔNG MẤT dữ liệu khi app khởi động lại.

Vì sao cần file này (bối cảnh thật, 2026-08-27): app chạy trên Streamlit
Community Cloud — ổ đĩa của container KHÔNG bền vững, bị dựng lại mới hoàn
toàn mỗi khi có bản deploy mới hoặc app "ngủ" rồi "thức dậy" sau 1 thời gian
không ai dùng. Outro/logo người dùng tự tải lên (outros/users/<id>/,
logos/users/<id>/) và thư viện outro tự nhận diện (known_outros/) đều CỐ
TÌNH không đưa lên GitHub (đúng thiết kế — đây là dữ liệu, không phải code),
nên mỗi lần ổ đĩa bị dựng lại là mất sạch — phản hồi thật từ người dùng:
"đăng nhập lại library bị mất outro".

Cách làm: coi ĐĨA CỤC BỘ là bản NHÁP (cache) làm việc trong phiên hiện tại,
Drive mới là nơi lưu THẬT SỰ bền vững:
  - Lúc app khởi động (1 lần/container, xem sync_down_all + st.cache_resource
    ở app.py): tải hết những gì đang có trên Drive về đúng cấu trúc thư mục
    local mà code cũ đã quen dùng (_outro_dir_for/_list_outros/... không cần
    sửa gì, vẫn đọc thẳng từ đĩa như trước).
  - Mỗi khi có người thêm/đổi tên/xoá outro hoặc logo qua giao diện: gọi
    thêm 1 dòng push_file()/rename_remote()/delete_remote() tương ứng NGAY
    sau thao tác trên đĩa, để đẩy thay đổi đó lên Drive ngay lập tức.

Yêu cầu Secrets (.streamlit/secrets.toml, xem README hướng dẫn setup):
    [gdrive]
    folder_id = "..."          # ID thư mục Drive gốc (đã share Editor cho
                                # service account bên dưới)
    [gdrive.service_account]
    ...                        # dán nguyên nội dung file JSON key của
                                # service account vào đây (dạng TOML)

Nếu CHƯA cấu hình Secrets (`[gdrive]` không có) — mọi hàm ở đây tự động
NO-OP (không lỗi, không cảnh báo ồn ào), app vẫn chạy bình thường như trước
khi có Drive, chỉ là không còn được bảo vệ khỏi mất dữ liệu — để môi trường
dev cục bộ (không cần Drive) hoặc lúc chưa kịp setup vẫn dùng được ngay.

Mọi lỗi kết nối Drive (mạng, quota, quyền truy cập...) đều bị NUỐT (log ra
console qua warnings, không ném lỗi) — đồng bộ THẤT BẠI không được phép làm
HỎNG thao tác chính của người dùng (tải outro lên vẫn phải thành công trên
đĩa cục bộ ngay cả khi Drive đang lỗi tạm thời), giống triết lý "an toàn
hơn" đã dùng xuyên suốt outro_core.py.
"""

import io
import mimetypes
import warnings
from pathlib import Path

try:
    import streamlit as st
except ImportError:  # cho phép test module này ngoài Streamlit neu can
    st = None

_ROOT_LOCAL = Path(__file__).resolve().parent  # goc de tinh duong dan tuong doi (vd "outros/users/duyen/photo/foo.mp4")

_service = None  # cache Drive API client — build 1 lần/tiến trình
_service_tried = False
_folder_id_cache = {}  # (parent_id, name) -> id, tranh goi lai API tim/tao thu muc nhieu lan trong 1 lan chay


def _configured():
    if st is None:
        return False
    try:
        return "gdrive" in st.secrets and "folder_id" in st.secrets["gdrive"]
    except Exception:
        return False


def _get_service():
    """Trả về Drive API client đã xác thực, cache lại (build 1 lần/tiến
    trình) — trả về None nếu chưa cấu hình Secrets hoặc lỗi xác thực (đã
    log cảnh báo), KHÔNG ném lỗi ra ngoài."""
    global _service, _service_tried
    if _service is not None:
        return _service
    if _service_tried:
        return None
    _service_tried = True
    if not _configured():
        return None
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        info = dict(st.secrets["gdrive"]["service_account"])
        creds = Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/drive"],
        )
        _service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return _service
    except Exception as e:
        warnings.warn(f"drive_sync: không xác thực được Google Drive ({e}) — bỏ qua đồng bộ.")
        return None


def _root_folder_id():
    if not _configured():
        return None
    return st.secrets["gdrive"]["folder_id"]


# QUAN TRỌNG: thư mục gốc BẮT BUỘC phải nằm trong 1 "Shared Drive" (Ổ đĩa
# dùng chung) — service account KHÔNG có dung lượng lưu trữ riêng trong "My
# Drive" thường (giới hạn của Google từ ~2021, đã kiểm chứng thực tế: tạo
# thư mục con thành công nhưng upload NỘI DUNG file báo lỗi 403
# "storageQuotaExceeded"), chỉ hoạt động được khi nội dung tính vào dung
# lượng của TỔ CHỨC qua Shared Drive. Vì vậy MỌI lệnh gọi files().list/get/
# create/update/get_media bên dưới đều phải kèm supportsAllDrives=True (và
# list còn cần thêm includeItemsFromAllDrives=True) — thiếu 1 trong 2 cờ
# này thì Drive API coi như "không thấy" nội dung nằm trong Shared Drive.
_DRIVE_KW = {"supportsAllDrives": True}
_LIST_KW = {**_DRIVE_KW, "includeItemsFromAllDrives": True}


def _ensure_subfolder(service, parent_id, name):
    """Tìm thư mục con tên `name` trong `parent_id`, tạo mới nếu chưa có —
    cache lại theo (parent_id, name) để không phải gọi API tìm/tạo lặp lại
    nhiều lần trong cùng 1 lượt chạy (đồng bộ 1 mẻ nhiều file thường lặp lại
    đúng vài thư mục cha giống nhau)."""
    key = (parent_id, name)
    if key in _folder_id_cache:
        return _folder_id_cache[key]
    q = (
        f"'{parent_id}' in parents and name = '{name}' and "
        "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    res = service.files().list(q=q, fields="files(id)", pageSize=1, **_LIST_KW).execute()
    files = res.get("files", [])
    if files:
        folder_id = files[0]["id"]
    else:
        meta = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
        folder = service.files().create(body=meta, fields="id", **_DRIVE_KW).execute()
        folder_id = folder["id"]
    _folder_id_cache[key] = folder_id
    return folder_id


def _resolve_folder(service, relative_dir_parts):
    """Đi từ thư mục gốc (folder_id trong Secrets), tạo/tìm lần lượt từng
    cấp thư mục con theo `relative_dir_parts` (vd ["outros","users","duyen",
    "photo"]) — trả về ID thư mục cuối cùng."""
    folder_id = _root_folder_id()
    for part in relative_dir_parts:
        folder_id = _ensure_subfolder(service, folder_id, part)
    return folder_id


def _find_file_in_folder(service, folder_id, name):
    q = f"'{folder_id}' in parents and name = '{name}' and trashed = false"
    res = service.files().list(q=q, fields="files(id)", pageSize=1, **_LIST_KW).execute()
    files = res.get("files", [])
    return files[0]["id"] if files else None


def _relative_path(local_path):
    """Quy đổi `local_path` (tuyệt đối HOẶC tương đối — .resolve() tự chuẩn
    hoá cả 2 kiểu về tuyệt đối trước khi so) về đường dẫn TƯƠNG ĐỐI so với
    gốc app — trả về None (kèm CẢNH BÁO, không im lặng) nếu path nằm ngoài
    hẳn phạm vi app, vì trường hợp này gần như luôn là dấu hiệu lỗi thật
    (gọi nhầm hàm với đường dẫn sai) chứ hiếm khi là chủ đích — im lặng bỏ
    qua từng khiến 1 lỗi thật (đường dẫn tương đối không tự quy đổi đúng)
    không hiện ra cảnh báo nào, rất khó phát hiện lúc gỡ lỗi."""
    try:
        return Path(local_path).resolve().relative_to(_ROOT_LOCAL)
    except ValueError:
        warnings.warn(f"drive_sync: đường dẫn '{local_path}' nằm ngoài phạm vi app ({_ROOT_LOCAL}) — bỏ qua đồng bộ.")
        return None


def push_file(local_path):
    """Đẩy 1 file cục bộ lên đúng vị trí tương ứng trên Drive (tạo mới nếu
    chưa có, GHI ĐÈ nội dung nếu đã có sẵn cùng tên) — dùng ngay sau mỗi lần
    ghi file mới vào outros/logos/known_outros trên đĩa. Không làm gì (trả
    về lặng lẽ) nếu chưa cấu hình Drive hoặc lỗi kết nối."""
    service = _get_service()
    if service is None:
        return
    local_path = Path(local_path)
    rel = _relative_path(local_path)
    if rel is None:
        return
    try:
        from googleapiclient.http import MediaFileUpload

        folder_id = _resolve_folder(service, rel.parts[:-1])
        name = rel.parts[-1]
        mime, _ = mimetypes.guess_type(name)
        media = MediaFileUpload(str(local_path), mimetype=mime or "application/octet-stream", resumable=False)
        existing_id = _find_file_in_folder(service, folder_id, name)
        if existing_id:
            service.files().update(fileId=existing_id, media_body=media, **_DRIVE_KW).execute()
        else:
            meta = {"name": name, "parents": [folder_id]}
            service.files().create(body=meta, media_body=media, fields="id", **_DRIVE_KW).execute()
    except Exception as e:
        warnings.warn(f"drive_sync: đẩy file '{local_path.name}' lên Drive thất bại ({e}) — vẫn còn trên đĩa cục bộ phiên này.")


def rename_remote(old_local_path, new_name):
    """Đổi tên file tương ứng trên Drive — CHỈ đổi metadata "name" (không
    tải lại nội dung), rẻ hơn nhiều so với xoá+đẩy lại. `old_local_path`:
    đường dẫn CŨ trên đĩa (trước khi rename cục bộ) để xác định đúng file
    trên Drive cần đổi tên."""
    service = _get_service()
    if service is None:
        return
    old_local_path = Path(old_local_path)
    rel = _relative_path(old_local_path)
    if rel is None:
        return
    try:
        folder_id = _resolve_folder(service, rel.parts[:-1])
        existing_id = _find_file_in_folder(service, folder_id, rel.parts[-1])
        if existing_id:
            service.files().update(fileId=existing_id, body={"name": new_name}, **_DRIVE_KW).execute()
    except Exception as e:
        warnings.warn(f"drive_sync: đổi tên file trên Drive thất bại ({e}).")


def delete_remote(local_path):
    """Xoá (đưa vào thùng rác Drive) file tương ứng — dùng ngay sau mỗi lần
    xoá file cục bộ."""
    service = _get_service()
    if service is None:
        return
    local_path = Path(local_path)
    rel = _relative_path(local_path)
    if rel is None:
        return
    try:
        folder_id = _resolve_folder(service, rel.parts[:-1])
        existing_id = _find_file_in_folder(service, folder_id, rel.parts[-1])
        if existing_id:
            service.files().update(fileId=existing_id, body={"trashed": True}, **_DRIVE_KW).execute()
    except Exception as e:
        warnings.warn(f"drive_sync: xoá file trên Drive thất bại ({e}).")


def sync_down_all(root_names=("outros", "logos", "known_outros")):
    """Tải TOÀN BỘ nội dung đang có trên Drive về đúng cấu trúc thư mục cục
    bộ tương ứng — gọi 1 LẦN lúc app khởi động (xem app.py, bọc trong
    st.cache_resource để không lặp lại mỗi lần trang tự tải lại). Chỉ tải
    file nào CHƯA có sẵn cục bộ (so theo tên) — container mới khởi động thì
    thư mục cục bộ đang trống nên tải hết, không cần so sánh gì phức tạp
    hơn (không có khái niệm "sửa file outro có sẵn", chỉ có thêm mới/xoá/
    đổi tên qua giao diện, các thao tác đó đã tự đồng bộ ngay lúc xảy ra)."""
    service = _get_service()
    if service is None:
        return
    try:
        for name in root_names:
            local_root = _ROOT_LOCAL / name
            local_root.mkdir(exist_ok=True)
            folder_id = _resolve_folder(service, (name,))
            _sync_down_folder(service, folder_id, local_root)
    except Exception as e:
        warnings.warn(f"drive_sync: tải dữ liệu từ Drive lúc khởi động thất bại ({e}) — bắt đầu với thư viện rỗng phiên này.")


def _sync_down_folder(service, folder_id, local_dir):
    local_dir.mkdir(parents=True, exist_ok=True)
    page_token = None
    while True:
        res = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=page_token, pageSize=200, **_LIST_KW,
        ).execute()
        for item in res.get("files", []):
            if item["mimeType"] == "application/vnd.google-apps.folder":
                _sync_down_folder(service, item["id"], local_dir / item["name"])
            else:
                local_path = local_dir / item["name"]
                if not local_path.exists():
                    _download_file(service, item["id"], local_path)
        page_token = res.get("nextPageToken")
        if not page_token:
            break


def _download_file(service, file_id, local_path):
    from googleapiclient.http import MediaIoBaseDownload

    request = service.files().get_media(fileId=file_id, **_DRIVE_KW)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    local_path.write_bytes(buf.getvalue())
