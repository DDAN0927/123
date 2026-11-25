package com.travel.trip;

import com.travel.security.CurrentUser;
import com.travel.trip.TripDtos.TripView;
import java.nio.charset.StandardCharsets;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** 导出接口：日历与打印版。都要求登录（行程是私有数据）。 */
@RestController
@RequestMapping("/api/trips/{id}/export")
public class ExportController {

    private final TripService trips;
    private final ExportService exporter;
    private final CurrentUser currentUser;

    public ExportController(TripService trips, ExportService exporter, CurrentUser currentUser) {
        this.trips = trips;
        this.exporter = exporter;
        this.currentUser = currentUser;
    }

    /** 手机日历直接导入：扫码或下载后点开即可。 */
    @GetMapping(value = "/ics", produces = "text/calendar;charset=UTF-8")
    public ResponseEntity<byte[]> ics(@PathVariable String id) {
        TripView trip = trips.get(currentUser.username(), id);
        byte[] body = exporter.ics(trip).getBytes(StandardCharsets.UTF_8);
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION,
                        ContentDisposition.attachment().filename(trip.title() + ".ics", StandardCharsets.UTF_8).build().toString())
                .body(body);
    }

    /** 打印版：浏览器里 Ctrl+P 另存为 PDF，服务端不嵌中文字体。 */
    @GetMapping(value = "/print", produces = "text/html;charset=UTF-8")
    public ResponseEntity<byte[]> print(@PathVariable String id) {
        TripView trip = trips.get(currentUser.username(), id);
        return ResponseEntity.ok()
                .contentType(new MediaType(MediaType.TEXT_HTML, StandardCharsets.UTF_8))
                .body(exporter.printableHtml(trip).getBytes(StandardCharsets.UTF_8));
    }
}
