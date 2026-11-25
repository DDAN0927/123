package com.travel.trip;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TripRepository extends JpaRepository<TripEntity, String> {

    List<TripEntity> findByUsernameOrderByUpdatedAtDesc(String username);

    Optional<TripEntity> findByIdAndUsername(String id, String username);

    Optional<TripEntity> findByShareToken(String shareToken);

    long countByUsername(String username);
}
