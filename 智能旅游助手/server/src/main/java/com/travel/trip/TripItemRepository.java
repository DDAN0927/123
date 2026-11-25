package com.travel.trip;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface TripItemRepository extends JpaRepository<TripItemEntity, Long> {

    List<TripItemEntity> findByTripIdOrderByDayIndexAscSortAscIdAsc(String tripId);

    Optional<TripItemEntity> findByIdAndTripId(Long id, String tripId);

    @Modifying
    @Query("delete from TripItemEntity i where i.tripId = :tripId and i.dayIndex = 0 and i.kind = 'packing'")
    int deleteGeneratedPacking(@Param("tripId") String tripId);

    @Modifying
    @Query("delete from TripItemEntity i where i.tripId = :tripId and i.dayIndex >= 1")
    int deleteItinerary(@Param("tripId") String tripId);

    @Modifying
    @Query("delete from TripItemEntity i where i.tripId = :tripId")
    int deleteByTrip(@Param("tripId") String tripId);

    long countByTripId(String tripId);
}
