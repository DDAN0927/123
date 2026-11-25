package com.travel.note;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TripNoteRepository extends JpaRepository<TripNoteEntity, Long> {

    List<TripNoteEntity> findByTripIdOrderByCreatedAtDesc(String tripId);

    Optional<TripNoteEntity> findByIdAndTripIdAndUsername(Long id, String tripId, String username);

    long countByTripId(String tripId);

    void deleteByTripId(String tripId);
}
