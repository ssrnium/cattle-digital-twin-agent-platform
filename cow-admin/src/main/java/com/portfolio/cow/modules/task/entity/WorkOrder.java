package com.portfolio.cow.modules.task.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.annotation.Version;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("work_order")
public class WorkOrder {

    public static final String TYPE_BREEDING_REVIEW = "BREEDING_REVIEW";
    public static final String TYPE_VET_CHECK = "VET_CHECK";
    public static final String TYPE_DEVICE_REPAIR = "DEVICE_REPAIR";

    public static final String STATE_NEW = "NEW";
    public static final String STATE_DISPATCHED = "DISPATCHED";
    public static final String STATE_PROCESSING = "PROCESSING";
    public static final String STATE_PENDING_REVIEW = "PENDING_REVIEW";
    public static final String STATE_CLOSED = "CLOSED";
    public static final String STATE_CANCELLED = "CANCELLED";

    @TableId(type = IdType.AUTO)
    private Long id;
    private String orderNo;
    private String type;
    private String cowId;
    private String deviceId;
    private String sourceEventId;
    private String state;
    private String priority;
    private Long assigneeId;
    private String description;
    private String reviewResult;
    private String reviewedBy;
    private LocalDateTime reviewedAt;

    /** 乐观锁：工单并发操作禁止 last-write-wins */
    @Version
    private Integer version;

    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
