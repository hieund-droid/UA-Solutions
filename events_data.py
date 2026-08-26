#!/usr/bin/env python3
"""
events_data.py — Danh sách ngày lễ/sự kiện theo quốc gia, phục vụ team UA
biết trước "sắp tới có gì" để chuẩn bị ads (đổi outro theo mùa, tăng ngân
sách trước các dịp lớn, v.v.).

CHỈ đưa vào đây những mục ĐÃ CÓ NGUỒN THẬT kiểm chứng được (source field —
link chính phủ/Wikipedia có trích dẫn/trang tin uy tín) — không tự bịa ngày
theo trí nhớ. Nếu không tìm được nguồn đáng tin cho 1 ngày nào đó, THÀ BỎ
QUA còn hơn đưa vào sai (giống triết lý "an toàn hơn đoán liều" của
outro_core.py).

Cấu trúc 1 sự kiện:
    {
        "name": "Tên tiếng Anh",              # hiển thị chính
        "local_name": "Tên bản địa" | None,    # tuỳ chọn, hiển thị kèm
        "countries": ["US", "Canada", ...],    # DANH SÁCH mã quốc gia (xem
        # COUNTRIES) — 1 sự kiện có thể diễn ra ở NHIỀU nước cùng lúc (vd
        # New Year's Day, Christmas Day) — gộp lại 1 mục duy nhất thay vì
        # lặp lại từng nước riêng (đỡ rối danh sách). Tier suy ra TỰ ĐỘNG từ
        # COUNTRIES cho từng nước trong danh sách (xem event_tiers()), không
        # lưu cứng field "tier" riêng — tránh lệch dữ liệu.
        "category": "official",                # official | unofficial
        "date_type": "fixed" | "nth_weekday" | "explicit" | "easter_offset",
        # fixed: có "month", "day" cố định hàng năm (vd Giáng sinh 25/12).
        # nth_weekday: có "month", "weekday" (0=Thứ 2...6=CN), "nth" (1-5,
        #   âm để đếm từ cuối tháng vd -1 = thứ cuối cùng), "offset_days"
        #   (tuỳ chọn, để tính ngày LIỀN SAU/TRƯỚC mốc đó).
        # easter_offset: có "offset_days" tính từ Chủ nhật Phục Sinh (xem
        #   _easter_sunday) — Good Friday, Easter Monday, Ascension...
        # explicit: ngày ÂM LỊCH/tôn giáo đổi theo năm, KHÔNG tính được bằng
        #   công thức (Tết, Diwali, Eid, Chuseok...) — lưu sẵn ngày CỤ THỂ
        #   lần diễn ra GẦN NHẤT đã kiểm chứng được nguồn, dạng "YYYY-MM-DD"
        #   ở field "date". Cần CẬP NHẬT LẠI mỗi năm khi ngày đó trôi qua —
        #   xem hàm needs_update() bên dưới để tool tự cảnh báo mục nào cũ.
        "source": "https://...",               # bắt buộc — link đã kiểm chứng
        # (mục gộp nhiều nước: chọn 1 nguồn đại diện — thường là Wikipedia
        # nếu có, vì đây là kiến thức phổ quát/đã được xác nhận rộng rãi,
        # không phải nguồn ít tin cậy hơn).
        "note": "Ghi chú thêm (tuỳ chọn)",
        # mục gộp nhiều nước: CHỈ giữ note nếu TẤT CẢ các nước trong nhóm
        # đều có note giống hệt nhau, nếu khác nhau thì bỏ (tránh áp đặt
        # ghi chú của 1 nước lên cả nhóm).
    }

LƯU Ý loại "shopping" (sự kiện mua sắm — Black Friday, Cyber Monday, 11.11,
El Buen Fin...) ĐÃ BỊ BỎ theo yêu cầu thực tế (2026-08-27) — team UA thấy
không cần theo dõi riêng loại này. Nếu cần lại sau này, xem git history của
file này để khôi phục dữ liệu cũ.
"""

from datetime import date, timedelta

COUNTRIES = {
    "US": ("United States", 1), "UK": ("United Kingdom", 1), "Canada": ("Canada", 1),
    "Australia": ("Australia", 1), "Germany": ("Germany", 1), "France": ("France", 1),
    "India": ("India", 2), "Brazil": ("Brazil", 2), "Mexico": ("Mexico", 2),
    "Indonesia": ("Indonesia", 2), "Philippines": ("Philippines", 2),
}

CATEGORY_LABELS = {
    "official": "Lễ chính thức", "unofficial": "Không chính thức",
}

# Cờ quốc gia — chỉ để hiển thị cho dễ quét nhanh bằng mắt, không ảnh hưởng
# logic lọc/tính ngày.
COUNTRY_FLAGS = {
    "US": "🇺🇸", "UK": "🇬🇧", "Canada": "🇨🇦", "Australia": "🇦🇺", "Germany": "🇩🇪",
    "France": "🇫🇷", "India": "🇮🇳", "Brazil": "🇧🇷",
    "Mexico": "🇲🇽", "Indonesia": "🇮🇩", "Philippines": "🇵🇭",
}

# Dữ liệu bên dưới lấy từ đợt nghiên cứu qua web thật (2026-08-26, bổ sung
# 2026-08-27 khi gộp sự kiện trùng nhiều nước — 2 mục còn thiếu, New Year's
# Day/Mexico và Christmas Day/India, đã kiểm chứng nguồn thêm lúc gộp — và mở
# rộng thêm 1 đợt lớn cùng ngày 2026-08-27, 5 Agent nghiên cứu song song theo
# nhóm quốc gia, tổng 44 sự kiện MỚI + 7 sự kiện gộp thêm nước vào mục đã có
# sẵn, tất cả đều đã qua WebSearch/WebFetch kiểm chứng nguồn thật, không suy
# đoán theo trí nhớ, xem khối "BO SUNG NGHIEN CUU 2026-08-27" cuối EVENTS) —
# mỗi mục có "source" là link đã thực sự tra cứu được.
#
# date_type="explicit" (ngày âm lịch/tôn giáo/lịch bán lẻ tự đặt — Tết,
# Diwali, Eid, Nyepi...) SẼ CŨ DẦN theo thời gian — needs_update() tự phát
# hiện mục nào đã qua ngày lưu sẵn để cảnh báo cập nhật lại, xem
# render_events() trong app.py.
#
# 2026-08-27, sau đợt mở rộng: BỎ HẲN Japan/South Korea khỏi COUNTRIES/
# COUNTRY_FLAGS/EVENTS theo yêu cầu thực tế — 28 sự kiện chỉ-riêng-2-nước-này
# bị xoá hẳn (không phải ẩn), các mục gộp nhiều nước (New Year's Day,
# Christmas Day, Valentine's Day...) chỉ bỏ bớt 2 nước này khỏi "countries",
# vẫn giữ các nước còn lại. Nếu cần lại, xem git history.
EVENTS = [
    {"name": "New Year's Day", "countries": ['US', 'UK', 'Canada', 'Australia', 'Germany', 'France', 'Brazil', 'Mexico', 'Indonesia', 'Philippines'], "category": 'official', "date_type": 'fixed', "month": 1, "day": 1, "source": 'https://remitly.com/blog/lifestyle-culture/us-federal-holidays'},
    {"name": 'Martin Luther King Jr. Day', "countries": ['US'], "category": 'official', "date_type": 'nth_weekday', "month": 1, "weekday": 0, "nth": 3, "source": 'https://remitly.com/blog/lifestyle-culture/us-federal-holidays'},
    {"name": 'Presidents Day', "countries": ['US'], "category": 'official', "date_type": 'nth_weekday', "month": 2, "weekday": 0, "nth": 3, "source": 'https://remitly.com/blog/lifestyle-culture/us-federal-holidays'},
    {"name": "Valentine's Day", "countries": ['US', 'UK', 'Canada', 'Australia', 'India', 'Mexico', 'Philippines', 'Germany', 'France'], "category": 'unofficial', "date_type": 'fixed', "month": 2, "day": 14, "source": 'https://en.wikipedia.org/wiki/Valentine%27s_Day'},
    {"name": "Galentine's Day", "countries": ['US'], "category": 'unofficial', "date_type": 'fixed', "month": 2, "day": 13, "source": 'https://en.wikipedia.org/wiki/Galentine%27s_Day_(observance)', "note": 'Viral từ phim Parks and Recreation, được thương mại hoá rộng rãi từ ~2017-2020'},
    {"name": 'Super Bowl Sunday', "countries": ['US'], "category": 'unofficial', "date_type": 'explicit', "date": '2026-02-08', "source": 'https://sports.yahoo.com', "note": 'Ngày do NFL ấn định hàng năm, không theo quy tắc cố định'},
    {"name": 'Memorial Day', "countries": ['US'], "category": 'official', "date_type": 'nth_weekday', "month": 5, "weekday": 0, "nth": -1, "source": 'https://remitly.com/blog/lifestyle-culture/us-federal-holidays'},
    {"name": 'Juneteenth', "countries": ['US'], "category": 'official', "date_type": 'fixed', "month": 6, "day": 19, "source": 'https://timeanddate.com/holidays/us/juneteenth'},
    {"name": 'Independence Day', "countries": ['US'], "category": 'official', "date_type": 'fixed', "month": 7, "day": 4, "source": 'https://remitly.com/blog/lifestyle-culture/us-federal-holidays'},
    {"name": 'Labor Day', "local_name": 'Labour Day', "countries": ['US', 'Canada'], "category": 'official', "date_type": 'nth_weekday', "month": 9, "weekday": 0, "nth": 1, "source": 'https://remitly.com/blog/lifestyle-culture/us-federal-holidays'},
    {"name": 'Halloween', "countries": ['US', 'UK', 'Canada', 'Australia', 'Germany', 'France'], "category": 'unofficial', "date_type": 'fixed', "month": 10, "day": 31, "source": 'https://en.wikipedia.org/wiki/Halloween'},
    {"name": 'Thanksgiving Day', "countries": ['US'], "category": 'official', "date_type": 'nth_weekday', "month": 11, "weekday": 3, "nth": 4, "source": 'https://remitly.com/blog/lifestyle-culture/us-federal-holidays'},
    {"name": 'Christmas Day', "countries": ['US', 'UK', 'Canada', 'Australia', 'Germany', 'France', 'India', 'Brazil', 'Mexico', 'Indonesia', 'Philippines'], "category": 'official', "date_type": 'fixed', "month": 12, "day": 25, "source": 'https://remitly.com/blog/lifestyle-culture/us-federal-holidays'},
    {"name": 'Mothering Sunday', "countries": ['UK'], "category": 'unofficial', "date_type": 'easter_offset', "offset_days": -21, "source": 'https://awarenessdays.com/awareness-days-calendar/mothers-day-uk'},
    {"name": 'Good Friday', "countries": ['UK', 'Canada', 'Australia', 'Germany', 'Brazil', 'Philippines', 'Indonesia'], "category": 'official', "date_type": 'easter_offset', "offset_days": -2, "source": 'https://time-and-date.uk.com/uk-bank-holidays-2026'},
    {"name": 'Easter Monday', "countries": ['UK', 'Australia', 'Germany', 'France'], "category": 'official', "date_type": 'easter_offset', "offset_days": 1, "source": 'https://time-and-date.uk.com/uk-bank-holidays-2026'},
    {"name": 'Early May Bank Holiday', "countries": ['UK'], "category": 'official', "date_type": 'nth_weekday', "month": 5, "weekday": 0, "nth": 1, "source": 'https://time-and-date.uk.com/uk-bank-holidays-2026'},
    {"name": 'Spring Bank Holiday', "countries": ['UK'], "category": 'official', "date_type": 'nth_weekday', "month": 5, "weekday": 0, "nth": -1, "source": 'https://time-and-date.uk.com/uk-bank-holidays-2026'},
    {"name": "Father's Day", "countries": ['UK', 'Canada', 'France', 'US'], "category": 'unofficial', "date_type": 'nth_weekday', "month": 6, "weekday": 6, "nth": 3, "source": 'https://timeanddate.com/holidays/uk/father-day'},
    {"name": 'Summer Bank Holiday', "countries": ['UK'], "category": 'official', "date_type": 'nth_weekday', "month": 8, "weekday": 0, "nth": -1, "source": 'https://time-and-date.uk.com/uk-bank-holidays-2026'},
    {"name": 'Boxing Day', "countries": ['UK', 'Canada', 'Germany'], "category": 'official', "date_type": 'fixed', "month": 12, "day": 26, "source": 'https://x.com/GOVUK/status/2007087899888746644'},
    {"name": 'Victoria Day', "countries": ['Canada'], "category": 'official', "date_type": 'explicit', "date": '2026-05-18', "source": 'https://remitly.com/blog/en-ca/lifestyle-and-culture/federal-statutory-holidays-in-canada-calendar', "note": 'Quy tắc: thứ Hai liền TRƯỚC ngày 25/5 — cần cập nhật tay mỗi năm'},
    {"name": "Mother's Day", "countries": ['Canada', 'Australia', 'Germany', 'Brazil', 'US'], "category": 'unofficial', "date_type": 'nth_weekday', "month": 5, "weekday": 6, "nth": 2, "source": 'https://twinkl.com/event/mothers-day-canada-2026'},
    {"name": 'Canada Day', "countries": ['Canada'], "category": 'official', "date_type": 'fixed', "month": 7, "day": 1, "source": 'https://remitly.com/blog/en-ca/lifestyle-and-culture/federal-statutory-holidays-in-canada-calendar'},
    {"name": 'National Day for Truth and Reconciliation', "countries": ['Canada'], "category": 'official', "date_type": 'fixed', "month": 9, "day": 30, "source": 'https://canada.ca/en/canadian-heritage/campaigns/national-day-truth-reconciliation.html', "note": 'Chỉ bắt buộc nghỉ với lao động thuộc quản lý liên bang + 1 số tỉnh bang, không toàn quốc'},
    {"name": 'Thanksgiving (Canada)', "countries": ['Canada'], "category": 'official', "date_type": 'nth_weekday', "month": 10, "weekday": 0, "nth": 2, "source": 'https://remitly.com/blog/en-ca/lifestyle-and-culture/federal-statutory-holidays-in-canada-calendar'},
    {"name": 'Rose Monday', "local_name": 'Rosenmontag', "countries": ['Germany'], "category": 'unofficial', "date_type": 'easter_offset', "offset_days": -48, "source": 'https://cute-calendar.com', "note": 'Chỉ nghỉ thực tế ở vùng Rhineland (Köln, Düsseldorf, Bonn, Mainz)'},
    {"name": 'Labour Day', "countries": ['Germany', 'France', 'Brazil', 'Mexico', 'Philippines'], "category": 'official', "date_type": 'fixed', "month": 5, "day": 1, "source": 'https://publicholidays.de/2026-dates', "note": 'Philippines gọi là "Labor Day" (chính tả Mỹ) — cùng "Ngày Quốc tế Lao động"'},
    {"name": 'Ascension Day', "countries": ['Germany', 'France'], "category": 'official', "date_type": 'easter_offset', "offset_days": 39, "source": 'https://publicholidays.de/2026-dates'},
    {"name": 'Whit Monday', "countries": ['Germany', 'France'], "category": 'official', "date_type": 'easter_offset', "offset_days": 50, "source": 'https://publicholidays.de/2026-dates'},
    {"name": 'German Unity Day', "local_name": 'Tag der Deutschen Einheit', "countries": ['Germany'], "category": 'official', "date_type": 'fixed', "month": 10, "day": 3, "source": 'https://publicholidays.de/2026-dates'},
    {"name": 'Reformation Day', "local_name": 'Reformationstag', "countries": ['Germany'], "category": 'official', "date_type": 'fixed', "month": 10, "day": 31, "source": 'https://ruhrnachrichten.de', "note": 'Chỉ 9/16 bang (không có ở Bayern, Berlin, NRW, Hesse...)'},
    {"name": 'Victory Day 1945', "local_name": 'Fête de la Victoire', "countries": ['France'], "category": 'official', "date_type": 'fixed', "month": 5, "day": 8, "source": 'https://franceinfo.fr'},
    {"name": "Mother's Day", "local_name": 'Fête des Mères', "countries": ['France'], "category": 'unofficial', "date_type": 'nth_weekday', "month": 5, "weekday": 6, "nth": -1, "source": 'https://icalendrier.fr'},
    {"name": 'Bastille Day', "local_name": 'Fête Nationale', "countries": ['France'], "category": 'official', "date_type": 'fixed', "month": 7, "day": 14, "source": 'https://franceinfo.fr'},
    {"name": 'Assumption Day', "local_name": 'Assomption', "countries": ['France'], "category": 'official', "date_type": 'fixed', "month": 8, "day": 15, "source": 'https://franceinfo.fr'},
    {"name": 'Back-to-school', "local_name": 'Rentrée scolaire', "countries": ['France'], "category": 'unofficial', "date_type": 'fixed', "month": 9, "day": 1, "source": 'https://info.gouv.fr', "note": 'Cao điểm mua sắm đồ dùng học tập'},
    {"name": "All Saints' Day", "local_name": 'Undas', "countries": ['France', 'Philippines'], "category": 'official', "date_type": 'fixed', "month": 11, "day": 1, "source": 'https://franceinfo.fr', "note": 'Undas — tên gọi dân gian ở Philippines, dịp về quê/thăm mộ lớn nhất năm ở đó'},
    {"name": 'Beaujolais Nouveau Day', "countries": ['France'], "category": 'unofficial', "date_type": 'nth_weekday', "month": 11, "weekday": 3, "nth": 3, "source": 'https://nationaltoday.com/beaujolais-nouveau-day'},
    {"name": 'Australia Day', "countries": ['Australia'], "category": 'official', "date_type": 'fixed', "month": 1, "day": 26, "source": 'https://fairwork.gov.au/employment-conditions/public-holidays/2026-public-holidays'},
    {"name": 'Anzac Day', "countries": ['Australia'], "category": 'official', "date_type": 'fixed', "month": 4, "day": 25, "source": 'https://fairwork.gov.au/employment-conditions/public-holidays/2026-public-holidays'},
    {"name": "Father's Day (Australia)", "countries": ['Australia'], "category": 'unofficial', "date_type": 'nth_weekday', "month": 9, "weekday": 6, "nth": 1, "source": 'https://manofmany.com/culture/fathers-day-australia', "note": 'Khác Mỹ/UK (tháng 6) — Úc là Chủ nhật đầu tháng 9'},
    {"name": 'Melbourne Cup Day (Victoria)', "countries": ['Australia'], "category": 'official', "date_type": 'nth_weekday', "month": 11, "weekday": 1, "nth": 1, "source": 'https://publicholidays.com.au/melbourne-cup-day', "note": 'Chỉ nghỉ ở bang Victoria, nhưng cả nước quan tâm (đua ngựa/cá cược lớn)'},
    {"name": 'Makar Sankranti', "countries": ['India'], "category": 'official', "date_type": 'fixed', "month": 1, "day": 14, "source": 'https://indiatvnews.com/lifestyle/spirituality/makar-sankranti-2026-date-january-14-or-15-muhurat-explained-2026-01-14-1025793'},
    {"name": 'Republic Day', "countries": ['India'], "category": 'official', "date_type": 'fixed', "month": 1, "day": 26, "source": 'https://cleartax.in/s/government-holidays-2026'},
    {"name": 'Holi', "countries": ['India'], "category": 'official', "date_type": 'explicit', "date": '2026-03-04', "source": 'https://cleartax.in/s/government-holidays-2026'},
    {"name": 'Eid al-Fitr', "local_name": 'Lebaran', "countries": ['India', 'Indonesia'], "category": 'official', "date_type": 'explicit', "date": '2026-03-21', "source": 'https://cleartax.in/s/government-holidays-2026', "note": 'Lebaran — tên gọi ở Indonesia. Philippines quan sát trăng riêng, ra ngày 20/3 (lệch 1 ngày) nên KHÔNG gộp vào đây'},
    {"name": 'Eid al-Adha', "countries": ['India', 'Indonesia', 'Philippines'], "category": 'official', "date_type": 'explicit', "date": '2026-05-27', "source": 'https://cleartax.in/s/government-holidays-2026', "note": 'Ấn Độ gọi là "Bakrid", Philippines gọi là "Eid\'l Adha" — cùng 1 lễ Hồi giáo, ngày đã khớp giữa 3 nước'},
    {"name": 'Independence Day', "countries": ['India'], "category": 'official', "date_type": 'fixed', "month": 8, "day": 15, "source": 'https://cleartax.in/s/government-holidays-2026'},
    {"name": 'Friendship Day (India)', "countries": ['India'], "category": 'unofficial', "date_type": 'nth_weekday', "month": 8, "weekday": 6, "nth": 1, "source": 'https://lovelydesign.in/blog/friendship-day-2026-date-history-why-august-first-sunday', "note": 'Quy ước riêng của Ấn Độ (Chủ nhật đầu tháng 8), phổ biến từ phim Bollywood 1998'},
    {"name": 'Raksha Bandhan', "countries": ['India'], "category": 'unofficial', "date_type": 'explicit', "date": '2026-08-28', "source": 'https://rakhisale.com/when-is-rakhi.asp', "note": 'Không phải quốc lễ nhưng dịp tặng quà anh chị em lớn'},
    {"name": 'Ganesh Chaturthi', "countries": ['India'], "category": 'unofficial', "date_type": 'explicit', "date": '2026-09-14', "source": 'https://imagicaaworld.com/blog/ganesh-chaturthi-2026', "note": 'Lớn nhất ở Maharashtra/miền Tây/Nam Ấn Độ'},
    {"name": 'Gandhi Jayanti', "countries": ['India'], "category": 'official', "date_type": 'fixed', "month": 10, "day": 2, "source": 'https://cleartax.in/s/government-holidays-2026'},
    {"name": 'Dussehra', "countries": ['India'], "category": 'official', "date_type": 'explicit', "date": '2026-10-20', "source": 'https://cleartax.in/s/government-holidays-2026'},
    {"name": 'Karwa Chauth', "countries": ['India'], "category": 'unofficial', "date_type": 'explicit', "date": '2026-10-29', "source": 'https://winni.in/article/when-is-karwa-chauth', "note": 'Không phải quốc lễ nhưng dịp mua trang sức/thời trang lớn'},
    {"name": 'Diwali', "countries": ['India'], "category": 'official', "date_type": 'explicit', "date": '2026-11-08', "source": 'https://publicholidays.in/diwali-deepavali', "note": 'Dịp mua sắm/biếu quà lớn nhất năm ở Ấn Độ'},
    {"name": 'Carnaval', "countries": ['Brazil'], "category": 'official', "date_type": 'easter_offset', "offset_days": -47, "source": 'https://calendarr.com/brasil/carnaval', "note": 'Cả tuần lễ hội đường phố lớn nhất Brazil, ~5-6 ngày quanh mốc này'},
    {"name": 'Tiradentes', "countries": ['Brazil'], "category": 'official', "date_type": 'fixed', "month": 4, "day": 21, "source": 'https://officeholidays.com/countries/brazil/2026'},
    {"name": 'Corpus Christi', "countries": ['Brazil', 'Germany'], "category": 'official', "date_type": 'easter_offset', "offset_days": 60, "source": 'https://officeholidays.com/countries/brazil/2026'},
    {"name": 'Independence Day', "local_name": 'Independência do Brasil', "countries": ['Brazil'], "category": 'official', "date_type": 'fixed', "month": 9, "day": 7, "source": 'https://officeholidays.com/countries/brazil/2026'},
    {"name": "Father's Day", "local_name": 'Dia dos Pais', "countries": ['Brazil'], "category": 'unofficial', "date_type": 'nth_weekday', "month": 8, "weekday": 6, "nth": 2, "source": 'https://calendarr.com/brasil/dia-dos-pais'},
    {"name": "Children's Day / N. Sra. Aparecida", "countries": ['Brazil'], "category": 'official', "date_type": 'fixed', "month": 10, "day": 12, "source": 'https://oantagonista.com.br'},
    {"name": 'Black Consciousness Day', "countries": ['Brazil'], "category": 'official', "date_type": 'fixed', "month": 11, "day": 20, "source": 'https://eskimo.travel/en/blog/brazil-public-holidays'},
    {"name": 'Epiphany', "local_name": 'Día de Reyes / Épiphanie', "countries": ['France', 'Mexico'], "category": 'unofficial', "date_type": 'fixed', "month": 1, "day": 6, "source": 'https://informador.mx', "note": 'Lễ Hiển Linh (Epiphany) — Mexico gọi "Three Kings\' Day"/"Día de Reyes", Pháp gọi "Épiphanie"'},
    {"name": 'Constitution Day', "local_name": 'Día de la Constitución', "countries": ['Mexico'], "category": 'official', "date_type": 'nth_weekday', "month": 2, "weekday": 0, "nth": 1, "source": 'https://eluniversal.com.mx/consultas/blog/rrhh/calendario-completo-de-dias-festivos-oficiales-2026-en-mexico'},
    {"name": "Benito Juárez's Birthday", "countries": ['Mexico'], "category": 'official', "date_type": 'nth_weekday', "month": 3, "weekday": 0, "nth": 3, "source": 'https://eluniversal.com.mx/consultas/blog/rrhh/calendario-completo-de-dias-festivos-oficiales-2026-en-mexico'},
    {"name": 'Cinco de Mayo', "countries": ['Mexico', 'US'], "category": 'unofficial', "date_type": 'fixed', "month": 5, "day": 5, "source": 'https://mediotiempo.com', "note": 'Không phải ngày nghỉ lễ lao động chính thức, chỉ lớn ở Puebla + hải ngoại (đặc biệt tại Mỹ)'},
    {"name": "Mother's Day", "local_name": 'Día de las Madres', "countries": ['Mexico'], "category": 'unofficial', "date_type": 'fixed', "month": 5, "day": 10, "source": 'https://infobae.com', "note": 'Cố định 10/5 hàng năm — khác Brazil (Chủ nhật thứ 2 của tháng 5)'},
    {"name": 'Independence Day', "countries": ['Mexico'], "category": 'official', "date_type": 'fixed', "month": 9, "day": 16, "source": 'https://eluniversal.com.mx/consultas/blog/rrhh/calendario-completo-de-dias-festivos-oficiales-2026-en-mexico'},
    {"name": 'Día de los Muertos', "countries": ['Mexico'], "category": 'unofficial', "date_type": 'fixed', "month": 11, "day": 1, "source": 'https://calendariodemexico.com/dia-de-muertos-2026-mexico-fechas-vacaciones-tradicion', "note": '1-2/11, di sản UNESCO, nhiều trường/bang cho nghỉ dù không phải quốc lễ liên bang'},
    {"name": 'Revolution Day', "countries": ['Mexico'], "category": 'official', "date_type": 'nth_weekday', "month": 11, "weekday": 0, "nth": 3, "source": 'https://eluniversal.com.mx/consultas/blog/rrhh/calendario-completo-de-dias-festivos-oficiales-2026-en-mexico'},
    {"name": 'Virgen de Guadalupe Day', "countries": ['Mexico'], "category": 'unofficial', "date_type": 'fixed', "month": 12, "day": 12, "source": 'https://record.com.mx'},
    {"name": "Isra Mi'raj", "countries": ['Indonesia'], "category": 'official', "date_type": 'explicit', "date": '2026-01-16', "source": 'https://detik.com/sumbagsel/berita/d-8302366'},
    {"name": 'Chinese New Year', "local_name": 'Imlek', "countries": ['Indonesia'], "category": 'official', "date_type": 'explicit', "date": '2026-02-17', "source": 'https://hari.co.id/en/public-holidays/2026'},
    {"name": 'Ramadan Begins', "countries": ['Indonesia'], "category": 'unofficial', "date_type": 'explicit', "date": '2026-02-19', "source": 'https://s3pendsains.fmipa.unesa.ac.id/post/pemerintah-tetapkan-1-ramadan-2026-1447-h-melalui-hasil-sidang-isbat', "note": 'Không phải ngày nghỉ, nhưng mở đầu mùa chi tiêu lớn nhất năm (~80% người Indonesia), đỉnh điểm 10 ngày cuối trước Lebaran'},
    {"name": 'Nyepi (Balinese New Year)', "countries": ['Indonesia'], "category": 'official', "date_type": 'explicit', "date": '2026-03-19', "source": 'https://detik.com/sulsel/berita/d-8487935'},
    {"name": 'Pancasila Day', "countries": ['Indonesia'], "category": 'official', "date_type": 'fixed', "month": 6, "day": 1, "source": 'https://hari.co.id/en/public-holidays/2026'},
    {"name": 'Islamic New Year', "countries": ['Indonesia'], "category": 'official', "date_type": 'explicit', "date": '2026-06-16', "source": 'https://hari.co.id/en/public-holidays/2026'},
    {"name": 'Independence Day', "local_name": 'Hari Kemerdekaan', "countries": ['Indonesia'], "category": 'official', "date_type": 'fixed', "month": 8, "day": 17, "source": 'https://hari.co.id/en/public-holidays/2026'},
    {"name": 'Maulid Nabi Muhammad', "countries": ['Indonesia'], "category": 'official', "date_type": 'explicit', "date": '2026-08-25', "source": 'https://hari.co.id/en/public-holidays/2026'},
    {"name": 'National Batik Day', "local_name": 'Hari Batik Nasional', "countries": ['Indonesia'], "category": 'unofficial', "date_type": 'fixed', "month": 10, "day": 2, "source": 'https://en.wikipedia.org/wiki/Batik_Day'},
    {"name": 'Youth Pledge Day', "local_name": 'Sumpah Pemuda', "countries": ['Indonesia'], "category": 'unofficial', "date_type": 'fixed', "month": 10, "day": 28, "source": 'https://indonesiayouthfoundation.org/sumpah-pemuda-day-a-youth-pledge-of-unity-and-national-identity'},
    {"name": "Eid'l Fitr", "countries": ['Philippines'], "category": 'official', "date_type": 'explicit', "date": '2026-03-20', "source": 'https://pia.gov.ph/news/proclamation-no-1189-s-2026-declaring-friday-20-march-2026-a-regular-holiday-throughout-the-country-in-observance-of-eidl-fitr-feast-of-ramadhan'},
    {"name": 'Maundy Thursday', "countries": ['Philippines'], "category": 'official', "date_type": 'easter_offset', "offset_days": -3, "source": 'https://publicholidays.ph/easter'},
    {"name": 'Day of Valor', "local_name": 'Araw ng Kagitingan', "countries": ['Philippines'], "category": 'official', "date_type": 'fixed', "month": 4, "day": 9, "source": 'https://newsinfo.inquirer.net/2104754'},
    {"name": 'Independence Day', "countries": ['Philippines'], "category": 'official', "date_type": 'fixed', "month": 6, "day": 12, "source": 'https://newsinfo.inquirer.net/2104754'},
    {"name": '"-Ber Months" Christmas Season Start', "countries": ['Philippines'], "category": 'unofficial', "date_type": 'fixed', "month": 9, "day": 1, "source": 'https://dhl.com/discover/en-ph/e-commerce-advice/e-commerce-best-practice/tips-to-prepare-for-the-ber-months', "note": 'Mùa Giáng sinh dài nhất thế giới (Sept-Dec), nên bắt đầu chiến dịch từ đây'},
    {"name": 'Ninoy Aquino Day', "countries": ['Philippines'], "category": 'official', "date_type": 'fixed', "month": 8, "day": 21, "source": 'https://newsinfo.inquirer.net/2104754'},
    {"name": 'National Heroes Day', "countries": ['Philippines'], "category": 'official', "date_type": 'nth_weekday', "month": 8, "weekday": 0, "nth": -1, "source": 'https://newsinfo.inquirer.net/2104754'},
    {"name": 'Bonifacio Day', "countries": ['Philippines'], "category": 'official', "date_type": 'fixed', "month": 11, "day": 30, "source": 'https://newsinfo.inquirer.net/2104754'},
    {"name": 'Christmas Eve', "countries": ['Philippines'], "category": 'official', "date_type": 'fixed', "month": 12, "day": 24, "source": 'https://newsinfo.inquirer.net/2104754'},
    {"name": 'Rizal Day', "countries": ['Philippines'], "category": 'official', "date_type": 'fixed', "month": 12, "day": 30, "source": 'https://newsinfo.inquirer.net/2104754'},
    {"name": "St. Patrick's Day", "countries": ['US', 'Canada'], "category": 'unofficial', "date_type": 'fixed', "month": 3, "day": 17, "source": "https://en.wikipedia.org/wiki/Saint_Patrick's_Day_in_the_United_States"},
    {"name": 'Armistice Day', "countries": ['US', 'Canada', 'France'], "category": 'official', "date_type": 'fixed', "month": 11, "day": 11, "source": 'https://en.wikipedia.org/wiki/Veterans_Day', "note": 'Gọi là "Veterans Day" ở Mỹ, "Remembrance Day" ở Canada — cùng kỷ niệm ngày đình chiến Thế chiến I (11/11/1918)'},
    {"name": "St Patrick's Day (Northern Ireland)", "countries": ['UK'], "category": 'official', "date_type": 'fixed', "month": 3, "day": 17, "source": 'https://x.com/GOVUK/status/2007088068654755942', "note": 'Chỉ là bank holiday ở Bắc Ireland — Anh/Scotland/Wales vẫn là ngày làm việc bình thường'},
    {"name": "St Andrew's Day", "countries": ['UK'], "category": 'official', "date_type": 'fixed', "month": 11, "day": 30, "source": 'https://www.legislation.gov.uk/asp/2007/2/section/1/notes', "note": 'Chỉ là bank holiday ở Scotland (quốc lễ Scotland)'},
    {"name": 'Bonfire Night', "local_name": 'Guy Fawkes Night', "countries": ['UK'], "category": 'unofficial', "date_type": 'fixed', "month": 11, "day": 5, "source": 'https://en.wikipedia.org/wiki/Guy_Fawkes_Night', "note": 'Không phải ngày nghỉ lễ nhưng truyền thống 400 năm khắp UK (pháo hoa, đốt lửa trại)'},
    {"name": 'Pancake Day', "local_name": 'Shrove Tuesday', "countries": ['UK'], "category": 'unofficial', "date_type": 'easter_offset', "offset_days": -47, "source": 'https://www.history.co.uk/articles/when-is-pancake-day', "note": 'Luôn 47 ngày trước Chủ nhật Phục Sinh — ngày ẩm thực/công thức nấu ăn lớn ở UK'},
    {"name": 'Remembrance Sunday', "countries": ['UK'], "category": 'official', "date_type": 'nth_weekday', "month": 11, "weekday": 6, "nth": 2, "source": 'https://www.cwgc.org/our-work/blog/everything-you-need-to-know-about-remembrance-day/', "note": 'Chủ nhật gần 11/11 nhất — lễ tưởng niệm trang trọng, cân nhắc điều chỉnh tông quảng cáo'},
    {"name": 'Family Day', "countries": ['Canada'], "category": 'official', "date_type": 'nth_weekday', "month": 2, "weekday": 0, "nth": 3, "source": 'https://en.wikipedia.org/wiki/Family_Day_(Canada)', "note": 'Thứ Hai thứ 3 tháng 2 — ngày nghỉ chính thức ở Alberta/BC/Ontario/Saskatchewan/New Brunswick (tỉnh khác có ngày tương đương tên khác)'},
    {"name": 'Easter Sunday', "countries": ['Canada'], "category": 'unofficial', "date_type": 'easter_offset', "offset_days": 0, "source": 'https://thecanadianencyclopedia.ca/en/article/easter-in-canada', "note": 'Đã có Good Friday/Easter Monday nhưng chưa có chính Chủ nhật Phục Sinh — ngày sum họp/tặng quà gia đình thực sự'},
    {"name": 'National Indigenous Peoples Day', "countries": ['Canada'], "category": 'official', "date_type": 'fixed', "month": 6, "day": 21, "source": 'https://www.rcaanc-cirnac.gc.ca/eng/1100100013718/1708446948967', "note": 'Công nhận toàn liên bang từ 1996, ngày nghỉ chính thức ở Yukon/Northwest Territories'},
    {"name": 'Saint-Jean-Baptiste Day', "local_name": 'Fête nationale du Québec', "countries": ['Canada'], "category": 'official', "date_type": 'fixed', "month": 6, "day": 24, "source": 'https://www.thecanadianencyclopedia.ca/en/article/la-fete-nationale-du-quebec-saint-jean-baptiste-day', "note": 'Ngày lễ chính thức có lương ở Quebec từ 1925 — ngày lễ văn hoá lớn nhất Quebec'},
    {"name": 'Labour Day (NSW/ACT/SA)', "countries": ['Australia'], "category": 'official', "date_type": 'nth_weekday', "month": 10, "weekday": 0, "nth": 1, "source": 'https://www.officeholidays.com/holidays/australia/australia-labour-day', "note": "Chỉ NSW/ACT/SA — bang khác có 'Labour Day' vào ngày khác (WA/VIC/TAS tháng 3, QLD/NT tháng 5)"},
    {"name": "King's Birthday", "countries": ['Australia'], "category": 'official', "date_type": 'nth_weekday', "month": 6, "weekday": 0, "nth": 2, "source": 'https://www.abc.net.au/news/2026-06-04/kings-birthday-public-holiday-june-8-monday-states/106757744', "note": 'Thứ Hai thứ 2 tháng 6 — NSW/VIC/SA/TAS/ACT/NT, riêng QLD/WA vào thời điểm khác'},
    {"name": 'NAIDOC Week', "countries": ['Australia'], "category": 'official', "date_type": 'nth_weekday', "month": 7, "weekday": 6, "nth": 1, "source": 'https://www.naidoc.org.au/about/naidoc-week', "note": 'Tuần lễ tôn vinh văn hoá thổ dân Úc/Torres Strait, bắt đầu Chủ nhật đầu tháng 7'},
    {"name": 'R U OK? Day', "countries": ['Australia'], "category": 'unofficial', "date_type": 'nth_weekday', "month": 9, "weekday": 3, "nth": 2, "source": 'https://www.ruok.org.au/r-u-ok-day', "note": 'Ngày hành động vì sức khoẻ tinh thần, thứ 5 thứ 2 tháng 9 — hưởng ứng rộng ở nơi làm việc'},
    {"name": 'Nikolaustag', "local_name": 'Nikolaustag', "countries": ['Germany'], "category": 'unofficial', "date_type": 'fixed', "month": 12, "day": 6, "source": 'https://www.hamburg.com/visitors/holidays/st-nicholas-day-23008', "note": 'Không phải ngày nghỉ lễ nhưng gần như ai cũng mừng — trẻ em để giày ra đêm 5/12 nhận quà nhỏ'},
    {"name": 'Repentance Day', "local_name": 'Buß- und Bettag', "countries": ['Germany'], "category": 'official', "date_type": 'explicit', "date": '2026-11-18', "source": 'https://publicholidays.de/de/repentance-day/', "note": 'Ngày nghỉ có lương chỉ còn ở bang Sachsen — luôn là thứ 4, 11 ngày trước Chủ nhật Vọng đầu tiên, cần tính lại mỗi năm'},
    {"name": 'Weiberfastnacht', "countries": ['Germany'], "category": 'unofficial', "date_type": 'easter_offset', "offset_days": -52, "source": 'https://germangirlinamerica.com/what-is-weiberfastnacht/', "note": 'Chủ yếu vùng Rhineland (Köln, Düsseldorf, Bonn) — mở đầu tuần Karneval sôi động nhất'},
    {"name": 'Chandeleur', "countries": ['France'], "category": 'unofficial', "date_type": 'fixed', "month": 2, "day": 2, "source": 'https://www.date-pratique.fr/chandeleur.html', "note": 'Truyền thống ăn crêpe gần như toàn quốc, không phải ngày nghỉ lễ'},
    {"name": 'Fête de la Musique', "countries": ['France'], "category": 'official', "date_type": 'fixed', "month": 6, "day": 21, "source": 'https://www.culture.gouv.fr/evenements-nationaux/fete-de-la-musique', "note": 'Sự kiện âm nhạc miễn phí toàn quốc do Bộ Văn hoá Pháp tổ chức từ 1982, không phải ngày nghỉ lễ'},
    {"name": 'Navratri', "local_name": 'शारदीय नवरात्रि', "countries": ['India'], "category": 'unofficial', "date_type": 'explicit', "date": '2026-10-11', "source": 'https://www.calendardate.com/navratri_2026.htm', "note": 'Lễ hội 9 đêm trước Dussehra — lớn nhất ở Gujarat/Tây Ấn Độ (garba/dandiya), cần xác minh lại ngày mỗi năm'},
    {"name": 'Durga Puja', "local_name": 'দুর্গা পূজা', "countries": ['India'], "category": 'official', "date_type": 'explicit', "date": '2026-10-16', "source": 'https://samvat.in/festivals/durga-puja-2026/', "note": 'Ngày nghỉ chính thức ở Tây Bengal/Odisha/Tripura/Bihar/Assam — ngày kết thúc trùng Dussehra, cần xác minh lại mỗi năm'},
    {"name": 'Onam', "local_name": 'ഓണം', "countries": ['India'], "category": 'official', "date_type": 'explicit', "date": '2026-08-26', "source": 'https://www.drikpanchang.com/festivals/onam/onam-thiruvonam-date.html?geoname-id=1254163', "note": 'Ngày nghỉ chính thức bang Kerala, lễ hội thu hoạch lớn nhất Nam Ấn Độ — cần xác minh lại mỗi năm'},
    {"name": "New Year's Eve", "local_name": 'Réveillon', "countries": ['Brazil'], "category": 'unofficial', "date_type": 'fixed', "month": 12, "day": 31, "source": 'https://en.prefeitura.rio/noticias/rio-reveillon-2026-celebra-o-futuro-e-traz-atracoes-ineditas-para-a-maior-festa-de-ano-novo-do-mundo/', "note": 'Khác Tết Dương lịch (1/1) — đêm giao thừa Copacabana thu hút ~2,5 triệu người, 1 trong các lễ hội giao thừa lớn nhất thế giới'},
    {"name": "Valentine's Day (BR)", "local_name": 'Dia dos Namorados', "countries": ['Brazil'], "category": 'unofficial', "date_type": 'fixed', "month": 6, "day": 12, "source": 'https://www.timeanddate.com/holidays/brazil/dia-dos-namorados', "note": "Ngày lễ tình nhân RIÊNG của Brazil, khác 14/2 quốc tế — lớn hơn cả Valentine's Day quốc tế ở đây"},
    {"name": 'Festa Junina', "countries": ['Brazil'], "category": 'unofficial', "date_type": 'fixed', "month": 6, "day": 24, "source": 'https://www.awarenessdays.com/awareness-days-calendar/festa-junina/', "note": 'Đỉnh điểm mùa lễ hội tháng 6 miền Bắc/Đông Bắc Brazil (quanh cả Santo Antônio 13/6, São Pedro 29/6)'},
    {"name": 'Republic Proclamation Day', "countries": ['Brazil'], "category": 'official', "date_type": 'fixed', "month": 11, "day": 15, "source": 'https://www.officeholidays.com/holidays/brazil/brazil-republic-day'},
    {"name": 'Flag Day', "local_name": 'Día de la Bandera', "countries": ['Mexico'], "category": 'official', "date_type": 'fixed', "month": 2, "day": 24, "source": 'https://en.wikipedia.org/wiki/Flag_Day_in_Mexico', "note": 'Ngày lễ dân sự, nghi thức chào cờ ở trường học toàn quốc'},
    {"name": 'Grito de Independencia', "countries": ['Mexico'], "category": 'unofficial', "date_type": 'fixed', "month": 9, "day": 15, "source": 'https://www.officeholidays.com/holidays/mexico/mexico-independence-day', "note": 'Đêm 15/9 (~23h) — khác Ngày Độc lập chính thức (16/9), khoảnh khắc văn hoá/mạng xã hội lớn nhất năm ở Mexico'},
    {"name": 'Día del Niño', "countries": ['Mexico'], "category": 'unofficial', "date_type": 'fixed', "month": 4, "day": 30, "source": 'https://anydayguide.com/calendar/1952', "note": 'Không phải ngày nghỉ lễ nhưng được mừng rộng khắp (trường học, tặng quà, hoạt động gia đình)'},
    {"name": 'Easter Sunday', "local_name": 'Paskah', "countries": ['Indonesia'], "category": 'official', "date_type": 'easter_offset', "offset_days": 0, "source": 'https://www.officeholidays.com/countries/indonesia/2026', "note": 'Ngày nghỉ lễ chính thức riêng biệt với Good Friday (nhiều nguồn ngoài chỉ nhắc Good Friday)'},
    {"name": 'Vesak Day', "local_name": 'Hari Raya Waisak', "countries": ['Indonesia'], "category": 'official', "date_type": 'explicit', "date": '2026-05-31', "source": 'https://www.officeholidays.com/holidays/indonesia/wesak-day', "note": 'Ngày nghỉ lễ chính thức, trung tâm lễ hội tại đền Borobudur — cần xác minh lại mỗi năm'},
    {"name": 'Nuzulul Quran', "countries": ['Indonesia'], "category": 'official', "date_type": 'explicit', "date": '2026-03-10', "source": 'https://www.setneg.go.id/baca/index/peringatan_nuzulul_quran_di_istana_negara_presiden_prabowo_subianto_ajak_jadikan_al_quran_sumber_persatuan_dan_kedamaian_bangsa', "note": 'Không phải ngày nghỉ nhưng có lễ kỷ niệm cấp nhà nước tại Istana Negara — cần xác minh lại mỗi năm'},
    {"name": 'EDSA People Power Revolution Anniversary', "countries": ['Philippines'], "category": 'official', "date_type": 'fixed', "month": 2, "day": 25, "source": 'https://lightoflove.com.ph/2026/02/06/edsa-people-power-feb-25-2026-is-a-special-working-holiday/', "note": 'Ngày kỷ niệm cố định 25/2 hàng năm theo sắc lệnh tổng thống — có nghỉ hay không tuỳ công bố từng năm'},
    {"name": 'Buwan ng Wika (National Language Month)', "countries": ['Philippines'], "category": 'official', "date_type": 'fixed', "month": 8, "day": 1, "source": 'https://en.wikipedia.org/wiki/Buwan_ng_Wika', "note": 'Cả tháng 8 là tháng ngôn ngữ quốc gia, cao điểm 19/8 (sinh nhật Quezon)'},
    {"name": 'Feast of the Black Nazarene', "local_name": 'Traslación', "countries": ['Philippines'], "category": 'unofficial', "date_type": 'fixed', "month": 1, "day": 9, "source": 'https://en.wikipedia.org/wiki/Feast_of_the_Black_Nazarene', "note": '1 trong những lễ hội tôn giáo lớn nhất châu Á (hơn 9,6 triệu người 2026), luôn 9/1'},
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


def event_tiers(event):
    """Tập hợp tier (1/2) mà sự kiện này áp dụng — suy ra TỰ ĐỘNG từ danh
    sách "countries" (tra COUNTRIES), không lưu cứng field riêng để tránh
    lệch dữ liệu khi 1 sự kiện gộp nhiều nước khác tier nhau (vd New Year's
    Day có cả nước tier 1 lẫn tier 2)."""
    return {COUNTRIES[c][1] for c in event["countries"] if c in COUNTRIES}


def upcoming_events(today=None, countries=None, tiers=None, categories=None, limit=None, until=None, since=None):
    """Danh sách sự kiện sắp tới, sắp xếp theo ngày gần nhất — lọc được
    theo quốc gia/tier/loại. 1 sự kiện có thể thuộc NHIỀU quốc gia
    ("countries" là 1 danh sách) — khớp bộ lọc quốc gia/tier nếu CÓ ÍT NHẤT
    1 nước trong danh sách của sự kiện khớp. `today` mặc định là hôm nay
    thật (truyền vào khi cần test với 1 ngày cố định).

    `since`/`until`: chỉ lấy sự kiện rơi trong khoảng [since, until] (bao
    gồm cả 2 đầu) — mặc định `since=today`, `until`=hết năm hiện tại
    (31/12). Cho 1 khung thời gian TRONG TƯƠNG LAI không dính hôm nay (vd
    "chỉ xem tháng 9", không phải "từ nay tới hết tháng 9") — truyền
    `since` là ngày đầu khung đó (xem `_event_range_bounds` trong app.py).
    Dữ liệu chỉ có ý nghĩa chắc chắn trong năm đang chạy (xem docstring
    EVENTS/needs_update — nhiều mục âm lịch/tôn giáo phải cập nhật lại MỖI
    NĂM, đoán xa hơn 1 năm dễ sai) — ưu tiên chắc chắn trong phạm vi gần
    hơn là dàn trải xa mà thiếu chính xác."""
    if today is None:
        today = date.today()
    if since is None:
        since = today
    if until is None:
        until = date(today.year, 12, 31)
    rows = []
    for ev in EVENTS:
        if countries and not (set(ev["countries"]) & set(countries)):
            continue
        if tiers and not (event_tiers(ev) & set(tiers)):
            continue
        if categories and ev["category"] not in categories:
            continue
        d = next_occurrence(ev, today)
        if d is None or d < since or d > until:
            continue
        rows.append((d, ev))
    rows.sort(key=lambda r: r[0])
    if limit:
        rows = rows[:limit]
    return rows
