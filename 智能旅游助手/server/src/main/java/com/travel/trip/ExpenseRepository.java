package com.travel.trip;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface ExpenseRepository extends JpaRepository<ExpenseEntity, Long> {

    List<ExpenseEntity> findByTripIdOrderByDayIndexAscIdAsc(String tripId);

    Optional<ExpenseEntity> findByIdAndTripId(Long id, String tripId);

    @Modifying
    @Query("delete from ExpenseEntity e where e.tripId = :tripId")
    int deleteByTrip(@Param("tripId") String tripId);
}
