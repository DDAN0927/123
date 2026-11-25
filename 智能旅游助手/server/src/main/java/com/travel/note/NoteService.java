package com.travel.note;

import com.travel.common.BizException;
import com.travel.trip.TripRepository;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** 游记业务。越权一律 404（与行程模块同一套规矩，403 等于告诉对方 id 存在）。 */
@Service
public class NoteService {

    private final TripNoteRepository notes;
    private final TripRepository trips;

    public NoteService(TripNoteRepository notes, TripRepository trips) {
        this.notes = notes;
        this.trips = trips;
    }

    @Transactional(readOnly = true)
    public List<NoteView> list(String username, String tripId) {
        requireTrip(username, tripId);
        return notes.findByTripIdOrderByCreatedAtDesc(tripId).stream().map(NoteService::view).toList();
    }

    @Transactional
    public NoteView create(String username, String tripId, NoteUpsertReq req) {
        requireTrip(username, tripId);
        String content = req.content() == null ? "" : req.content().trim();
        if (content.isEmpty()) {
            throw BizException.badRequest("游记正文不能为空");
        }
        String title = req.title() == null || req.title().isBlank() ? defaultTitle(content) : req.title().trim();
        TripNoteEntity n = new TripNoteEntity(tripId, username, title, content);
        n.setImages(join(req.images()));
        return view(notes.save(n));
    }

    @Transactional
    public NoteView update(String username, String tripId, Long id, NoteUpsertReq req) {
        TripNoteEntity n = notes.findByIdAndTripIdAndUsername(id, tripId, username)
                .orElseThrow(() -> BizException.notFound("这篇游记不存在"));
        if (req.title() != null && !req.title().isBlank()) {
            n.setTitle(req.title().trim());
        }
        if (req.content() != null && !req.content().isBlank()) {
            n.setContent(req.content().trim());
        }
        if (req.images() != null) {
            n.setImages(join(req.images()));
        }
        n.touch();
        return view(notes.save(n));
    }

    @Transactional
    public void delete(String username, String tripId, Long id) {
        TripNoteEntity n = notes.findByIdAndTripIdAndUsername(id, tripId, username)
                .orElseThrow(() -> BizException.notFound("这篇游记不存在"));
        notes.delete(n);
    }

    private void requireTrip(String username, String tripId) {
        trips.findByIdAndUsername(tripId, username).orElseThrow(() -> BizException.notFound("行程不存在"));
    }

    /** 没写标题时取正文首行前 20 字，比强制用户先想标题顺一点。 */
    private static String defaultTitle(String content) {
        String first = content.split("\\r?\\n", 2)[0].trim();
        if (first.isEmpty()) {
            return "未命名游记";
        }
        return first.length() > 20 ? first.substring(0, 20) : first;
    }

    private static String join(List<String> images) {
        if (images == null || images.isEmpty()) {
            return "";
        }
        List<String> clean = new ArrayList<>();
        for (String s : images) {
            if (s != null && !s.isBlank() && clean.size() < 9) {
                clean.add(s.trim());
            }
        }
        return String.join(",", clean);
    }

    private static NoteView view(TripNoteEntity n) {
        List<String> imgs = n.getImages() == null || n.getImages().isBlank()
                ? List.of()
                : List.of(n.getImages().split(","));
        return new NoteView(
                n.getId(),
                n.getTripId(),
                n.getTitle(),
                n.getContent(),
                imgs,
                n.getCreatedAt() == null ? null : n.getCreatedAt().toString(),
                n.getUpdatedAt() == null ? null : n.getUpdatedAt().toString());
    }

    public record NoteView(
            Long id, String tripId, String title, String content, List<String> images, String createdAt, String updatedAt) {}

    public record NoteUpsertReq(String title, String content, List<String> images) {}

    /** 供其它模块复用（例如删除行程时连带清游记）。 */
    @Transactional
    public void deleteAllOfTrip(String tripId) {
        notes.deleteByTripId(tripId);
    }

    static Instant now() {
        return Instant.now();
    }
}
