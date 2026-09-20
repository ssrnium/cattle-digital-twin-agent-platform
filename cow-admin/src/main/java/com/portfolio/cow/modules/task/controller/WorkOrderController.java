package com.portfolio.cow.modules.task.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.portfolio.cow.common.BizException;
import com.portfolio.cow.common.PageResult;
import com.portfolio.cow.common.Result;
import com.portfolio.cow.common.ResultCode;
import com.portfolio.cow.modules.system.annotation.OperLog;
import com.portfolio.cow.modules.task.entity.WorkOrder;
import com.portfolio.cow.modules.task.mapper.WorkOrderMapper;
import com.portfolio.cow.modules.task.service.WorkOrderService;
import com.portfolio.cow.security.LoginUser;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/tasks")
@RequiredArgsConstructor
public class WorkOrderController {

    private final WorkOrderMapper workOrderMapper;
    private final WorkOrderService workOrderService;

    /** 手工创建工单：仅 task:create 权限；SERVICE 角色（svc-agent）必须携带 X-Action-Id 审批凭证 */
    @PostMapping
    @PreAuthorize("hasAuthority('task:create')")
    @OperLog(title = "手工创建工单")
    public Result<WorkOrder> create(@RequestBody WorkOrder order,
                                    @RequestHeader(value = "X-Action-Id", required = false) String actionId) {
        if (isServiceAccount()) {
            return Result.ok(workOrderService.createByAgent(order, actionId));
        }
        return Result.ok(workOrderService.create(order));
    }

    /** 调用者是 SERVICE 角色（智能体服务账号）时，建单走 PENDING_ACTION 强制审批 */
    private boolean isServiceAccount() {
        Object principal = SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        return principal instanceof LoginUser u
                && u.getRoles() != null && u.getRoles().contains("SERVICE");
    }

    @GetMapping
    public Result<PageResult<WorkOrder>> page(@RequestParam(defaultValue = "1") long page,
                                              @RequestParam(defaultValue = "10") long size,
                                              @RequestParam(required = false) String state,
                                              @RequestParam(required = false) String type,
                                              @RequestParam(required = false) Long assigneeId) {
        LambdaQueryWrapper<WorkOrder> wrapper = new LambdaQueryWrapper<WorkOrder>()
                .eq(StringUtils.hasText(state), WorkOrder::getState, state)
                .eq(StringUtils.hasText(type), WorkOrder::getType, type)
                .eq(assigneeId != null, WorkOrder::getAssigneeId, assigneeId)
                .orderByDesc(WorkOrder::getCreateTime);
        return Result.ok(PageResult.of(workOrderMapper.selectPage(new Page<>(page, size), wrapper)));
    }

    @GetMapping("/{id}")
    public Result<WorkOrder> detail(@PathVariable Long id) {
        WorkOrder order = workOrderMapper.selectById(id);
        if (order == null) {
            throw new BizException(ResultCode.NOT_FOUND);
        }
        return Result.ok(order);
    }

    @PostMapping("/{id}/assign")
    @OperLog(title = "分派工单")
    public Result<WorkOrder> assign(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        return Result.ok(workOrderService.assign(id,
                toLong(body.get("assigneeId")), toInt(body.get("version"))));
    }

    @PostMapping("/{id}/start")
    @OperLog(title = "开始处理工单")
    public Result<WorkOrder> start(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        return Result.ok(workOrderService.start(id, toInt(body.get("version"))));
    }

    @PostMapping("/{id}/submit-review")
    @OperLog(title = "提交工单复查")
    public Result<WorkOrder> submitReview(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        return Result.ok(workOrderService.submitReview(id,
                (String) body.get("result"), toInt(body.get("version"))));
    }

    @PostMapping("/{id}/review")
    @OperLog(title = "工单复查")
    public Result<WorkOrder> review(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        boolean approve = Boolean.TRUE.equals(body.get("approved"));
        return Result.ok(workOrderService.review(id, approve,
                (String) body.get("reviewResult"), currentUsername(), toInt(body.get("version"))));
    }

    @PostMapping("/{id}/cancel")
    @OperLog(title = "取消工单")
    public Result<WorkOrder> cancel(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        return Result.ok(workOrderService.cancel(id,
                (String) body.get("reason"), toInt(body.get("version"))));
    }

    private String currentUsername() {
        Object principal = SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        return principal instanceof LoginUser u ? u.getUsername() : "unknown";
    }

    private Long toLong(Object o) {
        return o == null ? null : Long.valueOf(String.valueOf(o));
    }

    private Integer toInt(Object o) {
        return o == null ? null : Integer.valueOf(String.valueOf(o));
    }
}
