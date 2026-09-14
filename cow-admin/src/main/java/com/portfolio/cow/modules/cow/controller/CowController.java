package com.portfolio.cow.modules.cow.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.portfolio.cow.common.BizException;
import com.portfolio.cow.common.PageResult;
import com.portfolio.cow.common.Result;
import com.portfolio.cow.common.ResultCode;
import com.portfolio.cow.modules.cow.entity.CowProfile;
import com.portfolio.cow.modules.cow.entity.CowTimeline;
import com.portfolio.cow.modules.cow.entity.TwinState;
import com.portfolio.cow.modules.cow.mapper.CowProfileMapper;
import com.portfolio.cow.modules.cow.mapper.CowTimelineMapper;
import com.portfolio.cow.modules.cow.mapper.TwinStateMapper;
import com.portfolio.cow.modules.system.annotation.OperLog;
import lombok.RequiredArgsConstructor;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class CowController {

    private final CowProfileMapper cowProfileMapper;
    private final CowTimelineMapper cowTimelineMapper;
    private final TwinStateMapper twinStateMapper;

    @GetMapping("/cows")
    public Result<PageResult<CowProfile>> page(@RequestParam(defaultValue = "1") long page,
                                               @RequestParam(defaultValue = "10") long size,
                                               @RequestParam(required = false) String keyword,
                                               @RequestParam(required = false) String zone) {
        LambdaQueryWrapper<CowProfile> wrapper = new LambdaQueryWrapper<CowProfile>()
                .and(StringUtils.hasText(keyword), w -> w
                        .like(CowProfile::getCowId, keyword)
                        .or().like(CowProfile::getEarTag, keyword))
                .eq(StringUtils.hasText(zone), CowProfile::getZone, zone)
                .orderByAsc(CowProfile::getCowId);
        return Result.ok(PageResult.of(cowProfileMapper.selectPage(new Page<>(page, size), wrapper)));
    }

    @PostMapping("/cows")
    @OperLog(title = "新增牛档案")
    public Result<CowProfile> create(@RequestBody CowProfile cow) {
        if (!StringUtils.hasText(cow.getCowId())) {
            throw new BizException(ResultCode.BAD_REQUEST.getCode(), "cowId 不能为空");
        }
        Long exists = cowProfileMapper.selectCount(
                new LambdaQueryWrapper<CowProfile>().eq(CowProfile::getCowId, cow.getCowId()));
        if (exists > 0) {
            throw new BizException(ResultCode.CONFLICT.getCode(), "cowId 已存在");
        }
        cow.setId(null);
        if (!StringUtils.hasText(cow.getBarnId())) {
            cow.setBarnId("20号牛棚");
        }
        cow.setStatus(StringUtils.hasText(cow.getStatus()) ? cow.getStatus() : "ACTIVE");
        cow.setCreateTime(LocalDateTime.now());
        cowProfileMapper.insert(cow);
        return Result.ok(cow);
    }

    @PutMapping("/cows/{id}")
    @OperLog(title = "修改牛档案")
    public Result<CowProfile> update(@PathVariable Long id, @RequestBody CowProfile cow) {
        CowProfile db = cowProfileMapper.selectById(id);
        if (db == null) {
            throw new BizException(ResultCode.NOT_FOUND);
        }
        cow.setId(id);
        cow.setCowId(db.getCowId());
        cowProfileMapper.updateById(cow);
        return Result.ok(cowProfileMapper.selectById(id));
    }

    @DeleteMapping("/cows/{id}")
    @OperLog(title = "删除牛档案")
    public Result<Void> delete(@PathVariable Long id) {
        cowProfileMapper.deleteById(id);
        return Result.ok();
    }

    /** 单牛详情：档案 + 当前孪生状态 */
    @GetMapping("/cows/{cowId}")
    public Result<Map<String, Object>> detail(@PathVariable String cowId) {
        CowProfile cow = cowProfileMapper.selectOne(
                new LambdaQueryWrapper<CowProfile>().eq(CowProfile::getCowId, cowId));
        if (cow == null) {
            throw new BizException(ResultCode.NOT_FOUND.getCode(), "牛只不存在: " + cowId);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("profile", cow);
        data.put("twinState", twinStateMapper.selectById(cowId));
        return Result.ok(data);
    }

    /** 单牛时间线（含迟到事件，按事件发生时间倒序） */
    @GetMapping("/cows/{cowId}/timeline")
    public Result<List<CowTimeline>> timeline(@PathVariable String cowId,
                                              @RequestParam(defaultValue = "100") int limit) {
        List<CowTimeline> list = cowTimelineMapper.selectList(
                new LambdaQueryWrapper<CowTimeline>()
                        .eq(CowTimeline::getCowId, cowId)
                        .orderByDesc(CowTimeline::getEventTime)
                        .last("LIMIT " + Math.min(limit, 500)));
        return Result.ok(list);
    }

    /** 批量查询当前孪生状态，供牛棚二维图轮询 */
    @GetMapping("/twin/states")
    public Result<List<TwinState>> twinStates() {
        return Result.ok(twinStateMapper.selectList(null));
    }
}
