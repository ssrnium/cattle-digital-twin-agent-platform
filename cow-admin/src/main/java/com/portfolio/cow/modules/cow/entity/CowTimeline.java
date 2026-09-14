package com.portfolio.cow.modules.cow.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.Map;

@Data
@TableName(value = "cow_timeline", autoResultMap = true)
public class CowTimeline {

    @TableId(type = IdType.AUTO)
    private Long id;
    private String cowId;
    private String eventId;
    private String eventType;
    private String title;
    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> detail;
    /** MEASURED（人工/设备实测） / INFERRED（AI 推断） / MANUAL（人工录入） */
    private String stateNature;
    private LocalDateTime eventTime;
    private LocalDateTime createTime;
}
