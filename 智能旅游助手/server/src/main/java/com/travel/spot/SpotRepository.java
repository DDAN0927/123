package com.travel.spot;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

public interface SpotRepository extends JpaRepository<SpotEntity, Long> {

    List<SpotEntity> findByCityOrderByNameAsc(String city);

    Optional<SpotEntity> findByCityAndName(String city, String name);

    long countByCity(String city);

    void deleteByCity(String city);

    /** 筛选面板的城市清单：只取一列，不要把 8000 条实体整行读进内存。 */
    @Query("select distinct s.city from SpotEntity s order by s.city")
    List<String> distinctCities();
}
