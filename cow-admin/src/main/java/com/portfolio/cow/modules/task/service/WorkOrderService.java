package com.portfolio.cow.modules.task.service;

import com.portfolio.cow.common.BizException;
import com.portfolio.cow.common.ResultCode;
import com.portfolio.cow.modules.task.entity.WorkOrder;
import com.portfolio.cow.modules.task.mapper.WorkOrderMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.OptimisticLockingFailureException;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ThreadLocalRandom;

/**
 * 工单状态机。合法流转写死在 TRANSITIONS：
 * NEW → DISPATCHED
 * DISPATCHED → PROCESSING
 * PROCESSING → PENDING_REVIEW / CANCELLED
 * PENDING_REVIEW → CLOSED / CANCELLED
 * 非法流转抛 BizException；所有变更走 MyBatis-Plus 乐观锁（@Version），
 * 更新 0 行即并发冲突 → OptimisticLockingFailureException → 409，禁止 last-write-wins。
 */
@Service
@RequiredArgsConstructor
public class WorkOrderService {

    private static final Map<String, Set<String>> TRANSITIONS = Map.of(
            WorkOrder.STATE_NEW, Set.of(WorkOrder.STATE_DISPATCHED),
            WorkOrder.STATE_DISPATCHED, Set.of(WorkOrder.STATE_PROCESSING),
            WorkOrder.STATE_PROCESSING, Set.of(WorkOrder.STATE_PENDING_REVIEW, WorkOrder.STATE_CANCELLED),
            WorkOrder.STATE_PENDING_REVIEW, Set.of(WorkOrder.STATE_CLOSED, WorkOrder.STATE_CANCELLED)
    );

    private final WorkOrderMapper workOrderMapper;

    private static final Set<String> TYPES = Set.of(WorkOrder.TYPE_BREEDING_REVIEW, WorkOrder.TYPE_VET_CHECK, WorkOrder.TYPE_DEVICE_REPAIR);
    private static final Set<String> PRIORITIES = Set.of("HIGH", "NORMAL", "LOW");

    /** 手工创建工单（供牧场智能体 create_work_order 工具回调，走 task:create 权限） */
    public WorkOrder create(WorkOrder order) {
        if (order.getType() == null || !TYPES.contains(order.getType())) {
            throw new BizException(ResultCode.BAD_REQUEST.getCode(),
                    "非法工单类型: " + order.getType());
        }
        if (!StringUtils.hasText(order.getDescription())) {
            throw new BizException(ResultCode.BAD_REQUEST.getCode(), "description 不能为空");
        }
        order.setId(null);
        order.setOrderNo("WO" + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMddHHmmss"))
                + String.format("%05d", ThreadLocalRandom.current().nextInt(100000)));
        order.setState(WorkOrder.STATE_NEW);
        order.setPriority(PRIORITIES.contains(order.getPriority()) ? order.getPriority() : "NORMAL");
        order.setAssigneeId(null);
        order.setCreateTime(LocalDateTime.now());
        order.setUpdateTime(LocalDateTime.now());
        workOrderMapper.insert(order);
        return order;
    }

    public WorkOrder assign(Long id, Long assigneeId, Integer version) {
        WorkOrder order = mustGet(id);
        assertTransition(order.getState(), WorkOrder.STATE_DISPATCHED);
        if (assigneeId == null) {
            throw new BizException(ResultCode.BAD_REQUEST.getCode(), "assigneeId 不能为空");
        }
        order.setAssigneeId(assigneeId);
        return doUpdate(order, WorkOrder.STATE_DISPATCHED, version);
    }

    public WorkOrder start(Long id, Integer version) {
        WorkOrder order = mustGet(id);
        assertTransition(order.getState(), WorkOrder.STATE_PROCESSING);
        return doUpdate(order, WorkOrder.STATE_PROCESSING, version);
    }

    public WorkOrder submitReview(Long id, String result, Integer version) {
        WorkOrder order = mustGet(id);
        assertTransition(order.getState(), WorkOrder.STATE_PENDING_REVIEW);
        if (StringUtils.hasText(result)) {
            order.setDescription(order.getDescription() + "\n[处理反馈] " + result);
        }
        return doUpdate(order, WorkOrder.STATE_PENDING_REVIEW, version);
    }

    public WorkOrder review(Long id, boolean approve, String reviewResult,
                            String reviewedBy, Integer version) {
        WorkOrder order = mustGet(id);
        String target = approve ? WorkOrder.STATE_CLOSED : WorkOrder.STATE_CANCELLED;
        assertTransition(order.getState(), target);
        order.setReviewResult(reviewResult);
        order.setReviewedBy(reviewedBy);
        order.setReviewedAt(LocalDateTime.now());
        return doUpdate(order, target, version);
    }

    public WorkOrder cancel(Long id, String reason, Integer version) {
        WorkOrder order = mustGet(id);
        assertTransition(order.getState(), WorkOrder.STATE_CANCELLED);
        order.setReviewResult("取消原因: " + reason);
        order.setReviewedAt(LocalDateTime.now());
        return doUpdate(order, WorkOrder.STATE_CANCELLED, version);
    }

    private WorkOrder mustGet(Long id) {
        WorkOrder order = workOrderMapper.selectById(id);
        if (order == null) {
            throw new BizException(ResultCode.NOT_FOUND.getCode(), "工单不存在: " + id);
        }
        return order;
    }

    private void assertTransition(String from, String to) {
        Set<String> allowed = TRANSITIONS.getOrDefault(from, Set.of());
        if (!allowed.contains(to)) {
            throw new BizException(ResultCode.BAD_REQUEST.getCode(),
                    "非法状态流转: " + from + " → " + to);
        }
    }

    private WorkOrder doUpdate(WorkOrder order, String targetState, Integer version) {
        if (version == null) {
            throw new BizException(ResultCode.BAD_REQUEST.getCode(),
                    "缺少 version，无法做乐观锁校验");
        }
        order.setState(targetState);
        order.setVersion(version); // 客户端携带的读取版本，updateById 时 MP 自动 +1 并校验
        order.setUpdateTime(LocalDateTime.now());
        int rows = workOrderMapper.updateById(order);
        if (rows == 0) {
            throw new OptimisticLockingFailureException("work_order " + order.getId() + " version conflict");
        }
        return workOrderMapper.selectById(order.getId());
    }
}
