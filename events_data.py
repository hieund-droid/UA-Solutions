#!/usr/bin/env python3
"""
events_data.py — Danh sách ngày lễ/sự kiện theo quốc gia, phục vụ team UA
biết trước "sắp tới có gì" để chuẩn bị ads (đổi outro theo mùa, tăng ngân
sách trước Black Friday, v.v.).

CHỈ đưa vào đây những mục ĐÃ CÓ NGUỒN THẬT kiểm chứng được (source field —
link chính phủ/Wikipedia có trích dẫn/trang tin uy tín) — không tự bịa ngày
theo trí nhớ. Nếu không tìm được nguồn đáng tin cho 1 ngày nào đó, THÀ BỎ
QUA còn hơn đưa vào sai (giống triết lý "an toàn hơn đoán liều" của
outro_core.py).

Cấu trúc 1 sự kiện:
    {
        "name": "Tên tiếng Anh",              # hiển thị chính
        "local_name": "Tên bản địa" | None,    # tuỳ chọn, hiển thị kèm
        "country": "US",                       # mã quốc gia ngắn, xem COUNTRIES
        "tier": 1,                             # 1 hoặc 2 (gộp chung tier 2+3)
        "category": "official",                # official | shopping | unofficial
        "date_type": "fixed" | "nth_weekday" | "explicit",
        # fixed: có "month", "day" cố định hàng năm (vd Giáng sinh 25/12).
        # nth_weekday: có "month", "weekday" (0=Thứ 2...6=CN), "nth" (1-5,
        #   âm để đếm từ cuối tháng vd -1 = thứ cuối cùng), "offset_days"
        #   (tuỳ chọn, để tính ngày LIỀN SAU/TRƯỚC mốc đó — vd Black Friday
        #   = thứ 6 liền sau Lễ Tạ Ơn Mỹ, offset_days=1 tính từ Lễ Tạ Ơn).
        # explicit: ngày ÂM LỊCH/tôn giáo đổi theo năm, KHÔNG tính được bằng
        #   công thức (Tết, Diwali, Eid, Chuseok...) — lưu sẵn ngày CỤ THỂ
        #   lần diễn ra GẦN NHẤT đã kiểm chứng được nguồn, dạng "YYYY-MM-DD"
        #   ở field "date". Cần CẬP NHẬT LẠI mỗi năm khi ngày đó trôi qua —
        #   xem hàm needs_update() bên dưới để tool tự cảnh báo mục nào cũ.
        "month": 12, "day": 25,                # dùng cho date_type="fixed"
        "source": "https://...",               # bắt buộc — link đã kiểm chứng
        "note": "Ghi chú thêm (tuỳ chọn)",
    }
"""

from datetime import date, timedelta

COUNTRIES = {
    "US": ("United States", 1), "UK": ("United Kingdom", 1), "Canada": ("Canada", 1),
    "Australia": ("Australia", 1), "Germany": ("Germany", 1), "France": ("France", 1),
    "Japan": ("Japan", 1), "South Korea": ("South Korea", 1),
    "India": ("India", 2), "Brazil": ("Brazil", 2), "Mexico": ("Mexico", 2),
    "Indonesia": ("Indonesia", 2), "Philippines": ("Philippines", 2),
}

CATEGORY_LABELS = {
    "official": "Lễ chính thức", "shopping": "Sự kiện mua sắm", "unofficial": "Không chính thức",
}

# Dữ liệu bên dưới lấy từ đợt nghiên cứu qua web thật (2026-08-26) — mỗi
# mục có "source" là link đã thực sự tra cứu được, không suy đoán theo trí
# nhớ. Chi tiết đầy đủ (kể cả các mục KHÔNG đưa vào vì chưa đủ tin cậy) đã
# báo cáo lại cho người dùng lúc làm — xem lại hội thoại nếu cần đối chiếu.
#
# date_type="explicit" (ngày âm lịch/tôn giáo/lịch bán lẻ tự đặt — Tết,
# Diwali, Eid, Seollal, Chuseok, El Buen Fin...) SẼ CŨ DẦN theo thời gian —
# needs_update() tự phát hiện mục nào đã qua ngày lưu sẵn để cảnh báo cập
# nhật lại, xem render_events() trong app.py.
EVENTS = [
    # ---------------- UNITED STATES ----------------
    {"name": "New Year's Day", "country": "US", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 1, "day": 1,
     "source": "https://remitly.com/blog/lifestyle-culture/us-federal-holidays"},
    {"name": "Martin Luther King Jr. Day", "country": "US", "tier": 1, "category": "official",
     "date_type": "nth_weekday", "month": 1, "weekday": 0, "nth": 3,
     "source": "https://remitly.com/blog/lifestyle-culture/us-federal-holidays"},
    {"name": "Presidents Day", "country": "US", "tier": 1, "category": "official",
     "date_type": "nth_weekday", "month": 2, "weekday": 0, "nth": 3,
     "source": "https://remitly.com/blog/lifestyle-culture/us-federal-holidays"},
    {"name": "Valentine's Day", "country": "US", "tier": 1, "category": "unofficial",
     "date_type": "fixed", "month": 2, "day": 14,
     "source": "https://en.wikipedia.org/wiki/Valentine%27s_Day"},
    {"name": "Galentine's Day", "country": "US", "tier": 1, "category": "unofficial",
     "date_type": "fixed", "month": 2, "day": 13,
     "source": "https://en.wikipedia.org/wiki/Galentine%27s_Day_(observance)",
     "note": "Viral từ phim Parks and Recreation, được thương mại hoá rộng rãi từ ~2017-2020"},
    {"name": "Super Bowl Sunday", "country": "US", "tier": 1, "category": "unofficial",
     "date_type": "explicit", "date": "2026-02-08",
     "source": "https://sports.yahoo.com", "note": "Ngày do NFL ấn định hàng năm, không theo quy tắc cố định"},
    {"name": "Memorial Day", "country": "US", "tier": 1, "category": "official",
     "date_type": "nth_weekday", "month": 5, "weekday": 0, "nth": -1,
     "source": "https://remitly.com/blog/lifestyle-culture/us-federal-holidays"},
    {"name": "Juneteenth", "country": "US", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 6, "day": 19,
     "source": "https://timeanddate.com/holidays/us/juneteenth"},
    {"name": "Independence Day", "country": "US", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 7, "day": 4,
     "source": "https://remitly.com/blog/lifestyle-culture/us-federal-holidays"},
    {"name": "Labor Day", "country": "US", "tier": 1, "category": "official",
     "date_type": "nth_weekday", "month": 9, "weekday": 0, "nth": 1,
     "source": "https://remitly.com/blog/lifestyle-culture/us-federal-holidays"},
    {"name": "Halloween", "country": "US", "tier": 1, "category": "unofficial",
     "date_type": "fixed", "month": 10, "day": 31,
     "source": "https://en.wikipedia.org/wiki/Halloween"},
    {"name": "Thanksgiving Day", "country": "US", "tier": 1, "category": "official",
     "date_type": "nth_weekday", "month": 11, "weekday": 3, "nth": 4,
     "source": "https://remitly.com/blog/lifestyle-culture/us-federal-holidays"},
    {"name": "Black Friday", "country": "US", "tier": 1, "category": "shopping",
     "date_type": "nth_weekday", "month": 11, "weekday": 3, "nth": 4, "offset_days": 1,
     "source": "https://shopback.com/blog/finance/us-2026-sale-calendar"},
    {"name": "Cyber Monday", "country": "US", "tier": 1, "category": "shopping",
     "date_type": "nth_weekday", "month": 11, "weekday": 3, "nth": 4, "offset_days": 4,
     "source": "https://shopback.com/blog/finance/us-2026-sale-calendar"},
    {"name": "Christmas Day", "country": "US", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 12, "day": 25,
     "source": "https://remitly.com/blog/lifestyle-culture/us-federal-holidays"},

    # ---------------- UNITED KINGDOM ----------------
    {"name": "New Year's Day", "country": "UK", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 1, "day": 1,
     "source": "https://time-and-date.uk.com/uk-bank-holidays-2026"},
    {"name": "Valentine's Day", "country": "UK", "tier": 1, "category": "unofficial",
     "date_type": "fixed", "month": 2, "day": 14,
     "source": "https://en.wikipedia.org/wiki/Valentine%27s_Day"},
    {"name": "Mothering Sunday", "country": "UK", "tier": 1, "category": "unofficial",
     "date_type": "easter_offset", "offset_days": -21,
     "source": "https://awarenessdays.com/awareness-days-calendar/mothers-day-uk"},
    {"name": "Good Friday", "country": "UK", "tier": 1, "category": "official",
     "date_type": "easter_offset", "offset_days": -2,
     "source": "https://time-and-date.uk.com/uk-bank-holidays-2026"},
    {"name": "Easter Monday", "country": "UK", "tier": 1, "category": "official",
     "date_type": "easter_offset", "offset_days": 1,
     "source": "https://time-and-date.uk.com/uk-bank-holidays-2026"},
    {"name": "Early May Bank Holiday", "country": "UK", "tier": 1, "category": "official",
     "date_type": "nth_weekday", "month": 5, "weekday": 0, "nth": 1,
     "source": "https://time-and-date.uk.com/uk-bank-holidays-2026"},
    {"name": "Spring Bank Holiday", "country": "UK", "tier": 1, "category": "official",
     "date_type": "nth_weekday", "month": 5, "weekday": 0, "nth": -1,
     "source": "https://time-and-date.uk.com/uk-bank-holidays-2026"},
    {"name": "Father's Day", "country": "UK", "tier": 1, "category": "unofficial",
     "date_type": "nth_weekday", "month": 6, "weekday": 6, "nth": 3,
     "source": "https://timeanddate.com/holidays/uk/father-day"},
    {"name": "Halloween", "country": "UK", "tier": 1, "category": "unofficial",
     "date_type": "fixed", "month": 10, "day": 31, "source": "https://en.wikipedia.org/wiki/Halloween"},
    {"name": "Summer Bank Holiday", "country": "UK", "tier": 1, "category": "official",
     "date_type": "nth_weekday", "month": 8, "weekday": 0, "nth": -1,
     "source": "https://time-and-date.uk.com/uk-bank-holidays-2026"},
    {"name": "Black Friday", "country": "UK", "tier": 1, "category": "shopping",
     "date_type": "nth_weekday", "month": 11, "weekday": 3, "nth": 4, "offset_days": 1,
     "source": "https://shopback.com/blog/finance/us-2026-sale-calendar",
     "note": "Ngày theo lịch bán lẻ toàn cầu, UK áp dụng cùng ngày (chưa có nguồn riêng UK xác nhận)"},
    {"name": "Cyber Monday", "country": "UK", "tier": 1, "category": "shopping",
     "date_type": "nth_weekday", "month": 11, "weekday": 3, "nth": 4, "offset_days": 4,
     "source": "https://shopback.com/blog/finance/us-2026-sale-calendar"},
    {"name": "Christmas Day", "country": "UK", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 12, "day": 25,
     "source": "https://x.com/GOVUK/status/2007087899888746644"},
    {"name": "Boxing Day", "country": "UK", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 12, "day": 26,
     "source": "https://x.com/GOVUK/status/2007087899888746644"},

    # ---------------- CANADA ----------------
    {"name": "New Year's Day", "country": "Canada", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 1, "day": 1,
     "source": "https://remitly.com/blog/en-ca/lifestyle-and-culture/federal-statutory-holidays-in-canada-calendar"},
    {"name": "Valentine's Day", "country": "Canada", "tier": 1, "category": "unofficial",
     "date_type": "fixed", "month": 2, "day": 14, "source": "https://en.wikipedia.org/wiki/Valentine%27s_Day"},
    {"name": "Good Friday", "country": "Canada", "tier": 1, "category": "official",
     "date_type": "easter_offset", "offset_days": -2,
     "source": "https://remitly.com/blog/en-ca/lifestyle-and-culture/federal-statutory-holidays-in-canada-calendar"},
    {"name": "Victoria Day", "country": "Canada", "tier": 1, "category": "official",
     "date_type": "explicit", "date": "2026-05-18",
     "source": "https://remitly.com/blog/en-ca/lifestyle-and-culture/federal-statutory-holidays-in-canada-calendar",
     "note": "Quy tắc: thứ Hai liền TRƯỚC ngày 25/5 — cần cập nhật tay mỗi năm"},
    {"name": "Mother's Day", "country": "Canada", "tier": 1, "category": "unofficial",
     "date_type": "nth_weekday", "month": 5, "weekday": 6, "nth": 2,
     "source": "https://twinkl.com/event/mothers-day-canada-2026"},
    {"name": "Canada Day", "country": "Canada", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 7, "day": 1,
     "source": "https://remitly.com/blog/en-ca/lifestyle-and-culture/federal-statutory-holidays-in-canada-calendar"},
    {"name": "Father's Day", "country": "Canada", "tier": 1, "category": "unofficial",
     "date_type": "nth_weekday", "month": 6, "weekday": 6, "nth": 3,
     "source": "https://timeanddate.com/holidays/canada/father-day"},
    {"name": "Labour Day", "country": "Canada", "tier": 1, "category": "official",
     "date_type": "nth_weekday", "month": 9, "weekday": 0, "nth": 1,
     "source": "https://remitly.com/blog/en-ca/lifestyle-and-culture/federal-statutory-holidays-in-canada-calendar"},
    {"name": "National Day for Truth and Reconciliation", "country": "Canada", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 9, "day": 30,
     "source": "https://canada.ca/en/canadian-heritage/campaigns/national-day-truth-reconciliation.html",
     "note": "Chỉ bắt buộc nghỉ với lao động thuộc quản lý liên bang + 1 số tỉnh bang, không toàn quốc"},
    {"name": "Halloween", "country": "Canada", "tier": 1, "category": "unofficial",
     "date_type": "fixed", "month": 10, "day": 31, "source": "https://en.wikipedia.org/wiki/Halloween"},
    {"name": "Thanksgiving (Canada)", "country": "Canada", "tier": 1, "category": "official",
     "date_type": "nth_weekday", "month": 10, "weekday": 0, "nth": 2,
     "source": "https://remitly.com/blog/en-ca/lifestyle-and-culture/federal-statutory-holidays-in-canada-calendar"},
    {"name": "Remembrance Day", "country": "Canada", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 11, "day": 11,
     "source": "https://remitly.com/blog/en-ca/lifestyle-and-culture/federal-statutory-holidays-in-canada-calendar"},
    {"name": "Black Friday", "country": "Canada", "tier": 1, "category": "shopping",
     "date_type": "nth_weekday", "month": 11, "weekday": 3, "nth": 4, "offset_days": 1,
     "source": "https://shopback.com/blog/finance/us-2026-sale-calendar"},
    {"name": "Cyber Monday", "country": "Canada", "tier": 1, "category": "shopping",
     "date_type": "nth_weekday", "month": 11, "weekday": 3, "nth": 4, "offset_days": 4,
     "source": "https://shopback.com/blog/finance/us-2026-sale-calendar"},
    {"name": "Christmas Day", "country": "Canada", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 12, "day": 25,
     "source": "https://remitly.com/blog/en-ca/lifestyle-and-culture/federal-statutory-holidays-in-canada-calendar"},
    {"name": "Boxing Day", "country": "Canada", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 12, "day": 26,
     "source": "https://remitly.com/blog/en-ca/lifestyle-and-culture/federal-statutory-holidays-in-canada-calendar"},

    # ---------------- GERMANY ----------------
    {"name": "New Year's Day", "local_name": "Neujahr", "country": "Germany", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 1, "day": 1, "source": "https://publicholidays.de/2026-dates"},
    {"name": "Rose Monday", "local_name": "Rosenmontag", "country": "Germany", "tier": 1, "category": "unofficial",
     "date_type": "easter_offset", "offset_days": -48,
     "source": "https://cute-calendar.com", "note": "Chỉ nghỉ thực tế ở vùng Rhineland (Köln, Düsseldorf, Bonn, Mainz)"},
    {"name": "Good Friday", "local_name": "Karfreitag", "country": "Germany", "tier": 1, "category": "official",
     "date_type": "easter_offset", "offset_days": -2, "source": "https://publicholidays.de/2026-dates"},
    {"name": "Easter Monday", "local_name": "Ostermontag", "country": "Germany", "tier": 1, "category": "official",
     "date_type": "easter_offset", "offset_days": 1, "source": "https://publicholidays.de/2026-dates"},
    {"name": "Labour Day", "local_name": "Tag der Arbeit", "country": "Germany", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 5, "day": 1, "source": "https://publicholidays.de/2026-dates"},
    {"name": "Mother's Day", "local_name": "Muttertag", "country": "Germany", "tier": 1, "category": "unofficial",
     "date_type": "nth_weekday", "month": 5, "weekday": 6, "nth": 2, "source": "https://schulferien.org"},
    {"name": "Ascension Day", "local_name": "Christi Himmelfahrt", "country": "Germany", "tier": 1, "category": "official",
     "date_type": "easter_offset", "offset_days": 39, "source": "https://publicholidays.de/2026-dates",
     "note": "Cũng là \"Vatertag\" (Father's Day dân gian Đức) — văn hoá đàn ông đi chơi/uống bia"},
    {"name": "Whit Monday", "local_name": "Pfingstmontag", "country": "Germany", "tier": 1, "category": "official",
     "date_type": "easter_offset", "offset_days": 50, "source": "https://publicholidays.de/2026-dates"},
    {"name": "German Unity Day", "local_name": "Tag der Deutschen Einheit", "country": "Germany", "tier": 1,
     "category": "official", "date_type": "fixed", "month": 10, "day": 3,
     "source": "https://publicholidays.de/2026-dates"},
    {"name": "Reformation Day", "local_name": "Reformationstag", "country": "Germany", "tier": 1,
     "category": "official", "date_type": "fixed", "month": 10, "day": 31,
     "source": "https://ruhrnachrichten.de", "note": "Chỉ 9/16 bang (không có ở Bayern, Berlin, NRW, Hesse...)"},
    {"name": "Black Friday", "country": "Germany", "tier": 1, "category": "shopping",
     "date_type": "nth_weekday", "month": 11, "weekday": 3, "nth": 4, "offset_days": 1,
     "source": "https://publicholidays.de/black-friday"},
    {"name": "Cyber Monday", "country": "Germany", "tier": 1, "category": "shopping",
     "date_type": "nth_weekday", "month": 11, "weekday": 3, "nth": 4, "offset_days": 4,
     "source": "https://calendardate.com/cyber_monday_2026"},
    {"name": "Christmas Day", "local_name": "1. Weihnachtstag", "country": "Germany", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 12, "day": 25, "source": "https://publicholidays.de/2026-dates"},
    {"name": "Boxing Day", "local_name": "2. Weihnachtstag", "country": "Germany", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 12, "day": 26, "source": "https://publicholidays.de/2026-dates"},

    # ---------------- FRANCE ----------------
    {"name": "New Year's Day", "local_name": "Jour de l'An", "country": "France", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 1, "day": 1, "source": "https://franceinfo.fr"},
    {"name": "Winter Sales", "local_name": "Soldes d'hiver", "country": "France", "tier": 1, "category": "shopping",
     "date_type": "explicit", "date": "2026-01-07",
     "source": "https://service-public.gouv.fr/A17952",
     "note": "Nhà nước Pháp quy định, kéo dài ~4 tuần từ đầu tháng 1"},
    {"name": "Easter Monday", "local_name": "Lundi de Pâques", "country": "France", "tier": 1, "category": "official",
     "date_type": "easter_offset", "offset_days": 1, "source": "https://franceinfo.fr"},
    {"name": "Labour Day", "local_name": "Fête du Travail", "country": "France", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 5, "day": 1, "source": "https://franceinfo.fr"},
    {"name": "Victory Day 1945", "local_name": "Fête de la Victoire", "country": "France", "tier": 1,
     "category": "official", "date_type": "fixed", "month": 5, "day": 8, "source": "https://franceinfo.fr"},
    {"name": "Mother's Day", "local_name": "Fête des Mères", "country": "France", "tier": 1, "category": "unofficial",
     "date_type": "nth_weekday", "month": 5, "weekday": 6, "nth": -1, "source": "https://icalendrier.fr"},
    {"name": "Ascension Day", "local_name": "Jour de l'Ascension", "country": "France", "tier": 1,
     "category": "official", "date_type": "easter_offset", "offset_days": 39, "source": "https://franceinfo.fr"},
    {"name": "Whit Monday", "local_name": "Lundi de Pentecôte", "country": "France", "tier": 1, "category": "official",
     "date_type": "easter_offset", "offset_days": 50, "source": "https://franceinfo.fr"},
    {"name": "Father's Day", "local_name": "Fête des Pères", "country": "France", "tier": 1, "category": "unofficial",
     "date_type": "nth_weekday", "month": 6, "weekday": 6, "nth": 3, "source": "https://fltmfrance.com"},
    {"name": "Summer Sales", "local_name": "Soldes d'été", "country": "France", "tier": 1, "category": "shopping",
     "date_type": "explicit", "date": "2026-06-24",
     "source": "https://economie.gouv.fr", "note": "Nhà nước Pháp quy định, kéo dài ~4 tuần từ cuối tháng 6"},
    {"name": "Bastille Day", "local_name": "Fête Nationale", "country": "France", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 7, "day": 14, "source": "https://franceinfo.fr"},
    {"name": "Assumption Day", "local_name": "Assomption", "country": "France", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 8, "day": 15, "source": "https://franceinfo.fr"},
    {"name": "Back-to-school", "local_name": "Rentrée scolaire", "country": "France", "tier": 1,
     "category": "unofficial", "date_type": "fixed", "month": 9, "day": 1,
     "source": "https://info.gouv.fr", "note": "Cao điểm mua sắm đồ dùng học tập"},
    {"name": "All Saints' Day", "local_name": "Toussaint", "country": "France", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 11, "day": 1, "source": "https://franceinfo.fr"},
    {"name": "Armistice Day", "local_name": "Jour d'Armistice", "country": "France", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 11, "day": 11, "source": "https://franceinfo.fr"},
    {"name": "Beaujolais Nouveau Day", "country": "France", "tier": 1, "category": "unofficial",
     "date_type": "nth_weekday", "month": 11, "weekday": 3, "nth": 3,
     "source": "https://nationaltoday.com/beaujolais-nouveau-day"},
    {"name": "Black Friday", "country": "France", "tier": 1, "category": "shopping",
     "date_type": "nth_weekday", "month": 11, "weekday": 3, "nth": 4, "offset_days": 1,
     "source": "https://publicholidays.de/black-friday"},
    {"name": "Christmas Day", "local_name": "Noël", "country": "France", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 12, "day": 25, "source": "https://franceinfo.fr"},

    # ---------------- JAPAN ----------------
    {"name": "New Year's Day", "local_name": "元日", "country": "Japan", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 1, "day": 1, "source": "https://nippon.com/en/japan-data/h02302"},
    {"name": "Fukubukuro Lucky Bag Sales", "local_name": "福袋", "country": "Japan", "tier": 1, "category": "shopping",
     "date_type": "fixed", "month": 1, "day": 1, "source": "https://tokyoweekender.com",
     "note": "Mùa mua sắm lớn nhất năm, Dec29-Jan3 phần lớn đóng cửa, sale bắt đầu Jan1-2"},
    {"name": "Coming of Age Day", "local_name": "成人の日", "country": "Japan", "tier": 1, "category": "official",
     "date_type": "nth_weekday", "month": 1, "weekday": 0, "nth": 2, "source": "https://nippon.com/en/japan-data/h02302"},
    {"name": "National Foundation Day", "local_name": "建国記念の日", "country": "Japan", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 2, "day": 11, "source": "https://nippon.com/en/japan-data/h02794"},
    {"name": "Valentine's Day", "local_name": "バレンタインデー", "country": "Japan", "tier": 1, "category": "unofficial",
     "date_type": "fixed", "month": 2, "day": 14, "source": "https://tokyoweekender.com",
     "note": "Phụ nữ tặng chocolate cho nam giới — ngược văn hoá phương Tây"},
    {"name": "Emperor's Birthday", "local_name": "天皇誕生日", "country": "Japan", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 2, "day": 23, "source": "https://nippon.com/en/japan-data/h02794"},
    {"name": "White Day", "local_name": "ホワイトデー", "country": "Japan", "tier": 1, "category": "unofficial",
     "date_type": "fixed", "month": 3, "day": 14, "source": "https://time.com",
     "note": "Nam giới đáp lễ quà Valentine — khởi nguồn từ Nhật, sau lan sang Hàn/Đài Loan/TQ"},
    {"name": "Golden Week", "local_name": "ゴールデンウィーク", "country": "Japan", "tier": 1, "category": "official",
     "date_type": "explicit", "date": "2026-04-29",
     "source": "https://nippon.com/en/japan-data/h02302", "note": "Chuỗi nghỉ lễ dài nhất năm, kéo dài tới 6/5/2026"},
    {"name": "Marine Day", "local_name": "海の日", "country": "Japan", "tier": 1, "category": "official",
     "date_type": "nth_weekday", "month": 7, "weekday": 0, "nth": 3, "source": "https://nippon.com/en/japan-data/h02794"},
    {"name": "Mountain Day", "local_name": "山の日", "country": "Japan", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 8, "day": 11, "source": "https://nippon.com/en/japan-data/h02794"},
    {"name": "Obon", "local_name": "お盆", "country": "Japan", "tier": 1, "category": "unofficial",
     "date_type": "fixed", "month": 8, "day": 13, "source": "https://jrailpass.com",
     "note": "Không phải quốc lễ nhưng cao điểm di chuyển/nghỉ cả nước, ~13-16/8"},
    {"name": "Respect for the Aged Day", "local_name": "敬老の日", "country": "Japan", "tier": 1, "category": "official",
     "date_type": "nth_weekday", "month": 9, "weekday": 0, "nth": 3, "source": "https://en.japantravel.com"},
    {"name": "Black Friday", "country": "Japan", "tier": 1, "category": "shopping",
     "date_type": "nth_weekday", "month": 11, "weekday": 3, "nth": 4, "offset_days": 1,
     "source": "https://japanlifelab.com/amazon-japan-sale-calendar-2026"},
    {"name": "Christmas Day", "country": "Japan", "tier": 1, "category": "unofficial",
     "date_type": "fixed", "month": 12, "day": 25, "source": "https://nippon.com",
     "note": "Không phải quốc lễ (vẫn đi làm) nhưng thương mại hoá mạnh, gắn với hẹn hò/quà tặng"},

    # ---------------- SOUTH KOREA ----------------
    {"name": "New Year's Day", "local_name": "신정", "country": "South Korea", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 1, "day": 1, "source": "https://calendarific.com/holidays/2027/KR"},
    {"name": "Seollal (Lunar New Year)", "local_name": "설날", "country": "South Korea", "tier": 1,
     "category": "official", "date_type": "explicit", "date": "2026-02-16",
     "source": "https://publicholidays.co.kr/seollal", "note": "3 ngày (16-18/2/2026), mùa biếu quà/di chuyển lớn nhất năm"},
    {"name": "Independence Movement Day", "local_name": "삼일절", "country": "South Korea", "tier": 1,
     "category": "official", "date_type": "fixed", "month": 3, "day": 1,
     "source": "https://calendarific.com/holidays/2027/KR"},
    {"name": "White Day", "local_name": "화이트데이", "country": "South Korea", "tier": 1, "category": "unofficial",
     "date_type": "fixed", "month": 3, "day": 14, "source": "https://90daykorean.com/white-day-in-korea"},
    {"name": "Black Day", "local_name": "블랙데이", "country": "South Korea", "tier": 1, "category": "unofficial",
     "date_type": "fixed", "month": 4, "day": 14,
     "source": "https://en.wikipedia.org/wiki/Black_Day_(South_Korea)",
     "note": "Ngày người độc thân ăn mì tương đen — viral, được biết rộng rãi"},
    {"name": "Buddha's Birthday", "local_name": "석가탄신일", "country": "South Korea", "tier": 1, "category": "official",
     "date_type": "explicit", "date": "2026-05-24", "source": "https://time.now/holidays/south-korea/buddhas-birthday"},
    {"name": "Children's Day", "local_name": "어린이날", "country": "South Korea", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 5, "day": 5, "source": "https://calendarific.com/holidays/2027/KR"},
    {"name": "Memorial Day", "local_name": "현충일", "country": "South Korea", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 6, "day": 6, "source": "https://calendarific.com/holidays/2027/KR"},
    {"name": "Liberation Day", "local_name": "광복절", "country": "South Korea", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 8, "day": 15, "source": "https://calendarific.com/holidays/2027/KR"},
    {"name": "Chuseok", "local_name": "추석", "country": "South Korea", "tier": 1, "category": "official",
     "date_type": "explicit", "date": "2026-09-24",
     "source": "https://publicholidays.co.kr/chuseok", "note": "3 ngày (24-26/9/2026), mùa biếu quà lớn nhất năm (như Tết Trung thu + Lễ Tạ ơn gộp lại)"},
    {"name": "National Foundation Day", "local_name": "개천절", "country": "South Korea", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 10, "day": 3, "source": "https://calendarific.com/holidays/2027/KR"},
    {"name": "Hangeul Day", "local_name": "한글날", "country": "South Korea", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 10, "day": 9, "source": "https://calendarific.com/holidays/2027/KR"},
    {"name": "Pepero Day", "local_name": "빼빼로데이", "country": "South Korea", "tier": 1, "category": "unofficial",
     "date_type": "fixed", "month": 11, "day": 11,
     "source": "https://en.wikipedia.org/wiki/Pepero_Day",
     "note": "Ngày \"day marketing\" lớn nhất Hàn Quốc, do Lotte khởi xướng"},
    {"name": "Black Friday", "country": "South Korea", "tier": 1, "category": "shopping",
     "date_type": "nth_weekday", "month": 11, "weekday": 3, "nth": 4, "offset_days": 1,
     "source": "https://koreaittimes.com"},
    {"name": "Christmas Day", "local_name": "크리스마스", "country": "South Korea", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 12, "day": 25, "source": "https://calendarific.com/holidays/2027/KR"},

    # ---------------- AUSTRALIA ----------------
    {"name": "New Year's Day", "country": "Australia", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 1, "day": 1,
     "source": "https://fairwork.gov.au/employment-conditions/public-holidays/2026-public-holidays"},
    {"name": "Australia Day", "country": "Australia", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 1, "day": 26,
     "source": "https://fairwork.gov.au/employment-conditions/public-holidays/2026-public-holidays"},
    {"name": "Valentine's Day", "country": "Australia", "tier": 1, "category": "unofficial",
     "date_type": "fixed", "month": 2, "day": 14,
     "source": "https://roymorgan.com/findings/10121-arc-roy-morgan-media-release-valentines-day-spending-2026"},
    {"name": "Good Friday", "country": "Australia", "tier": 1, "category": "official",
     "date_type": "easter_offset", "offset_days": -2,
     "source": "https://timeanddate.com/holidays/australia/2026"},
    {"name": "Easter Monday", "country": "Australia", "tier": 1, "category": "official",
     "date_type": "easter_offset", "offset_days": 1, "source": "https://timeanddate.com/holidays/australia/2026"},
    {"name": "Anzac Day", "country": "Australia", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 4, "day": 25,
     "source": "https://fairwork.gov.au/employment-conditions/public-holidays/2026-public-holidays"},
    {"name": "Mother's Day", "country": "Australia", "tier": 1, "category": "unofficial",
     "date_type": "nth_weekday", "month": 5, "weekday": 6, "nth": 2, "source": "https://holidayapi.com/holidays/au/mothers-day"},
    {"name": "EOFY Sales", "country": "Australia", "tier": 1, "category": "shopping",
     "date_type": "fixed", "month": 6, "day": 30,
     "source": "https://choice.com.au/shopping/everyday-shopping/bargain-hunting/articles/what-to-know-for-eofy",
     "note": "Sale suốt tháng 6, đậm nhất 24-30/6 (theo năm tài chính Úc 1/7-30/6)"},
    {"name": "Afterpay Day", "country": "Australia", "tier": 1, "category": "shopping",
     "date_type": "explicit", "date": "2026-08-13",
     "source": "https://shopback.com.au/blog/savings/how-to-shop-afterpay-day-australia-2026"},
    {"name": "Father's Day (Australia)", "country": "Australia", "tier": 1, "category": "unofficial",
     "date_type": "nth_weekday", "month": 9, "weekday": 6, "nth": 1,
     "source": "https://manofmany.com/culture/fathers-day-australia",
     "note": "Khác Mỹ/UK (tháng 6) — Úc là Chủ nhật đầu tháng 9"},
    {"name": "Melbourne Cup Day (Victoria)", "country": "Australia", "tier": 1, "category": "official",
     "date_type": "nth_weekday", "month": 11, "weekday": 1, "nth": 1,
     "source": "https://publicholidays.com.au/melbourne-cup-day", "note": "Chỉ nghỉ ở bang Victoria, nhưng cả nước quan tâm (đua ngựa/cá cược lớn)"},
    {"name": "Click Frenzy", "country": "Australia", "tier": 1, "category": "shopping",
     "date_type": "explicit", "date": "2026-11-17", "source": "https://clickfrenzy.com.au/calendar"},
    {"name": "Black Friday", "country": "Australia", "tier": 1, "category": "shopping",
     "date_type": "nth_weekday", "month": 11, "weekday": 3, "nth": 4, "offset_days": 1,
     "source": "https://shopback.com.au/blog/finance/australia-black-friday-2026-sale-calendar"},
    {"name": "Cyber Monday", "country": "Australia", "tier": 1, "category": "shopping",
     "date_type": "nth_weekday", "month": 11, "weekday": 3, "nth": 4, "offset_days": 4,
     "source": "https://shopback.com.au/blog/finance/australia-black-friday-2026-sale-calendar"},
    {"name": "Christmas Day", "country": "Australia", "tier": 1, "category": "official",
     "date_type": "fixed", "month": 12, "day": 25,
     "source": "https://fairwork.gov.au/employment-conditions/public-holidays/2026-public-holidays"},
    {"name": "Boxing Day Sales", "country": "Australia", "tier": 1, "category": "shopping",
     "date_type": "fixed", "month": 12, "day": 26,
     "source": "https://manofmany.com/culture/best-boxing-day-sales",
     "note": "Ngày mua sắm tại cửa hàng lớn nhất năm ở Úc"},

    # ---------------- INDIA ----------------
    {"name": "Makar Sankranti", "country": "India", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 1, "day": 14,
     "source": "https://indiatvnews.com/lifestyle/spirituality/makar-sankranti-2026-date-january-14-or-15-muhurat-explained-2026-01-14-1025793"},
    {"name": "Republic Day", "country": "India", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 1, "day": 26, "source": "https://cleartax.in/s/government-holidays-2026"},
    {"name": "Valentine's Day", "country": "India", "tier": 2, "category": "unofficial",
     "date_type": "fixed", "month": 2, "day": 14, "source": "https://en.wikipedia.org/wiki/Valentine%27s_Day"},
    {"name": "Holi", "country": "India", "tier": 2, "category": "official",
     "date_type": "explicit", "date": "2026-03-04", "source": "https://cleartax.in/s/government-holidays-2026"},
    {"name": "Eid al-Fitr", "country": "India", "tier": 2, "category": "official",
     "date_type": "explicit", "date": "2026-03-21",
     "source": "https://cleartax.in/s/government-holidays-2026",
     "note": "Ngày tạm tính (theo quan sát mặt trăng), có thể lệch 1 ngày tới sát ngày mới chốt chính thức"},
    {"name": "Eid al-Adha (Bakrid)", "country": "India", "tier": 2, "category": "official",
     "date_type": "explicit", "date": "2026-05-27",
     "source": "https://cleartax.in/s/government-holidays-2026", "note": "Ngày tạm tính, theo quan sát mặt trăng"},
    {"name": "Amazon Great Republic Day Sale", "country": "India", "tier": 2, "category": "shopping",
     "date_type": "explicit", "date": "2026-01-16",
     "source": "https://aboutamazon.in/news/retail/amazon-great-republic-day-sale-2026"},
    {"name": "Independence Day", "country": "India", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 8, "day": 15, "source": "https://cleartax.in/s/government-holidays-2026"},
    {"name": "Friendship Day (India)", "country": "India", "tier": 2, "category": "unofficial",
     "date_type": "nth_weekday", "month": 8, "weekday": 6, "nth": 1,
     "source": "https://lovelydesign.in/blog/friendship-day-2026-date-history-why-august-first-sunday",
     "note": "Quy ước riêng của Ấn Độ (Chủ nhật đầu tháng 8), phổ biến từ phim Bollywood 1998"},
    {"name": "Raksha Bandhan", "country": "India", "tier": 2, "category": "unofficial",
     "date_type": "explicit", "date": "2026-08-28", "source": "https://rakhisale.com/when-is-rakhi.asp",
     "note": "Không phải quốc lễ nhưng dịp tặng quà anh chị em lớn"},
    {"name": "Ganesh Chaturthi", "country": "India", "tier": 2, "category": "unofficial",
     "date_type": "explicit", "date": "2026-09-14", "source": "https://imagicaaworld.com/blog/ganesh-chaturthi-2026",
     "note": "Lớn nhất ở Maharashtra/miền Tây/Nam Ấn Độ"},
    {"name": "Gandhi Jayanti", "country": "India", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 10, "day": 2, "source": "https://cleartax.in/s/government-holidays-2026"},
    {"name": "Dussehra", "country": "India", "tier": 2, "category": "official",
     "date_type": "explicit", "date": "2026-10-20", "source": "https://cleartax.in/s/government-holidays-2026"},
    {"name": "Karwa Chauth", "country": "India", "tier": 2, "category": "unofficial",
     "date_type": "explicit", "date": "2026-10-29", "source": "https://winni.in/article/when-is-karwa-chauth",
     "note": "Không phải quốc lễ nhưng dịp mua trang sức/thời trang lớn"},
    {"name": "Diwali", "country": "India", "tier": 2, "category": "official",
     "date_type": "explicit", "date": "2026-11-08",
     "source": "https://publicholidays.in/diwali-deepavali", "note": "Dịp mua sắm/biếu quà lớn nhất năm ở Ấn Độ"},
    {"name": "Black Friday", "country": "India", "tier": 2, "category": "shopping",
     "date_type": "nth_weekday", "month": 11, "weekday": 3, "nth": 4, "offset_days": 1,
     "source": "https://shopback.com/blog/finance/us-2026-sale-calendar",
     "note": "Ngày theo lịch bán lẻ toàn cầu, chưa có nguồn riêng xác nhận mức độ phổ biến tại Ấn Độ"},

    # ---------------- BRAZIL ----------------
    {"name": "New Year's Day", "local_name": "Confraternização Universal", "country": "Brazil", "tier": 2,
     "category": "official", "date_type": "fixed", "month": 1, "day": 1,
     "source": "https://officeholidays.com/countries/brazil/2026"},
    {"name": "Carnaval", "country": "Brazil", "tier": 2, "category": "official",
     "date_type": "easter_offset", "offset_days": -47,
     "source": "https://calendarr.com/brasil/carnaval", "note": "Cả tuần lễ hội đường phố lớn nhất Brazil, ~5-6 ngày quanh mốc này"},
    {"name": "Consumer Day", "local_name": "Dia do Consumidor", "country": "Brazil", "tier": 2, "category": "shopping",
     "date_type": "fixed", "month": 3, "day": 15, "source": "https://calendarr.com/brasil/dia-mundial-do-consumidor"},
    {"name": "Good Friday", "local_name": "Sexta-feira Santa", "country": "Brazil", "tier": 2, "category": "official",
     "date_type": "easter_offset", "offset_days": -2, "source": "https://officeholidays.com/countries/brazil/2026"},
    {"name": "Tiradentes", "country": "Brazil", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 4, "day": 21, "source": "https://officeholidays.com/countries/brazil/2026"},
    {"name": "Labour Day", "local_name": "Dia do Trabalho", "country": "Brazil", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 5, "day": 1, "source": "https://officeholidays.com/countries/brazil/2026"},
    {"name": "Mother's Day", "local_name": "Dia das Mães", "country": "Brazil", "tier": 2, "category": "unofficial",
     "date_type": "nth_weekday", "month": 5, "weekday": 6, "nth": 2, "source": "https://nsctotal.com.br"},
    {"name": "Corpus Christi", "country": "Brazil", "tier": 2, "category": "official",
     "date_type": "easter_offset", "offset_days": 60, "source": "https://officeholidays.com/countries/brazil/2026"},
    {"name": "Valentine's Day (BR)", "local_name": "Dia dos Namorados", "country": "Brazil", "tier": 2,
     "category": "shopping", "date_type": "fixed", "month": 6, "day": 12,
     "source": "https://oficinadanet.com.br/curiosidades/62320", "note": "Ngày lễ tình nhân RIÊNG của Brazil, khác 14/2 quốc tế"},
    {"name": "Independence Day", "local_name": "Independência do Brasil", "country": "Brazil", "tier": 2,
     "category": "official", "date_type": "fixed", "month": 9, "day": 7,
     "source": "https://officeholidays.com/countries/brazil/2026"},
    {"name": "Father's Day", "local_name": "Dia dos Pais", "country": "Brazil", "tier": 2, "category": "unofficial",
     "date_type": "nth_weekday", "month": 8, "weekday": 6, "nth": 2, "source": "https://calendarr.com/brasil/dia-dos-pais"},
    {"name": "Children's Day / N. Sra. Aparecida", "country": "Brazil", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 10, "day": 12, "source": "https://oantagonista.com.br"},
    {"name": "Black Consciousness Day", "country": "Brazil", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 11, "day": 20, "source": "https://eskimo.travel/en/blog/brazil-public-holidays"},
    {"name": "Black Friday", "country": "Brazil", "tier": 2, "category": "shopping",
     "date_type": "nth_weekday", "month": 11, "weekday": 4, "nth": -1,
     "source": "https://relampagoofertas.com.br/home/blog/black-friday-2026-como-aproveitar.html"},
    {"name": "Christmas Day", "local_name": "Natal", "country": "Brazil", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 12, "day": 25, "source": "https://officeholidays.com/countries/brazil/2026"},

    # ---------------- MEXICO ----------------
    {"name": "Three Kings' Day", "local_name": "Día de Reyes", "country": "Mexico", "tier": 2, "category": "unofficial",
     "date_type": "fixed", "month": 1, "day": 6, "source": "https://informador.mx"},
    {"name": "Constitution Day", "local_name": "Día de la Constitución", "country": "Mexico", "tier": 2,
     "category": "official", "date_type": "nth_weekday", "month": 2, "weekday": 0, "nth": 1,
     "source": "https://eluniversal.com.mx/consultas/blog/rrhh/calendario-completo-de-dias-festivos-oficiales-2026-en-mexico"},
    {"name": "Valentine's Day", "country": "Mexico", "tier": 2, "category": "unofficial",
     "date_type": "fixed", "month": 2, "day": 14, "source": "https://en.wikipedia.org/wiki/Valentine%27s_Day"},
    {"name": "Benito Juárez's Birthday", "country": "Mexico", "tier": 2, "category": "official",
     "date_type": "nth_weekday", "month": 3, "weekday": 0, "nth": 3,
     "source": "https://eluniversal.com.mx/consultas/blog/rrhh/calendario-completo-de-dias-festivos-oficiales-2026-en-mexico"},
    {"name": "Labour Day", "local_name": "Día del Trabajo", "country": "Mexico", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 5, "day": 1,
     "source": "https://eluniversal.com.mx/consultas/blog/rrhh/calendario-completo-de-dias-festivos-oficiales-2026-en-mexico"},
    {"name": "Cinco de Mayo", "country": "Mexico", "tier": 2, "category": "unofficial",
     "date_type": "fixed", "month": 5, "day": 5, "source": "https://mediotiempo.com",
     "note": "Không phải ngày nghỉ lễ lao động chính thức, chỉ lớn ở Puebla + hải ngoại (đặc biệt tại Mỹ)"},
    {"name": "Mother's Day", "local_name": "Día de las Madres", "country": "Mexico", "tier": 2, "category": "unofficial",
     "date_type": "fixed", "month": 5, "day": 10, "source": "https://infobae.com",
     "note": "Cố định 10/5 hàng năm — khác Brazil (Chủ nhật thứ 2 của tháng 5)"},
    {"name": "Hot Sale", "country": "Mexico", "tier": 2, "category": "shopping",
     "date_type": "explicit", "date": "2026-05-25", "source": "https://record.com.mx",
     "note": "Sự kiện TMĐT do AMVO tổ chức, kéo dài ~9 ngày"},
    {"name": "Independence Day", "country": "Mexico", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 9, "day": 16,
     "source": "https://eluniversal.com.mx/consultas/blog/rrhh/calendario-completo-de-dias-festivos-oficiales-2026-en-mexico"},
    {"name": "Día de los Muertos", "country": "Mexico", "tier": 2, "category": "unofficial",
     "date_type": "fixed", "month": 11, "day": 1, "source": "https://calendariodemexico.com/dia-de-muertos-2026-mexico-fechas-vacaciones-tradicion",
     "note": "1-2/11, di sản UNESCO, nhiều trường/bang cho nghỉ dù không phải quốc lễ liên bang"},
    {"name": "Revolution Day", "country": "Mexico", "tier": 2, "category": "official",
     "date_type": "nth_weekday", "month": 11, "weekday": 0, "nth": 3,
     "source": "https://eluniversal.com.mx/consultas/blog/rrhh/calendario-completo-de-dias-festivos-oficiales-2026-en-mexico"},
    {"name": "El Buen Fin", "country": "Mexico", "tier": 2, "category": "shopping",
     "date_type": "explicit", "date": "2026-11-13", "source": "https://ambito.com/mexico/economia/el-buen-fin-2026-cuando-es-y-que-tiendas-participan-n6278030",
     "note": "\"Black Friday\" phiên bản Mexico, gắn với dịp Cách mạng — ngày kết thúc chưa thống nhất (13-17/11)"},
    {"name": "Virgen de Guadalupe Day", "country": "Mexico", "tier": 2, "category": "unofficial",
     "date_type": "fixed", "month": 12, "day": 12, "source": "https://record.com.mx"},
    {"name": "Christmas Day", "local_name": "Navidad", "country": "Mexico", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 12, "day": 25,
     "source": "https://eluniversal.com.mx/consultas/blog/rrhh/calendario-completo-de-dias-festivos-oficiales-2026-en-mexico"},

    # ---------------- INDONESIA ----------------
    {"name": "New Year's Day", "local_name": "Tahun Baru Masehi", "country": "Indonesia", "tier": 2,
     "category": "official", "date_type": "fixed", "month": 1, "day": 1,
     "source": "https://hari.co.id/en/public-holidays/2026"},
    {"name": "Isra Mi'raj", "country": "Indonesia", "tier": 2, "category": "official",
     "date_type": "explicit", "date": "2026-01-16", "source": "https://detik.com/sumbagsel/berita/d-8302366"},
    {"name": "Chinese New Year", "local_name": "Imlek", "country": "Indonesia", "tier": 2, "category": "official",
     "date_type": "explicit", "date": "2026-02-17", "source": "https://hari.co.id/en/public-holidays/2026"},
    {"name": "Ramadan Begins", "country": "Indonesia", "tier": 2, "category": "unofficial",
     "date_type": "explicit", "date": "2026-02-19",
     "source": "https://s3pendsains.fmipa.unesa.ac.id/post/pemerintah-tetapkan-1-ramadan-2026-1447-h-melalui-hasil-sidang-isbat",
     "note": "Không phải ngày nghỉ, nhưng mở đầu mùa chi tiêu lớn nhất năm (~80% người Indonesia), đỉnh điểm 10 ngày cuối trước Lebaran"},
    {"name": "Nyepi (Balinese New Year)", "country": "Indonesia", "tier": 2, "category": "official",
     "date_type": "explicit", "date": "2026-03-19", "source": "https://detik.com/sulsel/berita/d-8487935"},
    {"name": "Eid al-Fitr (Lebaran)", "country": "Indonesia", "tier": 2, "category": "official",
     "date_type": "explicit", "date": "2026-03-21",
     "source": "https://setneg.go.id/baca/index/pemerintah_tetapkan_1_syawal_1447_h_jatuh_pada_21_maret_2026",
     "note": "Kèm nghỉ bù nhiều ngày, tạo cả tuần nghỉ/về quê (mudik) — dịp quan trọng nhất năm ở Indonesia"},
    {"name": "Pancasila Day", "country": "Indonesia", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 6, "day": 1, "source": "https://hari.co.id/en/public-holidays/2026"},
    {"name": "Eid al-Adha", "country": "Indonesia", "tier": 2, "category": "official",
     "date_type": "explicit", "date": "2026-05-27", "source": "https://hari.co.id/en/public-holidays/2026"},
    {"name": "Islamic New Year", "country": "Indonesia", "tier": 2, "category": "official",
     "date_type": "explicit", "date": "2026-06-16", "source": "https://hari.co.id/en/public-holidays/2026"},
    {"name": "Independence Day", "local_name": "Hari Kemerdekaan", "country": "Indonesia", "tier": 2,
     "category": "official", "date_type": "fixed", "month": 8, "day": 17,
     "source": "https://hari.co.id/en/public-holidays/2026"},
    {"name": "Maulid Nabi Muhammad", "country": "Indonesia", "tier": 2, "category": "official",
     "date_type": "explicit", "date": "2026-08-25", "source": "https://hari.co.id/en/public-holidays/2026"},
    {"name": "National Batik Day", "local_name": "Hari Batik Nasional", "country": "Indonesia", "tier": 2,
     "category": "unofficial", "date_type": "fixed", "month": 10, "day": 2,
     "source": "https://en.wikipedia.org/wiki/Batik_Day"},
    {"name": "Youth Pledge Day", "local_name": "Sumpah Pemuda", "country": "Indonesia", "tier": 2,
     "category": "unofficial", "date_type": "fixed", "month": 10, "day": 28,
     "source": "https://indonesiayouthfoundation.org/sumpah-pemuda-day-a-youth-pledge-of-unity-and-national-identity"},
    {"name": "11.11 Sale", "country": "Indonesia", "tier": 2, "category": "shopping",
     "date_type": "fixed", "month": 11, "day": 11, "source": "https://jakartadaily.id"},
    {"name": "Harbolnas (12.12)", "country": "Indonesia", "tier": 2, "category": "shopping",
     "date_type": "fixed", "month": 12, "day": 12,
     "source": "https://idea.or.id/kegiatan/detail/harbolnas-idea-1212", "note": "\"National Online Shopping Day\", chính phủ hậu thuẫn"},
    {"name": "Christmas Day", "local_name": "Natal", "country": "Indonesia", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 12, "day": 25, "source": "https://detik.com/sulsel/berita/d-8487935"},

    # ---------------- PHILIPPINES ----------------
    {"name": "New Year's Day", "country": "Philippines", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 1, "day": 1, "source": "https://newsinfo.inquirer.net/2104754"},
    {"name": "Valentine's Day", "country": "Philippines", "tier": 2, "category": "unofficial",
     "date_type": "fixed", "month": 2, "day": 14, "source": "https://business.inquirer.net/505660"},
    {"name": "Eid'l Fitr", "country": "Philippines", "tier": 2, "category": "official",
     "date_type": "explicit", "date": "2026-03-20",
     "source": "https://pia.gov.ph/news/proclamation-no-1189-s-2026-declaring-friday-20-march-2026-a-regular-holiday-throughout-the-country-in-observance-of-eidl-fitr-feast-of-ramadhan"},
    {"name": "Maundy Thursday", "country": "Philippines", "tier": 2, "category": "official",
     "date_type": "easter_offset", "offset_days": -3, "source": "https://publicholidays.ph/easter"},
    {"name": "Good Friday", "country": "Philippines", "tier": 2, "category": "official",
     "date_type": "easter_offset", "offset_days": -2, "source": "https://publicholidays.ph/easter"},
    {"name": "Day of Valor", "local_name": "Araw ng Kagitingan", "country": "Philippines", "tier": 2,
     "category": "official", "date_type": "fixed", "month": 4, "day": 9,
     "source": "https://newsinfo.inquirer.net/2104754"},
    {"name": "Labor Day", "country": "Philippines", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 5, "day": 1, "source": "https://newsinfo.inquirer.net/2104754"},
    {"name": "Eid'l Adha", "country": "Philippines", "tier": 2, "category": "official",
     "date_type": "explicit", "date": "2026-05-27", "source": "https://lawphil.net/executive/proc/proc2026/proc_1264_2026.html"},
    {"name": "Independence Day", "country": "Philippines", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 6, "day": 12, "source": "https://newsinfo.inquirer.net/2104754"},
    {"name": "\"-Ber Months\" Christmas Season Start", "country": "Philippines", "tier": 2, "category": "unofficial",
     "date_type": "fixed", "month": 9, "day": 1,
     "source": "https://dhl.com/discover/en-ph/e-commerce-advice/e-commerce-best-practice/tips-to-prepare-for-the-ber-months",
     "note": "Mùa Giáng sinh dài nhất thế giới (Sept-Dec), nên bắt đầu chiến dịch từ đây"},
    {"name": "Ninoy Aquino Day", "country": "Philippines", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 8, "day": 21, "source": "https://newsinfo.inquirer.net/2104754"},
    {"name": "National Heroes Day", "country": "Philippines", "tier": 2, "category": "official",
     "date_type": "nth_weekday", "month": 8, "weekday": 0, "nth": -1, "source": "https://newsinfo.inquirer.net/2104754"},
    {"name": "All Saints' Day / Undas", "country": "Philippines", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 11, "day": 1, "source": "https://newsinfo.inquirer.net/2104754",
     "note": "Dịp về quê/thăm mộ lớn nhất năm ở Philippines"},
    {"name": "11.11 Sale", "country": "Philippines", "tier": 2, "category": "shopping",
     "date_type": "fixed", "month": 11, "day": 11, "source": "https://rappler.com/brandrap/lazada-ecommerce-shopping-promo-november-11-2025"},
    {"name": "Bonifacio Day", "country": "Philippines", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 11, "day": 30, "source": "https://newsinfo.inquirer.net/2104754"},
    {"name": "12.12 Sale", "country": "Philippines", "tier": 2, "category": "shopping",
     "date_type": "fixed", "month": 12, "day": 12, "source": "https://newsinfo.inquirer.net/2104754"},
    {"name": "Christmas Eve", "country": "Philippines", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 12, "day": 24, "source": "https://newsinfo.inquirer.net/2104754"},
    {"name": "Christmas Day", "country": "Philippines", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 12, "day": 25, "source": "https://newsinfo.inquirer.net/2104754"},
    {"name": "Rizal Day", "country": "Philippines", "tier": 2, "category": "official",
     "date_type": "fixed", "month": 12, "day": 30, "source": "https://newsinfo.inquirer.net/2104754"},
]


def _easter_sunday(year):
    """Chủ nhật Phục Sinh của năm `year` — dùng thuật toán "Anonymous
    Gregorian algorithm" (Meeus/Jones/Butcher), thuật toán TOÁN HỌC chuẩn,
    không phải tra bảng — tính đúng cho MỌI năm, không cần cập nhật tay.
    Nhiều ngày lễ Easter-based (Good Friday, Ascension, Pentecost, Corpus
    Christi, Carnaval Brazil...) đều tính được từ đây (date_type
    "easter_offset") thay vì phải lưu cứng từng năm như ngày âm lịch thật
    (Tết, Diwali, Eid...) — 2 loại lịch khác nhau, đừng nhầm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _nth_weekday_of_month(year, month, weekday, nth):
    """Ngày thứ `nth` có thứ trong tuần = `weekday` (0=Thứ 2) của `month`
    năm `year`. `nth` âm = đếm từ cuối tháng (-1 = cái cuối cùng)."""
    if nth > 0:
        d = date(year, month, 1)
        offset = (weekday - d.weekday()) % 7
        d += timedelta(days=offset + 7 * (nth - 1))
        return d
    # nth am: bat dau tu ngay cuoi thang, lui ve
    if month == 12:
        d = date(year, 12, 31)
    else:
        d = date(year, month + 1, 1) - timedelta(days=1)
    offset = (d.weekday() - weekday) % 7
    d -= timedelta(days=offset - 7 * (-nth - 1) if offset >= 7 * (-nth - 1) else offset)
    d -= timedelta(days=7 * (-nth - 1))
    return d


def next_occurrence(event, today):
    """Ngày diễn ra GẦN NHẤT (từ `today` trở đi) của 1 sự kiện — trả về
    None nếu là loại "explicit" mà ngày lưu sẵn đã trôi qua (cần cập nhật
    lại, xem needs_update)."""
    dtype = event["date_type"]
    if dtype == "fixed":
        for year in (today.year, today.year + 1):
            d = date(year, event["month"], event["day"])
            if d >= today:
                return d
    elif dtype == "nth_weekday":
        for year in (today.year, today.year + 1):
            d = _nth_weekday_of_month(year, event["month"], event["weekday"], event["nth"])
            d += timedelta(days=event.get("offset_days", 0))
            if d >= today:
                return d
    elif dtype == "easter_offset":
        for year in (today.year, today.year + 1):
            d = _easter_sunday(year) + timedelta(days=event["offset_days"])
            if d >= today:
                return d
    elif dtype == "explicit":
        d = date.fromisoformat(event["date"])
        if d >= today:
            return d
        return None
    return None


def needs_update(event, today):
    """True nếu đây là sự kiện "explicit" (âm lịch/tôn giáo) mà ngày lưu
    sẵn đã trôi qua — cần vào tìm lại ngày kỳ tới + cập nhật source."""
    return event["date_type"] == "explicit" and date.fromisoformat(event["date"]) < today


def upcoming_events(today=None, countries=None, tiers=None, categories=None, limit=None):
    """Danh sách sự kiện sắp tới, sắp xếp theo ngày gần nhất — lọc được
    theo quốc gia/tier/loại. `today` mặc định là hôm nay thật (truyền vào
    khi cần test với 1 ngày cố định)."""
    if today is None:
        today = date.today()
    rows = []
    for ev in EVENTS:
        if countries and ev["country"] not in countries:
            continue
        if tiers and ev["tier"] not in tiers:
            continue
        if categories and ev["category"] not in categories:
            continue
        d = next_occurrence(ev, today)
        if d is None:
            continue
        rows.append((d, ev))
    rows.sort(key=lambda r: r[0])
    if limit:
        rows = rows[:limit]
    return rows
