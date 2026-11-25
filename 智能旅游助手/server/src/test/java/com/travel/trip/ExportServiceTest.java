package com.travel.trip;

import static org.assertj.core.api.Assertions.assertThat;

import com.travel.trip.TripDtos.DayView;
import com.travel.trip.TripDtos.ItemView;
import com.travel.trip.TripDtos.ProgressView;
import com.travel.trip.TripDtos.TripView;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * 导出功能的单元测试。
 *
 * <p>这几条都不是「函数能跑」，而是**导出的文件到了别人手机上会不会坏**：
 * 逗号没转义 → 手机日历只显示半句话；折行按 char 算 → 标题里的 emoji 变成乱码；
 * HTML 没转义 → 行程标题里的尖括号直接变成标签。
 */
class ExportServiceTest {

    private final ExportService service = new ExportService();

    private static ItemView item(long id, int day, String slot, String title, String note, boolean done) {
        return new ItemView(id, day, slot, "spot", title, note, done);
    }

    private static TripView trip(String title, String startDate, int days, List<ItemView> prep, List<DayView> itinerary) {
        return new TripView(
                "t1",
                "北京",
                title,
                startDate,
                days,
                3000,
                "",
                5,
                "upcoming",
                new ProgressView(0, 0, 0),
                prep,
                itinerary,
                null,
                new TripDtos.BudgetView(3000, java.math.BigDecimal.ZERO, java.math.BigDecimal.valueOf(3000), 0, Map.of(), List.of()),
                false,
                List.of());
    }

    // ---------------------------------------------------------------- 转义

    @Test
    @DisplayName("iCalendar 转义：分号、逗号、反斜杠、换行都有语义")
    void escapeHandlesIcsSpecialChars() {
        assertThat(ExportService.escape("A;B,C\\D")).isEqualTo("A\\;B\\,C\\\\D");
        assertThat(ExportService.escape("第一行\n第二行")).isEqualTo("第一行\\n第二行");
        assertThat(ExportService.escape("第一行\r\n第二行")).isEqualTo("第一行\\n第二行");
        assertThat(ExportService.escape(null)).isEmpty();
    }

    @Test
    @DisplayName("反斜杠必须先转义，否则会把后面的 \\; 再转一次")
    void escapeHandlesBackslashBeforeSemicolon() {
        // 若先转 ; 再转 \\，就会得到 "\\\\;"（三个反斜杠），手机端解析成字面量反斜杠 + 分号
        assertThat(ExportService.escape("a\\;b")).isEqualTo("a\\\\\\;b");
    }

    // ---------------------------------------------------------------- 折行

    @Test
    @DisplayName("短行不折")
    void shortLineIsNotFolded() {
        assertThat(ExportService.fold("第1天 上午 故宫")).isEqualTo("第1天 上午 故宫");
    }

    @Test
    @DisplayName("长行按 70 字节折行，续行以空格开头")
    void longLineIsFolded() {
        String folded = ExportService.fold("行".repeat(80));
        assertThat(folded).contains("\r\n ");
        for (String physical : folded.split("\r\n")) {
            // RFC 5545 要求 75 字节内（含续行那个前导空格）
            assertThat(physical.getBytes(StandardCharsets.UTF_8).length).isLessThanOrEqualTo(70);
        }
        assertThat(folded.replace("\r\n ", "")).isEqualTo("行".repeat(80));
    }

    @Test
    @DisplayName("折行不能把 emoji 的代理对切断")
    void foldDoesNotSplitSurrogatePair() {
        String raw = "🏯".repeat(40); // 每个 emoji 占 4 字节
        String folded = ExportService.fold(raw);
        // 能原样还原 = 没有半个字符被截断
        assertThat(folded.replace("\r\n ", "")).isEqualTo(raw);
        for (String physical : folded.split("\r\n")) {
            assertThat(physical.getBytes(StandardCharsets.UTF_8).length).isLessThanOrEqualTo(70);
        }
    }

    // ---------------------------------------------------------------- .ics

    @Test
    @DisplayName("每个条目一个 VEVENT，日期从出发日顺延")
    void icsHasOneEventPerItem() {
        TripView t =
                trip(
                        "北京 3 天",
                        "2026-11-01",
                        3,
                        List.of(item(1, 0, "证件与票据", "身份证", "", false)),
                        List.of(
                                new DayView(1, List.of(item(2, 1, "上午", "故宫", "提前 7 天预约", false))),
                                new DayView(2, List.of(item(3, 2, "上午", "颐和园", "", true)))));

        String ics = service.ics(t);
        assertThat(ics).startsWith("BEGIN:VCALENDAR\r\n");
        assertThat(ics).endsWith("END:VCALENDAR\r\n");
        assertThat(count(ics, "BEGIN:VEVENT")).isEqualTo(3); // 行前清单 1 + 每日 2
        assertThat(ics).contains("DTSTART;VALUE=DATE:20261101");
        assertThat(ics).contains("DTSTART;VALUE=DATE:20261102");
        // 行前清单一整条放在出发前一天
        assertThat(ics).contains("DTSTART;VALUE=DATE:20261031");
        assertThat(ics).contains("SUMMARY:第1天 上午 故宫");
        // 行前清单里带分组名：slot 非空时会拼成「分组 - 标题」
        assertThat(ics).contains("[ ] 证件与票据 - 身份证");
    }

    @Test
    @DisplayName("标题里的换行不会把 ics 结构撑破")
    void icsEscapesNewlinesInTitle() {
        TripView t = trip("北京\nEND:VCALENDAR", "2026-11-01", 1, List.of(), List.of());
        String ics = service.ics(t);
        // 转义后标题里的换行变成字面量 \n，所以「END:VCALENDAR」独占一行的只有真正的结尾那一行
        assertThat(ics.split("\r\n")).filteredOn(l -> l.equals("END:VCALENDAR")).hasSize(1);
        assertThat(ics).contains("X-WR-CALNAME:北京\\nEND:VCALENDAR");
    }

    // ---------------------------------------------------------------- 打印版

    @Test
    @DisplayName("打印版转义 HTML，标题里的标签不会变成真标签")
    void printableHtmlEscapesTitle() {
        TripView t = trip("<script>alert(1)</script>", "2026-11-01", 1, List.of(), List.of());
        String html = service.printableHtml(t);
        assertThat(html).doesNotContain("<script>alert(1)</script>");
        assertThat(html).contains("&lt;script&gt;alert(1)&lt;/script&gt;");
    }

    @Test
    @DisplayName("打印版包含行前清单与每天的小标题")
    void printableHtmlListsEverything() {
        TripView t =
                trip(
                        "北京 2 天",
                        "2026-11-01",
                        2,
                        List.of(item(1, 0, "", "身份证", "", true)),
                        List.of(new DayView(1, List.of(item(2, 1, "上午", "故宫", "提前 7 天预约", false)))));
        String html = service.printableHtml(t);
        assertThat(html).contains("<h2>行前清单</h2>");
        assertThat(html).contains("class=\"done\">身份证");
        assertThat(html).contains("<h2>第 1 天</h2>");
        assertThat(html).contains("提前 7 天预约");
        assertThat(html).contains("window.print()");
    }

    private static int count(String text, String needle) {
        int n = 0;
        int i = text.indexOf(needle);
        while (i >= 0) {
            n++;
            i = text.indexOf(needle, i + needle.length());
        }
        return n;
    }
}
