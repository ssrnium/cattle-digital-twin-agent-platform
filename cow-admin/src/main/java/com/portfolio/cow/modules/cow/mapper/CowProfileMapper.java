package com.portfolio.cow.modules.cow.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.portfolio.cow.modules.cow.entity.CowProfile;
import org.apache.ibatis.annotations.Select;

import java.util.List;
import java.util.Map;

public interface CowProfileMapper extends BaseMapper<CowProfile> {

    /** 健康状态分布：无孪生记录的牛计入 UNKNOWN */
    @Select("""
            SELECT COALESCE(t.state->>'health_status', 'UNKNOWN') AS name, COUNT(*) AS value
            FROM cow_profile c
            LEFT JOIN twin_state t ON c.cow_id = t.cow_id
            GROUP BY 1
            ORDER BY 2 DESC
            """)
    List<Map<String, Object>> selectHealthDistribution();
}
