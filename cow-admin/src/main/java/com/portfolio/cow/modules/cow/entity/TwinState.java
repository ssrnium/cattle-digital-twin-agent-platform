package com.portfolio.cow.modules.cow.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.annotation.Version;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * 单牛数字孪生当前状态。
 * state 内容约定：posture / zone / health_status(NORMAL|LAMENESS_RISK) /
 * estrus_status(NORMAL|SUSPECTED_HEAT) 等键值。
 */
@Data
@TableName(value = "twin_state", autoResultMap = true)
public class TwinState {

    @TableId
    private String cowId;

    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> state;

    /** MEASURED / INFERRED / MANUAL */
    private String stateNature;

    private String sourceEventId;
    private LocalDateTime eventTime;

    /** 乐观锁 */
    @Version
    private Integer version;

    private LocalDateTime updatedAt;
}
