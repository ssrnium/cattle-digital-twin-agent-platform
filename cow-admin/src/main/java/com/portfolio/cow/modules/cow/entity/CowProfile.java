package com.portfolio.cow.modules.cow.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("cow_profile")
public class CowProfile {

    @TableId(type = IdType.AUTO)
    private Long id;
    /** 业务唯一编号，如 COW-0001 */
    private String cowId;
    private String earTag;
    private String barnId;
    private String zone;
    private String status;
    private LocalDateTime createTime;
}
