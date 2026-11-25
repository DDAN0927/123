package com.travel.trip;

import com.travel.trip.TripDtos.DayView;
import com.travel.trip.TripDtos.ItemView;
import com.travel.trip.TripDtos.TripView;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * 导出：日历（.ics）与打印版（HTML）。
 *
 * <p>为什么 PDF 走打印版而不是服务端生成：服务端生成 PDF 要嵌中文字体，
 * 一个字体文件就是十几 MB，还容易在不同环境里变成方块字。打印版让浏览器出 PDF，
 * 字体与排版都交给用户本机，结果稳定得多。
 */
@Service
public class ExportService {

    private static final DateTimeFormatter ICS_DATE = DateTimeFormatter.ofPattern("yyyyMMdd");
    private static final DateTimeFormatter ICS_STAMP = DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmss'Z'");

    /**
     * 生成 iCalendar 文本。每天的条目做成全天事件，手机日历导入后按天铺开；
     * 行前清单一整条放在出发前一天，点开就是清单全文。
     */
    public String ics(TripView trip) {
        LocalDate start = trip.startDate() == null || trip.startDate().isBlank() ? LocalDate.now() : LocalDate.parse(trip.startDate());
        String stamp = LocalDateTime.now(ZoneOffset.UTC).format(ICS_STAMP);
        StringBuilder sb = new StringBuilder();
        sb.append("BEGIN:VCALENDAR\r\n")
                .append("VERSION:2.0\r\n")
                .append("PRODID:-//Travel Copilot//行程规划//CN\r\n")
                .append("CALSCALE:GREGORIAN\r\n")
                .append("METHOD:PUBLISH\r\n")
                .append("X-WR-CALNAME:").append(escape(trip.title())).append("\r\n");

        if (!trip.prep().isEmpty()) {
            StringBuilder desc = new StringBuilder("行前清单（共 ").append(trip.prep().size()).append(" 项）：\n");
            for (ItemView it : trip.prep()) {
                desc.append(it.done() ? "[x] " : "[ ] ").append(it.slot().isEmpty() ? "" : it.slot() + " - ").append(it.title()).append('\n');
            }
            appendEvent(sb, trip.id() + "-prep", start.minusDays(1), "行前准备：" + trip.title(), desc.toString(), stamp);
        }
        for (DayView day : trip.itinerary()) {
            LocalDate date = start.plusDays(day.day() - 1L);
            for (ItemView it : day.items()) {
                String summary = "第" + day.day() + "天 " + (it.slot().isEmpty() ? "" : it.slot() + " ") + it.title();
                appendEvent(sb, trip.id() + "-" + it.id(), date, summary, it.note(), stamp);
            }
        }
        sb.append("END:VCALENDAR\r\n");
        return sb.toString();
    }

    private void appendEvent(StringBuilder sb, String uid, LocalDate date, String summary, String description, String stamp) {
        sb.append("BEGIN:VEVENT\r\n")
                .append("UID:").append(uid).append("@travel-copilot\r\n")
                .append("DTSTAMP:").append(stamp).append("\r\n")
                .append("DTSTART;VALUE=DATE:").append(date.format(ICS_DATE)).append("\r\n")
                .append("SUMMARY:").append(fold(escape(summary))).append("\r\n");
        if (description != null && !description.isBlank()) {
            sb.append("DESCRIPTION:").append(fold(escape(description))).append("\r\n");
        }
        sb.append("END:VEVENT\r\n");
    }

    /** iCalendar 转义：反斜杠、分号、逗号、换行都有语义。 */
    static String escape(String raw) {
        if (raw == null) {
            return "";
        }
        return raw.replace("\\", "\\\\")
                .replace(";", "\\;")
                .replace(",", "\\,")
                .replace("\r\n", "\\n")
                .replace("\n", "\\n");
    }

    /**
     * 按 70 字节折行（RFC 5545 要求 75 字节内）。
     *
     * <p>必须按 **码点** 而不是 char 走：emoji 在 Java 里是两个 char（代理对），
     * 按 char 累加字节数会把「🏯」算成 2 字节，还可能把 CRLF 插在两个代理之间，
     * 得到一个无法解码的半个字符 —— 用户标题里带个表情就会踩到。
     */
    static String fold(String line) {
        byte[] bytes = line.getBytes(StandardCharsets.UTF_8);
        if (bytes.length <= 70) {
            return line;
        }
        StringBuilder out = new StringBuilder();
        int used = 0;
        int i = 0;
        while (i < line.length()) {
            int cp = line.codePointAt(i);
            int len = new String(Character.toChars(cp)).getBytes(StandardCharsets.UTF_8).length;
            if (used + len > 70) {
                out.append("\r\n ");
                used = 1;
            }
            out.appendCodePoint(cp);
            used += len;
            i += Character.charCount(cp);
        }
        return out.toString();
    }

    /** 打印版：自带打印样式，页面加载后可直接 Ctrl+P / 另存为 PDF。 */
    public String printableHtml(TripView trip) {
        StringBuilder sb = new StringBuilder();
        String title = html(trip.title());
        sb.append("<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">")
                .append("<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">")
                .append("<title>").append(title).append(" · 行程单</title><style>")
                .append(":root{--ink:#1f2328;--muted:#6b7280;--line:#e5e7eb}")
                .append("*{box-sizing:border-box}body{margin:0;padding:32px 28px;color:var(--ink);")
                .append("font:15px/1.7 -apple-system,'Segoe UI','Microsoft YaHei',sans-serif;background:#fff}")
                .append("h1{font-size:26px;margin:0 0 6px}h2{font-size:17px;margin:26px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}")
                .append(".meta{color:var(--muted);font-size:13px;margin-bottom:4px}")
                .append(".kv{display:flex;gap:18px;flex-wrap:wrap;color:var(--muted);font-size:13px;margin:10px 0 0}")
                .append("ul{margin:0;padding-left:18px}li{margin:3px 0}")
                .append(".done{color:var(--muted);text-decoration:line-through}")
                .append(".slot{display:inline-block;min-width:44px;color:var(--muted);font-size:12px}")
                .append(".note{color:var(--muted);font-size:12px;margin-left:6px}")
                .append(".bar{position:fixed;right:20px;bottom:20px;display:flex;gap:8px}")
                .append(".bar button{padding:9px 16px;border-radius:8px;border:1px solid var(--line);background:#fff;cursor:pointer;font-size:14px}")
                .append(".bar button.primary{background:#1f6feb;color:#fff;border-color:#1f6feb}")
                .append("@media print{.bar{display:none}body{padding:0}h2{break-after:avoid}li{break-inside:avoid}}")
                .append("</style></head><body>");

        sb.append("<h1>").append(title).append("</h1>");
        sb.append("<div class=\"meta\">").append(html(trip.city()))
                .append(trip.startDate().isEmpty() ? " · 日期待定" : " · " + trip.startDate())
                .append(" · ").append(trip.days()).append(" 天</div>");
        sb.append("<div class=\"kv\"><span>预算 ¥").append(trip.budget()).append("</span>")
                .append("<span>已记支出 ¥").append(trip.expenses().spent()).append("</span>")
                .append("<span>清单完成 ").append(trip.progress().done()).append("/").append(trip.progress().total()).append("</span></div>");

        if (!trip.prep().isEmpty()) {
            sb.append("<h2>行前清单</h2><ul>");
            for (ItemView it : trip.prep()) {
                sb.append("<li").append(it.done() ? " class=\"done\"" : "").append(">")
                        .append(html(it.title())).append("</li>");
            }
            sb.append("</ul>");
        }
        for (DayView day : trip.itinerary()) {
            sb.append("<h2>第 ").append(day.day()).append(" 天</h2><ul>");
            for (ItemView it : day.items()) {
                sb.append("<li").append(it.done() ? " class=\"done\"" : "").append(">");
                if (!it.slot().isEmpty()) {
                    sb.append("<span class=\"slot\">").append(html(it.slot())).append("</span>");
                }
                sb.append(html(it.title()));
                if (it.note() != null && !it.note().isBlank()) {
                    sb.append("<span class=\"note\">").append(html(it.note())).append("</span>");
                }
                sb.append("</li>");
            }
            sb.append("</ul>");
        }
        sb.append("<div class=\"bar\"><button class=\"primary\" onclick=\"window.print()\">打印 / 存为 PDF</button>")
                .append("<button onclick=\"window.close()\">关闭</button></div>");
        sb.append("</body></html>");
        return sb.toString();
    }

    private static String html(String raw) {
        if (raw == null) {
            return "";
        }
        return raw.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;");
    }

    /** 供测试用：条目数量对不上时通常是 dayIndex 越界被夹掉了。 */
    static int eventCount(List<DayView> itinerary) {
        return itinerary.stream().mapToInt(d -> d.items().size()).sum();
    }
}
