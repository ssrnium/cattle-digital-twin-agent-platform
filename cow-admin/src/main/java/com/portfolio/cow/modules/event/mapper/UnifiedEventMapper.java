package com.portfolio.cow.modules.event.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.portfolio.cow.modules.event.entity.UnifiedEvent;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;
import java.util.Map;

public interface UnifiedEventMapper extends BaseMapper<UnifiedEvent> {

    /** 近 N 天事件趋势（dashboard 折线图） */
    @Select("""
            SELECT to_char(event_time, 'MM-DD') AS name, COUNT(*) AS value
            FROM unified_event
            WHERE event_time >= now() - make_interval(days => #{days})
            GROUP BY 1
            ORDER BY MIN(event_time)
            """)
    List<Map<String, Object>> selectEventTrend(@Param("days") int days);
}
