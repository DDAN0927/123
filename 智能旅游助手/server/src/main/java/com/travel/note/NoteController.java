package com.travel.note;

import com.travel.note.NoteService.NoteUpsertReq;
import com.travel.note.NoteService.NoteView;
import com.travel.security.CurrentUser;
import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** 游记接口（任务书 3(5)）：按行程归属，读写都要校验行程属于当前用户。 */
@RestController
@RequestMapping("/api/trips/{tripId}/notes")
public class NoteController {

    private final NoteService notes;
    private final CurrentUser currentUser;

    public NoteController(NoteService notes, CurrentUser currentUser) {
        this.notes = notes;
        this.currentUser = currentUser;
    }

    @GetMapping
    public Map<String, Object> list(@PathVariable String tripId) {
        List<NoteView> rows = notes.list(currentUser.username(), tripId);
        return Map.of("notes", rows, "total", rows.size());
    }

    @PostMapping
    public Map<String, Object> create(@PathVariable String tripId, @RequestBody NoteUpsertReq req) {
        return Map.of("note", notes.create(currentUser.username(), tripId, req));
    }

    @PutMapping("/{id}")
    public Map<String, Object> update(@PathVariable String tripId, @PathVariable Long id, @RequestBody NoteUpsertReq req) {
        return Map.of("note", notes.update(currentUser.username(), tripId, id, req));
    }

    @DeleteMapping("/{id}")
    public Map<String, Object> delete(@PathVariable String tripId, @PathVariable Long id) {
        notes.delete(currentUser.username(), tripId, id);
        return Map.of("message", "已删除");
    }
}
